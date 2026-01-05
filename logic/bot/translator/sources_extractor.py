import re

from utils.config import Config
from utils.DQL_language import DQLLanguage

class SourcesExtractor:
    """
    Identifies and retrieves relevant document sources from user queries.

    This component implements a multi-strategy retrieval logic:
    1. Explicit: Direct mentions in the query.
    2. Contextual: Parsing task IDs (#1, #2) or previous message IDs.
    3. Implicit: Leveraging chat history and LLM reasoning to infer missing context.

    Responsibilities:
        - Parsing chat history to maintain document continuity.
        - Executing LLM-based extraction for explicit and implicit references.
        - Mapping task identifiers (#) to actual document objects.
        - Providing a robust fallback to all available sources upon failure.
    """
    
    # ----------------------
    # --- Initialization ---
    # ----------------------

    def __init__(self, cfg: Config):
        """
        Initialize the SourcesExtractor with system configuration.

        Args:
            cfg (Config): Global configuration providing LLM access, storage, 
                          logging, and session-specific chat history.
        """
        self._llm = cfg.get_LLM()
        self._storage = cfg.get_storage()
        self._logger = cfg.get_logger("Sources Extractor")
        self._project_root = cfg.project_root
        self._dql_language: DQLLanguage = cfg.get_DQL()
        
        # Cache of valid source names defined in the DQL language
        self._src_names = [src["name"] for src in self._dql_language.get_sources()]
        
        self.get_chat_history = cfg.get_chat_history

    # ------------------------------
    # --- Main Extraction Method ---
    # ------------------------------
        
    def get_last_used_sources(self, chat_history: list) -> list[str]:
        """
        Traverses the chat history in reverse to identify the most recently used sources.
        
        This maintains context across multiple turns by assuming that if a user 
        doesn't specify a source, they are likely referring to the last one discussed.

        Args:
            chat_history (list): List of message objects from the current session.

        Returns:
            list[str]: A list of source names found in the latest valid assistant response.
        """
        # Iterate from the most recent message back to the start
        for message in reversed(chat_history):
            used_documents = message.get("used_documents", [])

            # Normalize and deduplicate source names from the message metadata
            used_source_names = set()
            for doc in used_documents:
                if isinstance(doc, str):
                    used_source_names.add(doc)
            
            used_source_names = list(used_source_names)
            
            # Intersection: ensure inferred sources are valid within the current DQL schema
            matching_sources = [
                src for src in self._src_names if src in used_source_names
            ]

            if matching_sources:
                return matching_sources

        return []

    def extract(self, query: str, tasks_id: list = None) -> list:
        """
        Orchestrates the document extraction pipeline.
        
        The method attempts various extraction strategies in sequence, accumulating 
        results from explicit mentions, chat context, and specific task IDs (#).

        Args:
            query (str): The natural language input from the user.
            tasks_id (list, optional): List of IDs for previously generated tasks in the session.

        Returns:
            list: A list of relevant document references or a fallback list of all sources.
        """
        status = "Error"
        try:
            chat = self.get_chat_history()
            
            # Strategy 1: Look for direct names of documents in the query text
            documents = self._explicit_documents_extraction(query) 
            
            # Strategy 2: Check if the query mentions specific message IDs from history
            if chat:
                documents += self._previous_message_parsing(query, chat)
            
            # Strategy 3: Handle task-specific references like "Compare with #1"
            if "#" in query and tasks_id:
                documents += self._task_id_parsing(query, tasks_id)
            
            # Filter out any lingering internal task references (starting with #)
            documents = [d for d in documents if not str(d[0]).startswith("#")]
            
            # Strategy 4: If no documents found, use parsing and LLM to infer context from chat history
            if not documents:
                documents = self._documents_parsing(query)
                
                if (not documents) and chat:
                    documents = self._implicit_documents_extraction(query, chat)
                    
                if not documents:
                    raise ValueError("No Reference Found")
            
            status = "Done"
            
        except Exception as e:
            # Fallback Logic: Return all available sources to prevent pipeline failure
            self._logger.error(f"Sources extraction failed: {e}")
            documents = [[src, src] for src in self._src_names]
            
        # Audit log for the extraction outcome
        self._logger.info(f"Final Source Selection: \"{query}\" -> {documents} ({status})")
        
        return documents
    
    def _explicit_documents_extraction(self, query: str) -> list:
        """
        Uses LLM to identify document names directly mentioned in the query.
        """
        prompt = self._dql_language.prompts.get("ExplicitDocumentsExtraction.json", None)
        
        if not prompt:
            raise ValueError("ExplicitDocumentsExtraction.json prompt template missing.")
        
        if query.strip():
            # LLM selects names from the predefined DQL source list
            documents = self._llm.invoke(
                prompt,
                { "query": query },
                True # Process output as structured data
            )
            
            self._logger.info(f"Explicit Documents found: {documents}")
            return documents
        else:
            raise ValueError("Empty query string.")
    
    def _implicit_documents_extraction(self, query: str, chat: list) -> list:
        """
        Analyzes the chat context to infer which documents the user is referring to
        when no explicit mentions are present.
        """
        # Get context from the previous turn
        current_doc = self.get_last_used_sources(chat)
        self._logger.info(prompt)
        if not current_doc:
            current_doc_info = ""
        else:
            current_doc_info = f"Tieni in considerazione che gli eventuali documenti correnti sono: {', '.join(current_doc)}"
        
        query_dict = {
            "query": query,
            "chat": "\n".join([str(m) for m in chat]),
            "current_doc_info": current_doc_info
        }

        prompt = self._dql_language.prompts.get("ImplicitDocumentsExtraction.json", None)
        
        if not prompt:
            raise ValueError("ImplicitDocumentsExtraction.json prompt template missing.")
        
        if query_dict.get("query", "").strip():
            # LLM performs semantic inference using chat history
            documents = self._llm.invoke(
                prompt,
                query_dict,
                True
            )
            
            self._logger.info(f"Implicit Documents inferred: {documents}")
            return documents
        else:
            raise ValueError("Empty query string.")
    
    def _previous_message_parsing(self, query: str, chat: list) -> list:
        """
        Parses the query for direct mentions of previous message UUIDs.
        """
        ids = [msg["id"] for msg in chat]
        
        # Simple string matching for message IDs
        documents = [[msg_id, msg_id] for msg_id in ids if msg_id.lower() in query.lower()]
        
        self._logger.info(f"Message ID references found: {documents}")
        return documents
    
    def _documents_parsing(self, query: str) -> list:
        """
        Parses Documents Label.
        """
        documents = [[src, src] for src in self._src_names if src.lower() in query.lower()]
        
        self._logger.info(f"Documents parsing: {documents}")
        return documents
    
    def _task_id_parsing(self, query: str, ids: list) -> list:
        """
        Parses task identifiers (e.g., #1, #2) and maps them to actual IDs.
        """
        # Regex to find patterns like '#1', '#2', etc.
        found_ids = [int(x) for x in re.findall(r"#(\d+)", query)]
        
        # Map human-readable index (1-based) to list index (0-based)
        documents = [[ids[i - 1], f"#{i}"] for i in found_ids if i <= len(ids)]
        
        self._logger.info(f"Task ID references (#) found: {documents}")
        return documents