"""CLI display utilities for Mao game."""

import os
from typing import List, Dict, Any, Optional
from .colors import Colors, colorize, bold, dim, red, green, yellow, cyan
from core.card import Card, Suit


class GameDisplay:
    """Handles all CLI display output for the game."""

    # Card suit symbols
    CARD_SYMBOLS = {
        Suit.HEARTS: "♥",
        Suit.DIAMONDS: "♦",
        Suit.CLUBS: "♣",
        Suit.SPADES: "♠",
    }

    # Suit colors (red for hearts/diamonds)
    SUIT_COLORS = {
        Suit.HEARTS: Colors.RED,
        Suit.DIAMONDS: Colors.RED,
        Suit.CLUBS: Colors.WHITE,
        Suit.SPADES: Colors.WHITE,
    }

    def clear_screen(self) -> None:
        """Clear the terminal screen."""
        print("\033[2J\033[H", end="")

    def show_welcome(self) -> None:
        """Display welcome message."""
        print(f"""
{Colors.CYAN}╔══════════════════════════════════════╗
║            {Colors.YELLOW}MAO CARD GAME{Colors.CYAN}             ║
║                                      ║
║  The game with rules you must        ║
║  discover through play...            ║
╚══════════════════════════════════════╝{Colors.RESET}
        """)

    def show_help(self) -> None:
        """Display available commands."""
        print(f"""
{Colors.BOLD}Commands:{Colors.RESET}
  {Colors.YELLOW}join{Colors.RESET}              - Join the game
  {Colors.YELLOW}start{Colors.RESET}             - Start the game (when ready)

  {Colors.BOLD}During Game:{Colors.RESET}
  {Colors.GREEN}hand{Colors.RESET}, h, cards    - View your cards
  {Colors.GREEN}play{Colors.RESET} <card|#>      - Play a card (e.g., play H7, play 1)
  {Colors.GREEN}draw{Colors.RESET}, d            - Draw a card from the deck
  {Colors.GREEN}knock{Colors.RESET}, k           - Knock on the table
  {Colors.GREEN}say{Colors.RESET} <message>      - Say something (chat)
  {Colors.GREEN}throw{Colors.RESET} <card> at <player> - Throw a card at a player
  {Colors.GREEN}hit{Colors.RESET} <player>       - Hit another player
  {Colors.GREEN}penalty{Colors.RESET} <player> [-r] <reason> - Give penalty (-r: return card too)
  {Colors.GREEN}players{Colors.RESET}, pls       - View all players
  {Colors.GREEN}mao{Colors.RESET}               - Declare Mao (6s for others to challenge)

  {Colors.BOLD}Point of Order:{Colors.RESET}
  {Colors.MAGENTA}poo{Colors.RESET} [reason]      - Call Point of Order (pauses game)
  {Colors.MAGENTA}vote{Colors.RESET} <penalty #>  - Start a vote on a penalty during POO
  {Colors.MAGENTA}uphold{Colors.RESET}            - Vote to uphold the penalty
  {Colors.MAGENTA}overturn{Colors.RESET}          - Vote to overturn the penalty
  {Colors.MAGENTA}abstain{Colors.RESET}           - Abstain from voting
  {Colors.MAGENTA}end point of order{Colors.RESET} / {Colors.MAGENTA}epoo{Colors.RESET} - End Point of Order

  {Colors.BOLD}Other:{Colors.RESET}
  {Colors.DIM}help, ?            - Show this help
  {Colors.DIM}quit, q            - Leave the game{Colors.RESET}

{Colors.BOLD}Card Format:{Colors.RESET}
  <suit><rank> or <rank><suit> or <card #>
  {Colors.RED}Suits: H=Hearts, D=Diamonds{Colors.RESET}, C=Clubs, S=Spades
  Ranks: A, 2-10, J, Q, K
  Examples: H7, 7H, AS, 10D, play 1 (by hand position)
        """)

    def show_hand(self, cards: List[Card], sort: bool = False) -> None:
        """Display player's hand."""
        print(f"\n{Colors.BOLD}Your Hand:{Colors.RESET}")
        print("─" * 50)

        if not cards:
            print("  (no cards)")
            print("─" * 50)
            return

        if sort:
            cards = sorted(cards)

        # Display cards in rows of 5
        row_size = 5
        for i, card in enumerate(cards):
            symbol = self.CARD_SYMBOLS.get(card.suit, "?")
            color = self.SUIT_COLORS.get(card.suit, Colors.WHITE)
            card_str = f"{card.rank.display}{symbol}({card.suit.code})"
            colored = colorize(card_str, color, Colors.BOLD)

            # Card position number
            num = f"{i + 1:2}"

            print(f"  [{num}] {colored}", end="")

            # New line every row_size cards
            if (i + 1) % row_size == 0:
                print()

        # Final newline if needed
        if len(cards) % row_size != 0:
            print()

        print("─" * 50)
        print(f"Total: {Colors.BOLD}{len(cards)}{Colors.RESET} cards\n")

    def render_game_state(self, state: Dict[str, Any], player_id: str = None) -> None:
        """Render the current game state."""
        phase = state.get("phase", "unknown")
        phase_display = {
            "waiting": f"{Colors.YELLOW}WAITING FOR PLAYERS{Colors.RESET}",
            "in_progress": f"{Colors.GREEN}IN PROGRESS{Colors.RESET}",
            "point_of_order": f"{Colors.MAGENTA}POINT OF ORDER{Colors.RESET}",
            "finished": f"{Colors.CYAN}GAME OVER{Colors.RESET}",
        }

        # Header
        print(f"\n{'=' * 55}")
        print(f"  MAO - {phase_display.get(phase, phase)}")
        print(f"{'=' * 55}")

        # Mao declaration warning
        mao_declaring = state.get("mao_declaring_player_id")
        if mao_declaring:
            declaring_name = "Someone"
            for p in state.get("players", []):
                if p.get("id") == mao_declaring:
                    declaring_name = p.get("name", "Someone")
                    break
            is_you = mao_declaring == player_id
            if is_you:
                print(f"\n  {Colors.YELLOW}🎯 YOU are declaring MAO! Waiting for challenges...{Colors.RESET}")
            else:
                print(f"\n  {Colors.YELLOW}🎯 {declaring_name} is declaring MAO! Penalty to challenge!{Colors.RESET}")

        # Top card
        top_card_data = state.get("top_card")
        if top_card_data:
            try:
                top_card = Card.from_dict(top_card_data)
                self._show_top_card(top_card)
            except (KeyError, ValueError):
                print(f"\n  Top Card: ?")

        # Players
        print(f"\n  {Colors.BOLD}Players:{Colors.RESET}")
        print("  " + "─" * 45)

        for p in state.get("players", []):
            name = p.get("name", "Unknown")
            count = p.get("card_count", 0)
            is_you = p.get("id") == player_id

            you_marker = f" {Colors.DIM}(you){Colors.RESET}" if is_you else ""
            card_str = f"{count} card{'s' if count != 1 else ''}"

            print(f"    {name}{you_marker}: {card_str}")

        # Show your hand inline
        if player_id:
            for p in state.get("players", []):
                if p.get("id") == player_id and "hand" in p:
                    hand_cards = [Card.from_dict(c) for c in p["hand"]]
                    if hand_cards:
                        self.show_hand(hand_cards)
                    break

        # Point of Order info
        poo_data = state.get("point_of_order")
        if poo_data:
            self._show_poo_summary(poo_data)

        print(f"\n{'=' * 55}")
        print(f"  {Colors.DIM}Type 'help' for commands{Colors.RESET}\n")

    def _show_top_card(self, card: Card) -> None:
        """Display the top card of discard pile."""
        symbol = self.CARD_SYMBOLS.get(card.suit, "?")
        color = self.SUIT_COLORS.get(card.suit, Colors.WHITE)
        card_str = f"{card.rank.display}{symbol}"
        colored = colorize(card_str, color, Colors.BOLD)
        print(f"\n  {Colors.BOLD}Top Card:{Colors.RESET} {colored}")

    def _show_poo_summary(self, poo_data: Dict[str, Any]) -> None:
        """Show Point of Order summary in game state."""
        caller = poo_data.get("caller_name", "?")

        print(f"\n  {Colors.MAGENTA}{'─' * 45}{Colors.RESET}")
        print(f"  {Colors.MAGENTA}POINT OF ORDER{Colors.RESET} (called by {caller})")

        active_vote = poo_data.get("active_vote")
        if active_vote:
            penalty = active_vote.get("penalty", {})
            uphold = active_vote.get("uphold_count", 0)
            overturn = active_vote.get("overturn_count", 0)
            abstain = active_vote.get("abstain_count", 0)
            print(f"  {Colors.YELLOW}Active Vote:{Colors.RESET} {penalty.get('caller_name', '?')} → {penalty.get('target_name', '?')}: {penalty.get('reason', '?')}")
            print(f"    Uphold: {uphold} | Overturn: {overturn} | Abstain: {abstain}")
            print(f"  {Colors.DIM}Type 'uphold', 'overturn', or 'abstain' to vote{Colors.RESET}")
        else:
            print(f"  {Colors.DIM}Use 'vote <#>' to vote on a penalty, 'epoo' to end{Colors.RESET}")

    def show_message(self, message: str, event_type: str = None) -> None:
        """Display a notification message."""
        type_colors = {
            "play": Colors.GREEN,
            "draw": Colors.BLUE,
            "knock": Colors.YELLOW,
            "chat": Colors.CYAN,
            "penalty": Colors.RED,
            "throw": Colors.MAGENTA,
            "hit": Colors.RED,
            "return": Colors.YELLOW,
            "win": Colors.GREEN,
            "victory": Colors.GREEN,
            "game_start": Colors.GREEN,
            "mao_declare": Colors.YELLOW,
            "vote_start": Colors.MAGENTA,
            "vote_result": Colors.CYAN,
            "poo_end": Colors.MAGENTA,
        }

        color = type_colors.get(event_type, Colors.WHITE)
        prefix = f"[{event_type}] " if event_type else ""

        print(f"\n{color}{prefix}{message}{Colors.RESET}\n")

    def show_error(self, error: str) -> None:
        """Display an error message."""
        print(f"\n{Colors.RED}✗ {error}{Colors.RESET}\n")

    def show_penalty(self, cards: int, reason: str, caller: str = None) -> None:
        """Display penalty notification."""
        caller_str = f" from {caller}" if caller else ""
        print(f"\n{Colors.RED}{'─' * 45}{Colors.RESET}")
        print(f"{Colors.RED}  PENALTY: +{cards} card(s){caller_str}{Colors.RESET}")
        print(f"  Reason: {reason}")
        print(f"{Colors.RED}{'─' * 45}{Colors.RESET}\n")

    def show_point_of_order(self, data: Dict[str, Any]) -> None:
        """Display Point of Order information with penalty list."""
        self.clear_screen()

        caller = data.get("caller_name", "Unknown")
        reason = data.get("reason", "No reason given")

        print(f"\n{Colors.MAGENTA}{'!' * 55}{Colors.RESET}")
        print(f"{Colors.MAGENTA}  POINT OF ORDER{Colors.RESET}")
        print(f"{Colors.MAGENTA}{'!' * 55}{Colors.RESET}")

        print(f"\n  {Colors.BOLD}Called by:{Colors.RESET} {caller}")
        print(f"  {Colors.BOLD}Reason:{Colors.RESET} {reason}")
        print(f"  {Colors.DIM}No time limit - use 'end point of order' or 'epoo' to end{Colors.RESET}")

        # Show penalty history
        penalty_history = data.get("penalty_history", [])
        overturned_ids = data.get("overturned_penalty_ids", [])

        if penalty_history:
            print(f"\n  {Colors.BOLD}Penalties (use 'vote <#>' to vote on one):{Colors.RESET}")
            print("  " + "─" * 50)

            for i, p in enumerate(penalty_history):
                penalty_id = p.get("id", "")
                is_overturned = p.get("overturned", False) or penalty_id in overturned_ids
                caller_name = p.get("caller_name", "?")
                target_name = p.get("target_name", "?")
                p_reason = p.get("reason", "?")
                cards = p.get("cards", 1)

                if is_overturned:
                    status = f"{Colors.RED}[OVERTURNED]{Colors.RESET}"
                else:
                    status = ""

                num = f"{i + 1:2}"
                print(f"  [{num}] {caller_name} → {target_name}: {p_reason} ({cards} card{'s' if cards != 1 else ''}) {status}")

            print("  " + "─" * 50)
        else:
            print(f"\n  {Colors.DIM}No penalties to vote on.{Colors.RESET}")

        # Show recent logs
        logs = data.get("logs", [])
        if logs:
            print(f"\n  {Colors.DIM}Recent Game Log:{Colors.RESET}")
            print("  " + "─" * 50)
            for log in logs[-10:]:
                timestamp = log.get("timestamp", "")[-8:]
                details = log.get("details", "")
                print(f"  [{timestamp}] {details}")

        # Show active vote status
        active_vote = data.get("active_vote")
        if active_vote:
            penalty = active_vote.get("penalty", {})
            uphold = active_vote.get("uphold_count", 0)
            overturn = active_vote.get("overturn_count", 0)
            abstain = active_vote.get("abstain_count", 0)
            total = active_vote.get("total_players", 0)
            voted = uphold + overturn + abstain

            print(f"\n  {Colors.YELLOW}{'─' * 50}{Colors.RESET}")
            print(f"  {Colors.YELLOW}ACTIVE VOTE:{Colors.RESET} {penalty.get('caller_name', '?')} → {penalty.get('target_name', '?')}")
            print(f"    Reason: {penalty.get('reason', '?')}")
            print(f"    {Colors.GREEN}Uphold: {uphold}{Colors.RESET} | {Colors.RED}Overturn: {overturn}{Colors.RESET} | {Colors.DIM}Abstain: {abstain}{Colors.RESET}")
            print(f"    ({voted}/{total} voted)")
            print(f"\n  {Colors.CYAN}Type 'uphold', 'overturn', or 'abstain' to cast your vote{Colors.RESET}")
        else:
            print(f"\n  {Colors.CYAN}Commands: 'vote <#>' to vote on penalty, 'epoo' to end POO{Colors.RESET}")

        print(f"{Colors.MAGENTA}{'!' * 55}{Colors.RESET}\n")

    def show_victory_screen(self, winner_name: str, card_count: int = 0) -> None:
        """Display the victory screen with Mao.jpeg reference."""
        self.clear_screen()

        # Check if mao.jpeg exists for reference
        mao_image_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mao.jpeg")
        has_image = os.path.exists(mao_image_path)

        print(f"""
{Colors.YELLOW}{'★' * 55}{Colors.RESET}
{Colors.YELLOW}{'★' * 55}{Colors.RESET}

{Colors.GREEN}{Colors.BOLD}
    ╔═══════════════════════════════════════════════╗
    ║                                               ║
    ║          🎉  VICTORY!  🎉                     ║
    ║                                               ║
    ║     {winner_name} declares MAO and WINS!{' ' * max(0, 21 - len(winner_name))}║
    ║                                               ║
    ╚═══════════════════════════════════════════════╝
{Colors.RESET}

{Colors.CYAN}    🃏  The Chairman has spoken!  🃏{Colors.RESET}
""")

        if card_count > 0:
            print(f"{Colors.YELLOW}    Won with {card_count} card(s) still in hand! Bold move!{Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}    Won with an empty hand! Clean victory!{Colors.RESET}")

        if has_image:
            print(f"\n{Colors.DIM}    [Mao.jpeg: {mao_image_path}]{Colors.RESET}")
            # Try to display using sixel/kitty/iterm2 protocol if available
            self._try_display_image(mao_image_path)

        print(f"""
{Colors.YELLOW}{'★' * 55}{Colors.RESET}
{Colors.YELLOW}{'★' * 55}{Colors.RESET}
""")

    def _try_display_image(self, image_path: str) -> None:
        """Try to display an image in the terminal using iTerm2 inline images protocol."""
        try:
            import base64
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("ascii")

            # iTerm2 inline image protocol
            print(f"\033]1337;File=inline=1;width=30;preserveAspectRatio=1:{image_data}\a")
        except Exception:
            # If image display fails, just show the path (already shown above)
            pass

    def show_player_list(self, players: List[Dict[str, Any]]) -> None:
        """Display the list of players."""
        print(f"\n{Colors.BOLD}Players:{Colors.RESET}")
        print("─" * 40)

        if not players:
            print("  No players")
            return

        for i, p in enumerate(players, 1):
            name = p.get("name", "Unknown")
            card_count = p.get("card_count", "?")
            connected = p.get("is_connected", True)
            status = f"{Colors.GREEN}●{Colors.RESET}" if connected else f"{Colors.RED}○{Colors.RESET}"
            print(f"  {i}. {status} {name} ({card_count} cards)")

        print("─" * 40)

    def show_card_drawn(self, cards: List[Card]) -> None:
        """Display drawn cards."""
        if not cards:
            return

        card_strs = []
        for card in cards:
            symbol = self.CARD_SYMBOLS.get(card.suit, "?")
            color = self.SUIT_COLORS.get(card.suit, Colors.WHITE)
            card_str = f"{card.rank.display}{symbol}"
            card_strs.append(colorize(card_str, color, Colors.BOLD))

        print(f"\n{Colors.BLUE}Drew:{Colors.RESET} {', '.join(card_strs)}\n")
