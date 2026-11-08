import unittest
from unittest.mock import Mock
from fastapi import HTTPException
from foundation.dry_run import preview
from foundation.auth import Principal
from foundation import policy
import test_workflows as fixtures

class DryRunTests(unittest.TestCase):
    setUp=fixtures.WorkflowTests.setUp
    tearDown=fixtures.WorkflowTests.tearDown
    def test_only_read_dispatched(self):
        gateway=Mock();gateway.execute.return_value={'verified':True,'data':{'subject':'real read fixture'}}
        read={**fixtures.READ,'account_id':'account-a'}
        result=preview(self.sessions,'a',Principal('alice'),[read,fixtures.SEND],gateway)
        gateway.execute.assert_called_once_with('a',read)
        self.assertFalse(result['writes_executed']);self.assertEqual(result['steps'][1]['status'],'write_not_executed')
    def test_viewer_and_wrong_tenant_never_dispatch(self):
        for principal,org in [(Principal('reader'),'a'),(Principal('bob'),'a')]:
            gateway=Mock()
            with self.assertRaises(HTTPException):preview(self.sessions,org,principal,[fixtures.READ],gateway)
            gateway.execute.assert_not_called()
    def test_pause_prevents_provider_access(self):
        with self.sessions.begin() as s:policy.set_paused(s,'a',Principal('alice'),True)
        gateway=Mock()
        with self.assertRaises(HTTPException):preview(self.sessions,'a',Principal('alice'),[fixtures.READ],gateway)
        gateway.execute.assert_not_called()

    def test_missing_later_account_blocks_all_provider_calls(self):
        gateway=Mock()
        with self.assertRaises(HTTPException):preview(self.sessions,'a',Principal('alice'),[{**fixtures.READ,'account_id':'account-a'},fixtures.READ],gateway)
        gateway.execute.assert_not_called()
    def test_combined_preview_output_is_bounded(self):
        gateway=Mock();gateway.execute.return_value={'verified':True,'data':'x'*64000}
        with self.assertRaisesRegex(ValueError,'Combined preview'):
            preview(self.sessions,'a',Principal('alice'),[{**fixtures.READ,'account_id':'account-a'}]*5,gateway)
