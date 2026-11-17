"""HTTP client for the rival service, run on a background thread.

The frame loop never waits on the network: requests go to a small thread pool and the
selector polls the result each frame. The transport is injectable so tests never touch the
network. No credentials live here. The service holds any provider key.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass

DEADLINE_SECONDS = 5.0

Transport = Callable[[str, str, dict | None, float], tuple[int, dict]]


def urllib_transport(method: str, url: str, body: dict | None, timeout: float) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url, data=data, method=method, headers={"content-type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.loads(error.read() or b"{}")
        except ValueError:
            return error.code, {}


@dataclass
class Pending:
    encounter: int
    request_id: str
    supplied_ids: frozenset[str]
    started: float
    future: Future


class TacticClient:
    def __init__(
        self,
        base_url: str,
        transport: Transport = urllib_transport,
        clock: Callable[[], float] = time.monotonic,
        deadline: float = DEADLINE_SECONDS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        self.clock = clock
        self.deadline = deadline
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rival")

    def start_session(self) -> str | None:
        """Blocking, called once before play starts. None means live mode is unavailable."""
        try:
            status, body = self.transport("POST", f"{self.base_url}/sessions", None, self.deadline)
        except (OSError, ValueError):
            return None
        session_id = body.get("session_id") if status == 201 else None
        return session_id if isinstance(session_id, str) else None

    def submit(self, session_id: str, encounter: int, request_id: str, summary: dict) -> Pending:
        body = {"request_id": request_id, "encounter": encounter, "summary": summary}
        url = f"{self.base_url}/sessions/{session_id}/tactic"
        started = self.clock()  # before submitting, so a fast reply is timed correctly
        future = self._pool.submit(self._timed, "POST", url, body)
        supplied = frozenset(item["id"] for item in summary["items"])
        return Pending(encounter, request_id, supplied, started, future)

    def _timed(self, method: str, url: str, body: dict) -> tuple[int, dict, float]:
        """Run the request and note when the reply arrived, so lateness is judged by
        arrival time, not by when the game happened to look."""
        status, reply = self.transport(method, url, body, self.deadline)
        return status, reply, self.clock()

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
