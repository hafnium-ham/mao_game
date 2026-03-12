"""Player class for Mao card game."""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from .card import Card, Suit, Rank, SUIT_ORDER


@dataclass
class Player:
    """
    Represents a player in the Mao game.

    Tracks the player's hand, connection status, and penalty state.
    """
    id: str
    name: str
    hand: List[Card] = field(default_factory=list)
    is_connected: bool = True
    penalty_cards_pending: int = 0
    last_action_timestamp: float = 0.0

    def add_card(self, card: Card) -> None:
        """Add a card to the player's hand."""
        self.hand.append(card)

    def add_cards(self, cards: List[Card]) -> None:
        """Add multiple cards to the player's hand."""
        self.hand.extend(cards)

    def remove_card(self, card: Card) -> bool:
        """
        Remove a specific card from the player's hand.

        Args:
            card: The card to remove.

        Returns:
            True if card was found and removed, False otherwise.
        """
        try:
            self.hand.remove(card)
            return True
        except ValueError:
            return False

    def remove_card_by_index(self, index: int) -> Optional[Card]:
        """
        Remove and return a card by its index in the hand.

        Args:
            index: The index of the card to remove.

        Returns:
            The removed card, or None if index is invalid.
        """
        if 0 <= index < len(self.hand):
            return self.hand.pop(index)
        return None

    def has_card(self, card: Card) -> bool:
        """Check if the player has a specific card."""
        return card in self.hand

    def has_matching_card(self, suit: Optional[Suit] = None, rank: Optional[Rank] = None) -> bool:
        """
        Check if player has any card matching the given suit or rank.

        Args:
            suit: Suit to match (optional).
            rank: Rank to match (optional).

        Returns:
            True if player has at least one matching card.
        """
        for card in self.hand:
            if suit and card.suit == suit:
                return True
            if rank and card.rank == rank:
                return True
        return False

    def get_card_count(self) -> int:
        """Return the number of cards in the player's hand."""
        return len(self.hand)

    def is_empty_hand(self) -> bool:
        """Check if player has no cards (potential win condition)."""
        return len(self.hand) == 0

    def sort_hand(self, by_suit: bool = True, by_rank: bool = True) -> None:
        """
        Sort the player's hand.

        Args:
            by_suit: If True, group by suit.
            by_rank: If True, sort by rank within suit (or overall if by_suit is False).
        """
        if by_suit and by_rank:
            self.hand.sort()
        elif by_rank:
            self.hand.sort(key=lambda c: c.rank.sort_value)
        elif by_suit:
            self.hand.sort(key=lambda c: SUIT_ORDER.index(c.suit))

    def get_cards_by_suit(self, suit: Suit) -> List[Card]:
        """Get all cards of a specific suit."""
        return [card for card in self.hand if card.suit == suit]

    def get_cards_by_rank(self, rank: Rank) -> List[Card]:
        """Get all cards of a specific rank."""
        return [card for card in self.hand if card.rank == rank]

    def find_card(self, suit: Optional[Suit] = None, rank: Optional[Rank] = None) -> Optional[Card]:
        """
        Find first card matching the given suit and/or rank.

        Args:
            suit: Suit to match (optional).
            rank: Rank to match (optional).

        Returns:
            First matching card, or None if not found.
        """
        for card in self.hand:
            if suit and card.suit != suit:
                continue
            if rank and card.rank != rank:
                continue
            return card
        return None

    def clear_hand(self) -> List[Card]:
        """
        Remove all cards from hand and return them.

        Returns:
            List of cards that were in the hand.
        """
        cards = self.hand.copy()
        self.hand.clear()
        return cards

    def add_penalty(self, count: int = 1) -> None:
        """Add penalty cards to pending total."""
        self.penalty_cards_pending += count

    def clear_penalty(self) -> int:
        """
        Clear pending penalties and return the count.

        Returns:
            Number of penalty cards that were pending.
        """
        count = self.penalty_cards_pending
        self.penalty_cards_pending = 0
        return count

    def to_dict(self, include_hand: bool = False) -> Dict[str, Any]:
        """
        Serialize player for network transmission.

        Args:
            include_hand: If True, include card details (private to player).

        Returns:
            Dictionary representation of the player.
        """
        data = {
            "id": self.id,
            "name": self.name,
            "card_count": self.get_card_count(),
            "is_connected": self.is_connected,
            "penalty_cards_pending": self.penalty_cards_pending
        }

        if include_hand:
            data["hand"] = [card.to_dict() for card in self.hand]

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Player":
        """Create a Player from dictionary data."""
        player = cls(
            id=data["id"],
            name=data["name"],
            is_connected=data.get("is_connected", True),
            penalty_cards_pending=data.get("penalty_cards_pending", 0)
        )

        if "hand" in data:
            player.hand = [Card.from_dict(c) for c in data["hand"]]

        return player

    def __repr__(self) -> str:
        """Developer representation."""
        return f"Player(id={self.id!r}, name={self.name!r}, cards={self.get_card_count()})"

    def __str__(self) -> str:
        """User-friendly string representation."""
        return f"{self.name} ({self.get_card_count()} cards)"