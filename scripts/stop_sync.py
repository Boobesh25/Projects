import psycopg2
import os

DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:MySecretPassword123@127.0.0.1:5432/career_portal")

def stop_sync():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("""
        UPDATE sync_job_states 
        SET status = 'STOPPED', 
            error_message = 'Halted manually by user request', 
            completed_at = CURRENT_TIMESTAMP 
        WHERE status = 'RUNNING';
    """)
    conn.commit()
    print("Sync state updated to STOPPED in PostgreSQL.")
    cur.close()
    conn.close()

if __name__ == "__main__":
    stop_sync()
