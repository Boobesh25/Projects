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

def test_tech_role_classifier_rejects_placeholder_and_corrupt_roles():
    """Verify placeholder titles, retail, corrupt slugs, and non-tech titles are strictly rejected."""
    corrupt_or_non_tech = [
        "Opportunity at AT&T",
        "?Lang=En Us",
        "Opportunity at Walmart Global Tech",
        "Retail Sales Consultant",
        "Patient Care Technician",
        "Maintenance Scheduler",
        "Technical Opportunity at Schneider Electric",
        "Store Associate - North Region",
        "Photo 001 - Media Archive",
        "0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d"
    ]
    for role in corrupt_or_non_tech:
        is_tech, reason = TechRoleClassifier.is_technical_role(role)
        assert is_tech is False, f"Role '{role}' should be rejected, but was accepted: {reason}"

def test_job_sync_engine_segregates_jd_skills():
    """Verify JobSyncEngine partitions requirements into must_have and nice_to_have skills."""
    from core.job_sync_service import JobSyncEngine

    title = "Senior Backend Distributed Systems Engineer"
    description = """
    About the Role:
    We are looking for a Senior Backend Engineer to build robust cloud microservices.

    Requirements / Must Have:
    - 5+ years of experience with Python, FastAPI, and PostgreSQL.
    - Deep knowledge of Docker, Microservices, and Linux.

    Preferred Qualifications / Nice to Have:
    - Experience with Kubernetes, AWS, and Redis.
    - Familiarity with CI/CD, Kafka, and OpenTelemetry.
    """
    existing_skills = ["FastAPI", "Python", "Docker"]

    must_have, nice_to_have, all_skills = JobSyncEngine.segregate_skills_from_jd(
        title=title,
        description=description,
        existing_skills=existing_skills
    )

    assert "python" in must_have
    assert "fastapi" in must_have
    assert "postgresql" in must_have or "docker" in must_have
    assert "kubernetes" in nice_to_have or "aws" in nice_to_have or "redis" in nice_to_have
    assert len(all_skills) == len(set(all_skills))
    assert set(must_have).issubset(set(all_skills))
    assert set(nice_to_have).issubset(set(all_skills))

def test_job_sync_engine_filters_corrupt_jobs_during_upsert():
    """Verify _upsert_jobs rejects invalid titles, non-tech roles, and foreign on-site jobs."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    from core.job_sync_service import JobSyncEngine

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    test_jobs = [
        # Valid tech role
        {
            "job_id": "VALID-001",
            "company_name": "Google",
            "title": "Staff Software Engineer - Cloud Infrastructure",
            "location": "Bengaluru, India",
            "work_mode": "Hybrid",
            "url": "https://careers.google.com/jobs/results/12345",
            "raw_description": "Requirements: Python, Go, Kubernetes, Docker, Distributed Systems.",
            "posted_date": "2026-11-20"
        },
        # Corrupt placeholder title
        {
            "job_id": "INVALID-001",
            "company_name": "AT&T",
            "title": "Opportunity at AT&T",
            "location": "Bengaluru, India",
            "work_mode": "On-site",
            "url": "https://www.att.jobs/job/austin/retail-sales-consultant/117/102867945168",
            "raw_description": "Retail sales job description.",
        },
        # Query parameter corrupted title
        {
            "job_id": "INVALID-002",
            "company_name": "Schneider Electric",
            "title": "?Lang=En Us",
            "location": "Bengaluru, India",
            "work_mode": "Hybrid",
            "url": "https://careers.se.com/jobs/134243?lang=en-us",
            "raw_description": "Some job description",
        },
        # Non-tech retail title
        {
            "job_id": "INVALID-003",
            "company_name": "Retail Corp",
            "title": "Retail Sales Consultant",
            "location": "Mumbai, India",
            "work_mode": "On-site",
            "url": "https://careers.retailcorp.com/jobs/999",
            "raw_description": "Sales counter and customer support.",
        },
        # Foreign on-site role (Austin, TX)
        {
            "job_id": "INVALID-004",
            "company_name": "Tech Corp",
            "title": "Cloud Platform Systems Engineer",
            "location": "Austin, TX, United States",
            "work_mode": "On-site",
            "url": "https://careers.techcorp.com/jobs/austin-123",
            "raw_description": "Requirements: Python, Kubernetes.",
        }
    ]

    count = asyncio.run(JobSyncEngine._upsert_jobs(mock_session, test_jobs))
    assert count == 1, f"Expected 1 valid job to be upserted, got {count}"
    assert mock_session.add.call_count == 1
    added_obj = mock_session.add.call_args[0][0]
    assert added_obj.title == "Staff Software Engineer - Cloud Infrastructure"
    assert len(added_obj.must_have_skills) > 0
    assert len(added_obj.skills_required) > 0

def test_career_page_extractor_ats_routing():
    """Verify CareerPageExtractor routes Greenhouse, Lever, SmartRecruiters, and Ashby properly."""
    from analyzer.extractor import CareerPageExtractor
    from unittest.mock import patch, MagicMock

    # 1. SmartRecruiters mock
    mock_sr_resp = MagicMock()
    mock_sr_resp.status_code = 200
    mock_sr_resp.json.return_value = {
        "name": "Senior Python Backend Engineer",
        "location": {"city": "Bengaluru", "country": "India"},
        "releasedDate": "2026-11-20",
        "jobDescription": {
            "jobDescription": {"text": "<p>Build scalable FastAPI microservices with PostgreSQL and Docker.</p>"},
            "qualifications": {"text": "<p>At least 4 years of experience in Python.</p>"}
        }
    }
    with patch("requests.get", return_value=mock_sr_resp):
        sr_job = CareerPageExtractor.extract_from_url("https://jobs.smartrecruiters.com/TestCorp/12345678")
        assert sr_job is not None
        assert sr_job.title == "Senior Python Backend Engineer"
        assert sr_job.company == "Testcorp"
        assert "python" in sr_job.tech_stack

    # 2. Ashby mock
    mock_ashby_resp = MagicMock()
    mock_ashby_resp.status_code = 200
    mock_ashby_resp.json.return_value = {
        "jobs": [
            {
                "id": "ashby-999",
                "title": "Generative AI Systems Developer",
                "location": "Bengaluru, India",
                "jobUrl": "https://jobs.ashbyhq.com/AIStartup/ashby-999",
                "descriptionPlain": "Build Agentic AI and LangGraph workflows with pgvector and AWS. 3+ years experience.",
                "publishedAt": "2026-11-21"
            }
        ]
    }
    with patch("requests.get", return_value=mock_ashby_resp):
        ashby_job = CareerPageExtractor.extract_from_url("https://jobs.ashbyhq.com/AIStartup/ashby-999")
        assert ashby_job is not None
        assert ashby_job.title == "Generative AI Systems Developer"
        assert "python" in ashby_job.tech_stack or "agentic" in ashby_job.tech_stack

def test_cloud_sync_worker_crawl4ai_dispatch_logic():
    """Verify cloud_sync_worker checks ATS first, and invokes Crawl4AI for non-ATS portals."""
    from scripts.cloud_sync_worker import crawl_portal_and_sitemap
    from unittest.mock import patch

    # Case 1: ATS portal (Greenhouse) dispatches to crawl_ats
    greenhouse_portal = {
        "company_name": "Databricks",
        "career_url": "https://boards.greenhouse.io/databricks",
        "detected_ats": "Greenhouse"
    }
    with patch("scripts.cloud_sync_worker.crawl_ats", return_value=[{"job_id": "GH-1", "title": "Staff Engineer"}]) as mock_ats:
        res = crawl_portal_and_sitemap(greenhouse_portal)
        assert len(res) == 1
        assert mock_ats.called

    # Case 2: Non-ATS portal dispatches to Crawl4AI when available
    custom_portal = {
        "company_name": "CustomTech",
        "career_url": "https://careers.customtech.com",
        "detected_ats": "Custom / In-House"
    }
    with patch("scripts.cloud_sync_worker.crawl_ats", return_value=[]):
        with patch("scripts.cloud_sync_worker.CRAWL4AI_AVAILABLE", True):
            with patch("scripts.cloud_sync_worker.crawl_portal_with_crawl4ai_async", return_value=[{"job_id": "CRAWL-1", "title": "AI Developer"}]) as mock_crawl:
                res = crawl_portal_and_sitemap(custom_portal)
                assert len(res) == 1
                assert res[0]["title"] == "AI Developer"


