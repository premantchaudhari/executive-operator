import hashlib,secrets
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select
from .models import Organization,Membership,Invitation,AuditEvent,now,identifier
from .service import authorize

def owner(session,org,principal):
    session.execute(select(Organization).where(Organization.id==org).with_for_update()).scalar_one_or_none()
    member=authorize(session,org,principal)
    if member.role!='owner':raise HTTPException(403,'Owner role required')

def invite(session,org,principal,subject,role):
    owner(session,org,principal)
    if role not in ('admin','operator','viewer'):raise HTTPException(400,'Unsupported invitation role')
    if session.get(Membership,(org,subject)):raise HTTPException(409,'Already a member')
    token=secrets.token_urlsafe(32)
    item=Invitation(id=identifier(),organization_id=org,subject=subject,role=role,token_hash=hashlib.sha256(token.encode()).hexdigest(),expires_at=now()+timedelta(hours=24))
    session.add(item);session.add(AuditEvent(organization_id=org,actor=principal.subject,resource_id=item.id,event='invitation.created'))
    return {'id':item.id,'token':token,'expires_in_seconds':86400}

def accept(session,principal,token):
    item=session.scalar(select(Invitation).where(Invitation.token_hash==hashlib.sha256(token.encode()).hexdigest()).with_for_update())
    if item is None or item.subject!=principal.subject:raise HTTPException(404,'Invitation not found')
    expiry=item.expires_at
    if expiry.tzinfo is None:expiry=expiry.replace(tzinfo=now().tzinfo)
    if item.status!='pending' or expiry<=now():raise HTTPException(409,'Invitation expired or consumed')
    # Serialized by invitation lock; membership PK also prevents duplicate enrollment.
    if session.get(Membership,(item.organization_id,principal.subject)):raise HTTPException(409,'Already a member')
    session.add(Membership(organization_id=item.organization_id,subject=principal.subject,role=item.role))
    item.status='accepted'
    session.add(AuditEvent(organization_id=item.organization_id,actor=principal.subject,resource_id=item.id,event='invitation.accepted'))
    return {'organization_id':item.organization_id,'role':item.role}

def role_change(session,org,principal,subject,role):
    owner(session,org,principal)
    if role not in ('admin','operator','viewer'):raise HTTPException(400,'Unsupported role')
    target=session.get(Membership,(org,subject))
    if target is None:raise HTTPException(404,'Member not found')
    if target.role=='owner':raise HTTPException(409,'Owner transfer requires a separate verified workflow')
    target.role=role
    session.add(AuditEvent(organization_id=org,actor=principal.subject,resource_id=org,event='membership.role_changed'))
    return {'subject':subject,'role':role}
