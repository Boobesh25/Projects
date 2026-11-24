"""
Profile Optimizer & Gemini Tailoring Engine
============================================
Provides:
1. Semantic skill equivalence & framing analysis (e.g. RAG <-> Retrieval-Augmented Generation).
2. Deep comparative analysis distinguishing framing gaps from true skill gaps.
3. Gemini 2.0 Flash powered document tailoring with interactive user feedback loop.
4. ATS-compliant PDF compilation with standardized naming: <role>_<company>_<portal>.pdf.
5. Google Drive Cloud backup integration.
"""

import io
import os
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple, Optional
import requests

from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# -----------------------------------------------------------------------------
# Comprehensive Semantic Skill & Industry Acronym Dictionary
# -----------------------------------------------------------------------------
SEMANTIC_SKILL_SYNONYMS: Dict[str, Set[str]] = {
    "rag": {
        "rag", "retrieval-augmented generation", "retrieval augmented generation",
        "retrieval-augmented-generation"
    },
    "retrieval-augmented generation": {
        "rag", "retrieval-augmented generation", "retrieval augmented generation",
        "retrieval-augmented-generation"
    },
    "retrieval augmented generation": {
        "rag", "retrieval-augmented generation", "retrieval augmented generation"
    },
    "kubernetes": {
        "kubernetes", "k8s", "k8s cluster", "container orchestration"
    },
    "k8s": {
        "kubernetes", "k8s", "k8s cluster", "container orchestration"
    },
    "container orchestration": {
        "kubernetes", "k8s", "container orchestration"
    },
    "docker": {
        "docker", "containerization", "containers", "docker compose", "dockerfile"
    },
    "containerization": {
        "docker", "containers", "containerization"
    },
    "containers": {
        "docker", "containers", "containerization"
    },
    "ci/cd": {
        "ci/cd", "continuous integration", "continuous deployment", "continuous delivery"
    },
    "continuous integration": {
        "ci/cd", "continuous integration", "continuous deployment"
    },
    "continuous deployment": {
        "ci/cd", "continuous integration", "continuous deployment"
    },
    "terraform": {
        "terraform", "iac", "infrastructure as code", "infrastructure-as-code", "terragrunt"
    },
    "iac": {
        "terraform", "iac", "infrastructure as code", "infrastructure-as-code"
    },
    "infrastructure as code": {
        "terraform", "iac", "infrastructure as code", "infrastructure-as-code"
    },
    "aws": {
        "aws", "amazon web services", "aws cloud"
    },
    "amazon web services": {
        "aws", "amazon web services", "aws cloud"
    },
    "azure": {
        "azure", "microsoft azure", "azure cloud"
    },
    "microsoft azure": {
        "azure", "microsoft azure", "azure cloud"
    },
    "gcp": {
        "gcp", "google cloud platform", "google cloud"
    },
    "google cloud": {
        "gcp", "google cloud platform", "google cloud"
    },
    "google cloud platform": {
        "gcp", "google cloud platform", "google cloud"
    },
    "llms": {
        "llms", "large language models", "llm", "foundation models"
    },
    "large language models": {
        "llms", "large language models", "llm", "foundation models"
    },
    "llm": {
        "llms", "large language models", "llm", "foundation models"
    },
    "genai": {
        "genai", "generative ai", "generative artificial intelligence", "gen ai"
    },
    "generative ai": {
        "genai", "generative ai", "generative artificial intelligence", "gen ai"
    },
    "generative artificial intelligence": {
        "genai", "generative ai", "generative artificial intelligence", "gen ai"
    },
    "rest apis": {
        "rest apis", "restful apis", "rest api", "web apis"
    },
    "rest api": {
        "rest apis", "restful apis", "rest api"
    },
    "microservices": {
        "microservices", "microservice architecture", "distributed systems"
    },
    "distributed systems": {
        "microservices", "microservice architecture", "distributed systems"
    },
    "opentelemetry": {
        "opentelemetry", "otel", "distributed tracing"
    },
    "otel": {
        "opentelemetry", "otel", "distributed tracing"
    },
    "observability": {
        "observability", "monitoring and observability"
    },
    "vector database": {
        "vector database", "vector store"
    },
    "vector store": {
        "vector database", "vector store"
    },
    "linux": {
        "linux", "unix", "bash shell"
    },
    "prompt engineering": {
        "prompt engineering", "prompt design", "context optimization"
    },
    "agentic ai": {
        "agentic ai", "agentic workflows", "autonomous agents"
    }
}


def sanitize_filename(role: str, company: str, portal: str) -> str:
    """Produces clean, filesystem-safe filename: <role>_<company>_<portal>.pdf"""
    clean_role = re.sub(r"[^a-zA-Z0-9]+", "_", (role or "Role").strip()).strip("_")
    clean_comp = re.sub(r"[^a-zA-Z0-9]+", "_", (company or "Company").strip()).strip("_")
    clean_portal = re.sub(r"[^a-zA-Z0-9]+", "_", (portal or "Direct").strip()).strip("_")
    return f"{clean_role}_{clean_comp}_{clean_portal}.pdf"


def detect_skill_equivalences(
    verified_skills: Set[str],
    target_skills: List[str]
) -> Tuple[List[str], List[Dict[str, str]], List[str]]:
    """
    Classifies target job skills against candidate's verified skills:
    1. matched_skills: Direct exact or substring matches.
    2. framing_opportunities: Candidate already has the skill under an acronym/synonym,
       needing only an update in document wording.
    3. missing_skills: True technical gaps requiring learning.
    """
    matched = []
    framing = []
    missing = []

    norm_cand_skills = {s.strip().lower() for s in verified_skills}

    for skill in target_skills:
        clean_s = skill.strip().lower()
        if not clean_s:
            continue

        # 1. Exact or safe substring match
        is_direct = False
        for vs in norm_cand_skills:
            if not vs:
                continue
            if clean_s == vs:
                is_direct = True
                break
            if len(clean_s) >= 3 and clean_s in vs:
                is_direct = True
                break
            if len(vs) >= 3 and vs in clean_s and (len(vs) >= 4 or " " in vs or vs in ["sql", "rag", "aws", "gcp", "k8s", "nlp", "llm"]):
                is_direct = True
                break

        if is_direct:
            matched.append(clean_s)
            continue

        # 2. Semantic synonym cluster match
        found_synonym = False
        target_cluster = SEMANTIC_SKILL_SYNONYMS.get(clean_s, set())

        for vs in norm_cand_skills:
            cand_cluster = SEMANTIC_SKILL_SYNONYMS.get(vs, set())
            # Check overlap between clusters or if one is inside the other's cluster
            if (clean_s in cand_cluster) or (vs in target_cluster) or bool(target_cluster & cand_cluster):
                framing.append({
                    "candidate_skill": vs,
                    "jd_skill": clean_s,
                    "note": f"You already have verified experience in '{vs}'. Reframe as '{clean_s}' in your document to pass ATS keyword scoring."
                })
                matched.append(clean_s)  # Count toward skill match!
                found_synonym = True
                break

        if not found_synonym:
            missing.append(clean_s)

    return matched, framing, missing


def generate_tailored_profile_with_gemini(
    candidate_profile: Dict[str, Any],
    job_data: Dict[str, Any],
    user_feedback: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Invokes Gemini 2.0 Flash to tailor candidate document content to the target JD.
    Falls back to deterministic synthesis if API key is not configured.
    """
    cand_meta = candidate_profile.get("candidate", {})
    name = cand_meta.get("name", "Candidate")
    cand_title = cand_meta.get("professional_title", "Software Engineer")
    exp_years = cand_meta.get("experience_years", 3.0)
    skills = candidate_profile.get("verified_skills", [])
    if not skills:
        skills = candidate_profile.get("skills", {}).get("core_competencies", {}).get("items", [])

    job_title = job_data.get("title", "Target Role")
    company = job_data.get("company_name") or job_data.get("company") or "Target Company"
    job_desc = job_data.get("raw_markdown") or job_data.get("title", "")
    target_skills = job_data.get("skills_required") or job_data.get("tech_stack") or []

    # Detect framing opportunities first
    matched, framing, missing = detect_skill_equivalences(set(skills), target_skills)

    if api_key and api_key.strip():
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key.strip()}"
            
            framing_context = "\n".join([
                f"- Candidate has '{f['candidate_skill']}' -> JD specifies '{f['jd_skill']}'. Explicitly expose '{f['jd_skill']}' in tailored bullets!"
                for f in framing
            ])

            user_instruction_block = f"\nUser Directive / Custom Feedback:\n{user_feedback.strip()}" if user_feedback else ""

            prompt = f"""
You are an expert Executive Resume Writer and ATS Optimization Specialist.
Target Position: {job_title} at {company}
Candidate Name: {name} (Current: {cand_title}, {exp_years} Years Experience)
Candidate Verified Skills: {', '.join(skills)}

Job Description Context:
{job_desc[:3000]}

Semantic Framing Opportunities:
{framing_context or "Align tech stack terminology directly to JD requirements."}
{user_instruction_block}

Task:
Generate tailored content to optimize the candidate's document specifically for {company}'s {job_title} requisition:
1. "tailored_title": A target title directly matching the position seniority and domain.
2. "tailored_summary": A punchy 2-3 sentence executive summary aligning verified background to this role.
3. "framing_explanation": 2 sentences explaining how existing skills (like RAG vs Retrieval-Augmented Generation, Docker vs Containerization) were exposed to match the JD.
4. "tailored_experience_bullets": 4 high-impact, quantified STAR-format bullet points demonstrating relevant achievements with technical metrics.
5. "recommended_skills_display": An ordered list of top skills prioritizing the JD's exact terminology.

Output JSON only matching this schema:
{{
  "tailored_title": "...",
  "tailored_summary": "...",
  "framing_explanation": "...",
  "tailored_experience_bullets": ["...", "...", "...", "..."],
  "recommended_skills_display": ["...", "..."]
}}
"""
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"response_mime_type": "application/json", "temperature": 0.15}
            }
            r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=25)
            if r.status_code == 200:
                raw_json = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(raw_json)
        except Exception:
            pass

    # Deterministic High-Quality Fallback Synthesis
    framing_explanations = []
    for f in framing:
        framing_explanations.append(f"Reframed verified '{f['candidate_skill']}' as '{f['jd_skill']}' to match {company}'s ATS keyword filter.")

    tailored_bullets = [
        f"Architected and deployed cloud-native applications on {', '.join(skills[:3])}, reducing deployment latency by 45% across multi-region environments.",
        f"Spearheaded enterprise infrastructure automation utilizing {', '.join(target_skills[:3] if target_skills else skills[:3])}, maintaining 99.9% uptime for core microservices.",
        f"Implemented automated CI/CD container orchestration pipelines with Docker and Kubernetes, accelerating release cadence from bi-weekly to daily.",
        f"Engineered resilient distributed systems with comprehensive OpenTelemetry tracing, reducing mean time to detection (MTTD) by 60%."
    ]

    # Incorporate user feedback if provided
    if user_feedback:
        tailored_bullets[0] = f"Directed engineering initiative focused on: {user_feedback.strip()} while optimizing cloud efficiency and SLA standards."

    return {
        "tailored_title": job_title,
        "tailored_summary": f"Accomplished {job_title} with {exp_years}+ years of specialized experience designing, implementing, and deploying mission-critical systems. Proven track record delivering resilient infrastructure, automated pipelines, and cloud solutions directly aligned with {company}'s technical standards.",
        "framing_explanation": " ".join(framing_explanations) if framing_explanations else f"Aligned technical skill catalog directly to {company}'s primary requisition stack.",
        "tailored_experience_bullets": tailored_bullets,
        "recommended_skills_display": list(dict.fromkeys(target_skills + skills))[:14]
    }


def compile_tailored_pdf(
    candidate_name: str,
    contact_info: Dict[str, str],
    role_title: str,
    company_name: str,
    portal: str,
    tailored_summary: str = "",
    tailored_skills: Optional[List[str]] = None,
    experience_bullets: Optional[List[str]] = None
) -> bytes:
    """
    Compiles an ATS-compliant PDF directly from the candidate's authentic base Markdown document.
    Preserves all authentic work experience, metrics, and education without synthetic artifacts.
    """
    user_email = contact_info.get("email", "") if contact_info else ""
    base_md = get_candidate_base_markdown(user_email, "")
    return compile_markdown_to_pdf(
        md_text=base_md,
        role_title=role_title,
        company_name=company_name,
        portal=portal
    )


def save_to_cloud_backup(
    pdf_bytes: bytes,
    role_title: str,
    company_name: str,
    portal: str
) -> Dict[str, Any]:
    """
    Saves tailored PDF locally in standardized 'google_drive_export/' directory
    and uploads directly to Google Drive folder ('JobRadar Career Documents').
    """
    export_dir = Path("google_drive_export")
    export_dir.mkdir(parents=True, exist_ok=True)

    filename = sanitize_filename(role_title, company_name, portal)
    file_path = export_dir / filename

    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    abs_path = str(file_path.resolve())

    # Direct Google Drive synchronization
    drive_res: Dict[str, Any] = {}
    try:
        from gdrive_service import upload_to_gdrive
        drive_res = upload_to_gdrive(abs_path)
    except Exception as e:
        drive_res = {"status": "error", "message": str(e)}

    is_cloud_success = drive_res.get("status") == "success"

    return {
        "filename": filename,
        "local_path": abs_path,
        "size_bytes": len(pdf_bytes),
        "drive_status": drive_res.get("status", "local_only"),
        "drive_file_id": drive_res.get("drive_file_id"),
        "drive_file_url": drive_res.get("drive_file_url"),
        "drive_folder_id": drive_res.get("drive_folder_id"),
        "drive_folder_name": drive_res.get("drive_folder_name", "JobRadar Career Documents"),
        "drive_folder_url": drive_res.get("drive_folder_url"),
        "status": "Successfully synced to Google Drive" if is_cloud_success else "Saved to Local Google Drive Export Directory",
        "message": drive_res.get("message", "")
    }


def profile_dict_to_markdown(data: Dict[str, Any]) -> str:
    """
    Converts candidate YAML profile data dictionary into structured Markdown.
    """
    c = data.get("candidate", {})
    name = c.get("name", "Candidate Name")
    title = c.get("professional_title", "Software Engineer")
    loc = c.get("location", "India")
    contact = c.get("contact", {})
    email = contact.get("email", "")
    phone = contact.get("phone", "")
    links = c.get("links", {})

    lines = []
    lines.append(f"# {name}")
    meta_parts = [p for p in [title, loc, phone, email] if p]
    lines.append(" | ".join(meta_parts))
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary
    summaries = data.get("summaries", {})
    summary = summaries.get("primary") or summaries.get("classic_profile") or summaries.get("classic_ai_engineer") or ""
    if summary:
        lines.append("## Professional Summary")
        lines.append(summary.strip())
        lines.append("")
        lines.append("---")
        lines.append("")

    # Skills
    skills = data.get("skills", {})
    if skills:
        lines.append("## Core Technical Skills")
        for cat_k, cat_v in skills.items():
            if isinstance(cat_v, dict):
                cat_title = cat_v.get("title", cat_k.replace("_", " ").title())
                items = cat_v.get("items", [])
                items_str = ", ".join(items) if isinstance(items, list) else str(items)
                lines.append(f"* **{cat_title}:** {items_str}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Experience
    exp_list = data.get("experience", [])
    if exp_list:
        lines.append("## Professional Experience")
        for exp in exp_list:
            r = exp.get("role", "Engineer")
            comp = exp.get("company", "Company")
            period = exp.get("period", {})
            period_str = period.get("display", "") if isinstance(period, dict) else str(period)
            lines.append(f"### **{r}** - **{comp}**")
            if period_str:
                lines.append(f"*{period_str}*")
            bullets = exp.get("bullets", [])
            if not bullets and exp.get("summary"):
                lines.append(f"* {exp.get('summary')}")
            for b in bullets:
                if isinstance(b, dict):
                    tb = b.get("title", "")
                    tx = b.get("text", "")
                    if tb:
                        lines.append(f"* **{tb}:** {tx}")
                    else:
                        lines.append(f"* {tx}")
                else:
                    lines.append(f"* {b}")
            lines.append("")
        lines.append("---")
        lines.append("")

    # Projects
    projects = data.get("projects", [])
    if projects:
        lines.append("## Personal Projects & POCs")
        for p in projects:
            p_name = p.get("name", "Project")
            p_stack = p.get("tech_stack", "")
            lines.append(f"### **{p_name}**")
            if p_stack:
                lines.append(f"*{p_stack}*")
            p_bullets = p.get("bullets", [])
            for b in p_bullets:
                lines.append(f"* {b}")
            lines.append("")
        lines.append("---")
        lines.append("")

    # Education
    edu = data.get("education", [])
    if edu:
        lines.append("## Education")
        for e in edu:
            deg = e.get("degree", "Degree")
            inst = e.get("institution", "University")
            yr = e.get("year", "")
            lines.append(f"* **{deg}** — {inst} ({yr})")
        lines.append("")

    return "\n".join(lines)


def get_candidate_base_markdown(user_email: str, profile_yaml: str) -> str:
    """
    Retrieves the authentic base Markdown document for a candidate.
    Uses PROFILE.md for superadmin if available, otherwise converts YAML.
    """
    clean_email = (user_email or "").strip().lower()
    if clean_email == "boobesh2509@gmail.com" and os.path.exists("PROFILE.md"):
        try:
            with open("PROFILE.md", "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():
                    return clean_markdown_links(content)
        except Exception:
            pass

    import yaml
    try:
        data = yaml.safe_load(profile_yaml) or {}
        return clean_markdown_links(profile_dict_to_markdown(data))
    except Exception:
        return clean_markdown_links(profile_yaml or "# Candidate Profile\n\nNo document available.")


def clean_markdown_links(text: str) -> str:
    """
    Converts markdown links like [https://linkedin.com/...](url) or [+91 ...](tel:...)
    into clean text representation for authentic ATS presentation.
    """
    def _link_cleaner(match):
        txt = match.group(1).strip()
        txt = re.sub(r"^https?://(www\.)?", "", txt)
        return txt
    return re.sub(r"\[([^\]]+)\]\([^\)]+\)", _link_cleaner, text)


def _intelligent_deterministic_edit(
    existing_md: str,
    prompt_directive: str,
    target_skills: List[str],
    company: str
) -> str:
    """
    Intelligently analyzes the user's prompt directive and places edits into the exact,
    appropriate section of the existing Markdown document without destructive changes or awkward phrasing.
    """
    updated_md = existing_md
    p_low = prompt_directive.strip().lower()

    # 1. Apply semantic skill synonyms if referenced in prompt
    for acr, syns in SEMANTIC_SKILL_SYNONYMS.items():
        if acr.lower() in p_low:
            for target_syn in syns:
                if target_syn != acr and any(target_syn.lower() in s.lower() for s in target_skills):
                    updated_md = re.sub(rf"\b{re.escape(acr)}\b", f"{acr} ({target_syn.title()})", updated_md, flags=re.IGNORECASE)

    # 2. Check if user is asking to add a skill / tool / technology
    # e.g. "add chroma db to my technicial skills", "add chromadb to skills", "include redis", "add docker"
    clean_p = prompt_directive.strip()
    is_add_cmd = bool(re.search(r"^(?:please\s+)?(?:add|include|insert|append|put)\s+", clean_p, re.IGNORECASE))
    clean_skill_target = ""
    if is_add_cmd:
        clean_skill_target = re.sub(r"^(?:please\s+)?(?:add|include|insert|append|put)\s+", "", clean_p, flags=re.IGNORECASE).strip()
        clean_skill_target = re.sub(r"\s+(?:to|in|into|under)\s+(?:my\s+)?(?:core\s+)?(?:tech\w*\s+)?(?:stack\w*|skills?|profile|resume|document)\s*$", "", clean_skill_target, flags=re.IGNORECASE).strip()
        clean_skill_target = re.sub(r"\s+(?:to|in|into|under)\s+(?:my\s+)?(?:skills?|stack|profile|resume|document)\s*$", "", clean_skill_target, flags=re.IGNORECASE).strip()

    if is_add_cmd and clean_skill_target:
        skill_canon_map = {
            "chroma db": "ChromaDB", "chromadb": "ChromaDB", "chroma": "ChromaDB",
            "qdrant": "Qdrant", "pinecone": "Pinecone", "pgvector": "pgvector",
            "weaviate": "Weaviate", "milvus": "Milvus", "faiss": "FAISS",
            "docker": "Docker", "kubernetes": "Kubernetes", "k8s": "Kubernetes",
            "terraform": "Terraform", "fastapi": "FastAPI", "flask": "Flask",
            "django": "Django", "redis": "Redis", "kafka": "Kafka", "rabbitmq": "RabbitMQ",
            "celery": "Celery", "langgraph": "LangGraph", "langchain": "LangChain",
            "llamaindex": "LlamaIndex", "crewai": "CrewAI", "autogen": "AutoGen",
            "gemini": "Google Gemini", "bedrock": "AWS Bedrock", "aws bedrock": "AWS Bedrock",
            "azure openai": "Azure OpenAI", "opentelemetry": "OpenTelemetry", "langsmith": "LangSmith",
            "mcp": "Model Context Protocol (MCP)", "rag": "Retrieval-Augmented Generation (RAG)",
            "graphql": "GraphQL", "postgresql": "PostgreSQL", "mysql": "MySQL", "mongodb": "MongoDB",
            "aws": "AWS", "azure": "Azure", "gcp": "GCP"
        }
        canon_skill = skill_canon_map.get(clean_skill_target.lower(), clean_skill_target.title())

        # Check if skill is already in the document
        if canon_skill.lower() not in updated_md.lower():
            vector_db_tokens = ["chroma", "qdrant", "pinecone", "pgvector", "weaviate", "milvus", "faiss", "vector"]
            genai_tokens = ["langchain", "langgraph", "llamaindex", "crewai", "autogen", "gemini", "openai", "bedrock", "agent", "prompt", "mcp", "llm"]
            backend_tokens = ["python", "fastapi", "flask", "django", "redis", "kafka", "celery", "rabbitmq", "postgres", "sql", "mysql", "mongo", "rest", "graphql"]
            infra_tokens = ["docker", "kubernetes", "k8s", "terraform", "aws", "azure", "gcp", "helm", "ci/cd", "git", "argocd", "opentelemetry", "tracing", "monitoring"]

            lines = updated_md.split("\n")
            skills_sec_idx = -1
            for idx, l in enumerate(lines):
                if "## Core Technical Skills" in l or "## Technical Skills" in l or "## Skills" in l:
                    skills_sec_idx = idx
                    break

            if skills_sec_idx != -1:
                inserted = False
                target_token_lower = clean_skill_target.lower()
                for idx in range(skills_sec_idx + 1, len(lines)):
                    l = lines[idx]
                    if l.startswith("## ") or l == "---":
                        break

                    # Case A: Vector Database skill
                    if any(vt in target_token_lower for vt in vector_db_tokens):
                        if "Vector Databases" in l or "Embeddings" in l:
                            if re.search(r"Vector Databases\s*\([^)]+\)", l, re.IGNORECASE):
                                lines[idx] = re.sub(r"(Vector Databases\s*\([^)]+)(\))", rf"\1, {canon_skill}\2", l, flags=re.IGNORECASE)
                            else:
                                lines[idx] = l.rstrip(".") + f", {canon_skill}."
                            inserted = True
                            break

                    # Case B: GenAI & Agentic skill
                    elif any(gt in target_token_lower for gt in genai_tokens):
                        if "Generative AI" in l or "Agentic" in l:
                            lines[idx] = l.rstrip(".") + f", {canon_skill}."
                            inserted = True
                            break

                    # Case C: Backend & Data skill
                    elif any(bt in target_token_lower for bt in backend_tokens):
                        if "Backend" in l or "Data Engineering" in l:
                            lines[idx] = l.rstrip(".") + f", {canon_skill}."
                            inserted = True
                            break

                    # Case D: Infra / Cloud / Observability skill
                    elif any(it in target_token_lower for it in infra_tokens):
                        if "LLMOps" in l or "Infrastructure" in l or "DevOps" in l:
                            lines[idx] = l.rstrip(".") + f", {canon_skill}."
                            inserted = True
                            break

                # Fallback if no specific subcategory matched
                if not inserted:
                    for idx in range(skills_sec_idx + 1, len(lines)):
                        if lines[idx].strip().startswith("* ") or lines[idx].strip().startswith("- "):
                            lines[idx] = lines[idx].rstrip(".") + f", {canon_skill}."
                            inserted = True
                            break

                updated_md = "\n".join(lines)

    # 3. Check if user explicitly asked to modify professional summary
    if "summary" in p_low and not is_add_cmd:
        summary_match = re.search(r"(?:add|include|highlight|emphasize)\s+(.+?)(?:\s+(?:to|in|into)\s+(?:my\s+)?summary)?$", prompt_directive.strip(), re.IGNORECASE)
        if summary_match and "## Professional Summary" in updated_md:
            feature = summary_match.group(1).strip().rstrip(".")
            lines = updated_md.split("\n")
            for idx, l in enumerate(lines):
                if "## Professional Summary" in l:
                    for s_idx in range(idx + 1, len(lines)):
                        if lines[s_idx].strip() and not lines[s_idx].startswith("#") and lines[s_idx] != "---":
                            lines[s_idx] = lines[s_idx].rstrip(".") + f" Demonstrated expertise in {feature} directly aligned with {company}'s architectural standards."
                            break
                    break
            updated_md = "\n".join(lines)

    return clean_markdown_links(updated_md)


def prompt_enhance_document_with_gemini(
    existing_md: str,
    prompt_directive: str,
    job_data: Dict[str, Any],
    api_key: Optional[str] = None
) -> str:
    """
    Enriches the candidate's EXISTING real Markdown document based on prompt directive and job data.
    Preserves authentic facts, real companies, projects, and factual metrics.
    """
    job_title = job_data.get("title", "Target Role")
    company = job_data.get("company_name") or job_data.get("company") or "Target Company"
    job_desc = job_data.get("raw_markdown") or job_data.get("title", "")
    target_skills = job_data.get("skills_required") or job_data.get("tech_stack") or []

    effective_api_key = (api_key or "").strip() or os.getenv("GEMINI_API_KEY", "").strip()

    if effective_api_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={effective_api_key}"
            system_instruction = f"""
You are an expert Executive Document Specialist and ATS Resume Optimization Engineer.
Target Position: {job_title} at {company}
Target Tech Stack: {', '.join(target_skills)}
Target JD Excerpt:
{job_desc[:1800]}

The candidate has provided their EXISTING, REAL resume/document in Markdown format below.

USER'S CUSTOM DIRECTIVE:
"{prompt_directive}"

CRITICAL RULES:
1. ANALYZE AND WISELY PLACE: Intelligently determine which section of the candidate's existing document this directive belongs to.
   - If the user asks to add or emphasize a technology, tool, or skill (e.g. "add chroma db to my technical skills", "include postgresql", "add docker"):
     Add the exact tool/skill name cleanly under "Core Technical Skills" in its appropriate category (e.g. ChromaDB belongs under Vector Databases or Databases).
   - If the user specifies a section (e.g. "add X to professional summary" or "in experience"), add it seamlessly to that section using professional, authentic language.
   - NEVER write meta-commentary, placeholders, or copy-pasted user prompt text like "Targeted Focus: Directly experienced in add chroma db to my technical skills".
2. PRESERVE EXISTING RESUME TRUTH:
   - Preserve ALL existing real companies, job titles, dates, metrics, projects, and education.
   - Do NOT rewrite or delete other sections unless specifically asked.
3. Output ONLY the updated complete raw Markdown document without markdown code fences (no ```markdown).
"""
            payload = {
                "contents": [
                    {"parts": [{"text": f"EXISTING CANDIDATE DOCUMENT:\n\n{existing_md}\n\nUSER PROMPT DIRECTIVE:\n{prompt_directive}\n\nPlease update the existing document accordingly."}]}
                ],
                "systemInstruction": {"parts": [{"text": system_instruction}]},
                "generationConfig": {"temperature": 0.2}
            }
            r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=35)
            if r.status_code == 200:
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                if text.startswith("```"):
                    lines = text.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    text = "\n".join(lines).strip()
                if text:
                    return text
        except Exception:
            pass

    # Deterministic Intelligent Parser (Fallback without API key)
    return _intelligent_deterministic_edit(existing_md, prompt_directive, target_skills, company)


def compile_markdown_to_pdf(
    md_text: str,
    role_title: str,
    company_name: str,
    portal: str
) -> bytes:
    """
    Compiles an ATS-compliant, multi-page ReportLab PDF directly from Markdown content.
    Includes candidate header, requisition watermark bar, section dividers, and styled bullets.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=32,
        bottomMargin=32
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        alignment=1,
        textColor=colors.HexColor("#0F172A")
    )
    contact_style = ParagraphStyle(
        "DocContact",
        fontName="Helvetica",
        fontSize=8.8,
        leading=12,
        alignment=1,
        textColor=colors.HexColor("#475569")
    )
    h1_style = ParagraphStyle(
        "DocH1",
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=8,
        spaceAfter=2
    )
    h2_style = ParagraphStyle(
        "DocH2",
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=5,
        spaceAfter=2
    )
    body_style = ParagraphStyle(
        "DocBody",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1E293B")
    )
    bullet_style = ParagraphStyle(
        "DocBullet",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155"),
        leftIndent=12
    )
    meta_tag_style = ParagraphStyle(
        "MetaTag",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#2563EB"),
        alignment=1
    )

    story = []

    lines = md_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if "Ground Truth Invariants" in line:
            break

        line = clean_markdown_links(line)

        if line.startswith("# "):
            t = line[2:].strip()
            story.append(Paragraph(t.upper(), title_style))
            story.append(Spacer(1, 2))
        elif line == "---" or line == "***":
            story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#CBD5E1"), spaceBefore=3, spaceAfter=3))
        elif line.startswith("## "):
            sec_title = line[3:].strip()
            story.append(Paragraph(sec_title.upper(), h1_style))
            story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#CBD5E1"), spaceBefore=1, spaceAfter=3))
        elif line.startswith("### "):
            h3_text = line[4:].strip()
            h3_html = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", h3_text)
            story.append(Paragraph(h3_html, h2_style))
        elif line.startswith("* ") or line.startswith("- "):
            b_text = line[2:].strip()
            b_html = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", b_text)
            b_html = re.sub(r"\*(.*?)\*", r"<i>\1</i>", b_html)
            story.append(Paragraph(f"▪ {b_html}", bullet_style))
            story.append(Spacer(1, 1.5))
        else:
            p_html = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", line)
            p_html = re.sub(r"\*(.*?)\*", r"<i>\1</i>", p_html)
            if i <= 3 and not line.startswith("#"):
                story.append(Paragraph(p_html, contact_style))
            else:
                story.append(Paragraph(p_html, body_style))
            story.append(Spacer(1, 2.5))
        i += 1

    doc.build(story)
    return buffer.getvalue()


def markdown_to_live_preview_html(
    md_text: str,
    role_title: str,
    company_name: str,
    portal: str
) -> str:
    """
    Renders the Markdown content into a clean, authentic high-density ATS paper sheet HTML preview.
    Starts cleanly with candidate header, without requisition banners.
    """
    html_lines = []
    html_lines.append('<div class="ats-preview-sheet">')

    lines = md_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if "Ground Truth Invariants" in line:
            break

        line = clean_markdown_links(line)

        if line.startswith("# "):
            name = line[2:].strip()
            html_lines.append(f'<div class="ats-name">{name}</div>')
        elif line == "---" or line == "***":
            html_lines.append('<hr class="ats-hr">')
        elif line.startswith("## "):
            sec = line[3:].strip()
            html_lines.append(f'<div class="ats-section-title">{sec}</div>')
        elif line.startswith("### "):
            h3 = line[4:].strip()
            h3_fmt = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", h3)
            html_lines.append(f'<div class="ats-job-header">{h3_fmt}</div>')
        elif line.startswith("* ") or line.startswith("- "):
            b = line[2:].strip()
            b_fmt = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", b)
            b_fmt = re.sub(r"\*(.*?)\*", r"<i>\1</i>", b_fmt)
            html_lines.append(f'<div class="ats-bullet"><span class="ats-bullet-dot">▪</span><div>{b_fmt}</div></div>')
        else:
            p_fmt = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", line)
            p_fmt = re.sub(r"\*(.*?)\*", r"<i>\1</i>", p_fmt)
            if i <= 3 and not line.startswith("#"):
                html_lines.append(f'<div class="ats-contact-line">{p_fmt}</div>')
            else:
                html_lines.append(f'<div class="ats-body-p">{p_fmt}</div>')
        i += 1

    html_lines.append("</div>")
    return "\n".join(html_lines)
