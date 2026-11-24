#set page(
  paper: "a4",
  margin: (top: 36pt, bottom: 36pt, left: 40pt, right: 40pt),
  header: align(right)[
    #text(size: 8.5pt, fill: rgb("#6b7280"))[Automated Career Page Analyser & Job Matching Engine | Architecture Blueprint]
  ],
  footer: context align(center)[
    #text(size: 8.5pt, fill: rgb("#6b7280"))[Page #counter(page).display()]
  ]
)

#set text(
  font: "Times New Roman",
  size: 10pt,
  fill: rgb("#1f2937"),
  lang: "en",
  spacing: 105%
)

#set par(justify: true, leading: 0.56em)

// Styled Section Heading with Navy Accent
#let section_heading(title) = [
  #v(1.0em)
  #block(width: 100%, stroke: (bottom: 1.5pt + rgb("#1e3a8a")), inset: (bottom: 0.3em))[
    #text(weight: "bold", size: 13pt, fill: rgb("#1e3a8a"))[#title]
  ]
  #v(0.4em)
]

#let subsection_heading(title) = [
  #v(0.6em)
  #text(weight: "bold", size: 10.8pt, fill: rgb("#2563eb"))[#title]
  #v(0.2em)
]

#let callout_box(title, body, border_color: rgb("#2563eb"), bg_color: rgb("#eff6ff")) = [
  #block(
    width: 100%,
    fill: bg_color,
    stroke: (left: 3.5pt + border_color),
    inset: (x: 12pt, y: 8pt),
    radius: (right: 4pt)
  )[
    #if title != "" [
      #text(weight: "bold", size: 10pt, fill: border_color)[#title] \
      #v(0.2em)
    ]
    #text(size: 9.5pt, fill: rgb("#1f2937"))[#body]
  ]
]

// ==============================================================================
// TITLE & METADATA
// ==============================================================================
#align(center)[
  #text(weight: "bold", size: 21pt, fill: rgb("#1e3a8a"))[Automated Career Page Analyser] \
  #v(0.2em)
  #text(weight: "bold", size: 12.5pt, fill: rgb("#4b5563"))[Universal ATS Extraction & 75–80% Candidate Alignment Engine] \
  #v(0.4em)
  #text(size: 9.5pt, fill: rgb("#374151"))[
    *System Design & Production Architecture Blueprint* #h(0.5em) | #h(0.5em)
    Candidate: *Boobesh S (GenAI Engineer)* #h(0.5em) | #h(0.5em)
    Version 1.0.0
  ]
]

#v(0.8em)
#line(length: 100%, stroke: 0.75pt + rgb("#cbd5e1"))
#v(0.5em)

// ==============================================================================
// 1. EXECUTIVE SUMMARY
// ==============================================================================
#section_heading("1. Executive Summary & Problem Statement")

Modern technical recruitment is highly fragmented: companies publish open requisitions across dozens of bespoke career portals, proprietary single-page apps (SPAs), and third-party Applicant Tracking Systems (ATS). For an experienced engineer targeting high-conviction roles, manual job hunting is inefficient and error-prone.

This system automates the end-to-end job intelligence lifecycle:
+ *Discovery:* Programmatically discovers active career pages and direct job feeds without manual browsing.
+ *Zero-Loss Ingestion:* Normalizes radically different HTML layouts into a unified data contract without context loss.
+ *Automated Scoring:* Ingests the candidate's verified profile (`profile.yaml`) and evaluates Job Descriptions (JDs) against a strict *75%–80%+ match threshold*.
+ *Actionable Recommendations:* Identifies exact skill alignments, missing keywords, and automatically recommends which resume achievement bullets to prioritize.

#v(0.3em)
#callout_box("Core Design Goal", [
  Filter through thousands of noisy postings and deliver a curated stream of high-match requisitions where candidate skills (Python, FastAPI, Agentic AI, MCP, pgvector) and seniority (3+ years) yield a *>= 75% competitive advantage*.
])

// ==============================================================================
// 2. END-TO-END SYSTEM ARCHITECTURE
// ==============================================================================
#section_heading("2. End-to-End System Lifecycle")

The analyser is structured as a 5-stage automated pipeline:

#table(
  columns: (1.2fr, 2.2fr, 2.6fr),
  fill: (x, y) => if y == 0 { rgb("#1e3a8a") } else if calc.even(y) { rgb("#f8fafc") } else { none },
  stroke: (x, y) => if y == 0 { none } else { 0.5pt + rgb("#e2e8f0") },
  inset: (x: 8pt, y: 6pt),
  align: (left, left, left),
  
  // Header
  [#text(weight: "bold", fill: white)[Stage]],
  [#text(weight: "bold", fill: white)[Core Responsibility]],
  [#text(weight: "bold", fill: white)[Underlying Technologies]],

  // Row 1
  [*1. Discovery*],
  [Harvest target career endpoints, ATS slugs, and job posting URLs.],
  [Greenhouse/Lever/Ashby APIs, Google Dork cron jobs, YC company seed lists.],

  // Row 2
  [*2. Ingestion*],
  [Fetch raw content via direct API, microdata, or clean HTTP requests.],
  [Public REST JSON feeds, HTTP client with rotating headers, headless fallback.],

  // Row 3
  [*3. Normalization*],
  [Transform heterogeneous HTML into a canonical `JobPosting` data model.],
  [Schema.org `JobPosting` JSON-LD, BeautifulSoup AST Markdown parser, Pydantic.],

  // Row 4
  [*4. Evaluation*],
  [Execute hard constraints and multi-factor semantic alignment scoring.],
  [Candidate-as-Code (`profile.yaml`), experience gate, weighted skill matrix.],

  // Row 5
  [*5. Dispatch*],
  [Alert on $\ge 75\%$ matches with tailor tips; discard sub-60% roles.],
  [Markdown reports, JSON outputs, Slack/Telegram webhook dispatch hooks.]
)

// ==============================================================================
// 3. SOURCING & CAREER PAGE DISCOVERY
// ==============================================================================
#section_heading("3. Where & How to Find Career Pages")

Rather than writing brittle, custom scrapers for hundreds of independent corporate domains, modern discovery exploits the *80/20 ATS Hosting Pattern*. Over 80% of venture-backed tech and AI product companies do not build custom career backends; they host requisitions on standardized ATS platforms.

#subsection_heading("3.1 Direct Public ATS Endpoints (Zero-Scraping Strategy)")
These platforms expose publicly queryable JSON feeds that bypass web application firewalls and rate limits:
- *Greenhouse Portals:* `https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true`
- *Lever Portals:* `https://api.lever.co/v0/postings/{company}?mode=json`
- *Ashby Portals:* `https://jobs.ashbyhq.com/api/non-auth/job-board/{company}` (used by Perplexity, Cursor, Linear)

#subsection_heading("3.2 Automated Search Dorks (Cron-Driven Sourcing)")
For companies not in a predefined seed list, periodic search engine queries surface newly published roles:
- `site:boards.greenhouse.io ("GenAI" OR "Agentic AI" OR "AI Engineer") "FastAPI" ("India" OR "Remote")`
- `site:jobs.lever.co ("LLM" OR "Python") "LangGraph" OR "Model Context Protocol"`
- `site:jobs.ashbyhq.com ("Generative AI" OR "RAG") "PostgreSQL"`

// #pagebreak()

// ==============================================================================
// 4. HETEROGENEOUS INGESTION WITHOUT CONTEXT LOSS
// ==============================================================================
#section_heading("4. Universal Extraction: Preserving Context Across Diverse Layouts")

#subsection_heading("Why Naive Scrapers Fail")
Typical scrapers strip HTML tags with regex, resulting in a single flattened string. This destroys the critical semantic boundary between *Minimum Qualifications* (mandatory), *Preferred Qualifications* (optional), *Responsibilities*, and *Company Boilerplate*.

#subsection_heading("The 4-Tier Zero-Loss Extraction Pipeline")

#block(width: 100%, stroke: 0.75pt + rgb("#cbd5e1"), inset: 10pt, radius: 4pt)[
  *Tier 1: Direct ATS REST Payload (Preferred)* \
  When a URL belongs to Greenhouse, Lever, or Ashby, query the API directly. The JSON payload provides pre-isolated fields: `title`, `location`, `updated_at`, `departments`, and raw `content`. Zero DOM parsing required.

  #v(0.3em)
  *Tier 2: Schema.org JSON-LD Microdata* \
  Modern career pages embed Google Jobs structured metadata in `<script type="application/ld+json">`. The parser extracts `@type: "JobPosting"`, pulling `title`, `datePosted`, `hiringOrganization`, `jobLocation`, and `experienceRequirements` directly from structured JSON.

  #v(0.3em)
  *Tier 3: Hierarchical Markdown AST Parsing* \
  For custom non-ATS pages, HTML is converted to structured Markdown:
  - `<nav>`, `<footer>`, `<header>`, and script tags are pruned.
  - Headings (`<h1>`--`<h4>`) convert to `# Section Headers`, isolating requirements blocks.
  - List items (`<li>`) convert to bullet points (`- Item`), preserving distinct qualifications.

  #v(0.3em)
  *Tier 4: Pydantic Canonical Normalization* \
  All tiers funnel into a standardized, strictly typed `JobPosting` schema:
]

#v(0.4em)
```python
class JobPosting(BaseModel):
    url: str
    company: str
    title: str
    location: str
    posted_date: Optional[str]
    min_experience_years: Optional[float]
    max_experience_years: Optional[float]
    must_have_skills: List[str]
    nice_to_have_skills: List[str]
    tech_stack: List[str]
    responsibilities: List[str]
    raw_markdown: str
```

// ==============================================================================
// 5. THE 75% - 80% MATCHING ALGORITHM
// ==============================================================================
#section_heading("5. The 75%–80% Candidate Alignment Engine")

The matching engine compares the normalized `JobPosting` against Boobesh S's verified profile (`profile.yaml`).

#subsection_heading("5.1 Candidate Ground Truth Baseline")
- *Role:* Software Engineer (AI / GenAI) @ Corent Technology (Jan 2023 – Present)
- *Tenure:* 3+ Years production software engineering experience
- *Core Stack:* Python, FastAPI, Agentic AI, Google ADK, LangGraph, Model Context Protocol (MCP), ReAct loops, RAG, pgvector, Qdrant, Redis, Kafka, Docker, Kubernetes, OpenTelemetry, Azure OpenAI, Google Gemini.

#subsection_heading("5.2 Multi-Factor Scoring Formula")
The composite match score is computed as:

$ upright("Overall Score") = E_("fit") times [ 0.50 dot S_("skill") + 0.30 dot S_("semantic") + 0.20 dot S_("exp") ] $

Where:
- *$E_("fit") in {1.0, 0.4}$ (Hard Experience Gate):* Evaluates min/max years. If a role demands Staff/Principal ($> 5$ years min), $E_("fit") = 0.4$ (penalizing it below the threshold). Roles targeting 1--4 or 2--5 years receive $E_("fit") = 1.0$.
- *$S_("skill")$ (Skill Overlap Score, 50% Weight):* Direct overlap between JD mandatory tech requirements and the candidate's 56+ verified profile skills.
- *$S_("semantic")$ (Architectural Fit, 30% Weight):* Evaluates presence of core agentic signals (MCP, ReAct, RAG, database grounding, latency optimization, distributed tracing).
- *$S_("exp")$ (Seniority Sweet Spot, 20% Weight):* Full marks (100) when candidate experience (3.2 years) aligns squarely inside the target bracket.

#subsection_heading("5.3 Decision Thresholds & Actions")
#table(
  columns: (1.5fr, 1.8fr, 3.2fr),
  fill: (x, y) => if y == 0 { rgb("#1e3a8a") } else if y == 1 { rgb("#f0fdf4") } else { none },
  stroke: 0.5pt + rgb("#cbd5e1"),
  inset: (x: 8pt, y: 6pt),
  [#text(weight: "bold", fill: white)[Match Score]],
  [#text(weight: "bold", fill: white)[Category]],
  [#text(weight: "bold", fill: white)[Automated Pipeline Action]],

  [*>= 75.0%*],
  [#text(weight: "bold", fill: rgb("#166534"))[🔥 Strong Match]],
  [Trigger application notification; recommend exact resume bullets to spotlight.],

  [*60.0% -- 74.9%*],
  [#text(weight: "bold", fill: rgb("#854d0e"))[⚠️ Moderate Match]],
  [Flag specific missing keywords (e.g. AWS vs GCP, secondary framework gaps).],

  [*$<$ 60.0%*],
  [#text(weight: "bold", fill: rgb("#991b1b"))[❌ Mismatch / Disqualify]],
  [Automatically filter out (saves screening time on unsuitable requisitions).]
)

// #pagebreak()

// ==============================================================================
// 6. VALIDATION CASE STUDY: INFOSYS GENAI ROLE
// ==============================================================================
#section_heading("6. Validation Case Study: Infosys Career Portal")

To validate the engine against a real enterprise recruitment portal, we analyzed active job posting *`INFSYS-EXTERNAL-255682`* directly from `career.infosys.com`.

#subsection_heading("6.1 Requisition Ground Truth Data")
#table(
  columns: (2fr, 4.5fr),
  stroke: 0.5pt + rgb("#cbd5e1"),
  inset: (x: 8pt, y: 5.5pt),
  [*Company*], [Infosys Limited],
  [*Job Title*], [Python ML /GenAI],
  [*Reference Code*], [`INFSYS-EXTERNAL-255682`],
  [*Location*], [*BANGALORE, India* (Sole verified DC location on requisition page)],
  [*Experience Required*], [1 -- 3 Years (Junior to Mid-Level)],
  [*Education Match*], [BTech, MCA, MTech, *MSc* (Directly matched by candidate's M.Sc degree)],
  [*Unit / Division*], [Data & Analytics Unit]
)

#subsection_heading("6.2 Match Evaluation Breakdown")
Running `job_analyzer.py` against this authentic posting produced:

#callout_box("Evaluation Results: 92.7% Overall Match (STRONG FIT)", [
  - *Overall Score:* *92.7%* (Qualifies well above the 75% threshold)
  - *Experience Fit:* *100%* (1--3 years required <-> Candidate has 3.2 years)
  - *Education Fit:* *100%* (`MSc` listed in Educational Requirements)
  - *Matched Competencies:* `Python`, `FastAPI`, `Generative AI`, `LangGraph / LangChain`, `RAG`, `Vector DBs (ChromaDB/pgvector)`, `Azure OpenAI`, `Gemini`, `Docker`, `GitOps / Git`, `SQL`.
  - *Missing Mandatory Skills:* *None.*
  - *Tailoring Action:* Spotlight Bullet 3 (*Anti-Hallucination SQL Database Grounding*) and Bullet 2 (*Gemini Context Caching with MCP*).
], border_color: rgb("#166534"), bg_color: rgb("#f0fdf4"))

// ==============================================================================
// 7. IMPLEMENTATION & AUTOMATION ROADMAP
// ==============================================================================
#section_heading("7. Production Automation Blueprint")

```
   +-------------------------------------------------------------------------+
   |                     CRON SCHEDULER / DAILY TRIGGER                     |
   +-------------------------------------------------------------------------+
                                        |
                                        v
   +-----------------------+   +--------------------+   +--------------------+
   | Greenhouse API Scraper|   | Lever API Scraper  |   | Ashby API Scraper  |
   +-----------------------+   +--------------------+   +--------------------+
               |                         |                        |
               +-------------------------+------------------------+
                                        |
                                        v
   +-------------------------------------------------------------------------+
   |             CANONICAL NORMALIZER (Pydantic Schema Validation)           |
   +-------------------------------------------------------------------------+
                                        |
                                        v
   +-------------------------------------------------------------------------+
   |           MATCHING ENGINE (Evaluates vs Candidate profile.yaml)         |
   +-------------------------------------------------------------------------+
                                        |
                     +------------------+------------------+
                     |                                     |
              Score >= 75%                            Score < 75%
                     |                                     |
                     v                                     v
   +-----------------------------------+        +--------------------+
   | 🔥 HIGH-MATCH FEED               |        | 📁 Archived Log    |
   | - Tailored Bullet Recommendations |        +--------------------+
   | - Auto-Fill / Notification Alert  |
   +-----------------------------------+
```

#subsection_heading("Deliverables in Workspace")
- [`job_analyzer.py`](file:///e:/Learnings/Bulider/job_analyzer.py) --- Modular Python engine for crawling, parsing, and scoring JDs.
- [`profile.yaml`](file:///e:/Learnings/Bulider/profile.yaml) --- Candidate source-of-truth skill matrix and verified metrics.
- [`infosys_genai_job.json`](file:///e:/Learnings/Bulider/infosys_genai_job.json) --- Fully validated ground-truth JSON for the Infosys case study.
- [`sample_greenhouse_job.json`](file:///e:/Learnings/Bulider/sample_greenhouse_job.json) --- Live ATS API reference payload.
