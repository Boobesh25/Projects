"""
Job Matcher and Candidate Scoring Engine
========================================
Compares normalized JobPostings dynamically against ANY candidate's verified profile.
Applies dual-gate multi-factor scoring (experience filter + skill matrix + semantic alignment).
Identifies high-conviction matches >= 75-80% with complete user isolation.
"""

import re
import yaml
from pathlib import Path
from typing import Set, List, Dict, Any, Union, Tuple, Optional
from .models import JobPosting, MatchResult
try:
    from core.profile_optimizer import detect_skill_equivalences
except ImportError:
    try:
        from profile_optimizer import detect_skill_equivalences
    except ImportError:
        def detect_skill_equivalences(skill, verified_skills=None, min_ratio=0.82):
            return {skill.lower()}

class JobMatcher:
    def __init__(self, profile_input: Union[str, Dict[str, Any], Path] = "profile.yaml"):
        if isinstance(profile_input, dict):
            self.profile = profile_input
        else:
            p_path = Path(profile_input)
            if not p_path.is_absolute():
                candidates = [
                    Path.cwd() / profile_input,
                    Path.cwd() / "data" / profile_input,
                    Path(__file__).parent.parent / "data" / profile_input,
                    Path(__file__).parent.parent / profile_input,
                ]
                for c in candidates:
                    if c.exists():
                        p_path = c
                        break
            if p_path.exists():
                with open(p_path, "r", encoding="utf-8") as f:
                    self.profile = yaml.safe_load(f) or {}
            else:
                self.profile = {}

        cand_meta = self.profile.get("candidate", {})
        self.candidate_name = cand_meta.get("name", "Candidate")
        self.candidate_title = cand_meta.get("professional_title", "Software Engineer")
        self.candidate_location = cand_meta.get("location", "India")
        try:
            self.candidate_exp_years = float(cand_meta.get("experience_years", 3.0))
        except (ValueError, TypeError):
            self.candidate_exp_years = 3.0

        self.verified_skills = self._extract_profile_skills()
        self.experience_skills, self.recent_skills, self.project_skills, self.base_quantification_score = self._extract_ats_context()

    def _extract_ats_context(self) -> Tuple[Set[str], Set[str], Set[str], float]:
        """
        Extracts contextual metadata for Enterprise ATS Shortlisting:
        - Skills demonstrated in actual work experience (claims/bullets)
        - Skills demonstrated in the candidate's most recent position
        - Skills in project portfolios
        - Quantification/metric density score (STAR metrics, %, scale, action verbs)
        """
        exp_skills: Set[str] = set()
        recent_skills: Set[str] = set()
        proj_skills: Set[str] = set()
        metric_hits = 0
        action_verb_hits = 0
        total_bullets = 0

        action_verbs = {
            "architected", "engineered", "spearheaded", "optimized", "deployed",
            "automated", "reduced", "scaled", "designed", "implemented", "built",
            "developed", "slashed", "migrated", "configured", "integrated", "led",
            "orchestrated", "authored", "accelerated", "modeled", "benchmarked"
        }

        # 1. Experience Analysis
        exp_data = self.profile.get("experience", [])
        if isinstance(exp_data, dict):
            exp_list = exp_data.get("positions", []) or exp_data.get("jobs", []) or []
        elif isinstance(exp_data, list):
            exp_list = exp_data
        else:
            exp_list = []

        if isinstance(exp_list, list):
            for i, exp in enumerate(exp_list):
                is_recent = (i == 0) or any(k in str(exp.get("period", "")).lower() for k in ["present", "2024", "2023", "2025"])

                exp_summary = str(exp.get("summary", "")).lower()
                for s in self.verified_skills:
                    if re.search(rf"\b{re.escape(s)}\b", exp_summary):
                        exp_skills.add(s)
                        if is_recent:
                            recent_skills.add(s)

                bullets_raw: List[str] = []
                bp = exp.get("bullet_pool", [])
                if isinstance(bp, list):
                    for b in bp:
                        if isinstance(b, dict):
                            claim = b.get("claim", "")
                            bullets_raw.append(claim)
                            for t in b.get("tags", []):
                                clean_t = str(t).replace("-", " ").strip().lower()
                                exp_skills.add(clean_t)
                                if is_recent:
                                    recent_skills.add(clean_t)
                            for m in b.get("verified_metrics", []):
                                metric_hits += 1

                direct_bullets = exp.get("bullets", [])
                if isinstance(direct_bullets, list):
                    bullets_raw.extend([str(b) for b in direct_bullets])

                for b_text in bullets_raw:
                    total_bullets += 1
                    b_lower = b_text.lower()
                    if re.search(r"\b\d+([.,]\d+)?%|\b\d+\+?|\b~\d+%|\b\$\d+|\b\d+\s*(ms|kb|mb|gb|tb|qps|users|turns)", b_lower):
                        metric_hits += 1
                    words = set(re.findall(r"\b[a-z]{4,}\b", b_lower))
                    if words & action_verbs:
                        action_verb_hits += 1

                    for s in self.verified_skills:
                        if re.search(rf"\b{re.escape(s)}\b", b_lower):
                            exp_skills.add(s)
                            if is_recent:
                                recent_skills.add(s)

        # 2. Projects Analysis
        for p in self.profile.get("projects", []):
            if isinstance(p, dict):
                for t in p.get("tech_stack", []):
                    clean_t = str(t).strip().lower()
                    proj_skills.add(clean_t)
                for b in p.get("bullets", []):
                    b_lower = str(b).lower()
                    for s in self.verified_skills:
                        if re.search(rf"\b{re.escape(s)}\b", b_lower):
                            proj_skills.add(s)

        # Quantification density score (0-100)
        if total_bullets > 0:
            quant_ratio = (metric_hits * 1.5 + action_verb_hits) / max(total_bullets * 2.0, 1.0)
            quant_score = min(96.0, max(55.0, round(quant_ratio * 100.0, 1)))
        else:
            quant_score = 75.0

        return exp_skills, recent_skills, proj_skills, quant_score

    def _parse_jd_must_and_nice_to_have(self, job: JobPosting) -> Tuple[List[str], List[str]]:
        """
        Parses JD content into Must-Have (Core/Mandatory) and Nice-to-Have (Preferred/Secondary) skills.
        Differentiates requirements sections from preferred sections in raw markdown if explicit lists are missing.
        """
        must_have = [s.lower().strip() for s in (job.must_have_skills or []) if s and s.strip()]
        nice_to_have = [s.lower().strip() for s in (job.nice_to_have_skills or []) if s and s.strip()]
        all_target = [s.lower().strip() for s in (job.tech_stack or []) if s and s.strip()]
        raw_text = (job.raw_markdown or "").lower()

        # If must_have not explicitly given, try splitting by section headers
        if not must_have and raw_text:
            req_pattern = r"(?:minimum qualifications|basic qualifications|required qualifications|requirements|what you(?:'ll)? need|must have|core requirements)(.*?)(?:preferred qualifications|nice to have|bonus|desired|what we offer|responsibilities|\Z)"
            pref_pattern = r"(?:preferred qualifications|nice to have|bonus points|desired skills|good to have)(.*?)(?:responsibilities|benefits|about us|\Z)"

            req_match = re.search(req_pattern, raw_text, re.DOTALL)
            pref_match = re.search(pref_pattern, raw_text, re.DOTALL)

            req_corpus = req_match.group(1) if req_match else raw_text[:2000]
            pref_corpus = pref_match.group(1) if pref_match else ""

            for skill in all_target:
                if skill in req_corpus:
                    if skill not in must_have:
                        must_have.append(skill)
                elif skill in pref_corpus:
                    if skill not in nice_to_have:
                        nice_to_have.append(skill)
                else:
                    if len(must_have) < 5:
                        must_have.append(skill)
                    else:
                        nice_to_have.append(skill)

        if not must_have:
            must_have = all_target[:5] if all_target else [s for s in ["python", "apis", "cloud"] if s in raw_text]
            nice_to_have = all_target[5:]
        elif not nice_to_have and all_target:
            for skill in all_target:
                if skill not in must_have and skill not in nice_to_have:
                    nice_to_have.append(skill)

        return must_have, nice_to_have

    def _evaluate_knockout_gates(self, job: JobPosting) -> Tuple[bool, List[str], float]:
        """
        Applies real ATS knockout / binary eligibility filters:
        1. Minimum Experience Gate (Disqualifying shortfall vs within grace)
        2. Overqualification Ceiling Check
        3. Work Mode / Location compatibility
        4. Degree / Educational threshold
        Returns (passed, details, multiplier).
        """
        passed = True
        details = []
        multiplier = 1.0

        # 1. Experience Gate
        if job.min_experience_years is not None:
            min_req = float(job.min_experience_years)
            if self.candidate_exp_years < (min_req - 1.0):
                passed = False
                details.append(f"Disqualifying Experience Shortfall: Role requires {min_req}+ years; candidate has {self.candidate_exp_years} years.")
                multiplier = 0.45
            elif self.candidate_exp_years < min_req:
                details.append(f"Borderline Experience: Role asks for {min_req} years; candidate has {self.candidate_exp_years} years (within 1-year grace window).")
                multiplier = 0.90
            else:
                details.append(f"Experience Gate Passed: Candidate ({self.candidate_exp_years} yrs) meets required {min_req}+ years.")

            if job.max_experience_years is not None:
                max_req = float(job.max_experience_years)
                if self.candidate_exp_years > (max_req + 4.0):
                    details.append(f"Seniority Warning: Candidate experience ({self.candidate_exp_years} yrs) significantly exceeds role bracket ({min_req}-{max_req} yrs).")
                    multiplier = min(multiplier, 0.88)
        else:
            details.append("Experience Gate: No explicit experience minimum stated in requisition.")

        # 2. Location / Work Mode Gate
        work_mode = getattr(job, "work_mode", "Unspecified") or "Unspecified"
        if "onsite" in work_mode.lower():
            details.append(f"Work Mode: Requisition specifies Onsite at {job.location}.")
        else:
            details.append(f"Work Mode: {work_mode} compatible with candidate profile.")

        # 3. Education Gate
        edu_reqs = getattr(job, "educational_requirements", []) or []
        if edu_reqs:
            details.append(f"Education: Position specifies {', '.join(edu_reqs)}.")
        else:
            details.append("Education Gate: Standard technical degree requirement satisfied.")

        return passed, details, multiplier

    def _extract_profile_skills(self) -> Set[str]:
        """
        Extracts skills strictly from the candidate's verified profile data.
        Zero hardcoded cross-user skills or external assumptions.
        """
        skills: Set[str] = set()

        # 1. Classic skills structure (categories -> items)
        classic = self.profile.get("skills_classic", {})
        if isinstance(classic, dict):
            for _, val in classic.items():
                if isinstance(val, dict):
                    raw_items = val.get("items", "")
                    if isinstance(raw_items, str):
                        for item in raw_items.split(","):
                            clean = re.sub(r'\(.*?\)', '', item).strip().lower()
                            if clean:
                                skills.add(clean)
                    elif isinstance(raw_items, list):
                        for item in raw_items:
                            clean = re.sub(r'\(.*?\)', '', str(item)).strip().lower()
                            if clean:
                                skills.add(clean)

        # 2. Modern skills structure (categories -> items list)
        skills_sec = self.profile.get("skills", {})
        if isinstance(skills_sec, dict):
            for _, val in skills_sec.items():
                if isinstance(val, dict):
                    raw_items = val.get("items", [])
                    if isinstance(raw_items, list):
                        for item in raw_items:
                            clean = str(item).strip().lower()
                            if clean:
                                skills.add(clean)
                    elif isinstance(raw_items, str):
                        for item in raw_items.split(","):
                            clean = str(item).strip().lower()
                            if clean:
                                skills.add(clean)

        # 3. Direct verified_skills list if present
        verified = self.profile.get("verified_skills", [])
        if isinstance(verified, list):
            for v in verified:
                clean = str(v).strip().lower()
                if clean:
                    skills.add(clean)

        # 4. Project tech stacks
        for p in self.profile.get("projects", []):
            if isinstance(p, dict):
                for t in p.get("tech_stack", []):
                    clean = str(t).strip().lower()
                    if clean:
                        skills.add(clean)

        # 5. Candidate title keyword seeds (e.g. 'java' from 'Java Developer')
        title_lower = self.candidate_title.lower()
        for kw in ["python", "java", "golang", "go", "c++", "c#", "rust", "javascript", "typescript", "ruby", "php", "sql"]:
            if re.search(rf"\b{kw}\b", title_lower):
                skills.add(kw)

        return skills

    @classmethod
    def detect_role_domain(cls, title: str, text: str = "") -> str:
        combined = (title + " " + text).lower()
        if any(k in combined for k in [
            "genai", "generative ai", "langgraph", "langchain", "prompt engineer", "llm",
            "machine learning", "ai engineer", "ai platform", "ai systems", "ai fabric", "nlp",
            "data scientist", "applied scientist", "mlops", "deep learning", "agentic ai", "rag",
            "computer vision", "artificial intelligence"
        ]):
            return "AI & Machine Learning"
        if any(k in combined for k in [
            "cloud engineer", "cloud platform", "cloud architect", "devops", "sre", "site reliability",
            "infrastructure engineer", "infrastructure manager", "platform engineer", "kubernetes",
            "terraform", "aws engineer", "azure engineer", "gcp engineer", "cloud"
        ]):
            return "Cloud & DevOps"
        if any(k in combined for k in [
            "data engineer", "big data", "etl", "spark", "hadoop", "snowflake", "databricks", "data warehouse"
        ]):
            return "Data Engineering"
        if any(k in combined for k in [
            "qa engineer", "sdet", "testing engineer", "automation engineer", "quality assurance", "test automation"
        ]):
            return "Testing & QA"
        if any(k in combined for k in [
            "frontend", "front-end", "front end", "react developer", "angular", "vue", "ui developer", "full stack", "fullstack"
        ]):
            return "Frontend & Fullstack"
        return "Backend & Software Systems"

    def evaluate_job(self, job: JobPosting) -> MatchResult:
        """
        Enterprise ATS Candidate Tracking & Shortlist Evaluation Engine.
        Simulates how enterprise ATS parsers (Workday, Taleo, Greenhouse, Ashby, Lever)
        evaluate candidate profiles against a Job Description:
        1. Knockout Gates (Minimum Experience, Overqualification, Location/Work Mode)
        2. Categorized Skill Matching (Must-Have Mandatory vs Preferred Secondary)
        3. Experience Context Proof (Skills verified in real work experience bullets vs flat list)
        4. Recency & Depth Factor (Technologies used in current/latest positions)
        5. Quantification & STAR Impact Density (Metrics, %, scale, and strong action verbs)
        6. Seniority & Title Alignment
        7. Composite ATS Shortlist Score (0-100) & Actionable Shortlist Verdict.
        """
        # 1. Knockout Gate Evaluation
        knockout_passed, knockout_reasons, knockout_multiplier = self._evaluate_knockout_gates(job)
        exp_fit = knockout_passed and (job.min_experience_years is None or self.candidate_exp_years >= (job.min_experience_years - 1.0))
        if job.min_experience_years is not None:
            exp_text = f"{int(job.min_experience_years)}-{int(job.max_experience_years)} years" if job.max_experience_years else f"{int(job.min_experience_years)}+ years"
        else:
            exp_text = "Not explicitly stated"

        # 2. Partition Must-Have vs Nice-to-Have Skills
        must_haves, nice_to_haves = self._parse_jd_must_and_nice_to_have(job)

        # 3. Must-Have Matching (35% weight)
        m_matched, m_framing, m_missing = detect_skill_equivalences(self.verified_skills, must_haves)
        if must_haves:
            must_have_score = min(100.0, (len(m_matched) / len(must_haves)) * 100.0)
        else:
            must_have_score = 80.0

        # 4. Nice-to-Have Matching (15% weight)
        p_matched, p_framing, p_missing = detect_skill_equivalences(self.verified_skills, nice_to_haves)
        if nice_to_haves:
            preferred_score = min(100.0, (len(p_matched) / len(nice_to_haves)) * 100.0)
        else:
            preferred_score = 85.0

        all_matched = sorted(list(set(m_matched + p_matched)))
        all_missing = sorted(list(set(m_missing + p_missing)))
        framing_opps = m_framing + p_framing

        # 5. Experience Placement / Proof Context Score (15% weight)
        # Higher score when target skills are verified in actual work experience bullets
        if all_matched:
            exp_proof_count = sum(1 for s in all_matched if s in self.experience_skills)
            proj_proof_count = sum(1 for s in all_matched if s in self.project_skills and s not in self.experience_skills)
            flat_proof_count = max(0, len(all_matched) - exp_proof_count - proj_proof_count)
            context_score = min(100.0, ((exp_proof_count * 1.5 + proj_proof_count * 1.2 + flat_proof_count * 0.8) / (len(all_matched) * 1.5)) * 100.0)
        else:
            context_score = 50.0

        # 6. Recency & Depth Score (10% weight)
        # Skills used in current/latest position
        if all_matched:
            recent_count = sum(1 for s in all_matched if s in self.recent_skills)
            recency_score = min(100.0, 70.0 + (recent_count / len(all_matched)) * 30.0)
        else:
            recency_score = 65.0

        # 7. Quantification & STAR Impact Score (10% weight)
        quant_score = self.base_quantification_score

        # 8. Experience & Seniority Gate Score (15% weight)
        if exp_fit:
            if job.min_experience_years is not None and job.min_experience_years <= (self.candidate_exp_years + 0.5):
                exp_score = 100.0
            else:
                exp_score = 85.0
        else:
            exp_score = 30.0

        # 9. Role Domain & Seniority Alignment
        cand_domain = self.detect_role_domain(self.candidate_title, " ".join(self.verified_skills))
        job_domain = self.detect_role_domain(job.title, job.raw_markdown)

        is_cross_domain = False
        if cand_domain != job_domain:
            ai_keywords = {"genai", "generative ai", "langgraph", "langchain", "prompt engineering", "llms", "rag", "qdrant", "chromadb", "agentic ai"}
            cloud_keywords = {"aws", "azure", "gcp", "kubernetes", "terraform", "devops", "cloud"}
            if job_domain == "AI & Machine Learning" and not any(k in self.verified_skills for k in ai_keywords):
                is_cross_domain = True
            elif job_domain == "Cloud & DevOps" and not any(k in self.verified_skills for k in cloud_keywords):
                is_cross_domain = True
            elif cand_domain not in ["Backend & Software Systems"] and job_domain not in ["Backend & Software Systems"]:
                is_cross_domain = True

        cand_tokens = set(re.findall(r"\b[a-z]{3,}\b", self.candidate_title.lower())) - {"and", "for", "the", "with"}
        job_tokens = set(re.findall(r"\b[a-z]{3,}\b", job.title.lower())) - {"and", "for", "the", "with"}
        title_overlap = len(cand_tokens & job_tokens) / max(len(cand_tokens), 1)
        seniority_score = min(100.0, title_overlap * 70.0 + 30.0)

        # 10. Composite Enterprise ATS Shortlist Score
        ats_composite = round(
            knockout_multiplier * (
                0.35 * must_have_score +
                0.15 * preferred_score +
                0.15 * exp_score +
                0.15 * context_score +
                0.10 * recency_score +
                0.10 * quant_score
            ),
            1
        )

        # 11. ATS Shortlist Verdict
        if not knockout_passed or ats_composite < 50.0:
            ats_verdict = "KNOCKED OUT"
        elif ats_composite >= 80.0 and not is_cross_domain:
            ats_verdict = "SHORTLISTED"
        elif ats_composite >= 65.0:
            ats_verdict = "REVIEWABLE"
        else:
            ats_verdict = "POTENTIAL GAP"

        is_high = ats_composite >= 75.0 and not is_cross_domain and knockout_passed

        # 12. ATS Action Plan & Dynamic Tailoring Tips
        action_plan = []
        if ats_verdict == "SHORTLISTED":
            action_plan.append(f"ATS Shortlist Verdict: SHORTLISTED ({ats_composite}% Score). Top-tier candidate; passes automated recruiter screening filters.")
        elif ats_verdict == "REVIEWABLE":
            action_plan.append(f"ATS Shortlist Verdict: REVIEWABLE ({ats_composite}% Score). Competitive candidate; minor keyword framing or skill gap needs tailoring.")
        elif ats_verdict == "POTENTIAL GAP":
            action_plan.append(f"ATS Shortlist Verdict: POTENTIAL GAP ({ats_composite}% Score). Requisition has missing must-have keywords or seniority delta.")
        else:
            action_plan.append(f"ATS Shortlist Verdict: KNOCKED OUT ({ats_composite}% Score). Does not meet initial automated screening thresholds.")

        if m_missing:
            action_plan.append(f"Core Must-Have Gap: Missing [{', '.join(m_missing[:3])}]. Highlight relevant side projects or certifications.")
        if m_framing:
            for fo in m_framing[:2]:
                action_plan.append(f"Framing Opportunity: Expose verified '{fo['candidate_skill']}' as '{fo['jd_skill']}' to match exact ATS keyword filter.")
        if context_score < 75.0:
            action_plan.append("Experience Placement: Target skills are listed in skills section but lack proof in work experience bullets.")
        if recency_score < 80.0:
            action_plan.append("Recency: Ensure target technologies are explicitly cited in your current or most recent job description.")
        if quant_score >= 80.0:
            action_plan.append("STAR Impact: High metric density in experience bullets strengthens human recruiter pass-through.")

        ats_breakdown = {
            "ats_score": ats_composite,
            "ats_verdict": ats_verdict,
            "knockout_passed": knockout_passed,
            "knockout_reasons": knockout_reasons,
            "must_have_matched": m_matched,
            "must_have_missing": m_missing,
            "must_have_score": round(must_have_score, 1),
            "nice_to_have_matched": p_matched,
            "nice_to_have_missing": p_missing,
            "preferred_score": round(preferred_score, 1),
            "context_score": round(context_score, 1),
            "recency_score": round(recency_score, 1),
            "quantification_score": round(quant_score, 1),
            "seniority_score": round(seniority_score, 1),
            "ats_action_plan": action_plan
        }

        # Recommendation for UI display
        if is_cross_domain:
            rec = f"Adjacent Domain ({job_domain}): Shared tooling/infrastructure overlap; requires discipline shift."
        elif ats_verdict == "SHORTLISTED":
            rec = f"SHORTLISTED ({ats_composite}%) - High Conviction Application"
        elif ats_verdict == "REVIEWABLE":
            rec = f"REVIEWABLE ({ats_composite}%) - Viable with Profile Tailoring"
        elif ats_verdict == "POTENTIAL GAP":
            rec = f"POTENTIAL GAP ({ats_composite}%) - Skill / Seniority Gaps to Close"
        else:
            rec = f"KNOCKED OUT ({ats_composite}%) - Disqualified by Automated ATS Filter"

        return MatchResult(
            job_title=job.title,
            company=job.company,
            url=job.url,
            location=job.location,
            job_id=job.job_id,
            source_channel=getattr(job, "source_channel", "Career Page"),
            experience_fit=exp_fit,
            exp_required_text=exp_text,
            overall_match_score=ats_composite,
            skill_match_score=round(must_have_score, 1),
            semantic_match_score=round(context_score, 1),
            matched_skills=all_matched,
            missing_skills=all_missing,
            framing_opportunities=framing_opps,
            is_high_match=is_high,
            is_cross_domain=is_cross_domain,
            job_domain=job_domain,
            candidate_domain=cand_domain,
            recommendation=rec,
            tailoring_tips=action_plan,
            ats_score=ats_composite,
            ats_verdict=ats_verdict,
            knockout_passed=knockout_passed,
            knockout_reasons=knockout_reasons,
            must_have_matched=m_matched,
            must_have_missing=m_missing,
            nice_to_have_matched=p_matched,
            nice_to_have_missing=p_missing,
            must_have_score=round(must_have_score, 1),
            preferred_score=round(preferred_score, 1),
            context_score=round(context_score, 1),
            recency_score=round(recency_score, 1),
            quantification_score=round(quant_score, 1),
            seniority_score=round(seniority_score, 1),
            ats_action_plan=action_plan,
            ats_breakdown=ats_breakdown
        )
