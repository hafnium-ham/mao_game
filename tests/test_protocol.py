"""Tests for network protocol."""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mao_game.network.protocol import Message, MessageType, Protocol


class TestMessage(unittest.TestCase):
    """Test cases for Message class."""

    def test_message_creation(self):
        """Test creating a message."""
        msg = Message(
            type=MessageType.CHAT,
            player_id="p1",
            data={"message": "Hello"}
        )
        self.assertEqual(msg.type, MessageType.CHAT)
        self.assertEqual(msg.player_id, "p1")
        self.assertEqual(msg.data["message"], "Hello")

    def test_message_to_json(self):
        """Test message serialization."""
        msg = Message(
            type=MessageType.PLAY_CARD,
            player_id="p1",
            data={"card": {"suit": "hearts", "rank": "7"}}
        )
        json_str = msg.to_json()
        self.assertIn('"type": "play_card"', json_str)
        self.assertIn('"player_id": "p1"', json_str)

    def test_message_from_json(self):
        """Test message deserialization."""
        json_str = '{"type": "chat", "player_id": "p2", "data": {"message": "Hi"}}'
        msg = Message.from_json(json_str)

        self.assertEqual(msg.type, MessageType.CHAT)
        self.assertEqual(msg.player_id, "p2")
        self.assertEqual(msg.data["message"], "Hi")

    def test_message_invalid_json(self):
        """Test handling invalid JSON."""
        msg = Message.from_json("not valid json")
        self.assertEqual(msg.type, MessageType.ERROR)

    def test_message_invalid_type(self):
        """Test handling invalid message type."""
        json_str = '{"type": "invalid_type"}'
        msg = Message.from_json(json_str)
        self.assertEqual(msg.type, MessageType.ERROR)


class TestProtocol(unittest.TestCase):
    """Test cases for Protocol class."""

    def test_encode_message(self):
        """Test encoding a message."""
        msg = Message(type=MessageType.KNOCK, player_id="p1")
        encoded = Protocol.encode_message(msg)

        # Should have 4-byte header + JSON
        self.assertGreater(len(encoded), 4)

        # First 4 bytes should be length
        length = int.from_bytes(encoded[:4], byteorder="big")
        self.assertEqual(length, len(encoded) - 4)

    def test_decode_message(self):
        """Test decoding a message."""
        msg = Message(
            type=MessageType.DRAW_CARD,
            player_id="p1",
            data={"count": 2}
        )
        encoded = Protocol.encode_message(msg)

        decoded, remaining = Protocol.decode_message(encoded)
        self.assertEqual(decoded.type, MessageType.DRAW_CARD)
        self.assertEqual(decoded.player_id, "p1")
        self.assertEqual(decoded.data["count"], 2)
        self.assertEqual(len(remaining), 0)

    def test_decode_incomplete_message(self):
        """Test decoding incomplete message."""
        msg = Message(type=MessageType.CHAT, data={"message": "test"})
        encoded = Protocol.encode_message(msg)

        # Truncate the message
        incomplete = encoded[:10]

        decoded, remaining = Protocol.decode_message(incomplete)
        self.assertIsNone(decoded)
        self.assertEqual(len(remaining), 10)

    def test_decode_multiple_messages(self):
        """Test decoding multiple messages in buffer."""
        msg1 = Message(type=MessageType.KNOCK, player_id="p1")
        msg2 = Message(type=MessageType.CHAT, player_id="p2", data={"message": "Hi"})

        encoded = Protocol.encode_message(msg1) + Protocol.encode_message(msg2)

        # Decode first message
        decoded1, remaining1 = Protocol.decode_message(encoded)
        self.assertEqual(decoded1.type, MessageType.KNOCK)

        # Decode second message
        decoded2, remaining2 = Protocol.decode_message(remaining1)
        self.assertEqual(decoded2.type, MessageType.CHAT)
        self.assertEqual(len(remaining2), 0)


class TestMessageType(unittest.TestCase):
    """Test cases for MessageType enum."""

    def test_message_types_exist(self):
        """Test that all expected message types exist."""
        self.assertEqual(MessageType.CONNECT.value, "connect")
        self.assertEqual(MessageType.PLAY_CARD.value, "play_card")
        self.assertEqual(MessageType.DRAW_CARD.value, "draw_card")
        self.assertEqual(MessageType.POINT_OF_ORDER.value, "point_of_order")
        self.assertEqual(MessageType.VOTE.value, "vote")
        self.assertEqual(MessageType.DECLARE_MAO.value, "declare_mao")
        self.assertEqual(MessageType.CANCEL_MAO.value, "cancel_mao")


if __name__ == "__main__":
    unittest.main()