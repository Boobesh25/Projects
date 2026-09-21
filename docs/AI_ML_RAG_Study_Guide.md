# AI/ML/RAG Complete Study Guide
## Interview Preparation & Development Reference

*Based on real-world project experience: RAG system with hybrid search, hierarchical chunking, parent-child retrieval, MCP integration, and LangGraph agents.*

---

## Table of Contents

1. AI vs ML vs DL
2. Machine Learning Types & Algorithms
3. ML Evaluation Metrics
4. LLMs & Transformer Architecture
5. RAG vs Fine-Tuning
6. Retrieval: Chunking Strategies
7. Retrieval Validation & Eval Metrics
8. Generation: Model Parameters
9. LangChain & LangGraph
10. Vector Databases
11. Caching & Prompt Versioning
12. Cloud & Deployment
13. Docker & Kubernetes

---

## 1. AI vs ML vs DL

### Hierarchy

```
Artificial Intelligence (AI)
  └── Machine Learning (ML)
        └── Deep Learning (DL)
              └── LLMs (Large Language Models)
```

### Comparison

| Aspect | AI | ML | DL |
|--------|----|----|-----|
| Definition | Machines mimicking human intelligence | Algorithms learning from data without explicit programming | Neural networks with many layers learning representations |
| Data needed | Rules + data | Moderate data | Massive data |
| Feature engineering | Manual | Manual or semi-auto | Automatic |
| Hardware | CPU | CPU/GPU | GPU/TPU mandatory |
| Examples | Rule-based chatbots, expert systems | Spam detection, recommendations | Image recognition, NLP, LLMs |

### Interview Answer:
> "AI is the broad field of making machines intelligent. ML is a subset where machines learn patterns from data. DL is a subset of ML using neural networks with multiple layers. In our RAG project, we use DL-based embeddings (Gemini) to represent text as vectors, and an LLM (also DL) to generate answers."

---

## 2. Machine Learning Types & Algorithms

### 2.1 Supervised Learning
**What:** Model learns from labeled data (input → known output).

| Algorithm | Use Case | Key Parameters |
|-----------|----------|----------------|
| Linear Regression | Price prediction | learning_rate, regularization (L1/L2) |
| Logistic Regression | Binary classification | C (regularization strength), solver |
| Decision Tree | Classification/Regression | max_depth, min_samples_split |
| Random Forest | Ensemble classification | n_estimators, max_depth, max_features |
| SVM | Classification with margins | C (penalty), kernel (linear/rbf), gamma |
| XGBoost | Tabular data competitions | learning_rate, n_estimators, max_depth |

```python
# Random Forest Example
from sklearn.ensemble import RandomForestClassifier

model = RandomForestClassifier(
    n_estimators=100,    # More trees = less overfitting, slower
    max_depth=10,        # Deeper = more complex, risk of overfitting
    min_samples_split=5, # Higher = simpler tree, less overfitting
    max_features='sqrt', # Features per split: sqrt, log2, or float
)
model.fit(X_train, y_train)
predictions = model.predict(X_test)
```

**Parameter Impact:**
- `n_estimators↑` → better accuracy, diminishing returns after ~100-200
- `max_depth↑` → captures complex patterns, risks overfitting
- `min_samples_split↑` → simpler model, prevents overfitting
- `learning_rate↓` (XGBoost) → slower convergence but better generalization

### 2.2 Unsupervised Learning
**What:** Model finds patterns in unlabeled data.

| Algorithm | Use Case | Key Parameters |
|-----------|----------|----------------|
| K-Means | Customer segmentation | n_clusters (k), init method |
| DBSCAN | Anomaly detection | eps (distance), min_samples |
| PCA | Dimensionality reduction | n_components |
| Hierarchical Clustering | Taxonomy building | linkage (ward/complete/average) |

```python
# K-Means Example
from sklearn.cluster import KMeans

model = KMeans(
    n_clusters=5,     # Number of groups to find
    init='k-means++', # Smart initialization
    n_init=10,        # Run 10 times, pick best
    max_iter=300,     # Maximum iterations per run
)
clusters = model.fit_predict(X)
```

**Parameter Impact:**
- `n_clusters` → too few = underfitting, too many = overfitting (use elbow method)
- `eps` (DBSCAN) → smaller = more noise points, larger = fewer clusters

### 2.3 Reinforcement Learning
**What:** Agent learns by trial and error, receiving rewards/penalties.

| Algorithm | Use Case |
|-----------|----------|
| Q-Learning | Game playing |
| PPO | Robotics, RLHF for LLMs |
| DQN | Complex decision making |

### 2.4 Semi-Supervised Learning
**What:** Small labeled data + large unlabeled data. Used when labeling is expensive.

---

## 3. ML Evaluation Metrics

### 3.1 Classification Metrics

**Confusion Matrix:**
```
                Predicted
              Pos    Neg
Actual Pos  [ TP  |  FN ]
Actual Neg  [ FP  |  TN ]
```

| Metric | Formula | When to Use |
|--------|---------|-------------|
| **Accuracy** | (TP+TN) / Total | Balanced datasets |
| **Precision** | TP / (TP+FP) | When FP is costly (spam detection) |
| **Recall** | TP / (TP+FN) | When FN is costly (cancer detection) |
| **F1 Score** | 2×(P×R)/(P+R) | Imbalanced datasets, need balance |
| **AUC-ROC** | Area under ROC curve | Binary classification threshold tuning |
| **Specificity** | TN / (TN+FP) | When correctly identifying negatives matters |

```python
from sklearn.metrics import classification_report, confusion_matrix

print(classification_report(y_true, y_pred))
# Output:
#               precision    recall  f1-score   support
#     class 0       0.85      0.90      0.87       100
#     class 1       0.80      0.72      0.76        50
```

### 3.2 Regression Metrics

| Metric | Formula | When to Use |
|--------|---------|-------------|
| **MAE** | Mean Absolute Error | Interpretable, robust to outliers |
| **MSE** | Mean Squared Error | Penalizes large errors |
| **RMSE** | √MSE | Same units as target |
| **R²** | 1 - (SS_res/SS_tot) | Explains variance (0-1) |

### 3.3 RAG-Specific Metrics (Used in This Project)

| Metric | What It Measures | Our Project Use |
|--------|-----------------|-----------------|
| **Recall@K** | Did correct chunk appear in top K? | K=5, measures if Table 2-4 chunk is retrieved |
| **Precision@K** | Of K results, how many are relevant? | Of 5 returned, how many contain answer? |
| **MRR** | Position of first correct result | 1/rank — is Table 2-4 at position 1 or 5? |
| **Faithfulness** | Is answer supported by context? | Does LLM only use retrieved chunks? |
| **Hallucination Rate** | Claims not in context? | LLM says "Intel TSX" but context has "Uncore PMI" |
| **Context Coverage** | Expected keywords in retrieved context? | Do chunks contain "2026", "Uncore PMI"? |

### Interview Answer:
> "In our RAG project, we track Recall@5 to ensure the correct chunk is retrieved, MRR to check if it's ranked first, and Faithfulness to verify the LLM doesn't hallucinate. We discovered hallucination when the LLM answered about 'Intel TSX' from training data instead of the actual 'Uncore PMI' in the document."

---

## 4. LLMs & Transformer Architecture

### 4.1 Transformer Architecture

```
Input: "The sky is blue"
    │
    ▼
[Tokenization] → [1023, 4521, 892, 3102]
    │
    ▼
[Positional Encoding] → adds position info to each token
    │
    ▼
[Multi-Head Self-Attention] → each token attends to all others
    │                          "is" knows it relates to "sky"
    ▼
[Feed-Forward Network] → transforms representations
    │
    ▼
[Layer Norm + Residual Connections] → stabilizes training
    │
    ▼ (repeat N layers — GPT-4 has ~120 layers)
    │
[Output Head] → predicts next token probability
```

**Key Innovation: Self-Attention**
- Each token looks at every other token to understand context
- "It" in "The sky is blue. It is vast." → attention links "It" to "sky"
- Complexity: O(n²) where n = sequence length

### 4.2 LLM Types

| Type | Architecture | Examples | Use |
|------|-------------|----------|-----|
| Decoder-only | GPT-style, autoregressive | GPT-4, Gemini, Claude, LLaMA | Text generation, chat |
| Encoder-only | Bidirectional | BERT, RoBERTa | Classification, embeddings |
| Encoder-Decoder | Full transformer | T5, BART | Translation, summarization |

### 4.3 Key Parameters

| Parameter | Impact | Example |
|-----------|--------|---------|
| **Temperature** | Randomness. 0=deterministic, 1=creative | 0.2 for factual RAG, 0.8 for creative |
| **Top-P** | Nucleus sampling. 0.1=focused, 0.9=diverse | 0.95 default |
| **Top-K** | Consider only K most likely tokens | 40 default |
| **Max Tokens** | Maximum output length | 8192 in our project |
| **Frequency Penalty** | Penalizes repeated tokens | 0.5 to reduce repetition |

### Interview Answer:
> "In our project, we use Gemini Flash with temperature=0.2 for factual RAG answers and max_tokens=8192. Low temperature prevents the LLM from being creative when it should just report what's in the retrieved context."

---

## 5. RAG vs Fine-Tuning

### 5.1 RAG (Retrieval Augmented Generation)

```
User Query → Retrieve relevant chunks → Augment prompt with context → Generate answer
```

**When to use RAG:**
- Data changes frequently (docs updated daily)
- Need citations/sources
- Large knowledge base (100s of documents)
- Can't afford to retrain model
- Need accurate, grounded answers

### 5.2 Fine-Tuning

```
Training Data (Q&A pairs) → Train/update model weights → Deploy custom model
```

**When to use Fine-Tuning:**
- Need specific tone/style (legal language, medical terms)
- Task is well-defined and stable (classification, extraction)
- Want faster inference (no retrieval step)
- Data doesn't change often

### 5.3 Comparison

| Aspect | RAG | Fine-Tuning |
|--------|-----|-------------|
| Data freshness | Real-time (query-time retrieval) | Stale (retraining needed) |
| Cost | Low (just API calls + vector DB) | High (GPU training hours) |
| Hallucination | Lower (grounded in context) | Higher (model guesses) |
| Latency | Higher (retrieval + generation) | Lower (direct generation) |
| Transparency | High (can show source chunks) | Low (black box) |
| Setup time | Hours | Days/weeks |
| Best for | Q&A over documents, knowledge bases | Style transfer, classification |

### 5.4 When to Combine Both

```
Fine-tune for: Domain-specific language understanding
RAG for: Accessing current/specific data

Example: Fine-tune a model on legal language → Use RAG to retrieve specific case law
```

### Interview Answer (Project Scenario):
> "We chose RAG over fine-tuning because our Intel SDM PDF is 5000+ pages and updates with new processor releases. Fine-tuning would require retraining every time. With RAG, we just re-upload the new PDF and it's immediately searchable. We also need source citations — RAG naturally provides the chunk filename and relevance score."

---

## 6. Retrieval: Chunking Strategies

### 6.1 Why Chunking Matters
LLMs have context windows. A 25 MB PDF (5342 pages) can't fit in one prompt. We split it into searchable chunks, find the relevant ones, and send only those to the LLM.

### 6.2 Chunking Types

| Type | How | Pros | Cons | When to Use |
|------|-----|------|------|-------------|
| **Fixed-size** | Split every N chars | Simple, predictable | Breaks mid-sentence | Quick prototypes |
| **Recursive** | Split by paragraph → sentence → char | Respects text structure | No semantic awareness | Large docs, general use |
| **Semantic** | Embed sentences, split where similarity drops | Topic-coherent chunks | Expensive (API calls per sentence) | Small docs, high quality needed |
| **Markdown/Header** | Split on # headings | Preserves document structure | Only works with structured docs | PDFs with headings |
| **Structure-aware** | Detect tables, headings, prose separately | Tables stay intact | Complex, needs good parser | Technical docs with tables |

### 6.3 Our Project Evolution (Real Scenario)

```
Attempt 1: Semantic Chunking
  Problem: 25 MB PDF → embedding every sentence → 10,000+ Gemini API calls just for chunking
  Result: Timed out after 5 minutes
  
Attempt 2: Recursive Paragraph Chunking
  Problem: Tables got split mid-row ("Uncore PMI." in chunk 1, "IA32_DEBUGCTL..." in chunk 2)
  Result: Search for "Table 2-4" returned TOC dots, not actual table content
  
Attempt 3: Structure-Aware (PyMuPDF table detection)
  Solution: Detect tables as separate elements, keep them whole with headers
  Result: Table 2-4 stored as one chunk with all rows intact
  
Final: Hierarchical Parent-Child with Overlap
  - Parents: 2000 chars with 400 char overlap (context for LLM)
  - Children: 500 chars (precision for search)
  - Tables: Never split, always with heading
```

### 6.4 Parent-Child Retrieval

```
Storage:
  Qdrant (vector DB):  Children (500 chars, embedded for search)
  PostgreSQL:          Parents (2000 chars, raw text for LLM context)

Query time:
  1. Search children (vector + keyword) → find relevant small chunks
  2. Look up parent_id → fetch the full 2000-char parent
  3. Send parent to LLM → complete context without "it" ambiguity
```

### 6.5 Chunk Overlap

```
Without overlap:
  Parent 1: chars 0-2000    | Table starts at 1900
  Parent 2: chars 2000-4000 | Table continues at 2100
  → Table SPLIT across parents!

With 400 char overlap:
  Parent 1: chars 0-2000
  Parent 2: chars 1600-3600  ← starts 400 chars earlier
  → Table (1900-2200) fully contained in Parent 2
```

### 6.6 Noise Filtering

```python
def _is_noise_chunk(text: str) -> bool:
    """Detect TOC/index pages with dot patterns."""
    lines = text.split('\n')
    dot_lines = sum(1 for line in lines if '. .' in line)
    return dot_lines / max(len(lines), 1) > 0.3
```

**Why:** PDF table of contents pages ("Table 2-4 . . . . . . 2-28") pollute search results. Filtering them at upload time eliminates 30-40% of junk chunks.

### Interview Answer:
> "We started with semantic chunking but it was too expensive for large PDFs — embedding every sentence costs thousands of API calls. We switched to recursive paragraph-based chunking but discovered tables were getting split mid-row. Our final solution uses PyMuPDF's table detection to keep tables whole as single chunks, with parent-child hierarchy: small children for precise search, large parents for LLM context. The 400-char overlap between parents ensures content at boundaries is captured in at least one parent."

---

## 7. Retrieval Validation & Eval Metrics

### 7.1 Gold Dataset
A fixed set of (question, expected_answer, expected_chunks) created manually or with LLM assistance. Never changes — only the system under test changes.

### 7.2 Retrieval Metrics

**Recall@K:**
```
"Did the correct chunk appear in top K results?"
Recall@5 = (queries where correct chunk is in top 5) / (total queries)

Example: 4 out of 5 test queries find the right chunk → Recall@5 = 0.80
```

**Precision@K:**
```
"Of the K results returned, how many are relevant?"
Precision@5 = (relevant results in top 5) / 5

Example: 2 of 5 results are relevant → Precision@5 = 0.40
```

**MRR (Mean Reciprocal Rank):**
```
"How high is the first correct result?"
MRR = average(1/rank_of_first_correct)

Query 1: correct at position 1 → 1/1 = 1.0
Query 2: correct at position 3 → 1/3 = 0.33
Query 3: correct at position 2 → 1/2 = 0.5
MRR = (1.0 + 0.33 + 0.5) / 3 = 0.61
```

### 7.3 Grounding Metrics

**Faithfulness:**
```
"Is every claim in the answer supported by the retrieved context?"
LLM judge reads: context + answer → scores 0-1

Score 1.0: "Table 2-4 shows xAPIC removal in 2025" (matches context)
Score 0.0: "Intel TSX was removed in 2026" (not in context — hallucinated)
```

**Hallucination Rate:**
```
"% of answers containing info NOT in retrieved context"
Simple check: expected keywords in answer but NOT in contexts → hallucinated

Our project: LLM said "Intel SGX" and "Intel TSX" but actual table had 
"Uncore PMI" and "Key Locker" → hallucination detected
```

**Context Coverage:**
```
"What % of expected keywords appear in retrieved contexts?"
Expected: ["Uncore PMI", "2026", "IA32_DEBUGCTL"]
Found in contexts: ["Uncore PMI", "2026"] → Coverage = 2/3 = 67%
```

### 7.4 Tools

| Tool | Metrics | LLM Needed? |
|------|---------|-------------|
| RAGAS | Faithfulness, answer relevancy, context precision/recall | Yes (as judge) |
| DeepEval | Same + hallucination | Yes |
| Custom (our project) | MRR, Recall@K, Precision@K, Coverage, Hallucination | No |

### 7.5 When to Run Eval

| Trigger | What Runs |
|---------|-----------|
| Every PR/commit | Unit tests (fast) |
| Merge to main | Full eval (gold dataset) |
| Weekly schedule | Drift detection (same eval) |
| After data change | Re-run to check new document quality |

### Interview Answer:
> "We run RAGAS evaluation with Gemini as the LLM judge. Our gold dataset has 50 queries with expected answers. Before deploying any chunking change, we verify Recall@5 ≥ 0.80 and Hallucination ≤ 0.20. When we switched from flat chunking to hierarchical parent-child, MRR improved from 0.45 to 0.72 because relevant content was no longer split across chunks."

---

## 8. Generation: Model Parameters & Impact

### 8.1 Key Parameters

| Parameter | Range | Impact |
|-----------|-------|--------|
| **temperature** | 0.0 - 2.0 | 0=deterministic (RAG), 1=creative (stories) |
| **top_p** | 0.0 - 1.0 | Nucleus sampling. 0.1=very focused, 0.95=broad |
| **max_tokens** | 1 - 128K | Output length limit. Too low = truncated answers |
| **frequency_penalty** | -2.0 - 2.0 | Positive = avoid repetition |
| **presence_penalty** | -2.0 - 2.0 | Positive = encourage new topics |
| **stop_sequences** | list[str] | Stop generation at these strings |

### 8.2 Impact on RAG Answers

```python
# Our project setting
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-lite",
    temperature=0.2,        # Low: factual, grounded in context
    max_output_tokens=8192, # High: allow complete table descriptions
)
```

**Scenario from our project:**
- `max_tokens=4096` → answers about Table 2-4 got cut off mid-sentence
- Changed to `max_tokens=8192` → complete responses

**Temperature effect on RAG:**
- `temperature=0.0` → always same answer, very grounded
- `temperature=0.2` → slight variation, still factual (our choice)
- `temperature=0.8` → starts adding creative interpretations, hallucination risk↑

---

## 9. LangChain & LangGraph

### 9.1 LangChain Components

| Component | What | Our Project Use |
|-----------|------|-----------------|
| **ChatModel** | LLM wrapper | `ChatGoogleGenerativeAI` for Gemini |
| **Tools** | Functions the agent can call | `search_documents`, `calculator`, `web_search` |
| **Embeddings** | Text → vector | Gemini embeddings (1024-dim) |
| **Text Splitters** | Chunking | `MarkdownHeaderTextSplitter` (considered) |
| **Retrievers** | Search interface | Custom Qdrant-based retriever |
| **Callbacks** | Observability | Usage tracking, LangSmith tracing |

### 9.2 LangGraph Agent Types

| Agent Type | How It Works | When to Use | When NOT to Use |
|------------|-------------|-------------|-----------------|
| **ReAct** | Think → Act → Observe → Repeat | General Q&A, multi-tool | Simple single-tool tasks |
| **Plan-and-Execute** | Plan all steps first, then execute | Complex multi-step tasks | Simple questions |
| **Reflexion** | Critique own output, retry | High-quality writing | Speed-critical apps |
| **Multi-agent** | Multiple specialized agents | Complex workflows | Simple single-domain |

### 9.3 Our Project: ReAct Agent

```python
from langgraph.prebuilt import create_react_agent

agent = create_react_agent(
    model=llm,
    tools=[calculator, search_documents, web_search, get_data_schema, run_sql_query],
    prompt=SystemMessage(content=SYSTEM_PROMPT),
)
```

**Why ReAct:**
- Agent decides which tool to call based on the question
- Can chain: search → calculator (e.g., "average cost from document")
- Simple, well-tested, works with LangSmith tracing

### 9.4 When NOT to Use an Agent

| Scenario | Why No Agent | Alternative |
|----------|-------------|-------------|
| Simple Q&A (one document) | Agent overhead unnecessary | Direct retrieval + prompt |
| Fixed workflow (always same steps) | Agent might pick wrong tools | Hardcoded chain |
| Latency-critical (<1s) | Agent deliberation adds 2-5s | Direct LLM call |
| Predictable output format | Agent may format differently | Structured output chain |

### 9.5 How to Design an Agent

```
1. Define the problem scope (what questions will users ask?)
2. Identify required tools (what actions does the agent need?)
3. Write a system prompt with clear RULES and SCOPE
4. Set recursion/tool-call limits (prevent infinite loops)
5. Add grounding instructions ("only answer from context")
6. Test with adversarial queries
7. Add observability (LangSmith tracing)
```

**Our project lesson:**
> The agent called `search_documents` 13 times because results weren't satisfying. Fix: hard limit of 2 calls per tool per question, plus explicit prompt instruction "call ONCE, answer with what you have."

---

## 10. Vector Databases

### 10.1 What They Do
Store high-dimensional vectors (embeddings) and enable fast similarity search.

### 10.2 Comparison (Used in This Project: Qdrant)

| DB | Vector Search | Keyword Search | Scaling | Best For |
|----|--------------|----------------|---------|----------|
| **Qdrant** | ~5-10ms | ✅ Native text index | Cluster mode | RAG apps (our choice) |
| **Weaviate** | ~10-20ms | ✅ Built-in BM25 | Auto-shard | Multi-modal |
| **Milvus** | ~5-10ms | ✅ Sparse index | Designed for scale | Large-scale |
| **Pinecone** | ~10-20ms | ✅ Sparse-dense | Serverless | No-ops teams |
| **pgvector** | ~20-50ms | ✅ tsvector | Limited | Single-DB architecture |
| **Chroma** | ~10-20ms | ❌ | None | Prototypes |

### 10.3 Why Qdrant for Our Project

1. **Native text index** — keyword search without external BM25 library
2. **Payload filtering** — filter by filename, content_hash, parent_id
3. **Per-user collections** — isolation between users
4. **Docker deployment** — simple `qdrant/qdrant:v1.12.1`
5. **Free self-hosted** — no cloud costs

### 10.4 Qdrant Operations Used

```python
# Create collection with text index
client.create_collection(name, VectorParams(size=1024, distance=Distance.COSINE))
client.create_payload_index(name, "content", TextIndexParams(tokenizer=TokenizerType.WORD))

# Store with payload
PointStruct(id=uuid, vector=[...], payload={
    "content": "chunk text",
    "parent_id": "abc123",
    "filename": "manual.pdf",
    "content_hash": "sha256[:16]",
})

# Hybrid query: vector + text filter
client.query_points(collection, query_vector, limit=3)  # Vector search
client.scroll(collection, filter=MatchText("Table 2-4"))  # Keyword search
```

### 10.5 Interview Questions

**Q: Why not just use PostgreSQL with pgvector?**
> "pgvector works for <100K vectors but degrades at scale. Qdrant uses HNSW index (O(log n) search) and native payload filtering. For our 25K+ chunks, Qdrant gives <10ms queries vs pgvector's 50-150ms."

**Q: How do you handle multi-tenancy?**
> "One collection per user (`user_{id}`). Payload indexes on `filename` for per-document filtering. This gives complete data isolation between users."

**Q: What if the vector DB goes down?**
> "Docker volume persists data. On restart, Qdrant loads from disk. If storage corrupts (happened with BitLocker), we wipe the volume and re-upload — embeddings are cached in Redis, so re-embedding is fast."

---

## 11. Caching & Prompt Versioning

### 11.1 Caching Layers in Our Project

| Cache | What | TTL | Storage |
|-------|------|-----|---------|
| **Embedding cache** | Vector for each text chunk | 7 days | Redis |
| **Answer cache** | Full Q&A pairs | 24 hours | Redis |
| **Collection cache** | Qdrant keeps data in RAM | Persistent | Qdrant internal |

```python
# Embedding cache: avoid redundant API calls
def _get_cached(self, text: str) -> list[float] | None:
    key = f"emb:{sha256(text)[:20]}"
    cached = redis.get(key)
    return json.loads(cached) if cached else None
```

**Impact:** When re-uploading a 25 MB PDF, 5,929 out of 14,334 chunks hit cache = 41% fewer API calls.

### 11.2 Prompt Versioning

```python
# Prompts tracked via git (simplest)
SYSTEM_PROMPT_V1 = "You are a helpful assistant..."
SYSTEM_PROMPT_V2 = "You are a helpful assistant... RULES: call search ONCE..."
SYSTEM_PROMPT_V3 = "... Only answer from context. Say 'not found' if..."

SYSTEM_PROMPT = SYSTEM_PROMPT_V3  # Active version
```

**Tools for production:** LangSmith Hub, Promptfoo, Humanloop

**Why it matters:** Changing one word in a prompt can make the agent hallucinate or loop. Track versions, run eval on each version, deploy the one with best metrics.

---

## 12. Cloud & Deployment

### 12.1 LLM Providers

| Provider | Models | Pricing | Best For |
|----------|--------|---------|----------|
| **OpenAI** | GPT-4o, GPT-4o-mini | $2.50-$10/M tokens | Best tool calling, widest ecosystem |
| **Google Gemini** | Flash, Pro, Ultra | Free tier + $0.075/M | Fast, cheap, multimodal (our choice) |
| **AWS Bedrock** | Claude, Titan, Llama | Pay-per-use | Enterprise, AWS-native apps |
| **GCP Vertex AI** | Gemini, PaLM | Pay-per-use | GCP-native, managed RAG |
| **Hugging Face** | Open models (Llama, Mistral) | Free (self-host) or Inference API | Custom models, fine-tuning |
| **Azure OpenAI** | GPT-4, embeddings | Same as OpenAI | Enterprise compliance |

### 12.2 Deployment Platforms

| Platform | What | When to Use |
|----------|------|-------------|
| **GCP Cloud Run** | Serverless containers | Auto-scaling, pay-per-request |
| **AWS ECS/Fargate** | Managed containers | AWS-native, predictable workloads |
| **AWS Lambda** | Serverless functions | Short tasks (<15 min) |
| **Kubernetes (EKS/GKE)** | Container orchestration | Complex multi-service deployments |
| **Railway/Render** | Simple PaaS | Side projects, quick deploys |
| **Self-hosted VM** | EC2/Compute Engine | Full control, persistent services |

### 12.3 Our Project Deployment Architecture

```
┌─────────────────────────────────────────────┐
│  Docker Compose (local/staging)             │
│                                             │
│  ┌───────────┐ ┌────────┐ ┌──────┐        │
│  │ PostgreSQL│ │ Qdrant │ │Redis │        │
│  │  :5432    │ │ :6333  │ │:6379 │        │
│  └───────────┘ └────────┘ └──────┘        │
│                                             │
│  ┌───────────────────┐ ┌────────────────┐  │
│  │ FastAPI (API)     │ │ MCP Server     │  │
│  │  :8000            │ │  :8001         │  │
│  └───────────────────┘ └────────────────┘  │
│                                             │
│  ┌───────────────────┐                     │
│  │ Streamlit (UI)    │                     │
│  │  :8501            │                     │
│  └───────────────────┘                     │
└─────────────────────────────────────────────┘

External APIs:
  → Gemini (embeddings + LLM)
  → Google OAuth
  → LangSmith (tracing)
```

---

## 13. Docker & Kubernetes

### 13.1 Docker

**Dockerfile (our project):**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ ./src/
COPY run_api.py .
CMD ["python", "run_api.py"]
```

**Docker Compose (multi-service):**
```yaml
services:
  postgres:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
  qdrant:
    image: qdrant/qdrant:v1.12.1
    ports: ["6333:6333"]
    volumes: [qdrant_data:/qdrant/storage]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

### 13.2 Kubernetes (Production)

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-api
spec:
  replicas: 3  # Horizontal scaling
  selector:
    matchLabels:
      app: rag-api
  template:
    spec:
      containers:
      - name: api
        image: myregistry/rag-api:v1.2.3
        ports:
        - containerPort: 8000
        resources:
          limits:
            memory: "1Gi"
            cpu: "1000m"
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: rag-secrets
              key: database-url
```

**When Docker Compose → When Kubernetes:**

| Docker Compose | Kubernetes |
|----------------|------------|
| Single server | Multiple servers |
| Dev/staging | Production |
| 1-5 services | 10+ services |
| Manual scaling | Auto-scaling |
| Simple health checks | Liveness/readiness probes |
| No zero-downtime deploy | Rolling updates, canary |

### 13.3 Interview Questions

**Q: How do you handle secrets in Docker?**
> "Never in images or docker-compose.yml. Use `.env` files (git-ignored) for local, Kubernetes Secrets or AWS Secrets Manager for production."

**Q: How do you handle data persistence with Docker?**
> "Named volumes (`pgdata:/var/lib/postgresql/data`). Survived restarts. We lost data once when Docker's volume got corrupted due to BitLocker locking the host drive — lesson: keep Docker volumes on unencrypted drives or use cloud-managed databases."

**Q: Docker vs Kubernetes for RAG systems?**
> "Docker Compose for development and small deployments. Kubernetes when you need auto-scaling (traffic spikes during business hours), zero-downtime deployments, and multi-region redundancy. Our project uses Compose locally but would move to Cloud Run or EKS for production."

---

## Summary: Complete RAG Architecture (This Project)

```
User → Streamlit UI → WebSocket → FastAPI
                                      │
                                      ▼
                              LangGraph ReAct Agent
                              (decides which tool)
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                  ▼
            search_documents     run_sql_query      web_search
                    │                 │                  │
                    ▼                 ▼                  ▼
            Qdrant (vector)    PostgreSQL (CSV)   MCP Server
            + Text Index       + SQL queries      (DuckDuckGo)
                    │
                    ▼
            Parent lookup (PostgreSQL)
                    │
                    ▼
            LLM (Gemini Flash) generates answer
                    │
                    ▼
            Response → WebSocket → UI
```

**Key Design Decisions:**
1. Hierarchical chunking (parent-child) — preserves context
2. Hybrid search (vector + keyword) — catches both semantic and exact matches
3. No reranker (removed) — 22s latency wasn't worth the quality gain on CPU
4. Background processing — large PDFs don't block the server
5. Parallel embedding (5 concurrent) — 5x faster uploads
6. Session management — users can have multiple conversations
7. MCP server — web search accessible from any MCP client

---

*Document generated from real project development experience.*
*All scenarios, trade-offs, and decisions are from actual implementation.*
