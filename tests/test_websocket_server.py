"""Tests for WebSocket game server."""

import unittest
import asyncio
import json
import sys
import os
import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiohttp import test_utils, web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from mao_game.network.websocket_server import WebSocketGameServer
from mao_game.network.protocol import Message, MessageType, msg_connect, msg_join_game, msg_start_game


class TestProtocol(unittest.TestCase):
    """Test cases for protocol message handling."""

    def test_message_serialization(self):
        """Test message to_json and from_json."""
        msg = Message(
            type=MessageType.PLAY_CARD,
            player_id="p1",
            data={"card": {"suit": "hearts", "rank": "5"}}
        )

        json_str = msg.to_json()
        parsed = Message.from_json(json_str)

        self.assertEqual(parsed.type, MessageType.PLAY_CARD)
        self.assertEqual(parsed.player_id, "p1")
        self.assertEqual(parsed.data["card"]["suit"], "hearts")

    def test_error_message_parsing(self):
        """Test parsing invalid JSON returns error message."""
        msg = Message.from_json("not valid json")
        self.assertEqual(msg.type, MessageType.ERROR)
        self.assertIn("Invalid", msg.error)

    def test_convenience_functions(self):
        """Test message creation convenience functions."""
        msg = msg_connect("Alice")
        self.assertEqual(msg.type, MessageType.CONNECT)
        self.assertEqual(msg.data["name"], "Alice")

        msg = msg_join_game()
        self.assertEqual(msg.type, MessageType.JOIN_GAME)

        msg = msg_start_game()
        self.assertEqual(msg.type, MessageType.START_GAME)


class TestWebSocketServer(AioHTTPTestCase):
    """Test cases for WebSocket game server."""

    async def get_application(self):
        """Create test application."""
        server = WebSocketGameServer(port=0)  # Random port for testing
        return server.app

    async def connect_client(self, name: str = "TestPlayer"):
        """Helper to connect a test client and register name."""
        ws = await self.client.ws_connect('/ws')
        # Send connect message
        connect_msg = Message(type=MessageType.CONNECT, data={"name": name}).to_json()
        await ws.send_str(connect_msg)
        # Receive response
        response = await ws.receive()
        data = json.loads(response.data)
        return ws, data.get("player_id"), data.get("data", {}).get("name", name)

    async def test_websocket_connection(self):
        """Test basic WebSocket connection."""
        ws = await self.client.ws_connect('/ws')
        self.assertIsNotNone(ws)
        await ws.close()

    async def test_connect_message(self):
        """Test player connection and name registration."""
        ws, player_id, name = await self.connect_client("Alice")
        self.assertIsNotNone(player_id)
        # Name should be in the data field
        self.assertEqual(name, "Alice")
        await ws.close()

    async def test_unique_player_names(self):
        """Test that duplicate names get unique suffixes."""
        ws1, id1, name1 = await self.connect_client("Bob")
        ws2, id2, name2 = await self.connect_client("Bob")

        self.assertIsNotNone(id1)
        self.assertIsNotNone(id2)
        self.assertNotEqual(id1, id2)
        # Second Bob should get a suffix
        self.assertTrue(name2.startswith("Bob"))

        await ws1.close()
        await ws2.close()

    async def test_join_game(self):
        """Test joining a game."""
        ws, player_id, name = await self.connect_client("Charlie")

        # Send join game
        join_msg = Message(type=MessageType.JOIN_GAME).to_json()
        await ws.send_str(join_msg)

        # Read responses until we get game_state
        for _ in range(5):
            response = await ws.receive()
            data = json.loads(response.data)
            if data.get("type") == "game_state":
                self.assertIn("players", data.get("data", {}))
                break

        await ws.close()

    async def test_start_game_requires_multiple_players(self):
        """Test that game can't start with one player."""
        ws, player_id, name = await self.connect_client("Solo")

        # Join game
        await ws.send_str(Message(type=MessageType.JOIN_GAME).to_json())

        # Read responses until we find an error or exhaust messages
        found_error = False
        for _ in range(5):
            response = await ws.receive()
            data = json.loads(response.data)
            if data.get("type") == "error":
                found_error = True
                break
            if data.get("type") == "player_list":
                # Wait for player list, then try to start
                await ws.send_str(Message(type=MessageType.START_GAME).to_json())

        self.assertTrue(found_error, "Expected error when starting game with one player")
        await ws.close()

    async def test_full_game_flow(self):
        """Test complete game flow with two players."""
        # Connect two players
        ws1, id1, name1 = await self.connect_client("Player1")
        ws2, id2, name2 = await self.connect_client("Player2")

        # Both join
        await ws1.send_str(Message(type=MessageType.JOIN_GAME).to_json())
        await ws2.send_str(Message(type=MessageType.JOIN_GAME).to_json())

        # Consume join notifications
        responses1 = []
        responses2 = []
        for _ in range(3):
            try:
                r = await asyncio.wait_for(ws1.receive(), timeout=2)
                responses1.append(json.loads(r.data))
            except asyncio.TimeoutError:
                pass
            try:
                r = await asyncio.wait_for(ws2.receive(), timeout=2)
                responses2.append(json.loads(r.data))
            except asyncio.TimeoutError:
                pass

        # Start game
        await ws1.send_str(Message(type=MessageType.START_GAME).to_json())

        # Consume start notifications and hand updates
        for _ in range(5):
            try:
                r = await asyncio.wait_for(ws1.receive(), timeout=2)
            except asyncio.TimeoutError:
                pass
            try:
                r = await asyncio.wait_for(ws2.receive(), timeout=2)
            except asyncio.TimeoutError:
                pass

        # Both players should have hands - draw a card
        await ws1.send_str(Message(type=MessageType.DRAW_CARD).to_json())

        response = await asyncio.wait_for(ws1.receive(), timeout=2)
        data = json.loads(response.data)
        self.assertIn(data["type"], ["card_drawn", "hand_update", "notification", "game_state"])

        await ws1.close()
        await ws2.close()

    async def test_knock(self):
        """Test knock functionality."""
        ws1, id1, _ = await self.connect_client("Knocker")
        ws2, id2, _ = await self.connect_client("Listener")

        # Join and start game
        await ws1.send_str(Message(type=MessageType.JOIN_GAME).to_json())
        await ws2.send_str(Message(type=MessageType.JOIN_GAME).to_json())

        # Consume join responses
        for _ in range(3):
            try:
                await asyncio.wait_for(ws1.receive(), timeout=1)
            except asyncio.TimeoutError:
                pass
            try:
                await asyncio.wait_for(ws2.receive(), timeout=1)
            except asyncio.TimeoutError:
                pass

        await ws1.send_str(Message(type=MessageType.START_GAME).to_json())

        # Consume start messages
        for _ in range(8):
            try:
                await asyncio.wait_for(ws1.receive(), timeout=1)
            except asyncio.TimeoutError:
                pass
            try:
                await asyncio.wait_for(ws2.receive(), timeout=1)
            except asyncio.TimeoutError:
                pass

        # Knock
        await ws1.send_str(Message(type=MessageType.KNOCK).to_json())

        # Read response - find notification with "knocked"
        for _ in range(5):
            response = await asyncio.wait_for(ws1.receive(), timeout=2)
            data = json.loads(response.data)
            if data.get("type") == "notification" and "knocked" in data.get("data", {}).get("message", "").lower():
                break

        self.assertEqual(data["type"], "notification")
        self.assertIn("knocked", data["data"]["message"].lower())

        await ws1.close()
        await ws2.close()

    async def test_point_of_order(self):
        """Test Point of Order functionality."""
        ws1, id1, _ = await self.connect_client("Disputer")
        ws2, id2, _ = await self.connect_client("Agreeable")

        # Setup game
        await ws1.send_str(Message(type=MessageType.JOIN_GAME).to_json())
        await ws2.send_str(Message(type=MessageType.JOIN_GAME).to_json())

        # Consume join responses
        for _ in range(3):
            try:
                await asyncio.wait_for(ws1.receive(), timeout=1)
            except asyncio.TimeoutError:
                pass
            try:
                await asyncio.wait_for(ws2.receive(), timeout=1)
            except asyncio.TimeoutError:
                pass

        await ws1.send_str(Message(type=MessageType.START_GAME).to_json())

        # Consume start messages
        for _ in range(8):
            try:
                await asyncio.wait_for(ws1.receive(), timeout=1)
            except asyncio.TimeoutError:
                pass
            try:
                await asyncio.wait_for(ws2.receive(), timeout=1)
            except asyncio.TimeoutError:
                pass

        # Call Point of Order
        await ws1.send_str(Message(
            type=MessageType.POINT_OF_ORDER,
            data={"reason": "Testing POO"}
        ).to_json())

        # Read response - find point_of_order message
        for _ in range(5):
            response = await asyncio.wait_for(ws1.receive(), timeout=2)
            data = json.loads(response.data)
            if data.get("type") == "point_of_order":
                break

        self.assertEqual(data.get("type"), "point_of_order")

        # End Point of Order
        await ws1.send_str(Message(type=MessageType.END_POINT_OF_ORDER).to_json())

        # Find notification about ending POO
        for _ in range(5):
            response = await asyncio.wait_for(ws1.receive(), timeout=2)
            data = json.loads(response.data)
            if data.get("type") == "notification":
                break

        self.assertEqual(data.get("type"), "notification")

        await ws1.close()
        await ws2.close()


if __name__ == "__main__":
    unittest.main()