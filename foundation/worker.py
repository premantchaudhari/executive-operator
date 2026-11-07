"""Foundation worker. Does not execute provider tools before Phase 2/4 policies."""
import argparse
from .database import database
from .service import claim,finish,recover

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true',required=True)
    parser.parse_args()
    engine,sessions=database()
    try:
        with sessions.begin() as session:recover(session)
        with sessions.begin() as session:
            job=claim(session)
            details=(job.id,job.lease_token) if job else None
        if details:
            # Preserve work for review, never mark an unimplemented workflow successful.
            with sessions.begin() as session:finish(session,*details,'needs_review')
    finally:engine.dispose()
if __name__=='__main__':main()
