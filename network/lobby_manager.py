"""Lobby management for multi-game support."""

import json
import os
import random
import string
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False

from ..config.settings import MAX_LOBBIES, LOBBY_CODE_LENGTH


@dataclass
class Lobby:
    """A game lobby with its own game instance."""
    code: str
    name: str
    password_hash: str
    host_id: str
    host_name: str
    max_players: int = 10
    num_decks: int = 1
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    game: Optional[object] = None  # Will be Game instance
    clients: Dict[str, dict] = field(default_factory=dict)  # player_id -> {ws, name}
    phase: str = "waiting"  # waiting, in_progress, finished

    def to_dict(self) -> dict:
        """Serialize lobby info (without game state)."""
        return {
            "code": self.code,
            "name": self.name,
            "host_name": self.host_name,
            "player_count": len(self.clients),
            "max_players": self.max_players,
            "num_decks": self.num_decks,
            "has_password": bool(self.password_hash),
            "phase": self.phase,
            "created_at": self.created_at
        }


class LobbyManager:
    """Manages multiple game lobbies."""

    def __init__(self, data_dir: str = None):
        self.lobbies: Dict[str, Lobby] = {}
        self.data_file = self._get_data_file(data_dir)
        self._load_lobbies()

    def _get_data_file(self, data_dir: str = None) -> Path:
        """Get path to lobbies.json."""
        if data_dir:
            return Path(data_dir) / "lobbies.json"
        # Default to config directory
        return Path(__file__).parent.parent / "config" / "lobbies.json"

    def _load_lobbies(self):
        """Load lobbies from JSON file."""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    # Only load metadata, not game state
                    for code, lobby_data in data.get("lobbies", {}).items():
                        self.lobbies[code] = Lobby(
                            code=code,
                            name=lobby_data["name"],
                            password_hash=lobby_data["password_hash"],
                            host_id=lobby_data["host_id"],
                            host_name=lobby_data["host_name"],
                            max_players=lobby_data.get("max_players", 10),
                            num_decks=lobby_data.get("num_decks", 1),
                            created_at=lobby_data.get("created_at", datetime.now().isoformat())
                        )
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load lobbies file: {e}")

    def _save_lobbies(self):
        """Save lobbies to JSON file."""
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "lobbies": {
                code: {
                    "name": lobby.name,
                    "password_hash": lobby.password_hash,
                    "host_id": lobby.host_id,
                    "host_name": lobby.host_name,
                    "max_players": lobby.max_players,
                    "num_decks": lobby.num_decks,
                    "created_at": lobby.created_at
                }
                for code, lobby in self.lobbies.items()
            }
        }
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        if HAS_BCRYPT:
            return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        else:
            # Fallback for systems without bcrypt (development only)
            import hashlib
            return hashlib.sha256(password.encode('utf-8')).hexdigest()

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against its hash."""
        if HAS_BCRYPT:
            try:
                return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
            except Exception:
                return False
        else:
            # Fallback
            import hashlib
            return hashlib.sha256(password.encode('utf-8')).hexdigest() == password_hash

    def generate_code(self, length: int = LOBBY_CODE_LENGTH) -> str:
        """Generate a random lobby code."""
        chars = string.ascii_uppercase + string.digits
        code = ''.join(random.choice(chars) for _ in range(length))
        # Ensure uniqueness
        while code in self.lobbies:
            code = ''.join(random.choice(chars) for _ in range(length))
        return code

    def create_lobby(self, name: str, password: str, host_id: str, host_name: str,
                      max_players: int = 10, num_decks: int = 1) -> Optional[Lobby]:
        """Create a new lobby. Password is optional - empty string means no password."""
        if len(self.lobbies) >= MAX_LOBBIES:
            return None

        code = self.generate_code()
        # Only hash if password provided
        password_hash = self._hash_password(password) if password else ""

        lobby = Lobby(
            code=code,
            name=name,
            password_hash=password_hash,
            host_id=host_id,
            host_name=host_name,
            max_players=max_players,
            num_decks=num_decks
        )
        self.lobbies[code] = lobby
        self._save_lobbies()
        return lobby

    def get_lobby(self, code: str) -> Optional[Lobby]:
        """Get a lobby by code."""
        return self.lobbies.get(code.upper())

    def join_lobby(self, code: str, password: str, player_id: str, player_name: str, ws=None) -> tuple[Optional[Lobby], str]:
        """
        Join a lobby with password verification.
        Password is only required if the lobby has one set.

        Returns:
            (Lobby or None, error_message or None)
        """
        lobby = self.get_lobby(code)
        if not lobby:
            return None, "Lobby not found"

        # Only verify password if lobby has one
        if lobby.password_hash:
            if not self._verify_password(password, lobby.password_hash):
                return None, "Incorrect password"

        # Check if lobby is full
        if len(lobby.clients) >= lobby.max_players:
            return None, f"Lobby is full (max {lobby.max_players} players)"

        lobby.clients[player_id] = {"ws": ws, "name": player_name}
        return lobby, None

    def leave_lobby(self, code: str, player_id: str) -> bool:
        """Remove a player from a lobby."""
        lobby = self.get_lobby(code)
        if not lobby:
            return False

        if player_id in lobby.clients:
            del lobby.clients[player_id]

        # If host leaves, assign new host or delete lobby
        if player_id == lobby.host_id and lobby.clients:
            lobby.host_id = next(iter(lobby.clients.keys()))
            lobby.host_name = lobby.clients[lobby.host_id]["name"]

        # Delete empty lobbies
        if not lobby.clients:
            del self.lobbies[code]
            self._save_lobbies()

        return True

    def delete_lobby(self, code: str) -> bool:
        """Delete a lobby."""
        if code.upper() in self.lobbies:
            del self.lobbies[code.upper()]
            self._save_lobbies()
            return True
        return False

    def list_lobbies(self) -> List[dict]:
        """Get list of all lobbies (without sensitive data)."""
        return [lobby.to_dict() for lobby in self.lobbies.values()]

    def get_lobby_for_player(self, player_id: str) -> Optional[Lobby]:
        """Find which lobby a player is in."""
        for lobby in self.lobbies.values():
            if player_id in lobby.clients:
                return lobby
        return None