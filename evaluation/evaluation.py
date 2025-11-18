import os
import re
import pandas as pd
import sys
import time
import winsound

from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Root path of the project (two levels up from this file)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from logic.orchestrator import Orchestrator
from utils.file_manager import FileHandler

try:
    # Path of the folder where this file is located
    file_root = Path(__file__).resolve().parent

    file_list = []
    for file_name in os.listdir(file_root):
        if str(file_name).endswith('.csv'):
            file_list.append((os.path.join(file_root, file_name),
                              os.path.join(file_root, 'processed', file_name),
                              file_name))
    
    assistant = Orchestrator("evaluator")
    llm = assistant.get_cfg().llm

    for input_file, output_file, file_name in file_list:
        print(f"Processing DOC: {file_name}")
        
        if os.path.exists(input_file) is False:
            raise FileNotFoundError(f"Input file '{input_file}' not found.")

        if os.path.exists(output_file):
            os.remove(output_file)
            
        df = pd.read_csv(input_file, sep=';', encoding='utf-8-sig')

        results = []
        for index, row in df.iterrows():
            try:
                id = row['ID']
                query = row['question']
                annotator_answer = eval(row['output'])[-1]
                
                print(f"Processing ID: {id}")
                print(f"Starting model call...")
                    
                assistant_result = assistant.chat(query)
                model_answer = assistant_result.get("result", "")
                
                result = {}
                
                print(f"Model call completed.")
                
                time.sleep(20)
                
                if model_answer:
                    print(f"Answer from the model obtained. Starting evaluation...")
                    # Evaluation
                    template = FileHandler().read_file(os.path.join(file_root, "prompt", "evaluation.json"))
                    template["system"] = "\n".join(template["system"]).strip()
                    template["human"] = "\n".join(template["human"]).strip()
                    
                    prompt = ChatPromptTemplate.from_messages(
                                [("system", template["system"]), ("human", template["human"])]
                            )

                    # Build chain and invoke
                    chain = prompt | llm._llm | StrOutputParser()
                    result = chain.invoke({"truth_answer": annotator_answer, "model_answer": model_answer})
                    
                    result = llm.str_in_dict(result)
                    print(f"Evaluation completed.")
                else:
                    print(f"No answer from the model.")
                
                
                final_result = {
                    'ID': id,
                    'question': query,
                    'annotator_answer': re.sub(r"\n", r"\\n", annotator_answer),
                    'model_answer': re.sub(r"\n", r"\\n", model_answer),
                    'model_input': str(assistant_result.get("structured_input", {})),
                    'feasibility': row['feasibility'],
                    'accuracy_rating': result.get('accuracy_rating', -1),
                    'accuracy_comment': re.sub(r"\n", r"\\n", result.get('accuracy_comment', "")),
                    'completeness_rating': result.get('completeness_rating', -1),
                    'completeness_comment': re.sub(r"\n", r"\\n", result.get('correctness_comment', ""))
                }
                
                # Result Saving
                results.append(final_result)
                FileHandler().write_file(os.path.join("evaluation", "processed", f"{file_name} - {str(index)}.json"), final_result)
                
                time.sleep(20)
                winsound.Beep(1000, 500)
            except Exception:
                continue
        
        df_results = pd.DataFrame(results)
        df_results.to_csv(output_file, index=False, sep=';', encoding='utf-8-sig')
except FileNotFoundError as e:
    print(e)