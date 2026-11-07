"""Python demo path; live requests require LangGraph. SQLite owns approval state."""
import hashlib
import json
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
    # Persist the approved interpretation before execution. Retries do not re-plan.
    if not isinstance(key, str) or not 1 <= len(key) <= 128:
        raise ValueError('Invalid idempotency key')
    if not isinstance(data, dict) or set(data) not in ({'plan'}, {'text'}):
        raise ValueError('Provide exactly one of plan or text')
    if 'text' in data and (not isinstance(data['text'], str) or not 1 <= len(data['text']) <= 20000):
        raise ValueError('Task text must contain 1–20000 characters')
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    with engine.lock:
        engine.db.execute('CREATE TABLE IF NOT EXISTS requests(owner TEXT, key TEXT, digest TEXT, plan TEXT, PRIMARY KEY(owner,key))')
        cached = engine.db.execute('SELECT digest,plan FROM requests WHERE owner=? AND key=?',(owner,key)).fetchone()
        if cached:
            if cached['digest'] != digest:
                raise ValueError('Idempotency key already used for another request')
            return engine.submit(owner,key,json.loads(cached['plan']))
        plan = validate(data['plan']) if 'plan' in data else plan_text(data['text'], engine.provider.demo)
        engine.db.execute('INSERT INTO requests VALUES(?,?,?,?)',(owner,key,digest,json.dumps(plan)))
        return route_request(engine,owner,key,{'plan':plan})


def route_request(engine, owner, key, data):
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
