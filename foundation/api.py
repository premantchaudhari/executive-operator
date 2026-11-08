import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select,text
from sqlalchemy.orm import Session
from .auth import OIDCVerifier
from .database import database
from .models import Job,Artifact
from .service import authorize,enqueue
from . import workflows,conversations
from .integrations import Gateway
from .policy import set_paused
from operator_app.native_tools import catalog,APPS
from .access import invite,accept,role_change

class Submission(BaseModel):
    model_config=ConfigDict(extra='forbid')
    instruction: str=Field(min_length=1,max_length=20000)


class WorkflowBody(Submission):
    steps:list[dict]=Field(min_length=1,max_length=20)
class DecisionBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    digest:str=Field(min_length=64,max_length=64)
    approved:bool=Field(strict=True)

class PauseBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    paused:bool=Field(strict=True)
class ConnectionResumeBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    digest:str=Field(min_length=64,max_length=64)
    account_id:str=Field(min_length=1,max_length=255)
class EditBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    digest:str=Field(min_length=64,max_length=64)
    plan:dict

class InviteBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    subject:str=Field(min_length=1,max_length=255)
    role:str
class AcceptBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    token:str=Field(min_length=32,max_length=128)


def create_app(sessions=None,verifier=None,gateway_factory=None):
    gateway_factory=gateway_factory or Gateway.configured
    production=sessions is None
    engine=None
    if production:engine,sessions=database()
    verifier=verifier or OIDCVerifier()
    @asynccontextmanager
    async def lifespan(app):
        yield
        if engine is not None:engine.dispose()
    app=FastAPI(title='Executive Operator Foundation',version='0.3.0',lifespan=lifespan,docs_url=None if production else '/docs',redoc_url=None)
    bearer=HTTPBearer(auto_error=False)
    def db():
        with sessions() as session:
            with session.begin():yield session
    def identity(credentials:HTTPAuthorizationCredentials|None=Depends(bearer)):
        if credentials is None:raise HTTPException(401,'Authentication required')
        return verifier(credentials.credentials)
    @app.middleware('http')
    async def headers(request,call_next):
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        return response
    @app.get('/health/live')
    def live():return {'ok':True}
    @app.get('/health/ready')
    def ready(session:Session=Depends(db)):
        try:
            revision=session.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
            if revision!='0005':raise ValueError('Unsupported schema')
        except Exception:raise HTTPException(503,'Database or schema unavailable') from None
        return {'ok':True}
    @app.post('/v1/organizations/{org}/jobs',status_code=202)
    def submit(org:str,body:Submission,key:str=Header(alias='Idempotency-Key',min_length=1,max_length=128),principal=Depends(identity),session:Session=Depends(db)):
        authorize(session,org,principal,True)
        job=enqueue(session,org,principal,key,body.model_dump())
        return {'id':job.id,'status':job.status}
    @app.get('/v1/organizations/{org}/jobs/{job_id}')
    def get_job(org:str,job_id:str,principal=Depends(identity),session:Session=Depends(db)):
        authorize(session,org,principal)
        job=session.scalar(select(Job).where(Job.id==job_id,Job.organization_id==org))
        if job is None:raise HTTPException(404,'Job not found')
        return {'id':job.id,'status':job.status,'instruction':json.loads(job.payload)['instruction']}
    @app.get('/v1/organizations/{org}/artifacts/{artifact_id}')
    def artifact(org:str,artifact_id:str,principal=Depends(identity),session:Session=Depends(db)):
        authorize(session,org,principal)
        item=session.scalar(select(Artifact).where(Artifact.id==artifact_id,Artifact.organization_id==org))
        if item is None:raise HTTPException(404,'Artifact not found')
        return {'id':item.id,'filename':item.filename,'delivery':'not_enabled'}
    @app.post('/v1/organizations/{org}/invitations',status_code=201)
    def invitation(org:str,body:InviteBody,principal=Depends(identity),session:Session=Depends(db)):
        return invite(session,org,principal,body.subject,body.role)
    @app.post('/v1/invitations/accept')
    def accept_invitation(body:AcceptBody,principal=Depends(identity),session:Session=Depends(db)):
        return accept(session,principal,body.token)
    @app.patch('/v1/organizations/{org}/members')
    def change_role(org:str,body:InviteBody,principal=Depends(identity),session:Session=Depends(db)):
        return role_change(session,org,principal,body.subject,body.role)
    @app.post('/v1/organizations/{org}/read-data-preview')
    def read_data_preview(org:str,body:WorkflowBody,principal=Depends(identity)):
        from .policy import require_owner
        from .dry_run import preview
        import os
        with sessions.begin() as session:require_owner(session,org,principal)
        # Disabled until deployment supplies preview usage limits and reviewed tool mappings.
        if os.getenv('READ_DATA_PREVIEW_ENABLED')!='true':
            raise HTTPException(503,'Read-data preview is not enabled for this deployment')
        try:return preview(sessions,org,principal,body.steps,gateway_factory())
        except HTTPException:raise
        except ValueError:raise HTTPException(400,'Invalid preview or unverified read') from None
        except Exception:raise HTTPException(503,'Preview provider unavailable') from None
    @app.post('/v1/organizations/{org}/preview')
    def preview_workflow(org:str,body:WorkflowBody,principal=Depends(identity),session:Session=Depends(db)):
        return workflows.preview(session,org,principal,body.steps)
    @app.get('/v1/organizations/{org}/exceptions')
    def exception_inbox(org:str,principal=Depends(identity),session:Session=Depends(db)):
        return workflows.exceptions(session,org,principal)
    @app.post('/v1/organizations/{org}/workflows/{wid}/steps/{sid}/review')
    def refresh_review(org:str,wid:str,sid:str,body:DecisionBody,principal=Depends(identity),session:Session=Depends(db)):
        if body.approved:raise HTTPException(400,'Review refresh is not approval')
        return workflows.refresh_review(session,org,principal,wid,sid,body.digest)
    @app.post('/v1/organizations/{org}/workflows',status_code=202)
    def create_workflow(org:str,body:WorkflowBody,key:str=Header(alias='Idempotency-Key',min_length=1,max_length=128),principal=Depends(identity),session:Session=Depends(db)):
        wf=workflows.create(session,org,principal,key,body.instruction,body.steps)
        return workflows.summary(session,wf)
    @app.get('/v1/organizations/{org}/workflows/{wid}')
    def get_workflow(org:str,wid:str,principal=Depends(identity),session:Session=Depends(db)):
        return workflows.summary(session,workflows.scoped(session,org,principal,wid))
    @app.post('/v1/organizations/{org}/workflows/{wid}/steps/{sid}/decision')
    def decide_workflow(org:str,wid:str,sid:str,body:DecisionBody,principal=Depends(identity),session:Session=Depends(db)):
        return workflows.decide(session,org,principal,wid,sid,body.digest,body.approved)
    @app.post('/v1/organizations/{org}/workflows/{wid}/cancel')
    def cancel_workflow(org:str,wid:str,principal=Depends(identity),session:Session=Depends(db)):
        return workflows.cancel(session,org,principal,wid)
    @app.post('/v1/organizations/{org}/workflows/{wid}/steps/{sid}/connection')
    def resume_connected_step(org:str,wid:str,sid:str,body:ConnectionResumeBody,principal=Depends(identity),session:Session=Depends(db)):
        from .integrations import ConnectionRequired
        from .policy import require_owner
        # Check role before constructing a provider client or reading accounts.
        require_owner(session,org,principal)
        try:return workflows.resume_connection(session,org,principal,wid,sid,body.digest,body.account_id,gateway_factory())
        except HTTPException:raise
        except ConnectionRequired:raise HTTPException(404,'Connected account not found') from None
        except Exception:raise HTTPException(503,'Connection verification unavailable; workflow remains paused') from None
    @app.post('/v1/organizations/{org}/conversations',status_code=201)
    def new_conversation(org:str,principal=Depends(identity),session:Session=Depends(db)):
        return {'id':conversations.start(session,org,principal).id}
    @app.get('/v1/organizations/{org}/conversations/{cid}')
    def conversation_history(org:str,cid:str,principal=Depends(identity),session:Session=Depends(db)):
        return conversations.history(session,conversations.scoped(session,org,principal,cid))
    @app.post('/v1/organizations/{org}/conversations/{cid}/messages',status_code=202)
    def conversation_message(org:str,cid:str,body:Submission,key:str=Header(alias='Idempotency-Key',min_length=1,max_length=128),principal=Depends(identity),session:Session=Depends(db)):
        turn=conversations.message(session,org,principal,cid,key,body.instruction)
        return {'turn_id':turn.id,'status':turn.status}
    @app.get('/v1/organizations/{org}/integrations/catalog')
    def integration_catalog(org:str,principal=Depends(identity),session:Session=Depends(db)):
        authorize(session,org,principal)
        return {'tools':catalog()}
    @app.get('/v1/organizations/{org}/integrations/{integration}/status')
    def integration_status(org:str,integration:str,principal=Depends(identity),session:Session=Depends(db)):
        member=authorize(session,org,principal)
        if member.role not in ('owner','admin'):raise HTTPException(403,'Owner or admin required')
        if integration not in APPS:raise HTTPException(404,'Integration not found')
        try:return gateway_factory().status(org,integration)
        except Exception:raise HTTPException(503,'Integration status unavailable') from None
    @app.post('/v1/organizations/{org}/integrations/{integration}/connect')
    def integration_connect(org:str,integration:str,principal=Depends(identity),session:Session=Depends(db)):
        member=authorize(session,org,principal)
        if member.role!='owner':raise HTTPException(403,'Owner required to connect organization accounts')
        if integration not in APPS:raise HTTPException(404,'Integration not found')
        try:return gateway_factory().connect(org,integration)
        except Exception:raise HTTPException(503,'Connection configuration unavailable') from None
    @app.post('/v1/organizations/{org}/pause')
    def pause_organization(org:str,body:PauseBody,principal=Depends(identity),session:Session=Depends(db)):
        return set_paused(session,org,principal,body.paused)
    @app.post('/v1/organizations/{org}/integrations/{integration}/accounts/{account_id}/reconnect')
    def integration_reconnect(org:str,integration:str,account_id:str,principal=Depends(identity),session:Session=Depends(db)):
        return connection_action(session,org,principal,integration,account_id,'reconnect')
    @app.post('/v1/organizations/{org}/integrations/{integration}/accounts/{account_id}/revoke')
    def integration_revoke(org:str,integration:str,account_id:str,principal=Depends(identity),session:Session=Depends(db)):
        return connection_action(session,org,principal,integration,account_id,'revoke')
    def connection_action(session,org,principal,integration,account_id,operation):
        from .policy import require_owner
        from .integrations import ConnectionRequired
        from .models import AuditEvent
        from uuid import uuid5,NAMESPACE_URL
        require_owner(session,org,principal)
        if integration not in APPS:raise HTTPException(404,'Integration not found')
        if not 1<=len(account_id)<=255:raise HTTPException(400,'Invalid connected account')
        try:result=getattr(gateway_factory(),operation)(org,integration,account_id)
        except ConnectionRequired:raise HTTPException(404,'Connected account not found') from None
        except Exception:raise HTTPException(503,'Connection operation unconfirmed; check status before retrying') from None
        reference=str(uuid5(NAMESPACE_URL,json.dumps([org,integration,account_id])))
        session.add(AuditEvent(organization_id=org,actor=principal.subject,resource_id=reference,event='connection.'+operation))
        return result
    @app.patch('/v1/organizations/{org}/workflows/{wid}/steps/{sid}')
    def edit_workflow_step(org:str,wid:str,sid:str,body:EditBody,principal=Depends(identity),session:Session=Depends(db)):
        return workflows.edit_step(session,org,principal,wid,sid,body.digest,body.plan)
    return app
