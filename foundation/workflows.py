"""Persisted sequential workflow engine. External effects never run in a DB transaction."""
import hashlib,json
from datetime import timedelta
from sqlalchemy import select
from fastapi import HTTPException
from langgraph.graph import StateGraph,START,END
from typing import TypedDict
from operator_app.core import validate,APPROVAL
from operator_app.native_tools import TOOLS
from .models import Workflow,WorkflowStep,AuditEvent,Job,now,identifier
from .service import authorize,enqueue
from .policy import require_owner,permitted

def canonical(plan):
    base={k:v for k,v in plan.items() if k!='account_id'}
    validate(base)
    if 'account_id' in plan and (not isinstance(plan['account_id'],str) or not plan['account_id'].strip() or len(plan['account_id'])>255):
        raise ValueError('Invalid bound account')
    if plan['action'] not in TOOLS:
        raise HTTPException(409,'Production browser and sandbox execution require their dedicated policy gates')
    return json.dumps(plan,sort_keys=True,separators=(',',':'))
def digest(plan):return hashlib.sha256(plan.encode()).hexdigest()

def create(session,org,principal,key,instruction,plans):
    authorize(session,org,principal,True)
    if not 1<=len(plans)<=20:raise HTTPException(400,'Workflow requires 1–20 steps')
    encoded=[canonical(p) for p in plans]
    job=enqueue(session,org,principal,key,{'instruction':instruction,'steps':plans})
    existing=session.get(Workflow,job.id)
    if existing:return existing
    wf=Workflow(id=job.id,organization_id=org);session.add(wf);session.flush()
    for i,p in enumerate(encoded):session.add(WorkflowStep(workflow_id=wf.id,position=i,plan=p,digest=digest(p)))
    session.flush();return wf

def scoped(session,org,principal,wid,write=False):
    authorize(session,org,principal,write)
    wf=session.scalar(select(Workflow).where(Workflow.id==wid,Workflow.organization_id==org).with_for_update())
    if wf is None:raise HTTPException(404,'Workflow not found')
    return wf

def summary(session,wf):
    steps=session.scalars(select(WorkflowStep).where(WorkflowStep.workflow_id==wf.id).order_by(WorkflowStep.position)).all()
    return {'id':wf.id,'status':wf.status,'steps':[{'id':s.id,'position':s.position,'plan':json.loads(s.plan),'digest':s.digest,'status':s.status,'result':json.loads(s.result) if s.result else None} for s in steps]}

def decide(session,org,principal,wid,sid,expected_digest,approved):
    wf=scoped(session,org,principal,wid,True)
    require_owner(session,org,principal)
    step=session.scalar(select(WorkflowStep).where(WorkflowStep.id==sid,WorkflowStep.workflow_id==wid))
    if wf.status!='awaiting_approval' or step is None or step.status!='awaiting_approval':raise HTTPException(409,'Not awaiting this decision')
    if step.digest!=expected_digest:raise HTTPException(409,'Action version changed')
    if approved:
        if digest(step.plan)!=step.digest:raise HTTPException(409,'Stored action integrity check failed')
        canonical(json.loads(step.plan))
        job=session.get(Job,wid)
        if not permitted(session,org,job.submitted_by,principal.subject):
            raise HTTPException(409,'Execution is paused or submitter permission was revoked')
    expires=step.approval_until
    if expires is None or expires.replace(tzinfo=now().tzinfo) <=now():raise HTTPException(409,'Approval expired; request fresh review')
    if approved and json.loads(step.plan)['action'] in APPROVAL and not json.loads(step.plan).get('account_id'):
        raise HTTPException(409,'Select an account through an owner edit before approval')
    step.approved_by=principal.subject if approved else None
    step.status='approved' if approved else 'rejected';wf.status='queued' if approved else 'rejected'
    job=session.get(Job,wid)
    if job.status=='awaiting_approval':job.status='queued' if approved else 'rejected'
    session.add(AuditEvent(organization_id=org,actor=principal.subject,resource_id=sid,event='step.'+step.status))
    return {'status':wf.status}

def cancel(session,org,principal,wid):
    wf=scoped(session,org,principal,wid,True)
    if wf.status=='completed':raise HTTPException(409,'Completed workflow cannot be cancelled')
    wf.status='cancelled'
    session.add(AuditEvent(organization_id=org,actor=principal.subject,resource_id=wid,event='workflow.cancelled'))
    return {'status':wf.status}

class RunState(TypedDict):
    id:str
    continue_run:bool

def run(sessions,wid,execute):
    """Internal worker API only. execute is a reviewed adapter, never model-selected code.

    Persisted rows own progress. The graph deliberately has no second checkpointer;
    this is bounded sequential execution, not completed conversational planning.
    """
    def advance(state):
        with sessions.begin() as session:
            wf=session.scalar(select(Workflow).where(Workflow.id==wid).with_for_update())
            if wf is None:raise ValueError('Unknown workflow')
            job=session.get(Job,wid)
            if not permitted(session,wf.organization_id,job.submitted_by):
                return {'continue_run':False}
            if wf.status in ('completed','cancelled','rejected','needs_review'):return {'continue_run':False}
            step=session.scalar(select(WorkflowStep).where(WorkflowStep.workflow_id==wid,WorkflowStep.status!='completed').order_by(WorkflowStep.position).limit(1))
            if step is None:wf.status='completed';return {'continue_run':False}
            if step.status=='running':
                # Another worker may still be active, or crashed after an external effect.
                # Never steal or repeat a running step.
                return {'continue_run':False}
            if step.status=='awaiting_approval':return {'continue_run':False}
            if step.status not in ('pending','approved'):
                wf.status='needs_review';return {'continue_run':False}
            plan=json.loads(step.plan)
            if digest(step.plan)!=step.digest:raise ValueError('Corrupt plan')
            canonical(plan)
            if plan['action'] in APPROVAL and step.status!='approved':
                step.status='awaiting_approval';step.approval_until=now()+timedelta(minutes=15);wf.status='awaiting_approval'
                return {'continue_run':False}
            if step.status=='approved':
                if plan['action'] in APPROVAL and not plan.get('account_id'):
                    step.status='awaiting_approval';step.approved_by=None;step.approval_until=now()+timedelta(minutes=15);wf.status='awaiting_approval'
                    return {'continue_run':False}
                if not step.approved_by or not permitted(session,wf.organization_id,job.submitted_by,step.approved_by):
                    step.status='awaiting_approval';step.approved_by=None;step.approval_until=now()+timedelta(minutes=15);wf.status='awaiting_approval'
                    return {'continue_run':False}
                deadline=step.approval_until
                if deadline is None or deadline.replace(tzinfo=now().tzinfo)<=now():
                    step.status='awaiting_approval';step.approval_until=now()+timedelta(minutes=15);wf.status='awaiting_approval'
                    return {'continue_run':False}
            step.status='running';wf.status='running';sid=step.id;org=wf.organization_id
            session.add(AuditEvent(organization_id=org,actor='worker',resource_id=sid,event='step.running'))
        try:
            result=execute(org,plan,sid)
            if not isinstance(result,dict) or result.get('verified') is not True:raise ValueError('Unverified outcome')
            result_json=json.dumps(result,ensure_ascii=False,allow_nan=False)
            if len(result_json.encode('utf-8'))>64000:raise ValueError('Output too large')
            outcome='completed'
        except Exception:
            outcome='needs_review';result_json=json.dumps({'message':'Outcome uncertain or unverified; reconcile before retrying'})
        with sessions.begin() as session:
            wf=session.scalar(select(Workflow).where(Workflow.id==wid).with_for_update())
            step=session.get(WorkflowStep,sid);step.status=outcome;step.result=result_json
            session.add(AuditEvent(organization_id=org,actor='worker',resource_id=sid,event='step.'+outcome))
            if wf.status=='cancelled':return {'continue_run':False}
            wf.status='queued' if outcome=='completed' else 'needs_review'
        return {'continue_run':outcome=='completed'}
    graph=StateGraph(RunState);graph.add_node('advance',advance);graph.add_edge(START,'advance')
    graph.add_conditional_edges('advance',lambda s:'advance' if s['continue_run'] else END)
    return graph.compile().invoke({'id':wid,'continue_run':True},{'recursion_limit':25})


def edit_step(session,org,principal,wid,sid,expected_digest,plan):
    wf=scoped(session,org,principal,wid,True)
    require_owner(session,org,principal)
    step=session.scalar(select(WorkflowStep).where(WorkflowStep.id==sid,WorkflowStep.workflow_id==wid))
    if step is None:raise HTTPException(404,'Step not found')
    if wf.status in ('completed','cancelled','rejected','needs_review') or step.status not in ('pending','awaiting_approval','approved'):
        raise HTTPException(409,'Step cannot be edited in current state')
    if step.digest!=expected_digest:raise HTTPException(409,'Action version changed')
    encoded=canonical(plan)
    step.plan=encoded;step.digest=digest(encoded);step.status='pending';step.approved_by=None;step.approval_until=None
    wf.status='queued'
    session.add(AuditEvent(organization_id=org,actor=principal.subject,resource_id=sid,event='step.edited_approval_invalidated'))
    return {'digest':step.digest,'status':step.status}


def preview(session,org,principal,plans):
    """Pure validation: never enqueue, reserve budget, call providers or approve."""
    authorize(session,org,principal,True)
    if not 1<=len(plans)<=20:raise HTTPException(400,'Preview requires 1–20 steps')
    items=[]
    for plan in plans:
        encoded=canonical(plan)
        items.append({'plan':json.loads(encoded),'digest':digest(encoded),
                      'approval_required':plan['action'] in APPROVAL,
                      'effect':TOOLS[plan['action']][1]})
    return {'mode':'preview','executed':False,'steps':items,
            'limitations':['No provider access or live data fetched','Account and resource permissions require execution-time validation']}


def refresh_review(session,org,principal,wid,sid,expected_digest):
    wf=scoped(session,org,principal,wid,True)
    require_owner(session,org,principal)
    step=session.scalar(select(WorkflowStep).where(WorkflowStep.id==sid,WorkflowStep.workflow_id==wid))
    if step is None or wf.status!='awaiting_approval' or step.status!='awaiting_approval':
        raise HTTPException(409,'Step is not awaiting review')
    if step.digest!=expected_digest:raise HTTPException(409,'Action version changed')
    step.approved_by=None;step.approval_until=now()+timedelta(minutes=15)
    session.add(AuditEvent(organization_id=org,actor=principal.subject,resource_id=sid,event='step.review_refreshed'))
    return {'digest':step.digest,'approval_until':step.approval_until.isoformat()}


def exceptions(session,org,principal):
    require_owner(session,org,principal)
    items=session.scalars(select(Workflow).where(Workflow.organization_id==org,Workflow.status.in_(('awaiting_approval','needs_review'))).order_by(Workflow.id).limit(100)).all()
    return {'workflows':[summary(session,wf) for wf in items]}
