import threading
import time
from collections import defaultdict, deque


class ChatRateLimiter:
    def __init__(
        self,
        max_requests: int,
        window_seconds: int,
        clock=time.monotonic,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clock = clock
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def retry_after(self, client_ip: str) -> int | None:
        now = self.clock()
        cutoff = now - self.window_seconds
        with self.lock:
            for ip, timestamps in list(self.requests.items()):
                while timestamps and timestamps[0] <= cutoff:
                    timestamps.popleft()
                if not timestamps:
                    del self.requests[ip]

            timestamps = self.requests[client_ip]
            if len(timestamps) >= self.max_requests:
                return max(1, int(self.window_seconds - (now - timestamps[0]) + 0.999))

            timestamps.append(now)
            return None
