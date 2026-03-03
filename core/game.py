"""Game class for Mao card game - central game state management."""

from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import time
import random

from .card import Card
from .deck import Deck
from .player import Player


class GamePhase(Enum):
    """Phases of the game."""
    WAITING = "waiting"              # Waiting for players to join
    IN_PROGRESS = "in_progress"      # Normal play
    POINT_OF_ORDER = "point_of_order"  # Paused for dispute resolution
    FINISHED = "finished"            # Game over


class TurnDirection(Enum):
    """Direction of play."""
    CLOCKWISE = 1
    COUNTER_CLOCKWISE = -1


@dataclass
class GameLog:
    """Represents a logged game event."""
    timestamp: datetime
    event_type: str  # "play", "draw", "knock", "chat", "penalty", "throw", "hit", etc.
    player_id: Optional[str]
    player_name: Optional[str]
    details: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize log entry."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "player_id": self.player_id,
            "player_name": self.player_name,
            "details": self.details
        }


@dataclass
class PendingPenalty:
    """Represents a penalty that can be disputed."""
    id: str
    target_id: str
    target_name: str
    caller_id: str
    caller_name: str
    reason: str
    cards: int
    penalty_cards_dealt: List[Any] = field(default_factory=list)  # actual Card objects dealt
    overturned: bool = False
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize penalty."""
        return {
            "id": self.id,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "caller_id": self.caller_id,
            "caller_name": self.caller_name,
            "reason": self.reason,
            "cards": self.cards,
            "overturned": self.overturned,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ActiveVote:
    """Tracks an active vote on a specific penalty during Point of Order."""
    penalty_index: int  # index into penalty_history
    penalty: PendingPenalty
    votes: Dict[str, str] = field(default_factory=dict)  # player_id -> "uphold"/"overturn"/"abstain"
    total_players: int = 0

    def add_vote(self, player_id: str, vote: str) -> None:
        """Record a player's vote. vote is 'uphold', 'overturn', or 'abstain'."""
        if player_id not in self.votes and vote in ("uphold", "overturn", "abstain"):
            self.votes[player_id] = vote

    def get_vote_counts(self) -> Tuple[int, int, int]:
        """Returns (uphold_count, overturn_count, abstain_count)."""
        uphold = sum(1 for v in self.votes.values() if v == "uphold")
        overturn = sum(1 for v in self.votes.values() if v == "overturn")
        abstain = sum(1 for v in self.votes.values() if v == "abstain")
        return uphold, overturn, abstain

    def all_voted(self) -> bool:
        """Check if all players have voted."""
        return len(self.votes) >= self.total_players

    def get_result(self) -> Optional[str]:
        """
        Get the vote result once all players have voted.

        Returns 'uphold', 'overturn', or None if not all voted yet.
        """
        if not self.all_voted():
            return None
        uphold, overturn, abstain = self.get_vote_counts()
        if overturn > uphold:
            return "overturn"
        else:
            return "uphold"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize active vote."""
        uphold, overturn, abstain = self.get_vote_counts()
        return {
            "penalty_index": self.penalty_index,
            "penalty": self.penalty.to_dict(),
            "votes": self.votes,
            "uphold_count": uphold,
            "overturn_count": overturn,
            "abstain_count": abstain,
            "total_players": self.total_players,
            "all_voted": self.all_voted()
        }


@dataclass
class PointOfOrder:
    """
    Manages the Point of Order state.

    No time limit - only ended by a player calling 'end point of order'.
    Players can vote on individual penalties during POO.
    """
    caller_id: str
    caller_name: str
    reason: str
    total_players: int
    active_vote: Optional[ActiveVote] = None
    overturned_penalty_ids: List[str] = field(default_factory=list)  # penalty IDs that were overturned

    def start_vote(self, penalty_index: int, penalty: PendingPenalty, total_players: int) -> bool:
        """Start a vote on a specific penalty. Returns False if a vote is already active."""
        if self.active_vote is not None:
            return False
        if penalty.id in self.overturned_penalty_ids:
            return False  # Already overturned, can't vote again
        self.active_vote = ActiveVote(
            penalty_index=penalty_index,
            penalty=penalty,
            total_players=total_players
        )
        return True

    def end_current_vote(self) -> Optional[ActiveVote]:
        """End the current vote and return it."""
        vote = self.active_vote
        self.active_vote = None
        return vote

    def to_dict(self) -> Dict[str, Any]:
        """Serialize Point of Order state."""
        return {
            "caller_id": self.caller_id,
            "caller_name": self.caller_name,
            "reason": self.reason,
            "active_vote": self.active_vote.to_dict() if self.active_vote else None,
            "overturned_penalty_ids": self.overturned_penalty_ids,
        }


class Game:
    """
    Central game state manager for Mao.

    Handles players, turns, card piles, logging, and Point of Order.
    """

    def __init__(self, num_decks: int = 1, min_players: int = 2, cards_per_player: int = 7):
        """
        Initialize the game.

        Args:
            num_decks: Number of standard 52-card decks to use.
            min_players: Minimum players required to start.
            cards_per_player: Starting cards per player.
        """
        self.num_decks = num_decks
        self.min_players = min_players
        self.cards_per_player = cards_per_player

        # Players
        self.players: List[Player] = []
        self.player_order: List[str] = []  # Player IDs in turn order

        # Card piles
        self.draw_pile: Optional[Deck] = None
        self.discard_pile: List[Card] = []

        # Turn management
        self.current_player_index: int = 0
        self.turn_direction: TurnDirection = TurnDirection.CLOCKWISE

        # Game state
        self.phase: GamePhase = GamePhase.WAITING
        self.logs: List[GameLog] = []
        self.point_of_order: Optional[PointOfOrder] = None
        self.pending_penalties: List[PendingPenalty] = []
        self.penalty_history: List[PendingPenalty] = []  # All penalties ever given (for POO lookup)
        self.played_cards_stack: List[Tuple[str, str, Card]] = []  # (player_id, player_name, card) for returns

        # Recent cards for display (player_name, card)
        self.recent_cards: List[Tuple[str, Card]] = []

        # Winners
        self.winners: List[str] = []

        # Mao declaration tracking
        self.mao_declaring_player_id: Optional[str] = None
        self.mao_declaration_time: Optional[float] = None

        # Settings
        self.max_log_entries: int = 100

        # Card effect tracking
        self.consecutive_plays: List[Tuple[str, str]] = []  # (player_id, rank_display)
        self.jack_suit: Optional[Any] = None  # Current suit after Jack (Suit enum)
        self.last_played_card: Optional[Card] = None
        self.play_again: bool = False  # Queen effect

    # --- Player Management ---

    def add_player(self, player: Player) -> bool:
        """
        Add a player to the game.

        Args:
            player: The player to add.

        Returns:
            True if player was added, False if game already started or player ID exists.
        """
        if self.phase != GamePhase.WAITING:
            return False

        # Check for duplicate ID
        if any(p.id == player.id for p in self.players):
            return False

        self.players.append(player)
        self.player_order.append(player.id)
        self._log_event("join", player.id, player.name, f"{player.name} joined the game")
        return True

    def remove_player(self, player_id: str) -> bool:
        """
        Remove a player from the game.

        Args:
            player_id: ID of player to remove.

        Returns:
            True if player was removed, False if not found.
        """
        for i, player in enumerate(self.players):
            if player.id == player_id:
                self.players.pop(i)
                self.player_order.remove(player_id)

                # Adjust current player index if needed
                if self.current_player_index >= len(self.players):
                    self.current_player_index = 0

                self._log_event("leave", player_id, player.name, f"{player.name} left the game")
                return True
        return False

    def get_player(self, player_id: str) -> Optional[Player]:
        """Get a player by ID."""
        for player in self.players:
            if player.id == player_id:
                return player
        return None

    def get_player_by_name(self, name: str) -> Optional[Player]:
        """Get a player by name (case-insensitive partial match)."""
        name_lower = name.lower()
        for player in self.players:
            if name_lower in player.name.lower():
                return player
        return None

    def get_player_index(self, player_id: str) -> int:
        """Get the index of a player in turn order."""
        try:
            return self.player_order.index(player_id)
        except ValueError:
            return -1

    def get_current_player(self) -> Optional[Player]:
        """Get the player whose turn it is."""
        if not self.players or self.current_player_index >= len(self.players):
            return None
        return self.players[self.current_player_index]

    # --- Game Flow ---

    def start_game(self) -> bool:
        """
        Initialize and start the game.

        Returns:
            True if game started, False if not enough players.
        """
        if len(self.players) < self.min_players:
            return False

        if self.phase != GamePhase.WAITING:
            return False

        # Create and shuffle deck
        self.draw_pile = Deck(num_decks=self.num_decks)
        self.draw_pile.shuffle()

        # Deal cards to players
        for _ in range(self.cards_per_player):
            for player in self.players:
                card = self.draw_pile.draw()
                if card:
                    player.add_card(card)

        # Place initial card on discard pile
        initial_card = self.draw_pile.draw()
        if initial_card:
            self.discard_pile.append(initial_card)

        # Randomize starting player
        self.current_player_index = random.randint(0, len(self.players) - 1)

        self.phase = GamePhase.IN_PROGRESS
        self._log_event("game_start", None, None, f"Game started with {len(self.players)} players")

        return True

    def can_start(self) -> bool:
        """Check if game can be started."""
        return len(self.players) >= self.min_players and self.phase == GamePhase.WAITING

    # --- Turn Management ---

    def advance_turn(self) -> None:
        """Move to the next player's turn."""
        self.current_player_index = (
            (self.current_player_index + self.turn_direction.value)
            % len(self.players)
        )

    def reverse_direction(self) -> None:
        """Reverse the direction of play."""
        if self.turn_direction == TurnDirection.CLOCKWISE:
            self.turn_direction = TurnDirection.COUNTER_CLOCKWISE
        else:
            self.turn_direction = TurnDirection.CLOCKWISE

    def skip_next_player(self) -> None:
        """Skip the next player in turn order."""
        self.advance_turn()

    def is_player_turn(self, player_id: str) -> bool:
        """Check if it's the specified player's turn."""
        current = self.get_current_player()
        return current is not None and current.id == player_id

    # --- Card Actions ---

    def draw_card(self, player_id: str, count: int = 1) -> List[Card]:
        """
        Player draws cards from the draw pile.

        Args:
            player_id: ID of player drawing.
            count: Number of cards to draw.

        Returns:
            List of drawn cards.
        """
        player = self.get_player(player_id)
        if not player:
            return []

        drawn = []
        for _ in range(count):
            # Reshuffle discard if draw pile is empty
            if self.draw_pile.is_empty():
                self._reshuffle_discard()

            card = self.draw_pile.draw()
            if card:
                player.add_card(card)
                drawn.append(card)

        if drawn:
            player_name = player.name
            self._log_event("draw", player_id, player_name, f"{player_name} drew {len(drawn)} card(s)")

        return drawn

    def play_card(self, player_id: str, card: Card) -> bool:
        """
        Player plays a card to the discard pile.

        Args:
            player_id: ID of player playing.
            card: The card to play.

        Returns:
            True if card was played, False if player doesn't have it.
        """
        player = self.get_player(player_id)
        if not player:
            return False

        if not player.has_card(card):
            return False

        player.remove_card(card)
        self.discard_pile.append(card)

        # Track for returns
        self.played_cards_stack.append((player_id, player.name, card))

        # Track recent cards for display
        self.recent_cards.append((player.name, card))
        # Keep only the last 10 cards
        if len(self.recent_cards) > 10:
            self.recent_cards = self.recent_cards[-10:]

        # Track consecutive plays
        self._track_consecutive_play(player_id, card)

        # Track last played card
        self.last_played_card = card

        # Handle card effects
        self._apply_card_effect(card)

        self._log_event("play", player_id, player.name, f"{player.name} played {card}")

        # Check for win condition
        if player.is_empty_hand():
            self.winners.append(player_id)
            self._log_event("win", player_id, player.name, f"{player.name} has played all cards!")

        return True

    def _track_consecutive_play(self, player_id: str, card: Card) -> None:
        """Track consecutive plays of the same rank."""
        if self.consecutive_plays and self.consecutive_plays[-1][1] == card.rank.display:
            self.consecutive_plays.append((player_id, card.rank.display))
        else:
            self.consecutive_plays = [(player_id, card.rank.display)]

    def _apply_card_effect(self, card: Card) -> None:
        """Apply special card effects."""
        rank = card.rank.display

        # Reset play_again flag
        self.play_again = False

        # Jack: reset jack_suit when a non-Jack is played
        if rank != "J":
            self.jack_suit = None

        # 5: skip next player
        if rank == "5":
            self.skip_next_player()
            self._log_event("effect", None, None, f"5 played - next player skipped")

        # A: reverse direction
        elif rank == "A":
            self.reverse_direction()
            self._log_event("effect", None, None, f"Ace played - direction reversed")

        # Q: play again
        elif rank == "Q":
            self.play_again = True
            self._log_event("effect", None, None, f"Queen played - player goes again")

    def set_jack_suit(self, suit) -> None:
        """Set the current suit after a Jack is played."""
        self.jack_suit = suit
        self._log_event("effect", None, None, f"Suit changed to {suit.full_name if hasattr(suit, 'full_name') else suit}")

    def get_effective_suit(self) -> Optional[Any]:
        """Get the current effective suit (considering Jack)."""
        if self.jack_suit:
            return self.jack_suit
        top_card = self.get_top_card()
        return top_card.suit if top_card else None

    def get_consecutive_count(self) -> int:
        """Get the count of consecutive plays of the same rank."""
        return len(self.consecutive_plays)

    def check_consecutive_throw_required(self) -> Tuple[bool, str]:
        """
        Check if a throw card action is required due to consecutive plays.

        Returns:
            Tuple of (required, rank) where required is True if 3+ consecutive.
        """
        if len(self.consecutive_plays) >= 3:
            return True, self.consecutive_plays[0][1]
        return False, ""

    def should_play_again(self) -> bool:
        """Check if current player should play again (Queen effect)."""
        return self.play_again

    def get_top_card(self) -> Optional[Card]:
        """Get the top card of the discard pile."""
        if not self.discard_pile:
            return None
        return self.discard_pile[-1]

    def return_card(self, player_id: str) -> Optional[Tuple[str, str, Card]]:
        """
        Return the last played card (for misplays).

        Args:
            player_id: ID of player requesting return.

        Returns:
            Tuple of (original_player_id, original_player_name, card) if successful, None otherwise.
        """
        if not self.played_cards_stack:
            return None

        original_player_id, original_player_name, card = self.played_cards_stack.pop()

        # Remove from discard pile
        if self.discard_pile and self.discard_pile[-1] == card:
            self.discard_pile.pop()

        # Return to original player's hand
        original_player = self.get_player(original_player_id)
        if original_player:
            original_player.add_card(card)

        self._log_event("return", player_id, None, f"Card {card} returned to {original_player_name}")

        return (original_player_id, original_player_name, card)

    def _reshuffle_discard(self) -> None:
        """Reshuffle discard pile into draw pile when draw pile is empty."""
        if len(self.discard_pile) <= 1:
            return

        # Keep the top card
        top_card = self.discard_pile.pop()

        # Add rest to draw pile
        self.draw_pile.add_cards(self.discard_pile)
        self.draw_pile.shuffle()

        # Restore top card
        self.discard_pile = [top_card]

        self._log_event("reshuffle", None, None, "Discard pile reshuffled into draw pile")

    # --- Logging ---

    def _log_event(self, event_type: str, player_id: Optional[str],
                   player_name: Optional[str], details: str) -> None:
        """Record a game event."""
        log = GameLog(
            timestamp=datetime.now(),
            event_type=event_type,
            player_id=player_id,
            player_name=player_name,
            details=details
        )
        self.logs.append(log)

        # Trim old logs
        if len(self.logs) > self.max_log_entries:
            self.logs = self.logs[-self.max_log_entries:]

    def get_recent_logs(self, count: int = 20) -> List[GameLog]:
        """Get the most recent log entries."""
        return self.logs[-count:]

    def get_recent_cards(self, count: int = 3) -> List[Dict[str, Any]]:
        """Get the most recent played cards with player names."""
        recent = self.recent_cards[-count:] if self.recent_cards else []
        return [{"player_name": name, "card": card.to_dict()} for name, card in recent]

    # --- Point of Order ---

    def initiate_point_of_order(self, caller_id: str, reason: str = "General dispute") -> bool:
        """
        Start a Point of Order. No auto-vote, no time limit.
        Players can then vote on individual penalties.

        Args:
            caller_id: ID of player calling Point of Order.
            reason: Reason for the POO.

        Returns:
            True if POO was initiated, False if already in one.
        """
        if self.phase == GamePhase.POINT_OF_ORDER:
            return False

        caller = self.get_player(caller_id)
        if not caller:
            return False

        self.point_of_order = PointOfOrder(
            caller_id=caller_id,
            caller_name=caller.name,
            reason=reason,
            total_players=len(self.players)
        )

        self.phase = GamePhase.POINT_OF_ORDER
        self._log_event("poo_start", caller_id, caller.name, f"Point of Order called: {reason}")

        return True

    def end_point_of_order(self) -> bool:
        """
        End the current Point of Order and return to normal play.

        Returns:
            True if POO was ended, False if not in POO.
        """
        if self.phase != GamePhase.POINT_OF_ORDER:
            return False

        self._log_event("poo_end", None, None, "Point of Order ended")
        self.point_of_order = None
        self.phase = GamePhase.IN_PROGRESS
        return True

    def start_penalty_vote(self, penalty_index: int) -> Optional[ActiveVote]:
        """
        Start a vote on a specific penalty during Point of Order.

        Args:
            penalty_index: Index into penalty_history (1-based from user, 0-based internally).

        Returns:
            The ActiveVote if started, None if failed.
        """
        if self.phase != GamePhase.POINT_OF_ORDER or not self.point_of_order:
            return None

        if self.point_of_order.active_vote is not None:
            return None  # Already voting

        if penalty_index < 0 or penalty_index >= len(self.penalty_history):
            return None

        penalty = self.penalty_history[penalty_index]

        if penalty.overturned:
            return None  # Already overturned

        if penalty.id in self.point_of_order.overturned_penalty_ids:
            return None

        if self.point_of_order.start_vote(penalty_index, penalty, len(self.players)):
            self._log_event("vote_start", None, None,
                            f"Vote started on penalty #{penalty_index + 1}: {penalty.caller_name} → {penalty.target_name}: {penalty.reason}")
            return self.point_of_order.active_vote

        return None

    def add_vote(self, player_id: str, vote: str) -> bool:
        """
        Add a vote during an active penalty vote in Point of Order.

        Args:
            player_id: ID of voting player.
            vote: 'uphold', 'overturn', or 'abstain'.

        Returns:
            True if vote was recorded, False if not in POO or no active vote.
        """
        if self.phase != GamePhase.POINT_OF_ORDER or not self.point_of_order:
            return False

        if not self.point_of_order.active_vote:
            return False

        self.point_of_order.active_vote.add_vote(player_id, vote)

        voter = self.get_player(player_id)
        self._log_event("vote", player_id, voter.name if voter else None,
                        f"{voter.name if voter else 'Unknown'} voted to {vote}")

        return True

    def check_vote_result(self) -> Optional[str]:
        """
        Check if the current penalty vote is complete.

        Returns:
            'uphold', 'overturn', or None (still voting).
        """
        if not self.point_of_order or not self.point_of_order.active_vote:
            return None

        return self.point_of_order.active_vote.get_result()

    def resolve_penalty_vote(self, result: str) -> Optional[Dict[str, Any]]:
        """
        Resolve the current penalty vote.

        Args:
            result: 'uphold' or 'overturn'.

        Returns:
            Dict with resolution details, or None if no active vote.
        """
        if not self.point_of_order or not self.point_of_order.active_vote:
            return None

        vote = self.point_of_order.active_vote
        penalty = vote.penalty
        resolution = {
            "result": result,
            "penalty": penalty.to_dict(),
            "affected_player_id": None,
            "cards_moved": 0,
            "caller_penalized": False,
        }

        if result == "overturn":
            # Mark penalty as overturned
            penalty.overturned = True
            self.point_of_order.overturned_penalty_ids.append(penalty.id)

            # Remove penalty cards from target, give to caller
            target = self.get_player(penalty.target_id)
            caller = self.get_player(penalty.caller_id)

            cards_returned = 0
            cards_missing = 0

            if target and caller:
                for card in penalty.penalty_cards_dealt:
                    if target.has_card(card):
                        target.remove_card(card)
                        caller.add_card(card)
                        cards_returned += 1
                    else:
                        # Card was played/gone - caller gets a normal penalty card
                        cards_missing += 1

                # For missing cards, caller draws from deck
                if cards_missing > 0:
                    for _ in range(cards_missing):
                        if self.draw_pile.is_empty():
                            self._reshuffle_discard()
                        drawn = self.draw_pile.draw()
                        if drawn:
                            caller.add_card(drawn)

                resolution["affected_player_id"] = penalty.caller_id
                resolution["cards_moved"] = cards_returned
                resolution["caller_penalized"] = cards_missing > 0
                resolution["cards_missing"] = cards_missing

                self._log_event("vote_resolve", None, None,
                                f"Penalty overturned: {cards_returned} card(s) returned to {caller.name}" +
                                (f", {cards_missing} penalty card(s) drawn by {caller.name}" if cards_missing else ""))
            else:
                resolution["affected_player_id"] = penalty.target_id
        else:
            # Upheld - penalty stands, no changes needed
            resolution["affected_player_id"] = penalty.target_id
            self._log_event("vote_resolve", None, None, "Penalty upheld")

        # End the current vote (but stay in POO!)
        self.point_of_order.end_current_vote()

        return resolution

    # --- Penalties ---

    def give_penalty(self, caller_id: str, target_id: str, reason: str,
                     cards: int = 1) -> Optional[PendingPenalty]:
        """
        Give a penalty to another player.

        Args:
            caller_id: ID of player giving penalty.
            target_id: ID of player receiving penalty.
            reason: Reason for the penalty.
            cards: Number of penalty cards.

        Returns:
            PendingPenalty object if successful, None otherwise.
        """
        if self.phase != GamePhase.IN_PROGRESS:
            return None

        caller = self.get_player(caller_id)
        target = self.get_player(target_id)

        if not caller or not target:
            return None

        penalty = PendingPenalty(
            id=f"penalty_{len(self.penalty_history)}",
            target_id=target_id,
            target_name=target.name,
            caller_id=caller_id,
            caller_name=caller.name,
            reason=reason,
            cards=cards
        )

        self.pending_penalties.append(penalty)
        self.penalty_history.append(penalty)
        self._log_event("penalty", caller_id, caller.name,
                        f"{caller.name} gave {cards} penalty card(s) to {target.name}: {reason}")

        return penalty

    def apply_penalty(self, penalty_id: str) -> List[Card]:
        """
        Apply a pending penalty (draw cards) and track the dealt cards.

        Args:
            penalty_id: ID of the penalty to apply.

        Returns:
            List of cards dealt as penalty.
        """
        for i, penalty in enumerate(self.pending_penalties):
            if penalty.id == penalty_id:
                target = self.get_player(penalty.target_id)
                if target:
                    cards = self.draw_card(penalty.target_id, penalty.cards)
                    if cards:
                        penalty.penalty_cards_dealt = list(cards)
                        self.pending_penalties.pop(i)
                        return cards
        return []

    def get_last_penalty(self) -> Optional[PendingPenalty]:
        """Get the most recent pending penalty."""
        if self.pending_penalties:
            return self.pending_penalties[-1]
        return None

    # --- Mao Declaration ---

    def start_mao_declaration(self, player_id: str) -> bool:
        """
        Start a Mao declaration. Gives other players 6 seconds to challenge.

        Args:
            player_id: ID of declaring player.

        Returns:
            True if declaration started.
        """
        if self.mao_declaring_player_id is not None:
            return False  # Someone already declaring

        self.mao_declaring_player_id = player_id
        self.mao_declaration_time = time.time()
        return True

    def cancel_mao_declaration(self) -> None:
        """Cancel the current Mao declaration (e.g., after penalty)."""
        self.mao_declaring_player_id = None
        self.mao_declaration_time = None

    def check_mao_declaration_timer(self) -> bool:
        """
        Check if 6 seconds have passed since Mao declaration.

        Returns:
            True if 6 seconds elapsed and declaration should succeed.
        """
        if self.mao_declaring_player_id and self.mao_declaration_time:
            return time.time() - self.mao_declaration_time >= 6.0
        return False

    # --- Other Actions ---

    def knock(self, player_id: str) -> bool:
        """
        Player knocks on the table.

        Args:
            player_id: ID of knocking player.

        Returns:
            True if knock was recorded.
        """
        player = self.get_player(player_id)
        if not player:
            return False

        self._log_event("knock", player_id, player.name, f"{player.name} knocked on the table")
        return True

    def chat(self, player_id: str, message: str) -> bool:
        """
        Player says something.

        Args:
            player_id: ID of speaking player.
            message: What they said.

        Returns:
            True if chat was recorded.
        """
        player = self.get_player(player_id)
        if not player:
            return False

        self._log_event("chat", player_id, player.name, f"{player.name}: {message}")
        return True

    def throw_card(self, player_id: str, card: Card, target_id: str) -> bool:
        """
        Player throws a card at another player.

        Args:
            player_id: ID of throwing player.
            card: Card to throw.
            target_id: ID of target player.

        Returns:
            True if throw was successful.
        """
        player = self.get_player(player_id)
        target = self.get_player(target_id)

        if not player or not target:
            return False

        if not player.has_card(card):
            return False

        player.remove_card(card)
        target.add_card(card)

        self._log_event("throw", player_id, player.name,
                        f"{player.name} threw {card} at {target.name}")
        return True

    def hit_player(self, player_id: str, target_id: str) -> bool:
        """
        Player hits another player (action only, no card transfer).

        Args:
            player_id: ID of hitting player.
            target_id: ID of target player.

        Returns:
            True if hit was recorded.
        """
        player = self.get_player(player_id)
        target = self.get_player(target_id)

        if not player or not target:
            return False

        self._log_event("hit", player_id, player.name, f"{player.name} hit {target.name}")
        return True

    # --- Serialization ---

    def to_dict(self, for_player_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Serialize game state for transmission.

        Args:
            for_player_id: If provided, include private data for this player.

        Returns:
            Dictionary representation of game state.
        """
        data = {
            "phase": self.phase.value,
            "players": [],
            "turn_direction": self.turn_direction.value,
            "top_card": None,
            "discard_count": len(self.discard_pile),
            "draw_pile_count": self.draw_pile.remaining() if self.draw_pile else 0,
            "point_of_order": self.point_of_order.to_dict() if self.point_of_order else None,
            "mao_declaring_player_id": self.mao_declaring_player_id,
        }

        # Top card
        top = self.get_top_card()
        if top:
            data["top_card"] = top.to_dict()

        # Players (show card counts, not actual cards)
        for player in self.players:
            player_data = player.to_dict(include_hand=(player.id == for_player_id))
            data["players"].append(player_data)

        # Include penalty history for POO display
        if self.phase == GamePhase.POINT_OF_ORDER:
            data["penalty_history"] = [p.to_dict() for p in self.penalty_history]

        # Include recent cards (more during POO)
        from config.settings import RECENT_CARDS_SHOWN, RECENT_CARDS_SHOWN_POO
        if self.phase == GamePhase.POINT_OF_ORDER:
            data["recent_cards"] = self.get_recent_cards(RECENT_CARDS_SHOWN_POO)
        else:
            data["recent_cards"] = self.get_recent_cards(RECENT_CARDS_SHOWN)

        return data

    def get_player_hand(self, player_id: str) -> List[Card]:
        """Get a player's hand."""
        player = self.get_player(player_id)
        if player:
            return player.hand.copy()
        return []
