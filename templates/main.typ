// ==============================================================================
// Boobesh S - AI Engineer (Typst)
// Styled to exactly match 'Boobesh - AI Engineer_old.pdf'
// ==============================================================================

#set page(
  paper: "a4",
  margin: (top: 24pt, bottom: 24pt, left: 28pt, right: 28pt),
  header: none,
  footer: none
)

#set text(
  font: "Times New Roman",
  size: 10pt,
  fill: rgb("#25303d"),
  lang: "en",
  spacing: 105%
)

#set par(justify: true, leading: 0.53em)

// Centered Section Heading with 0.75pt horizontal line wings on both sides
#let section_heading(title) = [
  #v(0.70em)
  #grid(
    columns: (1fr, auto, 1fr),
    align: (center + horizon),
    gutter: 0.8em,
    line(length: 100%, stroke: 0.75pt + rgb("#25303d")),
    text(weight: "bold", size: 13.5pt, fill: rgb("#25303d"))[#title],
    line(length: 100%, stroke: 0.75pt + rgb("#25303d"))
  )
  #v(0.45em)
]

// Bullet Item matching old resume style (vector square bullet optically centered with first line)
#let bullet_item(body) = block(width: 100%, inset: (left: 1.25em, bottom: 0.28em))[
  #place(left, dx: -1.25em, dy: 0.20em)[#box(width: 3.2pt, height: 3.2pt, fill: rgb("#25303d"))]
  #body
]

// Page 2 Bullet Item with slightly more vertical breathing room
#let bullet_item_p2(body) = block(width: 100%, inset: (left: 1.25em, bottom: 0.36em))[
  #place(left, dx: -1.25em, dy: 0.20em)[#box(width: 3.2pt, height: 3.2pt, fill: rgb("#25303d"))]
  #body
]

// Skill Item: Clean inline layout WITHOUT bullets (ATS-friendly, no bullet characters)
#let skill_item(category, items) = block(width: 100%, inset: (bottom: 0.25em))[
  #text(weight: "bold", size: 10.2pt, fill: rgb("#25303d"))[#category:] #h(0.35em) #text(size: 10pt)[#items]
]


// ----------------- HEADER -----------------
#align(center)[
  #text(weight: "bold", size: 25pt, fill: rgb("#25303d"))[BOOBESH S] \
  #v(0.12em)
  #text(weight: "bold", size: 13.5pt, fill: rgb("#25303d"))[AI ENGINEER] \
  #v(0.32em)
  #text(size: 9.0pt, fill: rgb("#25303d"))[
    Chennai, India #h(0.35em) | #h(0.35em)
    #link("tel:+91 6381659585")[+91 6381659585] #h(0.35em) | #h(0.35em)
    #link("mailto:boobesh2509@gmail.com")[boobesh2509\@gmail.com] #h(0.35em) | #h(0.35em)
    #link("https://linkedin.com/in/boobesh-s-8a8387201")[https://linkedin.com/in/boobesh-s-8a8387201] #h(0.35em) | #h(0.35em)
    #link("https://github.com/Boobesh25")[https://github.com/Boobesh25]
  ]
]


// ----------------- PROFILE SUMMARY -----------------
#section_heading("Profile Summary")
#text(size: 10.2pt)[
AI-focused Software Engineer with 3+ years of experience building production-grade AI applications, RAG systems, and scalable backend architectures. Experienced in LLM integrations, agentic AI workflows, Kafka-based async processing, and real-time streaming systems using FastAPI, PostgreSQL, and cloud AI services. Strong hands-on experience to solving production AI challenges including retrieval accuracy, scalability, latency optimization, and AI workflow orchestration.
]


// ----------------- TECHNICAL SKILLS -----------------
#section_heading("Technical Skills")
#skill_item("Programming & Backend", "Python, FastAPI, REST APIs, WebSockets, SQLAlchemy, Pandas, Gunicorn, Nginx")
#skill_item("AI / GenAI", "Agentic AI (Google ADK, LangGraph), Model Context Protocol (MCP - Client & Server Integration), ReAct Decision Loops, RAG, Vector Search, Embeddings, Semantic Search, Cross-Encoders, Prompt Engineering, Multi-Provider LLM Routing")
#skill_item("Databases", "PostgreSQL (pgvector), MySQL, Qdrant, ChromaDB")
#skill_item("Messaging & Streaming", "Kafka, Redis, Server-Sent Events (SSE)")
#skill_item("Cloud & AI Platforms", "Azure OpenAI, AWS Bedrock, Vertex AI, Gemini AI, Google Cloud Run")
#skill_item("Infrastructure & Observability", "Docker, Kubernetes (HPA & KEDA Autoscaling), OpenTelemetry, OpenLIT, Fluent Bit, Loki, Grafana, LangSmith, ArgoCD, Linux")
#skill_item("Software Engineering Fundamentals", "Object-Oriented Design & Classic Design Patterns (Factory, Strategy, Observer, Singleton, Adapter, Builder), Distributed Tracing & Reliability Engineering, API Contract Design & Schema Validation (Pydantic)")


// ----------------- PROFESSIONAL EXPERIENCE -----------------
#section_heading("Professional Experience")

#block(width: 100%, inset: (bottom: 0.2em))[
  #grid(
    columns: (1fr, auto),
    align: (left, right),
    [#text(weight: "bold", size: 11.5pt, fill: rgb("#25303d"))[Software Engineer (AI / GenAI) - Corent Technology]],
    [#text(weight: "bold", size: 10.5pt, fill: rgb("#25303d"))[2023 - Present (3+ Years)]]
  )
  #v(-0.35em)
  #grid(
    columns: (1fr, auto),
    align: (left, right),
    [#text(style: "italic", size: 10pt, fill: rgb("#4b5563"))[Python Backend & AI Engineering Team]],
    [#text(size: 10pt, fill: rgb("#4b5563"))[Chennai, India]]
  )
]

#v(0.1em)
#block(width: 100%, inset: (left: 0.5em, bottom: 0.35em))[
  #text(style: "italic", size: 9.8pt, fill: rgb("#374151"))[Worked as part of the founding AI/ML engineering team, developing enterprise-grade GenAI applications, AI workflow orchestration systems, and cloud intelligence platforms.]
]

#bullet_item[*Multi-Agent Orchestration:* Architected a 2-tier agent orchestration system with Google ADK; deployed a deterministic root router to classify intent and delegate execution to specialized MCP ReAct agents, eliminating discovery hops and ensuring predictable routing.]

#bullet_item[*Context Caching:* Implemented Gemini Context Caching across 78+ MCP tool schemas and static system instructions, eliminating redundant prompt token ingestion to slash recurring input token costs by *75%* and reduce multi-turn agent response latency by *\~60%*.]

#bullet_item[*Anti-Hallucination Database Grounding:* Built a deterministic schema-grounding pipeline exposing relational schemas as MCP resources; constrained LLM outputs to validated, read-only SQL queries to guarantee *100% factual fidelity against live records*.]

#bullet_item[*Context-Window Payload Optimization:* Built an adaptive response-downsampling middleware for high-volume cloud telemetry payloads (*200 KB to 2 MB*), preserving context-window token budgets and eliminating token limit errors.]

#bullet_item[*Automated Data Analytics Pipeline:* Engineered an automated analytics pipeline generating dynamic Pandas aggregation and transformation logic from multi-cloud telemetry, with sandboxed runtime execution, syntax validation, and structured tabular fallbacks.]

#bullet_item[*Bounded Session Memory & HITL:* Designed a bounded-memory session service with Human-In-The-Loop (HITL) resolution, restricting history to recent user turns to enforce flat token economics while preserving pending clarification states for follow-ups.]

#bullet_item[*Multi-Provider LLM Routing:* Engineered a vendor-agnostic LLM abstraction dynamically routing between Google Gemini and AWS Bedrock (Nova), steering lightweight models to summarization and higher-tier models to multi-hop execution to minimize inference costs.]


#pagebreak()

#bullet_item_p2[*OpenTelemetry Distributed Tracing:* Instrumented end-to-end distributed tracing using OpenTelemetry and a custom PostgreSQL span exporter, capturing per-phase latency, model identifiers, and granular token consumption across all agent execution stages.]

#bullet_item_p2[*High-Performance Backend Engineering:* Architected asynchronous FastAPI microservices with PostgreSQL connection pooling behind Nginx; deployed KEDA autoscalers with Kafka consumers for resilient, event-driven background task processing.]

#bullet_item_p2[*Multi-Cloud Cost & Migration Intelligence:* Engineered multi-cloud cost intelligence and sizing workflows across AWS, Azure, and GCP (\~15 regions), delivering automated rightsizing models that identified *20-30% projected compute cost savings* for enterprise migrations.]


#section_heading("Personal Projects & POCs")

#block(width: 100%, inset: (bottom: 0.25em))[
  #text(weight: "bold", size: 10.8pt, fill: rgb("#25303d"))[GenAI Multi-Agent Chatbot Platform] \
  #v(-0.35em)
  #text(style: "italic", size: 9.2pt, fill: rgb("#4b5563"))[LangGraph, FastAPI, Google Gemini, Qdrant, Redis, PostgreSQL, Streamlit, LangSmith, Docker] \
  #v(-0.30em)
  #text(size: 8.8pt)[#link("https://github.com/Boobesh25/Projects")[https://github.com/Boobesh25/Projects] #h(0.5em) | #h(0.5em) #link("https://projects-bu8jtjbtyqe7otklpukvoq.streamlit.app/")[https://projects-bu8jtjbtyqe7otklpukvoq.streamlit.app/]]
]
#bullet_item_p2[Built an autonomous ReAct agent chatbot using LangGraph and Google Gemini that dynamically routes queries between SQL database tools, Qdrant document vector search, and computational tools without hardcoded rules.]
#bullet_item_p2[Implemented semantic chunking with adaptive similarity thresholds to split documents along topical boundaries, isolating collections per user in Qdrant.]
#bullet_item_p2[Integrated Redis caching with incremental re-embedding, slashing external LLM embedding API calls by *up to 80%* on document updates.]
#bullet_item_p2[Secured endpoints via Google OAuth 2.0 and JWT authentication, streaming real-time agent execution events over WebSockets with LangSmith observability.]
#v(0.5em)

#block(width: 100%, inset: (bottom: 0.25em))[
  #text(weight: "bold", size: 10.8pt, fill: rgb("#25303d"))[Production FastAPI on GKE with ArgoCD GitOps] \
  #v(-0.35em)
  #text(style: "italic", size: 9.2pt, fill: rgb("#4b5563"))[Google Kubernetes Engine (GKE), ArgoCD, Docker, FastAPI, HPA, GitOps] \
  #v(-0.30em)
  #text(size: 8.8pt)[#link("https://github.com/Boobesh25/fastapi-demo-cicd")[https://github.com/Boobesh25/fastapi-demo-cicd]]
]
#bullet_item_p2[Containerized a high-concurrency FastAPI microservice and deployed a 3-replica architecture on Google Kubernetes Engine with automated health checks.]
#bullet_item_p2[Configured Horizontal Pod Autoscaler (HPA) policies scaling pods dynamically under load, validated using an automated synthetic stress-testing endpoint.]
#bullet_item_p2[Established declarative GitOps delivery using ArgoCD with automated repository synchronization, pruning, and self-healing rollouts.]


#section_heading("Education")

#block(width: 100%, inset: (bottom: 0.42em))[
  #grid(
    columns: (1fr, auto),
    align: (left, right),
    [#text(weight: "bold", size: 10.2pt, fill: rgb("#25303d"))[Master of Science (M.Sc) in Cyber Forensic and Information Security (Correspondence)]],
    [#text(weight: "bold", size: 9.8pt, fill: rgb("#25303d"))[2022 - 2024]]
  )
  #v(-0.35em)
  #grid(
    columns: (1fr, auto),
    align: (left, right),
    [#text(style: "italic", size: 9.5pt, fill: rgb("#4b5563"))[University of Madras]],
    [#text(size: 9.5pt, fill: rgb("#4b5563"))[Chennai, India]]
  )
]

#block(width: 100%, inset: (bottom: 0.42em))[
  #grid(
    columns: (1fr, auto),
    align: (left, right),
    [#text(weight: "bold", size: 10.2pt, fill: rgb("#25303d"))[Bachelor of Science (B.Sc) in Computer Science]],
    [#text(weight: "bold", size: 9.8pt, fill: rgb("#25303d"))[2019 - 2022]]
  )
  #v(-0.35em)
  #grid(
    columns: (1fr, auto),
    align: (left, right),
    [#text(style: "italic", size: 9.5pt, fill: rgb("#4b5563"))[Mar Gregorios College of Arts & Science]],
    [#text(size: 9.5pt, fill: rgb("#4b5563"))[Chennai, India]]
  )
]
