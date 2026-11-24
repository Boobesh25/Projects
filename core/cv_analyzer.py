"""
Document & Profile Extractor Module
===================================
Parses uploaded candidate documents (PDF, DOCX, TXT, MD, YAML) and generates
the canonical YAML profile ground truth.
Supports:
1. Google Gemini API (if user configured api_key or GEMINI_API_KEY env var)
2. High-precision deterministic NLP parser capturing ALL sections:
   - Candidate Header & Contact Information (Email, Phone, Links, Location)
   - Professional Summary & Objectives
   - Core Technical Skills (categorized and comprehensive)
   - Professional Experience (ALL companies, roles, and ALL bullet points & expressions)
   - Flagship & Personal Projects (names, tech stacks, links, all bullets)
   - Education & Credentials (degrees, universities, dates, coursework)
   - Certifications & Licenses
"""

import io
import os
import re
import yaml
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional
import pypdf
import docx
import requests

class DocumentProfileAnalyzer:
    """Extracts raw text and converts into structured profile.yaml format."""

    @classmethod
    def extract_text(cls, file_bytes: bytes, filename: str) -> str:
        lower_fn = filename.lower()
        if lower_fn.endswith(".pdf"):
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            text_parts = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
            return "\n".join(text_parts)
        elif lower_fn.endswith(".docx"):
            doc = docx.Document(io.BytesIO(file_bytes))
            text_parts = []
            for p in doc.paragraphs:
                if p.text and p.text.strip():
                    text_parts.append(p.text.strip())
            # Also extract text from any tables (very common in resumes)
            for table in doc.tables:
                for row in table.rows:
                    row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_cells:
                        text_parts.append(" | ".join(row_cells))
            return "\n".join(text_parts)
        else:
            try:
                return file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                return file_bytes.decode("latin-1", errors="ignore")

    @classmethod
    def generate_yaml_profile(
        cls,
        raw_text: str,
        user_name: str = "Candidate",
        api_key: Optional[str] = None
    ) -> Tuple[str, List[str], Dict[str, Any]]:
        """
        Analyzes the extracted text and outputs:
        (profile_yaml_str, verified_skills_list, profile_dict)
        """
        # 1. If text is already valid YAML containing profile structure, return it directly
        try:
            parsed_yaml = yaml.safe_load(raw_text)
            if isinstance(parsed_yaml, dict) and any(k in parsed_yaml for k in ["candidate", "skills", "skills_classic", "experience"]):
                skills = cls._collect_skills_from_dict(parsed_yaml)
                yaml_str = yaml.dump(parsed_yaml, sort_keys=False, allow_unicode=True)
                return yaml_str, skills, parsed_yaml
        except Exception:
            pass

        # 2. Check for Gemini API key (passed in or from environment)
        active_api_key = api_key or os.getenv("GEMINI_API_KEY")
        if active_api_key:
            try:
                llm_dict = cls._extract_via_gemini(raw_text, active_api_key)
                if llm_dict and isinstance(llm_dict, dict) and "candidate" in llm_dict:
                    # Enrich any missing sections using deterministic extractor
                    det_dict = cls._deterministic_parse(raw_text, default_name=user_name)
                    cls._merge_fallback_sections(llm_dict, det_dict)
                    yaml_str = yaml.dump(llm_dict, sort_keys=False, allow_unicode=True)
                    skills = cls._collect_skills_from_dict(llm_dict)
                    return yaml_str, skills, llm_dict
            except Exception:
                pass

        # 3. Dynamic comprehensive deterministic parser extracting ALL sections
        profile_dict = cls._deterministic_parse(raw_text, default_name=user_name)
        yaml_str = yaml.dump(profile_dict, sort_keys=False, allow_unicode=True)
        skills = cls._collect_skills_from_dict(profile_dict)
        return yaml_str, skills, profile_dict

    @classmethod
    def _merge_fallback_sections(cls, target: Dict[str, Any], fallback: Dict[str, Any]) -> None:
        """Enriches the primary parsed dictionary with any sections missing from target."""
        for section in ["education", "projects", "certifications", "skills", "skills_classic", "experience"]:
            if not target.get(section):
                if fallback.get(section):
                    target[section] = fallback[section]

    @classmethod
    def _split_into_sections(cls, text: str) -> Dict[str, str]:
        """
        Segments the document into standard resume sections:
        header, summary, skills, experience, projects, education, certifications, awards.
        """
        section_patterns = [
            ("summary", re.compile(r"^(?:professional\s+summary|executive\s+summary|profile\s+summary|career\s+summary|summary|objective|about\s+me)\b", re.IGNORECASE)),
            ("skills", re.compile(r"^(?:technical\s+skills|core\s+competencies|key\s+skills|technical\s+proficiencies|technical\s+expertise|skills\s*(?:&|and)\s*abilities|skills|technologies|tools\s*(?:&|and)\s*technologies)\b", re.IGNORECASE)),
            ("experience", re.compile(r"^(?:professional\s+experience|work\s+experience|employment\s+history|relevant\s+experience|experience|career\s+history|work\s+history)\b", re.IGNORECASE)),
            ("projects", re.compile(r"^(?:personal\s+projects|technical\s+projects|key\s+projects|flagship\s+projects|academic\s+projects|projects|poc\s*(?:&|and)\s*projects)\b", re.IGNORECASE)),
            ("education", re.compile(r"^(?:education\s*(?:&|and)\s*credentials|academic\s+background|educational\s+qualifications|academics|education)\b", re.IGNORECASE)),
            ("certifications", re.compile(r"^(?:certifications\s*(?:&|and)\s*licenses|licenses\s*(?:&|and)\s*certifications|certifications|credentials|certificates)\b", re.IGNORECASE)),
            ("awards", re.compile(r"^(?:honors\s*(?:&|and)\s*awards|awards\s*(?:&|and)\s*achievements|awards|achievements)\b", re.IGNORECASE)),
        ]

        lines = text.split("\n")
        sections: Dict[str, List[str]] = {"header": []}
        current_section = "header"

        for line in lines:
            trimmed = line.strip()
            # Clean leading markdown headers e.g. "## Education" -> "Education"
            clean_line = re.sub(r"^#+\s*", "", trimmed).strip()
            matched_sec = None
            if clean_line and len(clean_line) < 60:
                for sec_name, pattern in section_patterns:
                    if pattern.match(clean_line):
                        matched_sec = sec_name
                        break
            if matched_sec:
                current_section = matched_sec
                if current_section not in sections:
                    sections[current_section] = []
            else:
                sections[current_section].append(line)

        return {k: "\n".join(v).strip() for k, v in sections.items()}

    @classmethod
    def _deterministic_parse(cls, text: str, default_name: str) -> Dict[str, Any]:
        """
        Parses raw document text extracting ALL sections:
        - Candidate Info (Name, Title, Location, Contact, Links)
        - Professional Summaries
        - Core Technical Skills (from Skills section + catalog scan)
        - Professional Experience (All roles, companies, dates, and all bullet points)
        - Personal & Technical Projects (Name, stack, links, bullets)
        - Education & Credentials (Degrees, universities, dates, relevance)
        - Certifications & Licenses
        """
        sections = cls._split_into_sections(text)
        header_text = sections.get("header", "")
        summary_text_raw = sections.get("summary", "")
        skills_text_raw = sections.get("skills", "")
        experience_text_raw = sections.get("experience", "")
        projects_text_raw = sections.get("projects", "")
        education_text_raw = sections.get("education", "")
        cert_text_raw = sections.get("certifications", "")

        lines = [l.strip() for l in text.split("\n") if l.strip()]

        # ---------------------------------------------------------------------
        # 1. Candidate Name
        # ---------------------------------------------------------------------
        candidate_name = default_name
        for l in lines[:10]:
            clean_l = re.sub(r"^#+\s*", "", l).strip()
            if re.match(r"^(curriculum vitae|resume|profile|cv|bio|personal details|contact|summary)$", clean_l, re.IGNORECASE):
                continue
            if re.match(r"^[A-Z][a-zA-Z\s\.\,\'-]{2,40}$", clean_l):
                if not any(k in clean_l.lower() for k in ["engineer", "developer", "experience", "skills", "education", "project", "summary", "email", "phone", "curriculum", "page"]):
                    candidate_name = clean_l.strip()
                    break

        # ---------------------------------------------------------------------
        # 2. Contact Information & Links
        # ---------------------------------------------------------------------
        email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
        cand_email = email_match.group(0).lower() if email_match else "candidate@example.com"

        phone_match = re.search(r"(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}", text)
        cand_phone = phone_match.group(0).strip() if phone_match else ""

        loc_match = re.search(r"\b(Bengaluru|Bangalore|Chennai|Hyderabad|Pune|Mumbai|Noida|Gurgaon|Delhi|Kolkata|Ahmedabad|Coimbatore|Kochi|Trivandrum|London|New York|San Francisco|Seattle|Austin|Boston|Remote|India|United States|UK|Canada|Germany)\b", text, re.IGNORECASE)
        cand_location = loc_match.group(0).title() if loc_match else "India"

        # Links (LinkedIn, GitHub, Portfolios)
        links: Dict[str, str] = {}
        linkedin_match = re.search(r"https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_\-]+/?", text)
        if linkedin_match:
            links["linkedin"] = linkedin_match.group(0)
        github_match = re.search(r"https?://(?:www\.)?github\.com/[a-zA-Z0-9_\-]+/?", text)
        if github_match:
            links["github"] = github_match.group(0)
        portfolio_match = re.search(r"https?://[a-zA-Z0-9_\-\.]+\.(?:app|dev|io|me|tech|com)(?:/[^\s]*)?", text)
        if portfolio_match and "linkedin" not in portfolio_match.group(0) and "github" not in portfolio_match.group(0):
            links["portfolio"] = portfolio_match.group(0)

        # ---------------------------------------------------------------------
        # 3. Professional Title
        # ---------------------------------------------------------------------
        title_catalog = [
            "GenAI Engineer", "Generative AI Engineer", "AI Engineer", "AI/ML Engineer", "Machine Learning Engineer",
            "Full Stack Developer", "Full Stack Engineer", "Python Developer", "Python Engineer", "Backend Developer",
            "Backend Engineer", "Frontend Developer", "Frontend Engineer", "Java Developer", "Java Software Engineer",
            "Software Engineer", "Senior Software Engineer", "Staff Engineer", "Lead Engineer", "Data Scientist", "Data Analyst",
            "Data Engineer", "Cloud Engineer", "DevOps Engineer", "Site Reliability Engineer", "Solutions Architect",
            "QA Engineer", "Automation Engineer", "Product Manager", "Systems Engineer", "Security Engineer"
        ]
        cand_title = "Software Engineer"
        for line in lines[:15]:
            for t in title_catalog:
                if re.search(rf"\b{re.escape(t)}\b", line, re.IGNORECASE):
                    cand_title = t
                    break
            if cand_title != "Software Engineer":
                break

        # ---------------------------------------------------------------------
        # 4. Experience Years
        # ---------------------------------------------------------------------
        year_ranges = re.findall(r"\b(20\d\d)\s*[-–—to]+\s*(20\d\d|present|current)\b", text, re.IGNORECASE)
        exp_years = 0.0
        if year_ranges:
            current_yr = 2026
            earliest = 2026
            for start_yr_str, end_yr_str in year_ranges:
                try:
                    s_yr = int(start_yr_str)
                    if 1990 < s_yr < earliest:
                        earliest = s_yr
                except Exception:
                    pass
            if earliest < current_yr:
                exp_years = float(current_yr - earliest)
        if exp_years == 0.0:
            exp_m = re.search(r"(\d+(\.\d+)?)\+?\s*years?", text, re.IGNORECASE)
            exp_years = float(exp_m.group(1)) if exp_m else 3.0

        # ---------------------------------------------------------------------
        # 5. Summary / Objective
        # ---------------------------------------------------------------------
        summary_text = ""
        if summary_text_raw:
            clean_sum_lines = [l.strip() for l in summary_text_raw.split("\n") if l.strip()]
            summary_text = " ".join(clean_sum_lines)
        if not summary_text or len(summary_text) < 30:
            summary_match = re.search(r"(?:summary|objective|about\s+me)[\s:\-]+(.*?)(?=\n\s*(?:skills|experience|education|projects)|\Z)", text, re.IGNORECASE | re.DOTALL)
            if summary_match:
                s_lines = [l.strip() for l in summary_match.group(1).split("\n") if l.strip()]
                summary_text = " ".join(s_lines[:5])
        if not summary_text or len(summary_text) < 25:
            summary_text = f"Accomplished {cand_title} with {int(exp_years)}+ years of experience designing, developing, and deploying high-impact software systems."

        # ---------------------------------------------------------------------
        # 6. Comprehensive Technical Skills Catalog
        # ---------------------------------------------------------------------
        tech_catalog = [
            # Programming Languages
            "python", "java", "javascript", "typescript", "c++", "c#", "go", "golang", "rust", "ruby", "php", "sql", "html", "css", "bash", "kotlin", "swift", "scala",
            # Frameworks & Libraries
            "fastapi", "flask", "django", "spring boot", "react", "angular", "vue", "next.js", "node.js", "express",
            "pytorch", "tensorflow", "scikit-learn", "keras", "hugging face", "pandas", "numpy", "opencv", "scipy",
            # AI / GenAI / LLM
            "rag", "langchain", "langgraph", "agentic ai", "generative ai", "llms", "prompt engineering", "gemini",
            "azure openai", "aws bedrock", "chromadb", "pgvector", "qdrant", "pinecone", "milvus", "faiss", "weaviate",
            "model context protocol", "mcp", "semantic search", "embeddings", "cross-encoders", "reranking",
            # Cloud & Infrastructure
            "docker", "kubernetes", "aws", "azure", "gcp", "google cloud", "google cloud run", "terraform", "ansible", "jenkins", "ci/cd",
            "linux", "git", "github", "argocd", "opentelemetry", "openlit", "langsmith", "prometheus", "grafana", "nginx", "gunicorn",
            # Databases, Messaging & Backend
            "postgresql", "mysql", "mongodb", "redis", "kafka", "rabbitmq", "sqlalchemy", "pydantic", "rest apis", "graphql", "microservices",
            "websockets", "asyncio", "asyncpg", "server-sent events", "sse", "grpc", "keda", "hpa", "gitops"
        ]

        found_skills = set()
        lower_text = text.lower()

        # 6a. Direct catalog scan
        for tech in tech_catalog:
            if re.search(rf"\b{re.escape(tech)}\b", lower_text):
                found_skills.add(tech)

        # 6b. Parse genuine skills listed in the Skills section
        if skills_text_raw:
            for s_line in skills_text_raw.split("\n"):
                s_clean = s_line.strip().lstrip("•-*–> ")
                if not s_clean:
                    continue
                # Split category headers e.g. "Languages: Python, Java"
                if ":" in s_clean:
                    parts = s_clean.split(":", 1)
                    s_clean = parts[1].strip()
                # Split comma/pipe/bullet separated items
                raw_items = re.split(r"[,|•;/]+", s_clean)
                for item in raw_items:
                    clean_item = item.strip().lower()
                    clean_item = re.sub(r'\(.*?\)', '', clean_item).strip()
                    if clean_item and 1 < len(clean_item) < 40 and not any(k in clean_item for k in ["level", "proficient", "basic", "intermediate", "advanced", "years"]):
                        found_skills.add(clean_item)

        if not found_skills:
            found_skills = {"python", "rest apis", "docker", "git", "postgresql"}

        found_skills_list = sorted(list(found_skills))

        # Categorize skills into classic groups
        def filter_group(keywords: List[str]) -> str:
            matched = [s.title() for s in found_skills_list if any(k in s.lower() for k in keywords)]
            return ", ".join(matched) if matched else ""

        skills_classic = {
            "programming_backend": {
                "title": "Programming & Backend",
                "items": filter_group(["python", "java", "javascript", "typescript", "c++", "c#", "go", "golang", "rust", "fastapi", "django", "flask", "react", "node.js", "spring boot", "rest", "graphql", "pydantic", "sqlalchemy", "pandas", "asyncio", "nginx", "gunicorn"])
            },
            "ai_genai": {
                "title": "AI & GenAI",
                "items": filter_group(["rag", "langchain", "langgraph", "agentic", "generative ai", "llm", "prompt", "gemini", "bedrock", "openai", "pytorch", "tensorflow", "scikit", "hugging", "mcp", "semantic", "embedding", "cross-encoder", "rerank"])
            },
            "databases": {
                "title": "Databases & Storage",
                "items": filter_group(["postgresql", "postgres", "mysql", "mongodb", "redis", "qdrant", "chromadb", "pgvector", "pinecone", "milvus", "faiss", "sql"])
            },
            "messaging_streaming": {
                "title": "Messaging & Streaming",
                "items": filter_group(["kafka", "rabbitmq", "redis", "websockets", "sse", "server-sent"])
            },
            "cloud_and_devops": {
                "title": "Cloud & DevOps",
                "items": filter_group(["docker", "kubernetes", "aws", "azure", "gcp", "google cloud", "terraform", "jenkins", "ci/cd", "linux", "git", "github", "argocd", "keda", "hpa", "gitops"])
            },
            "infrastructure_observability": {
                "title": "Infrastructure & Observability",
                "items": filter_group(["opentelemetry", "openlit", "langsmith", "prometheus", "grafana", "linux", "cloud run", "nginx"])
            }
        }
        # Prune empty groups
        skills_classic = {k: v for k, v in skills_classic.items() if v["items"]}
        if not skills_classic:
            skills_classic["programming_backend"] = {
                "title": "Core Technical Competencies",
                "items": ", ".join([s.title() for s in found_skills_list[:12]])
            }

        # ---------------------------------------------------------------------
        # 7. Professional Experience (Extract ALL Companies, Roles, and Bullets)
        # ---------------------------------------------------------------------
        exp_target_text = experience_text_raw if experience_text_raw else text
        parsed_experience = cls._parse_experience_section(exp_target_text, cand_title, exp_years)

        # ---------------------------------------------------------------------
        # 8. Personal & Flagship Projects (Extract Name, Stack, Bullets, Links)
        # ---------------------------------------------------------------------
        parsed_projects = cls._parse_projects_section(projects_text_raw)

        # ---------------------------------------------------------------------
        # 9. Education (Degrees, Institutions, Dates, Relevance)
        # ---------------------------------------------------------------------
        parsed_education = cls._parse_education_section(education_text_raw or text)

        # ---------------------------------------------------------------------
        # 10. Certifications
        # ---------------------------------------------------------------------
        parsed_certs = cls._parse_certifications_section(cert_text_raw)

        # ---------------------------------------------------------------------
        # 11. Canonical Structured Profile Dictionary
        # ---------------------------------------------------------------------
        profile_dict = {
            "candidate": {
                "name": candidate_name,
                "professional_title": cand_title,
                "sub_title": f"{cand_title} • {cand_location}",
                "location": cand_location,
                "experience_years": exp_years,
                "contact": {
                    "email": cand_email,
                    "phone": cand_phone
                },
                "links": links
            },
            "summaries": {
                "primary": summary_text,
                "classic_profile": f"Skilled {cand_title} experienced in {', '.join(found_skills_list[:6])}."
            },
            "skills": {
                "core_competencies": {
                    "title": "Core Technical Competencies",
                    "items": [s.title() for s in found_skills_list]
                }
            },
            "skills_classic": skills_classic,
            "experience": parsed_experience,
            "projects": parsed_projects,
            "education": parsed_education
        }
        if parsed_certs:
            profile_dict["certifications"] = parsed_certs

        return profile_dict

    @classmethod
    def _parse_experience_section(cls, text: str, default_title: str, exp_years: float) -> List[Dict[str, Any]]:
        """Extracts every company, role, date range, and all bullet points."""
        month_names = r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\.?"
        date_pattern = re.compile(
            rf"((?:{month_names}\s+)?20\d\d)\s*[-–—to]+\s*((?:{month_names}\s+)?20\d\d|present|current)",
            re.IGNORECASE
        )

        lines = [l.rstrip() for l in text.split("\n")]
        exp_entries: List[Dict[str, Any]] = []
        current_exp: Optional[Dict[str, Any]] = None

        for idx, line in enumerate(lines):
            trimmed = line.strip()
            if not trimmed:
                continue

            dm = date_pattern.search(trimmed)
            # Check if this line contains a date range
            if dm:
                period_str = dm.group(0).strip()
                remaining_on_line = date_pattern.sub("", trimmed).strip(" |-,•\t")

                # Look at previous line for company/role
                prev_line = lines[idx - 1].strip() if idx > 0 else ""
                prev_clean = re.sub(r"^#+\s*", "", prev_line).strip(" |-,•")

                comp_name = ""
                role_name = default_title
                loc_name = ""

                # 1. Check if previous line has both Role and Company (e.g. "Software Engineer | Corent Technology")
                if "|" in prev_clean:
                    parts = [p.strip() for p in prev_clean.split("|") if p.strip()]
                    role_name = parts[0]
                    comp_name = parts[1] if len(parts) > 1 else ""
                elif " - " in prev_clean:
                    parts = [p.strip() for p in prev_clean.split(" - ") if p.strip()]
                    role_name = parts[0]
                    comp_name = parts[1] if len(parts) > 1 else ""
                elif " at " in prev_clean.lower():
                    parts = re.split(r"\s+at\s+", prev_clean, flags=re.IGNORECASE)
                    role_name = parts[0].strip()
                    comp_name = parts[1].strip() if len(parts) > 1 else ""
                # 2. Check if current line before or after date has Role/Company
                elif "|" in remaining_on_line:
                    parts = [p.strip() for p in remaining_on_line.split("|") if p.strip()]
                    if prev_clean and len(prev_clean) > 2 and not date_pattern.search(prev_clean):
                        role_name = prev_clean
                        comp_name = parts[0]
                        if len(parts) > 1:
                            loc_name = parts[1]
                    else:
                        role_name = parts[0]
                        comp_name = parts[1] if len(parts) > 1 else ""
                elif prev_clean and len(prev_clean) > 2 and not date_pattern.search(prev_clean):
                    # Check if remaining_on_line is a location or company
                    if remaining_on_line and any(k in remaining_on_line.lower() for k in ["india", "usa", "remote", "chennai", "bangalore", "bengaluru", "hyderabad", "pune", "mumbai"]):
                        loc_name = remaining_on_line
                        comp_name = prev_clean
                    elif remaining_on_line:
                        comp_name = prev_clean
                        role_name = remaining_on_line
                    else:
                        comp_name = prev_clean

                # Check if remaining line is location
                if remaining_on_line and not loc_name:
                    loc_name = remaining_on_line.strip(" |-,")

                # Sanitize company name: avoid using pure month names or locations
                if comp_name:
                    lower_comp = comp_name.lower()
                    if re.match(rf"^{month_names}$", lower_comp):
                        comp_name = prev_clean if prev_clean else "Enterprise Technology"

                if not comp_name or len(comp_name) < 2:
                    comp_name = "Enterprise Technology"

                comp_name = re.sub(r"^(at|with|company)\s*", "", comp_name, flags=re.IGNORECASE).strip()

                if current_exp:
                    exp_entries.append(current_exp)

                current_exp = {
                    "company": comp_name,
                    "role": role_name or default_title,
                    "location": loc_name or "India",
                    "period": {"display": period_str.title()},
                    "summary": f"{role_name} driving key engineering initiatives.",
                    "bullets": []
                }
            elif current_exp:
                # Accumulate bullet points and expressions under current experience
                bullet_clean = trimmed.lstrip("•-*–—›▪1234567890.) ").strip()
                if bullet_clean and len(bullet_clean) > 15:
                    current_exp["bullets"].append(bullet_clean)

        if current_exp:
            exp_entries.append(current_exp)

        # Fallback if no structured date entries matched
        if not exp_entries:
            exp_entries = [{
                "company": "Technical Experience",
                "role": default_title,
                "period": {"display": f"{int(2026 - exp_years)} - Present"},
                "summary": f"Professional software engineering experience across production systems.",
                "bullets": [l.strip().lstrip("•-*– ") for l in lines if l.strip().startswith(("•", "-", "*", "–")) and len(l.strip()) > 20][:6]
            }]

        return exp_entries

    @classmethod
    def _parse_projects_section(cls, text: str) -> List[Dict[str, Any]]:
        """Extracts personal, academic, and flagship projects with stack, links, and bullets."""
        if not text:
            return []

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        projects: List[Dict[str, Any]] = []
        curr_proj: Optional[Dict[str, Any]] = None

        for line in lines:
            clean_l = re.sub(r"^#+\s*", "", line).strip()
            # Detect project title line (e.g. "### GenAI Multi-Agent Chatbot", "Project Name", etc.)
            is_header = line.startswith("#") or (len(clean_l) < 70 and not clean_l.startswith(("•", "-", "*", "Tech Stack:", "GitHub:", "Live Demo:", "http")))
            
            if is_header and not any(k in clean_l.lower() for k in ["tech stack", "technologies", "github", "http", "skills", "experience", "education"]):
                if curr_proj:
                    projects.append(curr_proj)
                curr_proj = {
                    "name": clean_l,
                    "tech_stack": "",
                    "highlight": "",
                    "bullets": []
                }
            elif curr_proj:
                if re.match(r"^(?:tech\s*stack|technologies|tools)[\s:\-]+", clean_l, re.IGNORECASE):
                    stack_val = re.sub(r"^(?:tech\s*stack|technologies|tools)[\s:\-]+", "", clean_l, flags=re.IGNORECASE).strip()
                    curr_proj["tech_stack"] = stack_val
                elif re.match(r"^(?:github|repo|code)[\s:\-]+", clean_l, re.IGNORECASE):
                    curr_proj["repo"] = re.sub(r"^(?:github|repo|code)[\s:\-]+", "", clean_l, flags=re.IGNORECASE).strip()
                elif re.match(r"^(?:live\s*demo|demo|live\s*url|link)[\s:\-]+", clean_l, re.IGNORECASE):
                    curr_proj["live_url"] = re.sub(r"^(?:live\s*demo|demo|live\s*url|link)[\s:\-]+", "", clean_l, flags=re.IGNORECASE).strip()
                else:
                    b_clean = clean_l.lstrip("•-*–—›▪1234567890.) ").strip()
                    if b_clean and len(b_clean) > 15:
                        curr_proj["bullets"].append(b_clean)
                        if not curr_proj["highlight"]:
                            curr_proj["highlight"] = b_clean

        if curr_proj:
            projects.append(curr_proj)

        return projects

    @classmethod
    def _parse_education_section(cls, text: str) -> List[Dict[str, Any]]:
        """Extracts all degrees, institutions, graduation dates, and relevance."""
        if not text:
            return []

        degree_keywords = [
            "master", "m.sc", "m.s.", "m.tech", "mca", "mba", "ph.d", "doctorate",
            "bachelor", "b.sc", "b.s.", "b.tech", "b.e.", "bca", "associate", "diploma", "degree"
        ]
        edu_entries: List[Dict[str, Any]] = []

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for idx, line in enumerate(lines):
            clean_l = re.sub(r"^#+\s*", "", line).strip()
            # Check if line contains a degree
            if any(re.search(rf"\b{re.escape(dk)}\b", clean_l, re.IGNORECASE) for dk in degree_keywords):
                degree_name = clean_l
                inst_name = "University"
                period_str = ""
                relevance_str = ""

                # Look for institution on the same line or next line
                if "|" in clean_l:
                    parts = [p.strip() for p in clean_l.split("|") if p.strip()]
                    degree_name = parts[0]
                    inst_name = parts[1] if len(parts) > 1 else "University"
                    period_str = parts[2] if len(parts) > 2 else ""
                elif idx + 1 < len(lines):
                    next_l = lines[idx + 1].strip()
                    if not any(re.search(rf"\b{re.escape(dk)}\b", next_l, re.IGNORECASE) for dk in degree_keywords):
                        if "|" in next_l:
                            p_parts = [p.strip() for p in next_l.split("|") if p.strip()]
                            inst_name = p_parts[0]
                            period_str = p_parts[1] if len(p_parts) > 1 else ""
                        else:
                            inst_name = next_l

                # Find year
                year_match = re.search(r"\b(20\d\d(?:\s*[-–—to]+\s*20\d\d)?)\b", line + " " + (lines[idx+1] if idx+1 < len(lines) else ""))
                if year_match and not period_str:
                    period_str = year_match.group(0)

                # Look for bullet/relevance on subsequent line
                if idx + 2 < len(lines) and lines[idx + 2].startswith(("•", "-", "*")):
                    relevance_str = lines[idx + 2].lstrip("•-*– ").strip()

                edu_entries.append({
                    "degree": degree_name,
                    "institution": inst_name,
                    "period": period_str,
                    "year": period_str,
                    "relevance": relevance_str or "Core academic coursework and computer science fundamentals."
                })

        return edu_entries

    @classmethod
    def _parse_certifications_section(cls, text: str) -> List[str]:
        """Extracts certifications and credentials list."""
        if not text:
            return []
        certs = []
        for line in text.split("\n"):
            clean_l = line.strip().lstrip("•-*–—›▪1234567890.) ").strip()
            if clean_l and len(clean_l) > 4 and not clean_l.lower().startswith(("certification", "license", "credential")):
                certs.append(clean_l)
        return certs

    @classmethod
    def _extract_via_gemini(cls, text: str, api_key: str) -> Dict[str, Any]:
        """Uses Gemini API to extract exhaustive structured profile JSON."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        prompt = f"""
You are an expert HR Parser and Resume-as-Code compiler.
Analyze this raw candidate document and extract ALL sections into JSON matching this exact structure:
{{
  "candidate": {{
    "name": "Candidate Full Name",
    "professional_title": "Current / Target Title",
    "sub_title": "Core specialization or tagline",
    "location": "City, Country",
    "contact": {{
      "email": "candidate@email.com",
      "phone": "+1 234 567 8900",
      "links": {{
        "linkedin": "https://linkedin.com/in/...",
        "github": "https://github.com/...",
        "portfolio": "https://..."
      }}
    }}
  }},
  "summaries": {{
    "primary": "Comprehensive executive/professional summary paragraph",
    "classic_profile": "Short 1-2 sentence profile summary"
  }},
  "skills": {{
    "core_competencies": {{
      "title": "Core Technical Competencies",
      "items": ["Skill 1", "Skill 2"]
    }}
  }},
  "skills_classic": {{
    "programming_backend": {{ "title": "Programming & Backend", "items": "Comma-separated list of all backend languages & frameworks" }},
    "ai_genai": {{ "title": "AI & GenAI", "items": "Comma-separated list of all AI/LLM tools" }},
    "databases": {{ "title": "Databases & Storage", "items": "Comma-separated list of all databases" }},
    "messaging_streaming": {{ "title": "Messaging & Streaming", "items": "Comma-separated list" }},
    "cloud_and_devops": {{ "title": "Cloud & DevOps", "items": "Comma-separated list of all cloud & DevOps tools" }},
    "infrastructure_observability": {{ "title": "Infrastructure & Observability", "items": "Comma-separated list" }}
  }},
  "experience": [
    {{
      "company": "Company Name",
      "role": "Role Title",
      "location": "City, Country or Remote",
      "period": {{ "display": "Period string e.g. January 2023 – Present" }},
      "summary": "Brief 1-sentence role summary",
      "bullets": [
        "Full authentic bullet point 1 with all metrics, tools, and technical expressions",
        "Full authentic bullet point 2"
      ]
    }}
  ],
  "projects": [
    {{
      "name": "Project Name",
      "tech_stack": "List or string of technologies",
      "repo": "https://github.com/...",
      "live_url": "https://...",
      "highlight": "Core project highlight",
      "bullets": [
        "Full project bullet point 1 describing architecture and features",
        "Full project bullet point 2"
      ]
    }}
  ],
  "education": [
    {{
      "degree": "Degree name e.g. Master of Science (M.Sc) in ...",
      "institution": "University or College Name",
      "location": "City, Country",
      "period": "Start – End Year e.g. 2022 – 2024",
      "year": "Graduation Year",
      "relevance": "Coursework, honors, GPA, or specialization"
    }}
  ],
  "certifications": [
    "Certification 1",
    "Certification 2"
  ]
}}

STRICT RULES:
1. Do NOT omit any sections. Extract ALL experience roles, ALL bullet points, ALL projects, ALL education degrees, and ALL skills.
2. Preserve exact technical keywords, percentages, and metrics.

Raw Document Text:
{text[:35000]}
"""
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json", "temperature": 0.1}
        }
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
        if r.status_code == 200:
            import json
            raw_json = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(raw_json)
        return {}

    @classmethod
    def _collect_skills_from_dict(cls, d: Dict[str, Any]) -> List[str]:
        """Collects and deduplicates all skills across all skill structures."""
        skills = set()
        classic = d.get("skills_classic", {})
        for cat, val in classic.items():
            if isinstance(val, dict):
                for item in val.get("items", "").split(","):
                    clean = item.strip().lower()
                    clean = re.sub(r'\(.*?\)', '', clean).strip()
                    if clean and len(clean) > 1:
                        skills.add(clean)

        skills_obj = d.get("skills", {})
        for cat, val in skills_obj.items():
            if isinstance(val, dict):
                items = val.get("items", [])
                if isinstance(items, list):
                    for item in items:
                        clean = str(item).strip().lower()
                        clean = re.sub(r'\(.*?\)', '', clean).strip()
                        if clean and len(clean) > 1:
                            skills.add(clean)
                elif isinstance(items, str):
                    for item in items.split(","):
                        clean = item.strip().lower()
                        clean = re.sub(r'\(.*?\)', '', clean).strip()
                        if clean and len(clean) > 1:
                            skills.add(clean)

        verified = d.get("verified_skills", [])
        if isinstance(verified, list):
            for v in verified:
                clean = str(v).strip().lower()
                if clean:
                    skills.add(clean)

        return sorted(list(skills))
