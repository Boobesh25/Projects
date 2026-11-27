import psycopg2

DB_URL = "postgresql://postgres:MySecretPassword123@127.0.0.1:5432/career_portal"

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

del_sql = """
    DELETE FROM company_jobs
    WHERE is_active = TRUE
      AND work_mode != 'Remote'
      AND (
          url ~* '/(nl|de|fr|uk|es|it|ca|au|jp|cn|kr|pl|br|mx|sg|ph)/jobs/'
          OR url ~* '/emea-en/'
          OR title ~* '\\y(nyc|london|tokyo|paris|berlin|munich|singapore|sydney)\\y'
      )
      AND NOT (
          title ~* '\\y(india|bengaluru|bangalore|hyderabad|chennai|pune|mumbai|delhi|noida|gurugram|gurgaon)\\y'
          OR url ~* '\\y(india|bengaluru|bangalore|hyderabad|chennai|pune|mumbai|delhi|noida|gurugram|gurgaon)\\y'
      );
"""
cur.execute(del_sql)
deleted = cur.rowcount
conn.commit()
print(f"Purged {deleted} foreign jobs.")

cur.execute("SELECT count(*) FROM company_jobs WHERE is_active = TRUE;")
remaining = cur.fetchone()[0]
print(f"Remaining clean India & Global Remote engineering jobs: {remaining}")

cur.close()
conn.close()
