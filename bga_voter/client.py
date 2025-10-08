"""BGA API client for reputation management with async support."""

import asyncio
import json
import re
import sys
from datetime import datetime

import aiohttp


from models import Player, RankingMode, ReputationValue
from utils import LOGFILE, progress_bar


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

    async def _fetch_player_data(
        self, session: aiohttp.ClientSession, player_id: int
    ) -> str:
        """Fetch player profile data from BGA asynchronously and return HTML text."""
        params = {"id": player_id}
        async with session.get(
            "https://boardgamearena.com/player",
            params=params,
        ) as response:
            return await response.text()

    async def _fetch_ranking_data_async(
        self,
        session: aiohttp.ClientSession,
        game_id: int,
        lookup_rank: int,
        ranking_mode: RankingMode,
    ) -> dict:
        """Fetch ranking data for a specific game asynchronously."""
        data = {
            "game": game_id,
            "start": lookup_rank,
            "mode": ranking_mode.value,
        }
        async with session.post(
            "https://boardgamearena.com/gamepanel/gamepanel/getRanking.html",
            data=data,
        ) as response:
            return await response.json()

    async def _update_reputation_async(
        self,
        session: aiohttp.ClientSession,
        player_id: int,
        update_action: ReputationValue,
    ) -> dict:
        """Update reputation for a specific player asynchronously."""
        params = {
            "player": player_id,
            "value": update_action.value,
            "category": "personal",
        }
        async with session.get(
            "https://boardgamearena.com/table/table/changeReputation.html",
            params=params,
        ) as response:
            return await response.json()

    # endregion

    # region --- Response Parsers ---

    def _parse_downvoted_ids_from_html(self, html_content: str) -> list[int]:
        """Extract downvoted player IDs from raw HTML (shared sync/async)."""
        downvote_regex = r'"red_thumbs_given"\s*:\s*({[^}]*})'
        match = re.search(downvote_regex, html_content)
        if not match:
            return []
        try:
            downvote_json = match.group(1)
            downvote_obj = json.loads(downvote_json)
            return [int(p_id) for p_id in downvote_obj.keys()]
        except (json.JSONDecodeError, ValueError):
            return []

    def _parse_friend_ids_from_html(self, html_content: str) -> list[int]:
        """Extract friend IDs from raw HTML (shared sync/async)."""
        friend_regex = r'"friends"\s*:\s*({[^}]*})'
        match = re.search(friend_regex, html_content)
        if not match:
            return []
        try:
            friend_json = match.group(1)
            friend_obj = json.loads(friend_json)
            return [int(p_id) for p_id in friend_obj.keys()]
        except (json.JSONDecodeError, ValueError):
            return []

    def _parse_ranking_data(self, data: dict) -> list[Player]:
        """Parse ranking data dict into Player objects."""
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

    async def _get_players_above_elo_async(
        self, session: aiohttp.ClientSession, game_id: int, elo_threshold: int
    ) -> list[Player]:
        """
        Fetch all players above a specific ELO threshold asynchronously.

        Args:
            session: aiohttp session
            game_id: The game ID to search
            elo_threshold: Minimum ELO to include

        Returns:
            List of Player objects above the threshold
        """
        players: list[Player] = []
        lookup_rank = 0
        fetched_count = 0
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"Finding players above ELO {elo_threshold}...")
        with open(LOGFILE, "a", buffering=1) as log_file:
            log_file.write(
                f"[{timestamp}] Starting ELO search (threshold: {elo_threshold})\n"
            )

        while True:
            response_data = await self._fetch_ranking_data_async(
                session, game_id, lookup_rank, RankingMode.ELO
            )
            players_fetched = self._parse_ranking_data(response_data)

            if not players_fetched:
                break

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
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOGFILE, "a", buffering=1) as log_file:
            log_file.write(
                f"[{timestamp}] ELO search complete: {len(players)} players found\n"
            )

        return players

    async def _get_players_above_arena_rank_async(
        self, session: aiohttp.ClientSession, game_id: int, rank_threshold: int
    ) -> list[Player]:
        """
        Fetch all players above a specific Arena rank threshold asynchronously.

        Args:
            session: aiohttp session
            game_id: The game ID to search
            rank_threshold: Maximum rank number to include (lower is better)

        Returns:
            List of Player objects above the threshold
        """
        players: list[Player] = []
        lookup_rank = 0
        fetched_count = 0
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"Finding players above Arena rank {rank_threshold}...")
        with open(LOGFILE, "a", buffering=1) as log_file:
            log_file.write(
                f"[{timestamp}] Starting Arena rank search (threshold: {rank_threshold})\n"
            )

        while True:
            response_data = await self._fetch_ranking_data_async(
                session, game_id, lookup_rank, RankingMode.ARENA
            )
            players_fetched = self._parse_ranking_data(response_data)

            if not players_fetched:
                break

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
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOGFILE, "a", buffering=1) as log_file:
            log_file.write(
                f"[{timestamp}] Arena rank search complete: {len(players)} players found\n"
            )

        return players

    async def _get_downvoted_ids_async(
        self, session: aiohttp.ClientSession, player_id: int
    ) -> list[int]:
        """Get list of player IDs that have been downvoted (sync fetch in async context)."""
        html_content = await self._fetch_player_data(session, player_id)
        return self._parse_downvoted_ids_from_html(html_content)

    async def _get_friend_ids_async(
        self, session: aiohttp.ClientSession, player_id: int
    ) -> list[int]:
        """Get list of friend player IDs (sync fetch in async context)."""
        html_content = await self._fetch_player_data(session, player_id)
        return self._parse_friend_ids_from_html(html_content)

    async def _update_reputation_by_id_async(
        self,
        session: aiohttp.ClientSession,
        player_id: int,
        update_action: ReputationValue,
        log_lock: asyncio.Lock,
    ) -> None:
        """Async version of updating reputation by player ID with logging."""
        response_data = await self._update_reputation_async(
            session, player_id, update_action
        )
        status = response_data.get("status")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        async with log_lock:
            with open(LOGFILE, "a", buffering=1) as log_file:
                if status == 1:
                    log_file.write(
                        f"[{timestamp}] Reputation updated: Player ID: {player_id} -> {update_action.name}\n"
                    )
                else:
                    error_msg = response_data.get("error", "Unknown error")
                    log_message = f"[{timestamp}] Reputation update failed: Player ID: {player_id} -> {update_action.name} - {error_msg}"
                    log_file.write(log_message + "\n")
                    raise Exception(
                        f"Reputation update failed for Player ID: {player_id}: {error_msg}"
                    )

    async def _update_reputation_by_player_async(
        self,
        session: aiohttp.ClientSession,
        player: Player,
        update_action: ReputationValue,
        log_lock: asyncio.Lock,
    ) -> None:
        """Update reputation by Player object asynchronously and log the result."""
        response_data = await self._update_reputation_async(
            session, player.player_id, update_action
        )
        status = response_data.get("status")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        async with log_lock:
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

    async def _reset_all_downvotes_async(self, player_id: int) -> None:
        """Async implementation of resetting all downvotes to neutral."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        connector = aiohttp.TCPConnector(limit=5)
        try:
            async with aiohttp.ClientSession(
                cookies=self.cookies,
                headers=self.headers,
                connector=connector,
            ) as session:
                downvoted_ids = await self._get_downvoted_ids_async(session, player_id)
                total = len(downvoted_ids)
                print(f"Found {total} downvoted players.")

                if total == 0:
                    print("No downvotes to reset.")
                    return

                log_lock = asyncio.Lock()
                tasks = [
                    self._update_reputation_by_id_async(
                        session, downvoted_id, ReputationValue.NEUTRAL, log_lock
                    )
                    for downvoted_id in downvoted_ids
                ]

                completed = 0
                for coro in asyncio.as_completed(tasks):
                    try:
                        await coro
                        completed += 1
                        progress_bar(completed, total)
                    except Exception as e:
                        timestamp_err = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        print(f"\n[{timestamp_err}] Error resetting downvote: {e}")

                print("\nAll downvotes successfully reset to neutral.")
        except Exception as e:
            print(f"[{timestamp}] Error setting downvotes to neutral: {e}")

    async def reset_all_downvotes_async(self, player_id: int) -> None:
        """Public async method to reset all downvotes, clearing the log first.

        This mirrors the synchronous `reset_all_downvotes` method but is awaitable
        for callers already inside an event loop.
        """

        await self._reset_all_downvotes_async(player_id)

    async def _adjust_reputation_async(
        self,
        player_id: int,
        game_id: int,
        threshold: int,
        search_depth: int,
        ranking_mode: RankingMode,
    ) -> None:
        """Async implementation of adjust_reputation."""
        # Create aiohttp session with cookies and headers
        connector = aiohttp.TCPConnector(limit=5)  # Limit concurrent connections
        async with aiohttp.ClientSession(
            cookies=self.cookies, headers=self.headers, connector=connector
        ) as session:
            is_elo_mode = ranking_mode == RankingMode.ELO
            players = (
                await self._get_players_above_elo_async(session, game_id, search_depth)
                if is_elo_mode
                else await self._get_players_above_arena_rank_async(
                    session, game_id, search_depth
                )
            )
            total = len(players)
            downvoted_ids_list, friend_ids_list = await asyncio.gather(
                self._get_downvoted_ids_async(session, player_id),
                self._get_friend_ids_async(session, player_id),
            )
            downvoted_ids = set(downvoted_ids_list)
            friend_ids = set(friend_ids_list)

            print(
                f"\n=== Adjusting Reputations ===\n"
                f"Mode         : {ranking_mode.name}\n"
                f"Threshold    : {threshold}\n"
                f"Search Depth : {search_depth}\n"
            )
            print(f"Processing {total} players...\n")

            log_lock = asyncio.Lock()
            tasks = []
            completed = 0
            set_to_neutral = 0
            downvoted = 0
            no_change = 0
            failed = 0

            player_action_map = {}

            with open(LOGFILE, "a", buffering=1) as log_file:
                for player in players:
                    rank_value = player.elo if is_elo_mode else player.rank_num
                    is_pass_threshold = (
                        rank_value >= threshold
                        if is_elo_mode
                        else rank_value <= threshold
                    )

                    if is_pass_threshold and player.player_id in downvoted_ids:
                        task = self._update_reputation_by_player_async(
                            session, player, ReputationValue.NEUTRAL, log_lock
                        )
                        tasks.append((task, "neutral"))
                        player_action_map[player.player_id] = "neutral"
                    elif (
                        not is_pass_threshold
                        and player.player_id not in downvoted_ids
                        and player.player_id not in friend_ids
                    ):
                        task = self._update_reputation_by_player_async(
                            session, player, ReputationValue.DOWNVOTE, log_lock
                        )
                        tasks.append((task, "downvoted"))
                        player_action_map[player.player_id] = "downvoted"
                    else:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        log_file.write(
                            f"[{timestamp}] No reputation update needed: "
                            f"{player.player_name} (ID: {player.player_id}, "
                            f"Rank: {player.rank_num}, ELO: {player.elo}) "
                            f"-> NO_ACTION\n"
                        )
                        no_change += 1
                        player_action_map[player.player_id] = "no_change"

            # Execute all tasks concurrently and track results
            for coro, action in tasks:
                try:
                    await coro
                    completed += 1
                    if action == "neutral":
                        set_to_neutral += 1
                    elif action == "downvoted":
                        downvoted += 1
                    progress_bar(completed, len(tasks))
                except Exception as e:
                    failed += 1
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"\n[{timestamp}] Error updating reputation: {e}\n")

        print("\nAll reputation updates completed.\n")
        print(f"Total processed: {total}")
        print(f"Set to neutral: {set_to_neutral}")
        print(f"Downvoted: {downvoted}")
        print(f"No change: {no_change}")
        print(f"Failed: {failed}")

        # Log summary statistics
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOGFILE, "a", buffering=1) as log_file:
            log_file.write(f"[{timestamp}] Reputation update summary:\n")
            log_file.write(f"Total processed: {total}\n")
            log_file.write(f"Set to neutral: {set_to_neutral}\n")
            log_file.write(f"Downvoted: {downvoted}\n")
            log_file.write(f"No change: {no_change}\n")
            log_file.write(f"Failed: {failed}\n")

    # endregion
