"""Tests for Player class."""

import unittest
from core.player import Player
from core.card import Card, Suit, Rank


class TestPlayer(unittest.TestCase):
    """Test cases for Player class."""

    def test_player_creation(self):
        """Test creating a player."""
        player = Player(id="test123", name="Alice")
        self.assertEqual(player.id, "test123")
        self.assertEqual(player.name, "Alice")
        self.assertEqual(len(player.hand), 0)

    def test_player_add_card(self):
        """Test adding a card to hand."""
        player = Player(id="test", name="Bob")
        card = Card(Suit.HEARTS, Rank.SEVEN)
        player.add_card(card)

        self.assertEqual(len(player.hand), 1)
        self.assertTrue(player.has_card(card))

    def test_player_remove_card(self):
        """Test removing a card from hand."""
        player = Player(id="test", name="Charlie")
        card = Card(Suit.DIAMONDS, Rank.KING)
        player.add_card(card)

        removed = player.remove_card(card)
        self.assertTrue(removed)
        self.assertEqual(len(player.hand), 0)
        self.assertFalse(player.has_card(card))

    def test_player_remove_card_not_present(self):
        """Test removing a card not in hand."""
        player = Player(id="test", name="Diana")
        card = Card(Suit.CLUBS, Rank.ACE)
        removed = player.remove_card(card)
        self.assertFalse(removed)

    def test_player_get_card_count(self):
        """Test getting card count."""
        player = Player(id="test", name="Eve")
        self.assertEqual(player.get_card_count(), 0)

        player.add_card(Card(Suit.SPADES, Rank.TWO))
        player.add_card(Card(Suit.HEARTS, Rank.THREE))
        self.assertEqual(player.get_card_count(), 2)

    def test_player_is_empty_hand(self):
        """Test empty hand check."""
        player = Player(id="test", name="Frank")
        self.assertTrue(player.is_empty_hand())

        player.add_card(Card(Suit.SPADES, Rank.ACE))
        self.assertFalse(player.is_empty_hand())

    def test_player_sort_hand(self):
        """Test sorting hand."""
        player = Player(id="test", name="Grace")
        player.add_card(Card(Suit.SPADES, Rank.KING))
        player.add_card(Card(Suit.HEARTS, Rank.TWO))
        player.add_card(Card(Suit.DIAMONDS, Rank.ACE))

        player.sort_hand()

        # First card should be the lowest (2 of Hearts)
        self.assertEqual(player.hand[0].rank, Rank.TWO)

    def test_player_to_dict(self):
        """Test serialization."""
        player = Player(id="test", name="Henry")
        player.add_card(Card(Suit.CLUBS, Rank.JACK))

        d = player.to_dict()
        self.assertEqual(d["id"], "test")
        self.assertEqual(d["name"], "Henry")
        self.assertEqual(d["card_count"], 1)
        self.assertNotIn("hand", d)  # Without include_hand

        d_with_hand = player.to_dict(include_hand=True)
        self.assertIn("hand", d_with_hand)
        self.assertEqual(len(d_with_hand["hand"]), 1)


if __name__ == "__main__":
    unittest.main()