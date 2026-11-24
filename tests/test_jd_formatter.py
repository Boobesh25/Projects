import pytest
from core.jd_formatter import JobDescriptionFormatter


def test_clean_raw_html():
    raw_html = "&lt;p&gt;We are looking for an &amp;lt;strong&amp;gt;AI Engineer&amp;lt;/strong&amp;gt;.&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;li&gt;FastAPI&lt;/li&gt;&lt;/ul&gt;"
    cleaned = JobDescriptionFormatter.clean_raw_html(raw_html)
    assert "<p>" not in cleaned
    assert "&lt;" not in cleaned
    assert "- Python" in cleaned
    assert "- FastAPI" in cleaned


def test_get_full_job_description_short_snippet():
    job = {
        "company_name": "LTIMindtree",
        "title": "AI Systems Engineer (Python, RAG, LangChain)",
        "location": "Bangalore / Pune, India",
        "work_mode": "Hybrid",
        "experience_text": "2 - 5 Years",
        "source_channel": "Naukri",
        "job_id": "NAUKRI-191124008129",
        "skills_required": ["python", "rag", "qdrant", "chromadb", "aws bedrock"],
        "raw_description": "Develop enterprise RAG systems using vector databases (Qdrant, ChromaDB), LangChain orchestration, and Python FastAPI microservices."
    }
    full_jd = JobDescriptionFormatter.get_full_job_description(job)
    assert len(full_jd) > 2000
    assert "About LTIMindtree:" in full_jd
    assert "Role Overview & Business Impact:" in full_jd
    assert "Key Responsibilities:" in full_jd
    assert "Required Technical Qualifications:" in full_jd
    assert "Preferred Qualifications:" in full_jd
    assert "Requisition Information & Work Environment:" in full_jd
    assert "#NAUKRI-191124008129" in full_jd


def test_get_full_job_description_data_engineer():
    job = {
        "company_name": "ANGEHEUERT GmbH",
        "title": "Senior Data Engineer (m/w/d)",
        "location": "Berlin, Germany",
        "work_mode": "Remote",
        "experience_text": "4 - 7 Years",
        "source_channel": "Career Page",
        "job_id": "REQ-162857",
        "skills_required": ["python", "spark", "kafka", "snowflake", "sql"],
        "raw_description": "Du mochtest nicht nur Daten verarbeiten, sondern eine moderne Datenplattform entwickeln."
    }
    full_jd = JobDescriptionFormatter.get_full_job_description(job)
    assert len(full_jd) > 2000
    assert "About ANGEHEUERT GmbH:" in full_jd
    assert "Data Engineering & Analytics Infrastructure" in full_jd
    assert "Apache Spark" in full_jd or "Spark" in full_jd


def test_get_full_job_description_authentic_ats():
    long_desc = "Authentic full job description from Greenhouse ATS.\n\n" + ("Detailed requirements and responsibilities for software development. " * 30)
    job = {
        "company_name": "GitLab",
        "title": "Engineering Manager",
        "raw_description": long_desc
    }
    result = JobDescriptionFormatter.get_full_job_description(job)
    # Authentic long description should be preserved
    assert "Authentic full job description" in result
    assert len(result) >= 300
