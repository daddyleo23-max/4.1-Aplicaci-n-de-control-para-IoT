"""Bounded per-process login limiter; deploy one worker, as control channels require.

Client address is supplied by ASGI. Trust forwarded headers only from the local
reverse proxy. Identifiers are hashed and never written to logs.
"""
from collections import OrderedDict, deque
from hashlib import sha256
from threading import Lock
import math
import time
from fastapi import HTTPException


class LoginLimiter:
    def __init__(self, clock=time.monotonic, max_keys=10000):
        self.clock, self.max_keys = clock, max_keys
        self.buckets = OrderedDict()
        self.lock = Lock()

    def check(self, address, email):
        now = self.clock()
        keys = [('ip:' + address, 30),
                ('account:' + sha256(email.strip().lower().encode()).hexdigest(), 12)]
        with self.lock:
            # All windows have the same lifetime. Old entries are removed first.
            while self.buckets and next(iter(self.buckets.values()))[-1] <= now - 60:
                self.buckets.popitem(last=False)
            retry = 0
            for key, limit in keys:
                queue = self.buckets.get(key, deque())
                while queue and queue[0] <= now - 60:
                    queue.popleft()
                if len(queue) >= limit:
                    retry = max(retry, math.ceil(queue[0] + 60 - now))
            if retry:
                raise HTTPException(429, 'Demasiados intentos. Espera antes de iniciar sesión.',
                                    headers={'Retry-After': str(max(1, retry)), 'Cache-Control': 'no-store'})
            if sum(key not in self.buckets for key, _ in keys) + len(self.buckets) > self.max_keys:
                raise HTTPException(429, 'Espera antes de iniciar sesión.',
                                    headers={'Retry-After': '60', 'Cache-Control': 'no-store'})
            for key, _ in keys:
                queue = self.buckets.setdefault(key, deque())
                queue.append(now)
                self.buckets.move_to_end(key)


login_limiter = LoginLimiter()
