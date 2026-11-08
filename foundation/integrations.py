"""Organization-scoped Composio gateway; all mappings are trusted deployment config."""
import json,re
from urllib.parse import urlsplit
from operator_app.native_tools import TOOLS,APPS,check_arguments

class ConnectionRequired(Exception):
    """Pre-dispatch connection/selection block; never wrap uncertain effects."""
class Gateway:
    def __init__(self,client,config):self.client,self.config=client,config
    @classmethod
    def configured(cls):
        import os
        from composio import Composio
        with open(os.environ['INTEGRATION_CONFIG']) as stream:config=json.load(stream)
        return cls(Composio(api_key=os.environ['COMPOSIO_API_KEY']),config)
    def settings(self,app):
        if app not in APPS:raise ValueError('Unsupported app')
        item=self.config.get(app)
        if not item or not item.get('auth_config_id'):raise ValueError('Integration not configured')
        return item
    def identity(self,org):return 'organization:'+org
    def connect(self,org,app):
        cfg=self.settings(app)
        response=self.client.connected_accounts.link(user_id=self.identity(org),auth_config_id=cfg['auth_config_id'])
        if urlsplit(response.redirect_url).scheme!='https':raise ValueError('Invalid authorization URL')
        return {'authorization_url':response.redirect_url,'app':app}
    def accounts(self,org,app):
        cfg=self.settings(app);identity=self.identity(org)
        result=self.client.connected_accounts.list(user_ids=[identity],statuses=['ACTIVE'])
        # Recheck ownership; never trust a filtered list alone. Never return credential state.
        return [a for a in result.items if a.user_id==identity and a.status=='ACTIVE' and a.auth_config.id==cfg['auth_config_id']]
    def status(self,org,app):
        accounts=self.accounts(org,app)
        return {'app':app,'accounts':[{'id':a.id,'status':a.status} for a in accounts],'selection_required':len(accounts)>1}
    def owned_account(self,org,app,account_id):
        cfg=self.settings(app)
        if not isinstance(account_id,str) or not 1<=len(account_id)<=255:raise ValueError('Invalid connected account')
        account=self.client.connected_accounts.get(account_id)
        if account.id!=account_id or account.user_id!=self.identity(org) or account.auth_config.id!=cfg['auth_config_id']:
            raise ConnectionRequired(app)
        return account
    def reconnect(self,org,app,account_id):
        # The hosted flow may produce a different upstream account. Never swap
        # a workflow's selected account or reuse approval from the old grant.
        self.owned_account(org,app,account_id)
        return {**self.connect(org,app),'previous_account_id':account_id,
                'status':'authorization_required','requires_account_selection':True}
    def revoke(self,org,app,account_id):
        account=self.owned_account(org,app,account_id)
        if account.status!='REVOKED':
            self.client.connected_accounts.revoke(account_id)
            account=self.owned_account(org,app,account_id)
        if account.status!='REVOKED':raise RuntimeError('Connection revocation not confirmed')
        # Composio documents upstream token revocation as best effort. A
        # REVOKED connection proves local provider disablement, not remote purge.
        return {'app':app,'account_id':account_id,'status':'REVOKED',
                'connection_disabled':True,'upstream_revocation':'best_effort'}
    def definition(self,action):
        from .gmail_verification import pointer_path
        app,_,fields=TOOLS[action];cfg=self.settings(app)
        definition=cfg.get('tools',{}).get(action)
        if not definition or not re.fullmatch(r'\d{8}_\d{2}',definition.get('version','')):raise ValueError('Reviewed dated tool version required')
        mapping=definition.get('argument_map',{})
        if set(mapping)!=set(fields) or len(set(mapping.values()))!=len(mapping) or any(not isinstance(v,str) or not v for v in mapping.values()):raise ValueError('Complete reviewed argument mapping required')
        if not re.fullmatch(r'[A-Z][A-Z0-9_]+',definition.get('slug','')):raise ValueError('Invalid configured tool slug')
        defaults=definition.get('defaults',{})
        if not isinstance(defaults,dict) or set(defaults)&set(mapping.values()) or any(not isinstance(k,str) or not k for k in defaults):
            raise ValueError('Reviewed defaults cannot override mapped arguments')
        if len(json.dumps(defaults,allow_nan=False).encode())>4000:raise ValueError('Defaults exceed cap')
        pointer_path(definition.get('result_path',''))
        return cfg,definition,mapping
    def execute(self,org,plan,account_id=None,verify=None):
        from operator_app.core import validate
        bound_account=plan.get('account_id')
        if bound_account is not None:
            if not isinstance(bound_account,str) or not bound_account.strip() or len(bound_account)>255:raise ValueError('Invalid bound account')
            if account_id is not None and account_id!=bound_account:raise ValueError('Approved account cannot be substituted')
            account_id=bound_account
        plan={k:v for k,v in plan.items() if k!='account_id'}
        validate(plan)
        action,args=plan['action'],plan['arguments']
        if action not in TOOLS:raise ValueError('Unregistered native tool')
        check_arguments(action,args)
        app,effect,fields=TOOLS[action];cfg,definition,mapping=self.definition(action)
        builtin=False
        if effect=='write' and verify is None:
            from .gmail_verification import CONTRACT
            if action!='gmail.send' or cfg.get('verification_contract')!=CONTRACT:
                raise ValueError('Write requires provider-specific verifier; execution blocked')
            # Validate readback configuration before any send can be dispatched.
            self.definition('gmail.get')
            if 'result_path' not in definition or 'result_path' not in cfg['tools']['gmail.get']:
                raise ValueError('Explicit reviewed send/readback result paths required')
            builtin=True
        if effect=='write' and (not isinstance(account_id,str) or not account_id.strip()):
            raise ValueError('Writes require an explicit connected account; automatic substitution is forbidden')
        from .disclosure import enforce
        enforce(plan,cfg.get('allowed_destinations'))
        accounts=self.accounts(org,app)
        selected=[a for a in accounts if account_id is None or a.id==account_id]
        if not selected:raise ConnectionRequired(app)
        if len(selected)!=1:raise ConnectionRequired(app)
        params={**definition.get('defaults',{}),**{mapping[k]:(json.loads(v) if k=='values_json' else v) for k,v in args.items()}}
        try:
            response=self.client.tools.execute(definition['slug'],user_id=self.identity(org),connected_account_id=selected[0].id,version=definition['version'],arguments=params)
        except ConnectionRequired:
            raise RuntimeError('Connection failure after dispatch requires reconciliation') from None
        if not isinstance(response,dict) or response.get('successful') is not True:raise RuntimeError('Native tool failed')
        from .gmail_verification import project,message_id,verify_sent,SentMessageUnconfirmed
        raw_data=response.get('data')
        if len(json.dumps(raw_data,ensure_ascii=False,allow_nan=False).encode())>64000:raise ValueError('Provider output exceeds cap')
        data=project(raw_data,definition.get('result_path',''));evidence=None
        try:
            if builtin:
                mid=message_id(data)
                try:
                    readback=self.execute(org,{'action':'gmail.get','account_id':selected[0].id,'arguments':{'message_id':mid}})
                    evidence=verify_sent(plan,readback['data'],mid);verified=True
                except Exception:raise SentMessageUnconfirmed(mid) from None
            else:verified=effect=='read' or verify(plan,response)
        except ConnectionRequired:
            raise RuntimeError('Connection failure during verification requires reconciliation') from None
        if verified is not True:raise RuntimeError('Provider postcondition unverified')
        result={'verified':True,'app':app,'action':action,'account_id':selected[0].id,'data':data}
        if evidence:result['evidence']=evidence
        return result
