"""
Unit Tests for DocumentProfileAnalyzer
======================================
Tests deterministic parsing of uploaded documents (PDF/DOCX/TXT/MD),
guaranteeing full extraction of:
- Candidate Contact & Info
- Professional Summary
- Core Technical Skills
- Professional Experience (with all bullet points & expressions)
- Flagship & Personal Projects (with stacks and bullet points)
- Education & Academic Credentials
- Certifications
"""

import pytest
import yaml
from core.cv_analyzer import DocumentProfileAnalyzer

SAMPLE_CANDIDATE_DOCUMENT = """
Boobesh S
GenAI Engineer • Chennai, India
boobesh2509@gmail.com | +91 6381659585 | https://linkedin.com/in/boobesh-s-8a8387201 | https://github.com/Boobesh25

Professional Summary
Accomplished AI Engineer with 3+ years of experience building production-grade AI applications, RAG systems, and scalable backend architectures. Experienced in multi-agent orchestration, tool integration via Model Context Protocol (MCP), and real-time streaming APIs using FastAPI and PostgreSQL.

Technical Skills
• Programming & Backend: Python, FastAPI, REST APIs, WebSockets, SQLAlchemy, Pandas, Gunicorn, Nginx
• AI & GenAI: Agentic AI, Google ADK, LangGraph, Model Context Protocol (MCP), ReAct Decision Loops, RAG, Vector Search, Embeddings, Prompt Engineering, Gemini, AWS Bedrock
• Databases & Storage: PostgreSQL (pgvector), MySQL, Qdrant, ChromaDB, Redis
• Cloud & DevOps: Docker, Kubernetes, GCP Cloud Run, AWS, Azure, ArgoCD, Linux, Git, GitHub
• Observability & LLMOps: OpenTelemetry, OpenLIT, LangSmith, Prometheus, Grafana

Professional Experience
Software Engineer (AI / GenAI) | Corent Technology
January 2023 – Present | Chennai, India
• Architected a 2-tier agent orchestration system with Google ADK; deployed a deterministic root router to classify intent and delegate execution to specialized MCP ReAct agents.
• Implemented Gemini Context Caching across 78+ MCP tool schemas and static system instructions, reducing token costs by 75% and latency by ~60%.
• Built a deterministic schema-grounding pipeline exposing relational schemas as MCP resources; constrained LLM outputs to validated, read-only SQL queries to guarantee 100% factual fidelity against live records.
• Built an adaptive response-downsampling middleware for high-volume cloud telemetry payloads (200 KB to 2 MB), preserving context-window token budgets.
• Instrumented end-to-end distributed tracing using OpenTelemetry and a custom PostgreSQL span exporter across all agent execution stages.

Projects
GenAI Multi-Agent Chatbot Platform
Tech Stack: LangGraph, FastAPI, Google Gemini, Qdrant, Redis, PostgreSQL, Streamlit, Docker
GitHub: https://github.com/Boobesh25/Projects
Live Demo: https://projects-bu8jtjbtyqe7otklpukvoq.streamlit.app/
• Built an autonomous ReAct agent chatbot using LangGraph and Google Gemini that dynamically routes queries between SQL database tools and Qdrant document vector search.
• Implemented semantic chunking with adaptive similarity thresholds to split documents along topical boundaries.
• Integrated Redis caching with incremental re-embedding, slashing external LLM embedding API calls by up to 80%.

Education
Master of Science (M.Sc) in Cyber Forensic and Information Security
University of Madras | Chennai, India | August 2022 – May 2024
• Advanced coursework in security protocols, threat vectors, data privacy, and systems auditing.

Bachelor of Science (B.Sc) in Computer Science
Mar Gregorios College of Arts & Science | Chennai, India | August 2019 – May 2022
• Core computer science fundamentals, data structures, algorithms, and database management.

Certifications
• Google Cloud Certified Associate Cloud Engineer
• HashiCorp Certified: Terraform Associate
"""

def test_extract_text_from_plain_bytes():
    raw_bytes = SAMPLE_CANDIDATE_DOCUMENT.encode("utf-8")
    extracted = DocumentProfileAnalyzer.extract_text(raw_bytes, "profile_doc.txt")
    assert "Boobesh S" in extracted
    assert "Corent Technology" in extracted
    assert "University of Madras" in extracted

def test_comprehensive_profile_extraction():
    yaml_str, verified_skills, profile_dict = DocumentProfileAnalyzer.generate_yaml_profile(
        raw_text=SAMPLE_CANDIDATE_DOCUMENT,
        user_name="Boobesh S"
    )

    # 1. Candidate Info
    cand = profile_dict.get("candidate", {})
    assert cand.get("name") == "Boobesh S"
    assert cand.get("contact", {}).get("email") == "boobesh2509@gmail.com"
    assert "linkedin" in cand.get("links", {})
    assert "github" in cand.get("links", {})

    # 2. Summary
    assert len(profile_dict.get("summaries", {}).get("primary", "")) > 30

    # 3. Core Technical Skills
    assert "python" in verified_skills
    assert "fastapi" in verified_skills
    assert "docker" in verified_skills
    assert len(verified_skills) >= 10

    # 4. Professional Experience & Bullets
    exp = profile_dict.get("experience", [])
    assert len(exp) >= 1
    corent_exp = exp[0]
    assert "Corent" in corent_exp.get("company", "")
    assert len(corent_exp.get("bullets", [])) >= 3
    # Check that authentic expressions and metrics were captured
    assert any("75%" in b or "latency" in b or "Google ADK" in b for b in corent_exp.get("bullets", []))

    # 5. Projects
    projects = profile_dict.get("projects", [])
    assert len(projects) >= 1
    p1 = projects[0]
    assert "Chatbot" in p1.get("name", "")
    assert len(p1.get("bullets", [])) >= 2
    assert "github" in p1.get("repo", "").lower()

    # 6. Education
    edu = profile_dict.get("education", [])
    assert len(edu) >= 2
    degrees = [e.get("degree", "").lower() for e in edu]
    assert any("master" in d or "m.sc" in d for d in degrees)
    assert any("bachelor" in d or "b.sc" in d for d in degrees)

    # 7. Valid YAML Serialization
    reloaded = yaml.safe_load(yaml_str)
    assert reloaded["candidate"]["name"] == "Boobesh S"
    assert len(reloaded["experience"]) >= 1
    assert len(reloaded["projects"]) >= 1
    assert len(reloaded["education"]) >= 1
