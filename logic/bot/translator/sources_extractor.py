import re

from utils.config import Config
from utils.DQL_language import DQLLanguage

class SourcesExtractor:
    """
    Extracts relevant sources/documents from a user query using an LLM.

    Responsibilities:
        - Prepare the list of available sources for the LLM.
        - Invoke the LLM to select sources relevant to the query.
        - Provide a fallback to all sources if extraction fails.
        - Log extraction results for traceability.
    """
    
    # ----------------------
    # --- Initialization ---
    # ----------------------

    def __init__(self, cfg: Config):
        """
        Initialize the SourcesExtractor with configuration and dependencies.

        Args:
            cfg (Config): Global configuration object providing logger, LLM, and DQL language data.
        """
        self._llm = cfg.llm
        self._storage = cfg.storage
        self._logger = cfg.get_logger("Sources Extractor")
        self._project_root = cfg.project_root
        self._dql_language: DQLLanguage = cfg.language

    # ------------------------------
    # --- Main Extraction Method ---
    # ------------------------------
    
    def get_chat_history(self, user_id, chat_id) -> list:
        return [
            {
                "id": chat.get("id", ""), 
                "prompt": chat.get("details", {}).get("prompt", ""), 
                "used_documents": chat.get("details", {}).get("used_documents", []),
                "content": chat.get("content", "")
            }
            for chat in self._storage.get_chat_messages(user_id, chat_id)
            if "details" in chat
        ]
    
    def extract(self, query: str, user_id, chat_id, tasks_id: list = None) -> list:
        status = "Error"
        try:
            chat = self.get_chat_history(user_id, chat_id)
            
            documents = self._explicit_documents_extraction(query) 
            
            if chat:
                documents += self._implicit_documents_extraction(query, chat) 
            
            if "#" in query and tasks_id:
                documents += self._task_id_extraction(query, tasks_id)
            
            documents = [d for d in documents if not str(d[0]).startswith("#")]
            
            if not documents:
                if chat:
                    documents = [[chat[-1]["id"], "risposta precedente"]]
                else:
                    raise ValueError("No Reference Found")
            
            status = "Done"
        except Exception as e:
            # Fallback: return all available sources
            self._logger.error(e)
            documents = [[src["name"], src["name"]] for src in self._dql_language.get_sources()]
            
        # Log the extraction result
        self._logger.info(f"{documents} - {status}")
        
        return documents
    
    def parsing(self, query, base_list, tasks_id: list = None):
        sources_list = []
        
        if not query:
            return None
        
        if "#" in query:
            sources_list += self._task_id_extraction(query, tasks_id)
            
        for b in base_list:
            if b[0] in query:
                sources_list.append([b[0], b[0]])
            elif b[1] in query:
                sources_list.append(b)
        
        return sources_list
    
    def _explicit_documents_extraction(self, query: str) -> list:
        """
        Extract relevant sources/documents from a user query.

        Steps:
            1. Prepare the query and list of available sources.
            2. Call the LLM to identify relevant documents.
            3. Convert LLM output into a list of document names.
            4. Fallback to all available sources if extraction fails.

        Args:
            query (str): User input query to extract sources from.

        Returns:
            list: List of document/source names deemed relevant.
        """
        # Retrieve the specific prompt for 'sources' extraction
        prompt = self._dql_language.prompts.get("ExplicitDocumentsExtraction.json", None)
        
        if not prompt:
            raise ValueError("ExplicitDocumentsExtraction.json prompt not found.")
        
        if query.strip():
            # Invoke LLM to extract from query
            documents = self._llm.invoke(
                prompt,
                { "query": query },
                True
            )
            
            # Log the extraction result
            self._logger.info(f"Explicit Documents: {documents}")
            
            return documents
        else:
            raise ValueError("Empty query provided to ExplicitDocumentsExtraction.")
    
    def _implicit_documents_extraction(self, query, chat) -> list:
        query_dict = {
            "query": query,
            "chat": str(chat)
        }

        # Retrieve the specific prompt for 'sources' extraction
        prompt = self._dql_language.prompts.get("ImplicitDocumentsExtraction.json", None)
        
        if not prompt:
            raise ValueError("ImplicitDocumentsExtraction.json prompt not found.")
        
        if query_dict.get("query", "").strip():
            # Invoke LLM to extract from query
            documents = self._llm.invoke(
                prompt,
                query_dict,
                True
            )
            
            # Log the extraction result
            self._logger.info(f"Implicit Documents: {documents}")
            
            return documents
        else:
            raise ValueError("Empty query provided to ImplicitDocumentsExtraction.")
    
    
    def _task_id_extraction(self, query: str, ids) -> list:
        found_ids = [int(x) for x in re.findall(r"#(\d+)", query)]
        documents = [[ids[i - 1], f"#{i}"] for i in found_ids if i <= len(ids)]
        
        # Log the extraction result
        self._logger.info(f"Previous Tasks: {documents}")
        
        return documents