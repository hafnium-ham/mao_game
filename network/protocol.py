"""Network protocol for Mao game client-server communication."""

import json
from enum import Enum
from typing import Any, Dict, Optional, Tuple
from dataclasses import dataclass, field
import time


class MessageType(Enum):
    """Types of messages exchanged between client and server."""

    # Connection management
    CONNECT = "connect"           # Client connecting
    DISCONNECT = "disconnect"     # Client disconnecting
    PLAYER_LIST = "player_list"   # List of connected players
    UPDATE_AVATAR = "update_avatar"  # Update player avatar
    AVATAR_UPDATE = "avatar_update"  # Broadcast avatar update

    # Authentication
    LOGIN = "login"               # Login request
    REGISTER = "register"         # Register new account
    LOGIN_SUCCESS = "login_success"  # Login successful
    LOGOUT = "logout"             # Logout request

    # Lobby management
    LIST_LOBBIES = "list_lobbies"       # Request list of lobbies
    CREATE_LOBBY = "create_lobby"       # Create new lobby
    JOIN_LOBBY = "join_lobby"           # Join existing lobby
    LEAVE_LOBBY = "leave_lobby"         # Leave current lobby
    LOBBY_LIST = "lobby_list"           # Server response: list of lobbies
    LOBBY_CREATED = "lobby_created"     # Server response: lobby created
    LOBBY_JOINED = "lobby_joined"       # Server response: lobby joined
    LOBBY_ERROR = "lobby_error"         # Server response: lobby error

    # Game flow
    JOIN_GAME = "join_game"       # Request to join game
    LEAVE_GAME = "leave_game"     # Leave current game
    START_GAME = "start_game"     # Request to start game
    GAME_STATE = "game_state"     # Full game state update
    GAME_OVER = "game_over"       # Game ended notification

    # Player actions
    DRAW_CARD = "draw_card"       # Draw from deck
    PLAY_CARD = "play_card"       # Play a card
    KNOCK = "knock"               # Knock on table
    CHAT = "chat"                 # Say something
    THROW_CARD = "throw_card"     # Throw card at player
    HIT_PLAYER = "hit_player"     # Hit another player
    GIVE_PENALTY = "give_penalty" # Give penalty to player
    VIEW_PLAYERS = "view_players" # Request player list
    RETURN_CARD = "return_card"   # Return last played card
    DECLARE_MAO = "declare_mao"   # Declare Mao (victory)
    CANCEL_MAO = "cancel_mao"     # Cancel Mao declaration
    MAO_DECLARED = "mao_declared" # Broadcast when someone declares Mao

    # Point of Order
    POINT_OF_ORDER = "point_of_order"        # Call Point of Order
    END_POINT_OF_ORDER = "end_point_of_order"  # End Point of Order
    VOTE_PENALTY = "vote_penalty"            # Select a penalty to vote on during POO
    VOTE = "vote"                            # Vote uphold/overturn/abstain during POO
    SHUFFLE_CARDS = "shuffle_cards"          # Shuffle cards during POO
    VIEW_HAND = "view_hand"                  # View hand (notifies others during POO)

    # Server responses
    SUCCESS = "success"           # Action successful
    ERROR = "error"               # Error occurred
    NOTIFICATION = "notification" # General notification

    # Private updates (sent to specific player)
    HAND_UPDATE = "hand_update"   # Player's hand updated
    CARD_DRAWN = "card_drawn"     # Card drawn notification
    PENALTY = "penalty"           # Penalty received


@dataclass
class Message:
    """A message exchanged between client and server."""

    type: MessageType
    player_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None

    def to_json(self) -> str:
        """Serialize message to JSON string."""
        return json.dumps({
            "type": self.type.value,
            "player_id": self.player_id,
            "data": self.data,
            "timestamp": self.timestamp,
            "error": self.error
        })

    @classmethod
    def from_json(cls, json_str: str) -> "Message":
        """Deserialize message from JSON string."""
        try:
            data = json.loads(json_str)
            return cls(
                type=MessageType(data["type"]),
                player_id=data.get("player_id"),
                data=data.get("data", {}),
                timestamp=data.get("timestamp", time.time()),
                error=data.get("error")
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Return error message for invalid JSON
            return cls(
                type=MessageType.ERROR,
                error=f"Invalid message format: {e}"
            )


class Protocol:
    """
    Handles encoding and decoding of network messages.

    Messages are sent with a 4-byte header containing the message length,
    followed by the JSON-encoded message body.
    """

    HEADER_SIZE = 4  # 4 bytes for message length (max ~4GB messages)

    @staticmethod
    def encode_message(message: Message) -> bytes:
        """
        Encode a message for transmission.

        Args:
            message: The message to encode.

        Returns:
            Bytes ready to send over socket.
        """
        json_str = message.to_json()
        json_bytes = json_str.encode("utf-8")
        length = len(json_bytes)
        header = length.to_bytes(Protocol.HEADER_SIZE, byteorder="big")
        return header + json_bytes

    @staticmethod
    def decode_message(data: bytes) -> Tuple[Optional[Message], bytes]:
        """
        Decode a message from received bytes.

        Args:
            data: Bytes received from socket.

        Returns:
            Tuple of (Message or None if incomplete, remaining bytes).
        """
        if len(data) < Protocol.HEADER_SIZE:
            return None, data

        # Read header
        length = int.from_bytes(data[:Protocol.HEADER_SIZE], byteorder="big")

        # Check if we have the full message
        if len(data) < Protocol.HEADER_SIZE + length:
            return None, data

        # Extract and decode message
        json_bytes = data[Protocol.HEADER_SIZE:Protocol.HEADER_SIZE + length]
        remaining = data[Protocol.HEADER_SIZE + length:]

        try:
            message = Message.from_json(json_bytes.decode("utf-8"))
            return message, remaining
        except Exception:
            return None, remaining

    @staticmethod
    def create_error(error_code: str, message: str) -> Message:
        """Create an error message."""
        return Message(
            type=MessageType.ERROR,
            error=error_code,
            data={"message": message}
        )

    @staticmethod
    def create_notification(message: str, event_type: str = None) -> Message:
        """Create a notification message."""
        data = {"message": message}
        if event_type:
            data["event_type"] = event_type
        return Message(
            type=MessageType.NOTIFICATION,
            data=data
        )

    @staticmethod
    def create_success(message: str = "OK") -> Message:
        """Create a success message."""
        return Message(
            type=MessageType.SUCCESS,
            data={"message": message}
        )


# Convenience functions for creating specific message types

def msg_connect(name: str) -> Message:
    """Create connection request message."""
    return Message(type=MessageType.CONNECT, data={"name": name})


def msg_login(username: str, password: str) -> Message:
    """Create login request message."""
    return Message(type=MessageType.LOGIN, data={"username": username, "password": password})


def msg_register(username: str, password: str, display_name: str = None) -> Message:
    """Create register request message."""
    data = {"username": username, "password": password}
    if display_name:
        data["display_name"] = display_name
    return Message(type=MessageType.REGISTER, data=data)


def msg_join_game() -> Message:
    """Create join game request."""
    return Message(type=MessageType.JOIN_GAME)


def msg_start_game() -> Message:
    """Create start game request."""
    return Message(type=MessageType.START_GAME)


def msg_play_card(card: dict, face_up: bool = True) -> Message:
    """Create play card message."""
    return Message(
        type=MessageType.PLAY_CARD,
        data={"card": card, "face_up": face_up}
    )


def msg_draw_card(count: int = 1) -> Message:
    """Create draw card message."""
    return Message(type=MessageType.DRAW_CARD, data={"count": count})


def msg_knock() -> Message:
    """Create knock message."""
    return Message(type=MessageType.KNOCK)


def msg_chat(message: str) -> Message:
    """Create chat message."""
    return Message(type=MessageType.CHAT, data={"message": message})


def msg_throw_card(card: dict, target_id: str) -> Message:
    """Create throw card message."""
    return Message(
        type=MessageType.THROW_CARD,
        data={"card": card, "target_id": target_id}
    )


def msg_hit_player(target_id: str) -> Message:
    """Create hit player message."""
    return Message(type=MessageType.HIT_PLAYER, data={"target_id": target_id})


def msg_give_penalty(target_id: str, reason: str, cards: int = 1) -> Message:
    """Create give penalty message."""
    return Message(
        type=MessageType.GIVE_PENALTY,
        data={"target_id": target_id, "reason": reason, "cards": cards}
    )


def msg_return_card() -> Message:
    """Create return card message."""
    return Message(type=MessageType.RETURN_CARD)


def msg_point_of_order(reason: str, penalty_target_id: str = None,
                        penalty_caller_id: str = None) -> Message:
    """Create Point of Order message."""
    data = {"reason": reason}
    if penalty_target_id:
        data["penalty_target_id"] = penalty_target_id
    if penalty_caller_id:
        data["penalty_caller_id"] = penalty_caller_id
    return Message(type=MessageType.POINT_OF_ORDER, data=data)


def msg_vote(agree: bool) -> Message:
    """Create vote message."""
    return Message(type=MessageType.VOTE, data={"agree": agree})


def msg_hand_update(cards: list) -> Message:
    """Create hand update message."""
    return Message(type=MessageType.HAND_UPDATE, data={"hand": cards})


def msg_game_state(state: dict) -> Message:
    """Create game state message."""
    return Message(type=MessageType.GAME_STATE, data=state)


def msg_player_list(players: list) -> Message:
    """Create player list message."""
    return Message(type=MessageType.PLAYER_LIST, data={"players": players})