import tempfile
import unittest
from unittest.mock import patch
from operator_app.core import Operator, validate
from operator_app.providers import Providers
from operator_app.orchestration import submit_request
from operator_app.runtime import acquire_database_lock

class HardeningTests(unittest.TestCase):
    def test_natural_language_retry_does_not_replan(self):
        op=Operator(':memory:',Providers())
        plan={'action':'gmail.read','arguments':{'query':'is:unread'}}
        with patch('operator_app.orchestration.plan_text',return_value=plan) as planner:
            a=submit_request(op,'owner','1',{'text':'read inbox'})
            b=submit_request(op,'owner','1',{'text':'read inbox'})
            self.assertEqual(a['id'],b['id'])
            self.assertEqual(planner.call_count,1)
            with self.assertRaises(ValueError): submit_request(op,'owner','1',{'text':'send email'})
        op.db.close()
    def test_single_process_database_ownership(self):
        with tempfile.TemporaryDirectory() as folder:
            first=acquire_database_lock(folder+'/db')
            try:
                with self.assertRaises(RuntimeError): acquire_database_lock(folder+'/db')
            finally: first.close()
            second=acquire_database_lock(folder+'/db'); second.close()
    def test_empty_arguments_rejected(self):
        with self.assertRaises(ValueError): validate({'action':'gmail.read','arguments':{'query':'  '}})
    def test_malformed_action_rejected(self):
        with self.assertRaises(ValueError): validate({'action':[],'arguments':{}})
    def test_ambiguous_input_rejected(self):
        op=Operator(':memory:',Providers())
        with self.assertRaises(ValueError): submit_request(op,'owner','x',{'text':'read inbox','plan':{}})
        op.db.close()
