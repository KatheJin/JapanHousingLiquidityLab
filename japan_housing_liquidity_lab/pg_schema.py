"""Current schema. Initial revision definitions remain frozen in pg_schema_v1."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from .pg_schema_v1 import LAYOUT,KEYS,enriched
from .pg_schema_v1 import metadata as v1_metadata
metadata=sa.MetaData()
for table in v1_metadata.sorted_tables: table.to_metadata(metadata)
TABLES={name:metadata.tables[name] for name in LAYOUT}
sa.Table('migration_receipts',metadata,sa.Column('source_sha256',sa.Text,primary_key=True),sa.Column('verified_at',sa.DateTime(timezone=True)),sa.Column('report',JSONB))
