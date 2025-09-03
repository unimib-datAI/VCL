from typing_extensions import TypedDict
from typing import Literal

from langgraph.types import Command
from langgraph.graph import StateGraph

from langchain.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain.prompts.chat import HumanMessagePromptTemplate, AIMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser

from storage import Storage

import os
import time
import re

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

from utils.config_graph import Config
from utils.file_manager import read_file

project_root = Path(__file__).resolve().parent.parent
cfg = Config.get_instance()

r = Storage()

class State(TypedDict):
    query: str
    thread_id: str
    
    command: str
    description_command: str
    
    documents: list[str]
    
    unit: str
    
    what_name: str
    what_type: str
    what_description: str
    
    section_condition: str
    data_condition: str
    response_condition: str
    
    iteration: int
    feedback: str
    response: dict

def correctionQuery(state: State) -> Command[Literal["intentClassification"]]:
    result = chain("1 - CorrectionQuery", state)
    
    return Command(
        goto="intentClassification",
        update={"query": result}
    )

def intentClassification(state: State) -> Command[Literal["documentExtraction", "unitExtraction"]]:
    result = chain("2 - IntentClassification", state)
    result = cfg.get_command_from_key(result)
    
    goto = ["documentExtraction"]
    
    if "calcola" in result:
        goto.append("unitExtraction")
        
    return Command(
        goto=goto,
        update={"command": result, "description_command": cfg.get_description_from_command(result)},
    )

def documentExtraction(state: State) -> Command[Literal["whatExtraction", "documentDisambiguation"]]:
    result = chain("3 - DocumentExtraction", state)
    
    result = cfg.str_in_list(result)

    goto = "whatExtraction"
    if "contesto" in result:
        goto = "documentDisambiguation"
    else:
        r.write(state["thread_id"], state["query"], result)
        
    return Command(
        goto=goto,
        update={"documents": result},
    )

def documentDisambiguation(state: State) -> Command[Literal["whatExtraction"]]:
    chat = r.read(state["thread_id"])
    
    if not (chat == []):
        doc = chain("3a - DocumentDisambiguation", state)
        doc = cfg.str_in_list(doc) 
    else:
        doc = ["sentenza di primo grado", "sentenza di secondo grado", "memoria giudiziale", "ricorso giudiziale"]
    
    r.write(state["thread_id"], state["query"], doc)
    
    return Command(
        goto="whatExtraction",
        update={"documents": doc},
    )
    
def unitExtraction(state: State) -> Command[Literal["whatExtraction"]]:
    result = chain("4 - UnitsExtraction", state)

    return Command(
        goto="whatExtraction",
        update={"unit": result},
    )

def whatExtraction(state: State) -> Command[Literal["entityDisambiguation",
                                                    "sectionsConditions"]]:
    result = chain("5 - WhatExtraction", state)
            
    what_name = ""
    what_type = ""
    
    if result == "persona" or result == "organizzazione" or result == "luogo" or result == "denaro" or result == "fonte" or result == "articolo":
        what_name = "entità" 
        what_type = result
        
        goto = "entityDisambiguation"
    else:
        what_name = result
        
        goto = "sectionsConditions"
        
    return Command(
        goto=goto,
        update={
            "what_name": what_name,
            "what_type": what_type
        }
    )
    
def entityDisambiguation(state: State) -> Command[Literal["sectionsConditions"]]:
    result = ""
    
    match state["what_type"]:
        case "persona":
            result = chain("5a - PersonDisambiguation", state)
        case "organizzazione":
            result = chain("5b - OrganizationDisambiguation", state)
        case "denaro":
            result = chain("5c - MoneyDisambiguation", state)
        case "fonte":
            result = chain("5d - SourcesDisambiguation", state)
        case "luogo":
            result = chain("5e - PlacesDisambiguation", state)
    
    return Command(
        goto="sectionsConditions",
        update={"what_description": result}
    )

def sectionsConditions(state: State) -> Command[Literal["dataConditions",
                                                        "responseConditions"]]:
    result = chain("6 - SectionsConditions", state)
        
    return Command(
        goto=["dataConditions", "responseConditions"],
        update={"section_condition": result}
    )
    
def dataConditions(state: State) -> Command[Literal["aggregator"]]:
    result = chain("6a - DataConditions", state)
    
    return Command(
        goto="aggregator",
        update={"data_condition": result}
    )
    
def responseConditions(state: State) -> Command[Literal["aggregator"]]:
    result = chain("6b - ResponseConditions", state)
    
    return Command(
        goto="aggregator",
        update={"response_condition": result}
    )
    
def aggregator(state: State) -> Command[Literal["evaluationResult"]]:
    response = {
        "query": state["query"],
        "command": state["command"],
        "documents": state["documents"]
    }
    
    if state["command"] == "calcola":
        response.update({"unit": state["unit"]})
    
    what = {"name": state["what_name"]}
    
    if state["what_name"] == "entità":
        what.update({"type": state["what_type"]})
        what.update({"description": state["what_description"]})
        
    response.update({"what": what})
    
    how = {}
    if state["section_condition"]:
        how.update({"Section": state["section_condition"]})
    
    if state["data_condition"]:
        how.update({"Data": state["data_condition"]})
    
    if state["response_condition"]:
        how.update({"Response": state["response_condition"]})
        
    response.update({"how": how})
    
    return Command(
        goto="evaluationResult",
        update={"response": response}
    )

def evaluationResult(state: State) -> Command[Literal["intentClassification", "__end__"]]:
    result = chain("7 - EvaluationResult", state)
    result = cfg.str_in_dict(result)
    
    if int(result["voto"]) < 8 and state["iteration"] < cfg.max_iteration:
        goto = "intentClassification"
    else:
        goto = "__end__"

    return Command(
        goto=goto,
        update={"iteration": state["iteration"] + 1, "feedback": result["motivazione"], "score": result["voto"]}
    )

def build_graph():
    graph_builder = StateGraph(State)
    
    graph_builder.add_node("correctionQuery", correctionQuery)
    
    graph_builder.add_node("intentClassification", intentClassification)
    
    graph_builder.add_node("documentExtraction", documentExtraction)
    graph_builder.add_node("documentDisambiguation", documentDisambiguation)
    
    graph_builder.add_node("unitExtraction", unitExtraction)
    
    graph_builder.add_node("whatExtraction", whatExtraction)
    graph_builder.add_node("entityDisambiguation", entityDisambiguation)
    
    graph_builder.add_node("sectionsConditions", sectionsConditions)
    graph_builder.add_node("dataConditions", dataConditions)
    graph_builder.add_node("responseConditions", responseConditions)
    
    graph_builder.add_node("aggregator", aggregator)
    graph_builder.add_node("evaluationResult", evaluationResult)
    
    graph_builder.set_entry_point("correctionQuery")
    
    return graph_builder.compile()

def chain(file: str, state: State) -> str:
    template = read_file(os.path.join(project_root, "prompts", "rewriting", f"{file}.json"))
    template["system"] = "\n".join(template["system"])
    template["human"] = "\n".join(template["human"])
    
    input = {}
    for p in template["params"]:
        if p == "chat":
            chat = r.read(state["thread_id"])
    
            if not (chat == []):
                chat_str = ""
                
                for i in range(len(chat)):
                    chat_str += f"""
                    RICHIESTA/DOMANDA {i}
                    - time: {chat[i]["time"]}
                    - query: \"{chat[i]["query"]}\""
                    - ID doc input: \"{chat[i]["docRef"]}\"
                    - ID doc response: \"{chat[i]["docOut"]}\""
                    
                    """
                    
                input.update({p: chat_str})
        else:  
            input.update({str(p): str(state[p])})
    
    if not (state["response"] == {}) and ("EvaluationResult" not in file):
        response_clean = str(state['response']).replace("{", "{{").replace("}", "}}")
        template["system"] = f"[PROMPT]\n{template["human"]}\n\n[FEEDBACK]\nConsidera che per la query è già stato generato un possibile output:\n{response_clean}\nquesto output ha ricevuto però una valutazione non sufficiente per i nostri standard in quanto \"{state['feedback']}\".\nnon devi riscostruire l'intero output, ma nella risposta tieni conto del feedback."

    if not (template["examples"] == []):
        example_prompt = ChatPromptTemplate.from_messages([
            HumanMessagePromptTemplate.from_template("{input}"),
            AIMessagePromptTemplate.from_template("Ragionamento: {reasoning}\nRisultato: {output}"),
        ])

        few_shot_prompt = FewShotChatMessagePromptTemplate(
            example_prompt=example_prompt,
            examples=template["examples"],
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", template["system"]),
            few_shot_prompt,
            ("human", template["human"])
        ])
    else:
        prompt = ChatPromptTemplate.from_messages([
            ("system", template["system"]),
            ("human", template["human"])
        ])
    
    chain = prompt | cfg.llm | StrOutputParser()
    result = chain.invoke(input)
    
    time.sleep(cfg.seconds)
    
    result = result.lower()
    
    if "risultato:" in result:
        result = result[result.index("risultato:") + 11:]
        
    if result == "''":
        result = ""
        
    return result.strip()

graph = build_graph()