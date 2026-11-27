"""
Tests for AI Role Generator and Verified URL Generation Engine
"""

import pytest
from core.ai_role_generator import AIRoleGenerator

def test_validate_gemini_key_format():
    is_valid, msg = AIRoleGenerator.validate_gemini_key("")
    assert is_valid is False
    assert "empty" in msg.lower()

    is_valid, msg = AIRoleGenerator.validate_gemini_key("invalid_key_123")
    assert is_valid is False

def test_validate_groq_key_format():
    is_valid, msg = AIRoleGenerator.validate_groq_key("")
    assert is_valid is False
    assert "empty" in msg.lower()

    is_valid, msg = AIRoleGenerator.validate_groq_key("invalid_groq_key_123")
    assert is_valid is False

def test_validate_llm_key_unified():
    is_valid, msg = AIRoleGenerator.validate_llm_key("gemini", "")
    assert is_valid is False
    is_valid, msg = AIRoleGenerator.validate_llm_key("groq", "")
    assert is_valid is False

def test_deterministic_role_synthesis():
    dummy_profile = {
        "candidate": {
            "name": "Alex Candidate",
            "professional_title": "Cloud & DevOps Engineer",
            "experience_years": 4.0
        },
        "skills": {
            "primary": {"items": ["AWS", "Docker", "Kubernetes", "Terraform", "CI/CD", "Linux"]}
        },
        "summaries": {
            "primary": "Cloud & DevOps Engineer with 4 years automating infrastructure."
        }
    }
    result = AIRoleGenerator.generate_roles(dummy_profile, api_key=None)
    assert "primary_domain" in result
    assert "direct_roles" in result
    assert "cross_roles" in result
    assert len(result["direct_roles"]) >= 3
    assert len(result["cross_roles"]) >= 2
    assert "core_search_keywords" in result

def test_build_verified_job_links():
    links = AIRoleGenerator.build_verified_job_links("Google", "DevOps Engineer")
    assert "career_portal" in links
    assert "linkedin_jobs" in links
    assert "naukri_jobs" in links

    assert "linkedin.com/jobs/search" in links["linkedin_jobs"]
    assert "sortBy=DD" in links["linkedin_jobs"]
    assert "Google" in links["linkedin_jobs"]
    assert "DevOps" in links["linkedin_jobs"]

    assert "naukri.com" in links["naukri_jobs"]
    assert "careers.google.com" in links["career_portal"]
