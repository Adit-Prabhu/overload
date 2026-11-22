"""HTTP client for the rival service, run on a background thread.

The frame loop never waits on the network: requests go to a small thread pool and the
selector polls the result each frame. The transport is injectable so tests never touch the
network. No credentials live here. The service holds any provider key.
"""

from __future__ import annotations

import contextlib
import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass

from overload import __version__

DEADLINE_SECONDS = 5.0
HISTORY_LIMIT = 2  # matches worker/src/schema.ts HISTORY_LIMIT
USER_AGENT = f"overload-game/{__version__}"
COUNTED_WORKER_STATUSES = frozenset(
    {
        "ok",
        "invalid_output",
        "timeout",
        "provider_error",
        "budget",
        "provider_not_configured",
    }
)

Transport = Callable[[str, str, dict | None, float], tuple[int, dict]]


def is_timeout_error(exc: BaseException) -> bool:
    """True for socket TimeoutError or URLError wrapping a TimeoutError."""
    if isinstance(exc, TimeoutError):
        return True
    return isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, TimeoutError)


def _worker_recorded_history(status_code: int, body: object, session_id: str) -> bool:
    """True when the Worker reply indicates RivalSession.propose persisted this summary."""
    if status_code != 200 or not isinstance(body, Mapping):
        return False
    if body.get("session_id") not in (None, session_id):
        return False
    reply_status = body.get("status")
    if not isinstance(reply_status, str):
        return False
    if reply_status in COUNTED_WORKER_STATUSES:
        return True
    if reply_status == "internal_error":
        attempts = body.get("attempts_used")
        return isinstance(attempts, int) and not isinstance(attempts, bool) and attempts >= 1
    return False


def urllib_transport(method: str, url: str, body: dict | None, timeout: float) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    # Cloudflare's edge refuses the default Python-urllib user agent (error 1010), so the
    # game names itself. The string identifies the build only, never the player.
    headers = {"content-type": "application/json", "user-agent": USER_AGENT}
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
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
    prior_supplied_ids: frozenset[str] = frozenset()


class TacticClient:
    def __init__(
        self,
        base_url: str,
        transport: Transport = urllib_transport,
        clock: Callable[[], float] = time.monotonic,
        deadline: float = DEADLINE_SECONDS,
        session_timeout: float = DEADLINE_SECONDS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        self.clock = clock
        self.deadline = deadline
        self.session_timeout = (
            session_timeout  # setup happens before play, apart from tactic deadlines
        )
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rival")
        self._warm_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rival-warm")
        self._warm_future: Future[None] | None = None
        self._history_lock = threading.Lock()
        self._session_history: dict[str, list[tuple[str, frozenset[str]]]] = {}

    def start_session(self) -> str | None:
        """Blocking, called once before play starts. None means live mode is unavailable."""
        try:
            status, body = self.transport(
                "POST", f"{self.base_url}/sessions", None, self.session_timeout
            )
        except Exception:  # unreachable, malformed or anything else: live mode is unavailable
            return None
        if status != 201 or not isinstance(body, dict):
            return None
        session_id = body.get("session_id")
        return session_id if isinstance(session_id, str) else None

    def submit(self, session_id: str, encounter: int, request_id: str, summary: dict) -> Pending:
        body = {"request_id": request_id, "encounter": encounter, "summary": summary}
        url = f"{self.base_url}/sessions/{session_id}/tactic"
        started = self.clock()  # before submitting, so a fast reply is timed correctly
        current = frozenset(item["id"] for item in summary["items"])
        with self._history_lock:
            prior_entries = self._session_history.get(session_id, [])
            prior = (
                frozenset().union(*(ids for _, ids in prior_entries))
                if prior_entries
                else frozenset()
            )
            self._session_history[session_id] = [*prior_entries, (request_id, current)][
                -HISTORY_LIMIT:
            ]
        future = self._pool.submit(self._timed, session_id, request_id, "POST", url, body)
        return Pending(encounter, request_id, current, started, future, prior_supplied_ids=prior)

    def _discard_history(self, session_id: str, request_id: str) -> None:
        with self._history_lock:
            entries = self._session_history.get(session_id)
            if not entries:
                return
            kept = [entry for entry in entries if entry[0] != request_id]
            if kept:
                self._session_history[session_id] = kept
            else:
                self._session_history.pop(session_id, None)

    def warm(self, session_id: str) -> None:
        """Fire-and-forget OAuth warm-up on its own pool. Never blocks or raises."""
        if self._warm_future is not None and not self._warm_future.done():
            return
        try:
            self._warm_future = self._warm_pool.submit(self._warm, session_id)
        except RuntimeError:
            return

    def _warm(self, session_id: str) -> None:
        with contextlib.suppress(Exception):
            self.transport(
                "POST",
                f"{self.base_url}/sessions/{session_id}/warmup",
                None,
                min(3.0, self.deadline),
            )

    def _timed(
        self, session_id: str, request_id: str, method: str, url: str, body: dict
    ) -> tuple[int, dict, float]:
        """Run the request and note when the reply arrived, so lateness is judged by
        arrival time, not by when the game happened to look."""
        try:
            status, reply = self.transport(method, url, body, self.deadline)
        except Exception as exc:
            if not is_timeout_error(exc):
                self._discard_history(session_id, request_id)
            raise
        if not _worker_recorded_history(status, reply, session_id):
            self._discard_history(session_id, request_id)
        return status, reply, self.clock()

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
        self._warm_pool.shutdown(wait=False, cancel_futures=True)
