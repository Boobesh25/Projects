import psycopg2
import os

DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:MySecretPassword123@127.0.0.1:5432/career_portal")

def purge_invalid_jobs():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    cur.execute("SELECT count(*) FROM company_jobs;")
    before_count = cur.fetchone()[0]
    print(f"Total jobs in DB before purge: {before_count}")
    
    cur.execute("""
        DELETE FROM company_jobs 
        WHERE raw_description ILIKE '%cookies%' 
           OR raw_description ILIKE '%Sourced from LinkedIn%'
           OR raw_description ILIKE '%Skip to main content%'
           OR raw_description ILIKE '%Direct URL:%'
           OR raw_description ILIKE '%Requisition ID:%'
           OR length(raw_description) < 250
           OR title ILIKE '%biotech%'
           OR title ILIKE '%officer%'
           OR title ILIKE '%sales%'
           OR title ILIKE '%retail%'
           OR title ILIKE '%nurse%'
           OR title ILIKE '%civil%'
           OR title ILIKE '%opportunity at%'
           OR title ILIKE '?lang=%';
    """)
    purged_count = cur.rowcount
    conn.commit()
    
    cur.execute("SELECT count(*) FROM company_jobs;")
    after_count = cur.fetchone()[0]
    print(f"Purged {purged_count} invalid/boilerplate jobs.")
    print(f"Remaining high-quality, authentic jobs in DB: {after_count}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    purge_invalid_jobs()
