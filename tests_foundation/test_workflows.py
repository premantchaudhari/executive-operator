import unittest
from fastapi import HTTPException
from sqlalchemy import select
import test_foundation as fixtures
from foundation import workflows
from foundation.models import Workflow,WorkflowStep
from foundation.auth import Principal
READ={'action':'gmail.read','arguments':{'query':'is:unread'}}
SEND={'account_id':'account-a','action':'gmail.send','arguments':{'recipient_email':'client@example.com','subject':'Review','body':'Exact approved body'}}
class WorkflowTests(unittest.TestCase):
    setUp=fixtures.FoundationTests.setUp
    tearDown=fixtures.FoundationTests.tearDown
    def create(self,steps):
        with self.sessions.begin() as s:return workflows.create(s,'a',Principal('alice'),'workflow-key','Business workflow',steps).id
    def state(self,wid):
        with self.sessions() as s:return workflows.summary(s,s.get(Workflow,wid))
    def test_pause_resume_without_repeating_completed_read(self):
        wid=self.create([READ,SEND]);calls=[]
        def execute(org,plan,key):calls.append(plan['action']);return {'verified':True,'receipt':key}
        workflows.run(self.sessions,wid,execute)
        snapshot=self.state(wid);self.assertEqual(snapshot['status'],'awaiting_approval')
        self.assertEqual(calls,['gmail.read']);step=snapshot['steps'][1]
        # New database sessions emulate a resumed invocation, not an in-memory continuation.
        with self.sessions.begin() as s:workflows.decide(s,'a',Principal('alice'),wid,step['id'],step['digest'],True)
        workflows.run(self.sessions,wid,execute);workflows.run(self.sessions,wid,execute)
        self.assertEqual(calls,['gmail.read','gmail.send']);self.assertEqual(self.state(wid)['status'],'completed')
    def test_uncertain_result_stops_following_steps(self):
        wid=self.create([READ,READ]);calls=[]
        def execute(*args):calls.append(1);raise TimeoutError()
        workflows.run(self.sessions,wid,execute);workflows.run(self.sessions,wid,execute)
        self.assertEqual(len(calls),1);self.assertEqual(self.state(wid)['status'],'needs_review')
    def test_cancel_prevents_execution(self):
        wid=self.create([READ])
        with self.sessions.begin() as s:workflows.cancel(s,'a',Principal('alice'),wid)
        calls=[];workflows.run(self.sessions,wid,lambda *a:calls.append(a));self.assertEqual(calls,[])
    def test_cross_tenant_decision_fails(self):
        wid=self.create([SEND]);workflows.run(self.sessions,wid,lambda *a:{'verified':True});step=self.state(wid)['steps'][0]
        with self.sessions.begin() as s:
            with self.assertRaises(HTTPException):workflows.decide(s,'b',Principal('bob'),wid,step['id'],step['digest'],True)
    def test_wrong_digest_fails(self):
        wid=self.create([SEND]);workflows.run(self.sessions,wid,lambda *a:{'verified':True});step=self.state(wid)['steps'][0]
        with self.sessions.begin() as s:
            with self.assertRaises(HTTPException):workflows.decide(s,'a',Principal('alice'),wid,step['id'],'0'*64,True)
    def test_running_step_never_replayed(self):
        wid=self.create([READ])
        with self.sessions.begin() as s:s.scalar(select(WorkflowStep).where(WorkflowStep.workflow_id==wid)).status='running'
        calls=[];workflows.run(self.sessions,wid,lambda *a:calls.append(a));self.assertEqual(calls,[])
