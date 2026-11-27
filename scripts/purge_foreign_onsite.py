import psycopg2
import re

DB_URL = "postgresql://postgres:MySecretPassword123@127.0.0.1:5432/career_portal"

FOREIGN_TERMS = [
    "china", "chengdu", "shanghai", "beijing", "shenzhen", "poland", "katowice", "warsaw", "krakow",
    "japan", "tokyo", "osaka", "austria", "graz", "vienna", "germany", "berlin", "munich", "frankfurt",
    "france", "paris", "israel", "tel aviv", "korea", "seoul", "taiwan", "taipei", "singapore",
    "australia", "sydney", "melbourne", "united kingdom", "london", "manchester", "canada", "toronto",
    "vancouver", "united states", "usa", "austin", "chicago", "new york", "san francisco", "seattle",
    "boston", "dallas", "atlanta", "denver", "ireland", "dublin", "netherlands", "amsterdam", "brazil",
    "mexico", "spain", "madrid", "italy", "milan", "rome"
]

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# Find foreign on-site in title or location
conditions = []
for term in FOREIGN_TERMS:
    conditions.append(f"title ILIKE '% {term}%'")
    conditions.append(f"title ILIKE '% in {term}%'")
    conditions.append(f"url ILIKE '%-{term}-%'")
    conditions.append(f"url ILIKE '%/{term}/%'")
    conditions.append(f"location ILIKE '%{term}%'")

where_foreign = " OR ".join(conditions)

query_count = f"""
    SELECT count(*) FROM company_jobs
    WHERE is_active = TRUE
      AND work_mode != 'Remote'
      AND ({where_foreign})
      AND NOT (
          title ILIKE '%india%' OR location ILIKE '%india%' 
          OR location ILIKE '%bengaluru%' OR location ILIKE '%bangalore%'
          OR location ILIKE '%hyderabad%' OR location ILIKE '%chennai%'
          OR location ILIKE '%pune%' OR location ILIKE '%mumbai%'
          OR location ILIKE '%noida%' OR location ILIKE '%delhi%'
          OR location ILIKE '%gurgaon%' OR location ILIKE '%gurugram%'
      );
"""
cur.execute(query_count)
foreign_count = cur.fetchone()[0]
print(f"Found {foreign_count} foreign on-site jobs falsely assigned to India or Non-Remote.")

# Delete them
del_query = f"""
    DELETE FROM company_jobs
    WHERE is_active = TRUE
      AND work_mode != 'Remote'
      AND ({where_foreign})
      AND NOT (
          title ILIKE '%india%' OR location ILIKE '%india%' 
          OR location ILIKE '%bengaluru%' OR location ILIKE '%bangalore%'
          OR location ILIKE '%hyderabad%' OR location ILIKE '%chennai%'
          OR location ILIKE '%pune%' OR location ILIKE '%mumbai%'
          OR location ILIKE '%noida%' OR location ILIKE '%delhi%'
          OR location ILIKE '%gurgaon%' OR location ILIKE '%gurugram%'
      );
"""
cur.execute(del_query)
deleted = cur.rowcount
conn.commit()
print(f"Successfully deleted {deleted} foreign on-site jobs.")

cur.execute("SELECT count(*) FROM company_jobs WHERE is_active = TRUE;")
remaining = cur.fetchone()[0]
print(f"True India & Global Remote active technical jobs remaining: {remaining}")

cur.close()
conn.close()
