import psycopg2

DB_URL = "postgresql://postgres:MySecretPassword123@127.0.0.1:5432/career_portal"

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

FOREIGN_URL_PREFIXES = [
    "/ca-en/", "/ca-fr/", "/emea-de/", "/emea-fr/", "/emea-es/", "/emea-nl/",
    "/latam-es/", "/latam-pt/", "/apj-jp/", "/apj-ph/", "/apj-cn/", "/apj-en/",
    "/uki-en/", "/global-en/", "/us-en/", "/de-de/", "/fr-fr/", "/es-es/",
    "/it-it/", "/nl-nl/", "/pl-pl/", "/pt-br/", "/ja-jp/", "/ko-kr/", "/zh-cn/",
    "/zh-tw/", "/en-us/", "/en-gb/", "/en-ca/", "/en-au/", "/en-sg/", "/en-ph/"
]

conditions = [f"url ILIKE '%{prefix}%'" for prefix in FOREIGN_URL_PREFIXES]
where_clause = " OR ".join(conditions)

cur.execute(f"""
    SELECT count(*) FROM company_jobs
    WHERE is_active = TRUE
      AND work_mode != 'Remote'
      AND ({where_clause});
""")
count = cur.fetchone()[0]
print(f"Found {count} jobs with foreign locale subpaths marked as On-site/Hybrid.")

if count > 0:
    cur.execute(f"""
        DELETE FROM company_jobs
        WHERE is_active = TRUE
          AND work_mode != 'Remote'
          AND ({where_clause});
    """)
    deleted = cur.rowcount
    conn.commit()
    print(f"Deleted {deleted} foreign regional jobs.")

cur.execute("SELECT count(*) FROM company_jobs WHERE is_active = TRUE;")
remaining = cur.fetchone()[0]
print(f"Remaining clean India & Global Remote jobs in DB: {remaining}")

cur.close()
conn.close()
