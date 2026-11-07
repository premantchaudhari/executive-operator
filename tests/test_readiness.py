import os
import unittest
from unittest.mock import patch
from operator_app.readiness import readiness
from operator_app.providers import Providers

class ReadinessTests(unittest.TestCase):
    def test_missing_credentials_fail_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            r=readiness(False)
            self.assertFalse(r['planner']['configured'])
            self.assertIn('GEMINI_API_KEY',r['planner']['missing_settings'])
    def test_diagnostics_never_return_secret_values(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY':'PRIVATE_SECRET_VALUE'}):
            self.assertNotIn('PRIVATE_SECRET_VALUE',str(readiness(False)))
    def test_demo_does_not_claim_live_connection(self):
        for r in readiness(True).values():
            self.assertEqual(r['mode'],'simulation')
            self.assertFalse(r['connection_verified'])
    def test_demo_mail_has_fictional_preview(self):
        r=Providers(True).execute('owner',{'action':'gmail.read','arguments':{'query':'is:unread'}})
        self.assertTrue(r['demo'])
        self.assertEqual(len(r['preview']['messages']),2)
