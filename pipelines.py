# pipelines.py
from langchain.memory import ConversationBufferMemory
from langchain.schema import AIMessage

from config import Config
from converters import OutputConverter
from prompt_chains import PromptChains

class NL2DQLPipeline:
    def __init__(self, prompt_chains: PromptChains, config: Config, converters: OutputConverter):
        self.pc = prompt_chains
        self.cfg = config
        self.converters = converters
        self.memory = ConversationBufferMemory(return_messages=True)

    def run(self, query: str) -> dict:
        dq = self.pc.chain_1.invoke({"query": query}).lower()
        
        cmd = self.pc.chain_2.invoke({"query": dq})
        cmd = self.converters.convert_key(cmd, self.cfg.command_map)
        
        dove = self.pc.chain_3a.invoke({"query": dq})
        dove = self.converters.query_in_list(dove)
        
        if ("contesto" not in str(dove)) and ("None" not in str(dove)):
            self.memory.chat_memory.add_user_message(dq)
            self.memory.chat_memory.add_ai_message(str(dove))
        elif "contesto" in str(dove):
            ai_messages = [eval(msg.content) for msg in self.memory.chat_memory.messages if isinstance(msg, AIMessage)]
            if "confronta" in dq:
                dove = sorted(list(set(ai_messages[-1]))) if ai_messages else ['sentenza di primo grado']
            else:
                dove = ai_messages[-1] if ai_messages else ['sentenza di primo grado']
        
        self.memory = ConversationBufferMemory(return_messages=True)
        what = self.pc.chain_3b.invoke({"query": dq, "comando": cmd, "descrizione_comando": self.cfg.command_descriptions.get(cmd, "")})
        
        cond = self.pc.chain_3c.invoke({"query": dq, "comando": cmd, "descrizione_comando": self.cfg.command_descriptions.get(cmd, "")})
        cond = self.converters.query_in_dict(cond)
        
        dql = {"comando": cmd, "dove": dove, "cosa": {"name": what}, "condizione": cond}
        
        if "entit" in dql["cosa"]["name"]:
            dql["cosa"]["name"] = "entita\'"
            dql_entity = self.pc.chain_4.invoke(
                {"query": dq, "comando": cmd, "descrizione_comando": self.cfg.command_descriptions.get(cmd, ""),
                "dove": dql["dove"]})
            dql.update({"cosa": self.converters.query_in_dict(dql_entity)})
        elif "frase" in dql["cosa"]["name"]:
            output_5 = self.pc.chain_5.invoke(
                {"query": dq, "comando": cmd, "descrizione_comando": self.cfg.command_descriptions.get(cmd, ""),
                "dove": dql["dove"]})

            if "entit" in output_5["relativa_a"]["name"]:
                output_5["relativa_a"]["name"] = "entita\'"
                dql_entity = self.pc.chain_4.invoke({"query": dq, "comando": cmd,
                                        "descrizione_comando": self.cfg.command_descriptions.get(cmd, ""),
                                        "dove": dql["dove"]})
                output_5.update({"relativa_a": self.converters.query_in_dict(dql_entity)})

            dql.update({"cosa": output_5})
    
        feedback = self.pc.evaluator.invoke({"question": dq, "response": dql})
        feedback = self.converters.query_in_dict(feedback)
        
        if int(feedback["voto"]) < 8:
            improved = self.pc.reflection.invoke({"question": dq, "response": dql, "feedback": feedback["motivazione"]})
            improved = self.converters.query_in_dict(improved)
            return {"original": dql, "feedback": feedback["motivazione"], "response": improved}
        else:  
            return {"original": dql, "feedback": feedback["motivazione"], "response": dql}