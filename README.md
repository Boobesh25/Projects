# JobRadar Enterprise Career Intelligence Platform

A high-density enterprise career discovery, dual-gate ATS requisition matcher, and split-screen document tailoring platform powered by a Tri-Agent Conversational AI Engine.

---

## 1. Directory Structure

```
jobradar_platform/
├── Dockerfile                         # Unified all-in-one container (runs API + UI)
├── Dockerfile.api                     # Standalone FastAPI API microservice container
├── Dockerfile.ui                      # Standalone Streamlit UI microservice container
├── docker-compose.yml                 # Multi-service setup (Postgres 16 + API + UI)
├── .dockerignore                      # Build ignore rules
├── .env.example                       # Environment template
├── requirements.txt                   # Complete dependencies
├── run_services.py                    # Process supervisor (runs API + UI concurrently)
├── entrypoint.sh                      # POSIX container startup script
│
├── api/                               # FastAPI Backend Application Layer
│   ├── __init__.py
│   └── main.py                        # REST endpoints, auth, streaming chat, and healthchecks
│
├── ui/                                # Streamlit Frontend Layer
│   ├── __init__.py
│   ├── app.py                         # High-density console UI, split-screen editor & chat
│   └── .streamlit/
│       └── config.toml                # Custom dark slate theme, server & port configuration
│
├── core/                              # Core Domain & Business Services
│   ├── __init__.py
│   ├── db_engine.py                   # Async SQLAlchemy engine (Postgres with SQLite fallback)
│   ├── db_models.py                   # Relational ORM models
│   ├── auth_service.py                # Security, JWT tokens & authorization
│   ├── chat_agent_service.py          # Tri-Agent Conversational AI Engine
│   ├── profile_optimizer.py           # ATS scoring, tailoring & document compiler
│   ├── company_crawler.py             # 2,000+ company catalog synchronizer
│   ├── pdf_report_generator.py        # PDF executive summary generator
│   ├── gdrive_service.py              # Cloud storage & Google Drive sync
│   └── cv_analyzer.py                 # Profile parser & skill extractor
│
├── analyzer/                          # Requisition Intelligence & Matching Engine
│   ├── __init__.py
│   ├── matcher.py                     # Dual-gate ATS matching engine (55/25/20)
│   ├── discovery.py                   # Career portal & ATS crawling engine
│   ├── extractor.py                   # Skill and requirement extraction
│   ├── models.py                      # Data models & schemas
│   ├── ai_reasoner.py                 # Reasoning & gap analysis
│   └── reporter.py                    # Excel & data formatting
│
└── data/                              # Static Catalog & Template Assets
    ├── enterprise_company_directory.json  # 2,049 company catalog
    ├── PROFILE.md                         # Candidate authentic baseline document
    ├── profile.yaml                       # Candidate profile YAML
    └── main.typ                           # Typst document template
```

---

## 2. Quickstart: Local Development

### Prerequisites
- Python 3.10+
- (Optional) PostgreSQL 15+ (if unavailable, SQLite activates automatically)

### Step 1: Install Dependencies
```bash
cd jobradar_platform
pip install -r requirements.txt
```

### Step 2: Configure Environment
```bash
cp .env.example .env
```

### Step 3: Launch Both Services Concurrently
```bash
python run_services.py
```
This automatically launches:
- **FastAPI Backend API**: `http://localhost:8000` (Docs: `http://localhost:8000/docs`)
- **Streamlit UI Portal**: `http://localhost:8501`

---

## 3. Docker Deployment

### Option A: Multi-Service Orchestration with Docker Compose (Recommended)
Launches PostgreSQL 16, the FastAPI backend, and the Streamlit frontend with healthchecks and automatic service discovery:

```bash
cd jobradar_platform
docker compose up --build
```

- Streamlit Console: `http://localhost:8501`
- Backend API: `http://localhost:8000`
- PostgreSQL: `localhost:5432`

### Option B: Unified Single Container
Builds a single image containing both API and UI with SQLite embedded:

```bash
docker build -t jobradar:latest -f Dockerfile .
docker run -p 8000:8000 -p 8501:8501 --env-file .env jobradar:latest
```

---

## 4. Standalone Streamlit Deployment

To deploy the Streamlit UI independently (e.g. on Streamlit Community Cloud, AWS App Runner, or Google Cloud Run):

1. Set the environment variable `API_BASE_URL` pointing to your hosted FastAPI backend:
   ```bash
   export API_BASE_URL=https://api.yourdomain.com
   ```
2. Run Streamlit directly:
   ```bash
   streamlit run ui/app.py
   ```

The custom dark slate theme, server settings, and port configuration are automatically loaded from `ui/.streamlit/config.toml`.

---

## 5. Security & Access Control

- **Authorized User**: Restricted exclusively to `boobesh2509@gmail.com`.
- **Zero Fabrication**: Preserves authentic career track record at **Corent Technology** without generating artificial roles or intrusive headers.
- **Auto Session Restoration**: Deep links (e.g. `?nav=Deep+Analysis+%26+Tailoring&job_id=...`) automatically authenticate and open the targeted requisition without login prompts.
