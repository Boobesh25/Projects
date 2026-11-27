import psycopg2
import json

conn = psycopg2.connect("postgresql://postgres:MySecretPassword123@127.0.0.1:5432/career_portal")
cur = conn.cursor()

# 1. Total jobs
cur.execute("SELECT count(*) FROM company_jobs;")
total_jobs = cur.fetchone()[0]

# 2. Invalid titles
cur.execute("""
    SELECT count(*) FROM company_jobs
    WHERE title ILIKE 'opportunity at%'
       OR title ILIKE 'technical opportunity at%'
       OR title ILIKE '%?lang=%'
       OR title ILIKE '%lang=en%'
       OR title ILIKE '%?%'
       OR length(title) < 4;
""")
invalid_title_count = cur.fetchone()[0]

# 3. Sample of invalid titles
cur.execute("""
    SELECT id, company_name, title, url, location, work_mode
    FROM company_jobs
    WHERE title ILIKE 'opportunity at%'
       OR title ILIKE 'technical opportunity at%'
       OR title ILIKE '%?lang=%'
       OR title ILIKE '%lang=en%'
       OR title ILIKE '%?%'
       OR length(title) < 4
    LIMIT 10;
""")
sample_invalid = cur.fetchall()

# 4. Check for retail, sales, cashier, nurse, driver, consultant non-tech jobs
cur.execute("""
    SELECT count(*) FROM company_jobs
    WHERE url ILIKE '%retail%'
       OR url ILIKE '%cashier%'
       OR url ILIKE '%sales-consultant%'
       OR url ILIKE '%store-associate%'
       OR title ILIKE '%retail sales%'
       OR title ILIKE '%store manager%';
""")
non_tech_count = cur.fetchone()[0]

# 5. Check foreign jobs (Austin, Texas, US, UK, etc. that are NOT Remote)
cur.execute("""
    SELECT count(*) FROM company_jobs
    WHERE (url ILIKE '%/us/%' OR url ILIKE '%/job/austin/%' OR url ILIKE '%/jobs/austin/%')
      AND work_mode != 'Remote';
""")
foreign_non_remote_count = cur.fetchone()[0]

# 6. Check skills_required breakdown
cur.execute("""
    SELECT count(*) FROM company_jobs
    WHERE skills_required IS NULL OR skills_required::text = '[]' OR skills_required::text = 'null';
""")
empty_skills_count = cur.fetchone()[0]

cur.close()
conn.close()

result = {
    "total_jobs": total_jobs,
    "invalid_title_count": invalid_title_count,
    "non_tech_count": non_tech_count,
    "foreign_non_remote_count": foreign_non_remote_count,
    "empty_skills_count": empty_skills_count,
    "sample_invalid": sample_invalid
}

print(json.dumps(result, indent=2, default=str))
