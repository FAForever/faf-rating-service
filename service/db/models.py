from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    Enum,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

metadata = MetaData()

game_featuredMods = Table(
    "game_featuredMods",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("gamemod", String, unique=True),
    Column("description", Text, nullable=False),
    Column("name", String, nullable=False),
    Column("publish", Boolean, nullable=False, server_default="f"),
    Column("order", Integer, nullable=False, server_default="0"),
    Column("git_url", String),
    Column("git_branch", String),
    Column("file_extension", String),
    Column("allow_override", Boolean),
)

game_player_stats = Table(
    "game_player_stats",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("gameId", Integer, ForeignKey("game_stats.id"), nullable=False),
    Column("playerId", Integer, ForeignKey("login.id"), nullable=False),
    Column("AI", Boolean, nullable=False),
    Column("faction", Integer, nullable=False),
    Column("color", Integer, nullable=False),
    Column("team", Integer, nullable=False),
    Column("place", Integer, nullable=False),
    Column("mean", Float, nullable=False),
    Column("deviation", Float, nullable=False),
    Column("after_mean", Float),
    Column("after_deviation", Float),
    Column("score", Integer),
    Column("scoreTime", TIMESTAMP),
    Column("result", String),
)

game_stats = Table(
    "game_stats",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("startTime", TIMESTAMP, nullable=False, server_default="CURRENT_TIMESTAMP"),
    Column("endTime", TIMESTAMP),
    Column("gameType", Integer, nullable=False),
    Column("gameMod", Integer, ForeignKey("game_featuredMods.id"), nullable=False),
    Column("host", Integer, nullable=False),
    Column("mapId", Integer),
    Column("gameName", String, nullable=False),
    Column("validity", Integer, nullable=False),
)

global_rating = Table(
    "global_rating",
    metadata,
    Column("id", Integer, ForeignKey("login.id"), primary_key=True),
    Column("mean", Float),
    Column("deviation", Float),
    Column("numGames", Integer, nullable=False),
    Column("is_active", Boolean, nullable=False),
)

login = Table(
    "login",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("login", String, nullable=False, unique=True),
    Column("password", String, nullable=False),
    Column("email", String, nullable=False, unique=True),
    Column("ip", String),
    Column("steamid", Integer, unique=True),
    Column("create_time", TIMESTAMP, nullable=False),
    Column("update_time", TIMESTAMP, nullable=False),
    Column("user_agent", String),
    Column("last_login", TIMESTAMP),
)

ladder1v1_rating = Table(
    "ladder1v1_rating",
    metadata,
    Column("id", Integer, ForeignKey("login.id"), primary_key=True),
    Column("mean", Float),
    Column("deviation", Float),
    Column("numGames", Integer, nullable=False),
    Column("winGames", Integer, nullable=False),
    Column("is_active", Boolean, nullable=False),
)

leaderboard = Table(
    "leaderboard",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("technical_name", String, nullable=False, unique=True),
)

leaderboard_rating = Table(
    "leaderboard_rating",
    metadata,
    Column("login_id", Integer, ForeignKey("login.id")),
    Column("mean", Float),
    Column("deviation", Float),
    Column("total_games", Integer, nullable=False),
    Column("won_games", Integer, nullable=False),
    Column("leaderboard_id", Integer, ForeignKey("leaderboard.id")),
)

leaderboard_rating_journal = Table(
    "leaderboard_rating_journal",
    metadata,
    Column("game_player_stats_id", Integer, ForeignKey("game_player_stats.id")),
    Column("leaderboard_id", Integer, ForeignKey("leaderboard.id")),
    Column("rating_mean_before", Float, nullable=False),
    Column("rating_mean_after", Float, nullable=False),
    Column("rating_deviation_before", Float, nullable=False),
    Column("rating_deviation_after", Float, nullable=False),
)
