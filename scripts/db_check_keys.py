import psycopg2

conn = psycopg2.connect("postgresql://postgres:MySecretPassword123@127.0.0.1:5432/career_portal")
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
print("Tables in career_portal:", [r[0] for r in cur.fetchall()])
