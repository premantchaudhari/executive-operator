import unittest
from fastapi import HTTPException
from foundation import workflows,policy
from foundation.auth import Principal
from foundation.models import Membership
import test_workflows as fixtures

class PolicyTests(unittest.TestCase):
    setUp=fixtures.WorkflowTests.setUp
    tearDown=fixtures.WorkflowTests.tearDown
    create=fixtures.WorkflowTests.create
    state=fixtures.WorkflowTests.state
    def test_pause_blocks_new_steps(self):
        wid=self.create([fixtures.READ]);calls=[]
        with self.sessions.begin() as s:policy.set_paused(s,'a',Principal('alice'),True)
        workflows.run(self.sessions,wid,lambda *a:calls.append(a));self.assertEqual(calls,[])
        with self.sessions.begin() as s:policy.set_paused(s,'a',Principal('alice'),False)
        workflows.run(self.sessions,wid,lambda *a:{'verified':True});self.assertEqual(self.state(wid)['status'],'completed')
    def test_edit_invalidates_previous_approval(self):
        wid=self.create([fixtures.SEND]);workflows.run(self.sessions,wid,lambda *a:{'verified':True});step=self.state(wid)['steps'][0]
        with self.sessions.begin() as s:workflows.decide(s,'a',Principal('alice'),wid,step['id'],step['digest'],True)
        changed={**fixtures.SEND,'arguments':{**fixtures.SEND['arguments'],'body':'Changed content'}}
        with self.sessions.begin() as s:workflows.edit_step(s,'a',Principal('alice'),wid,step['id'],step['digest'],changed)
        calls=[];workflows.run(self.sessions,wid,lambda *a:calls.append(a));self.assertEqual(calls,[])
        self.assertEqual(self.state(wid)['status'],'awaiting_approval')
    def test_operator_cannot_approve(self):
        wid=self.create([fixtures.SEND]);workflows.run(self.sessions,wid,lambda *a:{'verified':True});step=self.state(wid)['steps'][0]
        with self.sessions.begin() as s:s.add(Membership(organization_id='a',subject='operator',role='operator'))
        with self.sessions.begin() as s:
            with self.assertRaises(HTTPException):workflows.decide(s,'a',Principal('operator'),wid,step['id'],step['digest'],True)
    def test_revoked_submitter_blocks_dispatch(self):
        wid=self.create([fixtures.READ]);calls=[]
        with self.sessions.begin() as s:s.get(Membership,('a','alice')).role='viewer'
        workflows.run(self.sessions,wid,lambda *a:calls.append(a));self.assertEqual(calls,[])
