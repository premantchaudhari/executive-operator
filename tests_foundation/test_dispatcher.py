import unittest
from unittest.mock import Mock,MagicMock,patch
from threading import Event
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
