"""Game server for Mao card game."""

import socket
import threading
import uuid
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
import sys
import time

from .protocol import Message, MessageType, Protocol
from .game_session import GameSession
from core.game import Game, GamePhase
from core.player import Player
from core.card import Card
from config.settings import MAO_CHALLENGE_TIME, PENALTY_ACTION_DELAY, RECENT_CARDS_SHOWN, RECENT_CARDS_SHOWN_POO


@dataclass
class ConnectedClient:
    """Represents a connected client."""
    socket: socket.socket
    address: tuple
    player_id: str
    player_name: str
    session: GameSession


class GameServer:
    """
    Game server for Mao.

    Handles client connections, message routing, and game state management.
    Uses threading for concurrent client handling.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 5555,
                 max_players: int = 10, num_decks: int = 1):
        self.host = host
        self.port = port
        self.max_players = max_players
        self.num_decks = num_decks

        self.server_socket: Optional[socket.socket] = None
        self.clients: Dict[str, ConnectedClient] = {}
        self.game: Optional[Game] = None

        self.running = False
        self.lock = threading.RLock()

        # Mao declaration timer
        self.mao_timer: Optional[threading.Timer] = None

        # Message handlers mapped by MessageType
        self.message_handlers = {
            MessageType.CONNECT: self._handle_connect,
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

    # --- Server Lifecycle ---

    def start(self) -> None:
        """Start the game server."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(self.max_players)

        self.running = True
        self.game = Game(num_decks=self.num_decks)

        print(f"Mao Game Server started on {self.host}:{self.port}")
        print(f"Max players: {self.max_players}, Decks: {self.num_decks}")
        print("Press Ctrl+C to stop the server")

        # Start accept thread
        accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
        accept_thread.start()

        # Main server loop
        try:
            while self.running:
                threading.Event().wait(0.1)
        except KeyboardInterrupt:
            print("\nShutting down server...")
            self.stop()

    def stop(self) -> None:
        """Stop the server."""
        self.running = False

        if self.mao_timer:
            self.mao_timer.cancel()

        for client in list(self.clients.values()):
            try:
                client.socket.close()
            except socket.error:
                pass

        if self.server_socket:
            try:
                self.server_socket.close()
            except socket.error:
                pass

        print("Server stopped")

    # --- Connection Handling ---

    def _accept_connections(self) -> None:
        """Accept incoming client connections."""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                player_id = str(uuid.uuid4())[:8]

                print(f"Connection from {address}, assigned ID: {player_id}")

                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address, player_id),
                    daemon=True
                )
                client_thread.start()

            except socket.error as e:
                if self.running:
                    print(f"Error accepting connection: {e}")

    def _handle_client(self, client_socket: socket.socket, address: tuple,
                       player_id: str) -> None:
        """Handle individual client connection."""
        buffer = b""

        try:
            while self.running:
                data = client_socket.recv(4096)
                if not data:
                    break

                buffer += data

                while len(buffer) >= Protocol.HEADER_SIZE:
                    message, buffer = Protocol.decode_message(buffer)
                    if message:
                        message.player_id = player_id
                        self._process_message(message, client_socket, player_id)
                    else:
                        break

        except ConnectionResetError:
            pass
        except socket.error as e:
            if self.running:
                print(f"Socket error for {player_id}: {e}")
        finally:
            self._disconnect_client(player_id)

    def _process_message(self, message: Message, client_socket: socket.socket,
                         player_id: str) -> None:
        """Route message to appropriate handler."""
        handler = self.message_handlers.get(message.type)
        if handler:
            try:
                handler(message, client_socket, player_id)
            except Exception as e:
                print(f"Error handling {message.type}: {e}")
                import traceback
                traceback.print_exc()
                self._send_error(client_socket, f"Server error: {e}")
        else:
            self._send_error(client_socket, f"Unknown message type: {message.type}")

    def _disconnect_client(self, player_id: str) -> None:
        """Handle client disconnection."""
        with self.lock:
            if player_id in self.clients:
                client = self.clients.pop(player_id)
                try:
                    client.socket.close()
                except socket.error:
                    pass

                if self.game:
                    self.game.remove_player(player_id)

                print(f"Player {client.player_name} ({player_id}) disconnected")

                if self.game and self.game.players:
                    self._broadcast(Message(
                        type=MessageType.NOTIFICATION,
                        data={"message": f"{client.player_name} disconnected"}
                    ))
                    self._broadcast_game_state()

    # --- Message Handlers ---

    def _handle_connect(self, message: Message, client_socket: socket.socket,
                        player_id: str) -> None:
        """Handle initial connection and name registration."""
        name = message.data.get("name", f"Player_{player_id[:4]}")

        with self.lock:
            existing_names = [c.player_name for c in self.clients.values()]
            original_name = name
            counter = 1
            while name in existing_names:
                name = f"{original_name}_{counter}"
                counter += 1

            client = ConnectedClient(
                socket=client_socket,
                address=("", 0),  # Will be updated
                player_id=player_id,
                player_name=name,
                session=GameSession(player_id)
            )
            client.session.set_socket(client_socket, ("", 0))
            self.clients[player_id] = client

        self._send_message(client_socket, Message(
            type=MessageType.CONNECT,
            player_id=player_id,
            data={"player_id": player_id, "name": name}
        ))

        print(f"Player registered: {name} ({player_id})")

    def _handle_join(self, message: Message, client_socket: socket.socket,
                     player_id: str) -> None:
        """Handle player joining the game."""
        with self.lock:
            client = self.clients.get(player_id)
            if not client:
                self._send_error(client_socket, "Not connected")
                return

            if self.game.phase != GamePhase.WAITING:
                self._send_error(client_socket, "Game already in progress")
                return

            if len(self.game.players) >= self.max_players:
                self._send_error(client_socket, "Game is full")
                return

            player = Player(id=player_id, name=client.player_name)
            if self.game.add_player(player):
                self._broadcast(Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": f"{client.player_name} joined the game"}
                ))
                self._send_player_list(client_socket)
                self._broadcast_game_state()

                print(f"Player {client.player_name} joined the game ({len(self.game.players)}/{self.max_players})")
            else:
                self._send_error(client_socket, "Could not join game")

    def _handle_leave(self, message: Message, client_socket: socket.socket,
                      player_id: str) -> None:
        """Handle player leaving the game."""
        with self.lock:
            if self.game.remove_player(player_id):
                client = self.clients.get(player_id)
                name = client.player_name if client else player_id

                self._broadcast(Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": f"{name} left the game"}
                ))
                self._broadcast_game_state()

    def _handle_start(self, message: Message, client_socket: socket.socket,
                      player_id: str) -> None:
        """Handle request to start the game."""
        with self.lock:
            if not self.game.can_start():
                self._send_error(client_socket,
                    f"Need at least {self.game.min_players} players to start")
                return

            if self.game.start_game():
                self._broadcast(Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": "Game started!", "event_type": "game_start"}
                ))

                for player in self.game.players:
                    self._send_hand_update(player.id)

                self._broadcast_game_state()
                print(f"Game started with {len(self.game.players)} players")
            else:
                self._send_error(client_socket, "Could not start game")

    def _handle_play_card(self, message: Message, client_socket: socket.socket,
                          player_id: str) -> None:
        """Handle play card command. Any player can play at any time."""
        with self.lock:
            if self.game.phase != GamePhase.IN_PROGRESS:
                self._send_error(client_socket, "Game not in progress")
                return

            card_data = message.data.get("card")
            if not card_data:
                self._send_error(client_socket, "No card specified")
                return

            try:
                card = Card.from_dict(card_data)
            except (KeyError, ValueError) as e:
                self._send_error(client_socket, f"Invalid card: {e}")
                return

            player = self.game.get_player(player_id)
            if not player or not player.has_card(card):
                self._send_error(client_socket, f"You don't have that card")
                return

            if self.game.play_card(player_id, card):
                self._broadcast(Message(
                    type=MessageType.NOTIFICATION,
                    data={
                        "message": f"{player.name} played {card}",
                        "event_type": "play"
                    }
                ))

                self._send_hand_update(player_id)

                if player.is_empty_hand():
                    self._broadcast(Message(
                        type=MessageType.NOTIFICATION,
                        data={"message": f"{player.name} has played all cards!", "event_type": "win"}
                    ))

                self.game.advance_turn()
                self._broadcast_game_state()
            else:
                self._send_error(client_socket, "Could not play card")

    def _handle_draw_card(self, message: Message, client_socket: socket.socket,
                          player_id: str) -> None:
        """Handle draw card command."""
        with self.lock:
            if self.game.phase != GamePhase.IN_PROGRESS:
                self._send_error(client_socket, "Game not in progress")
                return

            count = message.data.get("count", 1)

            player = self.game.get_player(player_id)
            if not player:
                self._send_error(client_socket, "Player not found")
                return

            cards = self.game.draw_card(player_id, count)

            if cards:
                self._send_message(client_socket, Message(
                    type=MessageType.CARD_DRAWN,
                    data={"cards": [c.to_dict() for c in cards]}
                ))

                self._broadcast(Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": f"{player.name} drew {len(cards)} card(s)", "event_type": "draw"}
                ), exclude={player_id})

                self._send_hand_update(player_id)
                self._broadcast_game_state()

    def _handle_knock(self, message: Message, client_socket: socket.socket,
                      player_id: str) -> None:
        """Handle knock on table."""
        with self.lock:
            client = self.clients.get(player_id)
            if not client:
                return

            self.game.knock(player_id)

            self._broadcast(Message(
                type=MessageType.NOTIFICATION,
                data={"message": f"{client.player_name} knocked on the table", "event_type": "knock"}
            ))

    def _handle_chat(self, message: Message, client_socket: socket.socket,
                     player_id: str) -> None:
        """Handle chat/say command."""
        with self.lock:
            client = self.clients.get(player_id)
            if not client:
                return

            chat_message = message.data.get("message", "")
            if chat_message:
                self.game.chat(player_id, chat_message)

                self._broadcast(Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": f"{client.player_name}: {chat_message}", "event_type": "chat"}
                ))

    def _handle_throw(self, message: Message, client_socket: socket.socket,
                      player_id: str) -> None:
        """Handle throw card at player."""
        with self.lock:
            if self.game.phase != GamePhase.IN_PROGRESS:
                self._send_error(client_socket, "Game not in progress")
                return

            card_data = message.data.get("card")
            target_id = message.data.get("target_id")

            if not card_data or not target_id:
                self._send_error(client_socket, "Must specify card and target")
                return

            try:
                card = Card.from_dict(card_data)
            except (KeyError, ValueError) as e:
                self._send_error(client_socket, f"Invalid card: {e}")
                return

            if self.game.throw_card(player_id, card, target_id):
                player = self.game.get_player(player_id)
                target = self.game.get_player(target_id)

                self._send_hand_update(player_id)
                self._send_hand_update(target_id)

                self._broadcast(Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": f"{player.name} threw {card} at {target.name}", "event_type": "throw"}
                ))

                self._broadcast_game_state()
            else:
                self._send_error(client_socket, "Could not throw card")

    def _handle_hit(self, message: Message, client_socket: socket.socket,
                    player_id: str) -> None:
        """Handle hit player action."""
        with self.lock:
            target_id = message.data.get("target_id")
            if not target_id:
                self._send_error(client_socket, "Must specify target player")
                return

            player = self.game.get_player(player_id)
            target = self.game.get_player(target_id)

            if not player or not target:
                self._send_error(client_socket, "Player not found")
                return

            self.game.hit_player(player_id, target_id)

            self._broadcast(Message(
                type=MessageType.NOTIFICATION,
                data={"message": f"{player.name} hit {target.name}", "event_type": "hit"}
            ))

    def _handle_penalty(self, message: Message, client_socket: socket.socket,
                        player_id: str) -> None:
        """Handle give penalty command."""
        with self.lock:
            if self.game.phase != GamePhase.IN_PROGRESS:
                self._send_error(client_socket, "Game not in progress")
                return

            target_id = message.data.get("target_id")
            reason = message.data.get("reason", "No reason given")
            cards = message.data.get("cards", 1)

            if not target_id:
                self._send_error(client_socket, "Must specify target player")
                return

            penalty = self.game.give_penalty(player_id, target_id, reason, cards)

            if penalty:
                caller = self.game.get_player(player_id)
                target = self.game.get_player(target_id)

                # Broadcast penalty notification to everyone
                self._broadcast(Message(
                    type=MessageType.NOTIFICATION,
                    data={
                        "message": f"{caller.name} gave {cards} penalty card(s) to {target.name}: {reason}",
                        "event_type": "penalty"
                    }
                ))

                # Send penalty details only to the target
                target_client = self.clients.get(target_id)
                if target_client:
                    self._send_message(target_client.socket, Message(
                        type=MessageType.PENALTY,
                        data={"cards": cards, "reason": reason, "caller": caller.name}
                    ))

                # Apply penalty (draw cards) and track dealt cards
                self.game.apply_penalty(penalty.id)

                # Add delay between penalty actions
                if PENALTY_ACTION_DELAY > 0:
                    time.sleep(PENALTY_ACTION_DELAY)

                # Handle -r flag: return last played card (only if played by penalized player)
                return_card = message.data.get("return_card", False)
                if return_card:
                    # Check if last played card was by the penalized player
                    last_play = self.game.played_cards_stack[-1] if self.game.played_cards_stack else None
                    if last_play and last_play[0] == target_id:
                        result = self.game.return_card(player_id)
                        if result:
                            original_id, original_name, card = result
                            self._send_hand_update(original_id)
                            self._broadcast(Message(
                                type=MessageType.NOTIFICATION,
                                data={"message": f"Card {card} returned to {original_name}", "event_type": "return"}
                            ))

                # Cancel any active Mao declaration if penalty was given to the declaring player
                if self.game.mao_declaring_player_id == target_id:
                    self.game.cancel_mao_declaration()
                    if self.mao_timer:
                        self.mao_timer.cancel()
                        self.mao_timer = None
                    self._broadcast(Message(
                        type=MessageType.NOTIFICATION,
                        data={"message": f"{target.name}'s Mao declaration was challenged!", "event_type": "penalty"}
                    ))

                self._broadcast_game_state()
            else:
                self._send_error(client_socket, "Could not give penalty")

    def _handle_return(self, message: Message, client_socket: socket.socket,
                       player_id: str) -> None:
        """Handle return card command (kept for backward compat, but no longer exposed as command)."""
        with self.lock:
            if self.game.phase != GamePhase.IN_PROGRESS:
                self._send_error(client_socket, "Game not in progress")
                return

            result = self.game.return_card(player_id)

            if result:
                original_id, original_name, card = result
                self._send_hand_update(original_id)

                self._broadcast(Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": f"Card {card} returned to {original_name}", "event_type": "return"}
                ))

                self._broadcast_game_state()
            else:
                self._send_error(client_socket, "No card to return")

    def _handle_poo(self, message: Message, client_socket: socket.socket,
                    player_id: str) -> None:
        """Handle Point of Order command. Just enters POO mode - no auto-vote."""
        with self.lock:
            if self.game.phase == GamePhase.POINT_OF_ORDER:
                self._send_error(client_socket, "Already in Point of Order")
                return

            if self.game.phase != GamePhase.IN_PROGRESS:
                self._send_error(client_socket, "Game not in progress")
                return

            reason = message.data.get("reason", "General dispute")

            client = self.clients.get(player_id)
            caller_name = client.player_name if client else player_id

            if self.game.initiate_point_of_order(caller_id=player_id, reason=reason):
                # Build POO data with logs and penalty history
                poo_data = self.game.point_of_order.to_dict()
                poo_data["logs"] = [log.to_dict() for log in self.game.get_recent_logs(20)]
                poo_data["penalty_history"] = [p.to_dict() for p in self.game.penalty_history]

                self._broadcast(Message(
                    type=MessageType.POINT_OF_ORDER,
                    data=poo_data
                ))

                self._broadcast_game_state()
                print(f"Point of Order called by {caller_name}: {reason}")
            else:
                self._send_error(client_socket, "Could not start Point of Order")

    def _handle_end_poo(self, message: Message, client_socket: socket.socket,
                        player_id: str) -> None:
        """Handle end Point of Order command."""
        with self.lock:
            if self.game.phase != GamePhase.POINT_OF_ORDER:
                self._send_error(client_socket, "Not in Point of Order")
                return

            client = self.clients.get(player_id)
            caller_name = client.player_name if client else player_id

            if self.game.end_point_of_order():
                self._broadcast(Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": f"{caller_name} ended the Point of Order", "event_type": "poo_end"}
                ))

                self._broadcast_game_state()
                print(f"Point of Order ended by {caller_name}")
            else:
                self._send_error(client_socket, "Could not end Point of Order")

    def _handle_vote_penalty(self, message: Message, client_socket: socket.socket,
                             player_id: str) -> None:
        """Handle selecting a penalty to vote on during Point of Order."""
        with self.lock:
            if self.game.phase != GamePhase.POINT_OF_ORDER:
                self._send_error(client_socket, "Not in Point of Order")
                return

            # penalty_index is 0-based (client sends 1-based, subtracts 1 before sending)
            penalty_index = message.data.get("penalty_index")
            if penalty_index is None:
                self._send_error(client_socket, "Must specify penalty number")
                return

            active_vote = self.game.start_penalty_vote(penalty_index)

            if active_vote:
                penalty = active_vote.penalty

                # Broadcast that a vote has started
                self._broadcast(Message(
                    type=MessageType.NOTIFICATION,
                    data={
                        "message": f"Vote started on penalty #{penalty_index + 1}: "
                                   f"{penalty.caller_name} → {penalty.target_name}: {penalty.reason}\n"
                                   f"  Type 'uphold', 'overturn', or 'abstain' to vote.",
                        "event_type": "vote_start"
                    }
                ))

                # Send updated POO state
                poo_data = self.game.point_of_order.to_dict()
                poo_data["logs"] = [log.to_dict() for log in self.game.get_recent_logs(20)]
                poo_data["penalty_history"] = [p.to_dict() for p in self.game.penalty_history]

                self._broadcast(Message(
                    type=MessageType.POINT_OF_ORDER,
                    data=poo_data
                ))
            else:
                self._send_error(client_socket,
                    "Could not start vote. Either a vote is already active, "
                    "the penalty was already overturned, or invalid penalty number.")

    def _handle_vote(self, message: Message, client_socket: socket.socket,
                     player_id: str) -> None:
        """Handle vote during Point of Order (uphold/overturn/abstain on active penalty vote)."""
        with self.lock:
            if self.game.phase != GamePhase.POINT_OF_ORDER:
                self._send_error(client_socket, "Not in Point of Order")
                return

            if not self.game.point_of_order or not self.game.point_of_order.active_vote:
                self._send_error(client_socket, "No active vote. Use 'vote <penalty #>' to start a vote.")
                return

            vote = message.data.get("vote", "")
            if vote not in ("uphold", "overturn", "abstain"):
                self._send_error(client_socket, "Invalid vote. Use 'uphold', 'overturn', or 'abstain'.")
                return

            if self.game.add_vote(player_id, vote):
                client = self.clients.get(player_id)
                voter_name = client.player_name if client else player_id

                self._broadcast(Message(
                    type=MessageType.NOTIFICATION,
                    data={"message": f"{voter_name} voted to {vote}"}
                ))

                # Check if voting is complete
                result = self.game.check_vote_result()
                if result is not None:
                    self._resolve_penalty_vote(result)

    def _resolve_penalty_vote(self, result: str) -> None:
        """Resolve the current penalty vote during POO."""
        resolution = self.game.resolve_penalty_vote(result)
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

            # Update hands for both players
            self._send_hand_update(penalty_info["target_id"])
            self._send_hand_update(penalty_info["caller_id"])
        else:
            msg = f"Penalty UPHELD: {penalty_info['target_name']}'s penalty stands."

        self._broadcast(Message(
            type=MessageType.NOTIFICATION,
            data={"message": msg, "event_type": "vote_result"}
        ))

        # Send updated POO state (still in POO, can vote on more penalties)
        if self.game.point_of_order:
            poo_data = self.game.point_of_order.to_dict()
            poo_data["logs"] = [log.to_dict() for log in self.game.get_recent_logs(20)]
            poo_data["penalty_history"] = [p.to_dict() for p in self.game.penalty_history]

            self._broadcast(Message(
                type=MessageType.POINT_OF_ORDER,
                data=poo_data
            ))

        self._broadcast_game_state()

    def _handle_view_players(self, message: Message, client_socket: socket.socket,
                              player_id: str) -> None:
        """Handle request to view players."""
        self._send_player_list(client_socket)

    def _handle_declare_mao(self, message: Message, client_socket: socket.socket,
                             player_id: str) -> None:
        """Handle player declaring Mao. Works with cards in hand - 6 second delay."""
        with self.lock:
            if self.game.phase != GamePhase.IN_PROGRESS:
                self._send_error(client_socket, "Game not in progress")
                return

            player = self.game.get_player(player_id)
            if not player:
                self._send_error(client_socket, "Player not found")
                return

            if self.game.mao_declaring_player_id is not None:
                self._send_error(client_socket, "Someone is already declaring Mao!")
                return

            # Start the 6-second declaration timer
            if self.game.start_mao_declaration(player_id):
                card_count = player.get_card_count()
                card_msg = f" with {card_count} card(s) remaining" if card_count > 0 else " with an empty hand"

                self._broadcast(Message(
                    type=MessageType.NOTIFICATION,
                    data={
                        "message": f"🎯 {player.name} declares MAO{card_msg}! "
                                   f"Other players have 6 seconds to challenge with a penalty...",
                        "event_type": "mao_declare"
                    }
                ))

                self._broadcast_game_state()

                from config.settings import MAO_CHALLENGE_TIME

                # Start timer in a separate thread
                self.mao_timer = threading.Timer(MAO_CHALLENGE_TIME, self._mao_timer_expired, args=[player_id])
                self.mao_timer.daemon = True
                self.mao_timer.start()

                print(f"{player.name} declared Mao - {MAO_CHALLENGE_TIME} second timer started")

    def _mao_timer_expired(self, player_id: str) -> None:
        """Called when the 6-second Mao declaration timer expires."""
        with self.lock:
            # Check if the declaration is still active (wasn't cancelled by penalty)
            if self.game.mao_declaring_player_id != player_id:
                return

            player = self.game.get_player(player_id)
            if not player:
                self.game.cancel_mao_declaration()
                return

            # Declaration succeeded!
            self.game.cancel_mao_declaration()
            self.mao_timer = None

            self._broadcast(Message(
                type=MessageType.NOTIFICATION,
                data={
                    "message": f"🎉 {player.name} declares MAO and WINS! 🎉",
                    "event_type": "victory"
                }
            ))

            self.game.phase = GamePhase.FINISHED

            # Send victory data with winner info
            self._broadcast(Message(
                type=MessageType.GAME_OVER,
                data={
                    "winner_id": player_id,
                    "winner_name": player.name,
                    "card_count": player.get_card_count()
                }
            ))

            self._broadcast_game_state()
            print(f"Game over! {player.name} won by declaring Mao!")

    def _handle_cancel_mao(self, message: Message, client_socket: socket.socket,
                            player_id: str) -> None:
        """Handle any player canceling a Mao declaration."""
        with self.lock:
            if self.game.mao_declaring_player_id is None:
                self._send_error(client_socket, "No Mao declaration in progress")
                return

            player = self.game.get_player(player_id)
            declaring_player = self.game.get_player(self.game.mao_declaring_player_id)
            player_name = player.name if player else player_id
            declarer_name = declaring_player.name if declaring_player else "Someone"

            self.game.cancel_mao_declaration()
            if self.mao_timer:
                self.mao_timer.cancel()
                self.mao_timer = None

            self._broadcast(Message(
                type=MessageType.NOTIFICATION,
                data={"message": f"{player_name} canceled {declarer_name}'s Mao declaration", "event_type": "mao_declare"}
            ))
            self._broadcast_game_state()

    def _handle_shuffle_cards(self, message: Message, client_socket: socket.socket,
                               player_id: str) -> None:
        """
        Handle shuffle cards request during Point of Order.
        Shuffles discard pile (except top card) into draw pile to fix draw pile exhaustion.
        Does NOT affect other players' hands.
        """
        with self.lock:
            if self.game.phase != GamePhase.POINT_OF_ORDER:
                self._send_error(client_socket, "Can only shuffle cards during Point of Order")
                return

            # Check if draw pile is empty or low
            draw_count = self.game.draw_pile.remaining() if self.game.draw_pile else 0
            discard_count = len(self.game.discard_pile)

            if discard_count <= 1:
                self._send_error(client_socket, "Not enough cards in discard pile to shuffle")
                return

            client = self.clients.get(player_id)
            shuffler_name = client.player_name if client else player_id

            # Take all but top card from discard, shuffle into draw pile
            import random
            top_card = self.game.discard_pile[-1]
            cards_to_shuffle = self.game.discard_pile[:-1]

            if cards_to_shuffle:
                self.game.draw_pile.add_cards(cards_to_shuffle)
                self.game.draw_pile.shuffle()
                self.game.discard_pile = [top_card]

                self._broadcast(Message(
                    type=MessageType.NOTIFICATION,
                    data={
                        "message": f"{shuffler_name} shuffled {len(cards_to_shuffle)} card(s) from discard into draw pile. Draw pile now has {self.game.draw_pile.remaining()} cards.",
                        "event_type": "poo_action"
                    }
                ))
                self._broadcast_game_state()
            else:
                self._send_error(client_socket, "No cards to shuffle")

    def _handle_view_hand(self, message: Message, client_socket: socket.socket,
                           player_id: str) -> None:
        """
        Handle view own hand during Point of Order.
        Only shows player's own hand. Announces to all players that they looked.
        """
        with self.lock:
            if self.game.phase != GamePhase.POINT_OF_ORDER:
                self._send_error(client_socket, "Can only view hand during Point of Order")
                return

            player = self.game.get_player(player_id)
            if not player:
                self._send_error(client_socket, "Player not found")
                return

            client = self.clients.get(player_id)
            viewer_name = client.player_name if client else player_id

            # Send the hand to the requester (only their own hand)
            self._send_message(client_socket, Message(
                type=MessageType.HAND_UPDATE,
                data={"hand": [card.to_dict() for card in player.hand]}
            ))

            # Announce to ALL players that this person looked at their hand
            self._broadcast(Message(
                type=MessageType.NOTIFICATION,
                data={"message": f"{viewer_name} looked at their hand", "event_type": "poo_action"}
            ))

    # --- Utility Methods ---

    def _send_message(self, socket: socket.socket, message: Message) -> bool:
        """Send a message to a client socket."""
        try:
            socket.sendall(Protocol.encode_message(message))
            return True
        except socket.error:
            return False

    def _send_error(self, socket: socket.socket, error_message: str) -> None:
        """Send an error message to a client."""
        self._send_message(socket, Message(
            type=MessageType.ERROR,
            data={"message": error_message}
        ))

    def _send_hand_update(self, player_id: str) -> None:
        """Send hand update to a specific player."""
        client = self.clients.get(player_id)
        if not client:
            return

        hand = self.game.get_player_hand(player_id)
        self._send_message(client.socket, Message(
            type=MessageType.HAND_UPDATE,
            data={"hand": [card.to_dict() for card in hand]}
        ))

    def _send_player_list(self, socket: socket.socket) -> None:
        """Send the list of players to a client."""
        players_data = []
        for player in self.game.players:
            players_data.append({
                "id": player.id,
                "name": player.name,
                "card_count": player.get_card_count(),
                "is_connected": player.is_connected
            })

        self._send_message(socket, Message(
            type=MessageType.PLAYER_LIST,
            data={"players": players_data}
        ))

    def _broadcast(self, message: Message, exclude: Optional[Set[str]] = None) -> None:
        """Send a message to all connected clients."""
        exclude = exclude or set()
        for player_id, client in list(self.clients.items()):
            if player_id not in exclude:
                self._send_message(client.socket, message)

    def _broadcast_game_state(self) -> None:
        """Send current game state to all players."""
        for player_id, client in self.clients.items():
            state = self.game.to_dict(for_player_id=player_id)
            self._send_message(client.socket, Message(
                type=MessageType.GAME_STATE,
                player_id=player_id,
                data=state
            ))


def main():
    """Run the game server from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Mao Game Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5555, help="Port to listen on")
    parser.add_argument("--decks", type=int, default=1, help="Number of card decks")
    parser.add_argument("--max-players", type=int, default=10, help="Maximum players")

    args = parser.parse_args()

    server = GameServer(
        host=args.host,
        port=args.port,
        num_decks=args.decks,
        max_players=args.max_players
    )
    server.start()


if __name__ == "__main__":
    main()
