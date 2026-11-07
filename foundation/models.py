import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def identifier(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc)
class Base(DeclarativeBase): pass
class Organization(Base):
    __tablename__='organizations'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier)
    name: Mapped[str]=mapped_column(String(160))
class Membership(Base):
    __tablename__='memberships'
    organization_id: Mapped[str]=mapped_column(ForeignKey('organizations.id'),primary_key=True)
    subject: Mapped[str]=mapped_column(String(255),primary_key=True)
    role: Mapped[str]=mapped_column(String(20))
class Job(Base):
    __tablename__='jobs'
    __table_args__=(UniqueConstraint('organization_id','request_key'),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier)
    organization_id: Mapped[str]=mapped_column(ForeignKey('organizations.id'),index=True)
    submitted_by: Mapped[str]=mapped_column(String(255))
    request_key: Mapped[str]=mapped_column(String(128))
    payload: Mapped[str]=mapped_column(Text)
    status: Mapped[str]=mapped_column(String(24),default='queued',index=True)
    attempts: Mapped[int]=mapped_column(Integer,default=0)
    lease_token: Mapped[str|None]=mapped_column(String(36),nullable=True)
    lease_until: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class AuditEvent(Base):
    __tablename__='audit_events'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier)
    organization_id: Mapped[str]=mapped_column(ForeignKey('organizations.id'),index=True)
    actor: Mapped[str]=mapped_column(String(255))
    resource_id: Mapped[str]=mapped_column(String(36))
    event: Mapped[str]=mapped_column(String(64))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Artifact(Base):
    __tablename__='artifacts'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier)
    organization_id: Mapped[str]=mapped_column(ForeignKey('organizations.id'),index=True)
    object_key: Mapped[str]=mapped_column(String(512),unique=True)
    filename: Mapped[str]=mapped_column(String(255))
    # No public storage URLs. Authorized storage delivery is added in Phase 6.
class Invitation(Base):
    __tablename__='invitations'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier)
    organization_id: Mapped[str]=mapped_column(ForeignKey('organizations.id'),index=True)
    subject: Mapped[str]=mapped_column(String(255))
    role: Mapped[str]=mapped_column(String(20))
    token_hash: Mapped[str]=mapped_column(String(64),unique=True)
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    status: Mapped[str]=mapped_column(String(20),default='pending')
class Budget(Base):
    __tablename__='budgets'
    organization_id: Mapped[str]=mapped_column(ForeignKey('organizations.id'),primary_key=True)
    limit_microusd: Mapped[int]=mapped_column(Integer)
    reserved_microusd: Mapped[int]=mapped_column(Integer,default=0)
    spent_microusd: Mapped[int]=mapped_column(Integer,default=0)
class Reservation(Base):
    __tablename__='reservations'
    job_id: Mapped[str]=mapped_column(ForeignKey('jobs.id'),primary_key=True)
    amount_microusd: Mapped[int]=mapped_column(Integer)
    status: Mapped[str]=mapped_column(String(20),default='reserved')
class Workflow(Base):
    __tablename__='workflows'
    id: Mapped[str]=mapped_column(ForeignKey('jobs.id'),primary_key=True)
    organization_id: Mapped[str]=mapped_column(ForeignKey('organizations.id'),index=True)
    status: Mapped[str]=mapped_column(String(24),default='queued')
class WorkflowStep(Base):
    __tablename__='workflow_steps'
    __table_args__=(UniqueConstraint('workflow_id','position'),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier)
    workflow_id: Mapped[str]=mapped_column(ForeignKey('workflows.id'),index=True)
    position: Mapped[int]=mapped_column(Integer)
    plan: Mapped[str]=mapped_column(Text)
    digest: Mapped[str]=mapped_column(String(64))
    status: Mapped[str]=mapped_column(String(24),default='pending')
    result: Mapped[str|None]=mapped_column(Text,nullable=True)
    approved_by: Mapped[str|None]=mapped_column(String(255),nullable=True)
    approval_until: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
class Conversation(Base):
    __tablename__='conversations'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier)
    organization_id: Mapped[str]=mapped_column(ForeignKey('organizations.id'),index=True)
    status: Mapped[str]=mapped_column(String(24),default='open')
class ConversationTurn(Base):
    __tablename__='conversation_turns'
    __table_args__=(UniqueConstraint('conversation_id','request_key'),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=identifier)
    conversation_id: Mapped[str]=mapped_column(ForeignKey('conversations.id'),index=True)
    job_id: Mapped[str]=mapped_column(ForeignKey('jobs.id'),unique=True)
    request_key: Mapped[str]=mapped_column(String(128))
    author: Mapped[str]=mapped_column(String(255))
    message: Mapped[str]=mapped_column(Text)
    response: Mapped[str|None]=mapped_column(Text,nullable=True)
    status: Mapped[str]=mapped_column(String(24),default='queued')
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class OrganizationControl(Base):
    __tablename__='organization_controls'
    organization_id: Mapped[str]=mapped_column(ForeignKey('organizations.id'),primary_key=True)
    paused: Mapped[int]=mapped_column(Integer,default=0)
