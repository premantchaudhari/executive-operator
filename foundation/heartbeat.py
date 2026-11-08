"""Periodic lease renewal. Lease loss fences subsequent external calls."""
from threading import Event, Thread
from .service import renew

class LeaseHeartbeat:
    def __init__(self,sessions,job_id,token,interval=30):
        if not 0.01<=interval<=60:raise ValueError('Invalid heartbeat interval')
        self.sessions,self.job_id,self.token,self.interval=sessions,job_id,token,interval
        self.stop=Event();self.lost=Event();self.thread=None
    def check(self):
        if self.lost.is_set():raise ValueError('Lease heartbeat failed')
        try:
            with self.sessions.begin() as session:renew(session,self.job_id,self.token)
        except Exception:
            self.lost.set();raise
    def loop(self):
        while not self.stop.wait(self.interval):
            try:self.check()
            except Exception:return
    def __enter__(self):
        self.check();self.thread=Thread(target=self.loop,daemon=True);self.thread.start();return self
    def __exit__(self,*exc):
        self.stop.set();self.thread.join(timeout=5)
        if self.thread.is_alive():self.lost.set()
