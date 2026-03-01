"""Rule engine for Mao card game - handles complex rule validation."""

import json
import re
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

from .card import Card, Suit, Rank
from .player import Player
from .game import Game


class RuleType(Enum):
    """Types of rules."""
    CARD_EFFECT = "card_effect"
    SPEECH = "speech"
    TIMING = "timing"
    PLAY = "play"
    CONSECUTIVE = "consecutive"


@dataclass
class RuleViolation:
    """Represents a rule violation."""
    rule_name: str
    description: str
    penalty_cards: int
    can_be_disputed: bool = True
    action_required: str = ""  # What action is needed to fix


@dataclass
class CardEffect:
    """Represents a special card effect."""
    rank: str
    effect: str
    description: str
    consecutive_modifier: str = ""
    valid_names: List[str] = field(default_factory=list)
    cannot_play_on: List[str] = field(default_factory=list)


@dataclass
class SpeechRule:
    """Represents a speech-based rule."""
    name: str
    trigger: str
    condition: str
    penalty_cards: int
    description: str
    required_phrases: List[str] = field(default_factory=list)
    required_phrase_template: str = ""
    required_phrase_player: str = ""
    required_phrase_others: str = ""
    action: str = ""
    applies_to: str = "current_player"
    can_be_disputed: bool = True
    valid_names: List[str] = field(default_factory=list)


@dataclass
class ConsecutiveRule:
    """Represents a rule for consecutive plays."""
    threshold: int
    effect: str
    description: str
    special_cases: Dict[str, Dict] = field(default_factory=dict)


class RuleEngine:
    """
    Rule validation and enforcement engine for Mao.

    Loads rules from a JSON configuration file and provides
    methods to check for rule violations.
    """

    # Common profanity list for the no cursing rule
    PROFANITY_PATTERNS = [
        r'\b(fuck|shit|ass|bitch|bastard|crap)\b',
        # Add more patterns as needed
    ]

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the rule engine.

        Args:
            config_path: Path to the rules JSON file.
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}

        # Parsed rules
        self.card_effects: Dict[str, CardEffect] = {}
        self.speech_rules: List[SpeechRule] = []
        self.consecutive_rule: Optional[ConsecutiveRule] = None
        self.play_rules: Dict[str, Dict] = {}
        self.suit_rules: List[Dict] = []

        # Game settings
        self.cards_per_player = 5
        self.min_players = 2
        self.max_players = 10
        self.default_decks = 1

        # Penalty settings
        self.default_penalty_cards = 1
        self.max_penalty_cards = 5

        # Point of Order settings
        self.poo_enabled = True
        self.poo_time_limit = 60
        self.poo_majority = 0.5
        self.poo_restrictions = {}

        # State tracking for complex rules
        self.consecutive_plays: List[Tuple[str, Rank]] = []  # (player_id, rank)
        self.jack_suit: Optional[Suit] = None  # Current suit after Jack
        self.last_played_card: Optional[Card] = None

        if config_path:
            self.load_rules(config_path)

    def load_rules(self, config_path: str) -> None:
        """
        Load rules from a JSON configuration file.
        """
        path = Path(config_path)
        if not path.exists():
            print(f"Warning: Rules file not found: {config_path}")
            return

        try:
            with open(path, "r") as f:
                self.config = json.load(f)

            self._parse_config()
            print(f"Loaded rules from {config_path}")

        except json.JSONDecodeError as e:
            print(f"Error parsing rules file: {e}")
        except Exception as e:
            print(f"Error loading rules: {e}")

    def _parse_config(self) -> None:
        """Parse the loaded configuration into rule objects."""
        # Parse game settings
        game_settings = self.config.get("game_settings", {})
        self.cards_per_player = game_settings.get("cards_per_player", 5)
        self.min_players = game_settings.get("min_players", 2)
        self.max_players = game_settings.get("max_players", 10)
        self.default_decks = game_settings.get("default_decks", 1)

        # Parse card effects
        card_rules = self.config.get("card_rules", {})
        for card_rule in card_rules.get("special_cards", []):
            effect = CardEffect(
                rank=card_rule.get("rank", ""),
                effect=card_rule.get("effect", ""),
                description=card_rule.get("description", ""),
                consecutive_modifier=card_rule.get("consecutive_modifier", ""),
                valid_names=card_rule.get("valid_names", []),
                cannot_play_on=card_rule.get("cannot_play_on", [])
            )
            self.card_effects[effect.rank] = effect

        # Parse suit rules
        self.suit_rules = card_rules.get("suit_rules", [])

        # Parse consecutive rules
        consec = card_rules.get("consecutive_rules", {})
        if consec:
            self.consecutive_rule = ConsecutiveRule(
                threshold=consec.get("threshold", 3),
                effect=consec.get("effect", "throw_card"),
                description=consec.get("description", ""),
                special_cases=consec.get("special_case", {})
            )

        # Parse speech rules
        for rule in self.config.get("speech_rules", []):
            speech_rule = SpeechRule(
                name=rule.get("name", ""),
                trigger=rule.get("trigger", ""),
                condition=rule.get("condition", ""),
                penalty_cards=rule.get("penalty_cards", 1),
                description=rule.get("description", ""),
                required_phrases=rule.get("required_phrases", []),
                required_phrase_template=rule.get("required_phrase_template", ""),
                required_phrase_player=rule.get("required_phrase_player", ""),
                required_phrase_others=rule.get("required_phrase_others", ""),
                action=rule.get("action", ""),
                applies_to=rule.get("applies_to", "current_player"),
                can_be_disputed=rule.get("can_be_disputed", True),
                valid_names=rule.get("valid_names", [])
            )
            self.speech_rules.append(speech_rule)

        # Parse play rules
        for rule in self.config.get("play_rules", []):
            self.play_rules[rule.get("name", "")] = rule

        # Parse penalty settings
        penalties = self.config.get("penalties", {})
        self.default_penalty_cards = penalties.get("default_cards", 1)
        self.max_penalty_cards = penalties.get("max_penalty_cards", 5)

        # Parse Point of Order settings
        poo = self.config.get("point_of_order", {})
        self.poo_enabled = poo.get("enabled", True)
        self.poo_time_limit = poo.get("vote_time_limit_seconds", 60)
        self.poo_majority = poo.get("required_majority", 0.5)
        self.poo_restrictions = poo.get("restrictions", {})

    # --- Play Validation ---

    def validate_play(self, game: Game, player: Player, card: Card,
                      message: str = "") -> List[RuleViolation]:
        """
        Validate a play and return any violations.

        Args:
            game: Current game state.
            player: Player attempting to play.
            card: Card being played.
            message: What the player said.

        Returns:
            List of any rule violations.
        """
        violations = []

        # Check if it's the player's turn
        if not game.is_player_turn(player.id):
            violations.append(RuleViolation(
                rule_name="your_turn",
                description="It's not your turn",
                penalty_cards=2,
                can_be_disputed=False
            ))
            return violations

        # Check if player has the card
        if not player.has_card(card):
            violations.append(RuleViolation(
                rule_name="have_card",
                description="You don't have that card",
                penalty_cards=1,
                can_be_disputed=False
            ))
            return violations

        top_card = game.get_top_card()
        jack_on_jack_rule = self.play_rules.get("jack_on_jack_forbidden", {})

        # Check Jack on Jack rule
        if card.rank.display == "J" and top_card and top_card.rank.display == "J":
            if jack_on_jack_rule.get("auto_enforce", True):
                violations.append(RuleViolation(
                    rule_name="jack_on_jack_forbidden",
                    description=jack_on_jack_rule.get("description", "A Jack cannot be played on another Jack"),
                    penalty_cards=jack_on_jack_rule.get("penalty_cards", 1),
                    can_be_disputed=True
                ))
                return violations

        # Check matching rule
        if top_card:
            # Check if Jack has changed the suit
            effective_suit = self.jack_suit if self.jack_suit else top_card.suit

            # Jacks can be played on anything (except another Jack)
            if card.rank.display != "J":
                matches = (card.suit == effective_suit or card.rank == top_card.rank)
                if not matches:
                    matching_rule = self.play_rules.get("matching_suit_or_rank", {})
                    if matching_rule.get("auto_enforce", True):
                        violations.append(RuleViolation(
                            rule_name="matching_suit_or_rank",
                            description=f"Card must match {effective_suit.full_name} or {top_card.rank.display}",
                            penalty_cards=matching_rule.get("penalty_cards", 1),
                            can_be_disputed=True
                        ))

        return violations

    def process_play(self, player_id: str, card: Card, message: str = "") -> Tuple[CardEffect, List[RuleViolation]]:
        """
        Process a play and return the effect and any required actions.

        Args:
            player_id: ID of the player.
            card: Card that was played.
            message: What the player said.

        Returns:
            Tuple of (CardEffect if any, list of violations)
        """
        violations = []
        effect = None

        # Track consecutive plays
        if self.consecutive_plays and self.consecutive_plays[-1][1] == card.rank:
            self.consecutive_plays.append((player_id, card.rank))
        else:
            self.consecutive_plays = [(player_id, card.rank)]

        # Get card effect
        effect = self.card_effects.get(card.rank.display)

        # Reset jack suit if a non-Jack is played
        if card.rank.display != "J":
            self.jack_suit = None

        # Check speech rules
        violations.extend(self._check_speech_rules(card, message))

        # Check consecutive rules
        violations.extend(self._check_consecutive_rules(card, message))

        # Check suit-specific rules
        violations.extend(self._check_suit_rules(card, message))

        self.last_played_card = card

        return effect, violations

    def _check_speech_rules(self, card: Card, message: str) -> List[RuleViolation]:
        """Check speech-based rules."""
        violations = []
        message_lower = message.lower()

        for rule in self.speech_rules:
            if rule.trigger == "play_card":
                if self._check_condition(rule.condition, card=card):
                    # Check for required phrase
                    if rule.required_phrases:
                        found = any(phrase.lower() in message_lower for phrase in rule.required_phrases)
                        if not found:
                            violations.append(RuleViolation(
                                rule_name=rule.name,
                                description=rule.description,
                                penalty_cards=rule.penalty_cards,
                                can_be_disputed=rule.can_be_disputed
                            ))

                    # Check for template-based phrase (like "have a {very} nice day")
                    elif rule.required_phrase_template:
                        if not self._check_template_phrase(rule, card, message):
                            violations.append(RuleViolation(
                                rule_name=rule.name,
                                description=rule.description,
                                penalty_cards=rule.penalty_cards,
                                can_be_disputed=rule.can_be_disputed
                            ))

                    # Check for valid names (like Beatles members)
                    elif rule.valid_names:
                        found = any(name.lower() in message_lower for name in rule.valid_names)
                        if not found:
                            violations.append(RuleViolation(
                                rule_name=rule.name,
                                description=f"Must name a valid option: {', '.join(rule.valid_names)}",
                                penalty_cards=rule.penalty_cards,
                                can_be_disputed=rule.can_be_disputed
                            ))

                    # Check for action (like knock)
                    elif rule.action == "knock":
                        violations.append(RuleViolation(
                            rule_name=rule.name,
                            description=rule.description,
                            penalty_cards=rule.penalty_cards,
                            can_be_disputed=rule.can_be_disputed,
                            action_required="knock"
                        ))

            elif rule.trigger == "speech":
                # Check for false Mao
                if "mao" in rule.name.lower() and "hand_size" in rule.condition:
                    if "mao" in message_lower:
                        # This would need player context to check hand size
                        pass

                # Check for cursing
                if "cursing" in rule.name.lower() or "profanity" in rule.condition:
                    if self._contains_profanity(message):
                        violations.append(RuleViolation(
                            rule_name=rule.name,
                            description=rule.description,
                            penalty_cards=rule.penalty_cards,
                            can_be_disputed=rule.can_be_disputed
                        ))

        return violations

    def _check_consecutive_rules(self, card: Card, message: str) -> List[RuleViolation]:
        """Check rules related to consecutive plays."""
        violations = []

        if not self.consecutive_rule:
            return violations

        consecutive_count = len(self.consecutive_plays)

        if consecutive_count >= self.consecutive_rule.threshold:
            # Check for evil card announcement if 6's
            if card.rank.display == "6":
                special_case = self.consecutive_rule.special_cases
                if special_case and "evil card" not in message.lower():
                    violations.append(RuleViolation(
                        rule_name="evil_card_announcement",
                        description=special_case.get("description", "Must announce 'evil card'"),
                        penalty_cards=2,
                        can_be_disputed=True
                    ))

            # Require throw card action
            if self.consecutive_rule.effect == "throw_card":
                violations.append(RuleViolation(
                    rule_name="consecutive_throw",
                    description=self.consecutive_rule.description,
                    penalty_cards=2,
                    can_be_disputed=True,
                    action_required="throw_card"
                ))

        return violations

    def _check_suit_rules(self, card: Card, message: str) -> List[RuleViolation]:
        """Check suit-specific rules."""
        violations = []
        message_lower = message.lower()

        for rule in self.suit_rules:
            suit_name = rule.get("suit", "").lower()
            if card.suit.full_name != suit_name:
                continue

            # Check for specific rank requirement
            if "rank" in rule and card.rank.display != rule["rank"]:
                continue

            on_play = rule.get("on_play", "")

            # Spades announcement
            if on_play == "announce_spades" and card.rank.display != "A":
                required = f"{card.rank.display.lower()} of spades"
                if required not in message_lower:
                    violations.append(RuleViolation(
                        rule_name="announce_spades",
                        description=rule.get("description", "Must announce the card"),
                        penalty_cards=rule.get("penalty_cards", 2),
                        can_be_disputed=True
                    ))

            # Ace of Spades song
            elif on_play == "ace_of_spades_song" and card.rank.display == "A":
                required = "flying swooping ace of spades"
                if required not in message_lower:
                    violations.append(RuleViolation(
                        rule_name="ace_of_spades_song",
                        description=rule.get("description", "Must sing the Ace of Spades song"),
                        penalty_cards=rule.get("penalty_cards", 2),
                        can_be_disputed=True,
                        action_required="sing_ace_of_spades"
                    ))

            # Hearts knock
            elif on_play == "knock":
                violations.append(RuleViolation(
                    rule_name="knock_on_hearts",
                    description=rule.get("description", "Must knock when playing a heart"),
                    penalty_cards=rule.get("penalty_cards", 2),
                    can_be_disputed=True,
                    action_required="knock"
                ))

        return violations

    def _check_template_phrase(self, rule: SpeechRule, card: Card, message: str) -> bool:
        """Check if message matches a template phrase."""
        message_lower = message.lower()

        # Special case for "have a (very) nice day"
        if "nice day" in rule.required_phrase_template:
            consecutive_7s = self._count_consecutive_rank("7")

            # Build expected phrase
            very_count = consecutive_7s - 1  # First 7 has 0 "very"s
            if very_count < 0:
                very_count = 0

            very_string = " ".join(["very"] * very_count)
            if very_string:
                expected = f"have a {very_string} nice day"
            else:
                expected = "have a nice day"

            return expected in message_lower

        return False

    def _count_consecutive_rank(self, rank: str) -> int:
        """Count consecutive plays of a rank."""
        if not self.consecutive_plays:
            return 0

        count = 0
        for _, played_rank in reversed(self.consecutive_plays):
            if played_rank.display == rank:
                count += 1
            else:
                break

        return count

    def _check_condition(self, condition: str, card: Card = None,
                         player: Player = None) -> bool:
        """Check if a condition string is satisfied."""
        if not condition:
            return False

        condition = condition.strip()

        if card:
            # Check suit conditions
            if "card_suit" in condition:
                for suit in ["hearts", "diamonds", "clubs", "spades"]:
                    if f"card_suit == '{suit}'" in condition or f"card_suit=='{suit}'" in condition:
                        return card.suit.full_name == suit

            # Check rank conditions
            if "card_rank" in condition:
                for rank in ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]:
                    if f"card_rank == '{rank}'" in condition or f"card_rank=='{rank}'" in condition:
                        return card.rank.display == rank

        if player:
            # Check hand size conditions
            if "hand_size" in condition:
                match = re.search(r"hand_size\s*==\s*(\d+)", condition)
                if match:
                    target_size = int(match.group(1))
                    return player.get_card_count() == target_size

        return False

    def _contains_profanity(self, message: str) -> bool:
        """Check if message contains profanity."""
        message_lower = message.lower()
        for pattern in self.PROFANITY_PATTERNS:
            if re.search(pattern, message_lower):
                return True
        return False

    # --- Card Effect Helpers ---

    def get_card_effect(self, card: Card) -> Optional[CardEffect]:
        """Get the special effect for a card."""
        return self.card_effects.get(card.rank.display)

    def get_effect_description(self, card: Card) -> str:
        """Get the description of a card's effect."""
        effect = self.card_effects.get(card.rank.display)
        if effect:
            return effect.description
        return ""

    def should_skip_next(self, card: Card) -> bool:
        """Check if playing this card should skip the next player."""
        effect = self.card_effects.get(card.rank.display)
        return effect and effect.effect == "skip_next"

    def should_reverse(self, card: Card) -> bool:
        """Check if playing this card should reverse direction."""
        effect = self.card_effects.get(card.rank.display)
        return effect and effect.effect == "reverse"

    def should_play_again(self, card: Card) -> bool:
        """Check if player should play again."""
        effect = self.card_effects.get(card.rank.display)
        return effect and effect.effect == "play_again"

    def requires_hit(self, card: Card) -> bool:
        """Check if playing this card requires hitting another player."""
        effect = self.card_effects.get(card.rank.display)
        return effect and effect.effect == "hit_player"

    def is_jack(self, card: Card) -> bool:
        """Check if card is a Jack."""
        return card.rank.display == "J"

    def set_jack_suit(self, suit: Suit) -> None:
        """Set the suit after a Jack is played."""
        self.jack_suit = suit

    def get_effective_suit(self, top_card: Card) -> Suit:
        """Get the effective suit for matching (considering Jack)."""
        if self.jack_suit:
            return self.jack_suit
        return top_card.suit

    # --- Game State Helpers ---

    def reset_for_new_game(self) -> None:
        """Reset state for a new game."""
        self.consecutive_plays = []
        self.jack_suit = None
        self.last_played_card = None

    def get_consecutive_count(self) -> int:
        """Get the current consecutive play count."""
        return len(self.consecutive_plays)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize rule engine state."""
        return {
            "card_effects": {k: {"rank": v.rank, "effect": v.effect, "description": v.description}
                            for k, v in self.card_effects.items()},
            "speech_rules_count": len(self.speech_rules),
            "consecutive_rule": self.consecutive_rule.description if self.consecutive_rule else None,
            "cards_per_player": self.cards_per_player,
            "poo_enabled": self.poo_enabled,
            "current_consecutive": self.get_consecutive_count(),
            "jack_suit": self.jack_suit.full_name if self.jack_suit else None,
        }