# BGA Voter

A Python tool for managing player reputations on [Board Game Arena](https://boardgamearena.com/). This tool helps you automatically adjust player reputations based on ELO ratings or Arena rankings.

## Features

- **Automated Reputation Management**: Downvote players below your skill threshold and remove downvotes from those above
- **Dual Ranking Modes**: Support for both ELO and Arena ranking systems
- **Friend Protection**: Automatically excludes friends from downvoting
- **Interactive CLI**: User-friendly command-line interface with progress tracking
- **Detailed Logging**: All reputation changes are logged to `bga_voter.log`

## Installation

### Prerequisites

- Python 3.11 or higher
- pip

### Setup

1. Clone the repository:
```bash
git clone <repo>
cd <repo_folder_name>
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the tool to generate a default config:
```bash
python bga_voter/bgavoter.py
```

4. Edit `config.json` with your settings and credentials:
```json
{
  "player_id": 0,
  "game_id": 0,
  "cookies": {
  },
  "headers": {
  },
  "elo_safety_threshold": 450,
  "elo_search_depth": 200,
  "arena_safety_threshold": 1000,
  "arena_search_depth": 4000
}
```

### Getting Your Credentials

1. **Player ID**: Visit your profile on BGA and extract the ID from the URL
2. **Cookies & Headers**: Use browser developer tools (F12) to inspect network requests to BGA and copy the necessary authentication data
    1. Open BGA in your browser and log in
    2. Open developer tools (F12) and go to the "Network" tab
    3. Go to someone's page and downvote them
    4. Click on the request that starts with `changeReputation.html`
    5. Right click on the request and select "Copy" -> "Copy as cURL"
    6. Use an online tool like curlconverter.com to convert the cURL command to JSON
    7. Extract the `cookies` and `headers` fields from the JSON and paste them into your `config.json`

## Usage

### Interactive Mode (Recommended)

Simply run the tool without arguments:

```bash
python bga_voter/bgavoter.py
```

This will launch an interactive menu where you can:
1. Reset all downvotes
2. Adjust reputation (ELO mode)
3. Adjust reputation (Arena mode)
4. Update configuration
5. Exit

### Command Line Arguments

```bash
# Reset all downvotes to neutral
python bga_voter/bgavoter.py --reset

# Adjust reputations using ELO mode
python bga_voter/bgavoter.py --elo

# Adjust reputations using Arena mode
python bga_voter/bgavoter.py --arena
```

## Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `player_id` | Your BGA player ID | 0 (must set) |
| `game_id` | Game ID to manage (e.g., 1741 for Ark Nova) | 1741 |
| `cookies` | Authentication cookies | {} (must set) |
| `headers` | HTTP headers for requests | {} (must set) |
| `elo_safety_threshold` | ELO threshold - downvote players below this | 450 |
| `elo_search_depth` | How far to search in ELO rankings | 200 |
| `arena_safety_threshold` | Arena rank threshold - downvote players greater than this rank number | 1000 |
| `arena_search_depth` | How far to search in Arena rankings | 4000 |

## How It Works

### ELO Mode
- Fetches players above the `elo_search_depth` threshold
- Downvotes players with ELO below `elo_safety_threshold`
- Removes downvotes from players with ELO above `elo_safety_threshold`
- Never downvotes friends

### Arena Mode
- Fetches players above the `arena_search_depth` rank
- Downvotes players ranked worse than `arena_safety_threshold` (higher rank number)
- Removes downvotes from players ranked better than `arena_safety_threshold` (lower rank number)
- Never downvotes friends
