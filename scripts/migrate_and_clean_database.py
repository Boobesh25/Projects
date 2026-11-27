"""
Database Migration, Sanitization & Skill Segregation Engine
===========================================================
1. Adds `must_have_skills` and `nice_to_have_skills` JSONB columns to `company_jobs`.
2. Purges invalid, corrupt, non-technical, and foreign on-site jobs:
   - "Opportunity at <Company>" / "Technical Opportunity at <Company>"
   - Corrupt titles with query strings ("?lang=en-us", "?domain=...")
   - Non-technical roles (retail sales, cashier, nurse, customer support, etc.)
   - Foreign on-site/hybrid positions (Austin, Shanghai, Graz, US/UK non-remote)
3. Segregates skills in remaining valid jobs into Must-Have vs Nice-to-Have.
"""

import re
import json
import psycopg2
from psycopg2.extras import execute_values

DB_URL = "postgresql://postgres:MySecretPassword123@127.0.0.1:5432/career_portal"

# Curated technical tokens for skill segregation
TECH_TOKENS = [
    "python", "fastapi", "flask", "django", "langgraph", "langchain", "llamaindex",
    "mcp", "react", "rag", "pgvector", "qdrant", "chromadb", "pinecone", "redis",
    "kafka", "docker", "kubernetes", "argocd", "opentelemetry", "openlit", "gemini",
    "aws bedrock", "azure openai", "postgresql", "mysql", "sql", "pandas", "numpy",
    "agentic ai", "prompt engineering", "embeddings", "git", "gitops", "aws", "azure",
    "gcp", "google cloud", "machine learning", "deep learning", "nlp", "golang", "java",
    "c++", "c#", "rust", "typescript", "javascript", "linux", "ci/cd", "terraform",
    "rest api", "graphql", "microservices", "airflow", "spark", "hadoop", "elasticsearch",
    "solidity", "pytorch", "tensorflow", "snowflake", "databricks", "scikit-learn"
]

NON_TECH_PATTERNS = [
    r"\bretail\b", r"\bsales\s*consultant\b", r"\bstore\s*associate\b", r"\bcashier\b",
    r"\brecruiter\b", r"\bsourcer\b", r"\btalent acquisition\b", r"\bhuman resources\b",
    r"\bhr\s*(?:generalist|manager|executive|specialist|business partner|bp)\b",
    r"\bsales\s*(?:representative|rep|manager|executive|director|agent|lead)\b",
    r"\bbusiness development\b", r"\baccount executive\b", r"\bsdr\b", r"\bbdr\b",
    r"\bmarketing\s*(?:manager|specialist|lead|executive|intern)\b",
    r"\bcontent\s*(?:writer|creator|marketing)\b", r"\bcopywriter\b",
    r"\blegal counsel\b", r"\bparalegal\b", r"\bcompliance officer\b",
    r"\baccountant\b", r"\bbookkeeper\b", r"\btax\s*(?:analyst|consultant|manager)\b",
    r"\baudit\s*(?:associate|senior|manager)\b", r"\bpayroll\s*(?:specialist|lead)\b",
    r"\bloan\s*officer\b", r"\bcredit\s*analyst\b", r"\bwealth\s*manager\b",
    r"\breceptionist\b", r"\boffice\s*manager\b", r"\bexecutive\s*assistant\b",
    r"\bcustomer\s*support\s*representative\b", r"\bcall\s*center\b",
    r"\bcustomer\s*support\s*technician\b", r"\bnurse\b", r"\bphysician\b",
    r"\bdriver\b", r"\bwarehouse\b"
]

def segregate_skills(title, description, existing_skills=None):
    """
    Segregates skills into must-have, nice-to-have, and combined tech stack.
    """
    desc_clean = (description or "").lower()
    title_clean = (title or "").lower()
    
    must_have = []
    nice_to_have = []
    
    # 1. Section demarcation in JD
    req_pattern = r"(?:minimum qualifications|basic qualifications|required qualifications|requirements|what you(?:'ll)? need|must have|core requirements)(.*?)(?:preferred qualifications|nice to have|bonus|desired|what we offer|responsibilities|\Z)"
    pref_pattern = r"(?:preferred qualifications|nice to have|bonus points|desired skills|good to have)(.*?)(?:responsibilities|benefits|about us|\Z)"

    req_match = re.search(req_pattern, desc_clean, re.DOTALL)
    pref_match = re.search(pref_pattern, desc_clean, re.DOTALL)

    req_corpus = req_match.group(1) if req_match else desc_clean[:2500]
    pref_corpus = pref_match.group(1) if pref_match else ""

    found_skills = set()
    for token in TECH_TOKENS:
        # Check title first (highest priority must-have)
        if re.search(rf"\b{re.escape(token)}\b", title_clean):
            must_have.append(token)
            found_skills.add(token)
        elif pref_corpus and re.search(rf"\b{re.escape(token)}\b", pref_corpus):
            nice_to_have.append(token)
            found_skills.add(token)
        elif re.search(rf"\b{re.escape(token)}\b", req_corpus):
            must_have.append(token)
            found_skills.add(token)

    # Incorporate any pre-extracted skills
    if existing_skills and isinstance(existing_skills, list):
        for s in existing_skills:
            s_clean = str(s).lower().strip()
            if s_clean and s_clean not in found_skills:
                if len(must_have) < 6:
                    must_have.append(s_clean)
                else:
                    nice_to_have.append(s_clean)
                found_skills.add(s_clean)

    # Balance partitions if needed
    if not must_have and found_skills:
        all_sorted = list(found_skills)
        must_have = all_sorted[:5]
        nice_to_have = all_sorted[5:]

    all_skills = list(dict.fromkeys(must_have + nice_to_have))
    return must_have, nice_to_have, all_skills


def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("=== Step 1: Schema Migration ===")
    cur.execute("""
        ALTER TABLE company_jobs ADD COLUMN IF NOT EXISTS must_have_skills jsonb DEFAULT '[]'::jsonb;
        ALTER TABLE company_jobs ADD COLUMN IF NOT EXISTS nice_to_have_skills jsonb DEFAULT '[]'::jsonb;
    """)
    conn.commit()
    print("Schema updated with must_have_skills and nice_to_have_skills columns.")

    print("\n=== Step 2: Counting & Purging Invalid Jobs ===")
    
    # 1. Corrupt and Placeholder Titles
    cur.execute("""
        SELECT count(*) FROM company_jobs
        WHERE title ILIKE 'opportunity at%'
           OR title ILIKE 'technical opportunity at%'
           OR title ILIKE '%?lang=%'
           OR title ILIKE '%lang=en%'
           OR title ILIKE '%?domain=%'
           OR title ILIKE '%?%'
           OR length(title) < 4;
    """)
    placeholder_count = cur.fetchone()[0]
    print(f"Placeholder / Corrupt Title Jobs: {placeholder_count}")

    # 2. Foreign on-site / hybrid jobs that bypassed filter
    cur.execute("""
        SELECT count(*) FROM company_jobs
        WHERE (
            url ILIKE '%/us/%' 
            OR url ILIKE '%/us-en/%'
            OR url ILIKE '%/job/austin/%' 
            OR url ILIKE '%/jobs/austin/%'
            OR url ILIKE '%shanghai%'
            OR url ILIKE '%graz%'
            OR url ILIKE '%pyeongtaek%'
            OR url ILIKE '%migdal%'
            OR url ILIKE '%icheon%'
            OR location ILIKE '%austin%'
            OR location ILIKE '%shanghai%'
            OR location ILIKE '%graz%'
        ) AND work_mode != 'Remote';
    """)
    foreign_onsite_count = cur.fetchone()[0]
    print(f"Foreign On-site / Hybrid Jobs (non-India, non-remote): {foreign_onsite_count}")

    # 3. Explicit non-technical roles
    cur.execute("""
        SELECT count(*) FROM company_jobs
        WHERE url ILIKE '%retail-sales-consultant%'
           OR url ILIKE '%cashier%'
           OR url ILIKE '%store-associate%'
           OR title ILIKE '%retail sales%'
           OR title ILIKE '%store manager%'
           OR title ILIKE '%cashier%'
           OR title ILIKE '%customer support technician%';
    """)
    non_tech_count = cur.fetchone()[0]
    print(f"Explicit Non-Technical Roles: {non_tech_count}")

    # Execute atomic deletion of junk records
    cur.execute("""
        DELETE FROM company_jobs
        WHERE title ILIKE 'opportunity at%'
           OR title ILIKE 'technical opportunity at%'
           OR title ILIKE '%?lang=%'
           OR title ILIKE '%lang=en%'
           OR title ILIKE '%?domain=%'
           OR title ILIKE '%?%'
           OR length(title) < 4
           OR (
               (
                   url ILIKE '%/us/%' 
                   OR url ILIKE '%/us-en/%'
                   OR url ILIKE '%/job/austin/%' 
                   OR url ILIKE '%/jobs/austin/%'
                   OR url ILIKE '%shanghai%'
                   OR url ILIKE '%graz%'
                   OR url ILIKE '%pyeongtaek%'
                   OR url ILIKE '%migdal%'
                   OR url ILIKE '%icheon%'
                   OR location ILIKE '%austin%'
                   OR location ILIKE '%shanghai%'
                   OR location ILIKE '%graz%'
               ) AND work_mode != 'Remote'
           )
           OR url ILIKE '%retail-sales-consultant%'
           OR url ILIKE '%cashier%'
           OR url ILIKE '%store-associate%'
           OR title ILIKE '%retail sales%'
           OR title ILIKE '%store manager%'
           OR title ILIKE '%cashier%'
           OR title ILIKE '%customer support technician%';
    """)
    deleted_count = cur.rowcount
    conn.commit()
    print(f"Total invalid / corrupt / non-tech jobs purged from database: {deleted_count}")

    # Check remaining count
    cur.execute("SELECT count(*) FROM company_jobs WHERE is_active = TRUE;")
    remaining_valid = cur.fetchone()[0]
    print(f"Remaining Valid, High-Confidence Jobs in Database: {remaining_valid}")

    print("\n=== Step 3: Segregating Skills on Valid Grounded Jobs ===")
    cur.execute("""
        SELECT id, title, raw_description, skills_required 
        FROM company_jobs 
        WHERE is_active = TRUE 
          AND (must_have_skills IS NULL OR must_have_skills = '[]'::jsonb)
        LIMIT 5000;
    """)
    batch = cur.fetchall()
    print(f"Found {len(batch)} jobs ready for skill segregation.")

    updates = []
    for j_id, title, raw_desc, current_skills in batch:
        m_skills, n_skills, all_s = segregate_skills(title, raw_desc, current_skills)
        if m_skills or n_skills:
            updates.append((
                json.dumps(m_skills),
                json.dumps(n_skills),
                json.dumps(all_s),
                j_id
            ))

    if updates:
        cur.executemany("""
            UPDATE company_jobs 
            SET must_have_skills = %s::jsonb,
                nice_to_have_skills = %s::jsonb,
                skills_required = %s::jsonb
            WHERE id = %s;
        """, updates)
        conn.commit()
        print(f"Successfully segregated skills for {len(updates)} jobs.")

    # Verification sample
    cur.execute("""
        SELECT company_name, title, location, work_mode, must_have_skills, nice_to_have_skills
        FROM company_jobs
        WHERE is_active = TRUE AND jsonb_array_length(must_have_skills) > 0
        LIMIT 5;
    """)
    samples = cur.fetchall()
    print("\n=== Verification Samples with Segregated Skills ===")
    for s in samples:
        print(f"Company: {s[0]} | Title: {s[1]}")
        print(f"  Location: {s[2]} ({s[3]})")
        print(f"  Must-Have Skills: {s[4]}")
        print(f"  Nice-to-Have Skills: {s[5]}\n")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
