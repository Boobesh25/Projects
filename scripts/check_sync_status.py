import psycopg2
import subprocess
import os

DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:MySecretPassword123@127.0.0.1:5432/career_portal")

def check_status():
    print("=== WORKER PROCESS STATUS ===")
    try:
        ps_out = subprocess.check_output("ps aux | grep cloud_sync_worker.py | grep -v grep || true", shell=True).decode()
        print(ps_out.strip() or "No process running")
    except Exception as e:
        print(f"Error checking ps: {e}")

    print("\n=== RECENT SYNC LOG (LAST 30 LINES) ===")
    try:
        if os.path.exists("/home/sboobesh/scripts/sync.log"):
            log_out = subprocess.check_output("tail -n 30 /home/sboobesh/scripts/sync.log", shell=True).decode()
            print(log_out)
        else:
            print("sync.log not found yet.")
    except Exception as e:
        print(f"Error reading log: {e}")

    print("\n=== DATABASE SYNC STATE ===")
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT id, status, stage, progress_pct, total_ingested, new_jobs_added, started_at, error_message FROM sync_job_states ORDER BY started_at DESC LIMIT 1;")
        sync_state = cur.fetchone()
        print(f"sync_job_states: {sync_state}")
        
        cur.execute("SELECT count(*) FROM company_jobs;")
        job_count = cur.fetchone()[0]
        print(f"company_jobs total count: {job_count}")
        
        if job_count > 0:
            cur.execute("SELECT company_name, title, location, work_mode, experience_text, source_channel, skills_required, must_have_skills FROM company_jobs ORDER BY created_at DESC LIMIT 3;")
            sample_jobs = cur.fetchall()
            print("\nSample ingested jobs:")
            for j in sample_jobs:
                print(f"- [{j[5]}] {j[0]} | {j[1]} | {j[2]} | {j[3]} | Exp: {j[4]} | Skills: {j[6][:60] if j[6] else ''}...")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error checking DB: {e}")

if __name__ == "__main__":
    check_status()
