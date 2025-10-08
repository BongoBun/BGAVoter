"""HTTP operations (async) against BGA endpoints."""

import aiohttp
from bga_voter.models import RankingMode, ReputationValue

PLAYER_URL = "https://boardgamearena.com/player"
RANKING_URL = "https://boardgamearena.com/gamepanel/gamepanel/getRanking.html"
REP_UPDATE_URL = "https://boardgamearena.com/table/table/changeReputation.html"


async def fetch_player_html(session: aiohttp.ClientSession, player_id: int) -> str:
    async with session.get(PLAYER_URL, params={"id": player_id}) as r:
        return await r.text()


async def fetch_ranking_json(
    session: aiohttp.ClientSession, game_id: int, start: int, mode: RankingMode
) -> dict:
    async with session.post(
        RANKING_URL, data={"game": game_id, "start": start, "mode": mode.value}
    ) as r:
        return await r.json()


async def post_reputation_update(
    session: aiohttp.ClientSession, player_id: int, value: ReputationValue
) -> dict:
    async with session.get(
        REP_UPDATE_URL,
        params={"player": player_id, "value": value.value, "category": "personal"},
    ) as r:
        return await r.json()
