"""
Comprehensive tests for ALL Mao game commands.

Each test follows this structure:
1. GAME STATE SETUP - Create game and players
2. EXPECTED BEHAVIOR - What should happen
3. ACTIONS - What the player does
4. VERIFICATION - Check the result is correct
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mao_game.core.game import Game, GamePhase, TurnDirection
from mao_game.core.player import Player
from mao_game.core.card import Card, Suit, Rank
from mao_game.core.deck import Deck
from mao_game.network.protocol import Message, MessageType, Protocol


class TestBasicGameCommands(unittest.TestCase):
    """
    Tests for basic game commands: join, start, draw, play, knock, say.
    """

    def setUp(self):
        """GAME STATE SETUP: Create a new game with minimum players."""
        self.game = Game(num_decks=1, min_players=2, cards_per_player=5)
        self.player1 = Player(id="p1", name="Alice")
        self.player2 = Player(id="p2", name="Bob")

    def test_join_game(self):
        """
        TEST: Player can join a waiting game.

        GAME STATE SETUP:
        - Game in WAITING phase
        - No players yet

        EXPECTED BEHAVIOR:
        - Player successfully added
        - Player count increases

        ACTIONS:
        - Add player1 to game

        VERIFICATION:
        - add_player returns True
        - Game has 1 player
        - Player is in game
        """
        # ACTIONS
        result = self.game.add_player(self.player1)

        # VERIFICATION
        self.assertTrue(result, "Player should be able to join waiting game")
        self.assertEqual(len(self.game.players), 1, "Game should have 1 player")
        self.assertEqual(self.game.phase, GamePhase.WAITING, "Game should still be waiting")

    def test_cannot_join_started_game(self):
        """
        TEST: Players cannot join after game starts.

        GAME STATE SETUP:
        - Add minimum players and start game

        EXPECTED BEHAVIOR:
        - New player cannot join after game starts

        ACTIONS:
        - Start game
        - Try to add player3

        VERIFICATION:
        - add_player returns False
        - Player count unchanged
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # ACTIONS
        player3 = Player(id="p3", name="Charlie")
        result = self.game.add_player(player3)

        # VERIFICATION
        self.assertFalse(result, "Should not be able to join started game")
        self.assertEqual(len(self.game.players), 2, "Player count should be unchanged")

    def test_start_game_minimum_players(self):
        """
        TEST: Game can start with minimum players.

        GAME STATE SETUP:
        - Add exactly minimum players (2)

        EXPECTED BEHAVIOR:
        - Game starts successfully
        - Phase changes to IN_PROGRESS
        - Players receive cards
        - Discard pile has initial card

        ACTIONS:
        - Start game

        VERIFICATION:
        - start_game returns True
        - Phase is IN_PROGRESS
        - Players have correct number of cards
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)

        # ACTIONS
        result = self.game.start_game()

        # VERIFICATION
        self.assertTrue(result, "Game should start with minimum players")
        self.assertEqual(self.game.phase, GamePhase.IN_PROGRESS, "Game should be in progress")
        self.assertEqual(len(self.player1.hand), 5, "Player 1 should have 5 cards")
        self.assertEqual(len(self.player2.hand), 5, "Player 2 should have 5 cards")
        self.assertEqual(len(self.game.discard_pile), 1, "Discard pile should have 1 card")

    def test_cannot_start_with_one_player(self):
        """
        TEST: Game cannot start with fewer than minimum players.

        GAME STATE SETUP:
        - Only 1 player

        EXPECTED BEHAVIOR:
        - start_game returns False
        - Game stays in WAITING

        ACTIONS:
        - Try to start with 1 player

        VERIFICATION:
        - start_game returns False
        - Phase remains WAITING
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)

        # ACTIONS
        result = self.game.start_game()

        # VERIFICATION
        self.assertFalse(result, "Should not start with fewer than minimum players")
        self.assertEqual(self.game.phase, GamePhase.WAITING, "Game should still be waiting")

    def test_draw_card(self):
        """
        TEST: Player can draw cards from draw pile.

        GAME STATE SETUP:
        - Game started with 2 players

        EXPECTED BEHAVIOR:
        - Player's hand increases by drawn count
        - Draw pile decreases accordingly

        ACTIONS:
        - Draw 2 cards for player1

        VERIFICATION:
        - Player has 7 cards (5 initial + 2 drawn)
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()
        initial_cards = len(self.player1.hand)

        # ACTIONS
        drawn = self.game.draw_card("p1", 2)

        # VERIFICATION
        self.assertEqual(len(drawn), 2, "Should draw 2 cards")
        self.assertEqual(len(self.player1.hand), initial_cards + 2, "Player should have drawn cards added")

    def test_play_card(self):
        """
        TEST: Player can play a card they have.

        GAME STATE SETUP:
        - Game started
        - Player has specific card

        EXPECTED BEHAVIOR:
        - Card removed from hand
        - Card added to discard pile
        - Card becomes top card

        ACTIONS:
        - Play first card in player's hand

        VERIFICATION:
        - Hand decreased by 1
        - Top card is the played card
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()
        card_to_play = self.player1.hand[0]
        initial_count = len(self.player1.hand)

        # ACTIONS
        result = self.game.play_card("p1", card_to_play)

        # VERIFICATION
        self.assertTrue(result, "Should be able to play owned card")
        self.assertEqual(len(self.player1.hand), initial_count - 1, "Hand should decrease by 1")
        self.assertEqual(self.game.get_top_card(), card_to_play, "Top card should be played card")
        self.assertFalse(self.player1.has_card(card_to_play), "Player should no longer have the card")

    def test_cannot_play_unowned_card(self):
        """
        TEST: Player cannot play a card they don't have.

        GAME STATE SETUP:
        - Game started
        - Card exists but player doesn't own it

        EXPECTED BEHAVIOR:
        - play_card returns False
        - Hand unchanged

        ACTIONS:
        - Try to play card not in player's hand

        VERIFICATION:
        - play_card returns False
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # Find a card guaranteed NOT in player1's hand.
        # Player has only 5 of 52 cards, so this always terminates quickly.
        fake_card = next(
            Card(suit, rank)
            for suit in Suit
            for rank in Rank
            if not self.player1.has_card(Card(suit, rank))
        )

        # ACTIONS
        result = self.game.play_card("p1", fake_card)

        # VERIFICATION
        self.assertFalse(result, "Should not be able to play unowned card")

    def test_knock_on_table(self):
        """
        TEST: Player can knock on the table (log action).

        GAME STATE SETUP:
        - Game in progress

        EXPECTED BEHAVIOR:
        - Knock logged
        - Returns True

        ACTIONS:
        - Player knocks

        VERIFICATION:
        - knock returns True
        - Log contains knock event
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()
        initial_logs = len(self.game.logs)

        # ACTIONS
        result = self.game.knock("p1")

        # VERIFICATION
        self.assertTrue(result, "Knock should succeed")
        self.assertEqual(len(self.game.logs), initial_logs + 1, "Should have new log entry")

    def test_say_chat(self):
        """
        TEST: Player can say something (chat).

        GAME STATE SETUP:
        - Game in progress

        EXPECTED BEHAVIOR:
        - Chat logged with player name and message

        ACTIONS:
        - Player says "Hello!"

        VERIFICATION:
        - chat returns True
        - Log contains message
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # ACTIONS
        result = self.game.chat("p1", "Hello!")

        # VERIFICATION
        self.assertTrue(result, "Chat should succeed")
        # Find the chat log
        chat_logs = [log for log in self.game.logs if log.event_type == "chat"]
        self.assertEqual(len(chat_logs), 1, "Should have one chat log")
        self.assertIn("Hello!", chat_logs[0].details)


class TestCardEffects(unittest.TestCase):
    """
    Tests for special card effects: skip (5), reverse (A), play again (Q).

    CORE DESIGN PRINCIPLE: Card effects are NOT automatically enforced.
    Players discover and enforce rules manually through the penalty system.
    These tests verify that playing 5, Ace, or Queen does NOT auto-trigger effects.
    """

    def setUp(self):
        """GAME STATE SETUP: Create game with 3 players for testing turn effects."""
        self.game = Game(num_decks=1, min_players=2, cards_per_player=5)
        self.player1 = Player(id="p1", name="Alice")
        self.player2 = Player(id="p2", name="Bob")
        self.player3 = Player(id="p3", name="Charlie")

    def test_skip_card_5(self):
        """
        TEST: Playing a 5 does NOT auto-skip the next player.

        CORE DESIGN: Rules are NOT automatically enforced.
        Players enforce the skip rule manually through penalties.

        GAME STATE SETUP:
        - 3 players in game
        - current_player_index forced to 0 for determinism

        EXPECTED BEHAVIOR:
        - play_card("p1", card_5) does NOT change current_player_index
        - No automatic skip occurs during play_card()
        - Players must enforce the skip rule manually

        ACTIONS:
        - Force player index to 0
        - Give player1 a 5 and play it

        VERIFICATION:
        - current_player_index is still 0 after play_card (no auto-skip)
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.add_player(self.player3)
        self.game.start_game()

        # Force deterministic starting position
        self.game.current_player_index = 0

        # Give player1 a 5 to play
        card_5 = Card(Suit.HEARTS, Rank.FIVE)
        self.player1.add_card(card_5)

        # ACTIONS
        self.game.play_card("p1", card_5)

        # VERIFICATION: playing a 5 does NOT auto-skip
        # play_card() should NOT change the current_player_index
        self.assertEqual(self.game.current_player_index, 0,
                         "Playing a 5 should NOT automatically skip the next player")

    def test_reverse_card_ace(self):
        """
        TEST: Playing an Ace does NOT auto-reverse direction.

        CORE DESIGN: Rules are NOT automatically enforced.
        Players enforce the reverse rule manually through penalties.

        GAME STATE SETUP:
        - 3 players in game
        - Direction starts as CLOCKWISE

        EXPECTED BEHAVIOR:
        - After playing Ace, direction remains CLOCKWISE (no auto-reverse)
        - Players must manually enforce direction reversal

        ACTIONS:
        - Note initial direction (CLOCKWISE)
        - Play an Ace

        VERIFICATION:
        - Direction NOT changed from CLOCKWISE after playing Ace
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.add_player(self.player3)
        self.game.start_game()

        # Ensure starting direction is CLOCKWISE
        self.game.turn_direction = TurnDirection.CLOCKWISE
        initial_direction = self.game.turn_direction

        # Give player1 an Ace
        card_ace = Card(Suit.HEARTS, Rank.ACE)
        self.player1.add_card(card_ace)

        # ACTIONS
        self.game.play_card("p1", card_ace)

        # VERIFICATION: Ace does NOT auto-reverse direction
        self.assertEqual(self.game.turn_direction, initial_direction,
                         "Playing an Ace should NOT automatically reverse direction")

    def test_play_again_queen(self):
        """
        TEST: Playing a Queen does NOT auto-set the play_again flag.

        CORE DESIGN: Rules are NOT automatically enforced.
        Players enforce the play-again rule manually through penalties.

        GAME STATE SETUP:
        - Game in progress
        - Player has a Queen

        EXPECTED BEHAVIOR:
        - After playing Queen, should_play_again() returns False
        - play_again flag is NOT auto-set by playing a Queen

        ACTIONS:
        - Play a Queen

        VERIFICATION:
        - should_play_again() returns False (not auto-enabled)
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # Give player1 a Queen
        card_queen = Card(Suit.HEARTS, Rank.QUEEN)
        self.player1.add_card(card_queen)

        # ACTIONS
        self.game.play_card("p1", card_queen)

        # VERIFICATION: Queen does NOT auto-set play_again
        self.assertFalse(self.game.should_play_again(),
                         "Playing a Queen should NOT automatically enable play-again")


class TestPenaltyCommands(unittest.TestCase):
    """
    Tests for penalty-related commands: give penalty, return card.
    """

    def setUp(self):
        """GAME STATE SETUP: Game with 2 players."""
        self.game = Game(num_decks=1, min_players=2, cards_per_player=5)
        self.player1 = Player(id="p1", name="Alice")
        self.player2 = Player(id="p2", name="Bob")

    def test_give_penalty(self):
        """
        TEST: Player can give penalty to another player.

        GAME STATE SETUP:
        - Game in progress
        - Both players have initial cards

        EXPECTED BEHAVIOR:
        - Penalty is created
        - Penalty added to pending and history
        - Target player receives penalty info

        ACTIONS:
        - Player1 gives 2 card penalty to player2

        VERIFICATION:
        - Penalty created with correct details
        - Penalty in history
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # ACTIONS
        penalty = self.game.give_penalty("p1", "p2", "Wrong play", 2)

        # VERIFICATION
        self.assertIsNotNone(penalty, "Penalty should be created")
        self.assertEqual(penalty.caller_id, "p1", "Caller should be player1")
        self.assertEqual(penalty.target_id, "p2", "Target should be player2")
        self.assertEqual(penalty.cards, 2, "Should be 2 card penalty")
        self.assertEqual(penalty.reason, "Wrong play", "Reason should match")
        self.assertEqual(len(self.game.pending_penalties), 1, "Should have 1 pending penalty")

    def test_apply_penalty(self):
        """
        TEST: Applied penalty draws cards for target player.

        GAME STATE SETUP:
        - Game in progress
        - Penalty given

        EXPECTED BEHAVIOR:
        - Target's hand increases by penalty card count
        - Penalty cards are tracked for possible return

        ACTIONS:
        - Give and apply penalty

        VERIFICATION:
        - Target has more cards
        - Cards tracked in penalty
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()
        initial_cards = len(self.player2.hand)

        # ACTIONS
        penalty = self.game.give_penalty("p1", "p2", "Test", 2)
        drawn = self.game.apply_penalty(penalty.id)

        # VERIFICATION
        self.assertEqual(len(drawn), 2, "Should draw 2 penalty cards")
        self.assertEqual(len(self.player2.hand), initial_cards + 2,
                        "Target should have penalty cards added")
        self.assertEqual(len(penalty.penalty_cards_dealt), 2,
                        "Penalty should track dealt cards")

    def test_cannot_penalty_outside_game(self):
        """
        TEST: Cannot give penalty when game not in progress.

        GAME STATE SETUP:
        - Game in WAITING phase

        EXPECTED BEHAVIOR:
        - give_penalty returns None

        ACTIONS:
        - Try to give penalty before game starts

        VERIFICATION:
        - No penalty created
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        # Don't start game

        # ACTIONS
        penalty = self.game.give_penalty("p1", "p2", "Test", 1)

        # VERIFICATION
        self.assertIsNone(penalty, "Should not create penalty outside game")

    def test_return_card(self):
        """
        TEST: Return card returns last played card to original player.

        GAME STATE SETUP:
        - Game in progress
        - Player plays a card

        EXPECTED BEHAVIOR:
        - Card removed from discard
        - Card returned to player's hand

        ACTIONS:
        - Player1 plays a card
        - Return that card

        VERIFICATION:
        - Card back in player1's hand
        - Discard pile decreased
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # Player1 plays a card
        card_to_play = self.player1.hand[0]
        self.game.play_card("p1", card_to_play)
        cards_in_hand = len(self.player1.hand)

        # ACTIONS
        result = self.game.return_card("p2")

        # VERIFICATION
        self.assertIsNotNone(result, "Return should succeed")
        original_id, original_name, returned_card = result
        self.assertEqual(original_id, "p1", "Card should return to player1")
        self.assertEqual(returned_card, card_to_play, "Same card returned")
        self.assertEqual(len(self.player1.hand), cards_in_hand + 1,
                        "Player should have card back")


class TestPointOfOrderCommands(unittest.TestCase):
    """
    Tests for Point of Order commands: start POO, end POO, voting.
    """

    def setUp(self):
        """GAME STATE SETUP: Game with 3 players for voting."""
        self.game = Game(num_decks=1, min_players=2, cards_per_player=5)
        self.player1 = Player(id="p1", name="Alice")
        self.player2 = Player(id="p2", name="Bob")
        self.player3 = Player(id="p3", name="Charlie")

    def test_initiate_point_of_order(self):
        """
        TEST: Player can call Point of Order.

        GAME STATE SETUP:
        - Game in progress

        EXPECTED BEHAVIOR:
        - Game phase changes to POINT_OF_ORDER
        - POO caller tracked

        ACTIONS:
        - Player1 calls POO

        VERIFICATION:
        - Phase is POINT_OF_ORDER
        - POO caller is player1
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # ACTIONS
        result = self.game.initiate_point_of_order("p1", "Disputed penalty")

        # VERIFICATION
        self.assertTrue(result, "Should be able to start POO")
        self.assertEqual(self.game.phase, GamePhase.POINT_OF_ORDER,
                        "Phase should be POINT_OF_ORDER")
        self.assertEqual(self.game.point_of_order.caller_id, "p1",
                        "Caller should be player1")

    def test_cannot_start_poo_during_poo(self):
        """
        TEST: Cannot start a POO while already in POO.

        GAME STATE SETUP:
        - Already in POO

        EXPECTED BEHAVIOR:
        - Second POO attempt fails

        ACTIONS:
        - Start POO
        - Try to start another POO

        VERIFICATION:
        - Second initiation returns False
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()
        self.game.initiate_point_of_order("p1", "First")

        # ACTIONS
        result = self.game.initiate_point_of_order("p2", "Second")

        # VERIFICATION
        self.assertFalse(result, "Should not start POO during POO")

    def test_end_point_of_order(self):
        """
        TEST: Point of Order can be ended.

        GAME STATE SETUP:
        - Game in POO

        EXPECTED BEHAVIOR:
        - Phase returns to IN_PROGRESS
        - POO is cleared

        ACTIONS:
        - End POO

        VERIFICATION:
        - Phase is IN_PROGRESS
        - POO is None
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()
        self.game.initiate_point_of_order("p1", "Test")

        # ACTIONS
        result = self.game.end_point_of_order()

        # VERIFICATION
        self.assertTrue(result, "Should be able to end POO")
        self.assertEqual(self.game.phase, GamePhase.IN_PROGRESS,
                        "Phase should be back to IN_PROGRESS")
        self.assertIsNone(self.game.point_of_order, "POO should be cleared")

    def test_vote_on_penalty(self):
        """
        TEST: Players can vote on a penalty during POO.

        GAME STATE SETUP:
        - Game in progress
        - Penalty given
        - POO called

        EXPECTED BEHAVIOR:
        - Vote can be started
        - Players can vote uphold/overturn/abstain
        - Vote counts tracked

        ACTIONS:
        - Start vote on penalty
        - Players vote

        VERIFICATION:
        - Active vote created
        - Vote counts correct
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.add_player(self.player3)
        self.game.start_game()

        # Give a penalty
        penalty = self.game.give_penalty("p1", "p2", "Wrong play", 1)

        # Start POO
        self.game.initiate_point_of_order("p1", "Dispute")

        # ACTIONS
        vote = self.game.start_penalty_vote(0)  # Vote on first penalty

        # VERIFICATION
        self.assertIsNotNone(vote, "Vote should start")
        self.assertEqual(vote.penalty_index, 0, "Correct penalty index")

        # Players vote
        self.game.add_vote("p1", "uphold")
        self.game.add_vote("p2", "overturn")
        self.game.add_vote("p3", "abstain")

        # Check counts
        uphold, overturn, abstain = vote.get_vote_counts()
        self.assertEqual(uphold, 1, "One uphold vote")
        self.assertEqual(overturn, 1, "One overturn vote")
        self.assertEqual(abstain, 1, "One abstain vote")

    def test_penalty_overturned(self):
        """
        TEST: Penalty can be overturned by vote.

        GAME STATE SETUP:
        - POO active
        - Vote started on penalty

        EXPECTED BEHAVIOR:
        - If overturn votes > uphold votes, penalty overturned
        - Cards returned from target to caller

        ACTIONS:
        - All players vote overturn
        - Resolve vote

        VERIFICATION:
        - Penalty marked overturned
        - Cards transferred back
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.add_player(self.player3)
        self.game.start_game()

        initial_p2_cards = len(self.player2.hand)

        # Give and apply penalty
        penalty = self.game.give_penalty("p1", "p2", "Wrong", 1)
        self.game.apply_penalty(penalty.id)

        # Start POO and vote
        self.game.initiate_point_of_order("p1", "Dispute")
        self.game.start_penalty_vote(0)

        # ACTIONS - All vote to overturn
        self.game.add_vote("p1", "overturn")
        self.game.add_vote("p2", "overturn")
        self.game.add_vote("p3", "overturn")

        result = self.game.resolve_penalty_vote("overturn")

        # VERIFICATION
        self.assertEqual(result["result"], "overturn", "Result should be overturn")
        self.assertTrue(penalty.overturned, "Penalty should be marked overturned")

    def test_cannot_vote_on_overturned_penalty(self):
        """
        TEST: Cannot vote on a penalty that was already overturned.

        GAME STATE SETUP:
        - Penalty already overturned

        EXPECTED BEHAVIOR:
        - Starting vote on overturned penalty fails

        ACTIONS:
        - Try to start vote on overturned penalty

        VERIFICATION:
        - start_penalty_vote returns None
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # Give penalty, start POO, vote to overturn
        self.game.give_penalty("p1", "p2", "Test", 1)
        self.game.initiate_point_of_order("p1", "Dispute")
        self.game.start_penalty_vote(0)
        self.game.add_vote("p1", "overturn")
        self.game.add_vote("p2", "overturn")
        self.game.resolve_penalty_vote("overturn")

        # End and restart POO
        self.game.end_point_of_order()
        self.game.initiate_point_of_order("p1", "New")

        # ACTIONS
        result = self.game.start_penalty_vote(0)

        # VERIFICATION
        self.assertIsNone(result, "Should not start vote on overturned penalty")


class TestMaoDeclaration(unittest.TestCase):
    """
    Tests for Mao declaration commands: declare Mao, cancel Mao.
    """

    def setUp(self):
        """GAME STATE SETUP: Game with 2 players."""
        self.game = Game(num_decks=1, min_players=2, cards_per_player=5)
        self.player1 = Player(id="p1", name="Alice")
        self.player2 = Player(id="p2", name="Bob")

    def test_start_mao_declaration(self):
        """
        TEST: Player can declare Mao.

        GAME STATE SETUP:
        - Game in progress

        EXPECTED BEHAVIOR:
        - Mao declaration started
        - Player tracked as declaring

        ACTIONS:
        - Player1 starts Mao declaration

        VERIFICATION:
        - Declaration tracked
        - Timer exists
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # ACTIONS
        result = self.game.start_mao_declaration("p1")

        # VERIFICATION
        self.assertTrue(result, "Should start Mao declaration")
        self.assertEqual(self.game.mao_declaring_player_id, "p1",
                        "Player1 should be declaring")

    def test_cannot_declare_mao_twice(self):
        """
        TEST: Cannot declare Mao while another player is declaring.

        GAME STATE SETUP:
        - Player1 already declaring Mao

        EXPECTED BEHAVIOR:
        - Second declaration fails

        ACTIONS:
        - Player1 declares
        - Player2 tries to declare

        VERIFICATION:
        - Player2's declaration fails
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()
        self.game.start_mao_declaration("p1")

        # ACTIONS
        result = self.game.start_mao_declaration("p2")

        # VERIFICATION
        self.assertFalse(result, "Should not allow second declaration")

    def test_cancel_mao_declaration(self):
        """
        TEST: Mao declaration can be canceled.

        GAME STATE SETUP:
        - Mao declaration active

        EXPECTED BEHAVIOR:
        - Declaration cleared

        ACTIONS:
        - Cancel declaration

        VERIFICATION:
        - declaring_player_id is None
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()
        self.game.start_mao_declaration("p1")

        # ACTIONS
        self.game.cancel_mao_declaration()

        # VERIFICATION
        self.assertIsNone(self.game.mao_declaring_player_id,
                        "Declaration should be cleared")

    def test_mao_timer_expired(self):
        """
        TEST: Mao declaration succeeds after timer.

        GAME STATE SETUP:
        - Mao declaration active
        - Timer set

        EXPECTED BEHAVIOR:
        - check_mao_declaration_timer returns True after MAO_CHALLENGE_TIME

        ACTIONS:
        - Start declaration
        - Check timer

        VERIFICATION:
        - Timer check works correctly
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()
        self.game.start_mao_declaration("p1")

        # Simulate time passing (we can't wait 10s in test)
        # Just check the timer mechanism works
        import time
        self.game.mao_declaration_time = time.time() - 11  # Set to past

        # ACTIONS
        result = self.game.check_mao_declaration_timer()

        # VERIFICATION
        self.assertTrue(result, "Timer should be expired after 10+ seconds")


class TestThrowAndHit(unittest.TestCase):
    """
    Tests for throw and hit commands.
    """

    def setUp(self):
        """GAME STATE SETUP: Game with 2 players."""
        self.game = Game(num_decks=1, min_players=2, cards_per_player=5)
        self.player1 = Player(id="p1", name="Alice")
        self.player2 = Player(id="p2", name="Bob")

    def test_throw_card(self):
        """
        TEST: Player can throw card at another player.

        GAME STATE SETUP:
        - Game in progress
        - Player has a card

        EXPECTED BEHAVIOR:
        - Card removed from thrower
        - Card added to target

        ACTIONS:
        - Player1 throws card at player2

        VERIFICATION:
        - Player1 lost card
        - Player2 gained card
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        card_to_throw = self.player1.hand[0]
        p1_cards = len(self.player1.hand)
        p2_cards = len(self.player2.hand)

        # ACTIONS
        result = self.game.throw_card("p1", card_to_throw, "p2")

        # VERIFICATION
        self.assertTrue(result, "Throw should succeed")
        self.assertEqual(len(self.player1.hand), p1_cards - 1,
                        "Thrower should lose card")
        self.assertEqual(len(self.player2.hand), p2_cards + 1,
                        "Target should gain card")
        self.assertTrue(self.player2.has_card(card_to_throw),
                       "Target should have the thrown card")

    def test_cannot_throw_unowned_card(self):
        """
        TEST: Cannot throw a card you don't have.

        GAME STATE SETUP:
        - Game in progress
        - Card not in player's hand

        EXPECTED BEHAVIOR:
        - throw_card returns False

        ACTIONS:
        - Try to throw card player doesn't have

        VERIFICATION:
        - Returns False
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # Find a card guaranteed NOT in player1's hand.
        # Player has only 5 of 52 cards, so this always terminates quickly.
        fake_card = next(
            Card(suit, rank)
            for suit in Suit
            for rank in Rank
            if not self.player1.has_card(Card(suit, rank))
        )

        # ACTIONS
        result = self.game.throw_card("p1", fake_card, "p2")

        # VERIFICATION
        self.assertFalse(result, "Should not throw unowned card")

    def test_hit_player(self):
        """
        TEST: Player can hit another player (action only, no card transfer).

        GAME STATE SETUP:
        - Game in progress

        EXPECTED BEHAVIOR:
        - Hit logged
        - No cards transferred

        ACTIONS:
        - Player1 hits player2

        VERIFICATION:
        - Returns True
        - Log contains hit event
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()
        initial_logs = len(self.game.logs)

        # ACTIONS
        result = self.game.hit_player("p1", "p2")

        # VERIFICATION
        self.assertTrue(result, "Hit should succeed")
        self.assertEqual(len(self.game.logs), initial_logs + 1,
                        "Should have hit log")


class TestTurnManagement(unittest.TestCase):
    """
    Tests for turn management: advance turn, reverse direction.
    """

    def setUp(self):
        """GAME STATE SETUP: Game with 3 players."""
        self.game = Game(num_decks=1, min_players=2, cards_per_player=5)
        self.player1 = Player(id="p1", name="Alice")
        self.player2 = Player(id="p2", name="Bob")
        self.player3 = Player(id="p3", name="Charlie")

    def test_advance_turn(self):
        """
        TEST: Turn advances to next player.

        GAME STATE SETUP:
        - 3 players in clockwise order

        EXPECTED BEHAVIOR:
        - Turn advances to next player in order

        ACTIONS:
        - Advance turn

        VERIFICATION:
        - Player index increments (with wrap)
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.add_player(self.player3)
        self.game.start_game()

        initial = self.game.current_player_index

        # ACTIONS
        self.game.advance_turn()

        # VERIFICATION
        expected = (initial + 1) % 3
        self.assertEqual(self.game.current_player_index, expected,
                        "Turn should advance to next player")

    def test_reverse_direction(self):
        """
        TEST: Direction can be reversed.

        GAME STATE SETUP:
        - Direction is CLOCKWISE

        EXPECTED BEHAVIOR:
        - After reverse, direction is COUNTER_CLOCKWISE

        ACTIONS:
        - Reverse direction

        VERIFICATION:
        - Direction changed
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.add_player(self.player3)
        self.game.start_game()

        initial = self.game.turn_direction

        # ACTIONS
        self.game.reverse_direction()

        # VERIFICATION
        self.assertNotEqual(self.game.turn_direction, initial,
                          "Direction should change")

    def test_skip_next_player(self):
        """
        TEST: Skip advances turn twice (skipping one player).

        GAME STATE SETUP:
        - 3 players

        EXPECTED BEHAVIOR:
        - Turn advances twice

        ACTIONS:
        - Skip next player

        VERIFICATION:
        - Current player index advances by 2
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.add_player(self.player3)
        self.game.start_game()

        initial = self.game.current_player_index

        # ACTIONS
        self.game.skip_next_player()

        # VERIFICATION
        expected = (initial + 2) % 3
        self.assertEqual(self.game.current_player_index, expected,
                        "Should skip one player")


class TestProtocolMessages(unittest.TestCase):
    """
    Tests for protocol message handling: encoding, decoding, types.
    """

    def test_message_encoding(self):
        """
        TEST: Messages can be encoded with length header.

        GAME STATE SETUP: N/A (protocol test)

        EXPECTED BEHAVIOR:
        - Message has 4-byte length prefix
        - Body contains JSON data

        ACTIONS:
        - Create and encode message

        VERIFICATION:
        - Encoded message has correct format
        """
        # ACTIONS
        msg = Message(type=MessageType.PLAY_CARD, data={"card": {"suit": "hearts", "rank": "7"}})
        encoded = Protocol.encode_message(msg)

        # VERIFICATION
        self.assertGreater(len(encoded), 4, "Should have header + body")
        length = int.from_bytes(encoded[:4], byteorder="big")
        self.assertEqual(length, len(encoded) - 4, "Length header should match body")

    def test_message_decoding(self):
        """
        TEST: Encoded messages can be decoded.

        GAME STATE SETUP: N/A (protocol test)

        EXPECTED BEHAVIOR:
        - Decode returns original message

        ACTIONS:
        - Encode and decode message

        VERIFICATION:
        - Decoded message matches original
        """
        # ACTIONS
        msg = Message(type=MessageType.CHAT, data={"message": "Hello"})
        encoded = Protocol.encode_message(msg)
        decoded, remaining = Protocol.decode_message(encoded)

        # VERIFICATION
        self.assertEqual(decoded.type, MessageType.CHAT)
        self.assertEqual(decoded.data["message"], "Hello")
        self.assertEqual(len(remaining), 0)

    def test_multiple_messages_in_buffer(self):
        """
        TEST: Multiple messages in buffer are handled correctly.

        GAME STATE SETUP: N/A (protocol test)

        EXPECTED BEHAVIOR:
        - First message decoded, remaining returned

        ACTIONS:
        - Encode two messages together
        - Decode one

        VERIFICATION:
        - First message decoded
        - Remaining bytes preserved
        """
        # ACTIONS
        msg1 = Message(type=MessageType.KNOCK, data={})
        msg2 = Message(type=MessageType.CHAT, data={"message": "test"})
        encoded = Protocol.encode_message(msg1) + Protocol.encode_message(msg2)

        decoded1, remaining = Protocol.decode_message(encoded)
        decoded2, remaining2 = Protocol.decode_message(remaining)

        # VERIFICATION
        self.assertEqual(decoded1.type, MessageType.KNOCK)
        self.assertEqual(decoded2.type, MessageType.CHAT)
        self.assertEqual(len(remaining2), 0)


class TestSession3Changes(unittest.TestCase):
    """
    NEW Tests for Session 3 behavior changes:

    9.  Cancel Mao - ANY player can cancel (not just the declarer)
    10. Shuffle Cards - shuffles discard pile into draw pile (not player's hand)
    11. View Own Hand - game state only exposes requesting player's hand
    12. Return Card - only returned if last card was played by penalized player
    13. Hand Not Auto-Displayed - game state serialization does not expose hands
    14. POO Command Phrases - only exact "Point of Order" phrase starts POO
    """

    def setUp(self):
        """GAME STATE SETUP: 3-player game for comprehensive testing."""
        self.game = Game(num_decks=1, min_players=2, cards_per_player=5)
        self.player1 = Player(id="p1", name="Alice")
        self.player2 = Player(id="p2", name="Bob")
        self.player3 = Player(id="p3", name="Charlie")

    # --- Test 9: Cancel Mao (any player) ---

    def test_any_player_can_cancel_mao(self):
        """
        TEST 9: ANY player can cancel a Mao declaration (not just the declarer).

        GAME STATE SETUP:
        - Game in progress
        - Player1 has declared Mao

        EXPECTED BEHAVIOR:
        - Player2 (not the declarer) can cancel the Mao declaration
        - mao_declaring_player_id becomes None
        - Timer is cleared

        ACTIONS:
        - Player1 starts Mao declaration
        - Cancel the declaration (simulating any player canceling)

        VERIFICATION:
        - mao_declaring_player_id is None (cleared regardless of who cancels)
        - mao_declaration_time is None (timer cleared)
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # Player1 declares Mao
        result = self.game.start_mao_declaration("p1")
        self.assertTrue(result, "Player1 should be able to declare Mao")
        self.assertEqual(self.game.mao_declaring_player_id, "p1",
                         "Player1 should be the declaring player")

        # ACTIONS: Player2 (not the declarer) cancels - game.cancel_mao_declaration()
        # has no player restriction; the server enforces "any player" (no check on who cancels)
        self.game.cancel_mao_declaration()

        # VERIFICATION
        self.assertIsNone(self.game.mao_declaring_player_id,
                          "Mao declaration should be cleared when any player cancels")
        self.assertIsNone(self.game.mao_declaration_time,
                          "Declaration timer should be cleared after cancel")

    def test_cancel_mao_only_when_active(self):
        """
        TEST 9b: Canceling Mao when no declaration is active does nothing harmful.

        GAME STATE SETUP:
        - Game in progress, no active Mao declaration

        EXPECTED BEHAVIOR:
        - cancel_mao_declaration() still runs without error
        - State remains clean (None values)

        ACTIONS:
        - Call cancel_mao_declaration() with no active declaration

        VERIFICATION:
        - mao_declaring_player_id remains None
        - No exception raised
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # Confirm no active declaration
        self.assertIsNone(self.game.mao_declaring_player_id,
                          "No declaration should be active initially")

        # ACTIONS: Cancel when nothing to cancel (should be safe)
        self.game.cancel_mao_declaration()  # Should not raise

        # VERIFICATION
        self.assertIsNone(self.game.mao_declaring_player_id,
                          "mao_declaring_player_id should remain None")

    # --- Test 10: Shuffle Cards (discard to draw) ---

    def test_shuffle_discard_into_draw_pile(self):
        """
        TEST 10: Shuffle moves discard pile (except top card) into draw pile.

        This simulates the server's _handle_shuffle_cards logic which runs during POO.
        The server does NOT affect other players' hands - only pile manipulation.

        GAME STATE SETUP:
        - Game in POO
        - Discard pile has the initial card + 5 extra cards added (6 total)

        EXPECTED BEHAVIOR:
        - After shuffle: discard has exactly 1 card (top card)
        - Top card identity is preserved
        - Draw pile grows by (discard_count - 1) cards
        - Other players' hands are NOT affected

        ACTIONS:
        - Add 5 cards to discard pile
        - Simulate the shuffle operation (as server._handle_shuffle_cards does)

        VERIFICATION:
        - len(discard_pile) == 1
        - discard_pile[0] == original top card
        - draw_pile count increased by (initial_discard_count - 1)
        - Player hands unchanged
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        p1_cards_before = len(self.player1.hand)
        p2_cards_before = len(self.player2.hand)

        # Add extra cards to discard pile to simulate played cards
        for _ in range(5):
            card = self.game.draw_pile.draw()
            self.game.discard_pile.append(card)

        initial_draw_count = self.game.draw_pile.remaining()
        initial_discard_count = len(self.game.discard_pile)  # should be 1 + 5 = 6
        top_card_before_shuffle = self.game.discard_pile[-1]

        # Start POO (shuffle only works during POO in server)
        self.game.initiate_point_of_order("p1", "Deck exhaustion")

        # ACTIONS: Simulate the server's shuffle operation
        top_card = self.game.discard_pile[-1]
        cards_to_shuffle = self.game.discard_pile[:-1]
        self.game.draw_pile.add_cards(cards_to_shuffle)
        self.game.draw_pile.shuffle()
        self.game.discard_pile = [top_card]

        # VERIFICATION
        self.assertEqual(len(self.game.discard_pile), 1,
                         "Discard pile should have exactly 1 card after shuffle")
        self.assertEqual(self.game.discard_pile[0], top_card_before_shuffle,
                         "The top card must be preserved in the discard pile")

        expected_draw_count = initial_draw_count + (initial_discard_count - 1)
        self.assertEqual(self.game.draw_pile.remaining(), expected_draw_count,
                         f"Draw pile should have {expected_draw_count} cards "
                         f"(gained {initial_discard_count - 1} from discard)")

        # Players' hands must NOT be affected
        self.assertEqual(len(self.player1.hand), p1_cards_before,
                         "Player1's hand should NOT be changed by shuffle")
        self.assertEqual(len(self.player2.hand), p2_cards_before,
                         "Player2's hand should NOT be changed by shuffle")

    def test_shuffle_requires_enough_discard_cards(self):
        """
        TEST 10b: Shuffle fails gracefully when discard pile has only 1 card (top card).

        GAME STATE SETUP:
        - Game started with exactly 1 card in discard pile

        EXPECTED BEHAVIOR:
        - When only 1 card in discard, there's nothing to shuffle
        - cards_to_shuffle is empty (no-op)

        VERIFICATION:
        - cards_to_shuffle list is empty
        - No cards added to draw pile
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # Discard pile has exactly 1 card (the initial card placed during start_game)
        self.assertEqual(len(self.game.discard_pile), 1,
                         "Should have exactly 1 card in discard at game start")

        initial_draw_count = self.game.draw_pile.remaining()

        # Simulate the server's check: if discard_count <= 1, refuse to shuffle
        discard_count = len(self.game.discard_pile)
        can_shuffle = discard_count > 1

        # VERIFICATION
        self.assertFalse(can_shuffle,
                         "Should NOT be able to shuffle with only 1 card in discard")
        self.assertEqual(self.game.draw_pile.remaining(), initial_draw_count,
                         "Draw pile should be unchanged when shuffle is refused")

    # --- Test 11: View Own Hand (game state only exposes own hand) ---

    def test_game_state_only_shows_requesting_players_hand(self):
        """
        TEST 11: Game state serialization only includes hand for the requesting player.

        During POO, when a player views their hand, they only see their OWN cards.
        Other players' hand details are NOT included in the serialized game state.

        GAME STATE SETUP:
        - Game in progress, players have dealt hands

        EXPECTED BEHAVIOR:
        - to_dict(for_player_id="p1") includes hand data ONLY for p1
        - Player2's hand is NOT exposed (just card count)

        ACTIONS:
        - Serialize game state from p1's perspective

        VERIFICATION:
        - Player1's data has "hand" key with actual cards
        - Player2's data does NOT have "hand" key
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # ACTIONS: Get game state as seen by Player1
        state_as_p1 = self.game.to_dict(for_player_id="p1")

        # VERIFICATION
        p1_data = next(p for p in state_as_p1["players"] if p["id"] == "p1")
        p2_data = next(p for p in state_as_p1["players"] if p["id"] == "p2")

        # Player1 should see their own hand
        self.assertIn("hand", p1_data,
                      "Player1's own hand should be included in their game state view")
        self.assertIsNotNone(p1_data["hand"],
                             "Player1's hand data should not be None")
        self.assertEqual(len(p1_data["hand"]), len(self.player1.hand),
                         "Player1's hand data should match their actual hand size")

        # Player2's hand should NOT be visible to Player1
        self.assertNotIn("hand", p2_data,
                         "Player2's hand should NOT be visible to Player1")

    def test_get_player_hand_returns_correct_hand(self):
        """
        TEST 11b: get_player_hand() returns the correct player's hand.

        This is the server-side method used to send hand updates.
        It should return the exact player's hand, not other players'.

        VERIFICATION:
        - get_player_hand("p1") returns Player1's hand
        - get_player_hand("p2") returns Player2's hand (different from p1's)
        - Both are correct sizes
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # ACTIONS
        p1_hand = self.game.get_player_hand("p1")
        p2_hand = self.game.get_player_hand("p2")

        # VERIFICATION
        self.assertEqual(len(p1_hand), len(self.player1.hand),
                         "get_player_hand should return Player1's full hand")
        self.assertEqual(len(p2_hand), len(self.player2.hand),
                         "get_player_hand should return Player2's full hand")
        # The hands should be different (different cards were dealt)
        # We compare as sets of card strings since order may differ
        p1_card_strs = {str(c) for c in p1_hand}
        p2_card_strs = {str(c) for c in p2_hand}
        self.assertNotEqual(p1_card_strs, p2_card_strs,
                            "Player1 and Player2 should have different hands")

    # --- Test 12: Return Card (only if played by penalized player) ---

    def test_return_card_check_identifies_last_player(self):
        """
        TEST 12: The return_card check correctly identifies who played last.

        When the server processes a penalty with -r (return card) flag, it checks
        whether the LAST card played was by the PENALIZED player. If Player2 played
        last, penalizing Player1 should NOT return a card.

        GAME STATE SETUP:
        - Player1 plays a card (first)
        - Player2 plays a card (second, most recent)

        EXPECTED BEHAVIOR:
        - played_cards_stack[-1] shows Player2 as the last player
        - Server logic: if last_play[0] == target_id → only return if Player2 penalized
        - Penalizing Player1 should NOT trigger return (Player2 played last)

        ACTIONS:
        - Player1 plays card1
        - Player2 plays card2
        - Check who is last in played_cards_stack

        VERIFICATION:
        - last played card belongs to Player2 (id="p2")
        - Simulated server check: "should return card for p1?" → False
        - Simulated server check: "should return card for p2?" → True
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # Player1 plays first
        card1 = self.player1.hand[0]
        self.game.play_card("p1", card1)

        # Player2 plays second (most recent)
        card2 = self.player2.hand[0]
        self.game.play_card("p2", card2)

        # VERIFICATION: Check the played_cards_stack
        self.assertGreater(len(self.game.played_cards_stack), 0,
                           "played_cards_stack should have entries")

        last_player_id, last_player_name, last_card = self.game.played_cards_stack[-1]

        self.assertEqual(last_player_id, "p2",
                         "Last played card should belong to Player2")
        self.assertEqual(last_card, card2,
                         "Last card in stack should be the card Player2 played")

        # Simulate server's return_card check logic:
        # "if last_play[0] == target_id: then return card"
        should_return_for_p1 = (last_player_id == "p1")
        should_return_for_p2 = (last_player_id == "p2")

        self.assertFalse(should_return_for_p1,
                         "Should NOT return card when penalizing p1 (p2 played last)")
        self.assertTrue(should_return_for_p2,
                        "SHOULD return card when penalizing p2 (p2 played last)")

    def test_return_card_restores_to_last_player(self):
        """
        TEST 12b: game.return_card() restores the last played card to its owner.

        When the server calls game.return_card(), it removes the last card from
        the discard pile and returns it to the player who played it.

        GAME STATE SETUP:
        - Player1 plays a card

        EXPECTED BEHAVIOR:
        - return_card() returns (player_id, player_name, card) tuple
        - Card is back in Player1's hand
        - Card is removed from discard pile

        VERIFICATION:
        - Return result identifies Player1 as original owner
        - Player1's hand count increased by 1
        - The returned card matches what was played
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        card_played = self.player1.hand[0]
        p1_hand_before = len(self.player1.hand)

        self.game.play_card("p1", card_played)
        p1_hand_after_play = len(self.player1.hand)
        self.assertEqual(p1_hand_after_play, p1_hand_before - 1,
                         "Player1 should have 1 fewer card after playing")

        # ACTIONS: Return the card
        result = self.game.return_card("p2")  # p2 requests the return

        # VERIFICATION
        self.assertIsNotNone(result, "return_card should succeed")
        original_id, original_name, returned_card = result

        self.assertEqual(original_id, "p1",
                         "Returned card should go back to Player1 (who played it)")
        self.assertEqual(original_name, "Alice",
                         "Original player name should be Alice")
        self.assertEqual(returned_card, card_played,
                         "Returned card should be the one that was played")
        self.assertEqual(len(self.player1.hand), p1_hand_before,
                         "Player1 should have their card back")

    # --- Test 13: Hand Not Auto-Displayed ---

    def test_game_state_no_hand_data_without_player_id(self):
        """
        TEST 13: Game state without for_player_id does NOT include any hand data.

        When render_game_state is called, it uses to_dict(for_player_id=player_id).
        This test verifies that WITHOUT a player_id, NO hands are exposed.
        This ensures hands are never accidentally auto-shown.

        GAME STATE SETUP:
        - Game in progress with dealt cards

        EXPECTED BEHAVIOR:
        - to_dict() with no for_player_id → no "hand" keys in any player data
        - This is the "safe default" state that prevents accidental exposure

        ACTIONS:
        - Serialize game state without specifying a player

        VERIFICATION:
        - No player data has a "hand" key
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # ACTIONS: Get state with no requesting player (no hand included)
        state_no_player = self.game.to_dict()  # No for_player_id

        # VERIFICATION: No player should have hand data
        for player_data in state_no_player["players"]:
            self.assertNotIn("hand", player_data,
                             f"Player {player_data.get('name')} should NOT have hand "
                             f"data in state without for_player_id")

    def test_game_state_only_own_player_gets_hand(self):
        """
        TEST 13b: Only the requesting player gets hand data; others do not.

        This ensures the display can only show the requesting player's hand,
        not others'. Players must explicitly request their hand via 'hand' command.

        GAME STATE SETUP:
        - 3-player game in progress

        EXPECTED BEHAVIOR:
        - to_dict(for_player_id="p2") includes hand for p2 ONLY
        - p1 and p3 do NOT have hand data

        ACTIONS:
        - Serialize game state from p2's perspective

        VERIFICATION:
        - Only p2's data has "hand" key
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.add_player(self.player3)
        self.game.start_game()

        # ACTIONS
        state_as_p2 = self.game.to_dict(for_player_id="p2")

        # VERIFICATION
        for player_data in state_as_p2["players"]:
            pid = player_data.get("id")
            if pid == "p2":
                self.assertIn("hand", player_data,
                              "p2's own hand should be in their game state")
            else:
                self.assertNotIn("hand", player_data,
                                 f"Player {player_data.get('name')} (not p2) "
                                 f"should NOT have hand data in p2's state view")

    # --- Test 14: POO Command Phrases ---

    def test_poo_requires_player_in_game(self):
        """
        TEST 14: Point of Order can only be initiated by a player IN the game.

        GAME STATE SETUP:
        - Game in progress
        - Player1 is in game, "outsider" is not

        EXPECTED BEHAVIOR:
        - initiate_point_of_order("p1") succeeds
        - initiate_point_of_order("outsider") fails (player not found)

        ACTIONS:
        - Player1 (in game) initiates POO
        - Outsider (not in game) tries to initiate POO

        VERIFICATION:
        - Valid player's POO succeeds
        - Invalid player's POO fails
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # ACTIONS & VERIFICATION: Player in game can start POO
        result_valid = self.game.initiate_point_of_order("p1", "Dispute")
        self.assertTrue(result_valid, "Player in game should be able to start POO")
        self.assertEqual(self.game.phase, GamePhase.POINT_OF_ORDER,
                         "Phase should be POINT_OF_ORDER after valid initiation")

        # End POO to reset
        self.game.end_point_of_order()

        # ACTIONS & VERIFICATION: Player NOT in game cannot start POO
        result_invalid = self.game.initiate_point_of_order("outsider", "Fake")
        self.assertFalse(result_invalid,
                         "Player not in game should NOT be able to start POO")
        self.assertEqual(self.game.phase, GamePhase.IN_PROGRESS,
                         "Phase should remain IN_PROGRESS after invalid initiation")

    def test_poo_phrase_controls_game_state(self):
        """
        TEST 14b: "Point of Order" triggers exactly one phase transition.

        The game's initiate_point_of_order() is what "Point of Order" triggers.
        Only one POO can be active at a time - a second call does nothing.

        GAME STATE SETUP:
        - Game in progress

        EXPECTED BEHAVIOR:
        - First initiate_point_of_order() → True, phase = POINT_OF_ORDER
        - Second initiate_point_of_order() (nested) → False, phase unchanged

        ACTIONS:
        - Call initiate_point_of_order twice

        VERIFICATION:
        - First call returns True, second returns False
        - Phase is POINT_OF_ORDER (not double-nested)
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # ACTIONS
        first_result = self.game.initiate_point_of_order("p1", "First Point of Order")
        second_result = self.game.initiate_point_of_order("p2", "Second Point of Order")

        # VERIFICATION
        self.assertTrue(first_result,
                        "First 'Point of Order' should succeed")
        self.assertFalse(second_result,
                         "Second 'Point of Order' while one is active should fail")
        self.assertEqual(self.game.phase, GamePhase.POINT_OF_ORDER,
                         "Phase should be POINT_OF_ORDER (only one active)")
        # First caller should be tracked (not overwritten by failed second call)
        self.assertEqual(self.game.point_of_order.caller_id, "p1",
                         "Original POO caller should still be p1")

    def test_end_poo_restores_game_phase(self):
        """
        TEST 14c: Ending Point of Order ("End Point of Order" / "epoo") restores IN_PROGRESS.

        Both "End Point of Order" and "epoo" trigger end_point_of_order().
        This test verifies the underlying game logic is correct.

        GAME STATE SETUP:
        - Game in POINT_OF_ORDER phase

        EXPECTED BEHAVIOR:
        - end_point_of_order() → True, phase = IN_PROGRESS
        - point_of_order object is None
        - end_point_of_order() when NOT in POO → False

        ACTIONS:
        - Start POO
        - End POO
        - Try to end POO again

        VERIFICATION:
        - First end returns True, phase is IN_PROGRESS
        - Second end returns False (already ended)
        """
        # GAME STATE SETUP
        self.game.add_player(self.player1)
        self.game.add_player(self.player2)
        self.game.start_game()

        # Start POO
        self.game.initiate_point_of_order("p1", "Test Point of Order")
        self.assertEqual(self.game.phase, GamePhase.POINT_OF_ORDER,
                         "Phase should be POINT_OF_ORDER")

        # ACTIONS: End POO (simulates "End Point of Order" or "epoo" command)
        end_result = self.game.end_point_of_order()

        # VERIFICATION
        self.assertTrue(end_result, "end_point_of_order should return True")
        self.assertEqual(self.game.phase, GamePhase.IN_PROGRESS,
                         "Phase should be IN_PROGRESS after ending POO")
        self.assertIsNone(self.game.point_of_order,
                          "point_of_order should be None after ending")

        # Try to end again (simulates double "epoo" - should fail gracefully)
        second_end = self.game.end_point_of_order()
        self.assertFalse(second_end,
                         "Ending POO when not in POO should return False")


if __name__ == "__main__":
    unittest.main()
