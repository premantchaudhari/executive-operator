import unittest
from types import SimpleNamespace as Obj
from unittest.mock import Mock
from sqlalchemy import select
from fastapi.testclient import TestClient
from foundation.api import create_app
from foundation.auth import Principal
from foundation.models import AuditEvent
from foundation.integrations import Gateway,ConnectionRequired
import test_foundation as fixtures

class ConnectionGatewayTests(unittest.TestCase):
    def setUp(self):
        self.client=Mock()
        self.account=Obj(id='account-a',user_id='organization:a',status='ACTIVE',auth_config=Obj(id='auth'))
        self.client.connected_accounts.get.return_value=self.account
        self.client.connected_accounts.link.return_value=Obj(redirect_url='https://connect.composio.dev/authorize')
        self.gateway=Gateway(self.client,{'gmail':{'auth_config_id':'auth'}})
    def test_reconnect_requires_owned_account_and_new_selection(self):
        result=self.gateway.reconnect('a','gmail','account-a')
        self.assertEqual(result['status'],'authorization_required')
        self.assertTrue(result['requires_account_selection'])
        self.client.connected_accounts.link.assert_called_once_with(user_id='organization:a',auth_config_id='auth')
    def test_foreign_account_cannot_reconnect_or_revoke(self):
        for action in (self.gateway.reconnect,self.gateway.revoke):
            with self.assertRaises(ConnectionRequired):action('b','gmail','account-a')
        self.client.connected_accounts.link.assert_not_called();self.client.connected_accounts.revoke.assert_not_called()
    def test_wrong_auth_config_never_revoked(self):
        self.account.auth_config.id='foreign-auth'
        with self.assertRaises(ConnectionRequired):self.gateway.revoke('a','gmail','account-a')
        self.client.connected_accounts.revoke.assert_not_called()
    def test_revocation_requires_provider_readback(self):
        with self.assertRaisesRegex(RuntimeError,'not confirmed'):self.gateway.revoke('a','gmail','account-a')
        self.client.connected_accounts.revoke.assert_called_once_with('account-a')
    def test_verified_revoke_and_idempotent_second_call(self):
        self.client.connected_accounts.revoke.side_effect=lambda _:setattr(self.account,'status','REVOKED')
        result=self.gateway.revoke('a','gmail','account-a')
        self.assertTrue(result['connection_disabled']);self.assertEqual(result['upstream_revocation'],'best_effort')
        self.gateway.revoke('a','gmail','account-a')
        self.client.connected_accounts.revoke.assert_called_once()
    def test_account_response_never_exposes_credentials(self):
        self.account.status='REVOKED';self.account.state={'secret':'do-not-return'}
        self.assertNotIn('do-not-return',str(self.gateway.revoke('a','gmail','account-a')))

class ConnectionApiTests(unittest.TestCase):
    setUp=fixtures.FoundationTests.setUp
    tearDown=fixtures.FoundationTests.tearDown
    def client_for(self,gateway):
        return TestClient(create_app(self.sessions,lambda token:Principal(token),lambda:gateway))
    def request(self,client,action='revoke',org='a',user='alice'):
        return client.post(f'/v1/organizations/{org}/integrations/gmail/accounts/account-a/{action}',headers={'Authorization':'Bearer '+user})
    def test_owner_only_before_provider_access(self):
        gateway=Mock()
        with self.client_for(gateway) as client:
            self.assertEqual(self.request(client,user='reader').status_code,403)
            self.assertEqual(self.request(client,org='b').status_code,404)
        gateway.revoke.assert_not_called()
    def test_verified_operation_audited_without_account_secrets(self):
        gateway=Mock();gateway.revoke.return_value={'status':'REVOKED','connection_disabled':True}
        with self.client_for(gateway) as client:self.assertEqual(self.request(client).status_code,200)
        with self.sessions() as s:
            event=s.scalar(select(AuditEvent).where(AuditEvent.event=='connection.revoke'))
            self.assertIsNotNone(event);self.assertEqual(len(event.resource_id),36)
    def test_provider_failure_sanitized_and_not_success_audited(self):
        gateway=Mock();gateway.revoke.side_effect=RuntimeError('secret-token')
        with self.client_for(gateway) as client:
            result=self.request(client);self.assertEqual(result.status_code,503)
            self.assertNotIn('secret-token',result.text)
        with self.sessions() as s:self.assertIsNone(s.scalar(select(AuditEvent).where(AuditEvent.event=='connection.revoke')))
    def test_foreign_account_is_not_found(self):
        gateway=Mock();gateway.reconnect.side_effect=ConnectionRequired('gmail')
        with self.client_for(gateway) as client:self.assertEqual(self.request(client,'reconnect').status_code,404)
