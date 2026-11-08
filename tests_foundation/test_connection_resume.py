import unittest
from types import SimpleNamespace as Obj
from unittest.mock import Mock
from fastapi import HTTPException
from fastapi.testclient import TestClient
from foundation import workflows
from foundation.api import create_app
from foundation.auth import Principal
from foundation.dispatcher import dispatch_once
from foundation.integrations import Gateway,ConnectionRequired
from foundation.models import Job,WorkflowStep
from foundation.policy import set_paused
import test_workflows as fixtures

class ConnectionResumeTests(unittest.TestCase):
    setUp=fixtures.WorkflowTests.setUp
    tearDown=fixtures.WorkflowTests.tearDown
    create=fixtures.WorkflowTests.create
    state=fixtures.WorkflowTests.state
    def gateway(self):
        gateway=Mock();gateway.owned_account.return_value=Obj(status='ACTIVE')
        return gateway
    def park(self,plans=None):
        wid=self.create(plans or [fixtures.READ]);gateway=self.gateway()
        gateway.execute.side_effect=ConnectionRequired('gmail')
        self.assertEqual(dispatch_once(self.sessions,Mock(),gateway)['status'],'awaiting_connection')
        return wid,self.state(wid)['steps'][0],gateway
    def resume(self,wid,step,gateway,account='account-new',user='alice',org='a'):
        with self.sessions.begin() as s:
            return workflows.resume_connection(s,org,Principal(user),wid,step['id'],step['digest'],account,gateway)
    def test_restart_resume_preserves_completed_steps_and_does_not_replan(self):
        second={'action':'gmail.read','arguments':{'query':'from:client@example.com'}}
        wid=self.create([fixtures.READ,second,fixtures.SEND]);gateway=self.gateway()
        gateway.execute.side_effect=[{'verified':True,'receipt':'first-read'},ConnectionRequired('gmail')]
        self.assertEqual(dispatch_once(self.sessions,Mock(),gateway)['status'],'awaiting_connection')
        self.assertIsNone(dispatch_once(self.sessions,Mock(),gateway))
        paused=self.state(wid);step=paused['steps'][1]
        # Fresh application instance uses only persisted state after the pause.
        with TestClient(create_app(self.sessions,lambda token:Principal(token),lambda:gateway)) as client:
            result=client.post(f'/v1/organizations/a/workflows/{wid}/steps/{step["id"]}/connection',
                               headers={'Authorization':'Bearer alice'},json={'digest':step['digest'],'account_id':'account-new'})
            self.assertEqual(result.status_code,200)
        gateway.execute.side_effect=None;gateway.execute.return_value={'verified':True,'receipt':'resumed-read'}
        self.assertEqual(dispatch_once(self.sessions,Mock(),gateway)['status'],'awaiting_approval')
        state=self.state(wid)
        self.assertEqual(state['steps'][0]['result']['receipt'],'first-read')
        self.assertEqual(state['steps'][1]['plan']['account_id'],'account-new')
        self.assertEqual(gateway.execute.call_count,3)  # first read, preflight failure, resumed second read
        gateway.owned_account.assert_called_once_with('a','gmail','account-new')
    def test_reconnect_invalidates_write_grant_and_requires_new_approval(self):
        wid=self.create([fixtures.SEND]);gateway=self.gateway()
        dispatch_once(self.sessions,Mock(),gateway);step=self.state(wid)['steps'][0]
        with self.sessions.begin() as s:workflows.decide(s,'a',Principal('alice'),wid,step['id'],step['digest'],True)
        gateway.execute.side_effect=ConnectionRequired('gmail')
        self.assertEqual(dispatch_once(self.sessions,Mock(),gateway)['status'],'awaiting_connection')
        step=self.state(wid)['steps'][0];self.resume(wid,step,gateway)
        with self.sessions() as s:
            stored=s.get(WorkflowStep,step['id']);self.assertIsNone(stored.approved_by);self.assertIsNone(stored.approval_until)
        gateway.execute.reset_mock();gateway.execute.side_effect=None;gateway.execute.return_value={'verified':True}
        self.assertEqual(dispatch_once(self.sessions,Mock(),gateway)['status'],'awaiting_approval');gateway.execute.assert_not_called()
        fresh=self.state(wid)['steps'][0];self.assertNotEqual(fresh['digest'],step['digest'])
        with self.sessions.begin() as s:workflows.decide(s,'a',Principal('alice'),wid,fresh['id'],fresh['digest'],True)
        self.assertEqual(dispatch_once(self.sessions,Mock(),gateway)['status'],'completed');gateway.execute.assert_called_once()
    def test_uncertain_provider_failure_cannot_use_connection_resume(self):
        wid=self.create([fixtures.READ]);gateway=self.gateway();gateway.execute.side_effect=TimeoutError('secret')
        self.assertEqual(dispatch_once(self.sessions,Mock(),gateway)['status'],'needs_review')
        with self.assertRaises(HTTPException):self.resume(wid,self.state(wid)['steps'][0],gateway)
        gateway.owned_account.assert_not_called()
    def test_wrong_tenant_viewer_and_stale_digest_never_lookup_accounts(self):
        wid,step,gateway=self.park()
        for org,user in [('b','bob'),('a','reader')]:
            with self.assertRaises(HTTPException):self.resume(wid,step,gateway,org=org,user=user)
        with self.assertRaises(HTTPException):self.resume(wid,{**step,'digest':'0'*64},gateway)
        gateway.owned_account.assert_not_called()
    def test_inactive_or_foreign_account_does_not_unpark_job(self):
        wid,step,gateway=self.park();gateway.owned_account.return_value.status='REVOKED'
        with self.assertRaises(HTTPException):self.resume(wid,step,gateway)
        gateway.owned_account.side_effect=ConnectionRequired('gmail')
        with self.assertRaises(ConnectionRequired):self.resume(wid,step,gateway)
        with self.sessions() as s:self.assertEqual(s.get(Job,wid).status,'awaiting_connection')
    def test_paused_org_cannot_resume(self):
        wid,step,gateway=self.park()
        with self.sessions.begin() as s:set_paused(s,'a',Principal('alice'),True)
        with self.assertRaises(HTTPException):self.resume(wid,step,gateway)
        gateway.owned_account.assert_not_called()
    def test_cancel_connection_pause_prevents_claim_or_resume(self):
        wid,step,gateway=self.park()
        with self.sessions.begin() as s:workflows.cancel(s,'a',Principal('alice'),wid)
        self.assertIsNone(dispatch_once(self.sessions,Mock(),gateway))
        with self.assertRaises(HTTPException):self.resume(wid,step,gateway)
        with self.sessions() as s:self.assertEqual(s.get(Job,wid).status,'cancelled')
    def test_resume_replay_cannot_rebind_or_repeat_completed_work(self):
        wid,step,gateway=self.park();self.resume(wid,step,gateway)
        with self.assertRaises(HTTPException):self.resume(wid,step,gateway,account='different')
        self.assertEqual(gateway.owned_account.call_count,1)
        gateway.execute.side_effect=None;gateway.execute.return_value={'verified':True}
        self.assertEqual(dispatch_once(self.sessions,Mock(),gateway)['status'],'completed')
        self.assertIsNone(dispatch_once(self.sessions,Mock(),gateway))
    def test_exception_inbox_includes_persisted_connection_pause(self):
        wid,_,_=self.park()
        with self.sessions() as s:
            items=workflows.exceptions(s,'a',Principal('alice'))['workflows']
            self.assertEqual(items[0]['id'],wid);self.assertEqual(items[0]['status'],'awaiting_connection')
    def test_real_gateway_ambiguous_accounts_park_then_execute_only_selected_account(self):
        client=Mock()
        accounts=[Obj(id=name,user_id='organization:a',status='ACTIVE',auth_config=Obj(id='auth')) for name in ('account-a','account-b')]
        client.connected_accounts.list.return_value=Obj(items=accounts)
        client.connected_accounts.get.return_value=accounts[1]
        client.tools.execute.return_value={'successful':True,'data':{'values':[['report']]}}
        config={'googlesheets':{'auth_config_id':'auth','tools':{'sheets.read':{
            'slug':'SHEETS_READ','version':'20261101_00','argument_map':{'spreadsheet_id':'spreadsheetId','range':'range'}}}}}
        gateway=Gateway(client,config)
        wid=self.create([{'action':'sheets.read','arguments':{'spreadsheet_id':'sheet-1','range':'A1:B5'}}])
        self.assertEqual(dispatch_once(self.sessions,Mock(),gateway)['status'],'awaiting_connection')
        client.tools.execute.assert_not_called()
        self.resume(wid,self.state(wid)['steps'][0],gateway,account='account-b')
        self.assertEqual(dispatch_once(self.sessions,Mock(),gateway)['status'],'completed')
        self.assertEqual(client.tools.execute.call_args.kwargs['connected_account_id'],'account-b')
        client.tools.execute.assert_called_once()
    def test_api_provider_error_preserves_pause_and_redacts_exception(self):
        wid,step,gateway=self.park();gateway.owned_account.side_effect=RuntimeError('secret-do-not-show')
        with TestClient(create_app(self.sessions,lambda token:Principal(token),lambda:gateway)) as client:
            result=client.post(f'/v1/organizations/a/workflows/{wid}/steps/{step["id"]}/connection',
                               headers={'Authorization':'Bearer alice'},json={'digest':step['digest'],'account_id':'account-new'})
            self.assertEqual(result.status_code,503);self.assertNotIn('secret-do-not-show',result.text)
        self.assertEqual(self.state(wid)['status'],'awaiting_connection')
        self.assertIsNone(dispatch_once(self.sessions,Mock(),gateway))
