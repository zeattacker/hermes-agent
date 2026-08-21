"""A ceiling on how long two bots may talk to each other unattended.

Why
---
``DISCORD_ALLOW_BOTS`` (adapter.py, the ``on_message`` gate) lets one agent
answer another. The routing is already correct: a message mentioning some
other bot is ignored, so several agents can share a channel without shouting
over each other. What is missing is a stop.

Nothing in the adapter bounds an exchange. If zenith mentions cipher, cipher
answers mentioning zenith, and zenith answers again, the pair will keep going
for as long as the gateways are up — at three in the morning, in a channel
nobody is watching, against a metered LLM. The failure is not that a wrong
message is sent; it is that a right one is sent four hundred times.

So this counts consecutive bot-authored messages per channel and refuses past
a limit. It is a circuit breaker, not a conversation policy: the number should
be high enough that no real standup reaches it, and reaching it should be read
as "something is looping", not "the meeting ran long".

What resets it
--------------
**A human speaking.** That is the strongest signal that the channel is
attended and whatever happened before is over.

**Quiet.** An exchange that resumes after a long gap is a new exchange, not a
continuation — otherwise a channel that hosts one standup a night would
accumulate turns across nights and trip on the fourth.

Inert until switched on
-----------------------
With ``DISCORD_ALLOW_BOTS`` unset (the default, "none") no bot message reaches
this code at all, so installing it changes nothing until the flag is flipped.
That ordering is deliberate: the guard lands first, the capability second.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field

DEFAULT_LIMIT = 12
DEFAULT_WINDOW_S = 900.0   # 15 minutes of quiet ends an exchange

_ENV_LIMIT = "DISCORD_BOT_TURN_LIMIT"
_ENV_WINDOW = "DISCORD_BOT_TURN_WINDOW_S"


def _env_number(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass
class _Channel:
    turns: int = 0
    last_at: float = 0.0


@dataclass
class BotTurnLimiter:
    """Per-channel ceiling on consecutive bot-to-bot turns.

    Thread-safe: discord.py dispatches ``on_message`` on the event loop, but
    the adapter also touches state from worker threads, and a counter that
    undercounts under a race would defeat the point of having it.
    """

    limit: int = 0
    window_s: float = 0.0
    _channels: dict[str, _Channel] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _limit(self) -> int:
        return int(self.limit or _env_number(_ENV_LIMIT, DEFAULT_LIMIT))

    def _window(self) -> float:
        return self.window_s or _env_number(_ENV_WINDOW, DEFAULT_WINDOW_S)

    def note_human(self, channel_id: str) -> None:
        """A person spoke here. Whatever the bots were doing is over."""
        with self._lock:
            self._channels.pop(str(channel_id), None)

    def allow_bot_turn(self, channel_id: str, *, now: float | None = None) -> bool:
        """Count one bot-authored message. False once the ceiling is reached.

        Counts on the way in rather than on the way out: a turn that fails
        after the model has been called still cost the call, and the point of
        the ceiling is to bound spend as much as noise.
        """
        key = str(channel_id)
        stamp = time.monotonic() if now is None else now
        with self._lock:
            state = self._channels.get(key)
            if state is None or (stamp - state.last_at) > self._window():
                state = _Channel()
                self._channels[key] = state
            state.turns += 1
            state.last_at = stamp
            return state.turns <= self._limit()

    def turns(self, channel_id: str) -> int:
        with self._lock:
            state = self._channels.get(str(channel_id))
            return state.turns if state else 0

    def reset(self, channel_id: str | None = None) -> None:
        with self._lock:
            if channel_id is None:
                self._channels.clear()
            else:
                self._channels.pop(str(channel_id), None)
