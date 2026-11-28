"""
Unified Production Cloud Sync Worker (Consolidated Stage 1 & Stage 2)
=====================================================================
Single consolidated ingestion and synchronization engine:
- Channel A: LinkedIn Live Feeds (India tech clusters)
- Channel B: ATS Direct APIs (SmartRecruiters, Greenhouse, Lever, Ashby, Workday)
- Channel C: Company Portals & XML Sitemaps (Fast concurrent discovery)
- Stage 2: Structured AI Enrichment (Groq openai/gpt-oss-20b with 429 backoff)

Guarantees:
1. Strict Upfront India Country Elimination Filter (eliminates US, UK, EU foreign jobs).
2. Work Mode Normalization (Remote, Hybrid, On-site). Never NULL or 'None'.
3. Synchronized Experience Text matching min_exp and max_exp (never stale "1 - 3 Years").
4. Real-time Admin Sync Tracking in PostgreSQL (sync_job_states table).
5. Clean PostgreSQL Persistence with ON CONFLICT (url) DO UPDATE SET.
"""

import sys
import os
import re
import time
import json
import uuid
import gc
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import psycopg2
from psycopg2.extras import DictCursor, execute_values
import asyncio

try:
    from crawl4ai import AsyncWebCrawler
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False

DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:MySecretPassword123@127.0.0.1:5432/career_portal")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-20b"

def get_effective_gemini_key():
    global GEMINI_API_KEY
    if GEMINI_API_KEY:
        return GEMINI_API_KEY
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT api_key FROM users WHERE api_key IS NOT NULL AND api_key != '' LIMIT 1;")
        row = cur.fetchone()
        if row and row[0]:
            GEMINI_API_KEY = row[0].strip()
        cur.close()
        conn.close()
    except Exception:
        pass
    return GEMINI_API_KEY

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8"
}

INDIA_KEYWORDS = [
    "india", "bengaluru", "bangalore", "hyderabad", "chennai", "pune", "mumbai",
    "noida", "gurugram", "gurgaon", "delhi", "kolkata", "ahmedabad", "kochi",
    "coimbatore", "chandigarh", "indore", "jaipur", "trivandrum", "thiruvananthapuram"
]

FOREIGN_EXCLUSIONS = [
    "/us-en/", "/ca-en/", "/ca-fr/", "/emea-de/", "/emea-fr/", "/emea-es/", "/emea-nl/",
    "/latam-es/", "/latam-pt/", "/apj-jp/", "/apj-ph/", "/apj-cn/", "/uki-en/",
    "united states", "usa", "canada", "united kingdom", "germany", "france", "australia",
    "brazil", "spain", "italy", "netherlands", "singapore", "japan", "ireland", "mexico",
    "/us/", "/de/", "/fr/", "/uk/", "/ca/", "/au/", "/nl/", "/es/", "/it/",
    "/london/", "/manchester/", "/katowice/", "/warsaw/", "/utrecht/", "/amsterdam/",
    "/paris/", "/berlin/", "/munich/", "/tokyo/", "/sydney/", "/toronto/", "/new-york/",
    "/chicago/", "/san-francisco/", "/austin/", "/seattle/", "/boston/", "/taipei/", "/kowloon/"
]

def get_db():
    return psycopg2.connect(DB_URL)

def sanitize_str(val):
    if val is None:
        return ""
    return str(val).replace('\x00', '').replace('\0', '').strip()

def detect_work_mode(text, url=""):
    combined = f"{url} {text}".lower()
    if any(k in combined for k in ["-remote", "/remote", "work-from-home", "wfh", "100% remote", "fully remote"]):
        return "Remote"
    if any(k in combined for k in ["-hybrid", "/hybrid", "hybrid work", "hybrid remote"]):
        return "Hybrid"
    if any(k in combined for k in ["-onsite", "/onsite", "on-site", "in-office"]):
        return "On-site"
    if "remote" in combined:
        return "Remote"
    if "hybrid" in combined:
        return "Hybrid"
    return "On-site"

def is_india_eligible(loc_text, title_text="", url=""):
    combined = f"{url} {loc_text} {title_text}".lower()
    has_india = any(k in combined for k in INDIA_KEYWORDS)
    is_foreign = any(f in combined for f in FOREIGN_EXCLUSIONS) or any(
        re.search(rf"\b{re.escape(term)}\b", combined)
        for term in [
            "china", "chengdu", "shanghai", "beijing", "poland", "katowice", "warsaw",
            "japan", "tokyo", "austria", "graz", "germany", "berlin", "munich",
            "france", "paris", "israel", "tel aviv", "korea", "seoul", "taiwan", "taipei",
            "singapore", "australia", "sydney", "melbourne", "london", "canada", "toronto",
            "united states", "usa", "austin", "chicago", "new york", "san francisco", "seattle",
            "boston", "dallas", "ireland", "dublin", "netherlands", "amsterdam", "greece", "athens"
        ]
    )
    is_remote = "remote" in combined or any(k in combined for k in ["-remote", "/remote", "work-from-home", "wfh", "100% remote", "fully remote"])

    if is_foreign and not has_india:
        if is_remote:
            return True, "Remote", "Global Remote"
        return False, "On-site", (loc_text or "Abroad")
    if has_india:
        return True, detect_work_mode(combined, url), (loc_text or "India")
    if is_remote:
        return True, "Remote", (loc_text or "Remote")
    return False, "On-site", (loc_text or "Abroad")

def is_hex_garbage(title):
    words = (title or "").strip().split()
    if not words:
        return True
    short_words = sum(1 for w in words if len(w) <= 2)
    if len(words) >= 4 and (short_words / len(words)) >= 0.5:
        return True
    if re.match(r'^[a-fA-F0-9\s_-]{10,}$', title):
        return True
    return False

TECH_ANCHORS = {
    "engineer", "engineering", "developer", "architect", "programmer", "coder",
    "sde", "swe", "fde", "mts", "finops", "devops", "cloud", "platform", "systems",
    "infrastructure", "infra", "sre", "site reliability", "quant", "quantitative",
    "data engineer", "data scientist", "mlops", "machine learning", "deep learning",
    "ai developer", "ai engineer", "genai", "generative ai", "llm", "agentic",
    "founding engineer", "security engineer", "penetration tester", "cybersecurity",
    "qa engineer", "sdet", "automation engineer", "backend", "frontend", "full stack",
    "fullstack", "software", "tech lead", "technical lead", "cto", "vp engineering",
    "director engineering", "firmware", "embedded", "kernel", "dba", "database administrator",
    "solutions architect", "enterprise architect", "cloud architect", "network engineer",
    "data analyst", "system administrator", "sysadmin", "devsecops", "test engineer"
}

NON_TECH_PATTERNS = [
    r"\bretail\b", r"\bsales\b", r"\bstore\b", r"\bcashier\b", r"\bpatient\b",
    r"\bcare technician\b", r"\bscheduler\b", r"\bmerchandiser\b", r"\bofficer sales\b",
    r"\brecruiter\b", r"\bsourcer\b", r"\btalent acquisition\b", r"\bhuman resources\b",
    r"\bhr\b", r"\bmarketing\b", r"\bcontent\b", r"\bcopywriter\b", r"\blegal\b",
    r"\bparalegal\b", r"\baccountant\b", r"\bbookkeeper\b", r"\btax\b", r"\baudit\b",
    r"\bpayroll\b", r"\bloan\b", r"\bcredit\b", r"\bbranch manager\b", r"\breceptionist\b",
    r"\boffice manager\b", r"\bassistant\b", r"\bcustomer support\b", r"\bcall center\b",
    r"\bnurse\b", r"\bphysician\b", r"\bdriver\b", r"\bwarehouse\b", r"\bchronik\b",
    r"\bpanel talk\b", r"\bbilder\b", r"\bpress release\b", r"\bphoto\b",
    r"\bopportunity at\b", r"\btechnical opportunity at\b", r"^\?lang=", r"\?domain="
]

def is_valid_tech_title(title, url=""):
    t_low = (title or "").lower().strip()
    u_low = (url or "").lower()

    if len(t_low) < 4:
        return False, "Title too short"
    if "?" in t_low:
        return False, "Query string artifact in title"
    if is_hex_garbage(title):
        return False, "Hex hash garbage title"
    for pattern in NON_TECH_PATTERNS:
        if re.search(pattern, t_low):
            return False, f"Matches non-tech pattern: {pattern}"
    has_anchor = any(re.search(rf"\b{re.escape(anchor)}\b", t_low) for anchor in TECH_ANCHORS)
    if not has_anchor:
        return False, "Lacks technical anchor"
    return True, "Valid Tech Title"

def extract_semantic_title_from_url(url, company=""):
    clean_url = url.split("?")[0].split("#")[0].rstrip("/")
    parsed = urllib.parse.urlparse(clean_url)
    segments = [s for s in parsed.path.split("/") if s]

    filler_slugs = {
        "job", "jobs", "career", "careers", "posting", "postings", "requisition", "requisitions",
        "detail", "details", "view", "apply", "en", "us", "in", "uk", "de", "fr", "ca", "au",
        "global", "corporate", "all", "external", "search", "category", "location", "openings"
    }

    title_candidate = None
    for seg in reversed(segments):
        seg_lower = seg.lower()
        if seg_lower in filler_slugs:
            continue
        if seg.isdigit():
            continue
        if re.match(r'^(?:r|jr|req|job|g|p)[-_]?\d+$', seg_lower):
            continue
        if re.match(r'^[a-f0-9]{10,}$', seg_lower):
            continue
        if seg_lower in {"austin", "perth", "shanghai", "graz", "chennai", "bengaluru", "hyderabad", "mumbai", "pune", "delhi"}:
            continue

        cleaned = re.sub(r'[\d_-]+', ' ', seg).strip()
        cleaned = re.sub(r'\b(chn|kor|aut|isr|jid|externalenglobal)\b', '', cleaned, flags=re.I).strip()
        if len(cleaned) >= 4 and not is_hex_garbage(cleaned):
            title_candidate = cleaned.title()
            break

    if not title_candidate:
        return None, "No semantic role title in URL"

    return title_candidate, "Parsed from slug"

TECH_TOKENS = [
    "python", "fastapi", "flask", "django", "langgraph", "langchain", "llamaindex",
    "mcp", "react", "rag", "pgvector", "qdrant", "chromadb", "pinecone", "redis",
    "kafka", "docker", "kubernetes", "argocd", "opentelemetry", "openlit", "gemini",
    "aws bedrock", "azure openai", "postgresql", "mysql", "sql", "pandas", "numpy",
    "agentic ai", "prompt engineering", "embeddings", "git", "gitops", "aws", "azure",
    "gcp", "google cloud", "machine learning", "deep learning", "nlp", "golang", "java",
    "c++", "c#", "rust", "typescript", "javascript", "linux", "ci/cd", "terraform",
    "rest api", "graphql", "microservices", "airflow", "spark", "hadoop", "elasticsearch",
    "solidity", "pytorch", "tensorflow", "snowflake", "databricks", "scikit-learn",
    "devops", "finops", "sre", "cloud", "apis", "node.js", "angular", "vue"
]

def segregate_skills(title, description, existing_skills=None):
    desc_clean = (description or "").lower()
    title_clean = (title or "").lower()

    must_have = []
    nice_to_have = []

    req_pattern = r"(?:minimum qualifications|basic qualifications|required qualifications|requirements|what you(?:'ll)? need|must have|core requirements)(.*?)(?:preferred qualifications|nice to have|bonus|desired|what we offer|responsibilities|\Z)"
    pref_pattern = r"(?:preferred qualifications|nice to have|bonus points|desired skills|good to have)(.*?)(?:responsibilities|benefits|about us|\Z)"

    req_match = re.search(req_pattern, desc_clean, re.DOTALL)
    pref_match = re.search(pref_pattern, desc_clean, re.DOTALL)

    req_corpus = req_match.group(1) if req_match else desc_clean[:2500]
    pref_corpus = pref_match.group(1) if pref_match else ""

    found_skills = set()
    for token in TECH_TOKENS:
        if re.search(rf"\b{re.escape(token)}\b", title_clean):
            must_have.append(token)
            found_skills.add(token)
        elif pref_corpus and re.search(rf"\b{re.escape(token)}\b", pref_corpus):
            nice_to_have.append(token)
            found_skills.add(token)
        elif re.search(rf"\b{re.escape(token)}\b", req_corpus):
            must_have.append(token)
            found_skills.add(token)

    if existing_skills and isinstance(existing_skills, list):
        for s in existing_skills:
            s_clean = str(s).lower().strip()
            if s_clean and s_clean not in found_skills:
                if len(must_have) < 5:
                    must_have.append(s_clean)
                else:
                    nice_to_have.append(s_clean)
                found_skills.add(s_clean)

    for kw in ["python", "java", "golang", "react", "cloud", "aws", "azure", "docker", "kubernetes", "sql", "snowflake"]:
        if re.search(rf"\b{kw}\b", title_clean) and kw not in must_have:
            must_have.insert(0, kw)
            found_skills.add(kw)

    if not must_have and found_skills:
        all_sorted = list(found_skills)
        must_have = all_sorted[:4]
        nice_to_have = all_sorted[4:]

    if not must_have and not found_skills:
        # Fallback based on job title semantics for listings with short stub descriptions
        if any(k in title_clean for k in ["data engineer", "data platform", "etl"]):
            must_have = ["data engineering", "sql", "python", "etl"]
            nice_to_have = ["spark", "cloud", "data pipelines"]
        elif any(k in title_clean for k in ["ai", "machine learning", "ml", "deep learning", "nlp", "llm", "genai"]):
            must_have = ["machine learning", "python", "artificial intelligence", "algorithms"]
            nice_to_have = ["deep learning", "pytorch", "cloud"]
        elif any(k in title_clean for k in ["devops", "sre", "platform", "infrastructure", "systems", "cloud"]):
            must_have = ["devops", "cloud", "linux", "ci/cd"]
            nice_to_have = ["docker", "kubernetes", "terraform"]
        elif any(k in title_clean for k in ["frontend", "ui", "web", "react", "angular"]):
            must_have = ["frontend", "javascript", "react", "html/css"]
            nice_to_have = ["typescript", "rest api", "ui design"]
        elif any(k in title_clean for k in ["backend", "server", "microservice"]):
            must_have = ["backend", "python", "rest api", "sql"]
            nice_to_have = ["microservices", "docker", "distributed systems"]
        elif any(k in title_clean for k in ["full stack", "fullstack"]):
            must_have = ["full stack", "javascript", "python", "react"]
            nice_to_have = ["docker", "sql", "rest api"]
        elif any(k in title_clean for k in ["security", "cyber", "infosec"]):
            must_have = ["cybersecurity", "security architecture", "vulnerability assessment"]
            nice_to_have = ["cloud security", "compliance", "linux"]
        elif any(k in title_clean for k in ["embedded", "firmware", "hardware", "iot"]):
            must_have = ["embedded systems", "c++", "c", "rtos"]
            nice_to_have = ["linux", "microcontrollers", "firmware"]
        elif any(k in title_clean for k in ["qa", "sdet", "test", "quality"]):
            must_have = ["test automation", "qa", "python", "test strategies"]
            nice_to_have = ["ci/cd", "api testing", "selenium"]
        elif any(k in title_clean for k in ["architect", "principal", "staff"]):
            must_have = ["software architecture", "system design", "distributed systems", "apis"]
            nice_to_have = ["cloud", "microservices", "technical leadership"]
        else:
            must_have = ["software engineering", "data structures", "system design", "problem solving"]
            nice_to_have = ["git", "ci/cd", "agile"]

    all_skills = list(dict.fromkeys(must_have + nice_to_have))
    return must_have, nice_to_have, all_skills

def parse_exp(text):
    if not text:
        return None, None
    m = re.search(r'(\d+)\s*(?:-|to)\s*(\d+)\s*(?:years?|yrs?)', text, re.I)
    if m:
        try:
            return float(m.group(1)), float(m.group(2))
        except Exception:
            pass
    m2 = re.search(r'(\d+)\+?\s*(?:years?|yrs?)', text, re.I)
    if m2:
        try:
            return float(m2.group(1)), None
        except Exception:
            pass
    return None, None

def format_exp_text(min_e, max_e):
    if min_e is not None and max_e is not None and min_e != max_e:
        return f"{int(min_e)} - {int(max_e)} Years"
    elif min_e is not None and max_e is not None and min_e == max_e:
        return f"{int(min_e)} Years"
    elif min_e is not None:
        return f"{int(min_e)}+ Years"
    elif max_e is not None:
        return f"Up to {int(max_e)} Years"
    return "Not Specified"

def fetch_url(url, timeout=12):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return resp.read().decode("utf-8", errors="ignore")
    except Exception:
        pass
    return None

def init_sync_tables():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sync_job_states (
                id VARCHAR(64) PRIMARY KEY,
                status VARCHAR(32) NOT NULL,
                stage VARCHAR(128) NOT NULL,
                progress_pct INT NOT NULL DEFAULT 0,
                total_ingested INT NOT NULL DEFAULT 0,
                new_jobs_added INT NOT NULL DEFAULT 0,
                started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP WITH TIME ZONE,
                error_message TEXT
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Warning initializing sync table: {e}")

def update_sync_state(sync_id, status, stage, progress_pct, total_ingested, new_jobs, error_msg=None):
    try:
        conn = get_db()
        cur = conn.cursor()
        comp_time = "CURRENT_TIMESTAMP" if status in ["COMPLETED", "FAILED"] else "NULL"
        cur.execute(f"""
            INSERT INTO sync_job_states (id, status, stage, progress_pct, total_ingested, new_jobs_added, started_at, completed_at, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, {comp_time}, %s)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                stage = EXCLUDED.stage,
                progress_pct = EXCLUDED.progress_pct,
                total_ingested = EXCLUDED.total_ingested,
                new_jobs_added = EXCLUDED.new_jobs_added,
                completed_at = CASE WHEN EXCLUDED.status IN ('COMPLETED', 'FAILED') THEN CURRENT_TIMESTAMP ELSE sync_job_states.completed_at END,
                error_message = EXCLUDED.error_message;
        """, (sync_id, status, stage, progress_pct, total_ingested, new_jobs, error_msg))
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass

# ---------------------------------------------------------------------------
# STAGE 2: DUAL AI EXTRACTION & ENRICHMENT (GEMINI 2.0 FLASH + GROQ FALLBACK)
# ---------------------------------------------------------------------------
def _call_gemini_extraction(prompt):
    g_key = get_effective_gemini_key()
    if not g_key:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={g_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.1
        }
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
            return parsed
    except Exception as e:
        return None

def _call_groq_extraction(prompt):
    if not GROQ_API_KEY:
        return None
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "You extract structured job information. Respond strictly in valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    req = urllib.request.Request(GROQ_URL, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return json.loads(data["choices"][0]["message"]["content"])
    except urllib.error.HTTPError as e:
        if e.code == 429:
            time.sleep(8)
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return json.loads(data["choices"][0]["message"]["content"])
            except Exception:
                return None
        return None
    except Exception:
        return None

def enrich_job_with_ai(title, company_name, description_text):
    prompt = f"""Extract structured job data as JSON with keys:
- "skills": comprehensive array of ALL technical skills, programming languages, frameworks, cloud platforms, databases, tools, APIs, libraries, and technical concepts mentioned anywhere in the job description
- "must_have_skills": array of all mandatory core technical skills explicitly stated in the requirements/qualifications section
- "nice_to_have_skills": array of all secondary/preferred/bonus skills explicitly stated
- "min_exp": float or integer (or null)
- "max_exp": float or integer (or null)
- "work_mode": "Remote", "Hybrid", or "On-site"
- "summary": 2-sentence summary of the role

Company: {company_name}
Title: {title}
Description:
{description_text[:3500]}
"""
    # 1. Primary engine: Gemini 2.0 Flash
    gemini_res = _call_gemini_extraction(prompt)
    if gemini_res and isinstance(gemini_res, dict) and ("skills" in gemini_res or "must_have_skills" in gemini_res):
        return gemini_res

    # 2. Resilient fallback engine: Groq
    groq_res = _call_groq_extraction(prompt)
    if groq_res and isinstance(groq_res, dict) and ("skills" in groq_res or "must_have_skills" in groq_res):
        return groq_res

    return None

def run_stage2_enrichment_batch(limit=60):
    """
    Enriches un-enriched active jobs in company_jobs using Gemini or Groq.
    Operates in targeted batches to maintain API quota compliance.
    """
    print(f"\n[STAGE 2] Running AI Enrichment Batch (Target: up to {limit} jobs)...")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, company_name, title, location, work_mode, raw_description, url
        FROM company_jobs
        WHERE is_active = TRUE 
          AND (skills_required IS NULL OR skills_required::text = '[]' OR min_exp IS NULL)
        ORDER BY created_at DESC
        LIMIT %s;
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        print("[STAGE 2] All active jobs are already enriched.")
        return 0

    print(f"[STAGE 2] Enriching {len(rows)} pending jobs with Groq ({GROQ_MODEL})...")
    enriched_count = 0
    for r in rows:
        j_id, company, title, loc, w_mode, raw_desc, url = r
        desc_snippet = raw_desc or f"Role: {title} at {company}."
        ext = enrich_job_with_ai(title, company, desc_snippet)
        if ext:
            skills = ext.get("skills", [])
            m_s = ext.get("must_have_skills", [])
            n_s = ext.get("nice_to_have_skills", [])
            if not m_s and not n_s:
                m_s, n_s, skills = segregate_skills(title, desc_snippet, skills)
            min_e = ext.get("min_exp")
            max_e = ext.get("max_exp")
            ai_mode = ext.get("work_mode")
            work_mode = ai_mode if ai_mode in ["Remote", "Hybrid", "On-site"] else detect_work_mode(desc_snippet, url)
            summary = ext.get("summary", desc_snippet[:400])
            exp_text = format_exp_text(min_e, max_e)

            try:
                c2 = get_db()
                k2 = c2.cursor()
                k2.execute("""
                    UPDATE company_jobs
                    SET skills_required = %s,
                        must_have_skills = %s,
                        nice_to_have_skills = %s,
                        min_exp = COALESCE(%s, min_exp),
                        max_exp = COALESCE(%s, max_exp),
                        experience_text = %s,
                        work_mode = %s,
                        raw_description = %s
                    WHERE id = %s;
                """, (json.dumps(skills), json.dumps(m_s), json.dumps(n_s), min_e, max_e, exp_text, work_mode, summary, j_id))
                c2.commit()
                k2.close()
                c2.close()
                enriched_count += 1
            except Exception:
                pass
            time.sleep(1.2) # Rate limit guard for Groq free tier
    print(f"[STAGE 2] Successfully enriched {enriched_count}/{len(rows)} jobs.")
    return enriched_count

# ---------------------------------------------------------------------------
# CHANNEL A: DEEP LINKEDIN & #HIRING STREAMS AI INGESTION
# ---------------------------------------------------------------------------
LINKEDIN_SEARCH_QUERIES = [
    # Category 1: GenAI, LLM & Agentic AI
    {"keyword": "GenAI Engineer", "location": "India"},
    {"keyword": "Generative AI Developer", "location": "Bengaluru, Karnataka, India"},
    {"keyword": "LLM Engineer", "location": "Hyderabad, Telangana, India"},
    {"keyword": "Agentic AI", "location": "India"},
    {"keyword": "LangGraph Developer", "location": "India"},
    {"keyword": "RAG Engineer", "location": "Bengaluru, Karnataka, India"},
    {"keyword": "AI Systems Engineer", "location": "Pune, Maharashtra, India"},
    {"keyword": "Prompt Engineer Python", "location": "India"},
    
    # Category 2: Python & Modern Backend
    {"keyword": "Python Developer", "location": "Bengaluru, Karnataka, India"},
    {"keyword": "FastAPI Developer", "location": "India"},
    {"keyword": "Senior Python Backend Engineer", "location": "Hyderabad, Telangana, India"},
    {"keyword": "Python Distributed Systems", "location": "India"},
    {"keyword": "Django Backend Developer", "location": "Chennai, Tamil Nadu, India"},
    {"keyword": "Backend Engineer Python", "location": "Pune, Maharashtra, India"},
    
    # Category 3: Cloud, Platform & DevOps
    {"keyword": "DevOps Cloud Engineer", "location": "Bengaluru, Karnataka, India"},
    {"keyword": "AWS Cloud Platform Engineer", "location": "India"},
    {"keyword": "Kubernetes Engineer", "location": "Pune, Maharashtra, India"},
    {"keyword": "Site Reliability Engineer", "location": "Hyderabad, Telangana, India"},
    
    # Category 4: Data Engineering & MLOps
    {"keyword": "Data Engineer Python", "location": "Bengaluru, Karnataka, India"},
    {"keyword": "Machine Learning Engineer", "location": "India"},
    {"keyword": "MLOps Engineer", "location": "Hyderabad, Telangana, India"},
    {"keyword": "Vector Database Engineer", "location": "India"},
    
    # Category 5: Direct Recruiter Hiring Posts (#Hiring Streams)
    {"keyword": "#hiring python", "location": "India"},
    {"keyword": "#hiring genai", "location": "India"},
    {"keyword": "#hiring ai engineer", "location": "India"},
    {"keyword": "#hiring backend developer", "location": "Bengaluru, Karnataka, India"},
    {"keyword": "#hiring data engineer", "location": "Hyderabad, Telangana, India"},
    {"keyword": "we are hiring python developer", "location": "India"},
    {"keyword": "we are hiring software engineer", "location": "Bengaluru, Karnataka, India"},
    {"keyword": "immediate joiner python", "location": "India"},
    {"keyword": "urgent requirement python", "location": "India"},
    {"keyword": "hiring fastapi", "location": "India"}
]

def crawl_linkedin(max_ai_enrich=100):
    all_jobs = []
    seen_urls = set()
    discovered_cards = []

    print(f"[LINKEDIN] Querying {len(LINKEDIN_SEARCH_QUERIES)} search streams & #hiring channels...")
    for idx, q in enumerate(LINKEDIN_SEARCH_QUERIES, 1):
        kw = urllib.parse.quote(q["keyword"])
        loc = urllib.parse.quote(q["location"])
        for page in range(3):
            start = page * 25
            url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={kw}&location={loc}&f_TPR=r604800&start={start}"
            body = fetch_url(url, timeout=10)
            if not body or len(body) < 500:
                break
            links = re.findall(r'href="(https://[a-z]{2,3}\.linkedin\.com/jobs/view/[^"]+)"', body)
            titles = re.findall(r'<h3 class="base-search-card__title">([^<]+)</h3>', body)
            companies = re.findall(r'<h4 class="base-search-card__subtitle">\s*<a[^>]*>([^<]+)</a>', body)
            if not companies:
                companies = re.findall(r'<h4 class="base-search-card__subtitle">\s*([^<]+)\s*</h4>', body)
            locations = re.findall(r'<span class="job-search-card__location">([^<]+)</span>', body)
            
            n = min(len(links), len(titles))
            if n == 0:
                break
            for i in range(n):
                c_title = sanitize_str(titles[i])
                c_company = sanitize_str(companies[i]) if i < len(companies) else "Technology Firm"
                c_loc = sanitize_str(locations[i]) if i < len(locations) else "India"
                raw_link = links[i].split("?")[0]
                if raw_link in seen_urls:
                    continue
                seen_urls.add(raw_link)
                
                eligible, work_mode, clean_loc = is_india_eligible(c_loc, c_title, raw_link)
                if not eligible:
                    continue
                m_id = re.search(r'-(\d{8,12})$', raw_link) or re.search(r'/view/(\d{8,12})', raw_link)
                job_id = m_id.group(1) if m_id else str(abs(hash(raw_link)) % 100000000)

                discovered_cards.append({
                    "job_id": job_id,
                    "title": c_title,
                    "company_name": c_company,
                    "location": clean_loc,
                    "work_mode": work_mode,
                    "url": raw_link,
                    "keyword": q["keyword"]
                })
            time.sleep(0.4)

    print(f"[LINKEDIN] Discovered {len(discovered_cards)} unique roles. Ingesting full requirements & AI extracting...")
    
    for i, card in enumerate(discovered_cards):
        j_id = card["job_id"]
        detail_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{j_id}"
        d_html = fetch_url(detail_url, timeout=10)
        
        full_desc = ""
        recruiter_contact = None
        extracted_company = card["company_name"]
        extracted_title = card["title"]
        extracted_skills = []
        min_e, max_e = parse_exp(card["title"])
        work_mode = card["work_mode"]

        if d_html:
            desc_m = re.search(r'<div class="show-more-less-html__markup[^"]*">(.*?)</div>', d_html, re.DOTALL)
            if desc_m:
                clean_text = re.sub(r'<[^>]+>', ' ', desc_m.group(1)).strip()
                full_desc = re.sub(r'\s+', ' ', clean_text)
            recruiter_m = re.search(r'class="message-the-recruiter__recruiter-name[^"]*">([^<]+)<', d_html)
            if recruiter_m:
                recruiter_contact = f"Recruiter: {recruiter_m.group(1).strip()}"

        if not full_desc:
            full_desc = f"Role: {card['title']} at {card['company_name']}. Sourced from LinkedIn search query: {card['keyword']}."

        # AI Extraction for up to max_ai_enrich jobs
        m_s, n_s = [], []
        if i < max_ai_enrich:
            ext = enrich_job_with_ai(card["title"], card["company_name"], full_desc)
            if ext:
                if ext.get("company") and ext.get("company") not in ["Unknown Company", "Technology Firm", "None"]:
                    extracted_company = ext.get("company")
                if ext.get("title") and len(ext.get("title")) > 3:
                    extracted_title = ext.get("title")
                extracted_skills = ext.get("skills", [])
                m_s = ext.get("must_have_skills", [])
                n_s = ext.get("nice_to_have_skills", [])
                min_e = ext.get("min_exp", min_e)
                max_e = ext.get("max_exp", max_e)
                ai_mode = ext.get("work_mode")
                if ai_mode in ["Remote", "Hybrid", "On-site"]:
                    work_mode = ai_mode
                summary = ext.get("summary", "")
                if summary:
                    full_desc = f"{summary}\n\nFull Requirements:\n{full_desc}"
            time.sleep(1.0) # Groq rate-limit guard
        else:
            p_min, p_max = parse_exp(full_desc)
            if p_min is not None:
                min_e = p_min
            if p_max is not None:
                max_e = p_max

        if not m_s and not n_s:
            m_s, n_s, extracted_skills = segregate_skills(extracted_title, full_desc, extracted_skills)

        all_jobs.append({
            "job_id": f"LI-{j_id}",
            "company_name": extracted_company,
            "title": extracted_title,
            "location": card["location"],
            "work_mode": work_mode,
            "url": card["url"],
            "min_exp": min_e,
            "max_exp": max_e,
            "experience_text": format_exp_text(min_e, max_e),
            "skills": extracted_skills,
            "must_have_skills": m_s,
            "nice_to_have_skills": n_s,
            "raw_description": f"{full_desc}\n\n[Contact / Recruiter]: {recruiter_contact or 'Direct LinkedIn Posting'}\n[Search Keyword]: {card['keyword']}",
            "source_channel": "LinkedIn"
        })

    return all_jobs

# ---------------------------------------------------------------------------
# CHANNEL B: ATS DIRECT APIS
# ---------------------------------------------------------------------------
def crawl_ats(company_slug, company_name, base_url, ats_type):
    jobs = []
    # 1. SmartRecruiters
    if ats_type == "SmartRecruiters" or "smartrecruiters.com" in base_url:
        offset = 0
        while True:
            api_url = f"https://api.smartrecruiters.com/v1/companies/{company_slug}/postings?limit=100&offset={offset}"
            body = fetch_url(api_url, timeout=12)
            if not body:
                break
            try:
                data = json.loads(body)
                content = data.get("content", [])
                if not content:
                    break
                for item in content:
                    title = sanitize_str(item.get("name", ""))
                    loc_obj = item.get("location", {})
                    city = loc_obj.get("city", "")
                    country = loc_obj.get("country", "")
                    loc = f"{city}, {country}".strip(", ") or "India"
                    item_id = item.get('id')
                    url = f"https://jobs.smartrecruiters.com/{company_slug}/{item_id}"
                    eligible, work_mode, clean_loc = is_india_eligible(loc, title, url)
                    if not eligible:
                        continue
                    is_tech, _ = is_valid_tech_title(title, url)
                    if not is_tech:
                        continue

                    # Fetch authentic posting details JSON from SmartRecruiters API
                    detail_api = f"https://api.smartrecruiters.com/v1/companies/{company_slug}/postings/{item_id}"
                    detail_body = fetch_url(detail_api, timeout=8)
                    raw_desc = ""
                    if detail_body:
                        try:
                            d_json = json.loads(detail_body)
                            jd_obj = d_json.get("jobDescription", {})
                            parts = []
                            for sec in ["companyDescription", "jobDescription", "qualifications", "additionalInformation"]:
                                txt = jd_obj.get(sec, {}).get("text", "")
                                if txt:
                                    clean_sec = re.sub(r'<[^>]+>', ' ', txt).strip()
                                    parts.append(clean_sec)
                            raw_desc = "\n\n".join(parts)
                        except Exception:
                            pass
                    if not raw_desc:
                        raw_desc = f"Role: {title} at {company_name}. Requisition ID: {item_id}"

                    min_e, max_e = parse_exp(raw_desc + " " + title)
                    m_s, n_s, all_s = segregate_skills(title, raw_desc)
                    jobs.append({
                        "job_id": str(item_id),
                        "company_name": company_name,
                        "title": title,
                        "location": clean_loc,
                        "work_mode": work_mode,
                        "url": url,
                        "min_exp": min_e,
                        "max_exp": max_e,
                        "experience_text": format_exp_text(min_e, max_e),
                        "skills": all_s,
                        "must_have_skills": m_s,
                        "nice_to_have_skills": n_s,
                        "raw_description": raw_desc[:3000],
                        "source_channel": "SmartRecruiters"
                    })
                offset += len(content)
                if len(content) < 100:
                    break
            except Exception:
                break
        return jobs

    # 2. Greenhouse
    if ats_type == "Greenhouse" or "greenhouse.io" in base_url:
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true"
        body = fetch_url(api_url, timeout=12)
        if body:
            try:
                data = json.loads(body)
                for item in data.get("jobs", []):
                    title = sanitize_str(item.get("title", ""))
                    loc_obj = item.get("location", {})
                    loc = loc_obj.get("name", "India") if isinstance(loc_obj, dict) else str(loc_obj)
                    url = item.get("absolute_url", base_url)
                    eligible, work_mode, clean_loc = is_india_eligible(loc, title, url)
                    if not eligible:
                        continue
                    is_tech, _ = is_valid_tech_title(title, url)
                    if not is_tech:
                        continue
                    content = sanitize_str(item.get("content", ""))
                    clean_desc = re.sub(r'<[^>]+>', ' ', content)[:3000] if content else f"Role: {title} at {company_name}."
                    min_e, max_e = parse_exp(clean_desc + " " + title)
                    m_s, n_s, all_s = segregate_skills(title, clean_desc)
                    jobs.append({
                        "job_id": str(item.get("id")),
                        "company_name": company_name,
                        "title": title,
                        "location": clean_loc,
                        "work_mode": work_mode,
                        "url": url,
                        "min_exp": min_e,
                        "max_exp": max_e,
                        "experience_text": format_exp_text(min_e, max_e),
                        "skills": all_s,
                        "must_have_skills": m_s,
                        "nice_to_have_skills": n_s,
                        "raw_description": clean_desc,
                        "source_channel": "Greenhouse"
                    })
            except Exception:
                pass
        return jobs

    # 3. Lever
    if ats_type == "Lever" or "lever.co" in base_url:
        api_url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
        body = fetch_url(api_url, timeout=12)
        if body:
            try:
                data = json.loads(body)
                for item in data:
                    title = sanitize_str(item.get("text", ""))
                    cats = item.get("categories", {})
                    loc = cats.get("location", "India / Remote")
                    url = item.get("hostedUrl", base_url)
                    desc = sanitize_str(item.get("descriptionPlain", "") or item.get("description", ""))
                    eligible, work_mode, clean_loc = is_india_eligible(loc, title, url)
                    if not eligible:
                        continue
                    is_tech, _ = is_valid_tech_title(title, url)
                    if not is_tech:
                        continue
                    min_e, max_e = parse_exp(desc + " " + title)
                    m_s, n_s, all_s = segregate_skills(title, desc)
                    jobs.append({
                        "job_id": str(item.get("id")),
                        "company_name": company_name,
                        "title": title,
                        "location": clean_loc,
                        "work_mode": work_mode,
                        "url": url,
                        "min_exp": min_e,
                        "max_exp": max_e,
                        "experience_text": format_exp_text(min_e, max_e),
                        "skills": all_s,
                        "must_have_skills": m_s,
                        "nice_to_have_skills": n_s,
                        "raw_description": desc[:3000],
                        "source_channel": "Lever"
                    })
            except Exception:
                pass
        return jobs

    # 4. Ashby
    if ats_type == "Ashby" or "ashbyhq.com" in base_url:
        api_url = f"https://api.ashbyhq.com/posting-api/job-board/{company_slug}"
        body = fetch_url(api_url, timeout=12)
        if body:
            try:
                data = json.loads(body)
                for item in data.get("jobs", []):
                    title = sanitize_str(item.get("title", ""))
                    loc = sanitize_str(item.get("location", "India"))
                    url = item.get("jobUrl", base_url)
                    eligible, work_mode, clean_loc = is_india_eligible(loc, title, url)
                    if not eligible:
                        continue
                    is_tech, _ = is_valid_tech_title(title, url)
                    if not is_tech:
                        continue
                    desc_html = item.get("descriptionHtml") or item.get("descriptionPlain") or ""
                    clean_desc = re.sub(r'<[^>]+>', ' ', desc_html).strip() if desc_html else f"Role: {title} at {company_name}. Ashby Job Posting."
                    min_e, max_e = parse_exp(clean_desc + " " + title)
                    m_s, n_s, all_s = segregate_skills(title, clean_desc)
                    jobs.append({
                        "job_id": str(item.get("id")),
                        "company_name": company_name,
                        "title": title,
                        "location": clean_loc,
                        "work_mode": work_mode,
                        "url": url,
                        "min_exp": min_e,
                        "max_exp": max_e,
                        "experience_text": format_exp_text(min_e, max_e),
                        "skills": all_s,
                        "must_have_skills": m_s,
                        "nice_to_have_skills": n_s,
                        "raw_description": clean_desc[:3000],
                        "source_channel": "Ashby"
                    })
            except Exception:
                pass
        return jobs

    return []

# ---------------------------------------------------------------------------
# CHANNEL C: COMPANY PORTALS & SITEMAPS
# ---------------------------------------------------------------------------
def fetch_authentic_job_page_content(url, title, company):
    """
    Crawls target job posting URL to extract genuine JD content:
    1. If Crawl4AI is available, executes headless browser to render dynamic JS
       and return clean authentic markdown with boilerplate stripped.
    2. Fallback to Schema.org JSON-LD (structured data) if Crawl4AI unavailable.
    3. Returns cleaned text (or None if unavailable/too short).
    """
    if CRAWL4AI_AVAILABLE:
        try:
            async def _crawl():
                async with AsyncWebCrawler(headless=True) as crawler:
                    res = await crawler.arun(url=url)
                    if res and res.success and res.markdown:
                        clean_md = res.markdown.strip()
                        if len(clean_md) > 120:
                            return clean_md[:4000]
                return None
            md_res = asyncio.run(_crawl())
            if md_res:
                return md_res
        except Exception:
            pass

    try:
        html_content = fetch_url(url, timeout=8)
        if not html_content:
            return None

        # 1. Check Schema.org JSON-LD
        for m in re.finditer(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html_content, re.DOTALL | re.I):
            try:
                data = json.loads(m.group(1))
                if isinstance(data, list) and data:
                    data = data[0]
                if isinstance(data, dict) and data.get("@type") == "JobPosting":
                    desc = data.get("description", "")
                    if desc:
                        clean_desc = re.sub(r'<[^>]+>', ' ', desc).strip()
                        clean_desc = re.sub(r'\s+', ' ', clean_desc)
                        if len(clean_desc) > 100:
                            return clean_desc[:3000]
            except Exception:
                pass

        # 2. Check Semantic containers
        for pattern in [
            r'<div[^>]*class=["\'][^"\']*(?:job[-_]?desc|job[-_]?detail|posting[-_]?desc|role[-_]?desc)[^"\']*["\'][^>]*>(.*?)</div>',
            r'<article[^>]*>(.*?)</article>',
            r'<main[^>]*>(.*?)</main>',
            r'<div[^>]*id=["\'][^"\']*(?:job[-_]?desc|job[-_]?detail|content)[^"\']*["\'][^>]*>(.*?)</div>'
        ]:
            c_match = re.search(pattern, html_content, re.DOTALL | re.I)
            if c_match:
                clean_text = re.sub(r'<script[^>]*>.*?</script>', ' ', c_match.group(1), flags=re.DOTALL | re.I)
                clean_text = re.sub(r'<style[^>]*>.*?</style>', ' ', clean_text, flags=re.DOTALL | re.I)
                clean_text = re.sub(r'<[^>]+>', ' ', clean_text).strip()
                clean_text = re.sub(r'\s+', ' ', clean_text)
                if len(clean_text) > 150:
                    return clean_text[:3000]
    except Exception:
        pass
    return None

async def crawl_portal_with_crawl4ai_async(portal, max_jobs=None):
    """
    Crawls non-ATS career pages using Crawl4AI headless Chromium browser:
    1. Renders JavaScript SPA/CSR portals (Workday, Phenom, SuccessFactors, custom React/Vue).
    2. Extracts authentic rendered markdown and job links without regex guessing.
    3. Exhaustively traverses pagination (?page=2, ?start=20, /page/2, infinite scroll, load more).
    4. Crawls each candidate job page to extract clean, genuine JD markdown.
    5. Extracts ALL technical skills from the JD (comprehensive skills_required) and categorizes
       explicit must_have and nice_to_have requirements.
    """
    company = portal["company_name"]
    url = portal["career_url"]
    parsed = urllib.parse.urlparse(url)
    base_domain = f"{parsed.scheme}://{parsed.netloc}"

    jobs = []
    seen_urls = set()
    candidate_urls = []

    # Fast sitemap check for direct candidate URLs
    candidates_sitemap = [
        f"{base_domain}/sitemap.xml",
        f"{base_domain}/sitemap_jobs.xml",
        f"{url.rstrip('/')}/sitemap.xml"
    ]
    for s_url in candidates_sitemap:
        xml_text = fetch_url(s_url, timeout=5)
        if xml_text and ("<urlset" in xml_text or "<sitemapindex" in xml_text):
            sub_sitemaps = re.findall(r'<loc>([^<]+(?:job|career|posting|position)[^<]*\.xml)</loc>', xml_text, re.I)
            if not sub_sitemaps:
                sub_sitemaps = [s_url]
            for target_xml in sub_sitemaps:
                sub_text = fetch_url(target_xml, timeout=6) if target_xml != s_url else xml_text
                if sub_text:
                    for u in re.findall(r'<loc>([^<]+)</loc>', sub_text):
                        u_clean = u.strip().split("?")[0].split("#")[0]
                        if u_clean not in seen_urls and any(k in u_clean.lower() for k in ["/job/", "/jobs/", "/position/", "/career/", "/posting/", "/requisition/", "/detail/"]):
                            clean_title, _ = extract_semantic_title_from_url(u_clean, company)
                            if clean_title:
                                is_tech, _ = is_valid_tech_title(clean_title, u_clean)
                                eligible, _, _ = is_india_eligible("", clean_title, u_clean)
                                if is_tech and eligible:
                                    seen_urls.add(u_clean)
                                    candidate_urls.append((u_clean, clean_title))
                                    if max_jobs is not None and len(candidate_urls) >= max_jobs:
                                        break
        if max_jobs is not None and len(candidate_urls) >= max_jobs:
            break

    # If sitemap had no tech candidate URLs, render the portal page via Crawl4AI
    async with AsyncWebCrawler(headless=True) as crawler:
        if not candidate_urls:
            pages_to_crawl = [url]
            crawled_pages = set()
            consecutive_empty_pages = 0

            # Dynamic pagination & infinite scroll loop across ALL portal pages
            while pages_to_crawl and len(crawled_pages) < 50:
                if max_jobs is not None and len(candidate_urls) >= max_jobs:
                    break
                current_page_url = pages_to_crawl.pop(0)
                if current_page_url in crawled_pages:
                    continue
                crawled_pages.add(current_page_url)

                try:
                    js_scroll_and_load_more = """
                    window.scrollTo(0, document.body.scrollHeight);
                    try {
                        let btn = document.querySelector('button[class*="more" i], button[id*="more" i], a[class*="more" i]');
                        if (btn && !btn.disabled && btn.offsetParent !== null) btn.click();
                    } catch(e) {}
                    """
                    portal_res = await crawler.arun(url=current_page_url, js_code=js_scroll_and_load_more, page_timeout=15000)
                    if not portal_res or not portal_res.success:
                        continue

                    # Termination Guard 1: Detect explicit empty-state text on subsequent pages
                    page_md_low = (portal_res.markdown or "").lower()
                    if any(empty_kw in page_md_low for empty_kw in [
                        "no open positions", "no jobs found", "0 jobs match", "no current openings",
                        "no positions available", "no results found"
                    ]) and len(candidate_urls) > 0:
                        break

                    links = []
                    if hasattr(portal_res, "links") and isinstance(portal_res.links, dict):
                        links = list(portal_res.links.get("internal", []))

                    # Also collect rendered markdown links extracted by Crawl4AI
                    for m_text, m_href in re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', portal_res.markdown or ""):
                        links.append({"href": m_href, "text": m_text})

                    new_jobs_this_page = 0
                    for l_obj in links:
                        href = l_obj.get("href", "")
                        if not href or href.startswith("javascript:") or href.startswith("mailto:") or href.startswith("#"):
                            continue
                        if href.startswith("/"):
                            href = f"{base_domain}{href}"

                        # Detect all pagination links (?page=2, ?p=2, /page/2, etc.) to traverse multi-page portals
                        h_low = href.lower()
                        if any(p_kw in h_low for p_kw in ["page=", "p=", "start=", "offset=", "/page/"]):
                            clean_page_link = href.split("#")[0]
                            if clean_page_link not in crawled_pages and clean_page_link not in pages_to_crawl:
                                pages_to_crawl.append(clean_page_link)

                        h_clean = href.split("?")[0].split("#")[0]
                        if h_clean in seen_urls:
                            continue
                        if any(k in h_clean.lower() for k in ["/job/", "/jobs/", "/career/", "/position/", "/posting/", "/requisition/", "/opening/"]):
                            link_text = sanitize_str(l_obj.get("text", ""))
                            clean_title, _ = extract_semantic_title_from_url(h_clean, company)
                            final_title = link_text if (link_text and is_valid_tech_title(link_text, h_clean)[0]) else clean_title
                            if final_title:
                                is_tech, _ = is_valid_tech_title(final_title, h_clean)
                                eligible, _, _ = is_india_eligible("", final_title, h_clean)
                                if is_tech and eligible:
                                    seen_urls.add(h_clean)
                                    candidate_urls.append((h_clean, final_title))
                                    new_jobs_this_page += 1
                                    if max_jobs is not None and len(candidate_urls) >= max_jobs:
                                        break

                    # Termination Guard 2: Consecutive zero-yield page detector
                    if new_jobs_this_page == 0 and len(crawled_pages) > 1:
                        consecutive_empty_pages += 1
                        if consecutive_empty_pages >= 2:
                            # 2 consecutive pagination pages yielded zero new roles -> end of listings reached
                            break
                    else:
                        consecutive_empty_pages = 0

                except Exception as e:
                    print(f"[CRAWL4AI] Error rendering portal page {current_page_url}: {e}")

        # Crawl genuine rendered JD content for candidate tech URLs
        target_list = candidate_urls if max_jobs is None else candidate_urls[:max_jobs]
        for target_url, target_title in target_list:
            try:
                job_res = await crawler.arun(url=target_url, page_timeout=15000)
                if not job_res or not job_res.success or not job_res.markdown:
                    continue
                md_content = job_res.markdown.strip()
                if len(md_content) < 150:
                    continue

                # Refine title from h1 if present
                h1_m = re.search(r'^#\s+([^\n]+)', md_content, re.MULTILINE)
                resolved_title = target_title
                if h1_m:
                    h1_cand = sanitize_str(h1_m.group(1))
                    is_h1_tech, _ = is_valid_tech_title(h1_cand, target_url)
                    if is_h1_tech:
                        resolved_title = h1_cand

                m_s, n_s, all_s = [], [], []
                min_e, max_e = parse_exp(md_content + " " + resolved_title)
                work_mode = detect_work_mode(md_content, target_url)
                summary = ""

                # AI Structured Enrichment
                if GROQ_API_KEY:
                    ext = enrich_job_with_ai(resolved_title, company, md_content[:3500])
                    if ext:
                        all_s = ext.get("skills", [])
                        m_s = ext.get("must_have_skills", [])
                        n_s = ext.get("nice_to_have_skills", [])
                        min_e = ext.get("min_exp", min_e)
                        max_e = ext.get("max_exp", max_e)
                        ai_mode = ext.get("work_mode")
                        if ai_mode in ["Remote", "Hybrid", "On-site"]:
                            work_mode = ai_mode
                        summary = ext.get("summary", "")

                if not m_s and not n_s:
                    m_s, n_s, all_s = segregate_skills(resolved_title, md_content, all_s)

                clean_desc = f"{summary}\n\nFull Requirements:\n{md_content[:4000]}" if summary else md_content[:4000]

                jobs.append({
                    "job_id": f"CRAWL-{abs(hash(target_url)) % 100000000}",
                    "company_name": company,
                    "title": resolved_title,
                    "location": "India",
                    "work_mode": work_mode,
                    "url": target_url,
                    "min_exp": min_e,
                    "max_exp": max_e,
                    "experience_text": format_exp_text(min_e, max_e),
                    "skills": all_s,
                    "must_have_skills": m_s,
                    "nice_to_have_skills": n_s,
                    "raw_description": clean_desc,
                    "source_channel": "Career Page (Crawl4AI)"
                })
            except Exception as e:
                print(f"[CRAWL4AI] Error crawling job {target_url}: {e}")

    return jobs

# CHANNEL C: COMPANY PORTALS & SITEMAPS
# ---------------------------------------------------------------------------
def crawl_portal_and_sitemap(portal):
    company = portal["company_name"]
    url = portal["career_url"]
    ats = portal.get("detected_ats") or "Custom / In-House"
    
    parsed = urllib.parse.urlparse(url)
    slug = parsed.path.strip("/").split("/")[-1] or parsed.netloc.split(".")[0]
    base_domain = f"{parsed.scheme}://{parsed.netloc}"
    
    # 1. Try ATS (Greenhouse, Lever, SmartRecruiters, Ashby)
    ats_jobs = crawl_ats(slug, company, url, ats)
    if ats_jobs:
        return ats_jobs

    # 2. Non-ATS: Directly invoke Crawl4AI (Zero guessing, zero assumptions!)
    if CRAWL4AI_AVAILABLE:
        try:
            crawl_jobs = asyncio.run(crawl_portal_with_crawl4ai_async(portal))
            if crawl_jobs:
                return crawl_jobs
        except Exception as e:
            print(f"[CRAWL4AI] Fallback from Crawl4AI for {company}: {e}")

    # 2. Try Sitemaps
    candidates = [
        f"{base_domain}/sitemap.xml",
        f"{base_domain}/sitemap_jobs.xml",
        f"{url.rstrip('/')}/sitemap.xml"
    ]
    seen_urls = set()
    sitemap_jobs = []
    for s_url in candidates:
        xml_text = fetch_url(s_url, timeout=10)
        if not xml_text or ("<urlset" not in xml_text and "<sitemapindex" not in xml_text):
            continue
        sub_sitemaps = re.findall(r'<loc>([^<]+(?:job|career|posting|position)[^<]*\.xml)</loc>', xml_text, re.I)
        if not sub_sitemaps:
            sub_sitemaps = [s_url]
        for target_xml in sub_sitemaps[:3]:
            sub_text = fetch_url(target_xml, timeout=12) if target_xml != s_url else xml_text
            if not sub_text:
                continue
            for u in re.findall(r'<loc>([^<]+)</loc>', sub_text):
                u_clean = u.strip()
                if u_clean in seen_urls:
                    continue
                seen_urls.add(u_clean)
                if any(k in u_clean.lower() for k in ["/job/", "/jobs/", "/position/", "/career/", "/posting/", "/requisition/", "/detail/"]):
                    clean_title, t_reason = extract_semantic_title_from_url(u_clean, company)
                    if not clean_title:
                        continue
                    is_tech, tech_reason = is_valid_tech_title(clean_title, u_clean)
                    if not is_tech:
                        continue
                    eligible, work_mode, clean_loc = is_india_eligible("", clean_title, u_clean)
                    if not eligible:
                        continue
                    actual_desc = fetch_authentic_job_page_content(u_clean, clean_title, company)
                    raw_desc = actual_desc if actual_desc else f"Role: {clean_title} at {company}. Direct URL: {u_clean}"
                    min_e, max_e = parse_exp(raw_desc + " " + clean_title)
                    m_s, n_s, all_s = segregate_skills(clean_title, raw_desc)
                    sitemap_jobs.append({
                        "job_id": f"SM-{abs(hash(u_clean)) % 100000000}",
                        "company_name": company,
                        "title": clean_title,
                        "location": clean_loc,
                        "work_mode": work_mode,
                        "url": u_clean,
                        "min_exp": min_e,
                        "max_exp": max_e,
                        "experience_text": format_exp_text(min_e, max_e),
                        "skills": all_s,
                        "must_have_skills": m_s,
                        "nice_to_have_skills": n_s,
                        "raw_description": raw_desc,
                        "source_channel": "Career Page (Custom)"
                    })
        if sitemap_jobs:
            return sitemap_jobs

    # 3. Try HTML Link Crawling
    html_text = fetch_url(url, timeout=10)
    if html_text:
        job_links = re.findall(r'href="([^"]*(?:/job/|/jobs/|/position/|/career/|/requisition/|/opening/|detail)[^"]*)"', html_text, re.IGNORECASE)
        valid_links = []
        for link in job_links:
            if link.startswith("//"):
                link = f"{parsed.scheme}:{link}"
            elif link.startswith("/"):
                link = f"{parsed.scheme}://{parsed.netloc}{link}"
            if link.startswith("http") and link not in valid_links and link != url and not any(link.endswith(ext) for ext in [".pdf", ".jpg", ".png", ".css", ".js"]):
                valid_links.append(link)
        html_jobs = []
        for j_link in valid_links:
            clean_title, t_reason = extract_semantic_title_from_url(j_link, company)
            if not clean_title:
                continue
            is_tech, tech_reason = is_valid_tech_title(clean_title, j_link)
            if not is_tech:
                continue
            eligible, work_mode, clean_loc = is_india_eligible("", clean_title, j_link)
            if not eligible:
                continue
            actual_desc = fetch_authentic_job_page_content(j_link, clean_title, company)
            raw_desc = actual_desc if actual_desc else f"Role: {clean_title} at {company}. URL: {j_link}"
            min_e, max_e = parse_exp(raw_desc + " " + clean_title)
            m_s, n_s, all_s = segregate_skills(clean_title, raw_desc)
            html_jobs.append({
                "job_id": f"EXT-{abs(hash(j_link)) % 100000000}",
                "company_name": company,
                "title": clean_title,
                "location": clean_loc,
                "work_mode": work_mode,
                "url": j_link,
                "min_exp": min_e,
                "max_exp": max_e,
                "experience_text": format_exp_text(min_e, max_e),
                "skills": all_s,
                "must_have_skills": m_s,
                "nice_to_have_skills": n_s,
                "raw_description": raw_desc,
                "source_channel": "Career Page (Custom)"
            })
        return html_jobs

    return []

# ---------------------------------------------------------------------------
# PERSISTENCE (STREAMING TRANSACTIONS WITH STRICT EXPERIENCE REPAIR)
# ---------------------------------------------------------------------------
def persist_jobs(jobs):
    if not jobs:
        return 0
    seen = set()
    deduped = []
    for j in jobs:
        u = sanitize_str(j.get("url"))
        if u and u not in seen:
            seen.add(u)
            deduped.append(j)

    now_dt = datetime.now(timezone.utc).replace(tzinfo=None)
    now_d = now_dt.date()

    rows = []
    for j in deduped:
        title_cand = sanitize_str(j.get("title", ""))
        url_cand = sanitize_str(j.get("url", ""))

        # Strict Technical and Title verification
        is_tech, tech_reason = is_valid_tech_title(title_cand, url_cand)
        if not is_tech:
            continue

        min_e = j.get("min_exp")
        max_e = j.get("max_exp")
        exp_txt = format_exp_text(min_e, max_e)

        m_skills = j.get("must_have_skills") or []
        n_skills = j.get("nice_to_have_skills") or []
        all_skills = j.get("skills") or []
        if not m_skills and not n_skills:
            m_skills, n_skills, all_skills = segregate_skills(title_cand, j.get("raw_description", ""), all_skills)

        rows.append((
            str(uuid.uuid4()),
            sanitize_str(j.get("job_id", f"J-{abs(hash(url_cand)) % 10000000}")),
            sanitize_str(j["company_name"]),
            "MNC",
            sanitize_str(j.get("source_channel", "Career Page (Custom)")),
            title_cand,
            sanitize_str(j.get("location", "India")),
            sanitize_str(j.get("work_mode", "On-site")),
            exp_txt,
            min_e,
            max_e,
            url_cand,
            json.dumps(all_skills),
            json.dumps(m_skills),
            json.dumps(n_skills),
            sanitize_str(j.get("raw_description", ""))[:2500],
            now_dt,
            True,
            now_d,
            now_dt
        ))

    insert_sql = """
    INSERT INTO company_jobs (
        id, job_id, company_name, company_group, source_channel,
        title, location, work_mode, experience_text, min_exp, max_exp,
        url, skills_required, must_have_skills, nice_to_have_skills,
        raw_description, posted_date, is_active, fetched_date, created_at
    ) VALUES %s
    ON CONFLICT (url) DO UPDATE SET
        title = EXCLUDED.title,
        location = EXCLUDED.location,
        work_mode = EXCLUDED.work_mode,
        experience_text = EXCLUDED.experience_text,
        min_exp = COALESCE(EXCLUDED.min_exp, company_jobs.min_exp),
        max_exp = COALESCE(EXCLUDED.max_exp, company_jobs.max_exp),
        source_channel = EXCLUDED.source_channel,
        must_have_skills = CASE 
            WHEN EXCLUDED.must_have_skills IS NOT NULL AND EXCLUDED.must_have_skills::text != '[]' 
            THEN EXCLUDED.must_have_skills 
            ELSE company_jobs.must_have_skills 
        END,
        nice_to_have_skills = CASE 
            WHEN EXCLUDED.nice_to_have_skills IS NOT NULL AND EXCLUDED.nice_to_have_skills::text != '[]' 
            THEN EXCLUDED.nice_to_have_skills 
            ELSE company_jobs.nice_to_have_skills 
        END,
        skills_required = CASE 
            WHEN EXCLUDED.skills_required IS NOT NULL AND EXCLUDED.skills_required::text != '[]' 
            THEN EXCLUDED.skills_required 
            ELSE company_jobs.skills_required 
        END,
        raw_description = COALESCE(EXCLUDED.raw_description, company_jobs.raw_description),
        is_active = TRUE,
        fetched_date = EXCLUDED.fetched_date;
    """

    conn = get_db()
    cur = conn.cursor()
    saved = 0
    try:
        execute_values(cur, insert_sql, rows)
        conn.commit()
        saved = len(rows)
    except Exception:
        conn.rollback()
        for r in rows:
            try:
                single_sql = """
                INSERT INTO company_jobs (
                    id, job_id, company_name, company_group, source_channel,
                    title, location, work_mode, experience_text, min_exp, max_exp,
                    url, skills_required, must_have_skills, nice_to_have_skills,
                    raw_description, posted_date, is_active, fetched_date, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO UPDATE SET
                    title = EXCLUDED.title,
                    location = EXCLUDED.location,
                    work_mode = EXCLUDED.work_mode,
                    experience_text = EXCLUDED.experience_text,
                    min_exp = COALESCE(EXCLUDED.min_exp, company_jobs.min_exp),
                    max_exp = COALESCE(EXCLUDED.max_exp, company_jobs.max_exp),
                    source_channel = EXCLUDED.source_channel,
                    must_have_skills = CASE 
                        WHEN EXCLUDED.must_have_skills IS NOT NULL AND EXCLUDED.must_have_skills::text != '[]' 
                        THEN EXCLUDED.must_have_skills 
                        ELSE company_jobs.must_have_skills 
                    END,
                    nice_to_have_skills = CASE 
                        WHEN EXCLUDED.nice_to_have_skills IS NOT NULL AND EXCLUDED.nice_to_have_skills::text != '[]' 
                        THEN EXCLUDED.nice_to_have_skills 
                        ELSE company_jobs.nice_to_have_skills 
                    END,
                    skills_required = CASE 
                        WHEN EXCLUDED.skills_required IS NOT NULL AND EXCLUDED.skills_required::text != '[]' 
                        THEN EXCLUDED.skills_required 
                        ELSE company_jobs.skills_required 
                    END,
                    raw_description = COALESCE(EXCLUDED.raw_description, company_jobs.raw_description),
                    is_active = TRUE,
                    fetched_date = EXCLUDED.fetched_date;
                """
                cur.execute(single_sql, r)
                conn.commit()
                saved += 1
            except Exception:
                conn.rollback()
    finally:
        cur.close()
        conn.close()
    return saved

# ---------------------------------------------------------------------------
# MAIN FULL-SYNC PIPELINE (STAGE 1 & STAGE 2)
# ---------------------------------------------------------------------------
def run_full_sync():
    start_time = time.time()
    sync_id = str(uuid.uuid4())
    print("="*80)
    print("UNIFIED DUAL-STAGE SYNC WORKER (STAGE 1 & 2)")
    print(f"Sync ID: {sync_id} | Start: {datetime.now(timezone.utc).isoformat()}")
    print("="*80)

    init_sync_tables()

    # 1. State: Starting
    update_sync_state(sync_id, "RUNNING", "Stage 1: Ingesting LinkedIn Feeds", 5, 0, 0)

    # Channel A: LinkedIn
    print("\n[CHANNEL A] Crawling LinkedIn India Tech Streams...")
    li_jobs = crawl_linkedin()
    saved_li = persist_jobs(li_jobs)
    print(f"[LINKEDIN] Persisted {saved_li} verified India roles.")
    update_sync_state(sync_id, "RUNNING", "Stage 1: Crawling Portals & ATS APIs", 20, saved_li, saved_li)

    # Channel B & C: All Portals & ATS
    conn = get_db()
    cur = conn.cursor(cursor_factory=DictCursor)
    cur.execute("SELECT id, company_name, career_url, detected_ats FROM company_portals WHERE is_active = TRUE ORDER BY detected_ats != 'Custom / In-House' DESC;")
    portals = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()

    worker_threads = 2 if CRAWL4AI_AVAILABLE else 8
    print(f"\n[CHANNEL B & C] Crawling ALL {len(portals)} Company Portals & ATS APIs ({worker_threads} threads, Crawl4AI={CRAWL4AI_AVAILABLE})...")
    total_portal_jobs = 0
    buffer = []
    completed = 0

    with ThreadPoolExecutor(max_workers=worker_threads) as executor:
        futures = {executor.submit(crawl_portal_and_sitemap, p): p for p in portals}
        for f in as_completed(futures):
            p = futures[f]
            completed += 1
            try:
                res = f.result()
                if res:
                    buffer.extend(res)
            except Exception:
                pass

            if len(buffer) >= 50 or completed == len(portals):
                s = persist_jobs(buffer)
                total_portal_jobs += s
                buffer = []
                gc.collect()

            if completed % 25 == 0 or completed == len(portals):
                pct = 20 + int((completed / len(portals)) * 65)
                print(f" -> Progress: {completed}/{len(portals)} portals | Persisted: {total_portal_jobs} | Elapsed: {int(time.time() - start_time)}s", flush=True)
                update_sync_state(sync_id, "RUNNING", f"Crawling Portals ({completed}/{len(portals)})", pct, saved_li + total_portal_jobs, saved_li + total_portal_jobs)

    if buffer:
        s = persist_jobs(buffer)
        total_portal_jobs += s

    # Stage 2: AI Structured Enrichment & Repair
    update_sync_state(sync_id, "RUNNING", "Stage 2: AI Structured Enrichment & Normalization", 88, saved_li + total_portal_jobs, saved_li + total_portal_jobs)
    enriched_count = run_stage2_enrichment_batch(limit=50)

    # Global Data Integrity Pass
    conn = get_db()
    cur = conn.cursor()
    # Ensure no NULL or invalid work modes
    cur.execute("UPDATE company_jobs SET work_mode = 'On-site' WHERE work_mode IS NULL OR work_mode = 'None';")
    # Synchronize experience_text across all records
    cur.execute("""
        UPDATE company_jobs
        SET experience_text = CASE
            WHEN min_exp IS NOT NULL AND max_exp IS NOT NULL AND min_exp != max_exp THEN
                min_exp::int || ' - ' || max_exp::int || ' Years'
            WHEN min_exp IS NOT NULL AND max_exp IS NOT NULL AND min_exp = max_exp THEN
                min_exp::int || ' Years'
            WHEN min_exp IS NOT NULL AND max_exp IS NULL THEN
                min_exp::int || '+ Years'
            WHEN min_exp IS NULL AND max_exp IS NOT NULL THEN
                'Up to ' || max_exp::int || ' Years'
            ELSE
                'Not Specified'
        END
        WHERE experience_text = '1 - 3 Years' AND (min_exp != 1 OR max_exp != 3);
    """)
    cur.execute("SELECT count(*) FROM company_jobs WHERE is_active = TRUE;")
    active_in_db = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    total_all = saved_li + total_portal_jobs
    update_sync_state(sync_id, "COMPLETED", "Full Ingestion Sync Completed Successfully", 100, active_in_db, total_all)

    print("\n" + "="*80)
    print(f"FULL SYNC COMPLETED IN {int(time.time() - start_time)} SECONDS!")
    print(f"Total Active Jobs in PostgreSQL: {active_in_db}")
    print(f"Stage 2 AI Enriched Roles in this pass: {enriched_count}")
    print("="*80)

if __name__ == "__main__":
    run_full_sync()
