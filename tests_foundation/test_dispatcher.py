import unittest
from unittest.mock import Mock,MagicMock,patch
from threading import Event
from datetime import timedelta
from foundation.models import Job,WorkflowStep,now
from foundation.service import claim,recover
from foundation import workflows
from foundation.auth import Principal
from foundation.dispatcher import dispatch_once
from foundation.heartbeat import LeaseHeartbeat
import test_workflows as fixtures
class DispatcherTests(unittest.TestCase):
    setUp=fixtures.WorkflowTests.setUp
    tearDown=fixtures.WorkflowTests.tearDown
    create=fixtures.WorkflowTests.create
    state=fixtures.WorkflowTests.state
    def test_approval_pause_wake_and_once_only_dispatch(self):
        wid=self.create([fixtures.SEND]);gateway=Mock();gateway.execute.return_value={'verified':True}
        self.assertEqual(dispatch_once(self.sessions,Mock(),gateway)['status'],'awaiting_approval');gateway.execute.assert_not_called()
        step=self.state(wid)['steps'][0]
        with self.sessions.begin() as s:workflows.decide(s,'a',Principal('alice'),wid,step['id'],step['digest'],True)
        self.assertEqual(dispatch_once(self.sessions,Mock(),gateway)['status'],'completed')
        self.assertIsNone(dispatch_once(self.sessions,Mock(),gateway));gateway.execute.assert_called_once()
    def test_conversation_queue_plans_then_reads(self):
        from foundation import conversations
        with self.sessions.begin() as s:
            cid=conversations.start(s,'a',Principal('alice')).id
            conversations.message(s,'a',Principal('alice'),cid,'one','Read inbox')
        planner=Mock(return_value={'steps':[fixtures.READ]});gateway=Mock();gateway.execute.return_value={'verified':True}
        self.assertEqual(dispatch_once(self.sessions,planner,gateway)['status'],'completed');planner.assert_called_once();gateway.execute.assert_called_once()
    def test_cancel_queued_job_is_never_claimed(self):
        wid=self.create([fixtures.READ,fixtures.SEND])
        with self.sessions.begin() as s:workflows.cancel(s,'a',Principal('alice'),wid)
        gateway=Mock()
        self.assertIsNone(dispatch_once(self.sessions,Mock(),gateway))
        gateway.execute.assert_not_called()
        with self.sessions() as s:self.assertEqual(s.get(Job,wid).status,'cancelled')
        self.assertTrue(all(step['status']=='cancelled' for step in self.state(wid)['steps']))
    def test_edit_paused_action_wakes_job_and_requires_fresh_review(self):
        wid=self.create([fixtures.SEND]);gateway=Mock();gateway.execute.return_value={'verified':True}
        dispatch_once(self.sessions,Mock(),gateway)
        old=self.state(wid)['steps'][0]
        edited={**fixtures.SEND,'arguments':{**fixtures.SEND['arguments'],'body':'Revised exact body'}}
        with self.sessions.begin() as s:workflows.edit_step(s,'a',Principal('alice'),wid,old['id'],old['digest'],edited)
        self.assertEqual(dispatch_once(self.sessions,Mock(),gateway)['status'],'awaiting_approval')
        gateway.execute.assert_not_called()
        fresh=self.state(wid)['steps'][0];self.assertNotEqual(old['digest'],fresh['digest'])
        with self.sessions.begin() as s:workflows.decide(s,'a',Principal('alice'),wid,fresh['id'],fresh['digest'],True)
        self.assertEqual(dispatch_once(self.sessions,Mock(),gateway)['status'],'completed')
        self.assertEqual(gateway.execute.call_args.args[1],edited)
    def test_cancel_in_flight_records_receipt_and_stops_next_step(self):
        wid=self.create([fixtures.READ,fixtures.SEND]);gateway=Mock()
        def execute(*args):
            with self.sessions.begin() as s:workflows.cancel(s,'a',Principal('alice'),wid)
            return {'verified':True,'receipt':'in-flight-read'}
        gateway.execute.side_effect=execute
        self.assertEqual(dispatch_once(self.sessions,Mock(),gateway)['status'],'cancelled')
        state=self.state(wid);self.assertEqual(state['status'],'cancelled')
        self.assertEqual(state['steps'][0]['result']['receipt'],'in-flight-read')
        self.assertEqual(state['steps'][1]['status'],'cancelled');gateway.execute.assert_called_once()
        self.assertIsNone(dispatch_once(self.sessions,Mock(),gateway))
    def test_late_verified_response_cannot_undo_recovery(self):
        wid=self.create([fixtures.READ,fixtures.READ])
        with self.sessions.begin() as s:claim(s)
        calls=[]
        def execute(*args):
            calls.append(args)
            with self.sessions.begin() as s:s.get(Job,wid).lease_until=now()-timedelta(seconds=1)
            with self.sessions.begin() as s:self.assertEqual(recover(s),1)
            return {'verified':True,'receipt':'late-provider-receipt'}
        workflows.run(self.sessions,wid,execute)
        state=self.state(wid);self.assertEqual(state['status'],'needs_review')
        self.assertEqual(state['steps'][0]['status'],'needs_review')
        self.assertEqual(state['steps'][0]['result']['late_result']['receipt'],'late-provider-receipt')
        self.assertEqual(state['steps'][1]['status'],'pending');self.assertEqual(len(calls),1)
        self.assertIsNone(dispatch_once(self.sessions,Mock(),Mock()))
class HeartbeatTests(unittest.TestCase):
    def test_periodic_renewal_and_cleanup(self):
        renewed=Event()
        with patch('foundation.heartbeat.renew',side_effect=lambda *args:renewed.set()):
            with LeaseHeartbeat(MagicMock(),'job','token',0.01) as heartbeat:
                renewed.clear();self.assertTrue(renewed.wait(1))
            self.assertFalse(heartbeat.thread.is_alive())
    def test_renewal_failure_permanently_fences(self):
        with patch('foundation.heartbeat.renew',side_effect=ValueError()) as renew:
            heartbeat=LeaseHeartbeat(MagicMock(),'job','token')
            with self.assertRaises(ValueError):heartbeat.check()
            with self.assertRaises(ValueError):heartbeat.check()
            self.assertEqual(renew.call_count,1)
