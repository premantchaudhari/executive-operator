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

class Submission(BaseModel):
    model_config=ConfigDict(extra='forbid')
    instruction: str=Field(min_length=1,max_length=20000)


def create_app(sessions=None,verifier=None):
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
            if revision!='0001':raise ValueError('Unsupported schema')
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
    return app
