"""
Universal Ingestion and Extraction Engine
==========================================
Extracts structured job content across heterogeneous career pages.
Tier 1: Direct ATS APIs (Greenhouse, Lever, Ashby)
Tier 2: JSON-LD Schema.org JobPosting microdata
Tier 3: Context-preserving HTML-to-Markdown parser
"""

import re
import json
from urllib.parse import urlparse
from typing import Optional, Tuple, List, Dict, Any
import requests
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
from .models import JobPosting

class CareerPageExtractor:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8"
    }

    # Curated technical keyword lexicon for automated token detection
    KNOWN_TECH_TOKENS = [
        "python", "fastapi", "flask", "django", "langgraph", "langchain", "llamaindex",
        "model context protocol", "mcp", "react", "rag", "retrieval-augmented generation",
        "pgvector", "qdrant", "chromadb", "pinecone", "faiss", "redis", "kafka",
        "docker", "kubernetes", "argocd", "opentelemetry", "openlit", "gemini",
        "aws bedrock", "azure openai", "postgresql", "mysql", "sql", "pandas", "numpy",
        "agentic", "multi-agent", "prompt engineering", "embeddings", "git", "gitops",
        "aws", "azure", "gcp", "google cloud", "machine learning", "generative ai"
    ]

    @classmethod
    def extract_from_url(cls, url: str) -> Optional[JobPosting]:
        domain = urlparse(url).netloc.lower()

        # Tier 1A: Greenhouse API check
        if "boards.greenhouse.io" in domain or "greenhouse.io" in url:
            gh_job = cls._extract_greenhouse(url)
            if gh_job:
                return gh_job

        # Tier 1B: Lever API check
        if "jobs.lever.co" in domain:
            lever_job = cls._extract_lever(url)
            if lever_job:
                return lever_job

        # Tier 2 & 3: Generic Web Page via HTML + JSON-LD + Clean Markdown
        return cls._extract_generic_html(url)

    @classmethod
    def extract_from_json_dict(cls, data: Dict[str, Any], url: str = "") -> JobPosting:
        """Parses a local or raw JSON dictionary into canonical JobPosting"""
        raw_text = data.get("raw_text") or data.get("raw_description") or data.get("content") or ""
        soup = BeautifulSoup(raw_text, "html.parser")
        clean_text = soup.get_text(separator="\n")

        min_exp = data.get("min_experience_years")
        max_exp = data.get("max_experience_years")
        if min_exp is None and "work_experience" in data:
            min_exp, max_exp = cls._parse_experience_years(data["work_experience"])
        elif min_exp is None:
            min_exp, max_exp = cls._parse_experience_years(clean_text)

        # Collect explicit skills or infer from description
        skills = data.get("tech_stack", [])
        if not skills:
            skills = data.get("must_have_skills", []) + data.get("preferred_skills", [])
        
        found_tokens = cls._find_tech_tokens(clean_text)
        combined_skills = list(set([s.lower() for s in skills] + found_tokens))

        loc_val = data.get("location", "Unspecified")
        if isinstance(loc_val, dict):
            loc_str = loc_val.get("name") or "Unspecified"
        else:
            loc_str = str(loc_val) if loc_val else "Unspecified"

        company_name = data.get("company")
        if not company_name:
            target_url = data.get("url") or data.get("absolute_url") or url
            gh_m = re.search(r"greenhouse\.io/([^/]+)/jobs", target_url)
            if gh_m:
                company_name = gh_m.group(1).capitalize()
            else:
                company_name = "Unknown"

        return JobPosting(
            url=data.get("url", url) or data.get("absolute_url", ""),
            company=company_name,
            title=data.get("title", "Job Posting"),
            location=loc_str,
            job_id=data.get("job_id") or str(data.get("id", "")),
            posted_date=data.get("posted_date") or data.get("updated_at"),
            service_line=data.get("service_line"),
            min_experience_years=min_exp,
            max_experience_years=max_exp,
            educational_requirements=data.get("educational_requirements", []),
            must_have_skills=data.get("must_have_skills", combined_skills[:8]),
            nice_to_have_skills=data.get("nice_to_have_skills", combined_skills[8:]),
            tech_stack=combined_skills,
            responsibilities=data.get("responsibilities", []),
            raw_markdown=clean_text
        )

    @classmethod
    def _extract_greenhouse(cls, url: str) -> Optional[JobPosting]:
        try:
            match = re.search(r"greenhouse\.io/([^/]+)/jobs/(\d+)", url)
            if match:
                company, job_id = match.groups()
                api_url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{job_id}"
                resp = requests.get(api_url, headers=cls.HEADERS, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    soup = BeautifulSoup(data.get("content", ""), "html.parser")
                    clean_text = soup.get_text(separator="\n")
                    min_exp, max_exp = cls._parse_experience_years(clean_text)
                    tokens = cls._find_tech_tokens(clean_text)

                    return JobPosting(
                        url=url,
                        company=company.capitalize(),
                        title=data.get("title", ""),
                        location=data.get("location", {}).get("name", "Remote/Unspecified"),
                        job_id=str(job_id),
                        posted_date=data.get("updated_at"),
                        min_experience_years=min_exp,
                        max_experience_years=max_exp,
                        raw_markdown=clean_text,
                        tech_stack=tokens,
                        must_have_skills=tokens[:8],
                        nice_to_have_skills=tokens[8:]
                    )
        except Exception:
            pass
        return None

    @classmethod
    def _extract_lever(cls, url: str) -> Optional[JobPosting]:
        try:
            match = re.search(r"jobs\.lever\.co/([^/]+)/([a-f0-9\-]+)", url)
            if match:
                company, job_id = match.groups()
                api_url = f"https://api.lever.co/v0/postings/{company}/{job_id}"
                resp = requests.get(api_url, headers=cls.HEADERS, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    desc = data.get("descriptionPlain", "") or ""
                    for item in data.get("lists", []):
                        desc += f"\n\n{item.get('text', '')}:\n{item.get('content', '')}"
                    
                    min_exp, max_exp = cls._parse_experience_years(desc)
                    tokens = cls._find_tech_tokens(desc)

                    return JobPosting(
                        url=url,
                        company=company.capitalize(),
                        title=data.get("text", ""),
                        location=data.get("categories", {}).get("location", "Remote"),
                        job_id=job_id,
                        posted_date=str(data.get("createdAt")),
                        min_experience_years=min_exp,
                        max_experience_years=max_exp,
                        raw_markdown=desc,
                        tech_stack=tokens,
                        must_have_skills=tokens[:8],
                        nice_to_have_skills=tokens[8:]
                    )
        except Exception:
            pass
        return None

    @classmethod
    def _extract_generic_html(cls, url: str) -> Optional[JobPosting]:
        try:
            resp = requests.get(url, headers=cls.HEADERS, timeout=12)
            if resp.status_code != 200:
                return None
            
            soup = BeautifulSoup(resp.text, "html.parser")

            # Tier 2: Check for Schema.org JSON-LD microdata
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or "{}")
                    if isinstance(data, list) and len(data) > 0:
                        data = data[0]
                    if data.get("@type") == "JobPosting":
                        title = data.get("title", "")
                        comp = data.get("hiringOrganization", {}).get("name", urlparse(url).netloc)
                        desc_text = BeautifulSoup(data.get("description", ""), "html.parser").get_text(separator="\n")
                        min_exp, max_exp = cls._parse_experience_years(desc_text)
                        tokens = cls._find_tech_tokens(desc_text)

                        return JobPosting(
                            url=url,
                            company=comp,
                            title=title,
                            location=data.get("jobLocation", {}).get("address", {}).get("addressLocality", "Unspecified"),
                            posted_date=data.get("datePosted"),
                            min_experience_years=min_exp,
                            max_experience_years=max_exp,
                            raw_markdown=desc_text,
                            tech_stack=tokens,
                            must_have_skills=tokens[:8],
                            nice_to_have_skills=tokens[8:]
                        )
                except Exception:
                    continue

            # Tier 3: Hierarchical DOM cleanup
            for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                tag.decompose()

            title_elem = soup.find("h1") or soup.find("title")
            title = title_elem.get_text().strip() if title_elem else "Job Opportunity"

            clean_lines = []
            for elem in soup.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
                txt = elem.get_text().strip()
                if not txt:
                    continue
                if elem.name in ["h1", "h2", "h3", "h4"]:
                    clean_lines.append(f"\n### {txt}")
                elif elem.name == "li":
                    clean_lines.append(f"- {txt}")
                else:
                    clean_lines.append(txt)

            full_text = "\n".join(clean_lines)
            min_exp, max_exp = cls._parse_experience_years(full_text)
            tokens = cls._find_tech_tokens(full_text)

            return JobPosting(
                url=url,
                company=urlparse(url).netloc.replace("www.", "").split(".")[0].capitalize(),
                title=title,
                location="See Description",
                min_experience_years=min_exp,
                max_experience_years=max_exp,
                raw_markdown=full_text,
                tech_stack=tokens,
                must_have_skills=tokens[:8],
                nice_to_have_skills=tokens[8:]
            )
        except Exception:
            return None

    @classmethod
    def _find_tech_tokens(cls, text: str) -> List[str]:
        lower_text = text.lower()
        found = []
        for kw in cls.KNOWN_TECH_TOKENS:
            if re.search(r'\b' + re.escape(kw) + r'\b', lower_text):
                found.append(kw)
        return found

    @staticmethod
    def _parse_experience_years(text: str) -> Tuple[Optional[float], Optional[float]]:
        patterns = [
            r'(\d+)\s*[-–to]\s*(\d+)\s*\+?\s*years?',
            r'(\d+)\s*\+\s*years?',
            r'at least\s*(\d+)\s*years?',
            r'minimum\s*(?:of)?\s*(\d+)\s*years?',
            r'(\d+)\s*years?\s*(?:of)?\s*experience'
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 2 and groups[1]:
                    return float(groups[0]), float(groups[1])
                elif len(groups) >= 1:
                    return float(groups[0]), None
        return None, None
