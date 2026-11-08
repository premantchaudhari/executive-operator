import unittest
from foundation.disclosure import enforce
class DisclosureTests(unittest.TestCase):
    def setUp(self):self.plan={'action':'gmail.send','arguments':{'recipient_email':'client@example.com','subject':'x','body':'private'}}
    def test_missing_or_wrong_destination_denied(self):
        for policy in (None,{}, {'gmail.send':['other@example.com']},{'gmail.send':['*']}):
            with self.assertRaises(ValueError):enforce(self.plan,policy)
    def test_exact_destination_allowed(self):enforce(self.plan,{'gmail.send':['client@example.com']})
    def test_read_does_not_require_disclosure_grant(self):enforce({'action':'gmail.read','arguments':{'query':'is:unread'}},None)
