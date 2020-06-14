import asyncio
from typing import Dict

from aio_pika import IncomingMessage

import aiocron
from service import config
from service.db import FAFDatabase
from service.db.models import (game_player_stats, leaderboard,
                               leaderboard_rating, leaderboard_rating_journal)
from service.decorators import with_logger
from service.message_queue_service import MessageQueueService, message_to_dict
from service.metrics import rating_service_backlog
from sqlalchemy import and_, select
from trueskill import Rating

from .game_rater import GameRater, GameRatingError
from .typedefs import (GameOutcome, GameRatingData,
                       GameRatingSummaryWithCallback, PlayerID, RatingType,
                       ServiceNotReadyError, TeamRatingData)


@with_logger
class RatingService:
    """
    Service responsible for calculating and saving trueskill rating updates.
    To avoid race conditions, rating updates from a single game ought to be
    atomic.
    """

    def __init__(self, database: FAFDatabase, mq_service: MessageQueueService):
        self._db = database
        self._mq_service = mq_service
        self._accept_input = False
        self._queue = asyncio.Queue()
        self._task = None
        self._rating_type_ids = None

    async def initialize(self) -> None:
        if self._task is not None:
            self._logger.error("Service already runnning or not properly shut down.")
            return

        await self.update_data()
        self._update_cron = aiocron.crontab("*/10 * * * *", func=self.update_data)
        self._accept_input = True
        self._logger.debug("RatingService starting...")
        self._task = asyncio.create_task(self._handle_rating_queue())

        # Listen for game results
        await self._mq_service.listen(
            config.EXCHANGE_NAME, config.RATING_REQUEST_ROUTING_KEY, self.handle_message
        )

    async def update_data(self):
        async with self._db.acquire() as conn:
            sql = select([leaderboard])
            result = await conn.execute(sql)
            rows = await result.fetchall()

        self._rating_type_ids = {row["technical_name"]: row["id"] for row in rows}

    def handle_message(self, message: IncomingMessage):
        """
        Parses a rating request message from RabbitMQ and queues it up.
        Needs to be synchronous to be used as a callback.
        """
        try:
            parsed_dict = message_to_dict(message)
        except Exception as e:
            self._logger.warning(
                "Failed to parse message with body %s\n Raised exception %s",
                message.body,
                e,
            )
            message.reject()
        else:
            asyncio.create_task(self.enqueue(parsed_dict))

    async def enqueue(self, game_info: Dict) -> None:
        if not self._accept_input:
            self._logger.warning("Dropped rating request %s", game_info)
            raise ServiceNotReadyError(
                "RatingService not yet initialized or shutting down."
            )

        try:
            summary = GameRatingSummaryWithCallback.from_game_info_dict(game_info)
        except Exception as e:
            self._logger.warning(
                "Failed to parse game_info from message id %s: %s",
                game_info.get("_id"),
                str(e),
            )
            if game_info.get("_ack") is not None:
                game_info["_ack"]()
            return
        self._logger.debug("Queued up rating request for game %s", summary.game_id)
        await self._queue.put(summary)
        rating_service_backlog.set(self._queue.qsize())

    async def _handle_rating_queue(self) -> None:
        self._logger.info("RatingService started!")
        while self._accept_input or not self._queue.empty():
            summary = await self._queue.get()
            self._logger.debug("Now rating request for game  %s", summary.game_id)

            try:
                await self._rate(summary)
            except GameRatingError:
                self._logger.warning("Error rating game %s", summary)
            except Exception:  # pragma: no cover
                self._logger.exception("Failed rating request %s", summary)
            else:
                self._logger.debug("Done rating request.")

            self._queue.task_done()
            if summary.callback is not None:
                summary.callback()
            rating_service_backlog.set(self._queue.qsize())

        self._logger.info("RatingService stopped.")

    async def _rate(self, summary: GameRatingSummaryWithCallback) -> None:
        rating_data = await self._get_rating_data(summary)
        new_ratings = GameRater.compute_rating(rating_data)

        outcome_map = {
            player_id: team.outcome
            for team in summary.teams
            for player_id in team.player_ids
        }

        old_ratings = {
            player_id: rating
            for team in rating_data
            for player_id, rating in team.ratings.items()
        }
        await self._persist_rating_changes(
            summary.game_id, summary.rating_type, old_ratings, new_ratings, outcome_map
        )

    async def _get_rating_data(
        self, summary: GameRatingSummaryWithCallback
    ) -> GameRatingData:
        ratings = {}
        for team in summary.teams:
            for player_id in team.player_ids:
                ratings[player_id] = await self._get_player_rating(
                    player_id, summary.rating_type
                )

        return [
            TeamRatingData(
                team.outcome,
                {player_id: ratings[player_id] for player_id in team.player_ids},
            )
            for team in summary.teams
        ]

    async def _get_player_rating(
        self, player_id: int, rating_type: RatingType
    ) -> Rating:
        if self._rating_type_ids is None:
            self._logger.warning(
                "Tried to fetch player data before initializing service."
            )
            raise ServiceNotReadyError("RatingService not yet initialized.")

        rating_type_id = self._rating_type_ids.get(rating_type)
        if rating_type_id is None:
            raise ValueError(f"Unknown rating type {rating_type}.")

        async with self._db.acquire() as conn:
            sql = select(
                [leaderboard_rating.c.mean, leaderboard_rating.c.deviation]
            ).where(
                and_(
                    leaderboard_rating.c.login_id == player_id,
                    leaderboard_rating.c.leaderboard_id == rating_type_id,
                )
            )

            result = await conn.execute(sql)
            row = await result.fetchone()

        if row is not None:
            return Rating(row["mean"], row["deviation"])

        # No rating entry found,
        # will create a new default rating entry
        new_rating = await self._create_default_rating(conn, player_id, rating_type)
        return new_rating

    async def _create_default_rating(
        self, conn, player_id: int, rating_type: RatingType
    ):
        default_mean = config.START_RATING_MEAN
        default_deviation = config.START_RATING_DEV
        rating_type_id = self._rating_type_ids.get(rating_type)

        insertion_sql = leaderboard_rating.insert().values(
            login_id=player_id,
            mean=default_mean,
            deviation=default_deviation,
            total_games=0,
            won_games=0,
            leaderboard_id=rating_type_id,
        )
        await conn.execute(insertion_sql)

        return Rating(default_mean, default_deviation)

    async def _persist_rating_changes(
        self,
        game_id: int,
        rating_type: RatingType,
        old_ratings: Dict[PlayerID, Rating],
        new_ratings: Dict[PlayerID, Rating],
        outcomes: Dict[PlayerID, GameOutcome],
    ) -> None:
        """
        Persist computed ratings to the respective players' selected rating
        """
        async with self._db.acquire() as conn:
            for player_id, new_rating in new_ratings.items():
                old_rating = old_ratings[player_id]

                rating_type_id = self._rating_type_ids[rating_type]

                journal_insert_sql = leaderboard_rating_journal.insert().values(
                    leaderboard_id=rating_type_id,
                    rating_mean_before=old_rating.mu,
                    rating_deviation_before=old_rating.sigma,
                    rating_mean_after=new_rating.mu,
                    rating_deviation_after=new_rating.sigma,
                    game_player_stats_id=select([game_player_stats.c.id]).where(
                        and_(
                            game_player_stats.c.playerId == player_id,
                            game_player_stats.c.gameId == game_id,
                        )
                    ),
                )
                await conn.execute(journal_insert_sql)

                victory_increment = (
                    1 if outcomes[player_id] is GameOutcome.VICTORY else 0
                )
                rating_update_sql = (
                    leaderboard_rating.update()
                    .where(
                        and_(
                            leaderboard_rating.c.login_id == player_id,
                            leaderboard_rating.c.leaderboard_id == rating_type_id,
                        )
                    )
                    .values(
                        mean=new_rating.mu,
                        deviation=new_rating.sigma,
                        total_games=leaderboard_rating.c.total_games + 1,
                        won_games=leaderboard_rating.c.won_games + victory_increment,
                    )
                )
                await conn.execute(rating_update_sql)

                await self._notify_rating_change(player_id, rating_type, new_rating)

    async def _notify_rating_change(
        self, player_id: PlayerID, rating_type: RatingType, new_rating: Rating
    ) -> None:
        await self._mq_service.publish(
            config.EXCHANGE_NAME,
            config.RATING_UPDATE_ROUTING_KEY,
            {
                "player_id": player_id,
                "rating_type": rating_type,
                "new_rating_mean": new_rating.mu,
                "new_rating_deviation": new_rating.sigma,
            },
        )

    async def _join_rating_queue(self) -> None:
        """
        Offers a call that is blocking until the rating queue has been emptied.
        Mostly for testing purposes.
        """
        await self._queue.join()

    async def shutdown(self) -> None:
        """
        Finish rating all remaining games, then exit.
        """
        self._accept_input = False
        self._logger.debug(
            "Shutdown initiated. Waiting on current queue: %s", self._queue
        )
        await self._queue.join()
        self._task = None
        self._logger.debug("Queue emptied: %s", self._queue)

    def kill(self) -> None:
        """
        Exit without waiting for the queue to join.
        """
        self._accept_input = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
