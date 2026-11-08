import unittest
from foundation.browser_policy import proposal_digest

class BrowserPolicyTests(unittest.TestCase):
    def setUp(self):
        self.proposal=dict(organization_id='a',session_id='session-1',url='https://example.com/form',action={'kind':'click','target':'Submit','value':''},state='reviewed page',screenshot=b'image')
    def test_every_reviewed_dimension_changes_digest(self):
        original=proposal_digest(**self.proposal)
        for key,value in dict(organization_id='b',session_id='session-2',url='https://example.com/other',action={'kind':'click','target':'Buy','value':''},state='changed page',screenshot=b'new image').items():
            with self.subTest(key=key):self.assertNotEqual(original,proposal_digest(**{**self.proposal,key:value}))
    def test_key_order_does_not_change_digest(self):
        self.assertEqual(proposal_digest(**self.proposal),proposal_digest(**{**self.proposal,'action':{'value':'','target':'Submit','kind':'click'}}))
    def test_unsafe_or_missing_evidence_rejected(self):
        for key,value in [('url','http://example.com'),('url','https://user:pass@example.com'),('screenshot',b''),('state',''),('action',{'kind':'shell','target':'x','value':''})]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):proposal_digest(**{**self.proposal,key:value})
