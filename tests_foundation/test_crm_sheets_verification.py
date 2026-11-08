import copy
import json
import unittest
from types import SimpleNamespace as Obj
from unittest.mock import Mock
from foundation import workflows
from foundation.auth import Principal
from foundation.crm_sheets_verification import CONTRACTS,WriteUnconfirmed,a1
from foundation.dispatcher import dispatch_once
from foundation.integrations import Gateway
from operator_app.core import validate
import test_workflows as fixtures

CONTACT={'action':'hubspot.create_contact','account_id':'account-h',
         'arguments':{'email':'client@example.com','firstname':'Ada','lastname':'Lovelace'}}
ROWS=[['client@example.com','Ada',5],['review','=SAFE()',True]]
APPEND={'action':'sheets.append','account_id':'account-s',
        'arguments':{'spreadsheet_id':'sheet-1','range':'Tracking!A:C','values_json':json.dumps(ROWS)}}

def definition(slug,fields,defaults=None):
    return {'slug':slug,'version':'20261101_00','argument_map':{f:f for f in fields},
            'result_path':'','defaults':defaults or {}}

class NativeFixture:
    def __init__(self):
        self.client=Mock()
        self.client.connected_accounts.list.return_value=Obj(items=[
            Obj(id='account-h',user_id='organization:a',status='ACTIVE',auth_config=Obj(id='auth-h')),
            Obj(id='account-s',user_id='organization:a',status='ACTIVE',auth_config=Obj(id='auth-s'))])
        self.contact={'id':'7','archived':False,'properties':copy.deepcopy(CONTACT['arguments'])}
        self.append={'spreadsheetId':'sheet-1','updates':{'spreadsheetId':'sheet-1','updatedRange':'Tracking!A2:C3','updatedRows':2}}
        self.read={'range':'Tracking!A2:C3','majorDimension':'ROWS','values':copy.deepcopy(ROWS)}
        self.config={
            'hubspot':{'auth_config_id':'auth-h','verification_contract':CONTRACTS[CONTACT['action']][0],
                'allowed_destinations':{'hubspot.create_contact':['client@example.com']},'tools':{
                    'hubspot.create_contact':definition('CONTACT_CREATE',('email','firstname','lastname')),
                    'hubspot.get_contact':definition('CONTACT_GET',('contact_id',))}},
            'googlesheets':{'auth_config_id':'auth-s','verification_contract':CONTRACTS[APPEND['action']][0],
                'allowed_destinations':{'sheets.append':['sheet-1']},'tools':{
                    'sheets.append':definition('SHEETS_APPEND',('spreadsheet_id','range','values_json'),{'value_input_option':'RAW'}),
                    'sheets.read':definition('SHEETS_READ',('spreadsheet_id','range'),{'value_render_option':'UNFORMATTED_VALUE'})}}}
        def execute(slug,**kwargs):
            data={'CONTACT_CREATE':{'id':'7'},'CONTACT_GET':self.contact,'SHEETS_APPEND':self.append,'SHEETS_READ':self.read}[slug]
            return {'successful':True,'data':copy.deepcopy(data)}
        self.client.tools.execute.side_effect=execute
        self.gateway=Gateway(self.client,self.config)

class NativeVerificationTests(unittest.TestCase):
    def setUp(self):self.fx=NativeFixture()
    def test_contact_readback_bound_to_selected_account_and_returned_id(self):
        result=self.fx.gateway.execute('a',CONTACT)
        self.assertTrue(result['evidence']['postcondition_confirmed'])
        self.assertEqual(result['evidence']['contact_id'],'7')
        call=self.fx.client.tools.execute.call_args
        self.assertEqual(call.args[0],'CONTACT_GET');self.assertEqual(call.kwargs['arguments']['contact_id'],'7')
        self.assertTrue(all(c.kwargs['connected_account_id']=='account-h' for c in self.fx.client.tools.execute.call_args_list))
    def test_contact_state_and_property_mismatch_remain_uncertain(self):
        for mutate in (lambda c:c.update(id='8'),lambda c:c.update(archived=True),
                       lambda c:c['properties'].update(email='wrong@example.com'),lambda c:c.pop('archived')):
            with self.subTest(mutate=mutate):
                fx=NativeFixture();mutate(fx.contact)
                with self.assertRaises(WriteUnconfirmed) as error:fx.gateway.execute('a',CONTACT)
                self.assertEqual(error.exception.evidence['contact_id'],'7')
                self.assertFalse(error.exception.evidence['postcondition_confirmed'])
    def test_missing_contact_readback_configuration_blocks_create(self):
        del self.fx.config['hubspot']['tools']['hubspot.get_contact']
        with self.assertRaises(ValueError):self.fx.gateway.execute('a',CONTACT)
        self.fx.client.tools.execute.assert_not_called()
    def test_sheet_append_reads_exact_returned_rows_on_same_account(self):
        result=self.fx.gateway.execute('a',APPEND)
        self.assertTrue(result['evidence']['postcondition_confirmed'])
        call=self.fx.client.tools.execute.call_args
        self.assertEqual(call.kwargs['arguments']['range'],"'Tracking'!A2:C3")
        self.assertEqual(call.kwargs['arguments']['value_render_option'],'UNFORMATTED_VALUE')
        self.assertTrue(all(c.kwargs['connected_account_id']=='account-s' for c in self.fx.client.tools.execute.call_args_list))
        self.assertEqual(self.fx.client.tools.execute.call_args_list[0].kwargs['arguments']['value_input_option'],'RAW')
    def test_formula_text_stays_literal_and_boolean_is_not_a_number(self):
        self.fx.read['values'][1][1]=0
        with self.assertRaises(WriteUnconfirmed):self.fx.gateway.execute('a',APPEND)
        self.fx=NativeFixture();self.fx.read['values'][1][2]=1
        with self.assertRaises(WriteUnconfirmed):self.fx.gateway.execute('a',APPEND)
    def test_raw_and_readback_options_required_before_write(self):
        for tool,key,bad in [('sheets.append','value_input_option','USER_ENTERED'),('sheets.read','value_render_option','FORMATTED_VALUE')]:
            with self.subTest(tool=tool):
                fx=NativeFixture();fx.config['googlesheets']['tools'][tool]['defaults'][key]=bad
                with self.assertRaises(ValueError):fx.gateway.execute('a',APPEND)
                fx.client.tools.execute.assert_not_called()
    def test_foreign_sheet_or_out_of_bounds_receipt_is_not_followed(self):
        for changed in ('Other!A2:C3','Tracking!D2:F3','Tracking!A2:C4'):
            with self.subTest(range=changed):
                fx=NativeFixture();fx.append['updates']['updatedRange']=changed
                with self.assertRaises(WriteUnconfirmed):fx.gateway.execute('a',APPEND)
                fx.client.tools.execute.assert_called_once()  # no read of unapproved resource
        self.fx.append['spreadsheetId']='foreign-sheet'
        with self.assertRaises(WriteUnconfirmed):self.fx.gateway.execute('a',APPEND)
        self.fx.client.tools.execute.assert_called_once()
    def test_readback_range_or_values_mismatch_is_not_success(self):
        self.fx.read['range']='Tracking!A8:C9'
        with self.assertRaises(WriteUnconfirmed):self.fx.gateway.execute('a',APPEND)
        self.fx=NativeFixture();self.fx.read['values'][0][2]=6
        with self.assertRaises(WriteUnconfirmed):self.fx.gateway.execute('a',APPEND)
    def test_omitted_trailing_blank_cells_are_verified_as_blanks(self):
        rows=[['client@example.com','Ada',None],['review','done','']]
        plan={**APPEND,'arguments':{**APPEND['arguments'],'values_json':json.dumps(rows)}}
        self.fx.append['updates']['updatedRange']='Tracking!A2:B3'
        self.fx.read['values']=[r[:2] for r in rows]
        self.assertTrue(self.fx.gateway.execute('a',plan)['verified'])
    def test_unverifiable_rows_and_ambiguous_ranges_block_before_write(self):
        for args in ({'values_json':'[["x"],[]]'}, {'values_json':'[[null,""]]'}, {'range':'A:C'}, {'range':'Tracking!A1'}):
            with self.subTest(args=args):
                plan={**APPEND,'arguments':{**APPEND['arguments'],**args}}
                with self.assertRaises(ValueError):self.fx.gateway.execute('a',plan)
        self.fx.client.tools.execute.assert_not_called()
    def test_nonfinite_sheet_input_rejected(self):
        with self.assertRaises(ValueError):validate({k:v for k,v in {**APPEND,'arguments':{**APPEND['arguments'],'values_json':'[[NaN]]'}}.items() if k!='account_id'})
    def test_precision_losing_integer_blocked_before_append(self):
        plan={**APPEND,'arguments':{**APPEND['arguments'],'values_json':'[[9007199254740993]]'}}
        with self.assertRaises(ValueError):self.fx.gateway.execute('a',plan)
        self.fx.client.tools.execute.assert_not_called()
    def test_quoted_sheet_names_and_single_cell_receipts(self):
        self.assertEqual(a1("'Owner''s report'!A2"),("Owner's report",1,1,2,2))
    def test_single_cell_append_readback(self):
        plan={**APPEND,'arguments':{**APPEND['arguments'],'range':'Tracking!A:A','values_json':'[["one"]]'}}
        self.fx.append['updates'].update(updatedRange='Tracking!A2',updatedRows=1)
        self.fx.read.update(range='Tracking!A2',values=[['one']])
        self.assertTrue(self.fx.gateway.execute('a',plan)['evidence']['postcondition_confirmed'])
    def test_readback_timeout_keeps_receipt_without_automatic_retry(self):
        original=self.fx.client.tools.execute.side_effect
        def execute(slug,**kwargs):
            if slug=='SHEETS_READ':raise TimeoutError('private-provider-detail')
            return original(slug,**kwargs)
        self.fx.client.tools.execute.side_effect=execute
        with self.assertRaises(WriteUnconfirmed) as error:self.fx.gateway.execute('a',APPEND)
        self.assertEqual(error.exception.evidence['updated_range'],'Tracking!A2:C3')
        self.assertNotIn('private-provider-detail',str(error.exception))
        self.assertEqual(self.fx.client.tools.execute.call_count,2)
    def test_revocation_after_contact_create_is_not_preflight_resume(self):
        active=self.fx.client.connected_accounts.list.return_value
        self.fx.client.connected_accounts.list.side_effect=[active,Obj(items=[])]
        with self.assertRaises(WriteUnconfirmed) as error:self.fx.gateway.execute('a',CONTACT)
        self.assertEqual(error.exception.evidence['contact_id'],'7')
        self.fx.client.tools.execute.assert_called_once()
    def test_wrong_account_never_substituted(self):
        from foundation.integrations import ConnectionRequired
        with self.assertRaises(ConnectionRequired):self.fx.gateway.execute('b',CONTACT)
        self.fx.client.tools.execute.assert_not_called()

class NativeWorkflowTests(unittest.TestCase):
    setUp=fixtures.WorkflowTests.setUp
    tearDown=fixtures.WorkflowTests.tearDown
    create=fixtures.WorkflowTests.create
    state=fixtures.WorkflowTests.state
    def approve(self,wid,index):
        step=self.state(wid)['steps'][index]
        with self.sessions.begin() as s:workflows.decide(s,'a',Principal('alice'),wid,step['id'],step['digest'],True)
    def test_contact_then_sheet_each_approved_verified_and_not_replayed(self):
        fx=NativeFixture();wid=self.create([CONTACT,APPEND])
        self.assertEqual(dispatch_once(self.sessions,Mock(),fx.gateway)['status'],'awaiting_approval')
        fx.client.tools.execute.assert_not_called();self.approve(wid,0)
        self.assertEqual(dispatch_once(self.sessions,Mock(),fx.gateway)['status'],'awaiting_approval')
        self.approve(wid,1)
        self.assertEqual(dispatch_once(self.sessions,Mock(),fx.gateway)['status'],'completed')
        self.assertIsNone(dispatch_once(self.sessions,Mock(),fx.gateway))
        self.assertTrue(all(s['result']['evidence']['postcondition_confirmed'] for s in self.state(wid)['steps']))
        self.assertEqual([c.args[0] for c in fx.client.tools.execute.call_args_list],['CONTACT_CREATE','CONTACT_GET','SHEETS_APPEND','SHEETS_READ'])
    def test_partial_completion_keeps_contact_and_uncertain_sheet_receipt(self):
        fx=NativeFixture();fx.read['values'][1][0]='changed';wid=self.create([CONTACT,APPEND])
        dispatch_once(self.sessions,Mock(),fx.gateway);self.approve(wid,0)
        dispatch_once(self.sessions,Mock(),fx.gateway);self.approve(wid,1)
        self.assertEqual(dispatch_once(self.sessions,Mock(),fx.gateway)['status'],'needs_review')
        state=self.state(wid)
        self.assertEqual(state['steps'][0]['status'],'completed')
        self.assertEqual(state['steps'][1]['result']['evidence']['updated_range'],'Tracking!A2:C3')
        self.assertFalse(state['steps'][1]['result']['evidence']['postcondition_confirmed'])
        self.assertIsNone(dispatch_once(self.sessions,Mock(),fx.gateway));self.assertEqual(fx.client.tools.execute.call_count,4)
