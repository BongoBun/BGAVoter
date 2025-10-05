"""BGA API client for reputation management."""

import json
import re
import sys
from datetime import datetime

import requests

from models import Player, RankingMode, ReputationValue
from utils import LOGFILE, clear_log, progress_bar


class BGAVoter:
    """Client for interacting with Board Game Arena reputation system."""

    def __init__(self, cookies: dict, headers: dict) -> None:
        """
        Initialize the BGA Voter client.

        Args:
            cookies: Authentication cookies for BGA
            headers: HTTP headers for BGA requests
        """
        self.cookies = cookies
        self.headers = headers

    # region --- API Requests ---

    def _fetch_player_data(self, player_id: int) -> requests.Response:
        """Fetch player profile data from BGA."""
        params = {"id": player_id}
        response = requests.get(
            "https://boardgamearena.com/player",
            params=params,
            cookies=self.cookies,
            headers=self.headers,
        )
        return response

    def _fetch_ranking_data(
        self, game_id: int, lookup_rank: int, ranking_mode: RankingMode
    ) -> requests.Response:
        """Fetch ranking data for a specific game."""
        data = {
            "game": game_id,
            "start": lookup_rank,
            "mode": ranking_mode.value,
        }
        response = requests.post(
            "https://boardgamearena.com/gamepanel/gamepanel/getRanking.html",
            cookies=self.cookies,
            headers=self.headers,
            data=data,
        )
        return response

    def _update_reputation(
        self, player_id: int, update_action: ReputationValue
    ) -> requests.Response:
        """Update reputation for a specific player."""
        params = {
            "player": player_id,
            "value": update_action.value,
            "category": "personal",
        }
        response = requests.get(
            "https://boardgamearena.com/table/table/changeReputation.html",
            params=params,
            cookies=self.cookies,
            headers=self.headers,
        )
        return response

    # endregion

    # region --- Response Parsers ---

    def _parse_downvoted_ids_from_player_data(
        self, player_data: requests.Response
    ) -> list[int]:
        """Extract downvoted player IDs from player profile HTML."""
        html_content = player_data.text
        downvote_regex = r'"red_thumbs_given"\s*:\s*({[^}]*})'
        match = re.search(downvote_regex, html_content)
        downvoted_ids: list[int] = []

        if match:
            downvote_json = match.group(1)
            downvote_obj = json.loads(downvote_json)
            downvoted_ids = [int(p_id) for p_id in downvote_obj.keys()]

        return downvoted_ids

    def _parse_friend_ids_from_player_data(
        self, player_data: requests.Response
    ) -> list[int]:
        """Extract friend IDs from player profile HTML."""
        html_content = player_data.text
        friend_regex = r'"friends"\s*:\s*({[^}]*})'
        match = re.search(friend_regex, html_content)
        friend_ids: list[int] = []

        if match:
            friend_json = match.group(1)
            friend_obj = json.loads(friend_json)
            friend_ids = [int(p_id) for p_id in friend_obj.keys()]

        return friend_ids

    def _parse_ranking_data(self, response: requests.Response) -> list[Player]:
        """Parse ranking data response into Player objects."""
        data = response.json()
        ranks = data.get("data", {}).get("ranks", [])

        players: list[Player] = []
        for player in ranks:
            player_id = int(player["id"])
            player_name = player["name"]
            rank_num = int(player["rank_no"])
            if "ranking" in player:
                elo = round(float(player.get("ranking")) - 1300, 2)
            else:
                elo = -1
            players.append(Player(player_id, player_name, rank_num, elo))

        return players

    # endregion

    # region --- Helper Methods ---

    def _get_players_above_elo(self, game_id: int, elo_threshold: int) -> list[Player]:
        """
        Fetch all players above a specific ELO threshold.

        Args:
            game_id: The game ID to search
            elo_threshold: Minimum ELO to include

        Returns:
            List of Player objects above the threshold
        """
        players: list[Player] = []
        lookup_rank = 0
        fetched_count = 0

        print(f"Finding players above ELO {elo_threshold}...")

        while True:
            response = self._fetch_ranking_data(game_id, lookup_rank, RankingMode.ELO)
            players_fetched = self._parse_ranking_data(response)
            lowest_elo = players_fetched[-1].elo

            if lowest_elo <= elo_threshold:
                players.extend(p for p in players_fetched if p.elo > elo_threshold)
                fetched_count += sum(
                    1 for p in players_fetched if p.elo > elo_threshold
                )
                progress_bar(fetched_count, fetched_count)
                break

            players.extend(players_fetched)
            fetched_count += len(players_fetched)
            lookup_rank += 10

            sys.stdout.write(
                f"\rFound {fetched_count} players (Current ELO: {lowest_elo:.2f})..."
            )
            sys.stdout.flush()

        print(f"\nTotal players found: {len(players)}")
        return players

    def _get_players_above_arena_rank(
        self, game_id: int, rank_threshold: int
    ) -> list[Player]:
        """
        Fetch all players above a specific Arena rank threshold.

        Args:
            game_id: The game ID to search
            rank_threshold: Maximum rank number to include (lower is better)

        Returns:
            List of Player objects above the threshold
        """
        players: list[Player] = []
        lookup_rank = 0
        fetched_count = 0

        print(f"Finding players above Arena rank {rank_threshold}...")

        while True:
            response = self._fetch_ranking_data(game_id, lookup_rank, RankingMode.ARENA)
            players_fetched = self._parse_ranking_data(response)
            lowest_rank = players_fetched[-1].rank_num

            if lowest_rank >= rank_threshold:
                players.extend(
                    p for p in players_fetched if p.rank_num < rank_threshold
                )
                fetched_count += sum(
                    1 for p in players_fetched if p.rank_num < rank_threshold
                )
                progress_bar(fetched_count, fetched_count)
                break

            players.extend(players_fetched)
            fetched_count += len(players_fetched)
            lookup_rank += 10

            sys.stdout.write(
                f"\rFound {fetched_count} players (Current Rank: {lowest_rank})..."
            )
            sys.stdout.flush()

        print(f"\nTotal players found: {len(players)}")
        return players

    def _get_downvoted_ids(self, player_id: int) -> list[int]:
        """Get list of player IDs that have been downvoted."""
        response = self._fetch_player_data(player_id)
        downvoted_ids = self._parse_downvoted_ids_from_player_data(response)
        return downvoted_ids

    def _get_friend_ids(self, player_id: int) -> list[int]:
        """Get list of friend player IDs."""
        response = self._fetch_player_data(player_id)
        friend_ids = self._parse_friend_ids_from_player_data(response)
        return friend_ids

    def _update_reputation_by_id(
        self, player_id: int, update_action: ReputationValue
    ) -> None:
        """Update reputation by player ID and log the result."""
        response = self._update_reputation(player_id, update_action)
        response_data = response.json()
        status = response_data.get("status")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(LOGFILE, "a", buffering=1) as log_file:
            if status == 1:
                log_file.write(
                    f"[{timestamp}] Reputation updated: Player ID: {player_id} "
                    f"-> {update_action.name}\n"
                )
            else:
                error_msg = response_data.get("error", "Unknown error")
                log_message = (
                    f"[{timestamp}] Reputation update failed: "
                    f"Player ID: {player_id} -> {update_action.name} - {error_msg}"
                )
                log_file.write(log_message + "\n")
                raise Exception(
                    f"Reputation update failed for Player ID: {player_id}: "
                    f"{error_msg}"
                )

    def _update_reputation_by_player(
        self, player: Player, update_action: ReputationValue
    ) -> None:
        """Update reputation by Player object and log the result."""
        response = self._update_reputation(player.player_id, update_action)
        response_data = response.json()
        status = response_data.get("status")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(LOGFILE, "a", buffering=1) as log_file:
            if status == 1:
                log_file.write(
                    f"[{timestamp}] Reputation updated: {player.player_name} "
                    f"(ID: {player.player_id}, Rank: {player.rank_num}, "
                    f"ELO: {player.elo}) -> {update_action.name}\n"
                )
            else:
                error_msg = response_data.get("error", "Unknown error")
                log_message = (
                    f"[{timestamp}] Reputation update failed: {player.player_name} "
                    f"(ID: {player.player_id}, Rank: {player.rank_num}, "
                    f"ELO: {player.elo}) -> {update_action.name} - {error_msg}"
                )
                log_file.write(log_message + "\n")
                raise Exception(
                    f"Reputation update failed for {player.player_name} "
                    f"(ID: {player.player_id}): {error_msg}"
                )

    # endregion

    # region --- Public Methods ---

    @clear_log
    def reset_all_downvotes(self, player_id: int) -> None:
        """
        Reset all downvotes to neutral for a given player.

        Args:
            player_id: The player ID whose downvotes to reset
        """
        try:
            downvoted_ids = self._get_downvoted_ids(player_id)
            total = len(downvoted_ids)
            print(f"Found {total} downvoted players.")

            for i, downvoted_id in enumerate(downvoted_ids, start=1):
                self._update_reputation_by_id(downvoted_id, ReputationValue.NEUTRAL)
                progress_bar(i, total)

            print("\nAll downvotes successfully reset to neutral.")

        except Exception as e:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] Error setting downvotes to neutral: {e}")

    @clear_log
    def adjust_reputation(
        self,
        player_id: int,
        game_id: int,
        threshold: int,
        search_depth: int,
        ranking_mode: RankingMode,
    ) -> None:
        """
        Adjust player reputations based on ranking thresholds.

        Downvotes players below threshold and removes downvotes from players above.
        Friends are never downvoted.

        Args:
            player_id: The player ID performing the reputation updates
            game_id: The game ID to search rankings for
            threshold: The safety threshold (ELO or Arena rank)
            search_depth: How deep to search in rankings
            ranking_mode: Whether to use ELO or Arena rankings
        """
        is_elo_mode = ranking_mode == RankingMode.ELO
        players = (
            self._get_players_above_elo(game_id, search_depth)
            if is_elo_mode
            else self._get_players_above_arena_rank(game_id, search_depth)
        )
        total = len(players)
        downvoted_ids = set(self._get_downvoted_ids(player_id))
        friend_ids = set(self._get_friend_ids(player_id))

        print(
            f"\n=== Adjusting Reputations ===\n"
            f"Mode         : {ranking_mode.name}\n"
            f"Threshold    : {threshold}\n"
            f"Search Depth : {search_depth}\n"
        )
        print(f"Processing {total} players...\n")

        with open(LOGFILE, "a", buffering=1) as log_file:
            for i, player in enumerate(players, start=1):
                try:
                    rank_value = player.elo if is_elo_mode else player.rank_num
                    is_pass_threshold = (
                        rank_value >= threshold
                        if is_elo_mode
                        else rank_value <= threshold
                    )

                    if is_pass_threshold and player.player_id in downvoted_ids:
                        self._update_reputation_by_player(
                            player, ReputationValue.NEUTRAL
                        )
                    elif (
                        not is_pass_threshold
                        and player.player_id not in downvoted_ids
                        and player.player_id not in friend_ids
                    ):
                        self._update_reputation_by_player(
                            player, ReputationValue.DOWNVOTE
                        )
                    else:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        log_file.write(
                            f"[{timestamp}] No reputation update needed: "
                            f"{player.player_name} (ID: {player.player_id}, "
                            f"Rank: {player.rank_num}, ELO: {player.elo}) "
                            f"-> NO_ACTION\n"
                        )

                    progress_bar(i, total)

                except Exception as e:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(
                        f"\n[{timestamp}] Error updating reputation for player "
                        f"{player.player_id} ({player.player_name}): {e}\n"
                    )

        print("\nAll reputation updates completed.\n")

    # endregion
