"""How a call gets a room, its two tokens, and a transport.

Daily is the only thing in the stack that needs something minted before a call
can start, so the REST calls live here instead of in `main.py`, and `bot.py` goes
on knowing nothing about which transport it is running over.

**Two tokens, not one.** The bot joins as owner; the browser does not. Pipecat's
own dev runner hands the same owner token to both, which is right for a sample
and wrong for anything reachable from outside. The room is private and capped at
two participants for the same reason: a room URL that leaks is still useless
without a token, and a token that leaks cannot bring an audience.

Imports are deferred into the functions, like `providers.py`, so `/api/health`
can answer without pulling `daily-python` in.
"""

import logging
import time
from dataclasses import dataclass

from server.config import config

log = logging.getLogger("finvoice.daily")

# A planning conversation runs to minutes, not hours. The room is disposable —
# one is minted per call — so this only has to outlast the longest call anyone
# would actually have, and expiring is how an abandoned room cleans itself up.
ROOM_MINUTES = 60
TOKEN_SECONDS = ROOM_MINUTES * 60


@dataclass(frozen=True)
class Call:
    """One room, and who may join it."""

    room_url: str
    bot_token: str
    user_token: str


async def mint_call(http) -> Call:
    """Create a room for one call, with a token for the bot and one for the browser.

    Args:
        http: An open `aiohttp.ClientSession`; the app holds one for its lifetime.
    """
    from pipecat.transports.daily.utils import (
        DailyRESTHelper,
        DailyRoomParams,
        DailyRoomProperties,
    )

    helper = DailyRESTHelper(daily_api_key=config.daily_api_key, aiohttp_session=http)
    room = await helper.create_room(
        DailyRoomParams(
            privacy="private",
            properties=DailyRoomProperties(
                exp=time.time() + ROOM_MINUTES * 60,
                eject_at_room_exp=True,
                # Straight into the call: a pre-join screen asking to pick a
                # camera is noise for something that never uses one.
                enable_prejoin_ui=False,
                start_video_off=True,
                max_participants=2,
            ),
        )
    )
    bot_token = await helper.get_token(room.url, TOKEN_SECONDS, owner=True)
    user_token = await helper.get_token(
        room.url, TOKEN_SECONDS, owner=False, eject_at_token_exp=True
    )
    log.info("minted room %s", room.url)
    return Call(room_url=room.url, bot_token=bot_token, user_token=user_token)


def make_transport(call: Call):
    """The bot's side of the call."""
    from pipecat.transports.daily.transport import DailyParams, DailyTransport

    return DailyTransport(
        call.room_url,
        call.bot_token,
        "FinVoice",
        params=DailyParams(
            api_key=config.daily_api_key,
            audio_in_enabled=True,
            audio_out_enabled=True,
            # Voice only. Publishing a camera track we never write to costs
            # bandwidth and shows the user a dead video tile.
            camera_out_enabled=False,
            video_out_enabled=False,
            # Deepgram transcribes, not Daily: the STT provider is a seam we
            # choose in providers.py, and Daily's own transcription would
            # quietly bypass it.
            transcription_enabled=False,
        ),
    )
