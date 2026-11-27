import pytest
from core.jd_formatter import JobDescriptionFormatter


def test_clean_raw_html():
    raw_html = "&lt;p&gt;We are looking for an &amp;lt;strong&amp;gt;AI Engineer&amp;lt;/strong&amp;gt;.&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;li&gt;FastAPI&lt;/li&gt;&lt;/ul&gt;"
    cleaned = JobDescriptionFormatter.clean_raw_html(raw_html)
    assert "<p>" not in cleaned
    assert "&lt;" not in cleaned
    assert "- Python" in cleaned
    assert "- FastAPI" in cleaned


def test_get_full_job_description_authentic_snippet_preserved():
    job = {
        "company_name": "LTIMindtree",
        "title": "AI Systems Engineer (Python, RAG, LangChain)",
        "source_channel": "Naukri",
        "raw_description": "Develop enterprise RAG systems using vector databases (Qdrant, ChromaDB), LangChain orchestration, and Python FastAPI microservices."
    }
    result = JobDescriptionFormatter.get_full_job_description(job)
    # Authentic text must be preserved verbatim, without synthetic fabrication
    assert "Develop enterprise RAG systems using vector databases" in result
    assert "Feed Notice" in result


def test_get_full_job_description_authentic_ats():
    long_desc = "Authentic full job description from Greenhouse ATS.\n\n" + ("Detailed requirements and responsibilities for software development. " * 30)
    job = {
        "company_name": "GitLab",
        "title": "Engineering Manager",
        "raw_description": long_desc
    }
    result = JobDescriptionFormatter.get_full_job_description(job)
    # Authentic long description should be preserved verbatim
    assert "Authentic full job description" in result
    assert len(result) >= 300
    assert "Feed Notice" not in result
