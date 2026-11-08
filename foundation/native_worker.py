"""Explicit workflow runner through the scoped gateway; writes stay verifier-gated."""
import argparse
from .database import database
from .integrations import Gateway
from .workflows import run


def execute_workflow(sessions,workflow_id,gateway):
    # Gateway rechecks active account ownership, configured tool version and
    # disclosure policy. No generic verifier can authorize a native write.
    def execute(org,plan,step_id):
        return gateway.execute(org,plan)
    return run(sessions,workflow_id,execute)


def main():
    parser=argparse.ArgumentParser(description='Run one persisted native workflow')
    parser.add_argument('--workflow-id',required=True)
    args=parser.parse_args()
    engine,sessions=database()
    try:execute_workflow(sessions,args.workflow_id,Gateway.configured())
    finally:engine.dispose()

if __name__=='__main__':main()
