import os
import re
import pandas as pd
import requests
import socket
import sys

from pathlib import Path
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Root path of the project (two levels up from this file)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.file_manager import FileHandler
from utils.LLM import LLM
from utils.system_config import SystemConfig

try:
    # Path of the folder where this file is located
    file_root = Path(__file__).resolve().parent

    file_list = []
    for file_name in os.listdir(file_root):
        if str(file_name).endswith('.csv'):
            file_list.append((os.path.join(file_root, file_name),
                              os.path.join(file_root, 'processed', file_name)))

    # API details
    url: str = "http://127.0.0.1:8000/chat"
    headers: dict = {"Content-Type": "application/json"}

    llm = LLM().get_instance()
    config = SystemConfig().get_instance()

    for input_file, output_file in file_list:
        print(f"Processing DOC: {input_file}")
        
        if os.path.exists(input_file) is False:
            raise FileNotFoundError(f"Input file '{input_file}' not found.")

        if os.path.exists(output_file):
            os.remove(output_file)
            
        df = pd.read_csv(input_file, sep=';', encoding='utf-8-sig')

        results = []
        for index, row in df.iterrows():
            id = row['ID']
            query = row['question']
            annotator_answer = eval(row['output'])[-1]
            
            print(f"Processing ID: {id}")
            print(f"Starting model call...")
            # Model Call
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            
            data = {
                "message": query,
                "thread_id": id,
            }
            
            model_answer = requests.post(url, json=data, headers=headers)
            
            if model_answer.status_code == 200:
                model_answer = model_answer.json()
            else:
                model_answer = {}
                
            model_answer = model_answer.get('result', '').strip()
            
            result = {}
            
            print(f"Model call completed.")
            
            if model_answer:
                print(f"Answer from the model obtained. Starting evaluation...")
                # Evaluation
                template = read_file(os.path.join(file_root, "prompt", "evaluation.json"))
                template["system"] = "\n".join(template["system"]).strip()
                template["human"] = "\n".join(template["human"]).strip()
                
                prompt = ChatPromptTemplate.from_messages(
                            [("system", template["system"]), ("human", template["human"])]
                        )

                # Build chain and invoke
                chain = prompt | llm.llm | StrOutputParser()
                result = chain.invoke({"truth_answer": annotator_answer, "model_answer": model_answer})
                
                result = llm.str_in_dict(result)
                print(f"Evaluation completed.")
            else:
                print(f"No answer from the model.")
            
            # Result Saving
            results.append({
                'ID': id,
                'question': query,
                'annotator_answer': re.sub(r"\n", r"\\n", annotator_answer),
                'model_answer': re.sub(r"\n", r"\\n", model_answer),
                'feasibility': row['feasibility'],
                'accuracy_rating': result.get('accuracy_rating', ""),
                'accuracy_comment': re.sub(r"\n", r"\\n", result.get('accuracy_comment', "")),
                'completeness_rating': result.get('completeness_rating', ""),
                'correctness_comment': re.sub(r"\n", r"\\n", result.get('correctness_comment', ""))
            })
        
        df_results = pd.DataFrame(results)
        df_results.to_csv(output_file, index=False, sep=';', encoding='utf-8-sig')
except requests.exceptions.ConnectionError:
    print("Connection error. You may need to start the System server.")
except FileNotFoundError as e:
    print(e)