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
from typing import Set, List, Dict, Any, Union
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
        try:
            self.candidate_exp_years = float(cand_meta.get("experience_years", 3.0))
        except (ValueError, TypeError):
            self.candidate_exp_years = 3.0

        self.verified_skills = self._extract_profile_skills()

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
        # 1. Experience Seniority Gate
        exp_fit = True
        exp_text = "Not explicitly stated"

        if job.min_experience_years is not None:
            if job.max_experience_years is not None:
                exp_text = f"{int(job.min_experience_years)}-{int(job.max_experience_years)} years"
            else:
                exp_text = f"{int(job.min_experience_years)}+ years"

            # Check if role requires significantly more experience than candidate has
            if job.min_experience_years > (self.candidate_exp_years + 2.0):
                exp_fit = False
            # Check if role has a low ceiling (overqualified)
            if job.max_experience_years is not None and self.candidate_exp_years > (job.max_experience_years + 4.0):
                exp_fit = False

        # 2. Skill Matrix Overlap Score (55% weight) with Semantic Skill Equivalences
        target_skills = job.tech_stack if job.tech_stack else [s.lower() for s in (job.must_have_skills + job.nice_to_have_skills)]

        matched, framing_opps, missing = detect_skill_equivalences(self.verified_skills, target_skills)

        total_skills = len(target_skills)
        if total_skills > 0:
            skill_score = (len(matched) / total_skills) * 100.0
        else:
            # Fallback if job does not list explicit tech stack
            text_corpus = (job.title + " " + job.raw_markdown).lower()
            matched_corpus = [vs for vs in self.verified_skills if vs in text_corpus]
            if matched_corpus:
                skill_score = min(100.0, len(matched_corpus) * 20.0)
                matched = matched_corpus[:5]
            else:
                skill_score = 40.0

        # 3. Dynamic Title & Domain Alignment Score (25% weight)
        cand_domain = self.detect_role_domain(self.candidate_title, " ".join(self.verified_skills))
        job_domain = self.detect_role_domain(job.title, job.raw_markdown)

        # Cross-Domain Determination:
        # Check if job domain fundamentally diverges from candidate's specialization
        is_cross_domain = False
        if cand_domain != job_domain:
            ai_keywords = {"genai", "generative ai", "langgraph", "langchain", "prompt engineering", "llms", "rag", "qdrant", "chromadb", "agentic ai"}
            cloud_keywords = {"aws", "azure", "gcp", "kubernetes", "terraform", "devops", "cloud"}
            
            # If job is AI/ML and candidate lacks core AI keywords:
            if job_domain == "AI & Machine Learning" and not any(k in self.verified_skills for k in ai_keywords):
                is_cross_domain = True
            # If job is Cloud/DevOps and candidate lacks cloud keywords:
            elif job_domain == "Cloud & DevOps" and not any(k in self.verified_skills for k in cloud_keywords):
                is_cross_domain = True
            elif cand_domain not in ["Backend & Software Systems"] and job_domain not in ["Backend & Software Systems"]:
                is_cross_domain = True

        cand_tokens = set(re.findall(r"\b[a-z]{3,}\b", self.candidate_title.lower())) - {"and", "for", "the", "with"}
        job_tokens = set(re.findall(r"\b[a-z]{3,}\b", job.title.lower())) - {"and", "for", "the", "with"}

        title_overlap = len(cand_tokens & job_tokens) / max(len(cand_tokens), 1)
        
        # Check density of candidate skills appearing in the job description
        lower_desc = (job.title + " " + job.raw_markdown).lower()
        skills_in_desc = sum(1 for vs in self.verified_skills if vs in lower_desc)
        desc_alignment = min(1.0, skills_in_desc / max(len(self.verified_skills), 1))

        semantic_score = min(100.0, (title_overlap * 60.0 + desc_alignment * 40.0))

        # 4. Composite Dual-Gate Score (20% Experience weight)
        if exp_fit:
            if job.min_experience_years is not None and job.min_experience_years <= (self.candidate_exp_years + 0.5):
                exp_score = 100.0
            else:
                exp_score = 85.0
            exp_multiplier = 1.0
        else:
            exp_score = 25.0
            exp_multiplier = 0.45

        overall_score = round(
            exp_multiplier * (0.55 * skill_score + 0.25 * semantic_score + 0.20 * exp_score),
            1
        )
        is_high = overall_score >= 75.0

        # 5. Recommendation & Dynamic Tailoring Tips (Zero hardcoded bullets)
        if is_cross_domain:
            rec = f"Adjacent Domain ({job_domain}): Shared tooling/infrastructure overlap; requires discipline shift."
            tips = [
                f"Cross-Domain Opportunity in {job_domain}. Verified tooling overlap: {', '.join(matched[:3]) if matched else 'general software'}.",
                f"Primary requirements focus on {job_domain} core stack. Build specialized portfolio to apply."
            ]
        elif is_high:
            rec = "STRONG MATCH (>= 75%) - High Priority Application"
            tips = []
            if framing_opps:
                for fo in framing_opps[:2]:
                    tips.append(f"Framing Gap: Expose verified '{fo['candidate_skill']}' as '{fo['jd_skill']}' in your profile.")
            if missing:
                tips.append(f"Skill Gap: Highlight projects or certifications in {', '.join(missing[:3])} to close ATS keyword gap.")
            if matched:
                tips.append(f"Spotlight verified expertise in {', '.join(matched[:3])} prominently in profile summary.")
            if not exp_fit:
                tips.append(f"Requisition asks for {exp_text}; emphasize high-impact leadership to address seniority expectation.")
            else:
                tips.append(f"Align profile summary to directly address the '{job.title}' core requirements.")
        elif overall_score >= 60.0:
            rec = "MODERATE MATCH (60-74%) - Requires Targeted Profile Tailoring"
            tips = []
            if framing_opps:
                for fo in framing_opps[:2]:
                    tips.append(f"Framing Gap: Expose verified '{fo['candidate_skill']}' as '{fo['jd_skill']}' in your profile.")
            if missing:
                tips.append(f"Skill Gap: Highlight projects or certifications in {', '.join(missing[:3])} to close ATS keyword gap.")
            if matched:
                tips.append(f"Spotlight verified expertise in {', '.join(matched[:3])} prominently in profile summary.")
            if not exp_fit:
                tips.append(f"Requisition asks for {exp_text}; emphasize high-impact leadership to address seniority expectation.")
            else:
                tips.append(f"Align profile summary to directly address the '{job.title}' core requirements.")
        else:
            rec = "LOW MATCH (< 60%) - Disqualify / Seniority or Core Stack Mismatch"
            tips = []
            if framing_opps:
                for fo in framing_opps[:2]:
                    tips.append(f"Framing Gap: Expose verified '{fo['candidate_skill']}' as '{fo['jd_skill']}' in your profile.")
            if missing:
                tips.append(f"Skill Gap: Highlight projects or certifications in {', '.join(missing[:3])} to close ATS keyword gap.")
            if matched:
                tips.append(f"Spotlight verified expertise in {', '.join(matched[:3])} prominently in profile summary.")

        return MatchResult(
            job_title=job.title,
            company=job.company,
            url=job.url,
            location=job.location,
            job_id=job.job_id,
            source_channel=getattr(job, "source_channel", "Career Page"),
            experience_fit=exp_fit,
            exp_required_text=exp_text,
            overall_match_score=overall_score,
            skill_match_score=round(skill_score, 1),
            semantic_match_score=round(semantic_score, 1),
            matched_skills=matched,
            missing_skills=missing,
            framing_opportunities=framing_opps,
            is_high_match=is_high and not is_cross_domain,
            is_cross_domain=is_cross_domain,
            job_domain=job_domain,
            candidate_domain=cand_domain,
            recommendation=rec,
            tailoring_tips=tips
        )
