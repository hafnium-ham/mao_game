"""Tests for Card class."""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mao_game.core.card import Card, Suit, Rank


class TestCard(unittest.TestCase):
    """Test cases for Card class."""

    def test_card_creation(self):
        """Test creating a card."""
        card = Card(Suit.HEARTS, Rank.SEVEN)
        self.assertEqual(card.suit, Suit.HEARTS)
        self.assertEqual(card.rank, Rank.SEVEN)

    def test_card_str(self):
        """Test string representation."""
        card = Card(Suit.SPADES, Rank.ACE)
        self.assertEqual(str(card), "A♠")

    def test_card_to_dict(self):
        """Test serialization."""
        card = Card(Suit.DIAMONDS, Rank.KING)
        d = card.to_dict()
        self.assertEqual(d["suit"], "diamonds")
        self.assertEqual(d["rank"], "K")

    def test_card_from_dict(self):
        """Test deserialization."""
        d = {"suit": "clubs", "rank": "Q"}
        card = Card.from_dict(d)
        self.assertEqual(card.suit, Suit.CLUBS)
        self.assertEqual(card.rank, Rank.QUEEN)

    def test_card_parse(self):
        """Test parsing card from string."""
        # Various formats
        card1 = Card.parse("H7")
        self.assertEqual(card1.suit, Suit.HEARTS)
        self.assertEqual(card1.rank, Rank.SEVEN)

        card2 = Card.parse("AS")
        self.assertEqual(card2.suit, Suit.SPADES)
        self.assertEqual(card2.rank, Rank.ACE)

        card3 = Card.parse("10D")
        self.assertEqual(card3.suit, Suit.DIAMONDS)
        self.assertEqual(card3.rank, Rank.TEN)

    def test_card_equality(self):
        """Test card equality."""
        card1 = Card(Suit.HEARTS, Rank.SEVEN)
        card2 = Card(Suit.HEARTS, Rank.SEVEN)
        card3 = Card(Suit.SPADES, Rank.SEVEN)

        self.assertEqual(card1, card2)
        self.assertNotEqual(card1, card3)

    def test_card_comparison(self):
        """Test card comparison for sorting."""
        card1 = Card(Suit.HEARTS, Rank.TWO)
        card2 = Card(Suit.HEARTS, Rank.ACE)
        card3 = Card(Suit.HEARTS, Rank.KING)

        self.assertLess(card1, card2)
        self.assertLess(card3, card2)
        self.assertGreater(card2, card1)

    def test_face_cards(self):
        """Test face card ranks."""
        # J, Q, K are face cards
        self.assertIn(Rank.JACK.display, ["J"])
        self.assertIn(Rank.QUEEN.display, ["Q"])
        self.assertIn(Rank.KING.display, ["K"])
        # Non-face cards
        self.assertEqual(Rank.SEVEN.display, "7")
        self.assertEqual(Rank.ACE.display, "A")


class TestSuit(unittest.TestCase):
    """Test cases for Suit enum."""

    def test_suit_code(self):
        """Test suit codes."""
        self.assertEqual(Suit.HEARTS.code, "H")
        self.assertEqual(Suit.DIAMONDS.code, "D")
        self.assertEqual(Suit.CLUBS.code, "C")
        self.assertEqual(Suit.SPADES.code, "S")

    def test_suit_from_code(self):
        """Test getting suit from code."""
        self.assertEqual(Suit.from_code("H"), Suit.HEARTS)
        self.assertEqual(Suit.from_code("d"), Suit.DIAMONDS)
        self.assertEqual(Suit.from_code("c"), Suit.CLUBS)
        self.assertEqual(Suit.from_code("S"), Suit.SPADES)


class TestRank(unittest.TestCase):
    """Test cases for Rank enum."""

    def test_rank_display(self):
        """Test rank display values."""
        self.assertEqual(Rank.ACE.display, "A")
        self.assertEqual(Rank.TEN.display, "10")
        self.assertEqual(Rank.JACK.display, "J")

    def test_rank_from_display(self):
        """Test getting rank from display."""
        self.assertEqual(Rank.from_display("A"), Rank.ACE)
        self.assertEqual(Rank.from_display("10"), Rank.TEN)
        self.assertEqual(Rank.from_display("k"), Rank.KING)


if __name__ == "__main__":
    unittest.main()