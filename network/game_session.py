"""Game session for individual client connections."""

import socket
from typing import Optional
from dataclasses import dataclass

from .protocol import Message, Protocol


@dataclass
class GameSession:
    """
    Represents a single client's session on the server.

    Tracks connection state and handles message sending/receiving.
    """
    player_id: str
    socket: Optional[socket.socket] = None
    address: Optional[tuple] = None
    buffer: bytes = b""

    def set_socket(self, sock: socket.socket, address: tuple) -> None:
        """Set the socket for this session."""
        self.socket = sock
        self.address = address

    def send_message(self, message: Message) -> bool:
        """
        Send a message to this client.

        Args:
            message: The message to send.

        Returns:
            True if sent successfully, False on error.
        """
        if not self.socket:
            return False

        try:
            self.socket.sendall(Protocol.encode_message(message))
            return True
        except socket.error:
            return False

    def receive_message(self) -> Optional[Message]:
        """
        Receive a message from this client.

        Returns:
            A complete Message if available, None otherwise.
        """
        if not self.socket:
            return None

        try:
            data = self.socket.recv(4096)
            if not data:
                return None  # Connection closed

            self.buffer += data
            message, self.buffer = Protocol.decode_message(self.buffer)
            return message

        except socket.error:
            return None

    def close(self) -> None:
        """Close the socket connection."""
        if self.socket:
            try:
                self.socket.close()
            except socket.error:
                pass
            finally:
                self.socket = None
                self.buffer = b""

    def is_connected(self) -> bool:
        """Check if the session has an active connection."""
        return self.socket is not None