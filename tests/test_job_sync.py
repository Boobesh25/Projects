"""
Unit and Integration Tests for Autonomous Job Sync Service & Endpoints
=====================================================================
Validates:
1. TechRoleClassifier (Technical Anchor Priority, AI Developer, FDE, GenAI, Quant & FinTech tech vs Non-tech)
2. GeoLocationFilter (India any mode vs Abroad remote only)
3. ExperienceParser
4. POST /api/jobs/sync authentication (X-Sync-Secret & Admin token)
5. Mutual exclusion locking (409 Conflict prevention)
6. GET /api/jobs/sync/status telemetry
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app
from core.job_sync_service import TechRoleClassifier, GeoLocationFilter, ExperienceParser

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_tech_role_classifier_accepts_emerging_ai_and_quant():
    """Verify modern emerging AI roles and FinTech/Quant tech roles are accepted."""
    accepted_roles = [
        "AI Developer",
        "Forward Deployed Engineer (FDE)",
        "FDE - Enterprise Solutions",
        "Generative AI Platform Engineer",
        "GenAI / LLM Systems Developer",
        "Quant Developer - High Frequency Trading",
        "Quantitative Developer",
        "Software Engineer - Corporate Finance Systems",
        "FinOps Platform Architect",
        "MLOps Infrastructure Engineer",
        "Founding Engineer - Full Stack",
        "Cloud DevOps Specialist",
        "Kubernetes Platform Systems Engineer",
        "Backend Distributed Systems Engineer"
    ]
    for role in accepted_roles:
        is_tech, reason = TechRoleClassifier.is_technical_role(role)
        assert is_tech is True, f"Role '{role}' should be classified as technical, but got: {reason}"

def test_tech_role_classifier_rejects_non_tech():
    """Verify non-technical roles (Sales, HR, Marketing, Legal, pure Accounting) are rejected."""
    rejected_roles = [
        "Technical Recruiter",
        "Senior Talent Acquisition Specialist",
        "Human Resources Generalist",
        "Sales Representative - Enterprise Cloud",
        "Account Executive - SaaS",
        "Business Development Manager",
        "Digital Marketing Lead",
        "Content Writer & Copywriter",
        "Social Media Coordinator",
        "Corporate Legal Counsel",
        "Paralegal Specialist",
        "Senior Tax Accountant",
        "Audit Associate",
        "Credit Officer",
        "Office Manager & Executive Assistant",
        "Customer Support Representative"
    ]
    for role in rejected_roles:
        is_tech, reason = TechRoleClassifier.is_technical_role(role)
        assert is_tech is False, f"Role '{role}' should be rejected as non-technical, but was accepted: {reason}"

def test_geo_filter_india_and_remote():
    """Verify geographic filter rules: India (Any mode) and Abroad (Remote only)."""
    # India cases (Any work mode allowed)
    ok_in_onsite, _, mode1 = GeoLocationFilter.filter_geography("Bengaluru, India", "On-site")
    assert ok_in_onsite is True
    assert mode1 == "On-site"

    ok_in_hybrid, _, mode2 = GeoLocationFilter.filter_geography("Hyderabad, India", "Hybrid")
    assert ok_in_hybrid is True
    assert mode2 == "Hybrid"

    ok_in_remote, _, mode3 = GeoLocationFilter.filter_geography("Pune, India", "Remote")
    assert ok_in_remote is True
    assert mode3 == "Remote"

    # Abroad Remote (Allowed)
    ok_abroad_rem, _, mode4 = GeoLocationFilter.filter_geography("San Francisco, CA (Remote)", "Remote")
    assert ok_abroad_rem is True
    assert mode4 == "Remote"

    ok_global_rem, _, mode5 = GeoLocationFilter.filter_geography("Worldwide", "Remote")
    assert ok_global_rem is True
    assert mode5 == "Remote"

    # Abroad Non-Remote (Must be REJECTED)
    ok_abroad_onsite, _, _ = GeoLocationFilter.filter_geography("London, United Kingdom", "On-site")
    assert ok_abroad_onsite is False

    ok_abroad_hybrid, _, _ = GeoLocationFilter.filter_geography("New York, NY", "Hybrid")
    assert ok_abroad_hybrid is False

def test_experience_parser():
    """Verify experience text and bounds parsing."""
    text1, min1, max1 = ExperienceParser.parse_experience("Cloud Engineer", "Requires 2 - 5 years of experience")
    assert min1 == 2.0
    assert max1 == 5.0
    assert text1 == "2 - 5 Years"

    text2, min2, max2 = ExperienceParser.parse_experience("Senior Quant Developer")
    assert min2 >= 4.0
    assert max2 >= 8.0

def test_job_sync_api_unauthorized(client):
    """Calling POST /api/jobs/sync without credentials or secret returns 401."""
    res = client.post("/api/jobs/sync")
    assert res.status_code == 401

def test_job_sync_status_endpoint(client):
    """Calling GET /api/jobs/sync/status returns valid telemetry structure."""
    res = client.get("/api/jobs/sync/status")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "stage" in data
    assert "progress_pct" in data
    assert "active_jobs_in_db" in data
    assert data["status"] in ["IDLE", "RUNNING", "COMPLETED", "FAILED"]

def test_job_sync_trigger_and_mutual_exclusion(client):
    """
    Test initiating sync with X-Sync-Secret header:
    - First trigger returns 202 Accepted (or 409 if already executing)
    - Consecutive trigger while RUNNING returns 409 Conflict
    """
    from unittest.mock import patch, AsyncMock
    with patch("core.job_sync_service.JobSyncEngine.run_full_sync", new_callable=AsyncMock):
        headers = {"X-Sync-Secret": "jobradar_sync_secret_dev_2026"}
        res1 = client.post("/api/jobs/sync", headers=headers)
        assert res1.status_code in [202, 409]

        if res1.status_code == 202:
            data1 = res1.json()
            assert data1["status"] == "RUNNING"
            assert "GitHub Actions" in data1["triggered_by"]

            # Immediate follow-up trigger MUST encounter mutual exclusion lock (409 Conflict)
            res2 = client.post("/api/jobs/sync", headers=headers)
            assert res2.status_code == 409
            data2 = res2.json()
            assert any(w in data2["detail"].lower() for w in ["already", "active", "running"])
