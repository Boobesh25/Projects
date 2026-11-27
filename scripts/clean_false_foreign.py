import psycopg2

DB_URL = "postgresql://postgres:MySecretPassword123@127.0.0.1:5432/career_portal"

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# Fast regex for foreign countries/cities
foreign_regex = r'(china|chengdu|shanghai|beijing|shenzhen|poland|katowice|warsaw|krakow|japan|tokyo|osaka|austria|graz|vienna|germany|berlin|munich|frankfurt|france|paris|israel|tel aviv|korea|seoul|taiwan|taipei|australia|sydney|melbourne|london|manchester|canada|toronto|vancouver|usa|austin|chicago|seattle|boston|dallas|ireland|dublin|netherlands|amsterdam|brazil|mexico|spain|madrid|italy|milan|rome|romania|bucharest|hungary|budapest|czech|prague|sweden|stockholm|switzerland|zurich)'

india_regex = r'(india|bengaluru|bangalore|hyderabad|chennai|pune|mumbai|delhi|gurgaon|gurugram|noida)'

del_query = f"""
    DELETE FROM company_jobs
    WHERE is_active = TRUE
      AND work_mode != 'Remote'
      AND (title ~* '\\y{foreign_regex}\\y' OR url ~* '\\y{foreign_regex}\\y')
      AND NOT (title ~* '\\y{india_regex}\\y' OR url ~* '\\y{india_regex}\\y');
"""
cur.execute(del_query)
deleted = cur.rowcount
conn.commit()
print(f"Deleted {deleted} foreign on-site jobs falsely assigned.")

cur.execute("SELECT count(*) FROM company_jobs WHERE is_active = TRUE;")
remaining = cur.fetchone()[0]
print(f"Remaining clean, grounded jobs: {remaining}")

cur.close()
conn.close()
