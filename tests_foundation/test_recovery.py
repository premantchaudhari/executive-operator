import unittest
from datetime import timedelta
import test_foundation as fixtures
from foundation import conversations
from foundation.auth import Principal
from foundation.models import Job,ConversationTurn,Conversation,now
from foundation.service import claim,recover
class RecoveryTests(unittest.TestCase):
    setUp=fixtures.FoundationTests.setUp
    tearDown=fixtures.FoundationTests.tearDown
    def test_abandoned_planner_becomes_visible_review_without_retry(self):
        with self.sessions.begin() as s:
            cid=conversations.start(s,'a',Principal('alice')).id
            tid=conversations.message(s,'a',Principal('alice'),cid,'one','Read inbox').id
        with self.sessions.begin() as s:
            job=claim(s);job.lease_until=now()-timedelta(seconds=1)
            s.get(ConversationTurn,tid).status='planning'
        with self.sessions.begin() as s:self.assertEqual(recover(s),1)
        with self.sessions.begin() as s:
            self.assertEqual(s.get(ConversationTurn,tid).status,'needs_review')
            self.assertEqual(s.get(Conversation,cid).status,'needs_review')
            self.assertIsNone(claim(s));self.assertEqual(recover(s),0)
