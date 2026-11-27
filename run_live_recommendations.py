"""
Live Database Job Analysis and Recommendation Runner
===================================================
Fetches live jobs directly from PostgreSQL (company_jobs table), evaluates them
dynamically against the candidate profile in data/profile.yaml, and produces
prioritized high-conviction recommendations and an Excel workbook report.
"""

import sys
import os
from pathlib import Path
from typing import List, Tuple
from analyzer.discovery import JobDiscoveryEngine
from analyzer.matcher import JobMatcher
from analyzer.models import MatchResult
from analyzer.reporter import ExcelReportGenerator

def main():
    profile_path = Path("data/profile.yaml")
    if not profile_path.exists():
        print(f"Error: Candidate profile not found at {profile_path}")
        sys.exit(1)

    print("=" * 80)
    print("LIVE DATABASE JOB ANALYZER AND RECOMMENDATION ENGINE")
    print("=" * 80)

    # 1. Initialize Matcher with Candidate Profile
    matcher = JobMatcher(profile_input=profile_path)
    print(f"Candidate: {matcher.candidate_name} | Target: {matcher.candidate_title}")
    print(f"Verified Experience: {matcher.candidate_exp_years} Years")
    print(f"Verified Skills Count: {len(matcher.verified_skills)}")

    # 2. Fetch Live Active Jobs from PostgreSQL
    print("\nQuerying active jobs from PostgreSQL (company_jobs)...")
    postings = JobDiscoveryEngine.fetch_from_database(limit=250)
    print(f"Fetched {len(postings)} active jobs for evaluation.")

    if not postings:
        print("No active jobs found in PostgreSQL. Please run cloud_sync_worker.py first.")
        sys.exit(0)

    # 3. Evaluate Match for Each Job
    categorized_results: List[Tuple[str, MatchResult]] = []
    best_matches = []
    nearest_matches = []

    for job in postings:
        res = matcher.evaluate_job(job)
        if res.overall_match_score >= 75.0:
            category = "Best Match"
            best_matches.append(res)
        elif res.overall_match_score >= 60.0:
            category = "Nearest Match"
            nearest_matches.append(res)
        elif res.overall_match_score < 35.0:
            category = "Matched Role, JD Not Matched"
        else:
            category = "Evaluated"

        categorized_results.append((category, res))

    # Sort descending by match score
    best_matches.sort(key=lambda x: x.overall_match_score, reverse=True)
    nearest_matches.sort(key=lambda x: x.overall_match_score, reverse=True)
    categorized_results.sort(key=lambda x: x[1].overall_match_score, reverse=True)

    # 4. Generate Excel Report
    report_file = "Live_Job_Match_Analysis.xlsx"
    ExcelReportGenerator.generate_report(
        results=categorized_results,
        output_path=report_file,
        profile_path=str(profile_path)
    )
    print(f"\nGenerated Detailed Excel Report: {report_file}")

    # 5. Display Recommendations Summary
    print("\n" + "=" * 80)
    print(f"EVALUATION SUMMARY: {len(postings)} ROLES ANALYZED")
    print(f"  - High Priority Best Matches (>= 75%): {len(best_matches)}")
    print(f"  - Rapid Upskill Nearest Matches (60% - 74%): {len(nearest_matches)}")
    print("=" * 80)

    print("\n--- TOP HIGH-CONVICTION JOB RECOMMENDATIONS (BEST MATCHES >= 75%) ---")
    for idx, match in enumerate(best_matches[:10], 1):
        print(f"\n[{idx}] {match.job_title} @ {match.company}")
        print(f"    Location: {match.location} | Channel: {match.source_channel}")
        print(f"    Match Score: {match.overall_match_score:.1f}% (Skill: {match.skill_match_score:.1f}%, Semantic: {match.semantic_match_score:.1f}%)")
        print(f"    Experience Alignment: {'Matched' if match.experience_fit else 'Mismatch'} ({match.exp_required_text})")
        print(f"    Matched Skills: {', '.join(match.matched_skills[:6])}")
        if match.missing_skills:
            print(f"    Missing Skills: {', '.join(match.missing_skills[:4])}")
        print(f"    Application URL: {match.url}")
        print(f"    Recommendation: {match.recommendation}")

    if nearest_matches and len(best_matches) < 5:
        print("\n--- NEAREST MATCH OPPORTUNITIES (60% - 74%) ---")
        for idx, match in enumerate(nearest_matches[:5], 1):
            print(f"\n[{idx}] {match.job_title} @ {match.company}")
            print(f"    Location: {match.location} | Match Score: {match.overall_match_score:.1f}%")
            print(f"    Matched Skills: {', '.join(match.matched_skills[:5])}")
            print(f"    Missing Skills: {', '.join(match.missing_skills[:3])}")
            print(f"    URL: {match.url}")

    print("\n" + "=" * 80)
    print("Live recommendation run finished successfully.")
    print("=" * 80)

if __name__ == "__main__":
    main()
