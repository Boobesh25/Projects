import psycopg2
import json

conn = psycopg2.connect("postgresql://postgres:MySecretPassword123@127.0.0.1:5432/career_portal")
cur = conn.cursor()

# 1. Total jobs and channel breakdown
cur.execute("""
    SELECT source_channel, count(*), count(DISTINCT company_name)
    FROM company_jobs
    WHERE is_active = TRUE
    GROUP BY source_channel
    ORDER BY count(*) DESC;
""")
channel_stats = cur.fetchall()

# 2. Sync job states (last 3)
cur.execute("""
    SELECT id, status, stage, progress_pct, total_ingested, new_jobs_added, started_at, completed_at
    FROM sync_job_states
    ORDER BY started_at DESC
    LIMIT 3;
""")
sync_stats = cur.fetchall()

# 3. Recent LinkedIn jobs with AI extracted skills and description
cur.execute("""
    SELECT company_name, title, location, work_mode, experience_text, min_exp, max_exp, skills_required, substring(raw_description, 1, 200)
    FROM company_jobs
    WHERE source_channel = 'LinkedIn' AND is_active = TRUE
    ORDER BY created_at DESC
    LIMIT 5;
""")
recent_linkedin = cur.fetchall()

cur.close()
conn.close()

result = {
    "channel_stats": channel_stats,
    "sync_stats": sync_stats,
    "recent_linkedin_samples": recent_linkedin
}

print(json.dumps(result, indent=2, default=str))
