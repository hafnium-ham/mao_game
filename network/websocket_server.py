"""WebSocket game server for Mao card game with browser client support."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Dict, Optional, Set
from dataclasses import asdict

from aiohttp import web
import aiohttp

from .protocol import Message, MessageType
from .lobby_manager import LobbyManager, Lobby
from ..core.game import Game, GamePhase
from ..core.player import Player
from ..core.card import Card
from ..config.settings import MAO_CHALLENGE_TIME, MAX_PLAYERS_PER_LOBBY


class WebSocketGameServer:
    """
    Async WebSocket server for Mao game.

    Serves static files for browser client and handles WebSocket connections
    for real-time game communication.
    Supports multiple lobbies, each with their own game instance.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8080,
                 max_players: int = 10, num_decks: int = 1):
        self.host = host
        self.port = port
        self.max_players = max_players
        self.num_decks = num_decks

        # Multi-lobby support
        self.lobby_manager = LobbyManager()
        self.player_lobbies: Dict[str, str] = {}  # player_id -> lobby_code
        self.clients: Dict[str, dict] = {}  # player_id -> {websocket, name}
        self.player_names: Dict[str, str] = {}  # player_id -> name
        self.mao_timers: Dict[str, asyncio.TimerHandle] = {}  # lobby_code -> timer
        self.lock = asyncio.Lock()

        # Static files directory
        self.static_dir = Path(__file__).parent.parent / "static"

        # Message handlers
        self.message_handlers = {
            # Lobby management
            MessageType.LIST_LOBBIES: self._handle_list_lobbies,
            MessageType.CREATE_LOBBY: self._handle_create_lobby,
            MessageType.JOIN_LOBBY: self._handle_join_lobby,
            MessageType.LEAVE_LOBBY: self._handle_leave_lobby,
            # Connection
            MessageType.CONNECT: self._handle_connect,
            # Game actions
            MessageType.JOIN_GAME: self._handle_join,
            MessageType.LEAVE_GAME: self._handle_leave,
            MessageType.START_GAME: self._handle_start,
            MessageType.PLAY_CARD: self._handle_play_card,
            MessageType.DRAW_CARD: self._handle_draw_card,
            MessageType.KNOCK: self._handle_knock,
            MessageType.CHAT: self._handle_chat,
            MessageType.THROW_CARD: self._handle_throw,
            MessageType.HIT_PLAYER: self._handle_hit,
            MessageType.GIVE_PENALTY: self._handle_penalty,
            MessageType.RETURN_CARD: self._handle_return,
            MessageType.POINT_OF_ORDER: self._handle_poo,
            MessageType.END_POINT_OF_ORDER: self._handle_end_poo,
            MessageType.VOTE_PENALTY: self._handle_vote_penalty,
            MessageType.VOTE: self._handle_vote,
            MessageType.VIEW_PLAYERS: self._handle_view_players,
            MessageType.DECLARE_MAO: self._handle_declare_mao,
            MessageType.CANCEL_MAO: self._handle_cancel_mao,
            MessageType.SHUFFLE_CARDS: self._handle_shuffle_cards,
            MessageType.VIEW_HAND: self._handle_view_hand,
        }

        # aiohttp app
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self):
        """Set up aiohttp routes."""
        self.app.router.add_get('/', self._serve_index)
        self.app.router.add_get('/ws', self._websocket_handler)
        self.app.router.add_static('/static', self.static_dir)
        self.app.router.add_static('/cards', self.static_dir / 'cards')

    async def _serve_index(self, request: web.Request) -> web.Response:
        """Serve the main HTML page."""
        index_path = self.static_dir / 'index.html'
        if index_path.exists():
            return web.Response(
                text=index_path.read_text(),
                content_type='text/html'
            )
        return web.Response(text='Game client not found', status=404)

    async def _websocket_handler(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connections."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        player_id = str(uuid.uuid4())[:8]
        self.clients[player_id] = {'ws': ws, 'name': f'Player_{player_id[:4]}'}

        print(f"WebSocket connected: {player_id}")

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._process_message(player_id, msg.data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    print(f"WebSocket error: {ws.exception()}")
        finally:
            await self._disconnect_client(player_id)

        return ws

    async def _process_message(self, player_id: str, data: str):
        """Process incoming WebSocket message."""
        try:
            msg_data = json.loads(data)
            message = Message.from_json(data)
            message.player_id = player_id

            handler = self.message_handlers.get(message.type)
            if handler:
                await handler(message, player_id)
            else:
                await self._send_error(player_id, f"Unknown message type: {message.type}")
        except json.JSONDecodeError:
            await self._send_error(player_id, "Invalid JSON message")
        except Exception as e:
            print(f"Error processing message: {e}")
            import traceback
            traceback.print_exc()
            await self._send_error(player_id, f"Server error: {e}")

    # --- Message Handlers ---

    async def _handle_connect(self, message: Message, player_id: str):
        """Handle initial connection and name registration."""
        name = message.data.get("name", f"Player_{player_id[:4]}")

        async with self.lock:
            # Ensure unique name
            existing_names = [c['name'] for c in self.clients.values()]
            original_name = name
            counter = 1
            while name in existing_names:
                name = f"{original_name}_{counter}"
                counter += 1

            self.clients[player_id]['name'] = name
            self.player_names[player_id] = name

        await self._send_message(player_id, Message(
            type=MessageType.CONNECT,
            player_id=player_id,
            data={"player_id": player_id, "name": name}
        ))

        print(f"Player registered: {name} ({player_id})")

    # --- Lobby Handlers ---

    async def _handle_list_lobbies(self, message: Message, player_id: str):
        """Handle request to list available lobbies."""
        lobbies = self.lobby_manager.list_lobbies()
        await self._send_message(player_id, Message(
            type=MessageType.LOBBY_LIST,
            data={"lobbies": lobbies}
        ))

    async def _handle_create_lobby(self, message: Message, player_id: str):
        """Handle request to create a new lobby."""
        name = message.data.get("name", "Game")
        password = message.data.get("password", "")
        num_decks = message.data.get("num_decks", 1)
        max_players = message.data.get("max_players", 10)
        player_name = self.clients.get(player_id, {}).get('name', f'Player_{player_id[:4]}')

        lobby = self.lobby_manager.create_lobby(
            name=name,
            password=password,
            host_id=player_id,
            host_name=player_name,
            max_players=max_players,
            num_decks=num_decks
        )

        if lobby:
            # Auto-join the created lobby
            lobby.clients[player_id] = {"ws": self.clients[player_id]['ws'], "name": player_name}
            self.player_lobbies[player_id] = lobby.code

            # Create game and add player
            lobby.game = Game(num_decks=num_decks)
            player = Player(id=player_id, name=player_name)
            lobby.game.add_player(player)

            await self._send_message(player_id, Message(
                type=MessageType.LOBBY_CREATED,
                data={"code": lobby.code, "name": lobby.name, "max_players": max_players, "num_decks": num_decks}
            ))

            # Broadcast game state to lobby
            await self._broadcast_game_state(lobby)
            print(f"Lobby created: {lobby.code} by {player_name}")
        else:
            await self._send_error(player_id, "Could not create lobby (max lobbies reached)")

    async def _handle_join_lobby(self, message: Message, player_id: str):
        """Handle request to join a lobby."""
        code = message.data.get("code", "").upper()
        password = message.data.get("password", "")
        player_name = self.clients.get(player_id, {}).get('name', f'Player_{player_id[:4]}')
        ws = self.clients.get(player_id, {}).get('ws')

        lobby, error = self.lobby_manager.join_lobby(
            code=code,
            password=password,
            player_id=player_id,
            player_name=player_name,
            ws=ws
        )

        if lobby:
            self.player_lobbies[player_id] = lobby.code

            # Create game if needed using lobby's deck count
            if not lobby.game:
                lobby.game = Game(num_decks=lobby.num_decks)

            # Add player to lobby's game
            player = Player(id=player_id, name=player_name)
            lobby.game.add_player(player)

            await self._send_message(player_id, Message(
                type=MessageType.LOBBY_JOINED,
                data={
                    "code": lobby.code,
                    "name": lobby.name,
                    "player_count": len(lobby.clients),
                    "max_players": lobby.max_players,
                    "num_decks": lobby.num_decks
                }
            ))

            # Notify others in lobby
            await self._broadcast_to_lobby(lobby.code, Message(
                type=MessageType.NOTIFICATION,
                data={"message": f"{player_name} joined the lobby"}
            ), exclude={player_id})

            # Broadcast game state to all players in lobby
            await self._broadcast_game_state(lobby)

            print(f"Player {player_name} joined lobby {lobby.code}")
        else:
            await self._send_error(player_id, error or "Could not join lobby")

    async def _handle_leave_lobby(self, message: Message, player_id: str):
        """Handle request to leave current lobby."""
        lobby_code = self.player_lobbies.get(player_id)
        if not lobby_code:
            await self._send_error(player_id, "You are not in a lobby")
            return

        lobby = self.lobby_manager.get_lobby(lobby_code)
        player_name = self.clients.get(player_id, {}).get('name', player_id)

        if lobby and lobby.game:
            lobby.game.remove_player(player_id)

        self.lobby_manager.leave_lobby(lobby_code, player_id)
        del self.player_lobbies[player_id]

        await self._send_message(player_id, Message(
            type=MessageType.NOTIFICATION,
            data={"message": "Left lobby"}
        ))

        print(f"Player {player_name} left lobby {lobby_code}")

    def _get_player_lobby(self, player_id: str) -> Optional[Lobby]:
        """Get the lobby a player is currently in."""
        lobby_code = self.player_lobbies.get(player_id)
        if lobby_code:
            return self.lobby_manager.get_lobby(lobby_code)
        return None

    def _get_player_game(self, player_id: str) -> Optional[Game]:
        """Get the game for a player's lobby."""
        lobby = self._get_player_lobby(player_id)
        if lobby:
            return lobby.game
        return None

    async def _broadcast_to_lobby(self, lobby_code: str, message: Message, exclude: Optional[Set[str]] = None):
        """Send a message to all players in a specific lobby."""
        lobby = self.lobby_manager.get_lobby(lobby_code)
        if not lobby:
            return

        exclude = exclude or set()
        for player_id in lobby.clients:
            if player_id not in exclude:
                await self._send_message(player_id, message)

    # --- Game Handlers (modified for lobby support) ---

    async def _handle_join(self, message: Message, player_id: str):
        """Handle player joining the game (within their lobby)."""
        async with self.lock:
            lobby = self._get_player_lobby(player_id)
            if not lobby:
                await self._send_error(player_id, "You must join a lobby first")
                return

            if not lobby.game:
                lobby.game = Game(num_decks=self.num_decks)

            if lobby.game.phase != GamePhase.WAITING:
                await self._send_error(player_id, "Game already in progress")
                return

            if len(lobby.game.players) >= self.max_players:
                await self._send_error(player_id, "Game is full")
                return

            player = Player(id=player_id, name=self.clients[player_id]['name'])
            if lobby.game.add_player(player):
                player_name = self.clients[player_id]['name']
                print(f"Player {player_name} ({player_id}) added to game in lobby {lobby.code}. Total players: {len(lobby.game.players)}")

                await self._broadcast_to_lobby(lobby.code, Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": f"{player_name} joined the game"}
                ))
                await self._send_player_list(player_id, lobby)
                await self._broadcast_game_state(lobby)

                print(f"Player {player_name} joined lobby {lobby.code} ({len(lobby.game.players)}/{self.max_players})")
            else:
                print(f"Failed to add player to game")
                await self._send_error(player_id, "Could not join game")

    async def _handle_leave(self, message: Message, player_id: str):
        """Handle player leaving the game."""
        async with self.lock:
            lobby = self._get_player_lobby(player_id)
            if lobby and lobby.game and lobby.game.remove_player(player_id):
                name = self.player_names.get(player_id, player_id)
                await self._broadcast_to_lobby(lobby.code, Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": f"{name} left the game"}
                ))
                await self._broadcast_game_state(lobby)

    async def _handle_start(self, message: Message, player_id: str):
        """Handle request to start the game."""
        async with self.lock:
            lobby = self._get_player_lobby(player_id)
            if not lobby:
                await self._send_error(player_id, "You must be in a lobby")
                return

            if not lobby.game:
                print(f"Start game failed: no game instance")
                await self._send_error(player_id, "No game exists")
                return

            player_count = len(lobby.game.players)
            min_players = lobby.game.min_players
            print(f"Start game request: {player_count} players, need {min_players} minimum")

            if not lobby.game.can_start():
                await self._send_error(player_id,
                    f"Need at least {min_players} players to start. Currently have {player_count}.")
                return

            if lobby.game.start_game():
                lobby.phase = "in_progress"
                await self._broadcast_to_lobby(lobby.code, Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": "Game started!", "event_type": "game_start"}
                ))

                for player in lobby.game.players:
                    await self._send_hand_update(player.id, lobby.game)

                await self._broadcast_game_state(lobby)
                print(f"Game started in lobby {lobby.code} with {len(lobby.game.players)} players")
            else:
                await self._send_error(player_id, "Could not start game")

    async def _handle_play_card(self, message: Message, player_id: str):
        """Handle play card command."""
        async with self.lock:
            lobby = self._get_player_lobby(player_id)
            game = lobby.game if lobby else None
            if not game or game.phase != GamePhase.IN_PROGRESS:
                await self._send_error(player_id, "Game not in progress")
                return

            card_data = message.data.get("card")
            if not card_data:
                await self._send_error(player_id, "No card specified")
                return

            try:
                card = Card.from_dict(card_data)
            except (KeyError, ValueError) as e:
                await self._send_error(player_id, f"Invalid card: {e}")
                return

            player = game.get_player(player_id)
            if not player or not player.has_card(card):
                await self._send_error(player_id, "You don't have that card")
                return

            if game.play_card(player_id, card):
                await self._broadcast_to_lobby(lobby.code, Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": f"{player.name} played {card}", "event_type": "play"}
                ))

                await self._send_hand_update(player_id, game)

                if player.is_empty_hand():
                    await self._broadcast_to_lobby(lobby.code, Message(
                        type=MessageType.NOTIFICATION,
                        data={"message": f"{player.name} has played all cards!", "event_type": "win"}
                    ))

                game.advance_turn()
                await self._broadcast_game_state(lobby)
            else:
                await self._send_error(player_id, "Could not play card")

    async def _handle_draw_card(self, message: Message, player_id: str):
        """Handle draw card command."""
        async with self.lock:
            lobby = self._get_player_lobby(player_id)
            game = lobby.game if lobby else None
            if not game or game.phase != GamePhase.IN_PROGRESS:
                await self._send_error(player_id, "Game not in progress")
                return

            count = message.data.get("count", 1)
            player = game.get_player(player_id)
            if not player:
                await self._send_error(player_id, "Player not found")
                return

            cards = game.draw_card(player_id, count)

            if cards:
                await self._send_message(player_id, Message(
                    type=MessageType.CARD_DRAWN,
                    data={"cards": [c.to_dict() for c in cards]}
                ))

                await self._broadcast_to_lobby(lobby.code, Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": f"{player.name} drew {len(cards)} card(s)", "event_type": "draw"}
                ), exclude={player_id})

                await self._send_hand_update(player_id, game)
                await self._broadcast_game_state(lobby)

    async def _handle_knock(self, message: Message, player_id: str):
        """Handle knock on table."""
        async with self.lock:
            lobby = self._get_player_lobby(player_id)
            game = lobby.game if lobby else None
            if not game:
                return

            game.knock(player_id)
            name = self.player_names.get(player_id, player_id)

            await self._broadcast_to_lobby(lobby.code, Message(
                type=MessageType.NOTIFICATION,
                data={"message": f"{name} knocked on the table", "event_type": "knock"}
            ))

    async def _handle_chat(self, message: Message, player_id: str):
        """Handle chat/say command."""
        async with self.lock:
            lobby = self._get_player_lobby(player_id)
            game = lobby.game if lobby else None
            if not game:
                return

            chat_message = message.data.get("message", "")
            if chat_message:
                game.chat(player_id, chat_message)
                name = self.player_names.get(player_id, player_id)

                await self._broadcast_to_lobby(lobby.code, Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": f"{name}: {chat_message}", "event_type": "chat"}
                ))

    async def _handle_throw(self, message: Message, player_id: str):
        """Handle throw card at player."""
        async with self.lock:
            lobby = self._get_player_lobby(player_id)
            game = lobby.game if lobby else None
            if not game or game.phase != GamePhase.IN_PROGRESS:
                await self._send_error(player_id, "Game not in progress")
                return

            card_data = message.data.get("card")
            target_id = message.data.get("target_id")

            if not card_data or not target_id:
                await self._send_error(player_id, "Must specify card and target")
                return

            try:
                card = Card.from_dict(card_data)
            except (KeyError, ValueError) as e:
                await self._send_error(player_id, f"Invalid card: {e}")
                return

            if game.throw_card(player_id, card, target_id):
                player = game.get_player(player_id)
                target = game.get_player(target_id)

                await self._send_hand_update(player_id, game)
                await self._send_hand_update(target_id, game)

                await self._broadcast_to_lobby(lobby.code, Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": f"{player.name} threw {card} at {target.name}", "event_type": "throw"}
                ))

                await self._broadcast_game_state(lobby)
            else:
                await self._send_error(player_id, "Could not throw card")

    async def _handle_hit(self, message: Message, player_id: str):
        """Handle hit player action."""
        async with self.lock:
            lobby = self._get_player_lobby(player_id)
            game = lobby.game if lobby else None
            if not game:
                return

            target_id = message.data.get("target_id")
            if not target_id:
                await self._send_error(player_id, "Must specify target player")
                return

            player = game.get_player(player_id)
            target = game.get_player(target_id)

            if not player or not target:
                await self._send_error(player_id, "Player not found")
                return

            game.hit_player(player_id, target_id)

            await self._broadcast_to_lobby(lobby.code, Message(
                type=MessageType.NOTIFICATION,
                data={"message": f"{player.name} hit {target.name}", "event_type": "hit"}
            ))

    async def _handle_penalty(self, message: Message, player_id: str):
        """Handle give penalty command."""
        async with self.lock:
            lobby = self._get_player_lobby(player_id)
            game = lobby.game if lobby else None
            if not game or game.phase != GamePhase.IN_PROGRESS:
                await self._send_error(player_id, "Game not in progress")
                return

            target_id = message.data.get("target_id")
            reason = message.data.get("reason", "No reason given")
            cards = message.data.get("cards", 1)

            if not target_id:
                await self._send_error(player_id, "Must specify target player")
                return

            penalty = game.give_penalty(player_id, target_id, reason, cards)

            if penalty:
                caller = game.get_player(player_id)
                target = game.get_player(target_id)

                await self._broadcast_to_lobby(lobby.code, Message(
                    type=MessageType.NOTIFICATION,
                    data={
                        "message": f"{caller.name} gave {cards} penalty card(s) to {target.name}: {reason}",
                        "event_type": "penalty"
                    }
                ))

                # Send penalty details to target
                await self._send_message(target_id, Message(
                    type=MessageType.PENALTY,
                    data={"cards": cards, "reason": reason, "caller": caller.name}
                ))

                game.apply_penalty(penalty.id)

                # Handle return card if specified
                return_card = message.data.get("return_card", False)
                if return_card:
                    last_play = game.played_cards_stack[-1] if game.played_cards_stack else None
                    if last_play and last_play[0] == target_id:
                        result = game.return_card(player_id)
                        if result:
                            original_id, original_name, returned_card = result
                            await self._send_hand_update(original_id, game)
                            await self._broadcast_to_lobby(lobby.code, Message(
                                type=MessageType.NOTIFICATION,
                                data={"message": f"Card {returned_card} returned to {original_name}", "event_type": "return"}
                            ))

                # Cancel Mao declaration if penalty was given to declaring player
                if game.mao_declaring_player_id == target_id:
                    game.cancel_mao_declaration()
                    if lobby.code in self.mao_timers:
                        self.mao_timers[lobby.code].cancel()
                        del self.mao_timers[lobby.code]
                    await self._broadcast_to_lobby(lobby.code, Message(
                        type=MessageType.NOTIFICATION,
                        data={"message": f"{target.name}'s Mao declaration was challenged!", "event_type": "penalty"}
                    ))

                await self._broadcast_game_state(lobby)
            else:
                await self._send_error(player_id, "Could not give penalty")

    async def _handle_return(self, message: Message, player_id: str):
        """Handle return card command."""
        async with self.lock:
            lobby = self._get_player_lobby(player_id)
            game = lobby.game if lobby else None
            if not game or game.phase != GamePhase.IN_PROGRESS:
                await self._send_error(player_id, "Game not in progress")
                return

            result = game.return_card(player_id)

            if result:
                original_id, original_name, card = result
                await self._send_hand_update(original_id, game)
                await self._broadcast_to_lobby(lobby.code, Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": f"Card {card} returned to {original_name}", "event_type": "return"}
                ))
                await self._broadcast_game_state(lobby)
            else:
                await self._send_error(player_id, "No card to return")

    async def _handle_poo(self, message: Message, player_id: str):
        """Handle Point of Order command."""
        async with self.lock:
            lobby = self._get_player_lobby(player_id)
            game = lobby.game if lobby else None
            if not game:
                return

            if game.phase == GamePhase.POINT_OF_ORDER:
                await self._send_error(player_id, "Already in Point of Order")
                return

            if game.phase != GamePhase.IN_PROGRESS:
                await self._send_error(player_id, "Game not in progress")
                return

            reason = message.data.get("reason", "General dispute")
            caller_name = self.player_names.get(player_id, player_id)

            if game.initiate_point_of_order(caller_id=player_id, reason=reason):
                poo_data = game.point_of_order.to_dict()
                poo_data["logs"] = [log.to_dict() for log in game.get_recent_logs(20)]
                poo_data["penalty_history"] = [p.to_dict() for p in game.penalty_history]

                await self._broadcast_to_lobby(lobby.code, Message(
                    type=MessageType.POINT_OF_ORDER,
                    data=poo_data
                ))

                await self._broadcast_game_state(lobby)
                print(f"Point of Order called by {caller_name}: {reason}")
            else:
                await self._send_error(player_id, "Could not start Point of Order")

    async def _handle_end_poo(self, message: Message, player_id: str):
        """Handle end Point of Order command."""
        async with self.lock:
            lobby = self._get_player_lobby(player_id)
            game = lobby.game if lobby else None
            if not game or game.phase != GamePhase.POINT_OF_ORDER:
                await self._send_error(player_id, "Not in Point of Order")
                return

            caller_name = self.player_names.get(player_id, player_id)

            if game.end_point_of_order():
                await self._broadcast_to_lobby(lobby.code, Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": f"{caller_name} ended the Point of Order", "event_type": "poo_end"}
                ))
                await self._broadcast_game_state(lobby)
                print(f"Point of Order ended by {caller_name}")
            else:
                await self._send_error(player_id, "Could not end Point of Order")

    async def _handle_vote_penalty(self, message: Message, player_id: str):
        """Handle selecting a penalty to vote on during Point of Order."""
        async with self.lock:
            lobby = self._get_player_lobby(player_id)
            game = lobby.game if lobby else None
            if not game or game.phase != GamePhase.POINT_OF_ORDER:
                await self._send_error(player_id, "Not in Point of Order")
                return

            penalty_index = message.data.get("penalty_index")
            if penalty_index is None:
                await self._send_error(player_id, "Must specify penalty number")
                return

            active_vote = game.start_penalty_vote(penalty_index)

            if active_vote:
                penalty = active_vote.penalty

                await self._broadcast_to_lobby(lobby.code, Message(
                    type=MessageType.NOTIFICATION,
                    data={
                        "message": f"Vote started on penalty #{penalty_index + 1}: "
                                   f"{penalty.caller_name} → {penalty.target_name}: {penalty.reason}\n"
                                   f"  Type 'uphold', 'overturn', or 'abstain' to vote.",
                        "event_type": "vote_start"
                    }
                ))

                poo_data = game.point_of_order.to_dict()
                poo_data["logs"] = [log.to_dict() for log in game.get_recent_logs(20)]
                poo_data["penalty_history"] = [p.to_dict() for p in game.penalty_history]

                await self._broadcast_to_lobby(lobby.code, Message(
                    type=MessageType.POINT_OF_ORDER,
                    data=poo_data
                ))
            else:
                await self._send_error(player_id,
                    "Could not start vote. Either a vote is already active, "
                    "the penalty was already overturned, or invalid penalty number.")

    async def _handle_vote(self, message: Message, player_id: str):
        """Handle vote during Point of Order."""
        async with self.lock:
            lobby = self._get_player_lobby(player_id)
            game = lobby.game if lobby else None
            if not game or game.phase != GamePhase.POINT_OF_ORDER:
                await self._send_error(player_id, "Not in Point of Order")
                return

            if not game.point_of_order or not game.point_of_order.active_vote:
                await self._send_error(player_id, "No active vote. Use 'vote <penalty #>' to start a vote.")
                return

            vote = message.data.get("vote", "")
            if vote not in ("uphold", "overturn", "abstain"):
                await self._send_error(player_id, "Invalid vote. Use 'uphold', 'overturn', or 'abstain'.")
                return

            if game.add_vote(player_id, vote):
                voter_name = self.player_names.get(player_id, player_id)

                await self._broadcast_to_lobby(lobby.code, Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": f"{voter_name} voted to {vote}"}
                ))

                result = game.check_vote_result()
                if result is not None:
                    await self._resolve_penalty_vote(result, lobby)

    async def _resolve_penalty_vote(self, result: str, lobby: Lobby):
        """Resolve the current penalty vote during POO."""
        game = lobby.game
        resolution = game.resolve_penalty_vote(result)
        if not resolution:
            return

        penalty_info = resolution["penalty"]

        if result == "overturn":
            msg = (f"Penalty OVERTURNED: {penalty_info['caller_name']} wrongly penalized "
                   f"{penalty_info['target_name']}.")
            if resolution.get("caller_penalized"):
                msg += f" {penalty_info['caller_name']} draws {resolution.get('cards_missing', 0)} penalty card(s)."
            else:
                msg += f" {resolution.get('cards_moved', 0)} card(s) transferred to {penalty_info['caller_name']}."

            await self._send_hand_update(penalty_info["target_id"], game)
            await self._send_hand_update(penalty_info["caller_id"], game)
        else:
            msg = f"Penalty UPHELD: {penalty_info['target_name']}'s penalty stands."

        await self._broadcast_to_lobby(lobby.code, Message(
            type=MessageType.NOTIFICATION,
            data={"message": msg, "event_type": "vote_result"}
        ))

        if game.point_of_order:
            poo_data = game.point_of_order.to_dict()
            poo_data["logs"] = [log.to_dict() for log in game.get_recent_logs(20)]
            poo_data["penalty_history"] = [p.to_dict() for p in game.penalty_history]

            await self._broadcast_to_lobby(lobby.code, Message(
                type=MessageType.POINT_OF_ORDER,
                data=poo_data
            ))

        await self._broadcast_game_state(lobby)

    async def _handle_view_players(self, message: Message, player_id: str):
        """Handle request to view players."""
        lobby = self._get_player_lobby(player_id)
        await self._send_player_list(player_id, lobby)

    async def _handle_declare_mao(self, message: Message, player_id: str):
        """Handle player declaring Mao."""
        async with self.lock:
            lobby = self._get_player_lobby(player_id)
            game = lobby.game if lobby else None
            if not game or game.phase != GamePhase.IN_PROGRESS:
                await self._send_error(player_id, "Game not in progress")
                return

            player = game.get_player(player_id)
            if not player:
                await self._send_error(player_id, "Player not found")
                return

            if game.mao_declaring_player_id is not None:
                await self._send_error(player_id, "Someone is already declaring Mao!")
                return

            if game.start_mao_declaration(player_id):
                card_count = player.get_card_count()
                card_msg = f" with {card_count} card(s) remaining" if card_count > 0 else " with an empty hand"

                await self._broadcast_to_lobby(lobby.code, Message(
                    type=MessageType.NOTIFICATION,
                    data={
                        "message": f"🎯 {player.name} declares MAO{card_msg}! "
                                   f"Other players have 6 seconds to challenge...",
                        "event_type": "mao_declare"
                    }
                ))

                await self._broadcast_game_state(lobby)

                # Set async timer
                loop = asyncio.get_event_loop()
                self.mao_timers[lobby.code] = loop.call_later(MAO_CHALLENGE_TIME,
                    lambda: asyncio.create_task(self._mao_timer_expired(player_id, lobby.code)))

                print(f"{player.name} declared Mao - {MAO_CHALLENGE_TIME} second timer started")

    async def _mao_timer_expired(self, player_id: str, lobby_code: str):
        """Callback when Mao declaration timer expires."""
        async with self.lock:
            lobby = self.lobby_manager.get_lobby(lobby_code)
            if not lobby or not lobby.game:
                return
            game = lobby.game

            if game.mao_declaring_player_id != player_id:
                return

            player = game.get_player(player_id)
            if not player:
                game.cancel_mao_declaration()
                return

            game.cancel_mao_declaration()
            if lobby_code in self.mao_timers:
                del self.mao_timers[lobby_code]

            await self._broadcast_to_lobby(lobby_code, Message(
                type=MessageType.NOTIFICATION,
                data={"message": f"🎉 {player.name} declares MAO and WINS! 🎉", "event_type": "victory"}
            ))

            game.phase = GamePhase.FINISHED
            lobby.phase = "finished"

            await self._broadcast_to_lobby(lobby_code, Message(
                type=MessageType.GAME_OVER,
                data={
                    "winner_id": player_id,
                    "winner_name": player.name,
                    "card_count": player.get_card_count()
                }
            ))

            await self._broadcast_game_state(lobby)
            print(f"Game over! {player.name} won by declaring Mao!")

    async def _handle_cancel_mao(self, message: Message, player_id: str):
        """Handle canceling a Mao declaration."""
        async with self.lock:
            lobby = self._get_player_lobby(player_id)
            game = lobby.game if lobby else None
            if not game or game.mao_declaring_player_id is None:
                await self._send_error(player_id, "No Mao declaration in progress")
                return

            player = game.get_player(player_id)
            declaring_player = game.get_player(game.mao_declaring_player_id)
            player_name = player.name if player else player_id
            declarer_name = declaring_player.name if declaring_player else "Someone"

            game.cancel_mao_declaration()
            if lobby.code in self.mao_timers:
                self.mao_timers[lobby.code].cancel()
                del self.mao_timers[lobby.code]

            await self._broadcast_to_lobby(lobby.code, Message(
                type=MessageType.NOTIFICATION,
                data={"message": f"{player_name} canceled {declarer_name}'s Mao declaration", "event_type": "mao_declare"}
            ))
            await self._broadcast_game_state(lobby)

    async def _handle_shuffle_cards(self, message: Message, player_id: str):
        """Handle shuffle cards during Point of Order."""
        async with self.lock:
            lobby = self._get_player_lobby(player_id)
            game = lobby.game if lobby else None
            if not game or game.phase != GamePhase.POINT_OF_ORDER:
                await self._send_error(player_id, "Can only shuffle cards during Point of Order")
                return

            draw_count = game.draw_pile.remaining() if game.draw_pile else 0
            discard_count = len(game.discard_pile)

            if discard_count <= 1:
                await self._send_error(player_id, "Not enough cards in discard pile to shuffle")
                return

            shuffler_name = self.player_names.get(player_id, player_id)

            import random
            top_card = game.discard_pile[-1]
            cards_to_shuffle = game.discard_pile[:-1]

            if cards_to_shuffle:
                game.draw_pile.add_cards(cards_to_shuffle)
                game.draw_pile.shuffle()
                game.discard_pile = [top_card]

                await self._broadcast_to_lobby(lobby.code, Message(
                    type=MessageType.NOTIFICATION,
                    data={
                        "message": f"{shuffler_name} shuffled {len(cards_to_shuffle)} card(s) from discard into draw pile. Draw pile now has {game.draw_pile.remaining()} cards.",
                        "event_type": "poo_action"
                    }
                ))
                await self._broadcast_game_state(lobby)
            else:
                await self._send_error(player_id, "No cards to shuffle")

    async def _handle_view_hand(self, message: Message, player_id: str):
        """Handle view own hand during Point of Order."""
        async with self.lock:
            lobby = self._get_player_lobby(player_id)
            game = lobby.game if lobby else None
            if not game or game.phase != GamePhase.POINT_OF_ORDER:
                await self._send_error(player_id, "Can only view hand during Point of Order")
                return

            player = game.get_player(player_id)
            if not player:
                await self._send_error(player_id, "Player not found")
                return

            viewer_name = self.player_names.get(player_id, player_id)

            await self._send_message(player_id, Message(
                type=MessageType.HAND_UPDATE,
                data={"hand": [card.to_dict() for card in player.hand]}
            ))

            await self._broadcast_to_lobby(lobby.code, Message(
                type=MessageType.NOTIFICATION,
                data={"message": f"{viewer_name} looked at their hand", "event_type": "poo_action"}
            ))

    # --- Utility Methods ---

    async def _send_message(self, player_id: str, message: Message):
        """Send a message to a specific player."""
        client = self.clients.get(player_id)
        if client and client.get('ws'):
            ws = client['ws']
            try:
                await ws.send_str(message.to_json())
            except Exception as e:
                print(f"Error sending message to {player_id}: {e}")
                # Don't remove client here - let disconnect handler do it
        else:
            print(f"Warning: No websocket for player {player_id}")

    async def _send_error(self, player_id: str, error_message: str):
        """Send an error message to a player."""
        await self._send_message(player_id, Message(
            type=MessageType.ERROR,
            data={"message": error_message}
        ))

    async def _send_hand_update(self, player_id: str, game: Game):
        """Send hand update to a specific player."""
        if not game:
            return

        hand = game.get_player_hand(player_id)
        await self._send_message(player_id, Message(
            type=MessageType.HAND_UPDATE,
            data={"hand": [card.to_dict() for card in hand]}
        ))

    async def _send_player_list(self, player_id: str, lobby: Lobby):
        """Send the list of players to a client."""
        if not lobby or not lobby.game:
            return

        players_data = []
        for player in lobby.game.players:
            players_data.append({
                "id": player.id,
                "name": player.name,
                "card_count": player.get_card_count(),
                "is_connected": player.is_connected
            })

        await self._send_message(player_id, Message(
            type=MessageType.PLAYER_LIST,
            data={"players": players_data}
        ))

    async def _broadcast_game_state(self, lobby: Lobby):
        """Send current game state to all players in a lobby."""
        if not lobby or not lobby.game:
            return

        game = lobby.game
        player_count = len(game.players)
        client_count = len(lobby.clients)
        print(f"Broadcasting game state: {player_count} players in game, {client_count} connected clients in lobby {lobby.code}")

        for player_id in lobby.clients:
            state = game.to_dict(for_player_id=player_id)
            try:
                await self._send_message(player_id, Message(
                    type=MessageType.GAME_STATE,
                    player_id=player_id,
                    data=state
                ))
            except Exception as e:
                print(f"Failed to send game state to {player_id}: {e}")

    async def _disconnect_client(self, player_id: str):
        """Handle client disconnection."""
        async with self.lock:
            # Remove from lobby if in one
            lobby_code = self.player_lobbies.get(player_id)
            if lobby_code:
                lobby = self.lobby_manager.get_lobby(lobby_code)
                if lobby and lobby.game:
                    lobby.game.remove_player(player_id)
                self.lobby_manager.leave_lobby(lobby_code, player_id)
                del self.player_lobbies[player_id]

            if player_id in self.clients:
                del self.clients[player_id]

            if player_id in self.player_names:
                name = self.player_names.pop(player_id)
            else:
                name = player_id

            print(f"Player {name} ({player_id}) disconnected")

            # Notify others in the lobby
            lobby = self._get_player_lobby(player_id) if player_id in self.player_lobbies else None
            if lobby and lobby.game and lobby.game.players:
                await self._broadcast_to_lobby(lobby.code, Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": f"{name} disconnected"}
                ))
                await self._broadcast_game_state(lobby)

    def start(self):
        """Start the server."""
        web.run_app(self.app, host=self.host, port=self.port)


def main():
    """Run the WebSocket server from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Mao WebSocket Game Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    parser.add_argument("--decks", type=int, default=1, help="Number of card decks")
    parser.add_argument("--max-players", type=int, default=10, help="Maximum players")

    args = parser.parse_args()

    server = WebSocketGameServer(
        host=args.host,
        port=args.port,
        num_decks=args.decks,
        max_players=args.max_players
    )

    print(f"""
╔══════════════════════════════════════╗
║    MAO WEBSOCKET GAME SERVER          ║
║    http://{args.host}:{args.port}              ║
╚══════════════════════════════════════╝
    """)

    server.start()


if __name__ == "__main__":
    main()