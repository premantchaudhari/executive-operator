"""Tenant-scoped durable conversation turns; planning runs outside the API."""
import json
from fastapi import HTTPException
from sqlalchemy import select
from .models import Conversation,ConversationTurn,Job,Workflow,WorkflowStep,AuditEvent,identifier
from .service import authorize,enqueue
from .workflows import canonical,digest

def scoped(session,org,principal,cid,write=False):
    authorize(session,org,principal,write)
    item=session.scalar(select(Conversation).where(Conversation.id==cid,Conversation.organization_id==org).with_for_update())
    if item is None:raise HTTPException(404,'Conversation not found')
    return item

def start(session,org,principal):
    authorize(session,org,principal,True)
    item=Conversation(id=identifier(),organization_id=org);session.add(item);session.flush();return item

def message(session,org,principal,cid,key,text):
    convo=scoped(session,org,principal,cid,True)
    existing=session.scalar(select(ConversationTurn).where(ConversationTurn.conversation_id==cid,ConversationTurn.request_key==key))
    if existing:
        if existing.message!=text or existing.author!=principal.subject:raise HTTPException(409,'Message key conflict')
        return existing
    busy=session.scalar(select(ConversationTurn).where(ConversationTurn.conversation_id==cid,ConversationTurn.status.in_(['queued','planning'])))
    if busy:raise HTTPException(409,'Previous turn is still being planned')
    job=enqueue(session,org,principal,'chat:'+identifier(),{'instruction':text,'conversation_id':cid})
    turn=ConversationTurn(id=identifier(),conversation_id=cid,job_id=job.id,request_key=key,author=principal.subject,message=text)
    session.add(turn);convo.status='planning';session.flush();return turn

def history(session,convo):
    turns=session.scalars(select(ConversationTurn).where(ConversationTurn.conversation_id==convo.id).order_by(ConversationTurn.created_at,ConversationTurn.id)).all()
    return {'id':convo.id,'status':convo.status,'turns':[{'id':t.id,'author':t.author,'message':t.message,'status':t.status,'response':json.loads(t.response) if t.response else None} for t in turns]}

def plan_turn(sessions,turn_id,planner):
    """Internal planner dispatch. Claims a turn once; uncertain calls require review."""
    with sessions.begin() as s:
        turn=s.scalar(select(ConversationTurn).where(ConversationTurn.id==turn_id).with_for_update())
        if turn is None:raise ValueError('Unknown turn')
        if turn.status!='queued':return
        convo=s.get(Conversation,turn.conversation_id)
        # Membership is rechecked before model use; no caller-selected tenant.
        from .auth import Principal
        authorize(s,convo.organization_id,Principal(turn.author),True)
        turn.status='planning'
        context=history(s,convo)
    try:
        result=planner(context)
        if not isinstance(result,dict):raise ValueError('Invalid planner output')
        if set(result)=={'question'} and isinstance(result['question'],str) and 1<=len(result['question'])<=2000:
            state='clarification';encoded=[]
        elif set(result)=={'steps'} and isinstance(result['steps'],list) and 1<=len(result['steps'])<=20:
            encoded=[canonical(p) for p in result['steps']];state='planned'
        else:raise ValueError('Invalid planner output')
    except Exception:
        state='needs_review';encoded=[];result={'message':'Planning failed or output invalid; review before retrying'}
    with sessions.begin() as s:
        turn=s.scalar(select(ConversationTurn).where(ConversationTurn.id==turn_id).with_for_update())
        if turn.status!='planning':raise ValueError('Turn ownership changed')
        convo=s.get(Conversation,turn.conversation_id)
        if state=='planned':
            wf=Workflow(id=turn.job_id,organization_id=convo.organization_id);s.add(wf);s.flush()
            for i,p in enumerate(encoded):s.add(WorkflowStep(workflow_id=wf.id,position=i,plan=p,digest=digest(p)))
            result={'workflow_id':wf.id,'steps':result['steps']}
        turn.status=state;turn.response=json.dumps(result);convo.status=state
        s.add(AuditEvent(organization_id=convo.organization_id,actor='planner',resource_id=turn.id,event='conversation.'+state))
