"""Python demo path; live requests require LangGraph. SQLite owns approval state."""
from typing import TypedDict
from .core import validate
from .providers import plan_text

class RequestState(TypedDict, total=False):
    owner: str
    key: str
    text: str
    plan: dict
    task: dict


def submit_request(engine, owner, key, data):
    def prepare(state):
        plan = state.get('plan') or plan_text(state.get('text', ''), engine.provider.demo)
        return {'plan': validate(plan)}
    def persist(state):
        return {'task': engine.submit(state['owner'], state['key'], state['plan'])}
    state = {'owner': owner, 'key': key, **{k: data[k] for k in ('plan', 'text') if k in data}}
    if engine.provider.demo:
        state.update(prepare(state))
        return persist(state)['task']
    # No silent fallback in live mode if LangGraph is missing.
    from langgraph.graph import StateGraph, START, END
    graph = StateGraph(RequestState)
    graph.add_node('validate_plan', prepare)
    graph.add_node('persist_and_route', persist)
    graph.add_edge(START, 'validate_plan')
    graph.add_edge('validate_plan', 'persist_and_route')
    graph.add_edge('persist_and_route', END)
    return graph.compile().invoke(state)['task']
