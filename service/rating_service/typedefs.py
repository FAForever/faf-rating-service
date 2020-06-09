from typing import Dict, List, NamedTuple, Set, Optional, Callable
from enum import Enum, unique

from trueskill import Rating

PlayerID = int


# Values correspond to legacy table names.
# FIXME Should be dropped soon
# in favour of looking up rating types in `leaderboard`
class RatingType(Enum):
    GLOBAL = "global"
    LADDER_1V1 = "ladder_1v1"


@unique
class Victory(Enum):
    DEMORALIZATION = 0
    DOMINATION = 1
    ERADICATION = 2
    SANDBOX = 3


class GameOutcome(Enum):
    VICTORY = "VICTORY"
    DEFEAT = "DEFEAT"
    DRAW = "DRAW"
    MUTUAL_DRAW = "MUTUAL_DRAW"
    UNKNOWN = "UNKNOWN"
    CONFLICTING = "CONFLICTING"


class TeamRatingSummary(NamedTuple):
    outcome: GameOutcome
    player_ids: Set[int]


class TeamRatingData(NamedTuple):
    outcome: GameOutcome
    ratings: Dict[int, Rating]


GameRatingData = List[TeamRatingData]


class GameRatingSummaryWithCallback(NamedTuple):
    """
    Holds minimal information needed to rate a game.
    Fields:
     - game_id: id of the game to rate
     - rating_type: RatingType (e.g. LADDER_1V1)
     - teams: a list of two TeamRatingSummaries
    """

    game_id: int
    rating_type: RatingType
    teams: List[TeamRatingSummary]
    callback: Optional[Callable]

    @classmethod
    def from_game_info_dict(cls, game_info: Dict) -> "GameRatingSummaryWithCallback":
        if len(game_info["teams"]) != 2:
            raise ValueError("Detected other than two teams.")

        return cls(
            game_info["game_id"],
            getattr(RatingType, game_info["rating_type"]),
            [
                TeamRatingSummary(
                    getattr(GameOutcome, summary["outcome"]), set(summary["player_ids"])
                )
                for summary in game_info["teams"]
            ],
            game_info.get("_ack"),
        )


class RatingServiceError(Exception):
    pass


class ServiceNotReadyError(RatingServiceError):
    pass


# Identifiers must be kept in sync with the contents of the invalid_game_reasons table.
# New reasons added should have a description added to that table. Identifiers should never be
# reused, and values should never be deleted from invalid_game_reasons.
@unique
class ValidityState(Enum):
    VALID = 0
    TOO_MANY_DESYNCS = 1
    WRONG_VICTORY_CONDITION = 2
    NO_FOG_OF_WAR = 3
    CHEATS_ENABLED = 4
    PREBUILT_ENABLED = 5
    NORUSH_ENABLED = 6
    BAD_UNIT_RESTRICTIONS = 7
    BAD_MAP = 8
    TOO_SHORT = 9
    BAD_MOD = 10
    COOP_NOT_RANKED = 11
    MUTUAL_DRAW = 12
    SINGLE_PLAYER = 13
    FFA_NOT_RANKED = 14
    UNEVEN_TEAMS_NOT_RANKED = 15
    UNKNOWN_RESULT = 16
    UNLOCKED_TEAMS = 17
    MULTI_TEAM = 18
    HAS_AI_PLAYERS = 19
    CIVILIANS_REVEALED = 20
    WRONG_DIFFICULTY = 21
    EXPANSION_DISABLED = 22
    SPAWN_NOT_FIXED = 23
    OTHER_UNRANK = 24


class BasicGameInfo(NamedTuple):
    """
    Holds basic information about a game that does not change after launch.
    Fields:
     - game_id: id of the game
     - rating_type: RatingType (e.g. LADDER_1V1)
     - map_id: id of the map used
     - game_mode: name of the featured mod
    """

    game_id: int
    rating_type: Optional[RatingType]
    map_id: int
    game_mode: str
    mods: List[int]
    teams: List[Set["Player"]]


class EndedGameInfo(NamedTuple):
    """
    Holds the outcome of an ended game.
    Fields:
     - game_id: id of the game
     - rating_type: RatingType (e.g. LADDER_1V1)
     - map_id: id of the map used
     - game_mode: name of the featured mod
     - validity: ValidityState (e.g. VALID or TOO_SHORT)
     - team_summaries: a list of TeamRatingSummaries containing IDs of players
       on the team and the team's outcome
    """

    game_id: int
    rating_type: Optional[RatingType]
    map_id: int
    game_mode: str
    mods: List[int]
    commander_kills: Dict[str, int]
    validity: ValidityState
    team_summaries: List[TeamRatingSummary]

    @classmethod
    def from_basic(
        cls,
        basic_info: BasicGameInfo,
        validity: ValidityState,
        team_outcomes: List[GameOutcome],
        commander_kills: Dict[str, int],
    ) -> "EndedGameInfo":
        if len(basic_info.teams) != len(team_outcomes):
            raise ValueError(
                "Team sets of basic_info and team outcomes must refer to the "
                "same number of teams in the same order."
            )

        return cls(
            basic_info.game_id,
            basic_info.rating_type,
            basic_info.map_id,
            basic_info.game_mode,
            basic_info.mods,
            commander_kills,
            validity,
            [
                TeamRatingSummary(outcome, set(player.id for player in team))
                for outcome, team in zip(team_outcomes, basic_info.teams)
            ],
        )

    def to_dict(self):
        return {
            "game_id": self.game_id,
            "rating_type": self.rating_type.name
            if self.rating_type is not None
            else "None",
            "map_id": self.map_id,
            "featured_mod": self.game_mode,
            "sim_mod_ids": self.mods,
            "commander_kills": self.commander_kills,
            "validity": self.validity.name,
            "teams": [
                {
                    "outcome": team_summary.outcome.name,
                    "player_ids": list(team_summary.player_ids),
                }
                for team_summary in self.team_summaries
            ],
        }
