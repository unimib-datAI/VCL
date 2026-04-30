"""Batch evaluation script for comparing DQL and baseline model answers."""

import json
import os
import asyncio
import time
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environmental variables
load_dotenv()

from scripts.evaluation.core.path_retriever import retrieve_doc_paths
from scripts.evaluation.core.judge import GPTJudge
from scripts.evaluation.core.registry import ModelRegistry

from scripts.evaluation.models.dql import DQLModel
from scripts.evaluation.models.openai_filesearch import GPTModel
from scripts.evaluation.models.rag import RAGModel
from scripts.evaluation.models.copilot import CopilotModel
from scripts.evaluation.models.notebooklm import NotebookLMModel

project_root = Path(__file__).resolve().parent.parent.parent

def parse_arguments():
    """Handles command line arguments."""
    parser = argparse.ArgumentParser(description="LLM models evaluation script.")
    
    parser.add_argument(
        "-models", 
        nargs="+", 
        choices=["FileSearch", "RAG", "Copilot", "NotebookLM", "DQL"], 
        required=False,
        default=["FileSearch", "RAG", "Copilot", "NotebookLM", "DQL"],
        help="List of models to evaluate (e.g., --models RAG)"
    )
    parser.add_argument(
        "-usecase", 
        required=False,
        default="vitali",
        help="Which corpus the models need to use."
    )
    parser.add_argument(
        "-gen-llm", 
        type=str, 
        default="gpt-4o-mini", 
        help="OpenAI's LLM to use for generation in RAG and FileSearch (default: gpt-4o-mini)"
    )
    parser.add_argument(
        "-eval-llm", 
        type=str, 
        default="gpt-4o-mini", 
        help="OpenAI's LLM to use for evaluation/judge (default: gpt-4o-mini)"
    )
    parser.add_argument(
        "-k", 
        type=int, 
        default=1, 
        help="Number of iterations/answers per model (default: 1)"
    )
    
    return parser.parse_args()

def serialize(obj):
    """Serializes non-standard objects for JSON."""
    return str(obj)

def read_json(filepath):
    """Reads a JSON file and returns its content."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data, output_path):
    """Saves data to a JSON file."""
    with open(output_path, "w", encoding="utf-8") as o:
        json.dump(data, o, ensure_ascii=False, indent=4, default=serialize)
    print(f"[INFO] File saved to {output_path}")

def initialize_models_and_judge(selected_models, gen_llm, eval_llm, documents, usecase):
    """Registers the requested models and initializes the judge."""
    registry = ModelRegistry()
    
    # Available models mapping
    available_models = {
        "FileSearch": lambda: GPTModel(gen_llm),
        "RAG": lambda: RAGModel(gen_llm),
        "Copilot": lambda: CopilotModel(),
        "NotebookLM": lambda: NotebookLMModel(),
        "DQL": lambda: DQLModel(gen_llm, usecase)
    }

    # Model registration
    for model_name in selected_models:
        if model_name in available_models:
            model = available_models[model_name]()
            registry.register(model)
            print(f"[INFO] Initializing model: {model.name}")
            model.initialize(documents)
            print(f"[INFO] Model {model.name} initialized")

    # Judge initialization
    print("[INFO] Initializing Judge")
    judge = GPTJudge(eval_llm)
    judge.initialize(documents)
    asyncio.run(judge.start_prompt())
    print("[INFO] Judge initialized")
    
    return registry, judge

def generate_answers(model, question, question_data, k):
    """Generates answers for a specific model."""
    answers = {}
    details = {}
    
    for i in range(1, k + 1):
        idx = str(i)
        # Check if the answer already exists in the file
        if idx in question_data.get(model.name, {}).get("answers", {}):
            print(f"[INFO] Answer generation for {model.name} ({idx}): Found in file")
            answers[idx] = "\n".join(question_data[model.name]["answers"][idx])
            if idx in question_data[model.name].get("details", {}):
                details[idx] = question_data[model.name]["details"][idx]
        else:
            try:
                result = model.query(question)
                if isinstance(result, dict):
                    answers[idx] = result.get("content", "")
                    details[idx] = result
                else:
                    answers[idx] = result
                print(f"[INFO] Answer generation for {model.name} ({idx}): Done")
            except Exception as e:
                answers[idx] = ""
                print(f"[INFO] Answer generation for {model.name} ({idx}): Error {e}")
                
    return answers, details

def generate_claims(model_name, answers, question_data, judge, k):
    """Extracts claims from the generated answers."""
    claims = {}
    
    for i in range(1, k + 1):
        idx = str(i)
        # Check if claims already exist
        existing_claims = question_data.get(model_name, {}).get("claims", {}).get("answers", {})
        if idx in existing_claims:
            print(f"[INFO] Claims generation for {model_name} ({idx}): Found in file")
            claims[idx] = existing_claims[idx]
        else:
            try:
                claims[idx] = asyncio.run(judge.extract_claims(answers[idx]))
                print(f"[INFO] Claims generation for {model_name} ({idx}): Done")
            except Exception as e:
                claims[idx] = []
                print(f"[INFO] Claims generation for {model_name} ({idx}): Error {e}")
                
    return claims

def evaluate_models(registry, judge, question, final_results, question_data, k):
    """Executes the judge's evaluation on the generated answers and claims."""
    ground_truth_dict = question_data.get("ground_truth", {})
    
    for annotator in ground_truth_dict:
        print(f"[INFO] Evaluation annotator {annotator}: Start")
        ground_truth = ground_truth_dict.get(annotator, {}).get("text", [])
        
        if not ground_truth:
            print(f"[INFO] Annotator {annotator} skipped (No ground truth)")
            continue
            
        ground_truth_str = str(ground_truth)
        
        # Extract claims for ground truth if missing
        ground_truth_claims = ground_truth_dict.get(annotator, {}).get("claims")
        if not ground_truth_claims:
            ground_truth_claims = asyncio.run(judge.extract_claims(ground_truth_str))
            question_data["ground_truth"][annotator]["claims"] = ground_truth_claims

        # Evaluation for each model
        for model in registry.all():
            start_eval_time = datetime.now()
            
            answers = final_results[model.name]["answers"]
            answers_claims = final_results[model.name]["claims"]["answers"]
            
            if answers and answers_claims:
                # Execute evaluation only if not already done (or partial relative to K)
                existing_evals = question_data.get(model.name, {}).get("evaluation", {}).get(annotator, {})
                if len(existing_evals) <= k:
                    try:
                        eval_result = asyncio.run(
                            judge.judge(question, answers, ground_truth_str, answers_claims, ground_truth_claims)
                        )
                        final_results[model.name]["evaluation"][annotator] = eval_result
                        print(f"[INFO] Evaluation for {model.name}: Done")
                    except Exception as e:
                        final_results[model.name]["evaluation"][annotator] = {}
                        print(f"[INFO] Evaluation for {model.name}: Error {e}")
                else:
                    final_results[model.name]["evaluation"][annotator] = existing_evals
                    print(f"[INFO] Evaluation for {model.name}: Skipped (already present)")
            else:
                final_results[model.name]["evaluation"][annotator] = {}
                print(f"[INFO] Evaluation for {model.name}: Skipped (missing data)")

            # Record evaluation times
            end_eval_time = datetime.now()
            final_results[model.name]["time"]["evaluation_time"][annotator] = {
                "start": start_eval_time,
                "end": end_eval_time,
                "delta": (end_eval_time - start_eval_time).total_seconds()
            }

def main():
    """
    Run the full evaluation pipeline for every input question file.
    """
    args = parse_arguments()
    
    print("[INFO] Starting evaluation pipeline...")
    print(f"[CONFIG] Models: {args.models} | Gen LLM: {args.gen_llm} | Eval LLM: {args.eval_llm} | K: {args.k}")
    
    global_start_time = datetime.now()
    print(f"[TIME] Global start: {global_start_time}")

    input_dir = os.path.join(project_root, "scripts", "evaluation", "questions", "input")
    output_dir = os.path.join(project_root, "scripts", "evaluation", "questions", "output", 
                              global_start_time.isoformat().replace(":", "").replace(".", ""))
    os.makedirs(output_dir, exist_ok=True)

    documents = retrieve_doc_paths(project_root, args.usecase)
    print(f"[INFO] Retrieved {len(documents)} document paths")

    # 1. Register models and initialize judge
    registry, judge = initialize_models_and_judge(args.models, args.gen_llm, args.eval_llm, documents, args.usecase)

    for question_file in sorted(os.listdir(input_dir)):
        if not question_file.endswith(".json"):
            continue
            
        try:
            question_path = os.path.join(input_dir, question_file)
            question_data = read_json(question_path)

            id_question = question_data.get("ID")
            question = question_data.get("question")
            
            if not id_question or not question:
                print(f"[INFO] File {question_file} skipped (Missing ID or question)")
                continue

            print(f"\n--- [Processing Question {id_question}] ---")
            final_results = {}

            # 2 & 3. Generate answers and claims for each model
            for model in registry.all():
                final_results[model.name] = {
                    "answers": {},
                    "claims": {"answers": {}},
                    "evaluation": {},
                    "time": {"generation_time": {}, "evaluation_time": {}}
                }
                
                start_gen_time = datetime.now()
                
                # Generate answers
                answers, details = generate_answers(model, question, question_data, args.k)
                final_results[model.name]["answers"] = answers
                if details:
                    final_results[model.name]["details"] = details
                
                # Generate Claims
                claims = generate_claims(model.name, answers, question_data, judge, args.k)
                final_results[model.name]["claims"]["answers"] = claims
                
                end_gen_time = datetime.now()
                final_results[model.name]["time"]["generation_time"] = {
                    "start": start_gen_time,
                    "end": end_gen_time,
                    "delta": (end_gen_time - start_gen_time).total_seconds()
                }

            time.sleep(10) # Pause as in the original script
            
            # 4. Generate evaluations
            evaluate_models(registry, judge, question, final_results, question_data, args.k)

            # Final answer formatting (split by newline)
            for model in registry.all():
                for idx in final_results[model.name]["answers"]:
                    final_results[model.name]["answers"][idx] = str(final_results[model.name]["answers"][idx]).split("\n")

            # 5. Save to JSON file
            question_data.update(final_results)
            output_path = os.path.join(output_dir, question_file)
            save_json(question_data, output_path)

        except Exception as e:
            print(f"[CRITICAL ERROR] File {question_file}: {e}")

    global_end_time = datetime.now()
    print(f"\n[TIME] Global end: {global_end_time}")
    print(f"[INFO] Total execution time: {(global_end_time - global_start_time).total_seconds()} seconds")
    print("[INFO] Evaluation Done!")

if __name__ == "__main__":
    main()
