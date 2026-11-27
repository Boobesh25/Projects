"""
Backfills Must-Have and Nice-to-Have Skills across all active jobs in PostgreSQL.
"""

import re
import json
import psycopg2

DB_URL = "postgresql://postgres:MySecretPassword123@127.0.0.1:5432/career_portal"

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

    # Incorporate existing pre-extracted skills
    if existing_skills and isinstance(existing_skills, list):
        for s in existing_skills:
            s_clean = str(s).lower().strip()
            if s_clean and s_clean not in found_skills:
                if len(must_have) < 5:
                    must_have.append(s_clean)
                else:
                    nice_to_have.append(s_clean)
                found_skills.add(s_clean)

    # If title gives a skill domain (e.g. Python Developer -> python), ensure it's in must_have
    for kw in ["python", "java", "golang", "react", "cloud", "aws", "azure", "docker", "kubernetes", "sql", "snowflake"]:
        if re.search(rf"\b{kw}\b", title_clean) and kw not in must_have:
            must_have.insert(0, kw)
            found_skills.add(kw)

    # Balance partitions if must_have is empty
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


def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    cur.execute("SELECT id, title, raw_description, skills_required FROM company_jobs WHERE is_active = TRUE;")
    jobs = cur.fetchall()
    print(f"Total jobs to segregate skills for: {len(jobs)}")

    updates = []
    chunk_size = 1000
    updated_total = 0

    for idx, (j_id, title, raw_desc, current_skills) in enumerate(jobs):
        m_skills, n_skills, all_s = segregate_skills(title, raw_desc, current_skills)
        updates.append((
            json.dumps(m_skills),
            json.dumps(n_skills),
            json.dumps(all_s),
            j_id
        ))

        if len(updates) >= chunk_size or idx == len(jobs) - 1:
            cur.executemany("""
                UPDATE company_jobs 
                SET must_have_skills = %s::jsonb,
                    nice_to_have_skills = %s::jsonb,
                    skills_required = %s::jsonb
                WHERE id = %s;
            """, updates)
            conn.commit()
            updated_total += len(updates)
            print(f"Updated {updated_total} / {len(jobs)} jobs...")
            updates = []

    print("\n=== Skill Segregation Summary ===")
    cur.execute("""
        SELECT count(*) FROM company_jobs 
        WHERE is_active = TRUE AND jsonb_array_length(must_have_skills) > 0;
    """)
    with_must_have = cur.fetchone()[0]

    cur.execute("""
        SELECT count(*) FROM company_jobs 
        WHERE is_active = TRUE AND jsonb_array_length(nice_to_have_skills) > 0;
    """)
    with_nice_to_have = cur.fetchone()[0]

    print(f"Jobs with Must-Have Skills: {with_must_have} / {len(jobs)}")
    print(f"Jobs with Nice-to-Have Skills: {with_nice_to_have} / {len(jobs)}")

    cur.execute("""
        SELECT company_name, title, must_have_skills, nice_to_have_skills
        FROM company_jobs
        WHERE is_active = TRUE AND jsonb_array_length(must_have_skills) > 0
        LIMIT 5;
    """)
    samples = cur.fetchall()
    print("\n=== Sample Enriched Roles ===")
    for s in samples:
        print(f"[{s[0]}] {s[1]}")
        print(f"  Must-Have: {s[2]}")
        print(f"  Nice-to-Have: {s[3]}\n")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
