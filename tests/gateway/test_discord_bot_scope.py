"""Bot-to-bot permission, narrowed to named channels.

DISCORD_ALLOW_BOTS is server-wide. A standup needs agents answering each
other in one room; every other channel is where their output is read by
people, and a ping-pong there is noise at best. These pin the narrowing.
"""

from plugins.platforms.discord.bot_scope import channel_in_scope, parse_scope


def test_unset_is_server_wide_as_before():
    for raw in (None, "", "   "):
        assert channel_in_scope(raw, "123") is True


def test_only_the_named_channel_admits_bots():
    scope = "1494849990231724032"
    assert channel_in_scope(scope, "1494849990231724032") is True
    assert channel_in_scope(scope, "1494849934288224369") is False


def test_a_thread_inherits_its_parent_channel():
    """Without this the failure looks like agents refusing to answer.

    A thread is its own channel with its own id, so a standup that opens one
    would fall out of scope silently.
    """
    scope = "1494849990231724032"
    assert channel_in_scope(scope, "1540544925005914252",
                            "1494849990231724032") is True
    assert channel_in_scope(scope, "1540544925005914252",
                            "1494849934288224369") is False


def test_hash_prefixes_and_spacing_are_tolerated():
    assert parse_scope(" #standup , 123 ,, ") == {"standup", "123"}
    assert channel_in_scope("#standup, #brain", "standup") is True


# ── where the recent-channel-messages block may be prepended ───────────────


def test_history_backfill_is_everywhere_when_unset():
    from plugins.platforms.discord.bot_scope import history_in_scope
    assert history_in_scope(None, "123") is True
    assert history_in_scope("", "123") is True


def test_an_excluded_channel_gets_no_backfill():
    """Measured 2026-08-22: orion's standup turn arrived as 7,558 characters
    opening "[Recent channel messages]", carrying nova's answer verbatim —
    and orion answered with nova's sentence as its own."""
    from plugins.platforms.discord.bot_scope import history_in_scope
    assert history_in_scope("1494849990231724032", "1494849990231724032") is False
    assert history_in_scope("1494849990231724032", "999") is True


def test_a_thread_inherits_its_parent_s_exclusion():
    from plugins.platforms.discord.bot_scope import history_in_scope
    assert history_in_scope("111", "222", "111") is False
