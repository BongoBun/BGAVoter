"""Command-line interface for BGA Voter."""

import argparse
import sys
import asyncio


from client import BGAVoter
from config import load_config, update_config_interactive, validate_config, CONFIG_FILE
from models import RankingMode
from utils import random_fun_fact


def interactive_menu(client: BGAVoter, config: dict) -> None:
    """
    Display an interactive menu for user to choose operations.

    Args:
        client: Initialized BGAVoter client
        config: Configuration dictionary
    """
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

        choice = input("\nEnter your choice (1-5): ").strip()

        if choice == "1":
            print("\n--- Resetting All Downvotes ---")
            asyncio.run(client.reset_all_downvotes_async(config["player_id"]))

        elif choice == "2":
            print("\n--- Adjusting Reputation (ELO Mode) ---")
            asyncio.run(
                client._adjust_reputation_async(
                    config["player_id"],
                    config["game_id"],
                    config["elo_safety_threshold"],
                    config["elo_search_depth"],
                    RankingMode.ELO,
                )
            )

        elif choice == "3":
            print("\n--- Adjusting Reputation (Arena Mode) ---")
            asyncio.run(
                client._adjust_reputation_async(
                    config["player_id"],
                    config["game_id"],
                    config["arena_safety_threshold"],
                    config["arena_search_depth"] + 1,
                    RankingMode.ARENA,
                )
            )

        elif choice == "4":
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


def main() -> None:
    """Main entry point with CLI argument support."""
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

    # Initialize client
    client = BGAVoter(config["cookies"], config["headers"])

    # Check if multiple arguments provided
    args_count = sum([args.reset, args.elo, args.arena])

    if args_count > 1:
        print("[ERROR] Please specify only one operation at a time.")
        parser.print_help()
        return

    # If no arguments provided, default to interactive mode
    if args_count == 0:
        interactive_menu(client, config)
        return

    # Execute based on argument
    if args.reset:
        print("\n--- Resetting All Downvotes ---")
        asyncio.run(client.reset_all_downvotes_async(config["player_id"]))

    elif args.elo:
        print("\n--- Adjusting Reputation (ELO Mode) ---")
        asyncio.run(
            client._adjust_reputation_async(
                config["player_id"],
                config["game_id"],
                config["elo_safety_threshold"],
                config["elo_search_depth"],
                RankingMode.ELO,
            )
        )

    elif args.arena:
        print("\n--- Adjusting Reputation (Arena Mode) ---")
        asyncio.run(
            client._adjust_reputation_async(
                config["player_id"],
                config["game_id"],
                config["arena_safety_threshold"],
                config["arena_search_depth"] + 1,
                RankingMode.ARENA,
            )
        )


if __name__ == "__main__":
    main()
