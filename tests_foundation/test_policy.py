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
    def approve(self,wid):
        step=self.state(wid)['steps'][0]
        with self.sessions.begin() as s:workflows.decide(s,'a',Principal('alice'),wid,step['id'],step['digest'],True)
        return step
    def test_preview_has_no_job_budget_or_effect(self):
        from sqlalchemy import select,func
        from foundation.models import Job,Reservation,AuditEvent
        with self.sessions.begin() as s:
            result=workflows.preview(s,'a',Principal('alice'),[fixtures.SEND])
            self.assertFalse(result['executed']);self.assertTrue(result['steps'][0]['approval_required'])
            for model in (Job,Reservation,AuditEvent):self.assertEqual(s.scalar(select(func.count()).select_from(model)),0)
    def test_unsupported_layers_fail_closed(self):
        for plan in ({'action':'sandbox.python','arguments':{'code':'print(1)'}},{'action':'browser.inspect','arguments':{'url':'https://example.com'}}):
            with self.sessions.begin() as s:
                with self.assertRaises(HTTPException):workflows.preview(s,'a',Principal('alice'),[plan])
    def test_expired_review_refresh_and_replay(self):
        from foundation.models import WorkflowStep,now
        from datetime import timedelta
        wid=self.create([fixtures.SEND]);workflows.run(self.sessions,wid,lambda *a:None);step=self.state(wid)['steps'][0]
        with self.sessions.begin() as s:s.get(WorkflowStep,step['id']).approval_until=now()-timedelta(seconds=1)
        with self.sessions.begin() as s:
            with self.assertRaises(HTTPException):workflows.decide(s,'a',Principal('alice'),wid,step['id'],step['digest'],True)
        with self.sessions.begin() as s:workflows.refresh_review(s,'a',Principal('alice'),wid,step['id'],step['digest'])
        self.approve(wid)
        with self.sessions.begin() as s:
            with self.assertRaises(HTTPException):workflows.decide(s,'a',Principal('alice'),wid,step['id'],step['digest'],True)
        calls=[];workflows.run(self.sessions,wid,lambda *a:(calls.append(a) or {'verified':True}));workflows.run(self.sessions,wid,lambda *a:calls.append(a))
        self.assertEqual(len(calls),1)
    def test_approver_downgrade_invalidates_grant(self):
        wid=self.create([fixtures.SEND]);workflows.run(self.sessions,wid,lambda *a:None);self.approve(wid)
        with self.sessions.begin() as s:s.get(Membership,('a','alice')).role='operator'
        calls=[];workflows.run(self.sessions,wid,lambda *a:calls.append(a));self.assertEqual(calls,[])
        self.assertEqual(self.state(wid)['status'],'awaiting_approval')
    def test_rejection_never_dispatches(self):
        wid=self.create([fixtures.SEND]);workflows.run(self.sessions,wid,lambda *a:None);step=self.state(wid)['steps'][0]
        with self.sessions.begin() as s:workflows.decide(s,'a',Principal('alice'),wid,step['id'],step['digest'],False)
        calls=[];workflows.run(self.sessions,wid,lambda *a:calls.append(a));self.assertEqual(calls,[])
    def test_owner_exception_inbox_is_tenant_scoped(self):
        wid=self.create([fixtures.SEND]);workflows.run(self.sessions,wid,lambda *a:None)
        with self.sessions.begin() as s:
            self.assertEqual(len(workflows.exceptions(s,'a',Principal('alice'))['workflows']),1)
            self.assertEqual(workflows.exceptions(s,'b',Principal('bob'))['workflows'],[])
            with self.assertRaises(HTTPException):workflows.exceptions(s,'a',Principal('reader'))
