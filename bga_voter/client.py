"""BGA API client for reputation management with async support.

Refactored into modular subpackages: net (HTTP), parsing (HTML/JSON), logging (async logger), utils.
"""

import asyncio
import sys
from typing import Optional

import aiohttp

from bga_voter.models import Player, RankingMode, ReputationValue
from bga_voter.logger import AsyncLogger, LOGFILE
from bga_voter.utils import progress_bar
from bga_voter.net import fetch_player_html, fetch_ranking_json, post_reputation_update
from bga_voter.parsing import (
    parse_downvoted_ids,
    parse_friend_ids,
    parse_ranking_data,
)


class BGAVoter:
    """Client for interacting with Board Game Arena reputation system."""

    def __init__(
        self,
        cookies: dict,
        headers: dict,
        *,
        connector_limit: int = 10,
        logger: Optional[AsyncLogger] = None,
        log_file: str | None = None,
        auto_timestamp: bool = True,
        update_concurrency: int = 10,
    ) -> None:
        self.cookies = cookies
        self.headers = headers
        self.connector_limit = connector_limit
        self._session: aiohttp.ClientSession | None = None
        self.logger: AsyncLogger | None = logger or (
            AsyncLogger(log_file or LOGFILE, auto_timestamp=auto_timestamp)
            if log_file or logger is None
            else None
        )
        self.update_concurrency = max(1, int(update_concurrency))

    # --- Async context management -------------------------------------------------

    async def __aenter__(self) -> "BGAVoter":
        if self._session is None:
            connector = aiohttp.TCPConnector(limit=self.connector_limit)
            self._session = aiohttp.ClientSession(
                cookies=self.cookies, headers=self.headers, connector=connector
            )
        if self.logger and self.logger._task is None:
            await self.logger.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._session:
            await self._session.close()
            self._session = None
        if self.logger:
            await self.logger.stop()

    @property
    def session(self) -> aiohttp.ClientSession:
        if not self._session:
            raise RuntimeError(
                "Session not initialized. Use 'async with BGAVoter(...)'."
            )
        return self._session

    # --- Logging helpers ---------------------------------------------------------

    def get_logger(self) -> AsyncLogger | None:
        return self.logger

    async def log(self, message: str) -> None:
        if self.logger:
            await self.logger.log(message)

    async def _log(self, message: str) -> None:
        """Internal unified logging (async logger or sync fallback)."""
        if self.logger:
            await self.logger.log(message)
        else:
            with open(LOGFILE, "a", buffering=1) as f:
                f.write(message + "\n")

    # --- API Requests ------------------------------------------------------------

    async def _fetch_player_data(self, player_id: int) -> str:
        return await fetch_player_html(self.session, player_id)

    async def _fetch_ranking_data_async(
        self, game_id: int, lookup_rank: int, ranking_mode: RankingMode
    ) -> dict:
        return await fetch_ranking_json(
            self.session, game_id, lookup_rank, ranking_mode
        )

    async def _update_reputation_async(
        self, player_id: int, update_action: ReputationValue
    ) -> dict:
        return await post_reputation_update(self.session, player_id, update_action)

    # --- Parsers -----------------------------------------------------------------

    # Parsing now delegated to parsing subpackage

    # --- Helpers -----------------------------------------------------------------

    async def _get_players_above_elo_async(
        self, game_id: int, elo_threshold: int
    ) -> list[Player]:
        players: list[Player] = []
        lookup_rank = 0
        fetched = 0
        print(f"Finding players above ELO {elo_threshold}...")
        await self._log(f"Starting ELO search (threshold={elo_threshold})")

        while True:
            data = await self._fetch_ranking_data_async(
                game_id, lookup_rank, RankingMode.ELO
            )
            batch = parse_ranking_data(data)
            if not batch:
                break
            lowest_elo = batch[-1].elo
            if lowest_elo <= elo_threshold:
                filtered = [p for p in batch if p.elo > elo_threshold]
                players.extend(filtered)
                fetched += len(filtered)
                progress_bar(fetched, fetched)
                break
            players.extend(batch)
            fetched += len(batch)
            lookup_rank += 10
            sys.stdout.write(
                f"\rFound {fetched} players (Current ELO: {lowest_elo:.2f})..."
            )
            sys.stdout.flush()

        print(f"\nTotal players found: {len(players)}")
        await self._log(f"ELO search complete: {len(players)} players found")
        return players

    async def _get_players_above_arena_rank_async(
        self, game_id: int, rank_threshold: int
    ) -> list[Player]:
        players: list[Player] = []
        lookup_rank = 0
        fetched = 0
        print(f"Finding players above Arena rank {rank_threshold}...")
        await self._log(f"Starting Arena rank search (threshold={rank_threshold})")

        while True:
            data = await self._fetch_ranking_data_async(
                game_id, lookup_rank, RankingMode.ARENA
            )
            batch = parse_ranking_data(data)
            if not batch:
                break
            lowest_rank = batch[-1].rank_num
            if lowest_rank >= rank_threshold:
                filtered = [p for p in batch if p.rank_num < rank_threshold]
                players.extend(filtered)
                fetched += len(filtered)
                progress_bar(fetched, fetched)
                break
            players.extend(batch)
            fetched += len(batch)
            lookup_rank += 10
            sys.stdout.write(
                f"\rFound {fetched} players (Current Rank: {lowest_rank})..."
            )
            sys.stdout.flush()

        print(f"\nTotal players found: {len(players)}")
        await self._log(f"Arena rank search complete: {len(players)} players found")
        return players

    async def _get_downvoted_ids_async(self, player_id: int) -> list[int]:
        html = await self._fetch_player_data(player_id)
        return parse_downvoted_ids(html)

    async def _get_friend_ids_async(self, player_id: int) -> list[int]:
        html = await self._fetch_player_data(player_id)
        return parse_friend_ids(html)

    async def _log_update_result(
        self,
        success: bool,
        player_repr: str,
        action: ReputationValue,
        error: str | None = None,
    ) -> None:
        if success:
            await self._log(f"Reputation updated: {player_repr} -> {action.name}")
        else:
            await self._log(
                f"Reputation update failed: {player_repr} -> {action.name} - {error or 'Unknown error'}"
            )

    async def _update_reputation_by_id_async(
        self, player_id: int, update_action: ReputationValue, log_lock: asyncio.Lock
    ) -> None:
        data = await self._update_reputation_async(player_id, update_action)
        status = data.get("status")
        async with log_lock:
            if status == 1:
                await self._log_update_result(
                    True, f"Player ID {player_id}", update_action
                )
            else:
                error_msg = data.get("error", "Unknown error")
                await self._log_update_result(
                    False, f"Player ID {player_id}", update_action, error_msg
                )
                raise Exception(
                    f"Reputation update failed for Player ID {player_id}: {error_msg}"
                )

    async def _update_reputation_by_player_async(
        self, player: Player, update_action: ReputationValue, log_lock: asyncio.Lock
    ) -> None:
        data = await self._update_reputation_async(player.player_id, update_action)
        status = data.get("status")
        descriptor = f"{player.player_name} (ID:{player.player_id}, Rank:{player.rank_num}, ELO:{player.elo})"
        async with log_lock:
            if status == 1:
                await self._log_update_result(True, descriptor, update_action)
            else:
                error_msg = data.get("error", "Unknown error")
                await self._log_update_result(
                    False, descriptor, update_action, error_msg
                )
                raise Exception(
                    f"Reputation update failed for {player.player_name} (ID {player.player_id}): {error_msg}"
                )

    # --- Public Methods ----------------------------------------------------------

    async def _reset_all_downvotes_async(self, player_id: int) -> None:
        """Reset all existing downvotes to neutral."""
        try:
            downvoted_ids = await self._get_downvoted_ids_async(player_id)
            total = len(downvoted_ids)
            print(f"Found {total} downvoted players.")
            if total == 0:
                print("No downvotes to reset.")
                return

            log_lock = asyncio.Lock()
            tasks = [
                asyncio.create_task(
                    self._update_reputation_by_id_async(
                        pid, ReputationValue.NEUTRAL, log_lock
                    )
                )
                for pid in downvoted_ids
            ]

            completed = 0
            for fut in asyncio.as_completed(tasks):
                try:
                    await fut
                    completed += 1
                    progress_bar(completed, total)
                except Exception as e:
                    print(f"\nError resetting downvote: {e}")
                    await self._log(f"Error resetting downvote: {e}")

            print("\nAll downvotes successfully reset to neutral.")
            await self._log(f"All downvotes reset to neutral (count={total})")
        except Exception as e:
            print(f"Error setting downvotes to neutral: {e}")
            await self._log(f"Error setting downvotes to neutral: {e}")

    async def reset_all_downvotes_async(self, player_id: int) -> None:
        await self._reset_all_downvotes_async(player_id)

    async def _adjust_reputation_async(
        self,
        player_id: int,
        game_id: int,
        threshold: int,
        search_depth: int,
        ranking_mode: RankingMode,
    ) -> None:
        """Adjust reputations concurrently with bounded concurrency."""
        is_elo_mode = ranking_mode == RankingMode.ELO
        players = (
            await self._get_players_above_elo_async(game_id, search_depth)
            if is_elo_mode
            else await self._get_players_above_arena_rank_async(game_id, search_depth)
        )

        downvoted_ids_list, friend_ids_list = await asyncio.gather(
            self._get_downvoted_ids_async(player_id),
            self._get_friend_ids_async(player_id),
        )
        downvoted_ids = set(downvoted_ids_list)
        friend_ids = set(friend_ids_list)

        print(
            f"\n=== Adjusting Reputations ===\n"
            f"Mode         : {ranking_mode.name}\n"
            f"Threshold    : {threshold}\n"
            f"Search Depth : {search_depth}\n"
            f"Players Found: {len(players)}\n"
        )

        log_lock = asyncio.Lock()
        sem = asyncio.Semaphore(self.update_concurrency)

        async def bounded(player: Player, action: ReputationValue, label: str):
            async with sem:
                await self._update_reputation_by_player_async(player, action, log_lock)
            return label

        tasks: list[asyncio.Task[str]] = []
        no_change = 0
        for p in players:
            rank_value = p.elo if is_elo_mode else p.rank_num
            pass_threshold = (
                rank_value >= threshold if is_elo_mode else rank_value <= threshold
            )

            if pass_threshold and p.player_id in downvoted_ids:
                tasks.append(
                    asyncio.create_task(bounded(p, ReputationValue.NEUTRAL, "neutral"))
                )
            elif (
                not pass_threshold
                and p.player_id not in downvoted_ids
                and p.player_id not in friend_ids
            ):
                tasks.append(
                    asyncio.create_task(
                        bounded(p, ReputationValue.DOWNVOTE, "downvoted")
                    )
                )
            else:
                await self._log(
                    f"No action: {p.player_name} (ID:{p.player_id}, Rank:{p.rank_num}, ELO:{p.elo})"
                )
                no_change += 1

        completed = 0
        set_to_neutral = 0
        downvoted = 0
        failed = 0
        total_tasks = len(tasks)

        for fut in asyncio.as_completed(tasks):
            try:
                label = await fut
                completed += 1
                if label == "neutral":
                    set_to_neutral += 1
                elif label == "downvoted":
                    downvoted += 1
                progress_bar(completed, total_tasks)
            except Exception as e:
                failed += 1
                print(f"\nError updating reputation: {e}")

        print("\nAll reputation updates completed.\n")
        print(f"Total considered : {len(players)}")
        print(f"Set to neutral   : {set_to_neutral}")
        print(f"Downvoted        : {downvoted}")
        print(f"No change        : {no_change}")
        print(f"Failed           : {failed}")

        await self._log("Reputation update summary:")
        await self._log(f"Total considered: {len(players)}")
        await self._log(f"Set to neutral: {set_to_neutral}")
        await self._log(f"Downvoted: {downvoted}")
        await self._log(f"No change: {no_change}")
        await self._log(f"Failed: {failed}")
