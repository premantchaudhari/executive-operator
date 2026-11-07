"""Owner-bound approvals and organization pause state."""
from alembic import op
import sqlalchemy as sa
revision='0005'
down_revision='0004'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('workflow_steps',sa.Column('approved_by',sa.String(255),nullable=True))
    op.create_table('organization_controls',sa.Column('organization_id',sa.String(36),sa.ForeignKey('organizations.id'),primary_key=True),sa.Column('paused',sa.Integer(),nullable=False))
def downgrade():
    op.drop_table('organization_controls')
    op.drop_column('workflow_steps','approved_by')
