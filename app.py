# app.py
from config import Config
from converters import OutputConverter
from prompt_chains import PromptChains
from pipelines import NL2DQLPipeline
from operations import DQL2Operations, OperationExecutor
from datetime import datetime
import os

def main():
    cfg = Config()
    docs = cfg.load_documents()
    pc = PromptChains()
    converters = OutputConverter()
    nl2dql = NL2DQLPipeline(pc, cfg, converters)
    executor = OperationExecutor(docs)

    while True:
        user = input("Input (empty to end): ").strip()
        if not user:
            break

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_path = os.path.join("outputs", f"{timestamp}.txt")
        os.makedirs("outputs", exist_ok=True)

        with open(out_path, "w") as f:
            f.write(f"Input: {user}\n\n")
            dql_res = nl2dql.run(user)
            f.write(f"DQL: {dql_res}\n\n")
            ops = DQL2Operations.generate(dql_res["response"])
            f.write(f"Operations: {ops}\n\n")
            results = executor.execute(ops)

            # final formatting con result_chain2
            final = pc.result_2.invoke({
                "comando": dql_res["response"]["comando"],
                "condizioni": dql_res["feedback"],
                "testi": "\n".join(f"{t}: {txt}" for t, txt in results),
            })
            print(final)
            f.write(f"\nResult: {final}")

if __name__ == "__main__":
    main()
