from alembic import context
from foundation.database import database
from foundation.models import Base
engine,_=database()
with engine.connect() as connection:
    context.configure(connection=connection,target_metadata=Base.metadata)
    with context.begin_transaction():context.run_migrations()
engine.dispose()
