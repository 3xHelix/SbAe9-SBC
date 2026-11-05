# SPDX-License-Identifier: GPL-2.0-only
"""Paced changes to the card's stream ("Applying changes…").

Direct Mode, Speaker Config / the PipeWire profile, the sample rate and the
bit depth each rebuild the card's stream. Fired in quick bursts they leave the
AE-9 in bad states (stuck DSP, stutter that grows, stalled DMA), so, like
Creative's own app, these go through one queue: one change at a time, each
followed by a settle period while the window shows "Applying changes…".

Effects (SBX, sliders, EQ) don't rebuild the stream and don't come through here.
Changes made outside the app aren't blocked; the app just doesn't add its own
writes on top while a change settles.
"""

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from PySide6.QtCore import QObject, QTimer, Signal

MAX_MS = 10000      # give up waiting for a change to settle after this
POLL_MS = 400


@dataclass
class Change:
    key: str                         # one queued change per key; a newer pick replaces it
    label: str                       # shown under "Applying changes…"
    run: Callable[[], object]        # does the write
    min_ms: int = 3000               # always wait at least this long afterwards
    settled: Optional[Callable[[], bool]] = None   # True once the card looks settled
    needed: Optional[Callable[[], bool]] = None    # checked when its turn comes; False = skip
    started: float = field(default=0.0)


class Applier(QObject):
    busy_changed = Signal(bool)
    step = Signal(str, int, int)     # label, number, total in this round

    def __init__(self, nodes_refresh, parent=None):
        super().__init__(parent)
        self._refresh = nodes_refresh     # kicks a PipeWire snapshot
        self._queue = []
        self._current = None
        self._done = 0
        self._followups = []              # called when the queue runs dry
        self._poll = QTimer(self, interval=POLL_MS)
        self._poll.timeout.connect(self._check)

    @property
    def busy(self):
        return self._current is not None

    def add_followup(self, fn):
        """fn() runs when the queue empties; it may submit more changes, which
        then run inside the same notice."""
        self._followups.append(fn)

    def submit(self, change):
        self._queue = [c for c in self._queue if c.key != change.key]
        self._queue.append(change)
        if not self.busy:
            self._done = 0
            self.busy_changed.emit(True)
            self._next()

    def _next(self):
        if not self._queue:
            for fn in self._followups:
                fn()
        if not self._queue:
            self._current = None
            self._poll.stop()
            self.busy_changed.emit(False)
            return
        c = self._current = self._queue.pop(0)
        if c.needed is not None and not c.needed():
            self._next()   # nothing to do any more (e.g. a later pick undid it)
            return
        self._done += 1
        self.step.emit(c.label, self._done, self._done + len(self._queue))
        c.started = time.monotonic()
        try:
            c.run()
        finally:
            self._refresh()
            self._poll.start()

    def _check(self):
        c = self._current
        if c is None:
            return
        elapsed = (time.monotonic() - c.started) * 1000
        self._refresh()
        if elapsed < c.min_ms:
            return
        ok = True
        if c.settled is not None:
            try:
                ok = bool(c.settled())
            except Exception:
                ok = True
        if ok or elapsed >= MAX_MS:
            self._poll.stop()
            self._next()
