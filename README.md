# DQL
DQL is a language inspired by structured query languages ​​(such as SQL) that defines recurring linguistic commands, for example, Search, Summarize, Compare, Extract, Integrate, to describe the cognitive operations a person performs on documents.
It serves as a conceptual layer between the user and the language models (LLM), helping select and structure prompts consistently with the task at hand (search, synthesis, comparison, etc.), improving the accuracy, efficiency, and usefulness of AI responses.

The goal of this project is to implement a model that converts a natural language query into a DQL query and develop the system that leverages the DQL query to meet user needs.

## System Overview at V1

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

## How to Run the Code

To run this project, follow these steps:

1. Install dependencies
```bash
pip install *r requirements.txt
```
2. Create a folder named `settings` in the root of the project
3. Create `api_key.txt`, `url_redis.txt`, `token_redis.txt` and put into `settings`
4. Go to the [Gemini API website](https://aistudio.google.com/app/apikey)
5. Generate a new API key.
6. Copy the generated key and paste it into `api_key.txt`.
7. Go to the [Upstash Redis website](https://console.upstash.com/)
8. Create a DB
9. Place the upstash-redis URL and token in the `url_redis.txt` and `token_redis.txt` files respectively.
10. If you wanna access the Elasticsearch database make sure you are connected to your university's VPN. 
11. Run streamlit.
```bash
streamlit run app.py **server.fileWatcherType=none
```