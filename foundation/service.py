import json
from datetime import timedelta
from sqlalchemy import select, update
from fastapi import HTTPException
from .models import Membership, Job, AuditEvent, Artifact, now, identifier

def authorize(session,org,principal,write=False):
    membership=session.get(Membership,(org,principal.subject))
    if membership is None: raise HTTPException(404,'Organization not found')
    if membership.role not in ('owner','admin','operator','viewer'):
        raise HTTPException(403,'Invalid membership role')
    if write and membership.role=='viewer': raise HTTPException(403,'Read-only membership')
    return membership

def enqueue(session,org,principal,key,payload):
    # Serialize per-organization admission to prevent races across API workers.
    from .models import Organization
    session.execute(select(Organization).where(Organization.id==org).with_for_update()).scalar_one()
    authorize(session,org,principal,True)
    serialized=json.dumps(payload,sort_keys=True,separators=(',',':'))
    existing=session.scalar(select(Job).where(Job.organization_id==org,Job.request_key==key))
    if existing:
        if existing.payload!=serialized: raise HTTPException(409,'Idempotency key conflict')
        return existing
    job=Job(id=identifier(),organization_id=org,submitted_by=principal.subject,request_key=key,payload=serialized)
    session.add(job)
    session.add(AuditEvent(organization_id=org,actor=principal.subject,resource_id=job.id,event='job.queued'))
    session.flush()
    return job

def claim(session,lease_seconds=60):
    if not 1<=lease_seconds<=300: raise ValueError('Lease must be 1–300 seconds')
    job=session.scalar(select(Job).where(Job.status=='queued').order_by(Job.created_at,Job.id).with_for_update(skip_locked=True).limit(1))
    if job is None:return None
    job.status='running';job.attempts+=1;job.lease_token=identifier();job.lease_until=now()+timedelta(seconds=lease_seconds)
    session.add(AuditEvent(organization_id=job.organization_id,actor='worker',resource_id=job.id,event='job.claimed'))
    session.flush()
    return job

def finish(session,job_id,lease_token,status):
    if status not in ('completed','needs_review','failed'):raise ValueError('Invalid terminal status')
    row=session.execute(update(Job).where(Job.id==job_id,Job.status=='running',Job.lease_token==lease_token,Job.lease_until>now()).values(status=status,lease_token=None,lease_until=None).returning(Job.organization_id)).first()
    if row is None:raise ValueError('Expired or invalid worker lease')
    session.add(AuditEvent(organization_id=row[0],actor='worker',resource_id=job_id,event='job.'+status))

def recover(session):
    # Never requeue expired work: a remote side effect may already have occurred.
    rows=session.execute(update(Job).where(Job.status=='running',Job.lease_until<now()).values(status='needs_review',lease_token=None,lease_until=None).returning(Job.id,Job.organization_id)).all()
    for job_id,org in rows:session.add(AuditEvent(organization_id=org,actor='recovery',resource_id=job_id,event='job.lease_expired'))
    return len(rows)
