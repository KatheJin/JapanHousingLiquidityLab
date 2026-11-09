"""Immutable initial migration receipts; preserve proof after collection resumes."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision='012pg002'
down_revision='012pg001'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('migration_receipts',sa.Column('source_sha256',sa.Text,primary_key=True),sa.Column('verified_at',sa.DateTime(timezone=True)),sa.Column('report',JSONB))
def downgrade(): raise RuntimeError('Use a verified backup; receipt removal is intentionally disabled')
