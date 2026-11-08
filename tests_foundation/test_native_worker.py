import unittest
from unittest.mock import Mock
import test_workflows as fixtures
from foundation.native_worker import execute_workflow
from foundation import workflows
from foundation.auth import Principal

class NativeWorkerTests(unittest.TestCase):
    setUp=fixtures.WorkflowTests.setUp
    tearDown=fixtures.WorkflowTests.tearDown
    create=fixtures.WorkflowTests.create
    state=fixtures.WorkflowTests.state
    def test_scoped_plan_reaches_gateway_once(self):
        wid=self.create([{**fixtures.READ,'account_id':'account-a'}])
        gateway=Mock();gateway.execute.return_value={'verified':True,'data':{}}
        execute_workflow(self.sessions,wid,gateway);execute_workflow(self.sessions,wid,gateway)
        gateway.execute.assert_called_once_with('a',{**fixtures.READ,'account_id':'account-a'})
        self.assertEqual(self.state(wid)['status'],'completed')
    def test_unimplemented_write_verifier_stops_workflow(self):
        wid=self.create([fixtures.SEND]);gateway=Mock();gateway.execute.side_effect=ValueError('Verifier required')
        execute_workflow(self.sessions,wid,gateway);gateway.execute.assert_not_called()
        step=self.state(wid)['steps'][0]
        with self.sessions.begin() as s:workflows.decide(s,'a',Principal('alice'),wid,step['id'],step['digest'],True)
        execute_workflow(self.sessions,wid,gateway);execute_workflow(self.sessions,wid,gateway)
        self.assertEqual(gateway.execute.call_count,1);self.assertEqual(self.state(wid)['status'],'needs_review')
