# dql
Description Query Language

## How to Run the Code

To run this project, follow these steps:

1. Go to the [Gemini API website](https://aistudio.google.com/app/apikey)
2. Generate a new API key.
3. Copy the generated key and paste it into a file named `api_key.txt`. Optionally, you can run `app.py` with the `-api` flag if you want to store the key.
4. Make sure you are connected to your university's VPN — this is required to access the Elasticsearch database.
5. Run the `app.py` file. Use the `-rag` flag if you want only relevant chunks to be used during retrieval.

```bash
python app.py
```

## Future Improvements

The following enhancements are planned to improve the current system:

- **Transition from Chain Pipelines to a Multi-Agent System**
- **Improvement of the Evaluator-Autocorrection System and Prompts**: refine the evaluator component and the automatic correction logic, as well as improve the prompts used in `Result.txt` and `Result2.txt` for better reliability and interpretability.
- **Input Parameter Handling for Configurable Results**: introduce more flexible input parameterization to allow experiments and results to be generated under a wider range of configurations and scenarios.
- **More Precise and Rigorous Definition of Entities and Conditions**: clarify and formalize the semantic structure of entities and their conditions to ensure consistent interpretation and validation across components.