"""Deck class for Mao card game."""

import random
from typing import List, Optional
from .card import Card, Suit, Rank


class Deck:
    """
    Represents a deck of playing cards.

    Supports multiple standard 52-card decks combined together.
    """

    def __init__(self, num_decks: int = 1, cards: Optional[List[Card]] = None):
        """
        Initialize deck.

        Args:
            num_decks: Number of standard 52-card decks to include.
            cards: Optional pre-existing list of cards (for custom decks).
        """
        self.num_decks = num_decks
        if cards is not None:
            self._cards: List[Card] = cards
        else:
            self._cards: List[Card] = []
            self._initialize()

    def _initialize(self) -> None:
        """Create all cards for the specified number of standard decks."""
        self._cards = []
        for _ in range(self.num_decks):
            for suit in Suit:
                for rank in Rank:
                    self._cards.append(Card(suit=suit, rank=rank))

    def shuffle(self) -> None:
        """Randomize the order of cards in the deck."""
        random.shuffle(self._cards)

    def draw(self) -> Optional[Card]:
        """
        Draw the top card from the deck.

        Returns:
            The top card, or None if deck is empty.
        """
        if not self._cards:
            return None
        return self._cards.pop()

    def draw_multiple(self, count: int) -> List[Card]:
        """
        Draw multiple cards from the deck.

        Args:
            count: Number of cards to draw.

        Returns:
            List of drawn cards (may be fewer than requested if deck runs out).
        """
        drawn = []
        for _ in range(count):
            card = self.draw()
            if card is None:
                break
            drawn.append(card)
        return drawn

    def add_card(self, card: Card, to_bottom: bool = False) -> None:
        """
        Add a card to the deck.

        Args:
            card: The card to add.
            to_bottom: If True, add to bottom of deck; otherwise top.
        """
        if to_bottom:
            self._cards.insert(0, card)
        else:
            self._cards.append(card)

    def add_cards(self, cards: List[Card], to_bottom: bool = True) -> None:
        """
        Add multiple cards to the deck.

        Args:
            cards: List of cards to add.
            to_bottom: If True, add to bottom of deck; otherwise top.
        """
        if to_bottom:
            # Add to bottom, maintaining order
            self._cards = cards + self._cards
        else:
            self._cards.extend(cards)

    def is_empty(self) -> bool:
        """Check if the deck has no cards."""
        return len(self._cards) == 0

    def remaining(self) -> int:
        """Get the number of cards remaining in the deck."""
        return len(self._cards)

    def peek(self) -> Optional[Card]:
        """
        Look at the top card without removing it.

        Returns:
            The top card, or None if deck is empty.
        """
        if not self._cards:
            return None
        return self._cards[-1]

    def __len__(self) -> int:
        """Return the number of cards in the deck."""
        return len(self._cards)

    def __bool__(self) -> bool:
        """Return True if deck has cards."""
        return bool(self._cards)

    def __repr__(self) -> str:
        """Developer representation."""
        return f"Deck(num_decks={self.num_decks}, remaining={self.remaining()})"

    @classmethod
    def create_for_players(cls, num_players: int, cards_per_player: int = 7) -> "Deck":
        """
        Create a deck sized appropriately for the number of players.

        Args:
            num_players: Number of players in the game.
            cards_per_player: Starting cards per player.

        Returns:
            A new Deck with appropriate number of standard decks.
        """
        # Calculate total cards needed
        total_cards_needed = num_players * cards_per_player + 10  # Extra for discard

        # Each standard deck has 52 cards
        num_decks = max(1, (total_cards_needed // 52) + 1)

        # Scale with players: 1 deck for up to 4, 2 for up to 7, 3 for up to 10
        if num_players <= 4:
            num_decks = 1
        elif num_players <= 7:
            num_decks = 2
        else:
            num_decks = 3

        return cls(num_decks=num_decks)

    def to_dict(self) -> dict:
        """Serialize deck state for logging/debugging."""
        return {
            "num_decks": self.num_decks,
            "remaining": self.remaining(),
            "cards": [card.to_dict() for card in self._cards]
        }