import json
import numpy as np
import asyncio

from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import FactualCorrectness, Faithfulness

from collections import defaultdict

class GPTJudge:

    def __init__(self, model: str, atomicity: str ="low", coverage: str = "low"):
        if "gpt" not in model:
            raise ValueError("Model not supported!")

        self.model = model

        # Reusable OpenAI client + LLMs
        self.client = AsyncOpenAI()
        self.llm_default = llm_factory(self.model, client=self.client)
        self.llm_long = llm_factory(
            self.model, client=self.client, max_tokens=16384
        )

        self.faithfulness = Faithfulness(
            llm=self.llm_long
        )

        self.factualcorrectness = FactualCorrectness(
            llm=self.llm_long,
            atomicity=atomicity,
            coverage=coverage
        )

        self.context = []

    # -------------------------
    # Initialization
    # -------------------------
    def initialize(self, paths):
        self.context = []
        for path in paths:
            with open(path, "r", encoding="utf-8") as f:
                self.context.append(
                    dict(json.load(f)).get("text", "")
                )

    async def start_prompt(self):
        self.faithfulness.statement_generator_prompt = await self.faithfulness.statement_generator_prompt.adapt(
            target_language="italian",
            llm=self.llm_default,
            adapt_instruction=True
        )

        self.faithfulness.nli_statement_prompt  = await self.faithfulness.nli_statement_prompt.adapt(
            target_language="italian",
            llm=self.llm_default,
            adapt_instruction=True
        )

        self.factualcorrectness.prompt = await self.factualcorrectness.prompt.adapt(
            target_language="italian",
            llm=self.llm_default,
            adapt_instruction=True
        )

        self.factualcorrectness.nli_prompt = await self.factualcorrectness.nli_prompt.adapt(
            target_language="italian",
            llm=self.llm_default,
            adapt_instruction=True
        )

    # -------------------------
    # Claims extraction
    # -------------------------
    async def extract_claims(self, text, atomicity="low", coverage="low"):
        return await self.factualcorrectness._decompose_claims(text)

    # -------------------------
    # Precision / Recall / F1
    # -------------------------
    async def evaluate_precision_recall_f1(
        self,
        response_claims,
        reference_claims,
        response_text,
        reference_text,
    ):
        # Precision: response → reference
        resp_ref = await self.factualcorrectness._verify_claims(
            response_claims, reference_text
        )
        tp = sum(v.verdict for v in resp_ref.statements) if resp_ref else 0
        fp = len(resp_ref.statements) - tp if resp_ref else 0

        # Recall: reference → response
        ref_resp = await self.factualcorrectness._verify_claims(
            reference_claims, response_text
        )
        fn = sum(not v.verdict for v in ref_resp.statements) if ref_resp else 0

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        return {
            "precision": {
                "score": precision,
                "details": {
                    "tp": tp,
                    "fp": fp,
                    "statements": [
                        {
                            "statement": v.statement,
                            "verdict": int(v.verdict),
                            "reason": v.reason,
                        }
                        for v in resp_ref.statements
                    ]
                    if resp_ref
                    else None,
                },
            },
            "recall": {
                "score": recall,
                "details": {
                    "tp": tp,
                    "fn": fn,
                    "statements": [
                        {
                            "statement": v.statement,
                            "verdict": int(v.verdict),
                            "reason": v.reason,
                        }
                        for v in ref_resp.statements
                    ]
                    if ref_resp
                    else None,
                },
            },
            "f1": {"score": f1},
        }

    # -------------------------
    # Faithfulness (single corpus)
    # -------------------------
    async def evaluate_faithfulness(self, statements):
        context_str = "\n".join(self.context)
        verdicts = await self.faithfulness._create_verdicts(
            statements, context_str
        )
        score = self.faithfulness._compute_score(verdicts)

        return {
            "faithfulness": {
                "score": score,
                "details": {
                    "statements": [
                        {
                            "statement": v.statement,
                            "verdict": int(v.verdict),
                            "reason": v.reason,
                        }
                        for v in verdicts.statements
                    ]
                    if verdicts
                    else None
                },
            }
        }

    # -------------------------
    # Faithfulness (multi-doc)
    # -------------------------
    async def evaluate_faithfulness_multi(self, statements):
        per_statement = defaultdict(list)

        for doc in self.context:
            verdicts = await self.faithfulness._create_verdicts(statements, doc)

            for v in verdicts.statements:
                per_statement[v.statement].append(
                    {
                        "verdict": int(v.verdict),
                        "reason": v.reason,
                    }
                )

        aggregated = []
        for statement, verdicts in per_statement.items():
            supporting = [v for v in verdicts if v["verdict"] == 1]
            if supporting:
                aggregated.append(
                    {
                        "statement": statement,
                        "verdict": 1,
                        "reason": supporting[0]["reason"],
                    }
                )
            else:
                aggregated.append(
                    {
                        "statement": statement,
                        "verdict": 0,
                        "reason": [v["reason"] for v in verdicts],
                    }
                )

        supported = sum(v["verdict"] for v in aggregated)
        total = len(aggregated)
        score = supported / total if total > 0 else 0.0

        return {
            "faithfulness": {
                "score": score,
                "details": {"statements": aggregated},
            }
        }

    # -------------------------
    # Consistency
    # -------------------------
    def evaluate_consistency(self, results: dict):
        values = list(results.values())
        metrics = [
            k for k in values[0].keys() if "claims" not in k
        ]

        variances = 0.0
        details = {}

        for m in metrics:
            scores = [
                v.get(m, {}).get("score", 0.0) for v in values
            ]
            var = np.var(scores, ddof=1) if len(scores) > 1 else 0.0
            details[f"{m}_variance"] = var
            variances += var

        score = (
            max(0.0, 1 - variances / len(metrics))
            if metrics
            else 0.0
        )

        return {"consistency": {"score": score, "details": details}}

    # -------------------------
    # Judge single response
    # -------------------------
    async def _judge_single(
        self,
        idx,
        response,
        reference_claims,
        reference_text,
        response_claims
    ):
        r1 = await self.evaluate_precision_recall_f1(
            response_claims,
            reference_claims,
            response,
            reference_text,
        )
        r2 = await self.evaluate_faithfulness_multi(
            response_claims
        )

        result = {}
        result.update(r1)
        result.update(r2)

        return idx, result

    # -------------------------
    # Main judge (ASYNC)
    # -------------------------
    async def judge(self, question, responses, reference, responses_claims = None, reference_claims = None):
        if not self.context:
            raise Exception("Need to initialize context!")
        
        if not isinstance(responses, dict):
            responses = {"1": str(responses)}
        
        if not responses_claims:
            responses_claims = {}
            for i, response in responses.items():
                responses_claims[i] = await self.extract_claims(response)
            
        if not reference_claims:
            reference_claims = await self.extract_claims(reference)

        tasks = [
            self._judge_single(
                i, response, reference_claims, reference, responses_claims[i]
            )
            for i, response in responses.items()
        ]

        judged = await asyncio.gather(*tasks)
        results = dict(judged)

        if len(results) > 1:
            results.update(self.evaluate_consistency(results))

        results["reference_claims"] = reference_claims
        return results