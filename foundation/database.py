import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def database(url=None):
    url=url or os.environ['DATABASE_URL']
    if not url.startswith('postgresql+psycopg://'):
        raise ValueError('Production foundation requires postgresql+psycopg DATABASE_URL')
    engine=create_engine(url,pool_pre_ping=True,pool_size=5,max_overflow=5,hide_parameters=True)
    return engine,sessionmaker(engine,expire_on_commit=False)
