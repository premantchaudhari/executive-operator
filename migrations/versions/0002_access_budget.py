"""Frozen invitation and budget schema."""
from alembic import op
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

revision="0002"
down_revision="0001"
branch_labels=None
depends_on=None
def upgrade():
    for table in (Invitation.__table__,Budget.__table__,Reservation.__table__):table.create(op.get_bind())
def downgrade():
    for table in (Reservation.__table__,Budget.__table__,Invitation.__table__):table.drop(op.get_bind())
