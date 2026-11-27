import psycopg2
import os

DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:MySecretPassword123@127.0.0.1:5432/career_portal")

def clean_database():
    print(f"Connecting to {DB_URL}...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # 1. Truncate company_jobs
    print("Truncating company_jobs...")
    cur.execute("TRUNCATE TABLE company_jobs CASCADE;")
    
    # 2. Truncate sync_job_states
    print("Truncating sync_job_states...")
    cur.execute("TRUNCATE TABLE sync_job_states CASCADE;")
    
    # 3. Drop stale stage1_discovered_jobs if exists
    print("Dropping stale stage1_discovered_jobs if present...")
    cur.execute("DROP TABLE IF EXISTS stage1_discovered_jobs CASCADE;")
    
    conn.commit()
    
    # Verify counts
    cur.execute("SELECT count(*) FROM company_jobs;")
    cj_count = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM sync_job_states;")
    sjs_count = cur.fetchone()[0]
    
    print(f"Cleanup verification: company_jobs count = {cj_count}, sync_job_states count = {sjs_count}")
    cur.close()
    conn.close()

if __name__ == "__main__":
    clean_database()
