# DQL
DQL is a language inspired by structured query languages ​​(such as SQL) that defines recurring linguistic commands, for example, Search, Summarize, Compare, Extract, Integrate, to describe the cognitive operations a person performs on documents.
It serves as a conceptual layer between the user and the language models (LLM), helping select and structure prompts consistently with the task at hand (search, synthesis, comparison, etc.), improving the accuracy, efficiency, and usefulness of AI responses.

The goal of this project is to implement a model that converts a natural language query into a DQL query and develop the system that leverages the DQL query to meet user needs.

## System Overview at V0.1

The system is a **modular intelligent assistant** based on a **natural language processing and operation planning pipeline**.
Currently, it supports only **elementary queries**, meaning those containing a single request.

The components of the system are
* **GUI (User Interface):**
  The entry point for the user, who submits a question or command in natural language.

* **Orchestrator:**
  Coordinates all system modules.

  * Receives the user query (*q*).
  * Routes it to the appropriate modules: preprocessing, translation, planning, and execution.
  * Manages data flow (in JSON/dict format, DQL translation, or operational directives).

* **Conversational Memory:** stores previous interactions to maintain dialogue history.

    > The conversational memory does not contribute to building the system’s contextual understanding.

* **Log:** records all operations for monitoring and debugging purposes.

* **Preprocessing**: his module prepares the query before semantic processing.

    * **Spelling Checker:** corrects orthographic errors and normalizes the text.

* **Translator**: converts the natural language query into a **structured representation** (e.g., JSON or DQL). It is composed of 4 modules:
    * **Command Classifier:** Identifies the command type (e.g., *search*, *summarize*, *compare*).
    * **Source Extractor:** Detects the data source or domain of the request.
    * **What Extractor:** Determines the main object of the operation (what needs to be searched or processed).
    * **Condition Extractor:** Identifies constraints or filters (e.g., dates, authors, conditions).

    The output is a structured query representation (DQL / JSON).

* **Planner**: the **operation planning module**. It receives the structured query and generates a sequence of **atomic operations** or **operational directives**, defining their order and dependencies. The output is an execution plan (list of JSON/dicts).

    > Although the current V1 system only supports elementary commands, it has been observed that certain requests can be decomposed into smaller operations that leverage existing command types to improve response quality.

* **Executor**: executes the planned operations, following specific guidelines for each command type. This module also interacts with the **corpus** to perform searches, extractions, comparisons, or summaries.

## Future Improvements

Some features identified for V2 are:

* **Standardization of conditions**: currently, all conditions in the "how" field are represented in plain natural language. To best treat DQL as a manipulation language, it is necessary to represent them in a rigid format.
* **Operations Tool**: currently, the behavior after the translation phase consists of simply retrieving the appropriate document and passing the request to an LLM. Some operations can be implemented as algorithms, resulting in a deterministic and controllable system.
* **Augmentation Phase**: definitions/roles/data can be added.
* **Validator Component**: system for checking whether a query is acceptable
* **Form for uploading documents**
* **Custom Definitions Module**: Especially in a legal context, each judge has his or her own definition of terms.

Some features have already been partially implemented:

* **Support for complex/compound queries**: a system for breaking down the query into a list of subtasks has already been implemented, but disabled. The V1 system would then be repeated for each subtask.
* **Conversation support**: we chose to keep each message independent of the conversation in V1, but in a realistic scenario it is important that the conversation history is part of the context.
* **Evaluator Component**: Query rewriting quality evaluation system

## How to run the code

1.  **Install Dependencies**
    Ensure you have Python and `pip` installed. Run this command from the project root to install all required libraries:
    ```bash
    pip install -r requirements.txt
    ```
2.  **Create .env file**
    In the project's root directory, create the environment file (`.env`):
    
3.  **Credential Configuration**
    You can provide credentials (API key, DB URL, DB Token) in two ways: via configuration files (recommended) or by passing them as flags at runtime.
    
    - **Method 1: Configuration Files (Recommended)**

      - **LLM API Key**
        - Go to the website of the LLM provider you intend to use (e.g., [Google Gemini](https://aistudio.google.com/app/apikey), [OpenAI](https://platform.openai.com/api-keys), etc.).
        - Generate a new API key.
        - Inside the `.env`, create the correct variable between `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `GITHUB_COPILOT_API_KEY`, "HUGGINGFACEHUB_API_TOKEN" and paste the API key
      - **Database Credentials (MongoDB)**
        - Inside the `.env`, create the variables between `MONGO_URI`, `MONGO_INITDB_ROOT_USERNAME`, `MONGO_INITDB_ROOT_PASSWORD`

    - **Method 2: Runtime Flags**
      Alternatively, you can skip creating the variables in the enviroment file and pass the credentials directly at runtime using the `-api`, `-uri_db` flags (see section 4).

4. **VPN Connection for Elasticsearch**: If you need to access the Elasticsearch database, ensure you are connected to your university's VPN before running the script.

5. **Running the Application**
    Execute the Streamlit application using the `main.py` script.
    The base command is:
    ```bash
    python main.py
    ```
    The script accepts several optional flags (arguments) to customize its behavior.

    * `-api <KEY>`

        * **Description:** Provides the API key for the LLM.

    * `-uri_db <URI>`

        * **Description:** Provides the connection URL for the database (e.g., MongoDB).

    * `-provider <PROVIDER_NAME>`

        * **Description:** Specifies which LLM provider to use.
        * **Default:** `google_genai`
        * **Choices:** `google_genai`, `openai`, `copilot`, `huggingface`.

    * `-model_name <MODEL_NAME>`

        * **Description:** Specifies the exact LLM model name to use.
        * **Default:** `gemini-2.0-flash`
        * **Examples:** `gpt-4o-mini`, `claude-3-5-sonnet`, `mistralai/Mistral-7B-Instruct-v0.2`.

    * `-wait_seconds <NUMBER>`

        * **Description:** Sets the number of seconds to wait after each LLM call.
        * **Default:** `5`

    * `-spell_check_without_llm`

        * **Description:** If present, this flag disables the use of the LLM for the spell-checking phase, using an alternative method instead.
        * **Usage:** Just add the flag; it does not require a value

    