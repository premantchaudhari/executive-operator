import os
import unittest
from unittest.mock import Mock,patch
from fastapi.testclient import TestClient
from foundation.api import create_app
from foundation.auth import Principal
import test_foundation as fixtures
class PreviewApiTests(unittest.TestCase):
    setUp=fixtures.FoundationTests.setUp
    tearDown=fixtures.FoundationTests.tearDown
    def request(self,who='alice',steps=None):
        return self.client.post('/v1/organizations/a/read-data-preview',headers={'Authorization':'Bearer '+who},json={'instruction':'Preview','steps':steps or [{'action':'gmail.read','account_id':'account-a','arguments':{'query':'is:unread'}}]})
    def test_disabled_by_default(self):
        with patch.dict(os.environ,{'READ_DATA_PREVIEW_ENABLED':'false'}):self.assertEqual(self.request().status_code,503)
    def test_viewer_denied_before_provider(self):self.assertEqual(self.request('reader').status_code,403)
    def test_enabled_preview_returns_read_and_never_dispatches_write(self):
        gateway=Mock();gateway.execute.return_value={'verified':True,'data':{'subject':'fixture'}}
        self.client.close();self.client=TestClient(create_app(self.sessions,lambda token:Principal(token),lambda:gateway))
        steps=[{'action':'gmail.read','account_id':'account-a','arguments':{'query':'is:unread'}},{'action':'gmail.send','arguments':{'recipient_email':'client@example.com','subject':'Review','body':'Private'}}]
        with patch.dict(os.environ,{'READ_DATA_PREVIEW_ENABLED':'true'}):response=self.request(steps=steps)
        self.assertEqual(response.status_code,200);self.assertFalse(response.json()['writes_executed']);self.assertEqual(gateway.execute.call_count,1)
