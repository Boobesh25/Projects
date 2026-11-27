import re
import psycopg2

DB_URL = "postgresql://postgres:MySecretPassword123@127.0.0.1:5432/career_portal"

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# Comprehensive foreign territory and city names
ALL_FOREIGN = [
    "greece", "athens", "kallithea", "poland", "katowice", "warsaw", "krakow", "wroclaw",
    "germany", "berlin", "munich", "frankfurt", "stuttgart", "hamburg", "dusseldorf",
    "france", "paris", "lyon", "toulouse", "marseille",
    "spain", "madrid", "barcelona", "valencia", "seville",
    "italy", "milan", "rome", "turin", "bologna",
    "united kingdom", "london", "manchester", "birmingham", "edinburgh", "glasgow", "bristol", "cambridge",
    "ireland", "dublin", "cork", "galway",
    "netherlands", "amsterdam", "rotterdam", "utrecht", "eindhoven", "hague",
    "belgium", "brussels", "antwerp", "ghent",
    "switzerland", "zurich", "geneva", "basel", "lausanne",
    "sweden", "stockholm", "gothenburg", "malmo",
    "norway", "oslo", "bergen", "denmark", "copenhagen", "finland", "helsinki",
    "austria", "vienna", "graz", "linz", "salzburg",
    "czech", "prague", "brno", "hungary", "budapest", "romania", "bucharest", "cluj",
    "bulgaria", "sofia", "serbia", "belgrade", "croatia", "zagreb", "slovakia", "bratislava",
    "portugal", "lisbon", "porto",
    "china", "beijing", "shanghai", "shenzhen", "guangzhou", "chengdu", "hangzhou", "wuhan",
    "japan", "tokyo", "osaka", "yokohama", "kyoto", "nagoya",
    "korea", "seoul", "busan", "incheon", "pyeongtaek", "hwaseong", "icheon",
    "taiwan", "taipei", "hsinchu", "hong kong",
    "singapore", "malaysia", "kuala lumpur", "penang",
    "philippines", "manila", "cebu", "thailand", "bangkok", "vietnam", "hanoi", "ho chi minh",
    "indonesia", "jakarta",
    "australia", "sydney", "melbourne", "brisbane", "perth", "adelaide", "canberra",
    "new zealand", "auckland", "wellington",
    "united states", "usa", "austin", "chicago", "new york", "san francisco", "seattle", "boston",
    "dallas", "atlanta", "denver", "houston", "phoenix", "san diego", "los angeles", "san jose",
    "canada", "toronto", "vancouver", "montreal", "ottawa", "calgary",
    "mexico", "mexico city", "guadalajara", "monterrey", "brazil", "sao paulo", "rio de janeiro",
    "israel", "tel aviv", "jerusalem", "haifa", "migdal haemek",
    "uae", "dubai", "abu dhabi", "saudi", "riyadh", "jeddah", "qatar", "doha",
    "south africa", "johannesburg", "cape town"
]

foreign_pat = "|".join(re.escape(w) for w in ALL_FOREIGN)
india_pat = r"india|bengaluru|bangalore|hyderabad|chennai|pune|mumbai|delhi|gurgaon|gurugram|noida|kolkata|ahmedabad|kochi|indore|coimbatore|chandigarh|jaipur|trivandrum|thiruvananthapuram"

del_sql = f"""
    DELETE FROM company_jobs
    WHERE is_active = TRUE
      AND work_mode != 'Remote'
      AND (
          title ~* '\\y({foreign_pat})\\y'
          OR url ~* '\\y({foreign_pat})\\y'
      )
      AND NOT (
          title ~* '\\y({india_pat})\\y'
          OR url ~* '\\y({india_pat})\\y'
      );
"""

cur.execute(del_sql)
del_count = cur.rowcount
conn.commit()
print(f"Purged {del_count} foreign on-site jobs.")

cur.execute("SELECT count(*) FROM company_jobs WHERE is_active = TRUE;")
remaining = cur.fetchone()[0]
print(f"Total True India & Global Remote Engineering Jobs in DB: {remaining}")

cur.close()
conn.close()
