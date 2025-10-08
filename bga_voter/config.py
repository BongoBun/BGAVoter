"""Configuration management for BGA Voter."""

import json
import os


CONFIG_FILE = "config.json"


def load_config() -> dict:
    """Load configuration from config.json"""
    if not os.path.exists(CONFIG_FILE):
        create_default_config()

    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def create_default_config() -> None:
    """Create a default config.json template"""
    default_config = {
        "player_id": 0,
        "game_id": 1741,
        "cookies": {},
        "headers": {},
        "elo_safety_threshold": 450,
        "elo_search_depth": 200,
        "arena_safety_threshold": 1000,
        "arena_search_depth": 4000,
    }

    with open(CONFIG_FILE, "w") as f:
        json.dump(default_config, f, indent=2)

    print(f"\n[INFO] Created default {CONFIG_FILE}")
    print(f"Please edit {CONFIG_FILE} with your credentials and settings.\n")


def save_config(config: dict) -> None:
    """Save configuration to config.json"""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def validate_config(config: dict) -> tuple[bool, list[str]]:
    """
    Validate that required configuration fields are set.

    Returns:
        tuple: (is_valid, list of missing fields)
    """
    missing_fields = []

    if config.get("player_id", 0) == 0:
        missing_fields.append("player_id")
    if config.get("game_id", 0) == 0:
        missing_fields.append("game_id")
    if not config.get("cookies") or config["cookies"] == {}:
        missing_fields.append("cookies")
    if not config.get("headers") or config["headers"] == {}:
        missing_fields.append("headers")

    return len(missing_fields) == 0, missing_fields


def update_config_interactive(config: dict) -> dict:
    """
    Update config values interactively.

    Args:
        config: Current configuration dictionary

    Returns:
        Updated configuration dictionary
    """
    print("\n" + "=" * 50)
    print("Update Configuration")
    print("=" * 50)
    print("Leave blank to keep current value\\n")

    # Game ID with popular games
    print("Popular BGA Games:")
    print("  1924 - Terraforming Mars")
    print("  1741 - Ark Nova")
    print("  1008 - 6 nimmt!")
    print("  1390 - Castles of Burgundy")
    print("  (Or enter any other game ID)")

    current = config.get("game_id", 1741)
    new_value = input(f"\nGame ID [{current}]: ").strip()
    if new_value:
        config["game_id"] = int(new_value)

    # ELO Safety Threshold
    current = config.get("elo_safety_threshold", 450)
    new_value = input(f"ELO Safety Threshold [{current}]: ").strip()
    if new_value:
        config["elo_safety_threshold"] = int(new_value)

    # ELO Search Depth
    current = config.get("elo_search_depth", 200)
    new_value = input(f"ELO Search Depth [{current}]: ").strip()
    if new_value:
        config["elo_search_depth"] = int(new_value)

    # Arena Safety Threshold
    current = config.get("arena_safety_threshold", 1000)
    new_value = input(f"Arena Safety Threshold [{current}]: ").strip()
    if new_value:
        config["arena_safety_threshold"] = int(new_value)

    # Arena Search Depth
    current = config.get("arena_search_depth", 4000)
    new_value = input(f"Arena Search Depth [{current}]: ").strip()
    if new_value:
        config["arena_search_depth"] = int(new_value)

    save_config(config)
    print("\n✓ Configuration updated and saved to config.json")
    print(
        "Note: Player ID, cookies, and headers must be edited manually in config.json"
    )

    return config
