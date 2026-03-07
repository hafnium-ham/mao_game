"""Game client for Mao card game."""

import socket
import threading
import sys
import readline  # enables proper line editing (backspace, arrows) in input()
from typing import Optional, List, Dict, Any
from queue import Queue, Empty

from .protocol import Message, MessageType, Protocol
from core.card import Card, Suit, Rank
from ui.display import GameDisplay


class GameClient:
    """
    Game client for Mao.

    Connects to the server, handles user input, and displays game state.
    """

    def __init__(self, host: str = "localhost", port: int = 5555):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.player_id: Optional[str] = None
        self.player_name: str = ""

        self.running = False
        self.connected = False
        self.in_game = False
        self.receive_thread: Optional[threading.Thread] = None

        self.display = GameDisplay()
        self.game_state: Dict[str, Any] = {}
        self.hand: List[Card] = []
        self.point_of_order_active = False
        self.vote_active = False  # True when a penalty vote is in progress during POO

        # Message handlers
        self.message_handlers = {
            MessageType.CONNECT: self._on_connect,
            MessageType.GAME_STATE: self._on_game_state,
            MessageType.HAND_UPDATE: self._on_hand_update,
            MessageType.NOTIFICATION: self._on_notification,
            MessageType.ERROR: self._on_error,
            MessageType.PENALTY: self._on_penalty,
            MessageType.POINT_OF_ORDER: self._on_point_of_order,
            MessageType.CARD_DRAWN: self._on_card_drawn,
            MessageType.PLAYER_LIST: self._on_player_list,
            MessageType.SUCCESS: self._on_success,
            MessageType.GAME_OVER: self._on_game_over,
        }

    # --- Connection ---

    def connect(self, name: str) -> bool:
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            self.socket.settimeout(None)
            self.player_name = name
            self.running = True

            self._send_message(Message(
                type=MessageType.CONNECT,
                data={"name": name}
            ))

            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()

            import time
            timeout = 5
            start = time.time()
            while not self.connected and time.time() - start < timeout:
                time.sleep(0.1)

            return self.connected

        except socket.timeout:
            print(f"Connection to {self.host}:{self.port} timed out")
            return False
        except ConnectionRefusedError:
            print(f"Connection refused by {self.host}:{self.port}")
            return False
        except socket.error as e:
            print(f"Connection error: {e}")
            return False

    def disconnect(self) -> None:
        self.running = False
        self.connected = False

        if self.socket:
            try:
                self._send_message(Message(type=MessageType.DISCONNECT))
            except socket.error:
                pass
            finally:
                try:
                    self.socket.close()
                except socket.error:
                    pass
                self.socket = None

    # --- Main Loop ---

    def run(self) -> None:
        self.display.show_welcome()
        self.display.show_help()

        while self.running and self.connected:
            try:
                user_input = input("\n> ").strip()

                if not user_input:
                    continue

                self._execute_command(user_input)

            except KeyboardInterrupt:
                print("\nDisconnecting...")
                break
            except EOFError:
                print("\nDisconnecting...")
                break

        self.disconnect()

    def _execute_command(self, user_input: str) -> None:
        """Parse and execute a user command."""
        # Handle multi-word commands first
        lower = user_input.lower().strip()

        # "Point of Order" - exact phrase to call POO
        if lower == "point of order":
            self._cmd_poo("")
            return

        # "End Point of Order" - exact phrase to end POO
        if lower == "end point of order":
            self._cmd_end_poo("")
            return

        # Also support "epoo" as shorthand
        if lower == "epoo":
            self._cmd_end_poo("")
            return

        parts = user_input.split(None, 1)
        if not parts:
            return

        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # During an active vote in POO, allow direct vote words
        if self.vote_active and command in ("uphold", "overturn", "abstain"):
            self._cmd_cast_vote(command)
            return

        # Command handlers
        handlers = {
            "hand": self._cmd_hand,
            "h": self._cmd_hand,
            "cards": self._cmd_hand,
            "view": self._cmd_hand,  # Alias for hand
            "play": self._cmd_play,
            "p": self._cmd_play,
            "draw": self._cmd_draw,
            "d": self._cmd_draw,
            "knock": self._cmd_knock,
            "k": self._cmd_knock,
            "say": self._cmd_say,
            "chat": self._cmd_say,
            "throw": self._cmd_throw,
            "t": self._cmd_throw,
            "hit": self._cmd_hit,
            "penalty": self._cmd_penalty,
            "pe": self._cmd_penalty,
            "players": self._cmd_players,
            "pls": self._cmd_players,
            "vote": self._cmd_vote,
            "uphold": lambda a: self._cmd_cast_vote("uphold"),
            "overturn": lambda a: self._cmd_cast_vote("overturn"),
            "abstain": lambda a: self._cmd_cast_vote("abstain"),
            "mao": self._cmd_mao,
            "cancel": self._cmd_cancel_mao,
            "shuffle": self._cmd_shuffle,
            "join": self._cmd_join,
            "start": self._cmd_start,
            "help": self._cmd_help,
            "?": self._cmd_help,
            "quit": self._cmd_quit,
            "q": self._cmd_quit,
            "exit": self._cmd_quit,
        }

        handler = handlers.get(command)
        if handler:
            handler(args)
        else:
            print(f"Unknown command: {command}. Type 'help' for commands.")

    # --- Commands ---

    def _cmd_join(self, args: str) -> None:
        if self.in_game:
            print("Already in game!")
            return
        self._send_message(Message(type=MessageType.JOIN_GAME))
        print("Joining game...")

    def _cmd_start(self, args: str) -> None:
        if not self.in_game:
            print("You must join the game first! Type 'join'")
            return
        self._send_message(Message(type=MessageType.START_GAME))
        print("Requesting game start...")

    def _cmd_hand(self, args: str) -> None:
        if not self.hand:
            print("You have no cards.")
            return
        self.display.show_hand(self.hand, bool(args and "--sort" in args))

    def _cmd_play(self, args: str) -> None:
        """Play a card by name (e.g., play H7) or by index number (e.g., play 1)."""
        if not self.in_game or self.point_of_order_active:
            print("Cannot play right now.")
            return

        if not args:
            print("Usage: play <card> or play <number> (e.g., play H7, play 1)")
            return

        card_str = args.split()[0]

        # Check if it's a number (play by index)
        try:
            index = int(card_str)
            if index < 1 or index > len(self.hand):
                print(f"Invalid card number. You have {len(self.hand)} cards (1-{len(self.hand)}).")
                return
            card = self.hand[index - 1]
        except ValueError:
            # Parse as card name
            try:
                card = Card.parse(card_str)
            except ValueError as e:
                print(f"Invalid card: {e}")
                return

            if card not in self.hand:
                print(f"You don't have {card}")
                return

        self._send_message(Message(
            type=MessageType.PLAY_CARD,
            data={"card": card.to_dict()}
        ))

    def _cmd_draw(self, args: str) -> None:
        if not self.in_game or self.point_of_order_active:
            print("Cannot draw right now.")
            return

        count = 1
        if args:
            try:
                count = int(args.split()[0])
            except ValueError:
                pass

        self._send_message(Message(
            type=MessageType.DRAW_CARD,
            data={"count": count}
        ))

    def _cmd_knock(self, args: str) -> None:
        if not self.in_game:
            print("Not in game!")
            return
        self._send_message(Message(type=MessageType.KNOCK))

    def _cmd_say(self, args: str) -> None:
        if not self.in_game:
            print("Not in game!")
            return
        if not args:
            print("Usage: say <message>")
            return
        self._send_message(Message(
            type=MessageType.CHAT,
            data={"message": args}
        ))

    def _cmd_throw(self, args: str) -> None:
        if not self.in_game or self.point_of_order_active:
            print("Cannot throw right now.")
            return

        import re
        match = re.match(r"(.+?)\s+at\s+(.+)", args, re.IGNORECASE)
        if not match:
            print("Usage: throw <card> at <player>")
            return

        card_str, target = match.groups()

        try:
            card = Card.parse(card_str.strip())
        except ValueError as e:
            print(f"Invalid card: {e}")
            return

        if card not in self.hand:
            print(f"You don't have {card}")
            return

        target_id = self._find_player_by_name(target.strip())
        if not target_id:
            print(f"Player '{target}' not found")
            return

        self._send_message(Message(
            type=MessageType.THROW_CARD,
            data={"card": card.to_dict(), "target_id": target_id}
        ))

    def _cmd_hit(self, args: str) -> None:
        if not self.in_game:
            print("Not in game!")
            return
        if not args:
            print("Usage: hit <player>")
            return

        target_id = self._find_player_by_name(args.strip())
        if not target_id:
            print(f"Player '{args}' not found")
            return

        self._send_message(Message(
            type=MessageType.HIT_PLAYER,
            data={"target_id": target_id}
        ))

    def _cmd_penalty(self, args: str) -> None:
        """Give a penalty. Use -r to also return the last played card."""
        if not self.in_game or self.point_of_order_active:
            print("Cannot give penalty right now.")
            return

        parts = args.split(None, 1)
        if not parts:
            print("Usage: penalty <player> [-r] <reason>")
            return

        target = parts[0]
        remainder = parts[1] if len(parts) > 1 else "No reason given"

        return_card = False
        if remainder.startswith("-r "):
            return_card = True
            remainder = remainder[3:].strip() or "No reason given"
        elif remainder == "-r":
            return_card = True
            remainder = "No reason given"

        reason = remainder

        target_id = self._find_player_by_name(target)
        if not target_id:
            print(f"Player '{target}' not found")
            return

        self._send_message(Message(
            type=MessageType.GIVE_PENALTY,
            data={"target_id": target_id, "reason": reason, "return_card": return_card}
        ))

    def _cmd_players(self, args: str) -> None:
        self._send_message(Message(type=MessageType.VIEW_PLAYERS))

    def _cmd_poo(self, args: str) -> None:
        """Call Point of Order."""
        if not self.in_game:
            print("Not in game!")
            return

        if self.point_of_order_active:
            print("Already in Point of Order!")
            return

        reason = args if args else "General dispute"
        self._send_message(Message(
            type=MessageType.POINT_OF_ORDER,
            data={"reason": reason}
        ))

    def _cmd_end_poo(self, args: str) -> None:
        """End Point of Order."""
        if not self.point_of_order_active:
            print("Not in Point of Order!")
            return

        self._send_message(Message(type=MessageType.END_POINT_OF_ORDER))

    def _cmd_vote(self, args: str) -> None:
        """Vote command during Point of Order.
        - 'vote <number>' to select a penalty to vote on
        - 'vote uphold/overturn/abstain' to cast vote on active penalty
        """
        if not self.point_of_order_active:
            print("Not in Point of Order!")
            return

        if not args:
            print("Usage: vote <penalty #> to start a vote, or uphold/overturn/abstain to cast vote")
            return

        vote_arg = args.strip().lower()

        # Check if it's a vote cast (uphold/overturn/abstain)
        if vote_arg in ("uphold", "overturn", "abstain"):
            self._cmd_cast_vote(vote_arg)
            return

        # Check if it's "yes" or "no" (legacy compat)
        if vote_arg in ("yes", "y"):
            self._cmd_cast_vote("uphold")
            return
        if vote_arg in ("no", "n"):
            self._cmd_cast_vote("overturn")
            return

        # Otherwise, try to parse as penalty number
        try:
            penalty_num = int(vote_arg)
            if penalty_num < 1:
                print("Penalty number must be positive.")
                return

            # Send 0-based index to server
            self._send_message(Message(
                type=MessageType.VOTE_PENALTY,
                data={"penalty_index": penalty_num - 1}
            ))
        except ValueError:
            print("Usage: vote <penalty #> to start a vote, or uphold/overturn/abstain to cast vote")

    def _cmd_cast_vote(self, vote: str) -> None:
        """Cast uphold/overturn/abstain on the active penalty vote."""
        if not self.point_of_order_active:
            print("Not in Point of Order!")
            return

        if not self.vote_active:
            print("No active vote. Use 'vote <penalty #>' to start a vote first.")
            return

        self._send_message(Message(
            type=MessageType.VOTE,
            data={"vote": vote}
        ))

    def _cmd_mao(self, args: str) -> None:
        """Declare Mao. Can be declared with cards in hand - 10 second delay for challenges."""
        if not self.in_game:
            print("Not in game!")
            return

        self._send_message(Message(
            type=MessageType.DECLARE_MAO,
            data={}
        ))

    def _cmd_cancel_mao(self, args: str) -> None:
        """Cancel your own Mao declaration."""
        if not self.in_game:
            print("Not in game!")
            return

        self._send_message(Message(type=MessageType.CANCEL_MAO))

    def _cmd_shuffle(self, args: str) -> None:
        """
        Shuffle discard pile into draw pile during Point of Order.
        Used to fix draw pile exhaustion - does NOT affect other players.
        """
        if not self.point_of_order_active:
            print("Can only shuffle during Point of Order!")
            return

        self._send_message(Message(
            type=MessageType.SHUFFLE_CARDS,
            data={}
        ))

    def _cmd_view_hand(self, args: str) -> None:
        """View your own hand during Point of Order. All players will be notified."""
        if not self.point_of_order_active:
            # Outside POO, just show hand directly (it's already synced)
            if not self.hand:
                print("You have no cards.")
            else:
                self.display.show_hand(self.hand)
            return

        # During POO, request hand view from server (which announces to all)
        self._send_message(Message(
            type=MessageType.VIEW_HAND,
            data={}
        ))

    def _cmd_help(self, args: str) -> None:
        self.display.show_help()

    def _cmd_quit(self, args: str) -> None:
        self.running = False

    def _find_player_by_name(self, name: str) -> Optional[str]:
        name_lower = name.lower()
        for player in self.game_state.get("players", []):
            if name_lower in player.get("name", "").lower():
                return player.get("id")
        return None

    # --- Network ---

    def _receive_loop(self) -> None:
        buffer = b""

        while self.running:
            try:
                data = self.socket.recv(4096)
                if not data:
                    print("\nDisconnected from server.")
                    self.running = False
                    self.connected = False
                    break

                buffer += data

                while len(buffer) >= Protocol.HEADER_SIZE:
                    message, buffer = Protocol.decode_message(buffer)
                    if message:
                        self._handle_message(message)
                    else:
                        break

            except socket.error as e:
                if self.running:
                    print(f"\nConnection error: {e}")
                self.running = False
                self.connected = False
                break

    def _handle_message(self, message: Message) -> None:
        handler = self.message_handlers.get(message.type)
        if handler:
            handler(message)

    def _on_connect(self, message: Message) -> None:
        self.player_id = message.data.get("player_id")
        self.connected = True
        print(f"\nConnected as {message.data.get('name')} (ID: {self.player_id})")
        print("Type 'join' to join the game")

    def _on_game_state(self, message: Message) -> None:
        self.game_state = message.data
        phase = self.game_state.get("phase", "")
        self.point_of_order_active = (phase == "point_of_order")

        # Track if a vote is active during POO
        poo_data = self.game_state.get("point_of_order")
        if poo_data and poo_data.get("active_vote"):
            self.vote_active = True
        else:
            self.vote_active = False

        # Only mark as in_game if this player is in the players list
        player_ids = [p.get("id") for p in self.game_state.get("players", [])]
        if self.player_id in player_ids:
            self.in_game = True

        self.display.render_game_state(self.game_state, self.player_id)

    def _on_hand_update(self, message: Message) -> None:
        hand_data = message.data.get("hand", [])
        self.hand = [Card.from_dict(c) for c in hand_data]

        print(f"\nYour hand ({len(self.hand)} cards):")
        self.display.show_hand(self.hand)

    def _on_notification(self, message: Message) -> None:
        msg = message.data.get("message", "")
        event_type = message.data.get("event_type", "")
        self.display.show_message(msg, event_type)

    def _on_error(self, message: Message) -> None:
        error_msg = message.data.get("message", "Unknown error")
        if message.error:
            error_msg = message.error
        self.display.show_error(error_msg)

    def _on_penalty(self, message: Message) -> None:
        cards = message.data.get("cards", 1)
        reason = message.data.get("reason", "No reason given")
        caller = message.data.get("caller", "Someone")
        self.display.show_penalty(cards, reason, caller)

    def _on_point_of_order(self, message: Message) -> None:
        self.point_of_order_active = True

        # Check if a vote is active
        active_vote = message.data.get("active_vote")
        self.vote_active = active_vote is not None

        self.display.show_point_of_order(message.data)

    def _on_card_drawn(self, message: Message) -> None:
        cards = message.data.get("cards", [])
        if cards:
            card_objs = [Card.from_dict(c) for c in cards]
            print(f"\nYou drew: {', '.join(str(c) for c in card_objs)}")

    def _on_player_list(self, message: Message) -> None:
        players = message.data.get("players", [])
        self.display.show_player_list(players)

    def _on_success(self, message: Message) -> None:
        print(f"OK: {message.data.get('message', 'Success')}")

    def _on_game_over(self, message: Message) -> None:
        """Handle game over with victory screen."""
        winner_name = message.data.get("winner_name", "Unknown")
        card_count = message.data.get("card_count", 0)
        self.display.show_victory_screen(winner_name, card_count)

    def _send_message(self, message: Message) -> None:
        if self.socket:
            try:
                self.socket.sendall(Protocol.encode_message(message))
            except socket.error as e:
                print(f"Error sending message: {e}")
                self.connected = False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Mao Game Client")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=5555, help="Server port")
    parser.add_argument("--name", "-n", required=True, help="Player name")

    args = parser.parse_args()

    client = GameClient(host=args.host, port=args.port)

    if client.connect(args.name):
        client.run()
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
