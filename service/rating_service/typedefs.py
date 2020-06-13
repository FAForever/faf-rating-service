from enum import Enum
from typing import Callable, Dict, List, NamedTuple, Optional, Set

from trueskill import Rating

PlayerID = int

# RatingType is now a plain string instead of the hardcoded enum.
# It should correspond to the `technical_name` column
# of the `leaderboard` table
# e.g. "global" or "ladder_1v1"
RatingType = str


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
     - rating_type: RatingType (e.g. "ladder_1v1")
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
            game_info["rating_type"],
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
