import os
from datetime import datetime, timezone

from copy import deepcopy

from bot.utils.config import Config
from bot.utils.file_manager import write_file

from bot.preprocessor.preprocessor import Preprocessor
from bot.translator.translator import Translator
from bot.planner.planner import Planner
from bot.executor.executor import Executor

class Assistant():
    # Load the global configuration
    CFG = Config.get_instance()

    # Initialize components
    preprocessor = Preprocessor(CFG)
    planner = Planner(CFG)
    translator = Translator(CFG)
    executor = Executor(CFG)

    logger = CFG.get_logger("Assistant")

    def chat(self, prompt: str):
        # Log start of chat processing
        self.logger.info(f"Request Received: \"{prompt}\"")
        
        # Save id request
        timestamp = str(datetime.now(timezone.utc).isoformat())
        request_id = f"{str(self.CFG.user_id)}_{timestamp}".replace(":", "").replace(".", "")
        
        try:
            # Step 1: Preprocessing
            # Input: query
            # Output: clean version of the query
            self.logger.info("Step 1 (Preprocessing): Starting")
            
            prompt = self.preprocessor.process(prompt)
            
            self.logger.info("Step 1 (Preprocessing): Done")
            
            # Step 2: Translator
            # Input: query
            # Output: structured version of the query
            self.logger.info("Step 2 (Translator): Starting")
            structured_query = self.translator.rewrite(prompt)
            structured_query["id"] = request_id
            self.logger.info("Step 2 (Translator): Done")
            
            self.logger.info("Step 3 (Planner): Starting")
            operations = self.planner.decompose(deepcopy(structured_query))
            self.logger.info("Step 3 (Planner): Done")
            
            for index, operation in enumerate(operations):
                self.logger.info(f"Executing operation ID: {operation.get("id", "")} with command: {operation.get("command", "")}")
                self.logger.info("Step 4 (Executor): Starting")
                operation["order"] = index
                operation["result"], _ = self.executor.generate(operation, operations)
                self.logger.info("Step 4 (Executor): Done")
                
                
            result = operations[-1].get("result", "")
            self.logger.info("Request Completed")
        except Exception as e:
            self.logger.error("Request Failed")
            self.logger.error(e)
            
            structured_query = {}
            operations = []
            result = "Qualcosa è andato storto. Riprova!"
        
        final_response = {
            "id": request_id,
            "structured_input": structured_query,
            "input": prompt,
            "operations": operations,
            "result": result
        }
            
        doc_used = [doc for task in final_response.get("operations", []) for doc in task.get("from", [])]
        final_response["used_documents"] = list(set(doc_used))
        
        self.CFG.storage.write(self.CFG.user_id, final_response)
        write_file(
            os.path.join(self.CFG.project_root, "documents", f"{request_id}.json"), 
            final_response
        )
        
        
        return final_response
    
    def __init__(self):
        pass
    
#i = 1
#for node in nx.topological_sort(query_graph):
#    node_data = query_graph.nodes[node]["data"]
#    
#    node_data["order"] = i
#    
#    self.logger.info(f"Starting subtask {str(i)}/{str(query_graph.number_of_nodes())}: \"{node_data["prompt"]}\"")
#    
#    # Step 2: Rewriting
#    self.logger.info("Step 2 (Rewriting): Starting")
#    node_data["structured_query"] = self.rewriting.rewrite(node_data, user_id)
#    self.logger.info("Step 2 (Rewriting): Done")
#    
#    # Step 3: Retrieval
#    self.logger.info("Step 3 (Retrieval): Starting")
#    doc = self.retrieval.execute(node_data["structured_query"], query_graph, user_id)
#    self.logger.info("Step 3 (Retrieval): Done")
#    
#    # Step 4: Generation
#    self.logger.info("Step 4 (Generation): Starting")
#    node_data["result"], node_data["structured_query"] = self.generator.generate(node_data["structured_query"], doc, node_data["prompt"])
#    self.logger.info("Step 4 (Generation): Done")
#    
#    query_graph.nodes[node]["data"].update(node_data)
#    
#    i += 1
#    
#final_response = {
#    "id": request_id,
#    "input": query,
#    "tasks": [query_graph.nodes[node]["data"] for node in nx.topological_sort(query_graph)],
#    "result": query_graph.nodes[list(nx.topological_sort(query_graph))[-1]]["data"].get("result", "")
#}
#
#doc_used = [doc for task in final_response["tasks"] for doc in task.get("structured_query", {}).get("documents", [])]
#final_response["used_documents"] = list(set(doc_used))
#
#self.CFG.storage.write(user_id, final_response)
#
#file_name = str(final_response["id"]).replace(":", "_").replace(".", "_")
#
#write_file(
#    os.path.join(self.CFG.project_root, "documents", "result", f"{file_name}.json"), 
#    final_response
#)
#
#return final_response["result"]