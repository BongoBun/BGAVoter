"""Command-line interface for BGA Voter."""

import argparse
import sys
import asyncio

from bga_voter.client import BGAVoter
from bga_voter.config import (
    load_config,
    update_config_interactive,
    validate_config,
    CONFIG_FILE,
)
from bga_voter.models import RankingMode
from bga_voter.logger import AsyncLogger, LOGFILE as BGA_LOGFILE
from bga_voter.utils import random_fun_fact


async def interactive_menu_async(client: BGAVoter, config: dict) -> None:
    """Async interactive menu that reuses a single event loop."""

    async def async_input(prompt: str) -> str:
        return await asyncio.to_thread(input, prompt)

    while True:
        print("\n" + "=" * 50)
        print("BGA Voter - Interactive Menu")
        print("=" * 50)
        print("1. Reset all downvotes")
        print("2. Adjust reputation (ELO mode)")
        print("3. Adjust reputation (Arena mode)")
        print("4. Update configuration")
        print("5. Exit")
        print("=" * 50)

        choice = (await async_input("\nEnter your choice (1-5): ")).strip()

        if choice == "1":
            print("\n--- Resetting All Downvotes ---")
            await client.reset_all_downvotes_async(config["player_id"])

        elif choice == "2":
            print("\n--- Adjusting Reputation (ELO Mode) ---")
            await client._adjust_reputation_async(
                config["player_id"],
                config["game_id"],
                config["elo_safety_threshold"],
                config["elo_search_depth"],
                RankingMode.ELO,
            )

        elif choice == "3":
            print("\n--- Adjusting Reputation (Arena Mode) ---")
            await client._adjust_reputation_async(
                config["player_id"],
                config["game_id"],
                config["arena_safety_threshold"],
                config["arena_search_depth"] + 1,
                RankingMode.ARENA,
            )

        elif choice == "4":
            # Runs synchronously; small I/O so acceptable. If desired wrap in to_thread.
            config = update_config_interactive(config)

        elif choice == "5":
            filename = (
                "terraforming_mars_fun_facts.txt"
                if config["game_id"] == 1924
                else "ark_nova_fun_facts.txt"
            )
            random_fun_fact(filename)
            print("Exiting... Goodbye!\n")
            break

        else:
            print("\n[ERROR] Invalid choice. Please enter a number between 1-5.")


async def main_async() -> None:
    """Async main entry point with single event loop."""
    parser = argparse.ArgumentParser(
        description="BGA Voter - Manage player reputations on Board Game Arena"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset all downvotes to neutral",
    )
    parser.add_argument(
        "--elo",
        action="store_true",
        help="Adjust reputation using ELO mode",
    )
    parser.add_argument(
        "--arena",
        action="store_true",
        help="Adjust reputation using Arena mode",
    )

    args = parser.parse_args()

    # Load and validate configuration
    config = load_config()
    is_valid, missing_fields = validate_config(config)

    if not is_valid:
        print("\n[ERROR] Configuration incomplete!")
        print(f"Missing or empty fields: {', '.join(missing_fields)}")
        print(f"Please edit {CONFIG_FILE} with your credentials and settings.\n")
        sys.exit(0)

    # Check if multiple arguments provided
    args_count = sum([args.reset, args.elo, args.arena])

    if args_count > 1:
        print("[ERROR] Please specify only one operation at a time.")
        parser.print_help()
        return

    async with BGAVoter(
        config["cookies"], config["headers"], logger=AsyncLogger(BGA_LOGFILE)
    ) as client:
        # Interactive mode
        if args_count == 0:
            await interactive_menu_async(client, config)
            return

        if args.reset:
            print("\n--- Resetting All Downvotes ---")
            await client.reset_all_downvotes_async(config["player_id"])
        elif args.elo:
            print("\n--- Adjusting Reputation (ELO Mode) ---")
            await client._adjust_reputation_async(
                config["player_id"],
                config["game_id"],
                config["elo_safety_threshold"],
                config["elo_search_depth"],
                RankingMode.ELO,
            )
        elif args.arena:
            print("\n--- Adjusting Reputation (Arena Mode) ---")
            await client._adjust_reputation_async(
                config["player_id"],
                config["game_id"],
                config["arena_safety_threshold"],
                config["arena_search_depth"] + 1,
                RankingMode.ARENA,
            )


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
