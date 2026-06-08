import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Ensure project root is in the path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from backend.agents.workflow import compiled_workflow

def load_dataset(filepath: str) -> List[Dict[str, Any]]:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def evaluate_verdict(predicted: str, expected: str) -> str:
    """
    Classify predictions vs expected.
    Maps:
      TRUE / LIKELY TRUE -> TRUE
      FALSE / LIKELY FALSE -> FALSE
      MISLEADING -> MIXED
      UNVERIFIED -> UNKNOWN
    """
    p = predicted.upper()
    e = expected.upper()
    
    p_mapped = "TRUE" if p in ["TRUE", "LIKELY TRUE"] else ("FALSE" if p in ["FALSE", "LIKELY FALSE"] else "OTHER")
    e_mapped = "TRUE" if e in ["TRUE", "LIKELY TRUE"] else ("FALSE" if e in ["FALSE", "LIKELY FALSE"] else "OTHER")
    
    if p_mapped == e_mapped:
        return "CORRECT"
    return "INCORRECT"

async def run_evaluation():
    print("=" * 60)
    print("NEWSCHECK AI: EVALUATION HARNESS")
    print("=" * 60)
    
    dataset_path = ROOT_DIR / "evaluation" / "eval_dataset.json"
    if not dataset_path.exists():
        print(f"Error: Dataset not found at {dataset_path}")
        return
        
    dataset = load_dataset(str(dataset_path))
    print(f"Loaded {len(dataset)} evaluation items.\nRunning evaluations (this may take a moment)...")
    
    results = []
    correct_count = 0
    
    tp = 0 # True Positives (Expected True, Predicted True)
    tn = 0 # True Negatives (Expected False, Predicted False)
    fp = 0 # False Positives (Expected False, Predicted True)
    fn = 0 # False Negatives (Expected True, Predicted False)
    
    for idx, item in enumerate(dataset, 1):
        print(f"\n[{idx}/{len(dataset)}] Evaluating claim: '{item['text'][:60]}...'")
        
        initial_state = {
            "url": None,
            "raw_text": item["text"],
            "claims": [],
            "search_results": [],
            "evidences": {},
            "verdicts": {},
            "deep_search_done": False,
            "loop_count": 0,
            "errors": []
        }
        
        try:
            output = await compiled_workflow.ainvoke(initial_state)
            predicted_verdict = output.get("final_verdict", "UNVERIFIED")
            credibility_score = output.get("credibility_score", 50)
            
            expected_verdict = item["expected_verdict"]
            eval_result = evaluate_verdict(predicted_verdict, expected_verdict)
            
            if eval_result == "CORRECT":
                correct_count += 1
                
            # Update confusion matrix values (using TRUE/FALSE mapping)
            p_val = "TRUE" if predicted_verdict in ["TRUE", "LIKELY TRUE"] else "FALSE"
            e_val = "TRUE" if expected_verdict in ["TRUE", "LIKELY TRUE"] else "FALSE"
            
            if e_val == "TRUE" and p_val == "TRUE":
                tp += 1
            elif e_val == "FALSE" and p_val == "FALSE":
                tn += 1
            elif e_val == "FALSE" and p_val == "TRUE":
                fp += 1
            elif e_val == "TRUE" and p_val == "FALSE":
                fn += 1
                
            print(f"  -> Predicted: {predicted_verdict} (Score: {credibility_score}) | Expected: {expected_verdict} -> {eval_result}")
            
            results.append({
                "id": item["id"],
                "text": item["text"],
                "expected": expected_verdict,
                "predicted": predicted_verdict,
                "score": credibility_score,
                "status": eval_result
            })
        except Exception as e:
            print(f"  -> Failed to evaluate due to error: {e}")
            results.append({
                "id": item["id"],
                "text": item["text"],
                "expected": item["expected_verdict"],
                "predicted": "ERROR",
                "score": 0,
                "status": "FAILED"
            })

    # Calculations
    total = len(dataset)
    accuracy = correct_count / total if total > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS SUMMARY")
    print("=" * 60)
    print(f"Total Evaluated : {total}")
    print(f"Accuracy        : {accuracy:.2%}")
    print(f"Precision       : {precision:.2%}")
    print(f"Recall          : {recall:.2%}")
    print(f"F1-Score        : {f1:.2%}")
    print(f"TP: {tp} | TN: {tn} | FP: {fp} | FN: {fn}")
    print("=" * 60)
    
    # Save results to a report file
    report_file = ROOT_DIR / "evaluation" / "eval_results.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "metrics": {
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "confusion_matrix": {"TP": tp, "TN": tn, "FP": fp, "FN": fn}
            },
            "detailed_results": results
        }, f, indent=4)
    print(f"Saved evaluation results to {report_file}")

if __name__ == "__main__":
    asyncio.run(run_evaluation())
