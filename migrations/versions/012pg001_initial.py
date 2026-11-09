"""Initial collection schema. Keep pg_schema v1 definitions stable for this revision."""
from alembic import op
from japan_housing_liquidity_lab.pg_schema_v1 import metadata
revision='012pg001'
down_revision=None
branch_labels=None
depends_on=None
def upgrade(): metadata.create_all(op.get_bind())
def downgrade(): raise RuntimeError('Destructive downgrade disabled; restore a verified backup instead')
