import unittest
import test_foundation as fixtures
from foundation import conversations
from foundation.auth import Principal
from foundation.models import Conversation,Workflow
from fastapi import HTTPException

class ConversationTests(unittest.TestCase):
    setUp=fixtures.FoundationTests.setUp
    tearDown=fixtures.FoundationTests.tearDown
    def start(self):
        with self.sessions.begin() as s:return conversations.start(s,'a',Principal('alice')).id
    def message(self,cid,key='one',text='Send a reply'):
        with self.sessions.begin() as s:return conversations.message(s,'a',Principal('alice'),cid,key,text).id
    def state(self,cid):
        with self.sessions() as s:return conversations.history(s,s.get(Conversation,cid))
    def test_clarification_then_plan_preserves_context(self):
        cid=self.start();tid=self.message(cid)
        conversations.plan_turn(self.sessions,tid,lambda history:{'question':'Who should receive it, and what should it say?'})
        self.assertEqual(self.state(cid)['status'],'clarification')
        second=self.message(cid,'two','Send client@example.com the exact text: Meeting confirmed.')
        received=[]
        def planner(history):
            received.append(history)
            return {'steps':[{'action':'gmail.send','arguments':{'recipient_email':'client@example.com','subject':'Meeting','body':'Meeting confirmed.'}}]}
        conversations.plan_turn(self.sessions,second,planner)
        result=self.state(cid);self.assertEqual(len(result['turns']),2);self.assertEqual(result['status'],'planned')
        self.assertIn('question',received[0]['turns'][0]['response'])
        with self.sessions() as s:self.assertIsNotNone(s.get(Workflow,result['turns'][1]['response']['workflow_id']))
    def test_duplicate_turn_not_replanned(self):
        cid=self.start();tid=self.message(cid);calls=[]
        def planner(h):calls.append(1);return {'question':'Which recipient?'}
        conversations.plan_turn(self.sessions,tid,planner);self.assertEqual(self.message(cid),tid)
        conversations.plan_turn(self.sessions,tid,planner);self.assertEqual(calls,[1])
    def test_unsupported_plan_fails_without_workflow(self):
        cid=self.start();tid=self.message(cid)
        conversations.plan_turn(self.sessions,tid,lambda h:{'steps':[{'action':'payment.send','arguments':{}}]})
        self.assertEqual(self.state(cid)['status'],'needs_review')
    def test_cross_tenant_history(self):
        cid=self.start()
        with self.sessions.begin() as s:
            with self.assertRaises(HTTPException):conversations.scoped(s,'b',Principal('bob'),cid)
    def test_pending_turn_blocks_second_message(self):
        cid=self.start();self.message(cid)
        with self.assertRaises(HTTPException):self.message(cid,'two','another')
