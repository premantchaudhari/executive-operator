"""Supervisable queue consumer for planning and native workflows."""
import argparse,signal,threading,logging
from .database import database
from .dispatcher import dispatch_once
from .planner import generate
from .integrations import Gateway

class LazyGateway:
    def __init__(self):self.gateway=None
    def execute(self,*args,**kwargs):
        if self.gateway is None:self.gateway=Gateway.configured()
        return self.gateway.execute(*args,**kwargs)

def consume(sessions,planner,gateway,stop,once=False,poll_seconds=2):
    if not 0.1<=poll_seconds<=60:raise ValueError('Invalid poll interval')
    while not stop.is_set():
        result=dispatch_once(sessions,planner,gateway)
        if once:return result
        if result is None:stop.wait(poll_seconds)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');parser.add_argument('--poll-seconds',type=float,default=2)
    args=parser.parse_args()
    if not 0.1<=args.poll_seconds<=60:parser.error('poll-seconds must be 0.1–60')
    stop=threading.Event()
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:stop.set())
    engine,sessions=database()
    try:consume(sessions,generate,LazyGateway(),stop,args.once,args.poll_seconds)
    except Exception:
        logging.error('Worker stopped; inspect persisted job state');raise SystemExit(1) from None
    finally:engine.dispose()
if __name__=='__main__':main()
