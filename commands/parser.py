"""Command parser for Mao game."""

from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
import re


@dataclass
class ParsedCommand:
    """Represents a parsed user command."""
    command: str
    args: List[str]
    kwargs: Dict[str, Any]
    raw_input: str


class CommandParser:
    """
    Parses user input into structured commands.

    Supports command aliases and various argument formats.
    """

    def __init__(self):
        """Initialize the command parser."""
        self.aliases: Dict[str, str] = {}
        self._setup_commands()

    def _setup_commands(self) -> None:
        """Set up command aliases."""
        self.aliases = {
            "h": "hand",
            "cards": "hand",
            "p": "play",
            "d": "draw",
            "k": "knock",
            "chat": "say",
            "t": "throw",
            "pe": "penalty",
            "pls": "players",
            "r": "return",
            "?": "help",
            "q": "quit",
            "exit": "quit",
        }

    def parse(self, user_input: str) -> Optional[ParsedCommand]:
        """
        Parse user input into a command.

        Args:
            user_input: Raw user input string.

        Returns:
            ParsedCommand if valid, None if empty.
        """
        user_input = user_input.strip()
        if not user_input:
            return None

        # Split into tokens
        tokens = self._tokenize(user_input)
        if not tokens:
            return None

        command = tokens[0].lower()

        # Resolve alias
        command = self.aliases.get(command, command)

        # Parse command-specific arguments
        return self._parse_command(command, tokens[1:], user_input)

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize input string, respecting quotes.

        Args:
            text: Input string.

        Returns:
            List of tokens.
        """
        tokens = []
        current = ""
        in_quotes = False
        quote_char = None

        for char in text:
            if char in ('"', "'") and not in_quotes:
                in_quotes = True
                quote_char = char
            elif char == quote_char and in_quotes:
                in_quotes = False
                quote_char = None
            elif char.isspace() and not in_quotes:
                if current:
                    tokens.append(current)
                    current = ""
            else:
                current += char

        if current:
            tokens.append(current)

        return tokens

    def _parse_command(self, command: str, args: List[str], raw: str) -> ParsedCommand:
        """Parse command-specific arguments."""
        parsers = {
            "hand": self._parse_hand,
            "play": self._parse_play,
            "draw": self._parse_draw,
            "knock": self._parse_knock,
            "say": self._parse_say,
            "throw": self._parse_throw,
            "hit": self._parse_hit,
            "penalty": self._parse_penalty,
            "players": self._parse_players,
            "return": self._parse_return,
            "poo": self._parse_poo,
            "vote": self._parse_vote,
            "join": self._parse_join,
            "start": self._parse_start,
            "help": self._parse_help,
            "quit": self._parse_quit,
        }

        parser = parsers.get(command, self._parse_generic)
        return parser(command, args, raw)

    def _parse_generic(self, command: str, args: List[str], raw: str) -> ParsedCommand:
        """Generic parser for simple commands."""
        return ParsedCommand(
            command=command,
            args=args,
            kwargs={},
            raw_input=raw
        )

    def _parse_hand(self, command: str, args: List[str], raw: str) -> ParsedCommand:
        """Parse: hand [--sort]"""
        return ParsedCommand(
            command=command,
            args=args,
            kwargs={"sort": "--sort" in args},
            raw_input=raw
        )

    def _parse_play(self, command: str, args: List[str], raw: str) -> ParsedCommand:
        """Parse: play <card> [--face-up|--face-down]"""
        kwargs = {"face_up": "--face-down" not in args}

        # Filter out flags to get card
        card_args = [a for a in args if not a.startswith("--")]

        return ParsedCommand(
            command=command,
            args=card_args,
            kwargs=kwargs,
            raw_input=raw
        )

    def _parse_draw(self, command: str, args: List[str], raw: str) -> ParsedCommand:
        """Parse: draw [count]"""
        count = 1
        if args:
            try:
                count = int(args[0])
            except ValueError:
                pass

        return ParsedCommand(
            command=command,
            args=args,
            kwargs={"count": count},
            raw_input=raw
        )

    def _parse_knock(self, command: str, args: List[str], raw: str) -> ParsedCommand:
        """Parse: knock"""
        return ParsedCommand(command=command, args=args, kwargs={}, raw_input=raw)

    def _parse_say(self, command: str, args: List[str], raw: str) -> ParsedCommand:
        """Parse: say <message>"""
        # Extract message after command
        parts = raw.split(None, 1)
        message = parts[1] if len(parts) > 1 else ""

        return ParsedCommand(
            command=command,
            args=[],
            kwargs={"message": message},
            raw_input=raw
        )

    def _parse_throw(self, command: str, args: List[str], raw: str) -> ParsedCommand:
        """Parse: throw <card> at <player>"""
        card = None
        target = None

        # Find "at" separator
        try:
            at_index = args.index("at")
            card = " ".join(args[:at_index])
            target = " ".join(args[at_index + 1:])
        except (ValueError, IndexError):
            if args:
                card = args[0]
                if len(args) > 1:
                    target = " ".join(args[1:])

        return ParsedCommand(
            command=command,
            args=args,
            kwargs={"card": card, "target": target},
            raw_input=raw
        )

    def _parse_hit(self, command: str, args: List[str], raw: str) -> ParsedCommand:
        """Parse: hit <player>"""
        target = args[0] if args else None
        return ParsedCommand(
            command=command,
            args=args,
            kwargs={"target": target},
            raw_input=raw
        )

    def _parse_penalty(self, command: str, args: List[str], raw: str) -> ParsedCommand:
        """Parse: penalty <player> <reason> [--cards N]"""
        kwargs = {"cards": 1, "target": None, "reason": ""}

        # Parse flags
        filtered_args = []
        i = 0
        while i < len(args):
            if args[i] == "--cards" and i + 1 < len(args):
                try:
                    kwargs["cards"] = int(args[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                filtered_args.append(args[i])
                i += 1

        # First arg is target, rest is reason
        if filtered_args:
            kwargs["target"] = filtered_args[0]
            if len(filtered_args) > 1:
                kwargs["reason"] = " ".join(filtered_args[1:])

        return ParsedCommand(
            command=command,
            args=filtered_args,
            kwargs=kwargs,
            raw_input=raw
        )

    def _parse_players(self, command: str, args: List[str], raw: str) -> ParsedCommand:
        """Parse: players"""
        return ParsedCommand(command=command, args=args, kwargs={}, raw_input=raw)

    def _parse_return(self, command: str, args: List[str], raw: str) -> ParsedCommand:
        """Parse: return [card]"""
        card = args[0] if args else None
        return ParsedCommand(
            command=command,
            args=args,
            kwargs={"card": card},
            raw_input=raw
        )

    def _parse_poo(self, command: str, args: List[str], raw: str) -> ParsedCommand:
        """Parse: poo [reason]"""
        reason = " ".join(args) if args else "General dispute"
        return ParsedCommand(
            command=command,
            args=args,
            kwargs={"reason": reason},
            raw_input=raw
        )

    def _parse_vote(self, command: str, args: List[str], raw: str) -> ParsedCommand:
        """Parse: vote <yes|no|y|n>"""
        vote = args[0].lower() if args else ""
        agree = vote in ("yes", "y", "uphold", "1", "true")

        return ParsedCommand(
            command=command,
            args=args,
            kwargs={"agree": agree},
            raw_input=raw
        )

    def _parse_join(self, command: str, args: List[str], raw: str) -> ParsedCommand:
        """Parse: join"""
        return ParsedCommand(command=command, args=args, kwargs={}, raw_input=raw)

    def _parse_start(self, command: str, args: List[str], raw: str) -> ParsedCommand:
        """Parse: start"""
        return ParsedCommand(command=command, args=args, kwargs={}, raw_input=raw)

    def _parse_help(self, command: str, args: List[str], raw: str) -> ParsedCommand:
        """Parse: help [command]"""
        topic = args[0] if args else None
        return ParsedCommand(
            command=command,
            args=args,
            kwargs={"topic": topic},
            raw_input=raw
        )

    def _parse_quit(self, command: str, args: List[str], raw: str) -> ParsedCommand:
        """Parse: quit"""
        return ParsedCommand(command=command, args=args, kwargs={}, raw_input=raw)

    def get_help(self, command: Optional[str] = None) -> str:
        """
        Get help text for a command or all commands.

        Args:
            command: Specific command to get help for, or None for all.

        Returns:
            Help text string.
        """
        help_texts = {
            "hand": "hand [--sort] - View your cards. Use --sort to sort by suit.",
            "play": "play <card> - Play a card. Card format: H7, 7H, 'hearts 7'",
            "draw": "draw [count] - Draw cards from the deck. Default: 1",
            "knock": "knock - Knock on the table",
            "say": "say <message> - Say something (triggers speech rules)",
            "throw": "throw <card> at <player> - Throw a card at another player",
            "hit": "hit <player> - Hit another player",
            "penalty": "penalty <player> <reason> [--cards N] - Give penalty cards",
            "players": "players - View all players in the game",
            "return": "return - Return the last played card (for misplays)",
            "poo": "poo [reason] - Call Point of Order to dispute a penalty",
            "vote": "vote <yes|no> - Vote during Point of Order",
            "join": "join - Join the game",
            "start": "start - Start the game (needs minimum players)",
            "quit": "quit - Leave the game",
            "help": "help [command] - Show help",
        }

        if command:
            return help_texts.get(command, f"No help available for '{command}'")

        lines = ["Available commands:"]
        for cmd, help_text in help_texts.items():
            lines.append(f"  {help_text}")
        lines.append("\nCard format: <suit><rank> or <rank><suit>")
        lines.append("  Suits: H=Hearts, D=Diamonds, C=Clubs, S=Spades")
        lines.append("  Ranks: A, 2-10, J, Q, K")
        lines.append("  Examples: H7, 7H, AS, 10D")

        return "\n".join(lines)