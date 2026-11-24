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
