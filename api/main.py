"""
FastAPI Backend Application
===========================
Provides REST endpoints for:
1. Google OAuth & Session Management
2. User API Key Configuration
3. Base Document Upload & YAML Profile Compiler
4. Daily Company Ingestion (MNCs, AI Startups, Remote-First) - 100+ Companies
5. Live Profile-to-JD Match Analyser (including companies with 0 openings)
"""

import os
import sys
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any

# Ensure project root and core directories are on sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_current_dir)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)
_core_dir = os.path.join(_root_dir, "core")
if _core_dir not in sys.path:
    sys.path.insert(0, _core_dir)

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func

try:
    from core.db_models import User, CandidateProfile, CompanyJob, AnalysisJobResult
    from core.db_engine import init_db, get_db_session
    from core.auth_service import create_access_token, verify_google_id_token, get_current_user_payload
    from core.cv_analyzer import DocumentProfileAnalyzer
    from core.company_crawler import CompanyService
except ImportError:
    from db_models import User, CandidateProfile, CompanyJob, AnalysisJobResult
    from db_engine import init_db, get_db_session
    from auth_service import create_access_token, verify_google_id_token, get_current_user_payload
    from cv_analyzer import DocumentProfileAnalyzer
    from company_crawler import CompanyService

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(
    title="JobRadar Platform API - Career Intelligence & Matcher",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health")
@app.get("/api/health")
async def health_check():
    """Healthcheck endpoint for Docker containers and cloud probes."""
    return {
        "status": "healthy",
        "service": "JobRadar API",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# -----------------------------------------------------------------------------
# Request & Response Schemas
# -----------------------------------------------------------------------------
class GoogleAuthRequest(BaseModel):
    id_token: str

class DevLoginRequest(BaseModel):
    email: str = "boobesh2509@gmail.com"
    name: Optional[str] = "Boobesh S"

class AddUserRequest(BaseModel):
    email: str
    name: Optional[str] = "Authorized Candidate"

class AuthResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    avatar_url: Optional[str] = None
    token: str
    is_onboarded: bool

class ApiKeyRequest(BaseModel):
    api_key: str
    llm_endpoint: Optional[str] = "https://generativelanguage.googleapis.com/v1beta/openai/"

class SaveProfileRequest(BaseModel):
    profile_yaml: str
    candidate_name: str
    professional_title: str
    experience_years: float = 3.0
    verified_skills: List[str]

class RunAnalysisRequest(BaseModel):
    selected_companies: Optional[List[str]] = None
    selected_group: Optional[str] = "All"
    selected_channel: Optional[str] = "All"

class AddCompanyRequest(BaseModel):
    company_name: str
    company_group: Optional[str] = "MNC"
    career_url: Optional[str] = None

# -----------------------------------------------------------------------------
# Auth Endpoints
# -----------------------------------------------------------------------------
@app.post("/api/auth/google", response_model=AuthResponse)
async def google_login(req: GoogleAuthRequest, session: AsyncSession = Depends(get_db_session)):
    """Verifies Google ID token and returns session token."""
    g_info = await verify_google_id_token(req.id_token)
    email = g_info["email"]
    name = g_info["name"]

    stmt = select(User).where(User.email == email)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        user = User(
            id=g_info["google_id"],
            email=email,
            display_name=name,
            avatar_url=g_info.get("picture"),
            auth_provider="google"
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    p_stmt = select(CandidateProfile).where(CandidateProfile.user_id == user.id)
    p_res = await session.execute(p_stmt)
    has_profile = p_res.scalar_one_or_none() is not None

    token = create_access_token(user.id, user.email, user.display_name)
    return AuthResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        token=token,
        is_onboarded=has_profile
    )

@app.post("/api/auth/dev-login", response_model=AuthResponse)
async def dev_login(req: DevLoginRequest, session: AsyncSession = Depends(get_db_session)):
    """
    Login endpoint: Strictly requires email to exist in PostgreSQL database.
    No self-registration. Only boobesh2509@gmail.com can authorize additional emails.
    """
    clean_email = (req.email or "").strip().lower()
    if not clean_email:
        raise HTTPException(status_code=400, detail="Please enter an email address.")

    stmt = select(User).where(func.lower(User.email) == clean_email)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        # Superadmin bootstrap if database was just initialized
        if clean_email == "boobesh2509@gmail.com":
            user = User(
                email="boobesh2509@gmail.com",
                display_name=req.name or "Boobesh S",
                auth_provider="superadmin"
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            raise HTTPException(
                status_code=403,
                detail="Access Denied: Account is not authorized. Please contact your system administrator for access."
            )

    p_stmt = select(CandidateProfile).where(CandidateProfile.user_id == user.id)
    p_res = await session.execute(p_stmt)
    has_profile = p_res.scalar_one_or_none() is not None

    token = create_access_token(user.id, user.email, user.display_name)
    return AuthResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        token=token,
        is_onboarded=has_profile
    )

# -----------------------------------------------------------------------------
# Admin & User Access Control Endpoints (boobesh2509@gmail.com only)
# -----------------------------------------------------------------------------
@app.get("/api/admin/users")
async def list_authorized_users(
    user_payload: Dict[str, Any] = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_db_session)
):
    """Only boobesh2509@gmail.com can list all authorized users."""
    caller_email = (user_payload.get("email") or "").strip().lower()
    if caller_email != "boobesh2509@gmail.com":
        raise HTTPException(status_code=403, detail="Forbidden: Administrative privileges required.")

    stmt = select(User).order_by(User.created_at.asc())
    res = await session.execute(stmt)
    users = res.scalars().all()

    return [
        {
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "auth_provider": u.auth_provider,
            "is_superadmin": (u.email.lower() == "boobesh2509@gmail.com"),
            "created_at": str(u.created_at) if u.created_at else "N/A"
        }
        for u in users
    ]

@app.post("/api/admin/users")
async def add_authorized_user(
    req: AddUserRequest,
    user_payload: Dict[str, Any] = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_db_session)
):
    """Only boobesh2509@gmail.com can authorize new users."""
    caller_email = (user_payload.get("email") or "").strip().lower()
    if caller_email != "boobesh2509@gmail.com":
        raise HTTPException(status_code=403, detail="Forbidden: Administrative privileges required.")

    new_email = (req.email or "").strip().lower()
    if not new_email or "@" not in new_email:
        raise HTTPException(status_code=400, detail="Please provide a valid email address.")

    stmt = select(User).where(func.lower(User.email) == new_email)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"User '{new_email}' is already authorized in PostgreSQL database.")

    new_user = User(
        email=new_email,
        display_name=req.name or new_email.split("@")[0].title(),
        auth_provider="authorized_by_boobesh"
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    return {"message": f"User '{new_email}' has been successfully authorized.", "email": new_email}

@app.delete("/api/admin/users/{target_email}")
async def revoke_authorized_user(
    target_email: str,
    user_payload: Dict[str, Any] = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_db_session)
):
    """Only boobesh2509@gmail.com can revoke user access."""
    caller_email = (user_payload.get("email") or "").strip().lower()
    if caller_email != "boobesh2509@gmail.com":
        raise HTTPException(status_code=403, detail="Forbidden: Administrative privileges required.")

    clean_target = (target_email or "").strip().lower()
    if clean_target == "boobesh2509@gmail.com":
        raise HTTPException(status_code=400, detail="Cannot revoke superadmin account.")

    stmt = select(User).where(func.lower(User.email) == clean_target)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    await session.delete(user)
    await session.commit()

    return {"message": f"Access revoked for '{clean_target}'."}

# -----------------------------------------------------------------------------
# Onboarding & Profile Endpoints
# -----------------------------------------------------------------------------
@app.post("/api/user/api-key")
async def set_user_api_key(
    req: ApiKeyRequest,
    user_payload: Dict[str, Any] = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_db_session)
):
    """Save Gemini / LLM API Key."""
    user_id = user_payload["sub"]
    stmt = select(User).where(User.id == user_id)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.api_key = req.api_key
    user.llm_endpoint = req.llm_endpoint
    await session.commit()
    return {"message": "API key successfully configured."}

@app.post("/api/profile/upload")
async def upload_and_analyze_document(
    file: UploadFile = File(...),
    user_payload: Dict[str, Any] = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_db_session)
):
    """Upload base CV/doc -> parse text -> generate candidate YAML profile."""
    content = await file.read()
    raw_text = DocumentProfileAnalyzer.extract_text(content, file.filename)
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from document.")

    user_id = user_payload["sub"]
    stmt = select(User).where(User.id == user_id)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    api_key = user.api_key if user else None
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")

    yaml_str, skills, profile_dict = DocumentProfileAnalyzer.generate_yaml_profile(
        raw_text=raw_text,
        user_name=user_payload.get("name", "Candidate"),
        api_key=api_key
    )

    candidate_meta = profile_dict.get("candidate", {})
    return {
        "filename": file.filename,
        "candidate_name": candidate_meta.get("name", user_payload.get("name", "Candidate")),
        "professional_title": candidate_meta.get("professional_title", "Software Engineer"),
        "experience_years": float(candidate_meta.get("experience_years", 3.0)),
        "verified_skills": skills,
        "profile_yaml": yaml_str
    }

@app.post("/api/profile/save")
async def save_profile(
    req: SaveProfileRequest,
    user_payload: Dict[str, Any] = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_db_session)
):
    """Confirm and onboard candidate profile into PostgreSQL."""
    user_id = user_payload["sub"]
    stmt = select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    res = await session.execute(stmt)
    profile = res.scalar_one_or_none()

    if not profile:
        profile = CandidateProfile(
            user_id=user_id,
            candidate_name=req.candidate_name,
            professional_title=req.professional_title,
            experience_years=req.experience_years,
            verified_skills=req.verified_skills,
            profile_yaml=req.profile_yaml
        )
        session.add(profile)
    else:
        profile.candidate_name = req.candidate_name
        profile.professional_title = req.professional_title
        profile.experience_years = req.experience_years
        profile.verified_skills = req.verified_skills
        profile.profile_yaml = req.profile_yaml

    await session.commit()
    return {"message": "User onboarded successfully!", "is_onboarded": True}

@app.post("/api/profile/reset")
async def reset_profile(
    user_payload: Dict[str, Any] = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_db_session)
):
    """Deletes existing candidate profile so the user can start onboarding fresh."""
    user_id = user_payload["sub"]
    stmt = delete(CandidateProfile).where(CandidateProfile.user_id == user_id)
    await session.execute(stmt)
    await session.commit()
    return {"message": "Profile reset. Ready for fresh onboarding.", "is_onboarded": False}

@app.get("/api/profile")
async def get_my_profile(
    user_payload: Dict[str, Any] = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_db_session)
):
    """Retrieve candidate's active profile."""
    user_id = user_payload["sub"]
    stmt = select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    res = await session.execute(stmt)
    profile = res.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found. Complete onboarding first.")

    return {
        "candidate_name": profile.candidate_name,
        "professional_title": profile.professional_title,
        "experience_years": profile.experience_years,
        "verified_skills": profile.verified_skills,
        "profile_yaml": profile.profile_yaml
    }

# -----------------------------------------------------------------------------
# Daily Company Feeds & Analysis Endpoints
# -----------------------------------------------------------------------------
@app.get("/api/companies")
async def get_daily_companies(
    count: int = Query(5000, ge=10, le=50000),
    refresh: bool = Query(False),
    user_payload: Dict[str, Any] = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_db_session)
):
    """Loads daily companies into memory/DB when user logs in with zero artificial limits."""
    user_id = user_payload.get("user_id") or user_payload.get("sub")
    cand = await session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user_id))
    cand_domain = "Cloud & DevOps"
    if cand:
        from analyzer.matcher import JobMatcher
        cand_domain = JobMatcher.detect_role_domain(cand.professional_title, " ".join(cand.verified_skills))

    jobs = await CompanyService.sync_daily_jobs(session, target_count=count, force_refresh=refresh, candidate_domain=cand_domain)
    groups = sorted(list(set(j.company_group for j in jobs)))
    companies = sorted(list(set(j.company_name for j in jobs)))

    return {
        "total_jobs": len(jobs),
        "available_groups": ["All"] + groups,
        "available_companies": companies,
        "available_channels": ["All", "Career Page", "LinkedIn", "Naukri"],
        "jobs": [
            {
                "id": j.id,
                "job_id": j.job_id,
                "company_name": j.company_name,
                "company_group": j.company_group,
                "source_channel": getattr(j, "source_channel", "Career Page") or CompanyService.get_channel_from_url(j.url),
                "title": j.title,
                "location": j.location,
                "work_mode": j.work_mode,
                "experience_text": j.experience_text,
                "url": j.url,
                "job_apply_url": j.url,
                "skills_required": j.skills_required
            }
            for j in jobs
        ]
    }

@app.post("/api/companies/add")
async def add_custom_company(
    req: AddCompanyRequest,
    user_payload: Dict[str, Any] = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_db_session)
):
    """Allows dynamically registering ANY company to database without limits."""
    name_clean = req.company_name.strip()
    if not name_clean:
        raise HTTPException(status_code=400, detail="Company name cannot be empty.")

    stmt = select(CompanyJob).where(func.lower(CompanyJob.company_name) == name_clean.lower())
    res = await session.execute(stmt)
    existing = res.scalars().first()
    if existing:
        return {
            "status": "already_exists",
            "message": f"'{existing.company_name}' is already monitored in database.",
            "company_name": existing.company_name,
            "url": existing.url
        }

    career_url = req.career_url.strip() if req.career_url else CompanyService.get_official_career_url(name_clean)
    today = datetime.now(timezone.utc).date()

    new_job = CompanyJob(
        job_id="NO-ROLE-FOUND",
        company_name=name_clean,
        company_group=req.company_group or "MNC",
        source_channel="Career Page",
        title=f"Openings at {name_clean}",
        location="India / Global",
        work_mode="Unspecified",
        experience_text="N/A",
        min_exp=0.0,
        max_exp=0.0,
        url=career_url,
        skills_required=[],
        raw_description=f"Monitored across Career Page, LinkedIn & Naukri for active requisitions at {name_clean}.",
        fetched_date=today
    )
    session.add(new_job)
    await session.commit()
    await session.refresh(new_job)

    return {
        "status": "created",
        "message": f"Successfully registered '{name_clean}' to database.",
        "company_name": new_job.company_name,
        "url": new_job.url,
        "id": new_job.id
    }

@app.post("/api/analyze")
async def analyze_jobs(
    req: RunAnalysisRequest,
    user_payload: Dict[str, Any] = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_db_session)
):
    """Runs match analysis between candidate's YAML profile and selected jobs."""
    user_id = user_payload["sub"]
    stmt = select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    res = await session.execute(stmt)
    profile = res.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=400, detail="Profile not onboarded. Please upload your document first.")

    from analyzer.matcher import JobMatcher
    cand_domain = JobMatcher.detect_role_domain(profile.professional_title, " ".join(profile.verified_skills or []))

    analysis_dict = await CompanyService.run_analysis(
        session=session,
        user_id=user_id,
        profile_yaml_str=profile.profile_yaml,
        selected_companies=req.selected_companies,
        selected_group=req.selected_group,
        selected_channel=req.selected_channel,
        candidate_domain=cand_domain
    )

    return analysis_dict

# -----------------------------------------------------------------------------
# Deep Analysis & Gemini Tailoring Endpoints
# -----------------------------------------------------------------------------
class TailorAnalyzeRequest(BaseModel):
    job_data: Dict[str, Any]
    user_feedback: Optional[str] = None
    api_key: Optional[str] = None

class TailorCompileRequest(BaseModel):
    role_title: str
    company_name: str
    portal: str
    markdown_text: Optional[str] = None
    tailored_summary: Optional[str] = ""
    tailored_skills: Optional[List[str]] = []
    experience_bullets: Optional[List[str]] = []
    save_to_drive: bool = False

class PromptEditRequest(BaseModel):
    existing_markdown: str
    prompt_directive: str
    job_data: Dict[str, Any]
    api_key: Optional[str] = None

class TailorChatMessage(BaseModel):
    role: str
    content: str

class TailorChatRequest(BaseModel):
    message: str
    history: Optional[List[TailorChatMessage]] = []
    job_data: Dict[str, Any]
    existing_markdown: str
    api_key: Optional[str] = None

class DriveUploadRequest(BaseModel):
    markdown_text: str
    role_title: str
    company_name: str
    portal: str

@app.get("/api/profile/markdown")
async def get_my_profile_markdown(
    user_payload: Dict[str, Any] = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_db_session)
):
    """Retrieves the candidate's authentic base Markdown document."""
    user_id = user_payload["sub"]
    cand = await session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user_id))
    user = await session.scalar(select(User).where(User.id == user_id))
    if not cand:
        raise HTTPException(status_code=404, detail="No profile found. Complete onboarding first.")

    from profile_optimizer import get_candidate_base_markdown
    base_md = get_candidate_base_markdown(
        user_email=user.email if user else "",
        profile_yaml=cand.profile_yaml
    )
    return {"markdown": base_md}

@app.post("/api/tailor/prompt-edit")
async def tailor_prompt_edit(
    req: PromptEditRequest,
    user_payload: Dict[str, Any] = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_db_session)
):
    """Takes existing candidate markdown and modifies/enriches it with Gemini based on user prompt."""
    user_id = user_payload["sub"]
    user = await session.scalar(select(User).where(User.id == user_id))
    effective_key = req.api_key or (user.api_key if user else None) or os.getenv("GEMINI_API_KEY")

    from profile_optimizer import prompt_enhance_document_with_gemini
    updated_md = prompt_enhance_document_with_gemini(
        existing_md=req.existing_markdown,
        prompt_directive=req.prompt_directive,
        job_data=req.job_data,
        api_key=effective_key
    )
    return {"updated_markdown": updated_md}

@app.post("/api/tailor/analyze")
async def tailor_analyze(
    req: TailorAnalyzeRequest,
    user_payload: Dict[str, Any] = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_db_session)
):
    """Generates tailored profile content and detects framing opportunities with Gemini 2.0 Flash."""
    user_id = user_payload["sub"]
    cand = await session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user_id))
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate profile not found.")

    user = await session.scalar(select(User).where(User.id == user_id))
    effective_api_key = req.api_key or (user.api_key if user else None) or os.getenv("GEMINI_API_KEY")

    import yaml
    from profile_optimizer import generate_tailored_profile_with_gemini, detect_skill_equivalences
    cand_dict = yaml.safe_load(cand.profile_yaml) or {}
    cand_dict["verified_skills"] = cand.verified_skills or []

    tailored_result = generate_tailored_profile_with_gemini(
        candidate_profile=cand_dict,
        job_data=req.job_data,
        user_feedback=req.user_feedback,
        api_key=effective_api_key
    )

    target_skills = req.job_data.get("skills_required") or req.job_data.get("tech_stack") or []
    matched, framing, missing = detect_skill_equivalences(set(cand.verified_skills or []), target_skills)

    return {
        "tailored_data": tailored_result,
        "framing_opportunities": framing,
        "matched_skills": matched,
        "missing_skills": missing,
        "effective_key_present": bool(effective_api_key and effective_api_key.strip())
    }

@app.post("/api/tailor/compile")
async def tailor_compile(
    req: TailorCompileRequest,
    user_payload: Dict[str, Any] = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_db_session)
):
    """Compiles ATS-compliant PDF and saves to Google Drive backup."""
    user_id = user_payload["sub"]
    cand = await session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user_id))
    user = await session.scalar(select(User).where(User.id == user_id))

    cand_name = cand.candidate_name if cand else (user.display_name if user else "Candidate")
    contact_info = {
        "email": user.email if user else "candidate@domain.com",
        "phone": "+91 9876543210",
        "location": getattr(cand, "location", "India") or "India"
    }

    import base64
    from profile_optimizer import compile_tailored_pdf, compile_markdown_to_pdf, save_to_cloud_backup, sanitize_filename

    if req.markdown_text and req.markdown_text.strip():
        pdf_bytes = compile_markdown_to_pdf(
            md_text=req.markdown_text,
            role_title=req.role_title,
            company_name=req.company_name,
            portal=req.portal
        )
    else:
        from profile_optimizer import get_candidate_base_markdown
        base_md = get_candidate_base_markdown(user.email if user else "", cand.profile_yaml if cand else "")
        pdf_bytes = compile_markdown_to_pdf(
            md_text=base_md,
            role_title=req.role_title,
            company_name=req.company_name,
            portal=req.portal
        )

    filename = sanitize_filename(req.role_title, req.company_name, req.portal)
    drive_meta = None
    if req.save_to_drive:
        drive_meta = save_to_cloud_backup(pdf_bytes, req.role_title, req.company_name, req.portal)

    return {
        "filename": filename,
        "pdf_base64": base64.b64encode(pdf_bytes).decode("utf-8"),
        "drive_meta": drive_meta
    }

@app.post("/api/tailor/chat")
async def tailor_chat(
    req: TailorChatRequest,
    user_payload: Dict[str, Any] = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Server-side Streaming Conversational Agent for Deep JD Analysis & Document Tailoring.
    Provides ATS match score guidance, answers JD questions, and performs authentic document updates.
    """
    user_id = user_payload["sub"]
    user = await session.scalar(select(User).where(User.id == user_id))
    effective_key = req.api_key or (user.api_key if user else None) or os.getenv("GEMINI_API_KEY")

    try:
        from core.chat_agent_service import generate_chat_stream
    except ImportError:
        from chat_agent_service import generate_chat_stream
    hist_dicts = [{"role": h.role, "content": h.content} for h in (req.history or [])]

    async def stream_generator():
        async for chunk in generate_chat_stream(
            message=req.message,
            history=hist_dicts,
            job_data=req.job_data,
            existing_markdown=req.existing_markdown,
            api_key=effective_key
        ):
            yield chunk

    return StreamingResponse(stream_generator(), media_type="text/plain; charset=utf-8")

@app.post("/api/tailor/drive-upload")
async def tailor_drive_upload(
    req: DriveUploadRequest,
    user_payload: Dict[str, Any] = Depends(get_current_user_payload),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Server-side Google Drive sync: Compiles PDF on the server, uploads to the
    'JobRadar Career Documents' folder in Google Drive, and returns drive metadata.
    """
    try:
        from core.profile_optimizer import compile_markdown_to_pdf, save_to_cloud_backup
    except ImportError:
        from profile_optimizer import compile_markdown_to_pdf, save_to_cloud_backup
    
    pdf_bytes = compile_markdown_to_pdf(
        md_text=req.markdown_text,
        role_title=req.role_title,
        company_name=req.company_name,
        portal=req.portal
    )
    
    meta = save_to_cloud_backup(
        pdf_bytes=pdf_bytes,
        role_title=req.role_title,
        company_name=req.company_name,
        portal=req.portal
    )
    return meta

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT_API", "8000"))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)
