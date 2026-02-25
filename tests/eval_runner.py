import os
import json
import sys
import pathlib
import argparse
from typing import List, Dict
from datetime import datetime

# Add root to sys.path
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api import process_query
from app.agents.supervisor import SupervisorAgent

class LLMJudge:
    def __init__(self):
        # We reuse the Supervisor's LLM setup to get Groq/Ollama based on env
        self.agent = SupervisorAgent()
        self.llm = self.agent.llm

    def score_answer(self, question: str, ground_truth: str, generated_answer: str) -> Dict:
        prompt = f"""
        ### TASK ###
        You are an expert evaluator for a RAG (Retrieval-Augmented Generation) system.
        Rate the 'Generated Answer' based on the 'Ground Truth' for the given 'Question'.

        ### CRITERIA ###
        1. ACCURACY (1-5): Does the generated answer contain the correct information per the ground truth?
        2. FAITHFULNESS (1-5): Does the answer avoid hallucinating information not present in the context?
        3. TONE (1-5): Is the tone professional and helpful?

        ### DATA ###
        Question: {question}
        Ground Truth: {ground_truth}
        Generated Answer: {generated_answer}

        ### OUTPUT FORMAT ###
        Return ONLY a JSON object with the following keys:
        {{
            "accuracy_score": int,
            "faithfulness_score": int,
            "tone_score": int,
            "reasoning": "string"
        }}
        """
        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            # Basic cleanup if the LLM adds markdown blocks
            content = content.strip().replace("```json", "").replace("```", "")
            return json.loads(content)
        except Exception as e:
            return {"error": str(e), "accuracy_score": 0, "faithfulness_score": 0, "tone_score": 0, "reasoning": "Failed to evaluate"}

def run_evals():
    parser = argparse.ArgumentParser(description="Run RAG evaluations.")
    parser.add_argument("--name", type=str, default="unnamed_run", help="Name for this evaluation run.")
    args = parser.parse_args()
    
    run_name = args.name
    
    # Pre-create the subfolder for results
    runs_dir = ROOT / "tests" / "eval_runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    
    dataset_path = ROOT / "tests" / "eval_dataset.json"
    if not dataset_path.exists():
        print(f"❌ Error: Dataset not found at {dataset_path}")
        return

    with open(dataset_path, "r") as f:
        data = json.load(f)

    judge = LLMJudge()
    results = []

    print(f"\n🚀 Starting '{run_name}' evaluation on {len(data)} test cases...\n")

    for i, item in enumerate(data):
        biz_id = item["business_id"]
        q = item["question"]
        gt = item["ground_truth"]

        print(f"[{i+1}/{len(data)}] Testing Business: {biz_id}")
        print(f"      Query: {q}")

        # Run the actual pipeline
        response = process_query(biz_id, q)
        generated = response.get("answer", "")

        # Score the response
        scores = judge.score_answer(q, gt, generated)
        
        result = {
            "case": i + 1,
            "business_id": biz_id,
            "question": q,
            "ground_truth": gt,
            "context_retrieved": response.get("context", ""),
            "generated_answer": generated,
            "evaluation": scores
        }
        results.append(result)

        print(f"      Score: Acc={scores.get('accuracy_score')}, Faith={scores.get('faithfulness_score')}, Tone={scores.get('tone_score')}")
        print(f"      Reason: {scores.get('reasoning')}\n")

    if not results:
        print("No results to summarize.")
        return

    # Calculate Summary Metrics
    accuracy_scores = [float((r["evaluation"] if isinstance(r["evaluation"], dict) else {}).get("accuracy_score", 0)) for r in results]
    faithfulness_scores = [float((r["evaluation"] if isinstance(r["evaluation"], dict) else {}).get("faithfulness_score", 0)) for r in results]
    
    avg_acc = sum(accuracy_scores) / len(results)
    avg_faith = sum(faithfulness_scores) / len(results)
    
    # --- HISTORY TRACKING & COMPARISON ---
    history_path = ROOT / "tests" / "eval_history.json"
    history = []
    if history_path.exists():
        try:
            with open(history_path, "r") as f:
                history = json.load(f)
        except Exception:
            history = []

    print("--- EVALUATION SUMMARY ---")
    print(f"Run Name: {run_name}")
    print(f"Average Accuracy: {avg_acc:.2f} / 5.0")
    print(f"Average Faithfulness: {avg_faith:.2f} / 5.0")

    if history:
        last_run = history[-1]
        last_acc = last_run.get("avg_accuracy", 0)
        last_faith = last_run.get("avg_faithfulness", 0)

        diff_acc = avg_acc - last_acc
        diff_faith = avg_faith - last_faith

        print("\n--- COMPARISON WITH PREVIOUS RUN ('{}') ---".format(last_run.get("run_name", "previous")))
        
        # Flag Accuracy Changes
        if diff_acc < -0.1:
            print(f"⚠️  FLAG: Accuracy DROPPED by {abs(diff_acc):.2f} points!")
        elif diff_acc > 0.1:
            print(f"🚀 SUCCESS: Accuracy INCREASED by {diff_acc:.2f} points!")
        else:
            print(f"➡️  Accuracy remained stable (diff: {diff_acc:+.2f})")

        # Flag Faithfulness Changes
        if diff_faith < -0.1:
            print(f"⚠️  FLAG: Faithfulness DROPPED by {abs(diff_faith):.2f} points!")
        elif diff_faith > 0.1:
            print(f"🚀 SUCCESS: Faithfulness INCREASED by {diff_faith:.2f} points!")

    # Save detailed per-run results in the subfolder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"eval_results_{timestamp}_{run_name}.json"
    output_path = runs_dir / filename
    
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    # Update History Index
    history_entry = {
        "timestamp": datetime.now().isoformat(),
        "run_name": run_name,
        "avg_accuracy": round(float(avg_acc), 3),
        "avg_faithfulness": round(float(avg_faith), 3),
        "num_cases": len(results),
        "details_file": str(filename)
    }
    history.append(history_entry)
    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)

    print(f"\nDetailed results saved to: {output_path}")
    print(f"History index updated: {history_path}")

if __name__ == "__main__":
    run_evals()
