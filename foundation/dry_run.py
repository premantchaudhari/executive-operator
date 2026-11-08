"""Owner-only read-data preview. No workflow execution or write dispatch."""
from fastapi import HTTPException
from operator_app.native_tools import TOOLS
from .workflows import canonical,digest
from .policy import require_owner,permitted
from .models import AuditEvent
import json
from uuid import uuid5,NAMESPACE_URL


def preview(sessions,org,principal,plans,gateway):
    if not 1<=len(plans)<=20:raise HTTPException(400,'Preview requires 1–20 steps')
    encoded=[canonical(plan) for plan in plans]
    # Validate the entire request before the first potentially billable read.
    for item in encoded:
        plan=json.loads(item)
        if TOOLS[plan['action']][1]=='read' and not plan.get('account_id'):
            raise HTTPException(409,'Select an explicit read account')
    results=[]
    output_bytes=0
    for item in encoded:
        plan=json.loads(item)
        with sessions.begin() as session:
            require_owner(session,org,principal)
            if not permitted(session,org,principal.subject):raise HTTPException(409,'Organization paused')
            session.add(AuditEvent(organization_id=org,actor=principal.subject,resource_id=str(uuid5(NAMESPACE_URL,'executive-operator:preview:'+org+':'+digest(item))),event='dry_run.reviewed'))
        if TOOLS[plan['action']][1]=='write':
            results.append({'digest':digest(item),'status':'write_not_executed','plan':plan})
            continue
        if not plan.get('account_id'):raise HTTPException(409,'Select an explicit read account')
        result=gateway.execute(org,plan)
        if not isinstance(result,dict) or result.get('verified') is not True:raise ValueError('Read preview unverified')
        output_bytes+=len(json.dumps(result,ensure_ascii=False,allow_nan=False).encode('utf-8'))
        if output_bytes>256000:raise ValueError('Combined preview output exceeds limit')
        results.append({'digest':digest(item),'status':'read_fetched','result':result})
    return {'mode':'read_data_preview','writes_executed':False,'steps':results}
