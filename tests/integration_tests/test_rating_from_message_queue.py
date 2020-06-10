import pytest
import asyncio
from service.message_queue_service import MessageQueueService, message_to_dict
from service.rating_service import RatingService
from service.db.models import leaderboard_rating, leaderboard_rating_journal
from sqlalchemy import and_, select

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def mq_service():
    service = MessageQueueService()
    await service.initialize()

    await service.declare_exchange("test_exchange")

    yield service

    await service.shutdown()


@pytest.fixture
async def rating_service(database):
    service = RatingService(database)
    await service.initialize()
    yield service
    service.kill()


@pytest.fixture
def game_info():
    return {
        "game_id": 111,
        "rating_type": "global",
        "map_id": 222,
        "featured_mod": 0,
        "sim_mod_ids": [],
        "commander_kills": {},
        "validity": "Valid",
        "teams": [
            {"outcome": "VICTORY", "player_ids": [333]},
            {"outcome": "DEFEAT", "player_ids": [444]},
        ],
    }


async def test_rate_game(mq_service, rating_service, game_info):
    outcome_to_id = {
        team_dict["outcome"]: team_dict["player_ids"][0]
        for team_dict in game_info["teams"]
    }

    def on_message(message):
        parsed_dict = message_to_dict(message)
        asyncio.create_task(rating_service.enqueue(parsed_dict))

    await mq_service.listen("test_exchange", "#", on_message)

    await mq_service.publish("test_exchange", "routing.key", game_info)

    await asyncio.sleep(0.1)
    await rating_service._join_rating_queue()

    rating_type_id = rating_service._rating_type_ids["global"]

    async with rating_service._db.acquire() as conn:
        sql = select([leaderboard_rating.c.mean]).where(
            and_(
                leaderboard_rating.c.login_id == outcome_to_id["VICTORY"],
                leaderboard_rating.c.leaderboard_id == rating_type_id,
            )
        )
        results = await conn.execute(sql)
        winner_rating_row = await results.fetchone()

        sql = select([leaderboard_rating.c.mean]).where(
            and_(
                leaderboard_rating.c.login_id == outcome_to_id["DEFEAT"],
                leaderboard_rating.c.leaderboard_id == rating_type_id,
            )
        )
        results = await conn.execute(sql)
        loser_rating_row = await results.fetchone()

        sql = select([leaderboard_rating_journal])
        results = await conn.execute(sql)
        journal_row = await results.fetchone()

    assert winner_rating_row is not None
    assert winner_rating_row["mean"] > 1500

    assert loser_rating_row is not None
    assert loser_rating_row["mean"] < 1500

    assert journal_row is not None
    assert journal_row["leaderboard_id"] == rating_type_id
    assert journal_row["rating_mean_after"] in (
        winner_rating_row["mean"],
        loser_rating_row["mean"],
    )
