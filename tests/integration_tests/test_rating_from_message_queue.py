import asyncio

import pytest

from service import config
from service.db.models import leaderboard_rating, leaderboard_rating_journal
from service.message_queue_service import message_to_dict
from sqlalchemy import and_, select
from trueskill import Rating

pytestmark = pytest.mark.asyncio


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


async def test_rate_game(message_queue_service, rating_service, game_info, consumer):
    outcome_to_id = {
        team_dict["outcome"]: team_dict["player_ids"][0]
        for team_dict in game_info["teams"]
    }

    await message_queue_service.publish(
        config.EXCHANGE_NAME, config.RATING_REQUEST_ROUTING_KEY, game_info
    )

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

    print(consumer.received_messages)
    assert any(
        message.routing_key == "success.rating.update"
        for message in consumer.received_messages
    )


async def test_notify_rating_change(rating_service, consumer):
    player_id = 1
    new_rating = Rating(1000, 100)
    rating_type = "global"

    await rating_service._notify_rating_change(player_id, rating_type, new_rating)
    await asyncio.sleep(0.1)

    parsed_messages = [
        message_to_dict(message) for message in consumer.received_messages
    ]
    assert any(
        message.get("player_id") == player_id
        and message.get("new_rating_mean") == new_rating.mu
        and message.get("new_rating_deviation") == new_rating.sigma
        and message.get("rating_type") == rating_type
        for message in parsed_messages
    )
