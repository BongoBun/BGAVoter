"""Data models for BGA Voter."""

import enum


class Player:
    """Represents a player with ranking information."""

    def __init__(
        self, player_id: int, player_name: str, rank_num: int, elo: float
    ) -> None:
        self.player_id = player_id
        self.player_name = player_name
        self.rank_num = rank_num
        self.elo = elo


class ReputationValue(enum.IntEnum):
    """Reputation values for BGA voting system."""

    DOWNVOTE = -1
    NEUTRAL = 0


class RankingMode(enum.StrEnum):
    """Ranking modes for player lookup."""

    ELO = "elo"
    ARENA = "arena"
