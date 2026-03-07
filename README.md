# Mao Card Game

A multiplayer Mao card game with CLI interface for LAN play.

## Overview

Mao is a card game where "The Only Rule i can Tell You Is This One". This provides a networked multiplayer experience with a command-line interface.

## Features

- **Multiplayer LAN support** - Play with any number of players on your local network
- **Variable decks** - Configure number of standard 52-card decks
- **Rich command system** - View cards, play, draw, knock, chat, throw, hit, give penalties
- **Point of Order** - Dispute resolution system with voting on penalties
- **Mao Declaration** - Win by playing all cards and declaring "Mao!"

## Installation

### Requirements

- Python 3.8+
- No external dependencies (uses standard library)

### Setup

```bash
# Clone or download the repository
cd mao_game
```

## Running the Game

### Start a Server

```bash
python3 server_main.py [--port PORT] [--decks N] [--players MIN]
```

Options:
- `--port` - Server port (default: 5555)
- `--decks` - Number of decks to use (default: 1)
- `--players` - Minimum players to start (default: 2)

### Start a Client

```bash
python3 client_main.py --host HOST [--port PORT] [--name NAME]
```

Options:
- `--host` - Server IP address (required)
- `--port` - Server port (default: 5555)
- `--name` - Your player name

## Game Commands

### Basic Commands

| Command | Alias | Description |
|---------|-------|-------------|
| `help` | `h`, `?` | Show available commands |
| `cards` | `c`, `hand` | View your cards |
| `play <card>` | `p` | Play a card (e.g., `play H7`, `play AS`) |
| `draw` | `d` | Draw a card from the deck |
| `knock` | `k` | Knock on the table |
| `say <message>` | `s` | Say something |
| `players` | `pl` | List all players |
| `quit` | `q` | Leave the game |

### Card Notation

Cards are specified as: `<Rank><Suit>` or `<Suit><Rank>`

- **Suits**: H (Hearts), D (Diamonds), C (Clubs), S (Spades)
- **Ranks**: 2-10, J, Q, K, A

Examples: `H7`, `AS`, `10D`, `KC`

### Advanced Commands

| Command | Description |
|---------|-------------|
| `throw <card> <player>` | Throw a card at another player |
| `hit <player>` | Hit another player |
| `penalty <player> [reason] [-r]` | Give penalty cards. Use `-r` to return their last played card |
| `mao` | Declare Mao (win with 10 second challenge window) |
| `cancel mao` | Cancel a Mao declaration |

### Point of Order Commands

During a Point of Order, gameplay is paused for dispute resolution:

| Command | Description |
|---------|-------------|
| `Point of Order` | Call a Point of Order (exact phrase) |
| `End Point of Order`  | End the Point of Order |
| `vote <#>` | Start a vote on penalty # |
| `uphold` | Vote to uphold the penalty |
| `overturn` | Vote to overturn the penalty |
| `abstain` | Abstain from voting |
| `shuffle [player]` | Shuffle a player's cards (or your own) |

<!-- ## Game Rules

### Basic Rules

1. Each player starts with 5 cards
2. Match the top card by rank or suit
3. If you can't play, draw a card
4. First to empty their hand wins (must declare "Mao!")

### Special Cards

| Card | Effect |
|------|--------|
| 5 | Skip next player |
| A | Reverse direction of play |
| Q | Play again (same player goes) |
| J | Suit race - player calls a new suit |
| 7 | "Have a nice day" - next player draws until they get a 7 |
| 10 | "Beatles" - everyone says specific phrases |
| K | Hit - physically hit another player |

Add all rules here...

### Penalties

Players can give penalties for rule violations:
- Drawing penalty cards
- Returning played cards
- Penalties can be disputed via Point of Order -->

## Configuration

Game rules are stored in `config/rules.json`. in future updates, you will be able to customize:
- Special card effects
- Speech rules
- Consecutive play rules
- Starting cards per player

Settings in `config/settings.py`:
- `DEFAULT_PORT` - Default server port
- `DEFAULT_CARDS_PER_PLAYER` - Starting hand size (default: 5)
- `MAO_CHALLENGE_TIME` - Seconds to challenge Mao (default: 10)
- `PENALTY_ACTION_DELAY` - Delay between penalty actions (default: 1 second)
- `RECENT_CARDS_SHOWN` - Recent cards shown normally (default: 3)
- `RECENT_CARDS_SHOWN_POO` - Recent cards shown during POO (default: 5)

## Testing

Run the test suite:

```bash
python3 -m unittest discover -s mao_game/tests -v
```

## Project Structure

```
mao_game/
├── client_main.py      # Client entry point
├── server_main.py      # Server entry point
├── core/
│   ├── card.py         # Card, Suit, Rank classes
│   ├── deck.py         # Deck management
│   ├── player.py       # Player class
│   └── game.py         # Game state management
├── network/
│   ├── protocol.py     # Message protocol
│   ├── server.py       # TCP server
│   └── client.py       # CLI client
├── config/
│   ├── settings.py     # Game settings
│   └── rules.json      # Game rules
├── ui/
│   └── display.py      # Console display
└── tests/              # Unit tests
```

## License

MIT License