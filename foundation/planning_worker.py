"""Explicit one-turn planner dispatcher; run under a supervised worker job."""
import argparse
from .database import database
from .conversations import plan_turn
from .planner import generate

def main():
    p=argparse.ArgumentParser();p.add_argument('--turn-id',required=True);args=p.parse_args()
    engine,sessions=database()
    try:plan_turn(sessions,args.turn_id,generate)
    finally:engine.dispose()
if __name__=='__main__':main()
