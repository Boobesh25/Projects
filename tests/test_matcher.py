"""
Test Requisition Matcher & Dual-Gate Evaluation
"""
from analyzer.matcher import JobMatcher
from analyzer.models import JobPosting

def test_matcher_evaluation():
    mock_profile = {
        "candidate": {
            "name": "Boobesh S",
            "professional_title": "GenAI Engineer",
            "experience_years": 3.0
        },
        "skills_classic": {
            "ai": {"items": "python, fastapi, rag, langchain, postgresql"}
        }
    }
    matcher = JobMatcher(profile_input=mock_profile)
    assert matcher.candidate_exp_years == 3.0
    assert "python" in matcher.verified_skills
    assert "fastapi" in matcher.verified_skills

    job = JobPosting(
        url="https://example.com/job/1",
        company="Infosys Limited",
        title="AI Engineer",
        job_id="INF-101",
        must_have_skills=["python", "fastapi"],
        tech_stack=["rag", "langchain"],
        min_experience_years=2.0,
        max_experience_years=5.0
    )
    result = matcher.evaluate_job(job)
    assert result.overall_match_score >= 60.0
    assert "rag" in result.matched_skills
    assert result.experience_fit is True
    assert result.knockout_passed is True
    assert result.ats_verdict in ["SHORTLISTED", "REVIEWABLE"]

def test_ats_knockout_gate_disqualification():
    mock_profile = {
        "candidate": {
            "name": "Boobesh S",
            "professional_title": "GenAI Engineer",
            "experience_years": 3.0
        },
        "skills_classic": {
            "ai": {"items": "python, fastapi, docker"}
        }
    }
    matcher = JobMatcher(profile_input=mock_profile)

    # Job requiring 8+ years experience (Shortfall > 1.5 yrs threshold)
    job = JobPosting(
        url="https://example.com/job/senior-lead",
        company="Global Enterprise",
        title="Principal AI Architect",
        job_id="ARCH-900",
        must_have_skills=["python", "fastapi"],
        tech_stack=["docker"],
        min_experience_years=8.0,
        max_experience_years=12.0
    )
    result = matcher.evaluate_job(job)
    assert result.knockout_passed is False
    assert result.ats_verdict == "KNOCKED OUT"
    assert result.overall_match_score < 50.0
    assert any("Experience Shortfall" in reason for reason in result.knockout_reasons)

def test_ats_must_have_skill_gap_and_action_plan():
    mock_profile = {
        "candidate": {
            "name": "Boobesh S",
            "professional_title": "GenAI Engineer",
            "experience_years": 3.0
        },
        "skills_classic": {
            "ai": {"items": "python, fastapi"}
        }
    }
    matcher = JobMatcher(profile_input=mock_profile)

    # Requisition requiring skills candidate does not possess
    job = JobPosting(
        url="https://example.com/job/blockchain",
        company="Fintech Corp",
        title="Blockchain Developer",
        job_id="FIN-202",
        must_have_skills=["solidity", "rust", "smart contracts"],
        tech_stack=["ethereum"],
        min_experience_years=2.0,
        max_experience_years=4.0
    )
    result = matcher.evaluate_job(job)
    assert "solidity" in result.must_have_missing
    assert "rust" in result.must_have_missing
    assert result.ats_verdict in ["KNOCKED OUT", "POTENTIAL GAP"]
    assert any("Core Must-Have Gap" in tip for tip in result.ats_action_plan)

def test_ats_context_and_star_quantification():
    mock_profile = {
        "candidate": {
            "name": "Boobesh S",
            "professional_title": "Senior AI Systems Engineer",
            "experience_years": 4.0
        },
        "skills_classic": {
            "ai": {"items": "python, fastapi, rag, postgresql, redis, kubernetes"}
        },
        "experience": {
            "positions": [
                {
                    "title": "Senior AI Engineer",
                    "company": "TechNova",
                    "bullets": [
                        "Architected an enterprise RAG pipeline using FastAPI and Python, reducing latency by 42%.",
                        "Engineered high-throughput Redis caching layer serving 15,000 requests per minute with 99.9% uptime."
                    ]
                }
            ]
        }
    }
    matcher = JobMatcher(profile_input=mock_profile)
    # Verification of STAR metric density scoring
    assert matcher.base_quantification_score >= 70.0
    # Skills proven in actual employment bullets
    assert "python" in matcher.experience_skills
    assert "fastapi" in matcher.experience_skills
    assert "redis" in matcher.experience_skills

    job = JobPosting(
        url="https://example.com/job/ai-sr",
        company="AI Labs",
        title="Senior AI Systems Engineer",
        job_id="AIL-404",
        must_have_skills=["python", "fastapi"],
        tech_stack=["redis", "rag"],
        min_experience_years=3.0,
        max_experience_years=6.0
    )
    result = matcher.evaluate_job(job)
    assert result.knockout_passed is True
    assert result.ats_verdict == "SHORTLISTED"
    assert result.ats_score >= 80.0
    assert result.context_score > 60.0
    assert result.quantification_score >= 70.0

