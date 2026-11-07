"""Bounded HTTP concurrency and exclusive ownership of a deployment database."""
import os
from http.server import ThreadingHTTPServer
from threading import BoundedSemaphore

class BoundedHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, *args, max_connections=16, **kwargs):
        self.slots = BoundedSemaphore(max_connections)
        super().__init__(*args, **kwargs)
    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(15)
        return connection, address
    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            try:
                request.sendall(b'HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\nRetry-After: 2\r\n\r\n')
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise
    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


def acquire_database_lock(path):
    handle = open(path+'.lock', 'a')
    try:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0)
            handle.write('0')
            handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise RuntimeError('Another process owns this database; refusing unsafe concurrent execution')
    return handle  # Keep open for the process lifetime.
