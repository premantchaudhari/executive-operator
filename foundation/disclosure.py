"""Trusted destination allowlists; model output cannot grant disclosure permission."""
from operator_app.native_tools import TOOLS

DESTINATIONS={'gmail.send':'recipient_email','slack.send':'channel_id','sheets.append':'spreadsheet_id','calendar.create':'calendar_id','calendar.cancel':'event_id','hubspot.create_contact':'email'}

def enforce(plan,policy):
    action=plan['action']
    if TOOLS[action][1]!='write':return
    field=DESTINATIONS.get(action)
    if field is None:raise ValueError('Write has no reviewed destination policy')
    allowed=policy.get(action) if isinstance(policy,dict) else None
    if not isinstance(allowed,list) or any(not isinstance(v,str) or not v for v in allowed):
        raise ValueError('Explicit destination allowlist required')
    if plan['arguments'][field] not in allowed:
        raise ValueError('Destination is not authorized by deployment policy')
