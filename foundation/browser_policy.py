"""Browser proposal fingerprints. This module grants no execution authority."""
import hashlib
import json
from urllib.parse import urlsplit


def proposal_digest(*, organization_id, session_id, url, action, state, screenshot):
    """Bind reviewed evidence to one exact browser action; reject unsafe URLs."""
    if any(not isinstance(v,str) or not v or len(v)>2048 for v in (organization_id,session_id,url)):
        raise ValueError('Bound organization, session and URL required')
    parsed=urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('HTTPS URL without credentials required')
    if not isinstance(action,dict) or set(action)!={'kind','target','value'}:
        raise ValueError('Exact typed action required')
    if action['kind'] not in ('click','fill') or any(not isinstance(action[k],str) for k in ('target','value')) or not action['target']:
        raise ValueError('Unsupported browser action')
    if not isinstance(state,str) or not state or len(state)>1000000:
        raise ValueError('Bounded page state required')
    if not isinstance(screenshot,bytes) or not screenshot or len(screenshot)>10000000:
        raise ValueError('Bounded screenshot bytes required')
    payload={'organization':organization_id,'session':session_id,'url':url,'action':action,
             'state':hashlib.sha256(state.encode()).hexdigest(),
             'screenshot':hashlib.sha256(screenshot).hexdigest()}
    encoded=json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False)
    if len(encoded)>30000:raise ValueError('Proposal exceeds limit')
    return hashlib.sha256(encoded.encode()).hexdigest()
