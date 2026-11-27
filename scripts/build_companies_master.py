#!/usr/bin/env python3
"""
Master Companies List Generator
Designed to execute on your remote cloud server inside Docker / Linux.
"""

import json
import urllib.request
import csv
import re
import os
import sys

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

LEGAL_SUFFIXES = [
    r'\binc\.?\b', r'\bcorp\.?\b', r'\bcorporation\b', r'\bltd\.?\b', 
    r'\blimited\b', r'\bllc\b', r'\bpvt\.?\b', r'\bprivate\b', 
    r'\bplc\b', r'\bse\b', r'\bag\b', r'\bgmbh\b', r'\bsa\b',
    r'\btechnologies\b', r'\btechnology\b', r'\bsolutions\b', r'\bservices\b'
]

def clean_company_name(name: str) -> str:
    cleaned = name.strip()
    cleaned = re.sub(r'\(.*?\)', '', cleaned).strip()
    return cleaned

def normalize_key(name: str) -> str:
    norm = name.lower()
    for suff in LEGAL_SUFFIXES:
        norm = re.sub(suff, '', norm)
    return re.sub(r'[^a-z0-9]', '', norm)

def derive_domain_guess(name: str) -> str:
    norm = normalize_key(name)
    return f"{norm}.com" if norm else ""

def main():
    print("=" * 70)
    print("Building Master Companies List on Cloud Server")
    print("=" * 70)

    companies_dict = {}

    # 1. Load Local Curated Directory (2,075 companies)
    local_paths = ["enterprise_company_directory.json", "scripts/enterprise_company_directory.json", "/tmp/scripts/enterprise_company_directory.json"]
    loaded_local = False
    for p in local_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    local_data = json.load(f)
                    for category, names in local_data.items():
                        for raw_name in names:
                            clean_n = clean_company_name(raw_name)
                            key = normalize_key(clean_n)
                            if key and key not in companies_dict:
                                companies_dict[key] = {
                                    "name": clean_n,
                                    "domain": derive_domain_guess(clean_n),
                                    "category": category
                                }
                print(f"[OK] Ingested 2,075 base companies from {p}")
                loaded_local = True
                break
            except Exception as e:
                print(f"[WARN] Error reading {p}: {e}")

    # 2. Ingest S&P 500 Enterprises (GitHub Open Dataset)
    try:
        sp500_url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        req = urllib.request.Request(sp500_url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            lines = [line.decode('utf-8', errors='ignore') for line in resp.readlines()]
            reader = csv.DictReader(lines)
            sp_count = 0
            for row in reader:
                sec_name = row.get("Security") or row.get("Name") or ""
                clean_n = clean_company_name(sec_name)
                key = normalize_key(clean_n)
                if key and key not in companies_dict:
                    companies_dict[key] = {
                        "name": clean_n,
                        "domain": derive_domain_guess(clean_n),
                        "category": "S&P 500 Enterprise"
                    }
                    sp_count += 1
            print(f"[OK] Ingested {sp_count} new enterprises from S&P 500 dataset.")
    except Exception as e:
        print(f"[WARN] S&P 500 ingestion notice: {e}")

    # 3. Ingest Nifty 500 Indian Enterprises
    nifty_urls = [
        "https://raw.githubusercontent.com/anirudhpillai/nifty500_companies/master/ind_nifty500list.csv",
        "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    ]
    for n_url in nifty_urls:
        try:
            req = urllib.request.Request(n_url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as resp:
                lines = [line.decode('utf-8', errors='ignore') for line in resp.readlines()]
                reader = csv.DictReader(lines)
                nifty_count = 0
                for row in reader:
                    c_name = row.get("Company Name") or row.get("name") or ""
                    clean_n = clean_company_name(c_name)
                    key = normalize_key(clean_n)
                    if key and key not in companies_dict:
                        companies_dict[key] = {
                            "name": clean_n,
                            "domain": derive_domain_guess(clean_n),
                            "category": "India_Enterprise"
                        }
                        nifty_count += 1
                print(f"[OK] Ingested {nifty_count} new corporations from Nifty 500 dataset.")
                break
        except Exception as e:
            continue

    # 4. Ingest Y Combinator Tech Startups
    yc_urls = [
        "https://raw.githubusercontent.com/fake-names/y-combinator-companies/master/companies.json",
        "https://raw.githubusercontent.com/gorhack/yc-companies/main/data/companies.json"
    ]
    for y_url in yc_urls:
        try:
            req = urllib.request.Request(y_url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req, timeout=12) as resp:
                yc_data = json.loads(resp.read().decode('utf-8'))
                yc_count = 0
                for item in yc_data:
                    name = (item.get("name") or item.get("company_name") or "").strip()
                    website = (item.get("website") or item.get("url") or "").strip()
                    domain = website.replace("https://", "").replace("http://", "").split("/")[0].replace("www.", "")
                    clean_n = clean_company_name(name)
                    key = normalize_key(clean_n)
                    if key and key not in companies_dict:
                        companies_dict[key] = {
                            "name": clean_n,
                            "domain": domain or derive_domain_guess(clean_n),
                            "category": "YC_Tech_Startup"
                        }
                        yc_count += 1
                print(f"[OK] Ingested {yc_count} new startups from Y Combinator dataset.")
                break
        except Exception as e:
            continue

    master_list = list(companies_dict.values())
    total_count = len(master_list)

    print("\n" + "=" * 70)
    print(f"MASTER COMPANIES GENERATION COMPLETE: {total_count} TOTAL COMPANIES")
    print("=" * 70)

    cat_counts = {}
    for c in master_list:
        cat = c["category"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    for cat, count in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True):
        print(f" - {cat:<24}: {count} companies")

    output_file = "/tmp/scripts/master_companies_list.json" if os.path.exists("/tmp/scripts") else "master_companies_list.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(master_list, f, indent=2)

    print("=" * 70)
    print(f"Saved master file to: {output_file} ({round(os.path.getsize(output_file)/1024, 1)} KB)")

if __name__ == "__main__":
    main()
