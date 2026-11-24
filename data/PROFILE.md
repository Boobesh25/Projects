# Boobesh S
**GenAI Engineer** | Agentic AI & Scalable Python Systems  
Chennai, India | +91 6381659585 | boobesh2509@gmail.com | linkedin.com/in/boobesh-s-8a8387201 | github.com/Boobesh25

---

## Professional Summary
AI Engineer with 3+ years of experience building production-grade AI applications, agentic workflows, and scalable backend architectures. Experienced in multi-agent orchestration, tool integration via Model Context Protocol (MCP), and real-time streaming APIs using FastAPI and PostgreSQL. Proven track record in solving real-world AI challenges, including latency reduction, retrieval accuracy, token limits, and reliable database grounding across multi-cloud environments.

---

## Core Technical Skills

* **Generative AI & Agentic Systems:** Agentic AI (Google ADK, LangGraph), Model Context Protocol (MCP Client & Server Integration), ReAct Decision Loops, Multi-Agent Delegation & Tool Routing, Retrieval-Augmented Generation (RAG), Vector Databases (PostgreSQL with pgvector, Qdrant), Embeddings & Cross-Encoder Reranking, Prompt Engineering, Structured Output Guardrails, Multi-Provider LLM Abstraction (Google Gemini, AWS Bedrock Nova, Azure OpenAI), LLM Code Generation.
* **Backend & Data Engineering:** Python 3 (asyncio, asyncpg), FastAPI, REST & Server-Sent Events (SSE) Streaming, WebSockets, PostgreSQL, SQLAlchemy, Connection Pooling, Data Processing & Analytics (Pandas, NumPy), Caching & Asynchronous Messaging (Redis, Kafka), MySQL.
* **LLMOps, Infrastructure & Observability:** OpenTelemetry & OpenLIT (LLM Tracing & Token Observability), LangSmith Tracing, Docker (docker-compose), Kubernetes (Deployments, HPA & KEDA Autoscaling), GitOps & Deployment Automation (ArgoCD), Nginx, Gunicorn, Linux, Cloud Services (GCP Cloud Run, AWS Bedrock).
* **Engineering Fundamentals:** Object-Oriented Design & Classic Design Patterns (Factory, Strategy, Observer, Singleton, Adapter, Builder), Distributed Tracing, API Contract Design, Schema Validation (Pydantic), Reliability Engineering.

---

## Professional Experience

### **Software Engineer (AI / GenAI)** - **Corent Technology**
*Chennai, India | January 2023 – Present*  
*Python Backend & AI Engineering Team*  
*Role: Core Engineer Driving Architecture & Implementation of Enterprise Multi-Cloud Agentic AI Platform*

* **Multi-Agent Orchestration:** Architected a 2-tier agent orchestration system with Google ADK; deployed a deterministic root router to classify intent and delegate execution to specialized MCP ReAct agents, eliminating discovery hops and ensuring predictable routing.
* **Context Caching & Cost Optimization:** Implemented Gemini Context Caching across 78+ MCP tool schemas and static system instructions, eliminating redundant prompt token ingestion to slash recurring input token costs by **75%** and reduce multi-turn agent response latency by **~60%**.
* **Anti-Hallucination Data Grounding:** Built a deterministic schema-grounding pipeline exposing relational schemas as MCP resources; constrained LLM outputs to validated, read-only SQL queries to guarantee **100% factual fidelity against live records**.
* **Context-Window Payload Optimization:** Built an adaptive response-downsampling middleware for high-volume cloud telemetry payloads (**200 KB to 2 MB**), preserving context-window token budgets and eliminating token limit errors.
* **Automated Data Analytics Pipeline:** Engineered an automated analytics pipeline generating dynamic Pandas aggregation and transformation logic from multi-cloud telemetry, with sandboxed runtime execution, syntax validation, and structured tabular fallbacks.
* **Bounded Session Memory & HITL:** Designed a bounded-memory session service with Human-In-The-Loop (HITL) resolution, restricting history to recent user turns to enforce flat token economics while preserving pending clarification states for follow-ups.
* **Multi-Provider LLM Routing:** Engineered a vendor-agnostic LLM abstraction dynamically routing between Google Gemini and AWS Bedrock (Nova), steering lightweight models to summarization and higher-tier models to multi-hop execution to minimize inference costs.
* **OpenTelemetry GenAI Observability:** Instrumented end-to-end distributed tracing using OpenTelemetry and a custom PostgreSQL span exporter, capturing per-phase latency, model identifiers, and granular token consumption across all agent execution stages.
* **High-Performance Backend Architecture:** Architected asynchronous FastAPI microservices with PostgreSQL connection pooling behind Nginx; deployed KEDA autoscalers with Kafka consumers for resilient, event-driven background task processing.
* **Multi-Cloud Cost Intelligence:** Engineered multi-cloud cost intelligence and sizing workflows across AWS, Azure, and GCP (~15 regions), delivering automated rightsizing models that identified **20-30% projected compute cost savings** for enterprise migrations.

---

## Personal Projects & POCs

### **1. GenAI Multi-Agent Chatbot Platform**
*LangGraph, FastAPI, Google Gemini, Qdrant, Redis, PostgreSQL, Streamlit, LangSmith, Docker*  
[https://github.com/Boobesh25/Projects](https://github.com/Boobesh25/Projects) | [https://projects-bu8jtjbtyqe7otklpukvoq.streamlit.app/](https://projects-bu8jtjbtyqe7otklpukvoq.streamlit.app/)
* Built an autonomous ReAct agent chatbot using LangGraph and Google Gemini that dynamically routes queries between SQL database tools, Qdrant document vector search, and computational tools without hardcoded rules.
* Implemented semantic chunking with adaptive similarity thresholds to split documents along topical boundaries, isolating collections per user in Qdrant.
* Integrated Redis caching with incremental re-embedding, slashing external LLM embedding API calls by **up to 80%** on document updates.
* Secured endpoints via Google OAuth 2.0 and JWT authentication, streaming real-time agent execution events over WebSockets with LangSmith observability.

### **2. Production FastAPI on GKE with ArgoCD GitOps**
*Google Kubernetes Engine (GKE), ArgoCD, Docker, FastAPI, HPA, GitOps*  
[https://github.com/Boobesh25/fastapi-demo-cicd](https://github.com/Boobesh25/fastapi-demo-cicd)
* Containerized a high-concurrency FastAPI microservice and deployed a 3-replica architecture on Google Kubernetes Engine with automated health checks.
* Configured Horizontal Pod Autoscaler (HPA) policies scaling pods dynamically under load, validated using an automated synthetic stress-testing endpoint.
* Established declarative GitOps delivery using ArgoCD with automated repository synchronization, pruning, and self-healing rollouts.

---

## Education

* **Master of Science (M.Sc) in Cyber Forensic and Information Security (Correspondence)**  
  *University of Madras | Chennai, India (August 2022 – May 2024)*  
  Specialization in digital forensics, network security protocols, information privacy, and vulnerability analysis.

* **Bachelor of Science (B.Sc) in Computer Science**  
  *Mar Gregorios College of Arts & Science | Chennai, India (August 2019 – May 2022)*  
  Graduated with foundational expertise in algorithms, relational database management, and object-oriented software development.

---

## Ground Truth Invariants (For Tailoring Agents)
1. **Never fabricate company names, dates, or titles.**
2. **Never fabricate customer or revenue numbers; anchor on technical scale (78+ tools across 3 clouds and ~15 global regions).**
3. **Preserve verified quantitative metrics exactly:** `78+ tools`, `~60% latency reduction`, `<10s`, `200 KB to 2 MB payloads`, `up to 80% embedding cost savings`.
4. **Frame production work vs personal projects truthfully:** Corent Technology represents production Google ADK, custom MCP tooling, FastAPI, and PostgreSQL; GitOps with ArgoCD and GKE are verified hands-on projects.
