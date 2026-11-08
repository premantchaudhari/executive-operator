"""One leased dispatch across planning and persisted native workflows."""
from sqlalchemy import select
from .models import Job,Workflow,ConversationTurn,AuditEvent,now
from .service import claim,recover
from .heartbeat import LeaseHeartbeat
from .conversations import plan_turn
from .native_worker import execute_workflow


def dispatch_once(sessions,planner,gateway):
    with sessions.begin() as s:
        recover(s);job=claim(s,lease_seconds=300)
        if job is None:return None
        jid,token,org=job.id,job.lease_token,job.organization_id
        turn=s.scalar(select(ConversationTurn).where(ConversationTurn.job_id==jid));tid=turn.id if turn else None
    outcome='needs_review'
    try:
        with LeaseHeartbeat(sessions,jid,token) as heartbeat:
            def leased_planner(context):
                heartbeat.check();result=planner(context);heartbeat.check();return result
            class LeasedGateway:
                def execute(self,*args,**kwargs):
                    heartbeat.check()
                    result=gateway.execute(*args,**kwargs)
                    heartbeat.check()
                    return result
            if tid:plan_turn(sessions,tid,leased_planner)
            with sessions() as s:
                has_workflow=s.get(Workflow,jid) is not None
                turn=s.get(ConversationTurn,tid) if tid else None
                if turn and turn.status=='clarification':outcome='completed'
            if has_workflow:
                execute_workflow(sessions,jid,LeasedGateway())
                with sessions() as s:
                    state=s.get(Workflow,jid).status
                    outcome=state if state in ('completed','awaiting_approval','awaiting_connection','cancelled','rejected','needs_review') else 'needs_review'
            heartbeat.check()
    except Exception:outcome='needs_review'
    with sessions.begin() as s:
        job=s.scalar(select(Job).where(Job.id==jid).with_for_update())
        if job.status!='running' or job.lease_token!=token or job.lease_until.replace(tzinfo=now().tzinfo)<=now():
            raise ValueError('Dispatch lease lost; reconcile before retrying')
        workflow=s.scalar(select(Workflow).where(Workflow.id==jid).with_for_update())
        if workflow:
            if workflow.status in ('cancelled','rejected'):outcome=workflow.status
            elif outcome in ('awaiting_approval','awaiting_connection') and workflow.status=='queued':
                # Owner decision/edit raced the dispatcher's final bookkeeping.
                outcome='queued'
        job.status=outcome;job.lease_token=None;job.lease_until=None
        s.add(AuditEvent(organization_id=org,actor='dispatcher',resource_id=jid,event='job.'+outcome))
    return {'job_id':jid,'status':outcome}
