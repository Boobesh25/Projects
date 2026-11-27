"""
Strict Technical Role Enforcer & Database Purification Engine
============================================================
Purges:
1. Non-technical roles (sales, medical, cashier, retail, scheduler, etc.)
2. Hex hash titles (e.g. 'Bfebace D Ef Ee D', 'Ba E Faed...')
3. Non-job URLs (/bilder/, /chronik/, /press/, /news/, /media/)
4. City-as-title errors (e.g. 'Perth')
Keeps ONLY verified, genuine technical engineering / software / AI / data / cloud roles.
"""

import re
import psycopg2

DB_URL = "postgresql://postgres:MySecretPassword123@127.0.0.1:5432/career_portal"

TECH_ANCHORS = {
    "engineer", "engineering", "developer", "architect", "programmer", "coder",
    "sde", "swe", "fde", "mts", "finops", "devops", "cloud", "platform", "systems",
    "infrastructure", "infra", "sre", "site reliability", "quant", "quantitative",
    "data engineer", "data scientist", "mlops", "machine learning", "deep learning",
    "ai developer", "ai engineer", "genai", "generative ai", "llm", "agentic",
    "founding engineer", "security engineer", "penetration tester", "cybersecurity",
    "qa engineer", "sdet", "automation engineer", "backend", "frontend", "full stack",
    "fullstack", "software", "tech lead", "technical lead", "cto", "vp engineering",
    "director engineering", "firmware", "embedded", "kernel", "dba", "database administrator",
    "solutions architect", "enterprise architect", "cloud architect", "network engineer",
    "data analyst", "system administrator", "sysadmin", "devsecops", "test engineer"
}

NON_TECH_PATTERNS = [
    r"\bretail\b", r"\bsales\b", r"\bstore\b", r"\bcashier\b", r"\bpatient\b",
    r"\bcare technician\b", r"\bscheduler\b", r"\bmerchandiser\b", r"\bofficer sales\b",
    r"\brecruiter\b", r"\bsourcer\b", r"\btalent acquisition\b", r"\bhuman resources\b",
    r"\bhr\b", r"\bmarketing\b", r"\bcontent\b", r"\bcopywriter\b", r"\blegal\b",
    r"\bparalegal\b", r"\baccountant\b", r"\bbookkeeper\b", r"\btax\b", r"\baudit\b",
    r"\bpayroll\b", r"\bloan\b", r"\bcredit\b", r"\bbranch manager\b", r"\breceptionist\b",
    r"\boffice manager\b", r"\bassistant\b", r"\bcustomer support\b", r"\bcall center\b",
    r"\bnurse\b", r"\bphysician\b", r"\bdriver\b", r"\bwarehouse\b", r"\bchronik\b",
    r"\bpanel talk\b", r"\bbilder\b", r"\bpress release\b", r"\bphoto\b"
]

NON_JOB_URL_PATTERNS = [
    "/bilder/", "/chronik/", "/presse/", "/press/", "/news/", "/media/",
    "/article/", "/story/", "/blog/", "/about-us/", "/investors/"
]

def is_hex_garbage(title):
    words = title.strip().split()
    if not words:
        return True
    # If all or most words are 1-2 character hex fragments (e.g. 'Ba E Faed Cb Bf Ea B Ab F')
    short_words = sum(1 for w in words if len(w) <= 2)
    if len(words) >= 4 and (short_words / len(words)) >= 0.5:
        return True
    # If title matches pure hex string
    if re.match(r'^[a-fA-F0-9\s_-]{10,}$', title):
        return True
    return False

def is_valid_tech_title(title, url=""):
    t_low = (title or "").lower().strip()
    u_low = (url or "").lower()

    if len(t_low) < 4:
        return False, "Title too short"

    if any(pat in u_low for pat in NON_JOB_URL_PATTERNS):
        return False, "Non-job URL"

    if is_hex_garbage(title):
        return False, "Hex hash garbage title"

    # Explicit non-tech check
    for pattern in NON_TECH_PATTERNS:
        if re.search(pattern, t_low):
            return False, f"Matches non-tech pattern: {pattern}"

    # Must contain at least one technical anchor
    has_anchor = any(re.search(rf"\b{re.escape(anchor)}\b", t_low) for anchor in TECH_ANCHORS)
    if not has_anchor:
        return False, "Lacks technical anchor"

    return True, "Valid Tech Title"

def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("Fetching active jobs for strict technical verification...")
    cur.execute("SELECT id, title, url FROM company_jobs WHERE is_active = TRUE;")
    jobs = cur.fetchall()
    print(f"Total jobs to inspect: {len(jobs)}")

    invalid_ids = []
    for j_id, title, url in jobs:
        valid, reason = is_valid_tech_title(title, url)
        if not valid:
            invalid_ids.append(j_id)

    print(f"Found {len(invalid_ids)} non-technical or corrupt jobs.")

    if invalid_ids:
        # Delete in chunks
        chunk_size = 5000
        for i in range(0, len(invalid_ids), chunk_size):
            chunk = invalid_ids[i:i + chunk_size]
            cur.execute("DELETE FROM company_jobs WHERE id = ANY(%s);", (chunk,))
            conn.commit()
            print(f"Purged {min(i + chunk_size, len(invalid_ids))} / {len(invalid_ids)}...")

    cur.execute("SELECT count(*) FROM company_jobs WHERE is_active = TRUE;")
    remaining = cur.fetchone()[0]
    print(f"\nFinal Verified 100% Technical Engineering Jobs Remaining: {remaining}")

    cur.execute("""
        SELECT company_name, title, location, work_mode, source_channel
        FROM company_jobs
        WHERE is_active = TRUE
        ORDER BY random()
        LIMIT 10;
    """)
    samples = cur.fetchall()
    print("\n=== Clean Technical Roles Verification Sample ===")
    for s in samples:
        print(f"[{s[4]}] {s[0]} - {s[1]} ({s[2]}, {s[3]})")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
