"""
RAG Evaluation Script using RAGAS.

Metrics:
  Retrieval:
    - context_precision (Precision@K)
    - context_recall (Recall@K)
  Grounding:
    - faithfulness (Is the answer supported by context?)
    - answer_relevancy (Does the answer address the question?)

Custom:
    - MRR (Mean Reciprocal Rank)
    - Hallucination detection (keywords in answer but not in context)

Usage:
    python -m eval.run_eval --user_id 109146667799926584191
"""

import json
import asyncio
import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


def load_gold_dataset() -> list[dict]:
    """Load the gold test dataset."""
    dataset_path = Path(__file__).parent / "gold_dataset.json"
    with open(dataset_path, "r") as f:
        return json.load(f)


async def run_retrieval(user_id: str, test_set: list[dict]) -> list[dict]:
    """Run the RAG pipeline on each test question and collect results."""
    from src.rag.vectorstore import vectorstore
    from src.graph.workflow import build_graph
    from langchain_core.messages import HumanMessage

    agent = build_graph(user_id=user_id)
    results = []

    for item in test_set:
        question = item["question"]
        print(f"\n  📝 Query: {question}")

        # Get retrieval results (contexts)
        retrieved = await vectorstore.query(user_id, question, n_results=5)
        contexts = [r["content"] for r in retrieved]

        # Get agent answer
        try:
            response = await agent.ainvoke(
                {"messages": [HumanMessage(content=question)]},
                config={"recursion_limit": 20},
            )
            answer = response["messages"][-1].content
            if isinstance(answer, list):
                answer = " ".join(
                    p.get("text", str(p)) if isinstance(p, dict) else str(p)
                    for p in answer
                )
        except Exception as e:
            answer = f"Error: {e}"

        print(f"  ✅ Answer: {answer[:100]}...")

        results.append({
            "question": question,
            "answer": answer,
            "contexts": contexts,
            "ground_truth": item["ground_truth"],
            "expected_keywords": item.get("expected_keywords", []),
        })

    return results


def compute_mrr(results: list[dict]) -> float:
    """
    Compute Mean Reciprocal Rank.
    Checks if expected keywords appear in retrieved contexts.
    """
    reciprocal_ranks = []

    for item in results:
        keywords = item["expected_keywords"]
        contexts = item["contexts"]

        # Find rank of first context that contains any expected keyword
        rank = None
        for i, ctx in enumerate(contexts, 1):
            ctx_lower = ctx.lower()
            if any(kw.lower() in ctx_lower for kw in keywords):
                rank = i
                break

        if rank:
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)

    return sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0


def compute_recall_at_k(results: list[dict], k: int = 5) -> float:
    """
    Compute Recall@K.
    For each query, check if at least one relevant context is in top-K.
    """
    hits = 0
    for item in results:
        keywords = item["expected_keywords"]
        contexts = item["contexts"][:k]
        ctx_combined = " ".join(contexts).lower()

        if any(kw.lower() in ctx_combined for kw in keywords):
            hits += 1

    return hits / len(results) if results else 0.0


def compute_precision_at_k(results: list[dict], k: int = 5) -> float:
    """
    Compute Precision@K.
    Of the K contexts retrieved, how many contain relevant keywords?
    """
    precisions = []
    for item in results:
        keywords = item["expected_keywords"]
        contexts = item["contexts"][:k]

        relevant_count = 0
        for ctx in contexts:
            ctx_lower = ctx.lower()
            if any(kw.lower() in ctx_lower for kw in keywords):
                relevant_count += 1

        precisions.append(relevant_count / k)

    return sum(precisions) / len(precisions) if precisions else 0.0


def compute_hallucination_rate(results: list[dict]) -> float:
    """
    Simple hallucination detection.
    Checks if the answer contains claims not supported by the context.
    Uses keyword overlap as a proxy.
    """
    hallucination_count = 0

    for item in results:
        answer = item["answer"].lower()
        contexts_combined = " ".join(item["contexts"]).lower()
        ground_truth = item["ground_truth"].lower()

        # If answer mentions keywords that are in ground_truth but NOT in contexts
        # → likely hallucinated from training data
        keywords = item["expected_keywords"]
        for kw in keywords:
            if kw.lower() in answer and kw.lower() not in contexts_combined:
                hallucination_count += 1
                break

    return hallucination_count / len(results) if results else 0.0


def compute_context_coverage(results: list[dict]) -> float:
    """
    Context coverage: what % of expected keywords appear in retrieved contexts?
    """
    coverages = []
    for item in results:
        keywords = item["expected_keywords"]
        contexts_combined = " ".join(item["contexts"]).lower()

        if not keywords:
            coverages.append(1.0)
            continue

        found = sum(1 for kw in keywords if kw.lower() in contexts_combined)
        coverages.append(found / len(keywords))

    return sum(coverages) / len(coverages) if coverages else 0.0


async def run_ragas_eval(results: list[dict]):
    """Run RAGAS evaluation for faithfulness and answer relevancy using Gemini."""
    try:
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
        from datasets import Dataset
        from src.config.settings import settings

        # Configure RAGAS to use Gemini (instead of OpenAI)
        llm = LangchainLLMWrapper(ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
        ))
        embeddings = LangchainEmbeddingsWrapper(GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=settings.gemini_api_key,
        ))

        # Prepare dataset in RAGAS format
        eval_data = {
            "question": [r["question"] for r in results],
            "answer": [r["answer"] for r in results],
            "contexts": [r["contexts"] for r in results],
            "ground_truth": [r["ground_truth"] for r in results],
        }

        dataset = Dataset.from_dict(eval_data)

        print("\n  🔄 Running RAGAS evaluation (Gemini as judge)...")
        scores = evaluate(
            dataset=dataset,
            metrics=[faithfulness, answer_relevancy],
            llm=llm,
            embeddings=embeddings,
        )

        return {
            "faithfulness": float(scores["faithfulness"]),
            "answer_relevancy": float(scores["answer_relevancy"]),
        }

    except Exception as e:
        print(f"  ⚠️ RAGAS evaluation failed: {e}")
        return {"faithfulness": None, "answer_relevancy": None}


async def main():
    parser = argparse.ArgumentParser(description="RAG Evaluation")
    parser.add_argument("--user_id", default="eval_test_user", help="User ID whose collection to evaluate (default: eval_test_user)")
    parser.add_argument("--skip_ragas", action="store_true", help="Skip RAGAS LLM-judge metrics")
    args = parser.parse_args()

    print("=" * 60)
    print("  RAG EVALUATION")
    print("=" * 60)

    # Load test set
    test_set = load_gold_dataset()
    print(f"\n📋 Gold dataset: {len(test_set)} test queries")
    print(f"👤 User ID: {args.user_id}")

    # Run retrieval + answer generation
    print("\n🔍 Running RAG pipeline on test queries...")
    results = await run_retrieval(args.user_id, test_set)

    # Compute custom metrics
    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)

    mrr = compute_mrr(results)
    recall = compute_recall_at_k(results, k=5)
    precision = compute_precision_at_k(results, k=5)
    hallucination = compute_hallucination_rate(results)
    coverage = compute_context_coverage(results)

    print(f"\n📊 RETRIEVAL METRICS:")
    print(f"   Recall@5:          {recall:.2%}")
    print(f"   Precision@5:       {precision:.2%}")
    print(f"   MRR:               {mrr:.4f}")
    print(f"   Context Coverage:  {coverage:.2%}")

    print(f"\n📊 GROUNDING METRICS:")
    print(f"   Hallucination Rate: {hallucination:.2%}")

    # RAGAS evaluation (optional — needs LLM API)
    if not args.skip_ragas:
        ragas_scores = await run_ragas_eval(results)
        if ragas_scores["faithfulness"] is not None:
            print(f"   Faithfulness:       {ragas_scores['faithfulness']:.2%}")
            print(f"   Answer Relevancy:   {ragas_scores['answer_relevancy']:.2%}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  SUMMARY")
    print(f"{'=' * 60}")
    print(f"   ✅ Recall@5 ≥ 0.80:       {'PASS' if recall >= 0.80 else 'FAIL'} ({recall:.2%})")
    print(f"   ✅ MRR ≥ 0.50:            {'PASS' if mrr >= 0.50 else 'FAIL'} ({mrr:.4f})")
    print(f"   ✅ Hallucination ≤ 0.20:   {'PASS' if hallucination <= 0.20 else 'FAIL'} ({hallucination:.2%})")
    print(f"   ✅ Coverage ≥ 0.70:        {'PASS' if coverage >= 0.70 else 'FAIL'} ({coverage:.2%})")

    # Save results
    output_path = Path(__file__).parent / "eval_results.json"
    with open(output_path, "w") as f:
        json.dump({
            "metrics": {
                "recall_at_5": recall,
                "precision_at_5": precision,
                "mrr": mrr,
                "context_coverage": coverage,
                "hallucination_rate": hallucination,
            },
            "results": [
                {
                    "question": r["question"],
                    "answer": r["answer"][:200],
                    "ground_truth": r["ground_truth"],
                    "contexts_count": len(r["contexts"]),
                }
                for r in results
            ],
        }, f, indent=2)

    print(f"\n💾 Results saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
