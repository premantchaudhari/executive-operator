import os
import unittest
from datetime import timedelta
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,select,delete
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from foundation.models import Base,Organization,Membership,Job,AuditEvent,Artifact,Budget,Reservation,Invitation,Workflow,WorkflowStep,Conversation,ConversationTurn,now
from foundation.auth import Principal
from foundation.api import create_app
from foundation.service import claim,finish,recover

class FoundationTests(unittest.TestCase):
    def setUp(self):
        url=os.getenv('TEST_DATABASE_URL','sqlite://')
        if url!='sqlite://' and '/operator_test' not in url:raise RuntimeError('Use dedicated operator_test database')
        self.engine=create_engine(url,**({'poolclass':StaticPool,'connect_args':{'check_same_thread':False}} if url=='sqlite://' else {}))
        Base.metadata.create_all(self.engine)
        self.sessions=sessionmaker(self.engine,expire_on_commit=False)
        with self.sessions.begin() as s:
            for model in (AuditEvent,ConversationTurn,Conversation,WorkflowStep,Workflow,Reservation,Invitation,Budget,Artifact,Job,Membership,Organization):s.execute(delete(model))
            s.add_all([Organization(id='a',name='A'),Organization(id='b',name='B')]);s.flush()
            s.add_all([Budget(organization_id='a',limit_microusd=1000000),Budget(organization_id='b',limit_microusd=1000000)])
            s.add_all([Membership(organization_id='a',subject='alice',role='owner'),Membership(organization_id='b',subject='bob',role='owner'),Membership(organization_id='a',subject='reader',role='viewer')])
        def verify(token):
            if token not in ('alice','bob','reader'):raise HTTPException(401,'Invalid token')
            return Principal(token)
        self.client=TestClient(create_app(self.sessions,verify))
    def tearDown(self):self.client.close();self.engine.dispose()
    def submit(self,who='alice',org='a',key='one',text='Read inbox'):
        return self.client.post(f'/v1/organizations/{org}/jobs',headers={'Authorization':'Bearer '+who,'Idempotency-Key':key},json={'instruction':text})
    def test_authenticated_enqueue(self):
        r=self.submit();self.assertEqual(r.status_code,202)
        with self.sessions() as s:
            self.assertEqual(len(s.scalars(select(AuditEvent)).all()),1)
            self.assertEqual(s.get(Job,r.json()['id']).submitted_by,'alice')
    def test_cross_tenant_submit(self):self.assertEqual(self.submit(org='b').status_code,404)
    def test_viewer_cannot_submit(self):self.assertEqual(self.submit(who='reader').status_code,403)
    def test_cross_tenant_read(self):
        job=self.submit().json()['id']
        r=self.client.get(f'/v1/organizations/b/jobs/{job}',headers={'Authorization':'Bearer bob'})
        self.assertEqual(r.status_code,404)
    def test_auth_required(self):
        self.assertEqual(self.client.get('/v1/organizations/a/jobs/any').status_code,401)
    def test_duplicate_key_and_conflict(self):
        a=self.submit();b=self.submit()
        self.assertEqual(a.json()['id'],b.json()['id'])
        self.assertEqual(self.submit(text='Different').status_code,409)
    def test_payload_cannot_set_tenant(self):
        r=self.client.post('/v1/organizations/a/jobs',headers={'Authorization':'Bearer alice','Idempotency-Key':'x'},json={'instruction':'x','organization_id':'b'})
        self.assertEqual(r.status_code,422)
    def test_worker_lease(self):
        self.submit()
        with self.sessions.begin() as s:
            job=claim(s);job_id,token=job.id,job.lease_token
        with self.sessions.begin() as s:self.assertIsNone(claim(s))
        with self.sessions.begin() as s:
            with self.assertRaises(ValueError):finish(s,job_id,'forged','completed')
        with self.sessions.begin() as s:finish(s,job_id,token,'completed')
        with self.sessions.begin() as s:
            with self.assertRaises(ValueError):finish(s,job_id,token,'completed')
    def test_expired_lease_not_retried(self):
        self.submit()
        with self.sessions.begin() as s:
            job=claim(s);job.lease_until=now()-timedelta(seconds=1)
        with self.sessions.begin() as s:self.assertEqual(recover(s),1);self.assertIsNone(claim(s))
        with self.sessions() as s:self.assertEqual(s.scalar(select(Job)).status,'needs_review')
    def test_artifact_does_not_expose_storage_key(self):
        with self.sessions.begin() as s:s.add(Artifact(id='file-a',organization_id='a',object_key='secret/a/object',filename='report.csv'))
        for org,who,status in [('a','alice',200),('b','bob',404)]:
            r=self.client.get(f'/v1/organizations/{org}/artifacts/file-a',headers={'Authorization':'Bearer '+who})
            self.assertEqual(r.status_code,status);self.assertNotIn('secret/a/object',r.text)

    @unittest.skipUnless(os.getenv('TEST_DATABASE_URL'), 'Requires PostgreSQL')
    def test_postgres_skip_locked_claim(self):
        self.submit()
        with self.sessions.begin() as first:
            self.assertIsNotNone(claim(first))
            with self.sessions.begin() as second:self.assertIsNone(claim(second))

    def test_budget_reserved_once(self):
        self.submit();self.submit()
        with self.sessions() as s:self.assertEqual(s.get(Budget,'a').reserved_microusd,100000)
    def test_budget_exhaustion(self):
        with self.sessions.begin() as s:s.get(Budget,'a').limit_microusd=0
        self.assertEqual(self.submit().status_code,402)
    def test_invitation_identity_and_replay(self):
        headers={'Authorization':'Bearer alice'}
        r=self.client.post('/v1/organizations/a/invitations',headers=headers,json={'subject':'bob','role':'operator'})
        self.assertEqual(r.status_code,201);token=r.json()['token']
        self.assertEqual(self.client.post('/v1/invitations/accept',headers=headers,json={'token':token}).status_code,404)
        target={'Authorization':'Bearer bob'}
        self.assertEqual(self.client.post('/v1/invitations/accept',headers=target,json={'token':token}).status_code,200)
        self.assertEqual(self.client.post('/v1/invitations/accept',headers=target,json={'token':token}).status_code,409)
    def test_viewer_cannot_invite(self):
        self.assertEqual(self.client.post('/v1/organizations/a/invitations',headers={'Authorization':'Bearer reader'},json={'subject':'bob','role':'admin'}).status_code,403)
    def test_owner_cannot_be_demoted(self):
        self.assertEqual(self.client.patch('/v1/organizations/a/members',headers={'Authorization':'Bearer alice'},json={'subject':'alice','role':'viewer'}).status_code,409)
