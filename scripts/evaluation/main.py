from dotenv import load_dotenv
# Load environmental variables from the .env file (e.g., DB credentials)
load_dotenv()

import json
import os
import asyncio
import time

from datetime import datetime
from pathlib import Path

from scripts.evaluation.core.path_retriever import retrieve_doc_paths
from scripts.evaluation.core.judge import GPTJudge
from scripts.evaluation.core.registry import ModelRegistry

from scripts.evaluation.models.dql import DQLModel
from scripts.evaluation.models.openai_filesearch import GPTModel
from scripts.evaluation.models.rag import RAGModel
from scripts.evaluation.models.copilot import CopilotModel
from scripts.evaluation.models.notebooklm import NotebookLMModel

project_root = Path(__file__).resolve().parent.parent.parent

GENERATION_OPENAI_MODEL = "gpt-4o-mini"
EVALUATION_OPENAI_MODEL = "gpt-4o-mini"

K = 1

def serialize(obj):
    return str(obj)

def evaluation():
    print("[INFO] Starting evaluation...")
    global_start_time = datetime.now()
    print(f"[TIME] Global start: {global_start_time}")

    input_dir = os.path.join(
        project_root,
        "scripts",
        "evaluation",
        "questions",
        "input"
    )

    output_dir = os.path.join(
        project_root,
        "scripts",
        "evaluation",
        "questions",
        "output",
        global_start_time.isoformat().replace(":", "").replace(".", "")
    )
    os.makedirs(output_dir, exist_ok=True)
    print(f"[INFO] Output directory created at {output_dir}")

    documents = retrieve_doc_paths(project_root)
    print(f"[INFO] Retrieved {len(documents)} document paths")

    registry = ModelRegistry()
    #registry.register(DQLModel("DQL-Default"))
    #registry.register(DQLModel("LDQL-Default"))
    #registry.register(DQLModel("LDQL-U"))
    registry.register(DQLModel("LDQL-U (Patch 2)"))
    #registry.register(GPTModel(GENERATION_OPENAI_MODEL))
    #registry.register(RAGModel(GENERATION_OPENAI_MODEL))
    #registry.register(CopilotModel())
    #registry.register(NotebookLMModel())

    for m in registry.all():
        print(f"[INFO] Initializing model: {m.name}")
        m.initialize(documents)
        print(f"[INFO] Model {m.name} initialized")

    print(f"[INFO] Initializing Judge")
    judge = GPTJudge(EVALUATION_OPENAI_MODEL)
    judge.initialize(documents)
    asyncio.run(judge.start_prompt())
    print("[INFO] Judge initialized")

    for question_file in sorted(os.listdir(input_dir)):
        try:
            if question_file.endswith(".json"):
                question_path = os.path.join(input_dir, question_file)
                with open(question_path, "r", encoding="utf-8") as f:
                    question_data = json.load(f)

                id_question = question_data.get("ID")
                question = question_data.get("question")
                
                if not id_question or not question:
                    print(f"[INFO] {id_question} - Skipped")
                    continue
                
                final_results = {}
                
                print(f"[INFO] Generation response for {id_question}: Start")
                
                for model in registry.all():
                    print(f"[INFO] Answer generation for {model.name}: Start")
                    final_results[model.name] = {
                        "answers": {},
                        "claims": {
                            "answers": {},
                            "ground_truth": {}
                        },
                        "evaluation": {},
                        "time": {
                            "generation_time": {},
                            "evaluation_time": {}
                        }
                    }
                    
                    model_start_time = datetime.now()
                    
                    for i in range(1, K + 1):
                        if str(i) in question_data.get(model.name, {}).get("answers", {}):
                            print(f"[INFO] Answer generation for {model.name}: In the File")
                            final_results[model.name]["answers"][str(i)] = "\n".join(question_data[model.name]["answers"][str(i)])
                            
                            if str(i) in question_data[model.name].get("details", {}):
                                final_results[model.name]["details"] = {}
                                final_results[model.name]["details"][str(i)] = question_data[model.name]["details"][str(i)]
                        else:
                            try:
                                result = model.query(question)
                                if isinstance(result, dict):
                                    final_results[model.name]["answers"][str(i)] = result["content"] if "content" in result else ""
                                    final_results[model.name]["details"] = {}
                                    final_results[model.name]["details"][str(i)] = result
                                else:
                                    final_results[model.name]["answers"][str(i)] = result
                                print(f"[INFO] Answer generation for {model.name}: Done")
                            except Exception as e:
                                final_results[model.name]["answers"][str(i)] = ""
                                print(f"[INFO] Answer generation for {model.name}: Error {e}")
                    
                    print(f"[INFO] Claims generation for {model.name}: Start")
                    for i in range(1, K + 1):
                        if str(i) in question_data.get(model.name, {}).get("claims", {}).get("answers", {}):
                            print(f"[INFO] Claims generation for {model.name}: In the File")
                            final_results[model.name]["claims"]["answers"][str(i)] = question_data[model.name]["claims"]["answers"][str(i)]
                        else:
                            try:
                                final_results[model.name]["claims"]["answers"][str(i)] = asyncio.run(judge.extract_claims(final_results[model.name]["answers"][str(i)]))
                                print(f"[INFO] Claims generation for {model.name}: Done")
                            except Exception as e:
                                final_results[model.name]["claims"]["answers"][str(i)] = []
                                print(f"[INFO] Claims generation for {model.name}: Error {e}")
                            
                    model_response_time = datetime.now()
                    final_results[model.name]["time"]["generation_time"] = {
                        "start": model_start_time,
                        "end": model_response_time,
                        "delta": (model_response_time - model_start_time).total_seconds()
                    }
                
                print(f"[INFO] Generation for {id_question}: End")
                
                '''print(f"[INFO] Evaluation {id_question}: Start")
                
                ground_truth_dict = question_data.get("ground_truth", {})
                for annotator in ground_truth_dict:
                    print(f"[INFO] Annotator {annotator}: Start")
                    
                    ground_truth = ground_truth_dict.get(annotator, None)
                    #ground_truth = ground_truth[-1] if ground_truth else None

                    if not ground_truth:
                        print(f"[INFO] {id_question} - Skipped")
                        continue
                    
                    ground_truth = str(ground_truth)

                    ground_truth_claim = None
                    for model in registry.all():
                        if annotator in question_data.get(model.name, {}).get("claims", {}).get("ground_truth", {}):
                            c = question_data[model.name]["claims"]["ground_truth"][annotator]
                            if isinstance(c, list):
                                ground_truth_claim = c
                                break
                    
                    if not ground_truth_claim:
                        ground_truth_claim = asyncio.run(judge.extract_claims(ground_truth))
                    
                    for model in registry.all():
                        final_results[model.name]["claims"]["ground_truth"][annotator] = ground_truth_claim
                        
                        model_evaluation_start_time = datetime.now()
                        
                        answers = final_results[model.name]["answers"]
                        answers_claims = final_results[model.name]["claims"]["answers"]
                        
                        if answers and answers_claims:
                            try:
                                final_results[model.name]["evaluation"][annotator] = asyncio.run(judge.judge(question, answers, ground_truth, answers_claims, ground_truth_claim))
                                print(f"[INFO] Evaluation for {model.name}: Done")
                            except Exception as e:
                                final_results[model.name]["evaluation"][annotator] = {}
                                print(f"[INFO] Evaluation for {model.name}: Error {e}")
                        else:
                            final_results[model.name]["evaluation"][annotator] = {}
                            print(f"[INFO] Evaluation for {model.name}: Skipped")
                        model_evaluation_end_time = datetime.now()
                        
                        final_results[model.name]["time"]["evaluation_time"][annotator] = {
                            "start": model_evaluation_start_time,
                            "end": model_evaluation_end_time,
                            "delta": (model_evaluation_end_time - model_evaluation_start_time).total_seconds()
                        }
                        
                        time.sleep(10)
                        
                    print(f"[INFO] Annotator {annotator}: End")'''
                
                for model in registry.all():
                    for i in final_results[model.name]["answers"]:
                        final_results[model.name]["answers"][i] = str(final_results[model.name]["answers"][i]).split("\n")
                
                question_data.update(final_results)
                output_path = os.path.join(output_dir, question_file)
                with open(output_path, "w", encoding="utf-8") as o:
                    json.dump(question_data, o, ensure_ascii=False, indent=4, default=serialize)

                print(f"[INFO] Question {id_question} saved to {output_path}")
        except Exception as e:
            print(f"[ERROR] File {question_file}: {e}")

    global_end_time = datetime.now()
    print(f"[TIME] Global end: {global_end_time}")
    print(f"[INFO] Total execution time: {(global_end_time - global_start_time).total_seconds()} seconds")
    print("[INFO] Evaluation Done!")

if __name__ == "__main__":
    evaluation()
