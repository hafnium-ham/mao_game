"""Card class for Mao card game."""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any


class Suit(Enum):
    """Card suits with display symbols."""
    HEARTS = ("hearts", "♥", "H")
    DIAMONDS = ("diamonds", "♦", "D")
    CLUBS = ("clubs", "♣", "C")
    SPADES = ("spades", "♠", "S")

    def __init__(self, full_name: str, symbol: str, code: str):
        self.full_name = full_name
        self.symbol = symbol
        self.code = code

    @classmethod
    def from_code(cls, code: str) -> "Suit":
        """Get suit from single-letter code (H, D, C, S)."""
        code = code.upper()
        for suit in cls:
            if suit.code == code:
                return suit
        raise ValueError(f"Invalid suit code: {code}")

    @classmethod
    def from_name(cls, name: str) -> "Suit":
        """Get suit from full name (hearts, diamonds, etc.)."""
        name = name.lower()
        for suit in cls:
            if suit.full_name == name:
                return suit
        raise ValueError(f"Invalid suit name: {name}")

    @property
    def is_red(self) -> bool:
        """Check if suit is red (hearts or diamonds)."""
        return self in (Suit.HEARTS, Suit.DIAMONDS)


class Rank(Enum):
    """Card ranks with display values."""
    ACE = ("A", 1, 14)
    TWO = ("2", 2, 2)
    THREE = ("3", 3, 3)
    FOUR = ("4", 4, 4)
    FIVE = ("5", 5, 5)
    SIX = ("6", 6, 6)
    SEVEN = ("7", 7, 7)
    EIGHT = ("8", 8, 8)
    NINE = ("9", 9, 9)
    TEN = ("10", 10, 10)
    JACK = ("J", 11, 11)
    QUEEN = ("Q", 12, 12)
    KING = ("K", 13, 13)

    def __init__(self, display: str, num_value: int, sort_order: int):
        self.display = display
        self.num_value = num_value
        self.sort_order = sort_order

    @classmethod
    def from_display(cls, display: str) -> "Rank":
        """Get rank from display value (A, 2-10, J, Q, K)."""
        display = display.upper()
        for rank in cls:
            if rank.display == display:
                return rank
        raise ValueError(f"Invalid rank: {display}")

    @property
    def is_face_card(self) -> bool:
        """Check if rank is a face card (J, Q, K)."""
        return self in (Rank.JACK, Rank.QUEEN, Rank.KING)

    @property
    def is_number_card(self) -> bool:
        """Check if rank is a number card (2-10)."""
        return Rank.TWO.num_value <= self.num_value <= Rank.TEN.num_value


@dataclass(frozen=True)
class Card:
    """Represents a playing card with suit and rank."""
    suit: Suit
    rank: Rank

    def __str__(self) -> str:
        """String representation like 'A♠' or '10♥'."""
        return f"{self.rank.display}{self.suit.symbol}"

    def __repr__(self) -> str:
        """Developer representation."""
        return f"Card({self.suit.full_name}, {self.rank.display})"

    def __lt__(self, other: "Card") -> bool:
        """Compare cards for sorting (by suit, then rank)."""
        if not isinstance(other, Card):
            return NotImplemented
        # Sort by suit first, then by rank
        suit_order = [Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES]
        self_suit_idx = suit_order.index(self.suit)
        other_suit_idx = suit_order.index(other.suit)
        if self_suit_idx != other_suit_idx:
            return self_suit_idx < other_suit_idx
        return self.rank.sort_order < other.rank.sort_order

    def __le__(self, other: "Card") -> bool:
        """Less than or equal comparison."""
        return self == other or self < other

    def to_dict(self) -> Dict[str, Any]:
        """Serialize card for network transmission."""
        return {
            "suit": self.suit.full_name,
            "rank": self.rank.display
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Card":
        """Deserialize card from network data."""
        suit = Suit.from_name(data["suit"])
        rank = Rank.from_display(data["rank"])
        return cls(suit=suit, rank=rank)

    @classmethod
    def parse(cls, card_str: str) -> "Card":
        """
        Parse card from various string formats.

        Supported formats:
        - 'H7' or '7H' (suit code + rank)
        - 'hearts 7' or '7 of hearts' (full name)
        - 'A♠' or '♠A' (symbol format)
        """
        card_str = card_str.strip().upper()

        if not card_str:
            raise ValueError("Empty card string")

        # Try symbol format first (A♠, ♠A, 10♥, etc.)
        for suit in Suit:
            if suit.symbol in card_str:
                rank_str = card_str.replace(suit.symbol, "").strip()
                rank = Rank.from_display(rank_str)
                return cls(suit=suit, rank=rank)

        # Try suit code format (H7, 7H, D10, 10D, etc.)
        for suit in Suit:
            if card_str.startswith(suit.code):
                rank_str = card_str[1:]
                if rank_str:
                    rank = Rank.from_display(rank_str)
                    return cls(suit=suit, rank=rank)
            if card_str.endswith(suit.code):
                rank_str = card_str[:-1]
                if rank_str:
                    rank = Rank.from_display(rank_str)
                    return cls(suit=suit, rank=rank)

        # Try full name format
        card_str_lower = card_str.lower()
        for suit in Suit:
            if suit.full_name in card_str_lower:
                rank_str = card_str_lower.replace(suit.full_name, "").strip()
                rank_str = rank_str.replace("of", "").strip()
                if rank_str:
                    rank = Rank.from_display(rank_str)
                    return cls(suit=suit, rank=rank)

        raise ValueError(f"Could not parse card: {card_str}")

    @property
    def code(self) -> str:
        """Short code representation like 'H7' or 'SA'."""
        return f"{self.suit.code}{self.rank.display}"

    @property
    def full_name(self) -> str:
        """Full name like '7 of Hearts' or 'Ace of Spades'."""
        return f"{self.rank.display} of {self.suit.full_name.title()}"

    def matches(self, other: "Card") -> bool:
        """Check if this card matches another by suit or rank (for play validity)."""
        return self.suit == other.suit or self.rank == other.rank