import base64
import copy
import unittest
from types import SimpleNamespace as Obj
from unittest.mock import Mock
from foundation import workflows
from foundation.auth import Principal
from foundation.dispatcher import dispatch_once
from foundation.gmail_verification import CONTRACT,SentMessageUnconfirmed,verify_sent
from foundation.integrations import Gateway
import test_workflows as fixtures

def sent_message():
    args=fixtures.SEND['arguments']
    return {'id':'msg-1','labelIds':['SENT'],'payload':{
        'mimeType':'text/plain','headers':[{'name':'To','value':args['recipient_email']},
                                         {'name':'Subject','value':args['subject']}],
        'body':{'data':base64.urlsafe_b64encode(args['body'].encode()).decode()}}}

class GmailVerificationTests(unittest.TestCase):
    def setUp(self):
        self.client=Mock()
        self.client.connected_accounts.list.return_value=Obj(items=[Obj(id='account-a',user_id='organization:a',status='ACTIVE',auth_config=Obj(id='auth'))])
        self.message=sent_message()
        self.config={'gmail':{'auth_config_id':'auth','verification_contract':CONTRACT,
            'allowed_destinations':{'gmail.send':['client@example.com']},'tools':{
            'gmail.send':{'slug':'GMAIL_SEND','version':'20261101_00','result_path':'/response',
                'argument_map':{'recipient_email':'to','subject':'subject','body':'body'}},
            'gmail.get':{'slug':'GMAIL_GET','version':'20261101_00','result_path':'/message',
                'argument_map':{'message_id':'id'},'defaults':{'user_id':'me','format':'full'}}}}}
        def execute(slug,**kwargs):
            if slug=='GMAIL_SEND':return {'successful':True,'data':{'response':{'id':'msg-1'}}}
            return {'successful':True,'data':{'message':copy.deepcopy(self.message)}}
        self.client.tools.execute.side_effect=execute
        self.gateway=Gateway(self.client,self.config)
    def test_same_account_readback_and_evidence(self):
        result=self.gateway.execute('a',fixtures.SEND)
        self.assertTrue(result['evidence']['sent_copy_confirmed'])
        self.assertFalse(result['evidence']['delivery_confirmed'])
        self.assertEqual(result['evidence']['message_id'],'msg-1')
        calls=self.client.tools.execute.call_args_list
        self.assertEqual([c.args[0] for c in calls],['GMAIL_SEND','GMAIL_GET'])
        self.assertTrue(all(c.kwargs['connected_account_id']=='account-a' for c in calls))
        self.assertEqual(calls[1].kwargs['arguments'],{'user_id':'me','format':'full','id':'msg-1'})
    def test_missing_readback_configuration_blocks_before_send(self):
        del self.config['gmail']['tools']['gmail.get']
        with self.assertRaises(ValueError):self.gateway.execute('a',fixtures.SEND)
        self.client.tools.execute.assert_not_called()
    def test_opt_in_and_explicit_result_contract_required(self):
        self.config['gmail']['verification_contract']=''
        with self.assertRaises(ValueError):self.gateway.execute('a',fixtures.SEND)
        self.client.tools.execute.assert_not_called()
        self.config['gmail']['verification_contract']=CONTRACT
        del self.config['gmail']['tools']['gmail.get']['result_path']
        with self.assertRaises(ValueError):self.gateway.execute('a',fixtures.SEND)
        self.client.tools.execute.assert_not_called()
    def test_defaults_cannot_override_approved_arguments(self):
        self.config['gmail']['tools']['gmail.send']['defaults']={'to':'other@example.com'}
        with self.assertRaises(ValueError):self.gateway.execute('a',fixtures.SEND)
        self.client.tools.execute.assert_not_called()
    def test_unapproved_destination_never_sent(self):
        self.config['gmail']['allowed_destinations']['gmail.send']=[]
        with self.assertRaises(ValueError):self.gateway.execute('a',fixtures.SEND)
        self.client.tools.execute.assert_not_called()
    def test_subject_header_injection_never_sent(self):
        plan={**fixtures.SEND,'arguments':{**fixtures.SEND['arguments'],'subject':'Hello\r\nBcc:other@example.com'}}
        with self.assertRaises(ValueError):self.gateway.execute('a',plan)
        self.client.tools.execute.assert_not_called()
    def test_unsupported_or_changed_readback_fails_with_receipt(self):
        mutations=[lambda m:m.update(id='different'),lambda m:m.update(labelIds=['DRAFT']),
            lambda m:m['payload'].update(mimeType='text/html'),
            lambda m:m['payload']['headers'].append({'name':'Bcc','value':'other@example.com'}),
            lambda m:m['payload']['headers'][0].update(value='other@example.com'),
            lambda m:m['payload']['headers'][1].update(value='Changed'),
            lambda m:m['payload']['body'].update(data='Y2hhbmdlZA=='),
            lambda m:m['payload']['body'].update(attachmentId='attachment'),
            lambda m:m['payload']['headers'].append({'name':'To','value':'client@example.com'})]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.message=sent_message();mutate(self.message)
                with self.assertRaises(SentMessageUnconfirmed) as error:self.gateway.execute('a',fixtures.SEND)
                self.assertEqual(error.exception.message_id,'msg-1')
    def test_message_get_is_available_as_read_tool(self):
        result=self.gateway.execute('a',{'account_id':'account-a','action':'gmail.get','arguments':{'message_id':'msg-1'}})
        self.assertEqual(result['data']['id'],'msg-1')
    def test_invalid_message_resource_id_never_dispatched(self):
        with self.assertRaises(ValueError):self.gateway.execute('a',{'account_id':'account-a','action':'gmail.get','arguments':{'message_id':'../foreign'}})
        self.client.tools.execute.assert_not_called()
    def test_conflicting_mime_header_is_not_verified(self):
        self.message['payload']['headers'].append({'name':'Content-Type','value':'text/html; charset=utf-8'})
        with self.assertRaises(SentMessageUnconfirmed):self.gateway.execute('a',fixtures.SEND)
    def test_revocation_after_send_keeps_receipt_and_is_not_connection_pause(self):
        active=self.client.connected_accounts.list.return_value
        self.client.connected_accounts.list.side_effect=[active,Obj(items=[])]
        with self.assertRaises(SentMessageUnconfirmed) as error:self.gateway.execute('a',fixtures.SEND)
        self.assertEqual(error.exception.message_id,'msg-1')
        self.client.tools.execute.assert_called_once()
    def test_mime_terminal_newline_is_explicitly_normalized(self):
        self.message['payload']['body']['data']=base64.urlsafe_b64encode((fixtures.SEND['arguments']['body']+'\r\n').encode()).decode()
        self.assertTrue(self.gateway.execute('a',fixtures.SEND)['evidence']['sent_copy_confirmed'])

class GmailWorkflowTests(unittest.TestCase):
    setUp=fixtures.WorkflowTests.setUp
    tearDown=fixtures.WorkflowTests.tearDown
    create=fixtures.WorkflowTests.create
    state=fixtures.WorkflowTests.state
    def gateway(self):
        fixture=GmailVerificationTests();fixture.setUp();return fixture
    def approve(self,wid):
        step=self.state(wid)['steps'][0]
        with self.sessions.begin() as s:workflows.decide(s,'a',Principal('alice'),wid,step['id'],step['digest'],True)
    def test_production_dispatch_pauses_then_records_verified_sent_copy_once(self):
        fixture=self.gateway();wid=self.create([fixtures.SEND])
        self.assertEqual(dispatch_once(self.sessions,Mock(),fixture.gateway)['status'],'awaiting_approval')
        fixture.client.tools.execute.assert_not_called();self.approve(wid)
        self.assertEqual(dispatch_once(self.sessions,Mock(),fixture.gateway)['status'],'completed')
        self.assertIsNone(dispatch_once(self.sessions,Mock(),fixture.gateway))
        result=self.state(wid)['steps'][0]['result']
        self.assertEqual(result['evidence']['message_id'],'msg-1');self.assertFalse(result['evidence']['delivery_confirmed'])
        self.assertEqual(fixture.client.tools.execute.call_count,2)
    def test_post_send_mismatch_enters_review_and_never_resends(self):
        fixture=self.gateway();fixture.message['payload']['headers'][0]['value']='other@example.com'
        wid=self.create([fixtures.SEND]);dispatch_once(self.sessions,Mock(),fixture.gateway);self.approve(wid)
        self.assertEqual(dispatch_once(self.sessions,Mock(),fixture.gateway)['status'],'needs_review')
        self.assertIsNone(dispatch_once(self.sessions,Mock(),fixture.gateway))
        result=self.state(wid)['steps'][0]['result']
        self.assertEqual(result['evidence']['message_id'],'msg-1')
        self.assertFalse(result['evidence']['sent_copy_confirmed'])
        self.assertEqual(fixture.client.tools.execute.call_count,2)
