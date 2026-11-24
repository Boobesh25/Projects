#!/usr/bin/env python3
"""
Career Page Analyser - Runner CLI
=================================
Usage:
  # 1. Analyze single local JSON (Infosys case study)
  python analyze.py infosys_genai_job.json

  # 2. Analyze a direct URL (ATS or Corporate Career Page)
  python analyze.py https://boards.greenhouse.io/canonical/jobs/5238202

  # 3. Discover jobs across ALL companies dynamically (No static company list needed)
  python analyze.py --discover "ai" --threshold 75

  # 4. Scan an entire company board
  python analyze.py --board canonical --threshold 75
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List
import requests

from analyzer import (
    JobMatcher,
    CareerPageExtractor,
    JobDiscoveryEngine,
    JobPosting,
    MatchResult,
    analyze_url,
    analyze_json_file
)

def scan_greenhouse_board(company_slug: str, min_threshold: float = 75.0):
    print(f"\n🔍 Querying public Greenhouse board for '{company_slug}'...")
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true"
    try:
        resp = requests.get(url, timeout=12)
        if resp.status_code != 200:
            print(f"❌ Failed to query board '{company_slug}' (HTTP {resp.status_code}).")
            return
        data = resp.json()
    except Exception as e:
        print(f"❌ Network error querying board: {e}")
        return

    jobs = data.get("jobs", [])
    print(f"Found {len(jobs)} active jobs at {company_slug.capitalize()}. Evaluating against profile.yaml...\n")

    matcher = JobMatcher()
    high_matches: List[MatchResult] = []
    moderate_matches: List[MatchResult] = []

    for j in jobs:
        title = j.get("title", "")
        lower_t = title.lower()
        if any(kw in lower_t for kw in ["software", "ai", "ml", "python", "backend", "engineer", "developer", "data"]):
            posting = CareerPageExtractor.extract_from_json_dict(j, url=j.get("absolute_url", ""))
            result = matcher.evaluate_job(posting)
            if result.overall_match_score >= min_threshold:
                high_matches.append(result)
            elif result.overall_match_score >= 60.0:
                moderate_matches.append(result)

    _display_batch_results(high_matches, moderate_matches, min_threshold, f"Company: {company_slug.capitalize()}")

def discover_open_jobs(keyword: str = "ai", limit: int = 30, min_threshold: float = 75.0, output_file: str = None):
    print(f"\n🌐 Initiating Dynamic Discovery across global companies for keyword: '{keyword}'...")
    print("   (Fetching live feeds from Arbeitnow, Remotive, Jobicy, RemoteOK - Zero company list needed)\n")

    postings = JobDiscoveryEngine.fetch_from_open_apis(tag=keyword, limit=limit)
    print(f"📥 Discovered {len(postings)} live job postings across diverse companies. Scoring against profile.yaml...\n")

    matcher = JobMatcher()
    high_matches: List[MatchResult] = []
    moderate_matches: List[MatchResult] = []

    matched_records = []
    for p in postings:
        result = matcher.evaluate_job(p)
        if result.overall_match_score >= min_threshold:
            high_matches.append(result)
            matched_records.append(result.model_dump())
        elif result.overall_match_score >= 60.0:
            moderate_matches.append(result)

    _display_batch_results(high_matches, moderate_matches, min_threshold, f"Keyword: '{keyword}'")

    if output_file and high_matches:
        out_path = Path(output_file)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(matched_records, f, indent=2)
        print(f"\n💾 Saved {len(high_matches)} high-match records to: {out_path.name}")

def _display_batch_results(high_matches: List[MatchResult], moderate_matches: List[MatchResult], min_threshold: float, context: str):
    print(f"🎯 Evaluation Complete [{context}]:")
    print(f"   🔥 High Matches (>= {min_threshold}%): {len(high_matches)}")
    print(f"   ⚡ Moderate Matches (60-74%): {len(moderate_matches)}\n")

    if high_matches:
        print("="*75)
        print(f"🔥 PRIORITY HIGH MATCHES (>= {min_threshold}%):")
        print("="*75)
        for m in sorted(high_matches, key=lambda x: x.overall_match_score, reverse=True):
            print(f"\n* [{m.overall_match_score}%] {m.job_title} @ {m.company}")
            print(f"  Location: {m.location} | Exp Req: {m.exp_required_text}")
            print(f"  URL: {m.url}")
            print(f"  Matched Skills: {', '.join(m.matched_skills[:8])}")
            if m.tailoring_tips:
                print(f"  Tailoring: {m.tailoring_tips[0]}")
    else:
        print(f"No roles reached the >= {min_threshold}% threshold. Top moderate matches:")
        for m in sorted(moderate_matches, key=lambda x: x.overall_match_score, reverse=True)[:5]:
            print(f" - [{m.overall_match_score}%] {m.job_title} @ {m.company} ({m.location})")
            print(f"   URL: {m.url}")

def main():
    parser = argparse.ArgumentParser(description="Career Page Analyser & Job Matcher")
    parser.add_argument("target", nargs="?", help="Job URL or path to local JD JSON file")
    parser.add_argument("--discover", help="Keyword to dynamically discover jobs across ALL companies (e.g. ai, python)")
    parser.add_argument("--limit", type=int, default=30, help="Max jobs to evaluate in discovery (default: 30)")
    parser.add_argument("--board", help="Greenhouse company slug (e.g. canonical, figma, scaleai)")
    parser.add_argument("--threshold", type=float, default=75.0, help="Minimum match score threshold (default: 75.0)")
    parser.add_argument("--save", help="Optional path to save >= 75% matched jobs as JSON")
    parser.add_argument("--excel", action="store_true", help="Generate comprehensive Excel report (Job_Match_Analysis.xlsx)")
    parser.add_argument("--ai", action="store_true", help="Enable AI Deep Reasoning (Elevator pitch, gap reasoning, interview questions)")
    parser.add_argument("--api-key", help="Google AI Studio Gemini API key (or set GEMINI_API_KEY env var)")
    args = parser.parse_args()

    if args.excel:
        from generate_job_analysis_excel import build_report
        build_report()
        return

    if args.discover:
        discover_open_jobs(keyword=args.discover, limit=args.limit, min_threshold=args.threshold, output_file=args.save)
        return

    if args.board:
        scan_greenhouse_board(args.board, min_threshold=args.threshold)
        return

    def run_ai_if_requested(match_result, raw_text=""):
        if not args.ai:
            return
        from analyzer import AIReasoner
        reasoner = AIReasoner(api_key=args.api_key)
        print("\n" + "="*60)
        print(f"🤖 AI REASONER STATUS: {reasoner.get_status_info()}")
        print("="*60)
        if not reasoner.is_available():
            print("💡 TIP: To enable AI features for free:")
            print("  1. Get a 100% Free Gemini API key from https://aistudio.google.com")
            print("     Set it in PowerShell: $env:GEMINI_API_KEY='your_key'")
            print("  2. OR start LM Studio locally on port 1234 (Zero key needed)")
            return

        print("⚡ Generating AI Deep Semantic Fit, Recruiter Pitch & Interview Prep...\n")
        with open("profile.yaml", "r", encoding="utf-8") as pf:
            import yaml
            prof = yaml.safe_load(pf)
        candidate_summary = prof.get("summaries", {}).get("primary", "")

        ai_res = reasoner.generate_deep_fit_analysis(
            job_title=match_result.job_title,
            company=match_result.company,
            jd_text=raw_text or match_result.tailoring_tips[0] if match_result.tailoring_tips else "",
            candidate_summary=candidate_summary,
            matched_skills=match_result.matched_skills,
            missing_skills=match_result.missing_skills
        )

        if "error" in ai_res:
            print(f"❌ AI Reasoning error: {ai_res['error']}")
            return

        print("🎯 AI SEMANTIC VERDICT:")
        print(f"  {ai_res.get('semantic_fit_verdict', 'N/A')}\n")

        print("💪 TRANSFERABLE STRENGTHS:")
        for s in ai_res.get("transferable_strengths", []):
            print(f"  * {s}")

        print("\n📢 TAILORED RECRUITER ELEVATOR PITCH:")
        print(f"  \"{ai_res.get('recruiter_elevator_pitch', 'N/A')}\"\n")

        print("❓ PREDICTED TECHNICAL INTERVIEW QUESTIONS:")
        for q in ai_res.get("top_interview_questions", []):
            print(f"  [Q] {q}")
        print("="*60 + "\n")

    if not args.target:
        # Default self-test with infosys_genai_job.json
        default_target = "infosys_genai_job.json"
        if Path(default_target).exists():
            print(f"No target specified. Running evaluation on default case study: {default_target}\n")
            res = analyze_json_file(default_target)
            print(res.format_terminal_summary())
            with open(default_target, "r", encoding="utf-8") as f:
                raw_t = json.load(f).get("raw_text", "")
            run_ai_if_requested(res, raw_t)
        else:
            parser.print_help()
        return

    target = args.target
    if target.startswith("http://") or target.startswith("https://"):
        print(f"\n🌐 Scraping and analyzing live URL: {target}...")
        res = analyze_url(target)
        if not res:
            print(f"❌ Failed to extract job from URL: {target}")
            return
        print(res.format_terminal_summary())
        run_ai_if_requested(res)
    elif Path(target).exists():
        print(f"\n📄 Analyzing local JSON: {target}...")
        res = analyze_json_file(target)
        print(res.format_terminal_summary())
        with open(target, "r", encoding="utf-8") as f:
            raw_t = json.load(f).get("raw_text", "")
        run_ai_if_requested(res, raw_t)
    else:
        print(f"❌ Target '{target}' is neither an active URL nor an existing file.")

if __name__ == "__main__":
    main()
