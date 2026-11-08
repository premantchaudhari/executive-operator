"""Organization-scoped Composio gateway; all mappings are trusted deployment config."""
import json,re
from urllib.parse import urlsplit
from operator_app.native_tools import TOOLS,APPS,check_arguments

class ConnectionRequired(Exception):pass
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
        app,effect,fields=TOOLS[action];cfg=self.settings(app)
        definition=cfg.get('tools',{}).get(action)
        if not definition or not re.fullmatch(r'\d{8}_\d{2}',definition.get('version','')):raise ValueError('Reviewed dated tool version required')
        mapping=definition.get('argument_map',{})
        if set(mapping)!=set(fields) or len(set(mapping.values()))!=len(mapping) or any(not isinstance(v,str) or not v for v in mapping.values()):raise ValueError('Complete reviewed argument mapping required')
        if not re.fullmatch(r'[A-Z][A-Z0-9_]+',definition.get('slug','')):raise ValueError('Invalid configured tool slug')
        if effect=='write' and verify is None:raise ValueError('Write requires provider-specific verifier; execution blocked')
        if effect=='write' and (not isinstance(account_id,str) or not account_id.strip()):
            raise ValueError('Writes require an explicit connected account; automatic substitution is forbidden')
        from .disclosure import enforce
        enforce(plan,cfg.get('allowed_destinations'))
        accounts=self.accounts(org,app)
        selected=[a for a in accounts if account_id is None or a.id==account_id]
        if not selected:raise ConnectionRequired(app)
        if len(selected)!=1:raise ValueError('Explicit account selection required')
        params={mapping[k]:(json.loads(v) if k=='values_json' else v) for k,v in args.items()}
        response=self.client.tools.execute(definition['slug'],user_id=self.identity(org),connected_account_id=selected[0].id,version=definition['version'],arguments=params)
        if not isinstance(response,dict) or response.get('successful') is not True:raise RuntimeError('Native tool failed')
        data=response.get('data')
        encoded=json.dumps(data)
        if len(encoded)>64000:raise ValueError('Provider output exceeds cap')
        verified=effect=='read' or verify(plan,response)
        if verified is not True:raise RuntimeError('Provider postcondition unverified')
        return {'verified':True,'app':app,'action':action,'account_id':selected[0].id,'data':data}
