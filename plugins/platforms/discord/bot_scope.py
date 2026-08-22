"""Which channels bot-to-bot messages are allowed in.

``DISCORD_ALLOW_BOTS`` decides *whether* one bot may hear another; this
decides *where*. Letting agents talk to each other is useful in exactly one
room — a standup, a triage huddle — and a liability everywhere else, because
every other channel is where their output is read by people. Turning the whole
server bot-to-bot to get one room is a poor trade.

Unset means server-wide, which is what ``DISCORD_ALLOW_BOTS`` did before this
existed. Nothing changes for anyone who does not set it.
"""

from __future__ import annotations

from typing import Optional


def parse_scope(raw: Optional[str]) -> set[str]:
    """Channel ids (or names) from a comma-separated allowlist.

    A leading ``#`` is tolerated because that is how the channels are written
    everywhere else — in configs, in the send targets, in conversation.
    """
    return {
        item.strip().lstrip("#")
        for item in (raw or "").split(",")
        if item.strip()
    }


def channel_in_scope(raw_scope: Optional[str], channel_id: str,
                     parent_id: str = "") -> bool:
    """May bots speak to each other here?

    ``parent_id`` matters: a thread is its own channel with its own id, so a
    standup that opens a thread would silently fall out of scope without it —
    the failure would look like the agents simply refusing to answer.
    """
    scope = parse_scope(raw_scope)
    if not scope:
        return True
    return str(channel_id) in scope or (bool(parent_id) and str(parent_id) in scope)


def history_in_scope(raw_exclude: Optional[str], channel_id: str,
                     parent_id: str = "") -> bool:
    """May the recent-channel-messages block be prepended here?

    ``DISCORD_ALLOW_BOTS`` turns out to govern two different things: whether
    another bot's message *triggers* a turn, and whether it is *included* in
    the backfilled context block. Measured 2026-08-22 in a live standup —
    orion's turn arrived as 7,558 characters opening "[Recent channel
    messages]" and carrying cipher's, ledger's and nova's answers verbatim.
    Orion answered with nova's sentence, "semua aktivitas hari ini murni
    administratif Marketing", as its own.

    Worse, zenith's closing summary of the previous run was in there too, so
    each run fed the next one its own paraphrase.

    A standup is exactly the room where agents must NOT read each other
    freely: the whole design is that a claim reaches the division it names
    through a controlled relay, with the claim attributed. Uncontrolled
    context turns that into copying.

    Unset means backfill everywhere, which is what happened before this
    existed. Nothing changes for anyone who does not set it.
    """
    excluded = parse_scope(raw_exclude)
    if not excluded:
        return True
    return not (str(channel_id) in excluded
                or (bool(parent_id) and str(parent_id) in excluded))
