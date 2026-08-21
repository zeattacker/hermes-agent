"""Tests for the bot-to-bot turn ceiling.

The failure this prevents is not a wrong message. It is a right one sent four
hundred times: two agents answering each other at three in the morning in a
channel nobody watches, against a metered LLM. DISCORD_ALLOW_BOTS makes that
possible and the mention-routing above it makes it *likely*, because a reply
that mentions the sender is exactly what reaches us.
"""

import unittest

from plugins.platforms.discord.bot_turn_limit import (
    DEFAULT_LIMIT,
    BotTurnLimiter,
)


class TestBotTurnLimit(unittest.TestCase):
    def test_an_exchange_under_the_ceiling_is_untouched(self):
        limiter = BotTurnLimiter(limit=5, window_s=100)
        self.assertTrue(all(
            limiter.allow_bot_turn("c", now=t) for t in range(5)))

    def test_the_ceiling_stops_the_exchange(self):
        limiter = BotTurnLimiter(limit=3, window_s=100)
        allowed = [limiter.allow_bot_turn("c", now=t) for t in range(5)]
        self.assertEqual(allowed, [True, True, True, False, False])

    def test_a_human_speaking_clears_the_count(self):
        """The strongest signal that the channel is attended."""
        limiter = BotTurnLimiter(limit=2, window_s=100)
        limiter.allow_bot_turn("c", now=0)
        limiter.allow_bot_turn("c", now=1)
        self.assertFalse(limiter.allow_bot_turn("c", now=2))

        limiter.note_human("c")
        self.assertTrue(limiter.allow_bot_turn("c", now=3))

    def test_quiet_ends_the_exchange_so_nights_do_not_accumulate(self):
        """A channel hosting one standup a night must not trip on the fourth."""
        limiter = BotTurnLimiter(limit=2, window_s=60)
        limiter.allow_bot_turn("c", now=0)
        limiter.allow_bot_turn("c", now=1)
        self.assertFalse(limiter.allow_bot_turn("c", now=2))

        self.assertTrue(limiter.allow_bot_turn("c", now=1000))

    def test_channels_are_counted_apart(self):
        """A loop in #standup must not silence #engineering."""
        limiter = BotTurnLimiter(limit=1, window_s=100)
        self.assertTrue(limiter.allow_bot_turn("standup", now=0))
        self.assertFalse(limiter.allow_bot_turn("standup", now=1))
        self.assertTrue(limiter.allow_bot_turn("engineering", now=2))

    def test_the_turn_is_counted_before_the_model_is_called(self):
        """A turn that is refused after the call still cost the call.

        The ceiling bounds spend as much as noise, so it counts on the way in.
        """
        limiter = BotTurnLimiter(limit=1, window_s=100)
        limiter.allow_bot_turn("c", now=0)
        self.assertEqual(limiter.turns("c"), 1)

    def test_the_default_ceiling_is_well_above_a_real_standup(self):
        """Reaching it should read as "something is looping", not "the
        meeting ran long". Five divisions answering zenith once each is 10."""
        self.assertGreaterEqual(DEFAULT_LIMIT, 10)

    def test_a_bad_env_value_falls_back_instead_of_disabling_the_guard(self):
        import os
        os.environ["DISCORD_BOT_TURN_LIMIT"] = "not-a-number"
        try:
            limiter = BotTurnLimiter(window_s=100)
            allowed = [limiter.allow_bot_turn("c", now=t)
                       for t in range(DEFAULT_LIMIT + 2)]
            self.assertTrue(allowed[0])
            self.assertFalse(allowed[-1])
        finally:
            os.environ.pop("DISCORD_BOT_TURN_LIMIT", None)

    def test_zero_is_refused_as_a_limit_so_the_guard_cannot_mute_everything(self):
        import os
        os.environ["DISCORD_BOT_TURN_LIMIT"] = "0"
        try:
            limiter = BotTurnLimiter(window_s=100)
            self.assertTrue(limiter.allow_bot_turn("c", now=0))
        finally:
            os.environ.pop("DISCORD_BOT_TURN_LIMIT", None)


if __name__ == "__main__":
    unittest.main()
