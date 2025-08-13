from typing_extensions import TypedDict
from typing import Literal

from langgraph.types import Command
from langgraph.graph import StateGraph, START, END

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

from utils.config_graph import Config

import os
import json
import time


project_root = Path(__file__).resolve().parent.parent
cfg = Config.get_instance()


class State(TypedDict):
    query: str
    command: str
    where: list[str]
    what: dict
    ent: dict
    phr: dict
    how: dict
    iteration: int
    feedback: str
    response: dict
    

def correctionQuery(state: State) -> Command[Literal["intentClassification"]]:
    result = chain("1 - CorrectionQuery", {"query": state["query"]}, state)
    
    return Command(
        goto="intentClassification",
        update={"query": result},
    )

def intentClassification(state: State) -> Command[Literal["documentExtraction"]]:
    result = chain("2 - IntentClassification", {"query": state["query"], "\'command\'": ""}, state)

    return Command(
        goto="documentExtraction",
        update={"command": cfg.get_command_from_key(result)},
    )

def documentExtraction(state: State) -> Command[Literal["whatExtraction"]]:
    result = chain("3 - DocumentExtraction", {"query": state["query"]}, state)
    result = cfg.str_in_list(result)

    return Command(
        goto="whatExtraction",
        update={"where": result},
    )

def whatExtraction(state: State) -> Command[Literal["entityDisambiguation", "phraseDisambiguation", "conditionsExtraction"]]:
    result = chain("4 - WhatExtraction", {"query": state["query"], "comando": state["command"], "descrizione_comando": cfg.get_description_from_command(state["command"])}, state)
    result = {"name": result}

    if "entit" in result["name"]:
        goto = "entityDisambiguation"
    elif "frase" in result["name"]:
        goto = "phraseDisambiguation"
    else:
        goto = "conditionsExtraction"
        
    return Command(
        goto=goto,
        update={"what": result}
    )

def entityDisambiguation(state: State) -> Command[Literal["conditionsExtraction"]]:
    result = chain("5a - EntityDisambiguation", {"query": state["query"], "comando": state["command"], "descrizione_comando": cfg.get_description_from_command(state["command"]),
                "dove": state["where"]}, state)
    result = cfg.str_in_dict(result)

    what = state["what"]
    if not what or "relativo_a" in what.keys():
        what["relativo_a"] = result
    else:
        what = result

    return Command(
        goto="conditionsExtraction",
        update={"what": what}
    )

def phraseDisambiguation(state: State) -> Command[Literal["entityDisambiguation", "conditionsExtraction"]]:
    result = chain("5b - PhraseDisambiguation", {"query": state["query"], "comando": state["command"], "descrizione_comando": cfg.get_description_from_command(state["command"]),
                "dove": state["where"]}, state)
    result = cfg.str_in_dict(result)

    return Command(
        goto="conditionsExtraction",
        update={"what": result}
    )

def conditionsExtraction(state: State) -> Command[Literal["evaluationResult"]]:
    result = chain("6 - ConditionsExtraction", {"query": state["query"], "comando": state["command"], "descrizione_comando": cfg.get_description_from_command(state["command"])}, state)
    result = cfg.str_in_dict(result)
        
    return Command(
        goto="evaluationResult",
        update={"how": result}
    )

def evaluationResult(state: State) -> Command[Literal["intentClassification", END]]:
    response = {"command": state["command"], "what": state["what"], "where": state["where"], "how": state["how"]}
    result = chain("7 - EvaluationResult", {"question": state["query"], "response": str(response)}, state)
    result = cfg.str_in_dict(result)
    
    if int(result["voto"]) < 8 and state["iteration"] < cfg.max_iteration:
        goto = "intentClassification"
    else:
        goto = END

    return Command(
        goto=goto,
        update={"iteration": state["iteration"] + 1, "feedback": result["motivazione"], "score": result["voto"], "response": response}
    )

def build_graph():
    graph_builder = StateGraph(State)
    graph_builder.add_node("correctionQuery", correctionQuery)
    graph_builder.add_node("intentClassification", intentClassification)
    graph_builder.add_node("documentExtraction", documentExtraction)
    graph_builder.add_node("whatExtraction", whatExtraction)
    graph_builder.add_node("entityDisambiguation", entityDisambiguation)
    graph_builder.add_node("phraseDisambiguation", phraseDisambiguation)
    graph_builder.add_node("conditionsExtraction", conditionsExtraction)
    graph_builder.add_node("evaluationResult", evaluationResult)
    graph_builder.set_entry_point("correctionQuery")
    
    return graph_builder.compile()

def chain(name: str, input: dict, state: State) -> str:
    path = os.path.join(project_root, "prompts", "rewriting", f"{name}.txt")

    template = open(path, "r").read()

    if state["response"] is not None:
        response_clean = str(state['response']).replace("{", "(").replace("}", ")")
        template = f"[FEEDBACK]\nconsidera che per la query \"{state['query']}\" è già stato generato un possibile output:\n{response_clean}\nquesto output ha ricevuto però una valutazione non sufficiente per i nostri standard in quanto \"{state['feedback']}\".\nnon devi riscostruire l'intero output, ma nella risposta tieni conto del feedback.\n[PROMPT]\n{template}"

    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | cfg.llm | StrOutputParser()
    result = chain.invoke(input)
    
    time.sleep(cfg.seconds)
    
    return result.strip().lower()

graph = build_graph()