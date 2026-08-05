# VCL — Verbal Command Language

VCL (Verbal Command Language) is a structured, extensible query language designed to describe *cognitive operations* a human performs on documents. Think of it as a semantics-first abstraction layer between natural language and the concrete operations performed on legal/technical documents: **search**, **summarize**, **extract**, **compare**, **integrate**, **verify**, and so on.

The project implements the following core modules:

* Preprocessor: Converts Natural Language (NL) input into a Directed Acyclic Graph (DAG), subsequently transforming it into a list of tasks in NL to guide the execution.
* Translator: A translator from natural language → VCL/JSON.
* Planner: Turns structured VCL into an ordered execution plan, managing dependencies between operations.
* Executor: Runs atomic operations against a document corpus using LLMs and deterministic tools where appropriate.
* GUI: A Streamlit-based interface for interactive usage.
* Storage & LLM Layer: Storage integrations (MongoDB/Elasticsearch) and a configurable multi-provider LLM layer.
* Evaluation Script: Includes a dedicated evaluation script to assess system performance, accuracy, and reliability across the workflow.

The system is intentionally **modular** so components can be swapped (different LLM providers, plug-in deterministic tools, alternative UIs).

# 1. Features

This section explains, in depth, what VCL provides now (V0.2) and what it intends to provide.

* **Structured cognitive primitives**
  A catalog of atomic operations (e.g., `search`, `summarize`, `extract semantic`, `extract logical`, `compare`, `integrate`, `verify`, `classify`, `reorganize`) with deterministic semantics and operational guidelines. Commands are configured in a single JSON language file so the semantics are explicit and editable.

* **Natural Language → VCL translation**
  The translator subsystem converts user NL queries into a structured VCL representation (JSON). This representation captures `command`, `what`, `source`, `conditions`, and optional `parameters`.

* **Operation planner**
  A planner maps a VCL representation into an ordered list of atomic operations (an execution plan). The planner resolves dependencies and can break some commands into multiple sub-operations when beneficial.

* **LLM-guided execution**
  Execution primarily uses a LLM for tasks. In Future, deterministic tools or algorithmic routines will be used (e.g., exact reference extraction, regex-based monetary extraction) where possible.

* **Command-specific behavior & constraints**
  Each VCL command has a specific set of operational guidelines (for example, `search` must return verbatim text snippets only, no paraphrase; `summarize` must be a conceptual rewrite). These guidelines are enforced by the executor.

* **Streamlit GUI**
  Lightweight web UI for interactive queries, document uploads, and result visualization.

* **Document DB integrations**
  Built to work with MongoDB and Elasticsearch; 
  ! Document upload and indexing have not been implemented yet.

* **Logging & monitoring**
  Full logging of translation, planning and execution phases for auditability and debugging.

* **Conversation memory**
  Keeps a history of interactions (V.1: stored but not used to influence understanding by default).

* **Editable configuration**
  VCL possible sources, and the `what` types are defined in a config JSON that can be edited by GUI.

# 2. Supported VCL Commands

Below is a compact reference of the supported commands. Each command entry summarizes the intent and the key operational guidelines the executor follows.

### Commands

* **`search` (`cerca`)** — Conceptual search for entities, legal concepts, or snippets.

  * Output: verbatim excerpts only (no paraphrase), only snippets that directly answer the query.
  * Use: find references, parties, locations, monetary amounts, precedent citations.

* **`summarize` (`riassumi`)** — Concise, autonomous summary preserving key facts, arguments and dispositive.

  * Output: new text (rewritten) capturing facts, relevant arguments, device; no verbatim copy of entire sections.

* **`extract semantic` (`estrai semantico`)** — Extract semantically coherent sections (facts, reasons, devices).

  * Output: focused sections, reformulated for clarity but preserving conceptual content.

* **`extract logical` (`estrai logico`)** — Reconstruct argumentation chain (sillogisms, premises→conclusion).

  * Output: stepwise mapping of premises, intermediate inferences, and conclusion(s). Reformulation allowed to clarify logical structure.

* **`compare` (`confronta`)** — Comparative analysis across documents, highlighting agreements and divergences.

  * Output: grouped concordances and discordances, optionally short textual citations as evidence.

* **`integrate` (`integra`)** — Merge multiple documents into a consolidated single text.

  * Output: consolidated text where duplicates are removed, conflicts are flagged or resolved under chosen policy.

* **`verify` (`verifica`)** — Consistency and reference checking (legal citations, internal contradictions).

  * Output: report of anomalies (incorrect citations, logical inconsistencies). No opinions on merits.

* **`analyze` (`analizza`)** — Structural decomposition and evaluation of completeness and argumentative robustness.

  * Output: an analytic report mapping sections, evaluating completeness and logical support.

* **`reorganize` (`riorganizza`)** — Re-order sections according to a chosen criterion (chronological, topical).

  * Output: restructured text with preserved unit content.

* **`classify` (`classifica`)** — Tag portions of text with legal function labels (e.g., petition, counterclaim, dispositive).

  * Output: mapping of text spans → labels.

* **`other` (`altro`)** — Fallback for intentions not covered by predefined commands.

  * Output: best-effort response that may combine behaviors from other commands.

# 3. Architecture

The system was designed as a modular pipeline with clear separation of concerns.

![architecture](documents/images/system.png)

# 4. Descriptions of main components

This section provides a compact but detailed description of each major component of execution

### GUI — Streamlit App

* **Role:** User entry point. Query entry, document upload, view results.
* **Implementation:** Streamlit + minimal front-end logic; calls orchestrator API or runs in-process.
* **LLM-based:** **No** (UI only; however, it can display LLM results).

### Orchestrator

* **Role:** Central coordinator. Receives user requests and routes them through preprocessing, translation, planning and execution steps. Responsible for format conversions (NL → JSON/DQL, JSON → plan).
* **Implementation:** Python service with modular plugs for each pipeline stage.
* **LLM-based:** **No**.

### Preprocessing

* **Role:** Normalize text (lowercasing where needed), perform spellchecking/normalization, sanitize input.
* **Implementation:** Two modes:

  * LLM-based spelling correction (default) — uses an LLM to correct typos and preserve intent.
  * Rule-based or dictionary-based fallback when `-parsers` is set.
* **LLM-based:** **Optional** (default yes, configurable).

### Translator (NL → VCL)

* **Role:** Convert an NL query to a VCL JSON structure with fields such as `command`, `what`, `source`, `conditions`, `params`.
* **Submodules (all LLM-based):**

  1. **Command Classifier:** chooses the best-matching VCL command.
  2. **Source Extractor:** identifies which document sources are relevant (sentenza 1°, memoria, ricorso).
  3. **What Extractor:** determines the object of operation (e.g., `fact`, `decision`, `precedent`, `sillogism`).
  4. **Condition Extractor:** pulls filters (dates, parties, jurisdiction).
* **LLM-based:** **Yes**. Each component takes as input the NL query and possibly the results of the previous steps.

### Planner

* **Role:** Convert VCL JSON into an ordered plan of atomic operations. Resolve dependencies and split complex requests into sub-operations when needed.
* **Implementation:** Rule engine plus a planner algorithm that maps VCL -> sequence of tasks (JSON list).
* **LLM-based:** **No** (deterministic planning logic).

### Executor

* **Role:** Executes the plan. For each atomic operation, invokes the appropriate tool:

  * Deterministic functions: regex extraction, citation parsing, DB queries.
  * LLM-invocations for summarization, logical reconstruction, paraphrasing, synthesis.
* **Behavior:** The executor enforces the operational guidelines for each command (e.g., `search` returns verbatim snippets).
* **LLM-based:** **Yes** It takes as input the information that can be obtained from the language configuration and the user's VCL request.

### Databases (Document Corpus)

* **Role:** Store and serve documents/history chat to the executor/GUI.
* **Implementation:** MongoDB/Elasticsearch

Here is the corrected and fully translated version of your README section. The formatting has been improved, the Italian text has been translated to English, and typos/inconsistencies have been fixed for a more professional tone.

***

# 5. Installation

## 1) Clone repository

```bash
git clone https://github.com/unimib-datAI/VCL.git
cd VCL
```

## 2) Python environment

```bash
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
.\.venv\Scripts\activate     # Windows
```

## 3) Install dependencies

```bash
pip install -r requirements.txt
```

## 4) Create `.env` file

Create a `.env` file in the repo root with the variables you need. A `.env.example` file is provided as a reference with the main parameters.

`MONGO_INITDB_ROOT_USERNAME` and `MONGO_INITDB_ROOT_PASSWORD` are the credentials used by Docker to initialize the MongoDB root user **the first time the container is created** (i.e. when `./data` is empty). `MONGO_URI` is the connection string the application uses to talk to that same database, so it must embed those same credentials and point at the host-mapped port (`27019`, see `docker-compose.yml`), for example:

```
MONGO_INITDB_ROOT_USERNAME=vcl_admin
MONGO_INITDB_ROOT_PASSWORD=<a-strong-password>
MONGO_URI=mongodb://vcl_admin:<a-strong-password>@localhost:27019/?authSource=admin
```

**NB**: if you change these credentials *after* the container has already been initialized once, MongoDB will **not** pick them up automatically — the root user already exists with the old credentials. Either wipe `./data` and let Docker re-initialize, or connect with the existing credentials and update/create the user manually (e.g. via `docker exec -it dql-mongodb mongo admin -u <old_user> -p <old_pass>`).

## 5) Insert corpus files

You must store your documents in the `documents/corpus` directory. The directory should be structured as follows:

```text
VCL
├── ...
├── documents
│   ├── ...
│   └── corpus
│       ├── <name_corpus_1>
│       │   ├── <file_1>.json
│       │   ├── <file_2>.json
│       │   ├── ...
│       │   └── <file_n>.json
│       ├── <name_corpus_2>
│       ├── ...
│       └── <name_corpus_m>
└── ...
```

Download the *Vitali + Salomone + UDA* corpus at the following link (available only with a UniMiB account): [Drive Link](https://drive.google.com/file/d/1Y70yRqSiD-8TTFILIej9CetEX-f41dpG/view?usp=sharing)

Alternatively, custom individual JSON files must have the following structure:

```json
{
  "type_doc": "<label_present_in_the_ontology>",
  "text": "<document_text>",
  "name": "<file_name>",
  "owner": "<user_with_access>"
}
```

For evaluations, inside the `scripts/evaluation/questions` directory, you must have two folders:
*   `input`: Place the JSON files containing the questions here.
*   `output`: The directory where the scripts will save the results.

```text
VCL
├── ...
├── scripts
│   ├── ...
│   └── evaluation
│       ├── ...
│       ├── questions
│       │   ├── input
│       │   |   ├── <file_1>.json
│       │   |   ├── <file_2>.json
│       │   |   ├── ...
│       │   |   └── <file_n>.json
│       │   └── input
│       └── ...
└── ...
```

Download the *Batini questions on the Vitali case* at the following link (available only with a UniMiB account): [Drive Link](https://drive.google.com/file/d/1BfHRpb3xwrUvSIUbFdv10yCd9zz4jgZE/view?usp=sharing)

Alternatively, custom question JSON files must follow this structure:

```json
{
    "ID": "<question_id>",
    "question": "<question_text>",
    "ground_truth": {
        "<annotator_1>": {
            "text": [
              "<sub_output_1>", 
              "<sub_output_2>",
              "...",
              "<sub_output_n>",
              "<final_output>"
            ]
        },
        "<annotator_2>": {},
        "...": {},
        "<annotator_m>": {}
    }
}
```
*(Note: `<sub_output_i>` elements are not mandatory).*

## 6) Use the correct docker-compose

If you need to deploy VCL on Chronos, you must delete the default `docker-compose.yml` and rename `docker-compose-chronos.yml` to `docker-compose.yml`.

## 7) Create the initial user

During the container creation, the database will be empty. You must create at least one user to access the application. To do this, run the following commands from the root directory:

```bash
docker compose up -d --build
python scripts/create_user.py -username <USER> -password <PASSWORD> -role Admin
```

**NB**: `docker compose up -d --build` (with the default `docker-compose.yml`) only starts the **MongoDB** container — the `dql-system` service is commented out and unused, since the application itself is run locally with `python main.py` (see step 8), not inside Docker.

*Optional parameters:*
*   `-email <EMAIL>` (No emails are sent)

*Password requirements:* at least 8 characters, with at least 1 lowercase letter, 1 uppercase letter, 1 digit and 1 special character (`!@#$%^&*()-_+.`).

**NB**

* The **vitali** and **salomone** use cases are accessible to all users.
* All other use cases require a user with a username matching the corpus name.


## 8) Running the application

```bash
python main.py
```

Then access the application via:
*   **Streamlit link:** [http://localhost:8501](http://localhost:8501)
*   **FastAPI link:** [http://0.0.0.0:9000](http://0.0.0.0:9000)

**NB**: The `docker compose us` and `docker compose down` operations are handled automatically in `main.py`.

### Command Line Arguments

The script accepts several optional flags (arguments) to customize its behavior:

*   `-api <KEY>`
    *   **Description:** Provides the API key for the LLM.

*   `-uri_db <URI>`
    *   **Description:** Provides the connection URL for the database (e.g., MongoDB).

*   `-provider <PROVIDER_NAME>`
    *   **Description:** Specifies which LLM provider to use.
    *   **Default:** `google_genai`
    *   **Choices:** `google_genai`, `openai`, `azure_openai`, `copilot`, `huggingface`.
    *   **Azure OpenAI / Microsoft Foundry:** to use a model deployed on Azure AI Foundry, set `-provider azure_openai` and fill in `.env`:
        ```
        AZURE_OPENAI_API_KEY=<key>
        AZURE_OPENAI_ENDPOINT=<endpoint>
        ```
        Both values are on the deployment's **Details** page in the Azure AI Foundry portal:
        * **Key** → `AZURE_OPENAI_API_KEY`.
        * **Endpoint** → `AZURE_OPENAI_ENDPOINT`, copied as-is (it may look like `https://<resource>.services.ai.azure.com/openai/v1/responses` — that's fine, it's normalized automatically to the resource root).
        * **Name** (the deployment name at the top of the page, e.g. `gpt-4.1-mini-renzo-vcl-local`) → passed via `-model_name` when launching the app, e.g.:
          ```bash
          python main.py -provider azure_openai -model_name gpt-4.1-mini-renzo-vcl-local
          ```
        No other Azure-specific variables are required — `api-version` defaults to a recent stable release and only needs overriding (`OPENAI_API_VERSION` in `.env`) for edge cases.

*   `-model_name <MODEL_NAME>`
    *   **Description:** Specifies the exact LLM model name to use.
    *   **Default:** `gemini-2.5-flash`
    *   **Examples:** `gpt-4o-mini`, `claude-3-5-sonnet`, `mistralai/Mistral-7B-Instruct-v0.2`.

*   `-wait_seconds <NUMBER>`
    *   **Description:** Sets the number of seconds to wait after each LLM call.
    *   **Default:** `0`

*   `-evaluation_mode`
    *   **Description:** If present, the Streamlit application is not started, and the experimentation script is executed instead.
    *   **Usage:** Just add the flag; it does not require a value.

#### Evaluation Mode Parameters
If you use the `-evaluation_mode` flag, you must also configure the following parameters:

*   `-models <LIST>`
    *   **Description:** List of models to evaluate.
    *   **Choices:** `FileSearch`, `RAG`, `Copilot`, `NotebookLM`, `DQL`
    *   **Default:** all models

*   `-gen-llm <MODEL_NAME>`
    *   **Description:** OpenAI's LLM to use for generation in RAG and FileSearch.
    *   **Default:** `gpt-4o-mini`

*   `-eval-llm <MODEL_NAME>`
    *   **Description:** OpenAI's LLM to use for evaluation/judge.
    *   **Default:** `gpt-4o-mini`

*   `-k <NUMBER>`
    *   **Description:** Number of iterations/answers per model.
    *   **Default:** `1`
