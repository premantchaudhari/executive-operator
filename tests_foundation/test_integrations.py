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
