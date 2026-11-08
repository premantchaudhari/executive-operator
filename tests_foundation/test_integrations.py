import unittest
from types import SimpleNamespace as Obj
from unittest.mock import Mock
from foundation.integrations import Gateway,ConnectionRequired
from operator_app.core import validate,APPROVAL
from operator_app.native_tools import TOOLS,APPS

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client=Mock()
        self.client.connected_accounts.list.return_value=Obj(items=[Obj(id='account-a',user_id='organization:a',status='ACTIVE',auth_config=Obj(id='auth'))])
        self.config={'googlesheets':{'auth_config_id':'auth','tools':{'sheets.read':{'slug':'SHEETS_READ','version':'20261101_00','argument_map':{'spreadsheet_id':'spreadsheetId','range':'range'}}}}}
        self.gateway=Gateway(self.client,self.config)
        self.plan={'action':'sheets.read','arguments':{'spreadsheet_id':'sheet-1','range':'A1:B5'}}
    def test_catalog_covers_seven_apps(self):self.assertEqual(len(APPS),7)
    def test_read_execution_binds_owner_account_and_version(self):
        self.client.tools.execute.return_value={'successful':True,'data':{'values':[['ok']]}}
        result=self.gateway.execute('a',self.plan)
        self.assertTrue(result['verified']);kwargs=self.client.tools.execute.call_args.kwargs
        self.assertEqual(kwargs['user_id'],'organization:a');self.assertEqual(kwargs['connected_account_id'],'account-a');self.assertEqual(kwargs['version'],'20261101_00')
    def test_cross_organization_account_rejected(self):
        with self.assertRaises(ConnectionRequired):self.gateway.execute('b',self.plan)
        self.client.tools.execute.assert_not_called()
    def test_missing_version_blocks(self):
        self.config['googlesheets']['tools']['sheets.read']['version']='latest'
        with self.assertRaises(ValueError):self.gateway.execute('a',self.plan)
        self.client.tools.execute.assert_not_called()
    def test_read_failure_not_success(self):
        self.client.tools.execute.return_value={'successful':False}
        with self.assertRaises(RuntimeError):self.gateway.execute('a',self.plan)
    def test_all_write_actions_require_approval(self):
        for action,(_,effect,_) in TOOLS.items():
            if effect=='write':self.assertIn(action,APPROVAL)
    def test_sheet_rows_validation(self):
        with self.assertRaises(ValueError):validate({'action':'sheets.append','arguments':{'spreadsheet_id':'s','range':'A1','values_json':'{"not":"rows"}'}})
    def test_payment_query_blocked(self):
        with self.assertRaises(ValueError):validate({'action':'quickbooks.query','arguments':{'query':'DELETE FROM Invoice'}})
    def test_ambiguous_account_selection_blocks(self):
        self.client.connected_accounts.list.return_value.items.append(Obj(id='other',user_id='organization:a',status='ACTIVE',auth_config=Obj(id='auth')))
        with self.assertRaises(ValueError):self.gateway.execute('a',self.plan)
        self.client.tools.execute.assert_not_called()

    def test_write_without_explicit_account_never_dispatches(self):
        self.config['googlesheets']['tools']['sheets.append']={'slug':'SHEETS_APPEND','version':'20261101_00','argument_map':{'spreadsheet_id':'spreadsheetId','range':'range','values_json':'values'}}
        plan={'action':'sheets.append','arguments':{'spreadsheet_id':'s','range':'A1','values_json':'[[1]]'}}
        with self.assertRaisesRegex(ValueError,'explicit connected account'):
            self.gateway.execute('a',plan,verify=lambda *args:True)
        self.client.tools.execute.assert_not_called()
    def test_revoked_explicit_account_never_substituted(self):
        with self.assertRaises(ConnectionRequired):self.gateway.execute('a',self.plan,account_id='revoked-account')
        self.client.tools.execute.assert_not_called()

    def test_gateway_rejects_email_header_injection_before_provider(self):
        plan={'action':'gmail.send','arguments':{'recipient_email':'client@example.com\r\nBcc:other@example.com','subject':'Hi','body':'Private'}}
        with self.assertRaises(ValueError):self.gateway.execute('a',plan,account_id='account-a',verify=lambda *args:True)
        self.client.tools.execute.assert_not_called()
    def test_gateway_rejects_unexpected_plan_fields(self):
        with self.assertRaises(ValueError):self.gateway.execute('a',{**self.plan,'organization_id':'b'})
        self.client.tools.execute.assert_not_called()

    def test_bound_account_cannot_be_overridden(self):
        with self.assertRaisesRegex(ValueError,'cannot be substituted'):
            self.gateway.execute('a',{**self.plan,'account_id':'account-a'},account_id='other')
        self.client.tools.execute.assert_not_called()
    def test_bound_account_used_for_provider_dispatch(self):
        self.client.tools.execute.return_value={'successful':True,'data':{}}
        self.gateway.execute('a',{**self.plan,'account_id':'account-a'})
        self.assertEqual(self.client.tools.execute.call_args.kwargs['connected_account_id'],'account-a')
