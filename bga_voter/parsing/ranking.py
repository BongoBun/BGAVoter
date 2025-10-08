"""Ranking data parsing."""

from typing import List
from bga_voter.models import Player


def parse_ranking_data(data: dict) -> List[Player]:
    ranks = data.get("data", {}).get("ranks", [])
    players: List[Player] = []
    for p in ranks:
        player_id = int(p["id"])
        name = p["name"]
        rank_no = int(p["rank_no"])
        if "ranking" in p:
            elo = round(float(p.get("ranking")) - 1300, 2)
        else:
            elo = -1
        players.append(Player(player_id, name, rank_no, elo))
    return players
