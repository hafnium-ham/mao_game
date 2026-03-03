"""Tests for Game class."""

import unittest
from core.game import Game, GamePhase, TurnDirection
from core.player import Player
from core.card import Card, Suit, Rank


class TestGame(unittest.TestCase):
    """Test cases for Game class."""

    def setUp(self):
        """Set up test fixtures."""
        self.game = Game(num_decks=1, min_players=2, cards_per_player=5)

    def test_game_creation(self):
        """Test game initialization."""
        self.assertEqual(self.game.phase, GamePhase.WAITING)
        self.assertEqual(len(self.game.players), 0)
        self.assertIsNone(self.game.draw_pile)

    def test_add_player(self):
        """Test adding players."""
        player1 = Player(id="p1", name="Alice")
        player2 = Player(id="p2", name="Bob")

        self.assertTrue(self.game.add_player(player1))
        self.assertTrue(self.game.add_player(player2))
        self.assertEqual(len(self.game.players), 2)

        # Can't add duplicate
        self.assertFalse(self.game.add_player(player1))

    def test_remove_player(self):
        """Test removing players."""
        player = Player(id="p1", name="Alice")
        self.game.add_player(player)

        self.assertTrue(self.game.remove_player("p1"))
        self.assertEqual(len(self.game.players), 0)

        self.assertFalse(self.game.remove_player("nonexistent"))

    def test_start_game(self):
        """Test starting a game."""
        self.game.add_player(Player(id="p1", name="Alice"))
        self.game.add_player(Player(id="p2", name="Bob"))

        self.assertTrue(self.game.start_game())
        self.assertEqual(self.game.phase, GamePhase.IN_PROGRESS)

        # Players should have cards
        for player in self.game.players:
            self.assertEqual(len(player.hand), 5)

        # Discard pile should have one card
        self.assertEqual(len(self.game.discard_pile), 1)

    def test_cannot_start_with_one_player(self):
        """Test that game can't start with only one player."""
        self.game.add_player(Player(id="p1", name="Alice"))
        self.assertFalse(self.game.start_game())
        self.assertEqual(self.game.phase, GamePhase.WAITING)

    def test_draw_card(self):
        """Test drawing cards."""
        self.game.add_player(Player(id="p1", name="Alice"))
        self.game.add_player(Player(id="p2", name="Bob"))
        self.game.start_game()

        cards = self.game.draw_card("p1", 2)
        self.assertEqual(len(cards), 2)

        player = self.game.get_player("p1")
        self.assertEqual(len(player.hand), 7)  # 5 initial + 2 drawn

    def test_play_card(self):
        """Test playing a card."""
        self.game.add_player(Player(id="p1", name="Alice"))
        self.game.add_player(Player(id="p2", name="Bob"))
        self.game.start_game()

        player = self.game.get_player("p1")
        card = player.hand[0]

        self.assertTrue(self.game.play_card("p1", card))
        self.assertEqual(len(player.hand), 4)
        self.assertEqual(self.game.get_top_card(), card)

    def test_turn_management(self):
        """Test turn advancement."""
        self.game.add_player(Player(id="p1", name="Alice"))
        self.game.add_player(Player(id="p2", name="Bob"))
        self.game.add_player(Player(id="p3", name="Charlie"))
        self.game.start_game()

        initial_index = self.game.current_player_index
        self.game.advance_turn()

        self.assertEqual(
            self.game.current_player_index,
            (initial_index + 1) % 3
        )

    def test_reverse_direction(self):
        """Test reversing turn direction."""
        self.game.add_player(Player(id="p1", name="Alice"))
        self.game.add_player(Player(id="p2", name="Bob"))
        self.game.add_player(Player(id="p3", name="Charlie"))
        self.game.start_game()

        initial_direction = self.game.turn_direction
        self.game.reverse_direction()

        self.assertNotEqual(self.game.turn_direction, initial_direction)

    def test_point_of_order(self):
        """Test Point of Order initiation."""
        self.game.add_player(Player(id="p1", name="Alice"))
        self.game.add_player(Player(id="p2", name="Bob"))
        self.game.start_game()

        self.assertTrue(self.game.initiate_point_of_order("p1", "Testing"))
        self.assertEqual(self.game.phase, GamePhase.POINT_OF_ORDER)
        self.assertIsNotNone(self.game.point_of_order)

        # Can't start another POO
        self.assertFalse(self.game.initiate_point_of_order("p2", "Another"))

    def test_end_point_of_order(self):
        """Test ending Point of Order."""
        self.game.add_player(Player(id="p1", name="Alice"))
        self.game.add_player(Player(id="p2", name="Bob"))
        self.game.start_game()

        self.game.initiate_point_of_order("p1", "Testing")
        self.assertTrue(self.game.end_point_of_order())
        self.assertEqual(self.game.phase, GamePhase.IN_PROGRESS)
        self.assertIsNone(self.game.point_of_order)

    def test_give_penalty(self):
        """Test giving penalties."""
        self.game.add_player(Player(id="p1", name="Alice"))
        self.game.add_player(Player(id="p2", name="Bob"))
        self.game.start_game()

        penalty = self.game.give_penalty("p1", "p2", "Test penalty", 2)
        self.assertIsNotNone(penalty)
        self.assertEqual(penalty.cards, 2)
        self.assertEqual(penalty.reason, "Test penalty")
        self.assertEqual(len(self.game.penalty_history), 1)

    def test_apply_penalty(self):
        """Test applying a penalty (drawing cards)."""
        self.game.add_player(Player(id="p1", name="Alice"))
        self.game.add_player(Player(id="p2", name="Bob"))
        self.game.start_game()

        penalty = self.game.give_penalty("p1", "p2", "Test", 2)
        target = self.game.get_player("p2")
        initial_count = len(target.hand)

        cards = self.game.apply_penalty(penalty.id)
        self.assertEqual(len(cards), 2)
        self.assertEqual(len(target.hand), initial_count + 2)

    def test_mao_declaration(self):
        """Test Mao declaration."""
        self.game.add_player(Player(id="p1", name="Alice"))
        self.game.add_player(Player(id="p2", name="Bob"))
        self.game.start_game()

        self.assertTrue(self.game.start_mao_declaration("p1"))
        self.assertEqual(self.game.mao_declaring_player_id, "p1")

        # Can't declare while another is
        self.assertFalse(self.game.start_mao_declaration("p2"))

        # Cancel
        self.game.cancel_mao_declaration()
        self.assertIsNone(self.game.mao_declaring_player_id)

    def test_knock(self):
        """Test knocking on table."""
        self.game.add_player(Player(id="p1", name="Alice"))
        self.game.start_game()

        self.assertTrue(self.game.knock("p1"))
        self.assertEqual(len(self.game.logs), 2)  # start + knock

    def test_chat(self):
        """Test chat/say."""
        self.game.add_player(Player(id="p1", name="Alice"))
        self.game.start_game()

        self.assertTrue(self.game.chat("p1", "Hello!"))
        self.assertEqual(len(self.game.logs), 2)

    def test_throw_card(self):
        """Test throwing cards at players."""
        self.game.add_player(Player(id="p1", name="Alice"))
        self.game.add_player(Player(id="p2", name="Bob"))
        self.game.start_game()

        p1 = self.game.get_player("p1")
        p2 = self.game.get_player("p2")
        card = p1.hand[0]

        self.assertTrue(self.game.throw_card("p1", card, "p2"))
        self.assertFalse(p1.has_card(card))
        self.assertTrue(p2.has_card(card))

    def test_hit_player(self):
        """Test hitting a player (action only)."""
        self.game.add_player(Player(id="p1", name="Alice"))
        self.game.add_player(Player(id="p2", name="Bob"))
        self.game.start_game()

        self.assertTrue(self.game.hit_player("p1", "p2"))
        # Just an action, no card transfer

    def test_get_recent_cards(self):
        """Test tracking recent played cards."""
        self.game.add_player(Player(id="p1", name="Alice"))
        self.game.add_player(Player(id="p2", name="Bob"))
        self.game.start_game()

        p1 = self.game.get_player("p1")
        card1 = p1.hand[0]
        card2 = p1.hand[1] if len(p1.hand) > 1 else None

        self.game.play_card("p1", card1)
        if card2:
            self.game.play_card("p1", card2)

        recent = self.game.get_recent_cards(2)
        self.assertGreater(len(recent), 0)
        self.assertIn("player_name", recent[0])

    def test_card_effects(self):
        """Test special card effects."""
        self.game.add_player(Player(id="p1", name="Alice"))
        self.game.add_player(Player(id="p2", name="Bob"))
        self.game.add_player(Player(id="p3", name="Charlie"))
        self.game.start_game()

        # Test skip (5)
        self.game.current_player_index = 0
        card = Card(Suit.HEARTS, Rank.FIVE)
        self.game.play_card("p1", card)
        self.assertTrue(self.game.should_skip_next)

        # Note: The actual skip is handled in play_card via _apply_card_effect


class TestPenaltyVoting(unittest.TestCase):
    """Test cases for penalty voting during Point of Order."""

    def setUp(self):
        """Set up test fixtures."""
        self.game = Game(num_decks=1, min_players=2, cards_per_player=5)
        self.game.add_player(Player(id="p1", name="Alice"))
        self.game.add_player(Player(id="p2", name="Bob"))
        self.game.add_player(Player(id="p3", name="Charlie"))
        self.game.start_game()

    def test_start_penalty_vote(self):
        """Test starting a penalty vote during POO."""
        # Give a penalty first
        self.game.give_penalty("p1", "p2", "Test", 1)

        # Start POO
        self.game.initiate_point_of_order("p1", "Dispute")

        # Start vote on penalty 0
        vote = self.game.start_penalty_vote(0)
        self.assertIsNotNone(vote)
        self.assertEqual(vote.penalty_index, 0)

    def test_add_vote(self):
        """Test casting votes."""
        self.game.give_penalty("p1", "p2", "Test", 1)
        self.game.initiate_point_of_order("p1", "Dispute")
        self.game.start_penalty_vote(0)

        self.assertTrue(self.game.add_vote("p1", "uphold"))
        self.assertTrue(self.game.add_vote("p2", "overturn"))

        # Can't vote twice
        self.assertFalse(self.game.add_vote("p1", "overturn"))

    def test_vote_result_uphold(self):
        """Test vote result - upheld."""
        self.game.give_penalty("p1", "p2", "Test", 1)
        self.game.initiate_point_of_order("p1", "Dispute")
        self.game.start_penalty_vote(0)

        self.game.add_vote("p1", "uphold")
        self.game.add_vote("p2", "uphold")
        self.game.add_vote("p3", "uphold")

        result = self.game.check_vote_result()
        self.assertEqual(result, "uphold")

    def test_vote_result_overturn(self):
        """Test vote result - overturned."""
        self.game.give_penalty("p1", "p2", "Test", 1)
        self.game.initiate_point_of_order("p1", "Dispute")
        self.game.start_penalty_vote(0)

        self.game.add_vote("p1", "uphold")
        self.game.add_vote("p2", "overturn")
        self.game.add_vote("p3", "overturn")

        result = self.game.check_vote_result()
        self.assertEqual(result, "overturn")

    def test_cannot_vote_overturned_penalty(self):
        """Test that overturned penalties can't be voted on again."""
        self.game.give_penalty("p1", "p2", "Test", 1)
        self.game.initiate_point_of_order("p1", "Dispute")
        self.game.start_penalty_vote(0)

        self.game.add_vote("p1", "overturn")
        self.game.add_vote("p2", "overturn")
        self.game.add_vote("p3", "overturn")

        result = self.game.check_vote_result()
        self.assertEqual(result, "overturn")

        resolution = self.game.resolve_penalty_vote(result)
        self.assertEqual(resolution["result"], "overturn")

        # Can't vote on same penalty again
        self.game.end_point_of_order()
        self.game.initiate_point_of_order("p1", "New dispute")
        vote = self.game.start_penalty_vote(0)
        self.assertIsNone(vote)  # Should fail - penalty already overturned


if __name__ == "__main__":
    unittest.main()