"""Debug-Modul - Echtzeitsicht auf Fehler, Abweisungen und Dateninkonsistenzen.

Bei diesem Projekt ist das kein Komfort. Die Sicherheitsaussagen aus
MC-RFC-20260725-001 §9 halten nur, solange zwei Dinge sichtbar werden:
gebrochene Board-Ketten und eine Ledger-Abrechnung, die nicht aufgeht. Genau
diese beiden Faelle landen hier als `inconsistency` - zusammen mit jeder
regelkonformen Abweisung (`reject`) und jedem unerwarteten Fehler (`error`).

Der Puffer liegt im Prozessspeicher und ueberlebt keinen Neustart. Das ist
gewollt: er ist ein Beobachtungsfenster, keine zweite Wahrheit neben Board und
Ledger.
"""

from __future__ import annotations

import threading
import traceback
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

Level = Literal["info", "reject", "error", "inconsistency"]

MAX_EVENTS = 500


@dataclass
class Event:
    ts: str
    level: Level
    category: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


class DebugLog:
    def __init__(self, maxlen: int = MAX_EVENTS) -> None:
        self._events: deque[Event] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._counts: dict[str, int] = {"info": 0, "reject": 0, "error": 0, "inconsistency": 0}

    def log(self, level: Level, category: str, message: str, **detail: Any) -> None:
        event = Event(
            ts=datetime.now().strftime("%H:%M:%S"),
            level=level,
            category=category,
            message=message,
            detail=detail,
        )
        with self._lock:
            self._events.appendleft(event)
            self._counts[level] += 1

    def info(self, category: str, message: str, **detail: Any) -> None:
        self.log("info", category, message, **detail)

    def reject(self, category: str, message: str, **detail: Any) -> None:
        self.log("reject", category, message, **detail)

    def error(self, category: str, message: str, **detail: Any) -> None:
        self.log("error", category, message, **detail)

    def inconsistency(self, category: str, message: str, **detail: Any) -> None:
        self.log("inconsistency", category, message, **detail)

    def exception(self, category: str, exc: BaseException) -> None:
        self.log(
            "error",
            category,
            f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc(limit=6),
        )

    def events(self, level: str | None = None) -> list[Event]:
        with self._lock:
            events = list(self._events)
        if level and level != "all":
            events = [e for e in events if e.level == level]
        return events

    def counts(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counts)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._counts = {k: 0 for k in self._counts}


log = DebugLog()
