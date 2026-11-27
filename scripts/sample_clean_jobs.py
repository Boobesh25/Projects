import psycopg2
import json

DB_URL = "postgresql://postgres:MySecretPassword123@127.0.0.1:5432/career_portal"

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

cur.execute("""
    SELECT company_name, title, location, work_mode, source_channel, url
    FROM company_jobs
    WHERE is_active = TRUE
    ORDER BY random()
    LIMIT 10;
""")
samples = cur.fetchall()
for s in samples:
    print(f"[{s[4]}] {s[0]} - {s[1]} ({s[2]}, {s[3]}) -> {s[5]}")

cur.close()
conn.close()
