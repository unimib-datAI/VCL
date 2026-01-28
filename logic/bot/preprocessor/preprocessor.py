from logic.bot.preprocessor.rephraser import Rephraser
from logic.bot.preprocessor.decomposer import Decomposer
from utils.config import Config


class Preprocessor:
    """
    Orchestrates the initial cleaning and structural preparation of user queries.

    This class serves as the first stage of the DQL pipeline. It ensures that 
    the input is linguistically correct and contextually complete before 
    breaking it down into executable sub-tasks.

    Responsibilities:
        - Rectify typos and grammatical errors in new sessions.
        - Resolve contextual references (anaphora) in ongoing chats.
        - Normalize text for consistent internal processing.
        - Decompose complex requests into a sequence of atomic tasks.
    """
    
    # ----------------------
    # --- Initialization ---
    # ----------------------

    def __init__(self, cfg: Config):
        """
        Initialize the Preprocessor with specialized sub-modules.

        Args:
            cfg (Config): Global configuration instance providing logging, 
                          storage access, and LLM handles.
        """
        self._logger = cfg.get_logger("Preprocessor")
        self._decomposer_class = Decomposer(cfg)
        self._rephraser_class = Rephraser(cfg)
        self._storage = cfg.get_storage()
        
        # Helper function to retrieve the current conversation history
        self.get_chat_history = cfg.get_chat_history

    # -----------------------------------
    # --- Main Preprocessing Pipeline ---
    # -----------------------------------

    def process(self, query: str) -> tuple:
        """
        Executes the full preprocessing workflow on a raw user string.

        The pipeline dynamically adapts based on session history:
            1. If NEW SESSION: Applies spelling/grammar correction.
            2. If EXISTING CHAT: Rephrases the query to include previous context.
            3. Normalization: Converts text to lowercase.
            4. Decomposition: Splits the query into a structured list of tasks.

        Args:
            query (str): The raw string input from the user interface.

        Returns:
            tuple: A tuple containing (normalized_query, list_of_tasks), 
                   where list_of_tasks contains dictionaries ready for translation.
        
        Raises:
            Exception: If the input query is empty or not a valid string.
        """
        if not query or not isinstance(query, str):
            raise Exception("Received empty or invalid query during preprocessing.")
        
        # Retrieve context to decide between correction or rephrasing
        chat = self.get_chat_history()
        
        if not chat:
            chat = None
        
        # PHASE 1: Contextual expansion for ongoing conversations
        self._logger.info("Initiating contextual rephrasing.")
        corrected_query = self._rephraser_class.rephrase(query, chat)
        self._logger.info("Query rephrasing completed.")

        # PHASE 2: Text Normalization
        # Lowercasing helps standardizing the input for the DQL keyword matching
        normalized_query = corrected_query.lower()
        
        # PHASE 3: Structural Decomposition
        # Breaking the complex prompt into atomic, interdependent tasks
        self._logger.info("Starting query decomposition into atomic tasks.")
        prompts = self._decomposer_class.decompose(normalized_query)
        self._logger.info("Query decomposition completed.")

        return normalized_query, prompts