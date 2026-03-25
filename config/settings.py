"""Game settings and constants for Mao."""

# Game settings
DEFAULT_PORT = 5555
DEFAULT_HOST = "0.0.0.0"
DEFAULT_DECKS = 1
DEFAULT_MAX_PLAYERS = 10
DEFAULT_MIN_PLAYERS = 2
DEFAULT_CARDS_PER_PLAYER = 5  # As per rules

# Lobby settings
MAX_LOBBIES = 20
LOBBY_CODE_LENGTH = 6
MAX_PLAYERS_PER_LOBBY = 10
RATE_LIMIT_CONNECTIONS = 5  # per minute per IP
RATE_LIMIT_WINDOW = 60  # seconds

# WebSocket settings
WS_PORT = 8080

# Network settings
SOCKET_TIMEOUT = 10
RECV_BUFFER_SIZE = 4096
MESSAGE_HEADER_SIZE = 4

# Mao declaration settings
MAO_CHALLENGE_TIME = 10  # seconds for others to challenge Mao declaration

# Point of Order settings
POO_TIME_LIMIT = 60  # seconds (no longer used - POO has no time limit)
POO_REQUIRED_MAJORITY = 0.5  # 50% + 1 to overturn

# Penalty settings
PENALTY_ACTION_DELAY = 1.0  # seconds between penalty actions

# Logging settings
MAX_LOG_ENTRIES = 100
RECENT_CARDS_SHOWN = 3  # cards shown in normal play
RECENT_CARDS_SHOWN_POO = 5  # cards shown during Point of Order

# Card display
SUIT_SYMBOLS = {
    "hearts": "♥",
    "diamonds": "♦",
    "clubs": "♣",
    "spades": "♠",
}

SUIT_COLORS = {
    "hearts": "red",
    "diamonds": "red",
    "clubs": "black",
    "spades": "black",
}

RANK_VALUES = {
    "A": 14,  # Ace high
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
}
'''
Rules:
 players start with 5 cards. playing a 5 ships the next player. playing an ace causes the order to reverse. playing a 7 requires the player to say have a (very * the number of 7's played consecutively before this) nice day, playing a 10 requires you to name a member of the beatles, playing a jack means any player may name a suit, the first one is what the suit changes to. a jack cannot be played on a jack. a queen allows you to play again, a king requires you to hit another player, 3 cards played consecutively of the same value require the 3rd player to throw a card at another player(the player it is thrown at muct take it. if the 3 cards are 6's evil card must be announced) each player that continues to play the same value must also throw a card at any player. if a card's suit is spades the player must say (value) of spades, if it is an ace of spades they must sing"flying swooping ace of spades, doo dah doo dah" and all other players must sing "doo dah doo dah", if the card's value is hearts the player that played the card must knock. if a player is on their last card they must announce it. after a player playes their last card they must say "Mao" to win, if they say "Mao" any other time it is a penalty. if they curse any time it is a penaly. to play a card must match suit or rank(excluding jacks), and on your turn you can either draw 1 card or play 1 card. during a point of order you may not touch your cards, you may not say "Point of Order" except in "end Point of Order"

'''