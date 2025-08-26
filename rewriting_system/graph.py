from typing_extensions import TypedDict
from typing import Literal

from langgraph.types import Command
from langgraph.graph import StateGraph

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

import os
import time

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

from utils.config_graph import Config

project_root = Path(__file__).resolve().parent.parent
cfg = Config.get_instance()

class State(TypedDict):
    query: str
    
    command: str
    
    documents: list[str]
    
    unit: str
    
    what_name: str
    what_type: str
    what_description: str
    
    how_section: str
    how_temporal: str
    how_mathematics: str
    how_logic: str
    how_formal: str
    how_textual: str
    
    iteration: int
    feedback: str
    response: dict

def correctionQuery(state: State) -> Command[Literal["intentClassification"]]:
    result = chain("1 - CorrectionQuery", 
                   {"query": state["query"]}, 
                   state)
    
    return Command(
        goto="intentClassification",
        update={"query": result}
    )

def intentClassification(state: State) -> Command[Literal["documentExtraction", "unitExtraction"]]:
    result = chain("2 - IntentClassification", 
                   {"query": state["query"]}, 
                   state)
    result = cfg.get_command_from_key(result)
    
    goto = ["documentExtraction"]
    
    if "calcola" in result:
        goto.append("unitExtraction")
        
    return Command(
        goto=goto,
        update={"command": result},
    )

def documentExtraction(state: State) -> Command[Literal["whatExtraction"]]:
    result = chain("3 - DocumentExtraction", 
                   {"query": state["query"]}, 
                   state)
    
    result = cfg.str_in_list(result)

    return Command(
        goto="whatExtraction",
        update={"documents": result},
    )
    
def unitExtraction(state: State) -> Command[Literal["whatExtraction"]]:
    result = chain("4 - UnitsExtraction", {"query": state["query"]}, state)

    return Command(
        goto="whatExtraction",
        update={"unit": result},
    )

def whatExtraction(state: State) -> Command[Literal["personDisambiguation",
                                                    "organizationDisambiguation", 
                                                    "moneyDisambiguation", 
                                                    "sourcesDisambiguation", 
                                                    "articlesDisambiguation", 
                                                    "placesDisambiguation",
                                                    "sectionsConditions"]]:
    result = chain("4 - WhatExtraction", 
                   {
                       "query": state["query"], 
                       "comando": state["command"], 
                       "descrizione_comando": cfg.get_description_from_command(state["command"])
                    }, 
                   state)

    match result:
        case "persona":
            goto = "personDisambiguation"
        case "organizzazione":
            goto = "organizationDisambiguation"
        case "luogo":
            goto = "placesDisambiguation"
        case "denaro":
            goto = "moneyDisambiguation"
        case "fonte":
            goto = "sourcesDisambiguation"
        case "articolo":
            goto = "articlesDisambiguation"
        case _:
            goto = "sectionsConditions"
            
    what_name = ""
    what_type = ""
    
    if result == "persona" or result == "organizzazione" or result == "luogo" or result == "denaro" or result == "fonte" or result == "articolo":
        what_name = "entità" 
        what_type = result
    else:
        what_name = result
        
    return Command(
        goto=goto,
        update={
            "what_name": what_name,
            "what_type": what_type
        }
    )
    
def personDisambiguation(state: State) -> Command[Literal["sectionsConditions"]]:
    result = chain("5a - PersonDisambiguation", {}, state)
    
    return Command(
        goto="sectionsConditions",
        update={"what_description": result}
    )
    
def organizationDisambiguation(state: State) -> Command[Literal["sectionsConditions"]]:
    result = chain("5b - OrganizationDisambiguation", {}, state)
    
    return Command(
        goto="sectionsConditions",
        update={"what_description": result}
    )
    
def moneyDisambiguation(state: State) -> Command[Literal["sectionsConditions"]]:
    result = chain("5c - MoneyDisambiguation", {}, state)
    
    return Command(
        goto="sectionsConditions",
        update={"what_description": result}
    )
    
def sourcesDisambiguation(state: State) -> Command[Literal["sectionsConditions"]]:
    result = chain("5d - SourcesDisambiguation", {}, state)
    
    return Command(
        goto="sectionsConditions",
        update={"what_description": result}
    )
    
def articlesDisambiguation(state: State) -> Command[Literal["sectionsConditions"]]:
    result = chain("5e - ArticlesDisambiguation", {}, state)
    
    return Command(
        goto="sectionsConditions",
        update={"what_description": result}
    )
    
def placesDisambiguation(state: State) -> Command[Literal["sectionsConditions"]]:
    result = chain("5f - PlacesDisambiguation", {}, state)
    
    return Command(
        goto="sectionsConditions",
        update={"what_description": result}
    )

def sectionsConditions(state: State) -> Command[Literal["temporalConditions", 
                                                        "mathematicsConditions", 
                                                        "logicConditions", 
                                                        "formalConditions",
                                                        "textualConditions"]]:
    result = chain("6 - SectionsConditions", {"query": state["query"], "comando": state["command"], "descrizione_comando": cfg.get_description_from_command(state["command"])}, state)
        
    return Command(
        goto=["temporalConditions", "mathematicsConditions", "logicConditions", "formalConditions", "textualConditions"],
        update={"how_section": result}
    )
    
def temporalConditions(state: State) -> Command[Literal["aggregator"]]:
    result = chain("6a - TemporalConditions", {}, state)
    
    return Command(
        goto="aggregator",
        update={"how_temporal": result}
    )
    
def mathematicsConditions(state: State) -> Command[Literal["aggregator"]]:
    result = chain("6b - MathematicsConditions", {}, state)
    
    return Command(
        goto="aggregator",
        update={"how_mathematics": result}
    )
    
def logicConditions(state: State) -> Command[Literal["aggregator"]]:
    result = chain("6c - LogicConditions", {}, state)
    
    return Command(
        goto="aggregator",
        update={"how_logic": result}
    )
    
def formalConditions(state: State) -> Command[Literal["aggregator"]]:
    result = chain("6d - FormalConditions", {}, state)
    
    return Command(
        goto="aggregator",
        update={"how_formal": result}
    )
    
def textualConditions(state: State) -> Command[Literal["aggregator"]]:
    result = chain("6e - TextualConditions", {}, state)
    
    return Command(
        goto="aggregator",
        update={"how_textual": result}
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
    
    how = {}
    if state["how_section"]:
        how.update({"Section": state["how_section"]})
    
    if state["how_temporal"]:
        how.update({"Temporal": state["how_temporal"]})
    
    if state["how_mathematics"]:
        how.update({"Mathematics": state["how_mathematics"]})
    
    if state["how_logic"]:
        how.update({"Logic": state["how_logic"]})
    
    if state["how_formal"]:
        how.update({"Formal": state["how_formal"]})
    
    if state["how_textual"]:
        how.update({"Textual": state["how_textual"]})
        
    response.update({"how": how})
    
    return Command(
        goto="evaluationResult",
        update={"response": response}
    )

def evaluationResult(state: State) -> Command[Literal["intentClassification", "__end__"]]:
    result = chain("7 - EvaluationResult", {"question": state["query"], "response": str(state["response"])}, state)
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
    
    graph_builder.add_node("unitExtraction", unitExtraction)
    
    graph_builder.add_node("whatExtraction", whatExtraction)
    graph_builder.add_node("personDisambiguation", personDisambiguation)
    graph_builder.add_node("organizationDisambiguation", organizationDisambiguation)
    graph_builder.add_node("moneyDisambiguation", moneyDisambiguation)
    graph_builder.add_node("sourcesDisambiguation", sourcesDisambiguation)
    graph_builder.add_node("articlesDisambiguation", articlesDisambiguation)
    graph_builder.add_node("placesDisambiguation", placesDisambiguation)
    
    graph_builder.add_node("sectionsConditions", sectionsConditions)
    graph_builder.add_node("temporalConditions", temporalConditions)
    graph_builder.add_node("mathematicsConditions", mathematicsConditions)
    graph_builder.add_node("logicConditions", logicConditions)
    graph_builder.add_node("formalConditions", formalConditions)
    graph_builder.add_node("textualConditions", textualConditions)
    
    graph_builder.add_node("aggregator", aggregator)
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
with open("images/graph.png", "wb") as f:
    f.write(graph.get_graph().draw_mermaid_png())