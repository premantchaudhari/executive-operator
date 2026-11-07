"""Server-side policy independent of model instructions."""
from fastapi import HTTPException
from .models import OrganizationControl,Membership,AuditEvent
from .service import authorize

def require_owner(session,org,principal):
    member=authorize(session,org,principal)
    if member.role!='owner':raise HTTPException(403,'Owner approval required')

def set_paused(session,org,principal,paused):
    require_owner(session,org,principal)
    item=session.get(OrganizationControl,org)
    if item is None:item=OrganizationControl(organization_id=org);session.add(item)
    item.paused=int(paused)
    session.add(AuditEvent(organization_id=org,actor=principal.subject,resource_id=org,event='organization.paused' if paused else 'organization.resumed'))
    return {'paused':paused}

def permitted(session,org,submitter,approver=None):
    control=session.get(OrganizationControl,org)
    if control and control.paused:return False
    member=session.get(Membership,(org,submitter))
    if member is None or member.role not in ('owner','admin','operator'):return False
    if approver:
        owner=session.get(Membership,(org,approver))
        if owner is None or owner.role!='owner':return False
    return True
