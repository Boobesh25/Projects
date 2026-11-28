import psycopg2
import os

DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:MySecretPassword123@127.0.0.1:5432/career_portal")

def run_diagnostics():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    cur.execute("SELECT count(*) FROM company_jobs;")
    total = cur.fetchone()[0]
    
    cur.execute("""
        SELECT count(*) FROM company_jobs 
        WHERE raw_description ILIKE '%cookies%' 
           OR raw_description ILIKE '%Sourced from LinkedIn%'
           OR raw_description ILIKE '%Skip to main content%'
           OR length(raw_description) < 250;
    """)
    invalid_cnt = cur.fetchone()[0]
    
    print(f"Total jobs in DB: {total}")
    print(f"Invalid / boilerplate / cookie / placeholder jobs: {invalid_cnt} ({invalid_cnt/total*100:.1f}%)" if total else "Empty DB")
    
    print("\nBreakdown of invalid jobs by reason:")
    cur.execute("SELECT count(*) FROM company_jobs WHERE raw_description ILIKE '%Sourced from LinkedIn%';")
    print(f"- LinkedIn placeholders: {cur.fetchone()[0]}")
    
    cur.execute("SELECT count(*) FROM company_jobs WHERE raw_description ILIKE '%cookies%' OR raw_description ILIKE '%Skip to main content%';")
    print(f"- Cookie banner / Nav dump: {cur.fetchone()[0]}")
    
    cur.execute("SELECT count(*) FROM company_jobs WHERE length(raw_description) < 250;")
    print(f"- Truncated / empty descriptions (< 250 chars): {cur.fetchone()[0]}")
    
    cur.execute("""
        SELECT count(*) FROM company_jobs 
        WHERE title ILIKE '%biotech%' 
           OR title ILIKE '%officer%' 
           OR title ILIKE '%civil%' 
           OR title ILIKE '%nurse%'
           OR title ILIKE '%sales%'
           OR title ILIKE '%retail%';
    """)
    print(f"- Non-IT / non-tech titles: {cur.fetchone()[0]}")
    
    print("\nSamples of valid genuine JDs:")
    cur.execute("""
        SELECT company_name, title, source_channel, length(raw_description), substring(raw_description from 1 for 180)
        FROM company_jobs
        WHERE raw_description NOT ILIKE '%cookies%'
          AND raw_description NOT ILIKE '%Sourced from LinkedIn%'
          AND length(raw_description) > 300
        LIMIT 3;
    """)
    for r in cur.fetchall():
        print(f"[{r[2]}] {r[0]} - {r[1]} (Len: {r[3]}): {r[4]}...\n")
        
    cur.close()
    conn.close()

if __name__ == "__main__":
    run_diagnostics()
