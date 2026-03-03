"""Tests for Deck class."""

import unittest
from core.deck import Deck
from core.card import Card, Suit, Rank


class TestDeck(unittest.TestCase):
    """Test cases for Deck class."""

    def test_deck_creation_single(self):
        """Test creating a single deck."""
        deck = Deck(num_decks=1)
        self.assertEqual(deck.remaining(), 52)

    def test_deck_creation_multiple(self):
        """Test creating multiple decks."""
        deck = Deck(num_decks=2)
        self.assertEqual(deck.remaining(), 104)

    def test_deck_draw(self):
        """Test drawing cards."""
        deck = Deck(num_decks=1)
        card = deck.draw()
        self.assertIsInstance(card, Card)
        self.assertEqual(deck.remaining(), 51)

    def test_deck_draw_empty(self):
        """Test drawing from empty deck."""
        deck = Deck(num_decks=1)
        for _ in range(52):
            deck.draw()
        card = deck.draw()
        self.assertIsNone(card)

    def test_deck_shuffle(self):
        """Test shuffling doesn't change count."""
        deck = Deck(num_decks=1)
        original_count = deck.remaining()
        deck.shuffle()
        self.assertEqual(deck.remaining(), original_count)

    def test_deck_add_cards(self):
        """Test adding cards back to deck."""
        deck = Deck(num_decks=1)
        cards = []
        for _ in range(10):
            card = deck.draw()
            if card:
                cards.append(card)

        deck.add_cards(cards)
        self.assertEqual(deck.remaining(), 52)

    def test_deck_is_empty(self):
        """Test empty check."""
        deck = Deck(num_decks=1)
        self.assertFalse(deck.is_empty())

        for _ in range(52):
            deck.draw()

        self.assertTrue(deck.is_empty())


if __name__ == "__main__":
    unittest.main()