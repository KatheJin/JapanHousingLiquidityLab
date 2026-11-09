from alembic import context
from japan_housing_liquidity_lab.pg_store import engine
from japan_housing_liquidity_lab.pg_schema import metadata
engine_instance=engine()
try:
    with engine_instance.connect() as connection:
        context.configure(connection=connection,target_metadata=metadata)
        with context.begin_transaction(): context.run_migrations()
finally: engine_instance.dispose()
