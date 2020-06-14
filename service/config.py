import logging

import trueskill

# Logging setup
TRACE = 5
logging.addLevelName(TRACE, "TRACE")
logging.getLogger("aio_pika").setLevel(logging.INFO)

# Credit to Axle for parameter changes,
# see: http://forums.faforever.com/viewtopic.php?f=45&t=11698#p119599
# Optimum values for ladder here, using them for global as well.
trueskill.setup(mu=1500, sigma=500, beta=240, tau=10, draw_probability=0.10)


LOG_LEVEL = "DEBUG"

DB_SERVER = "127.0.0.1"
DB_PORT = 3306
DB_LOGIN = "root"
DB_PASSWORD = "banana"
DB_NAME = "faf"

START_RATING_MEAN = 1500
START_RATING_DEV = 500

MQ_USER = "faf-rating-service"
MQ_PASSWORD = "banana"
MQ_PORT = 5672
MQ_VHOST = "/faf-lobby"
MQ_PREFETCH_COUNT = 300

EXCHANGE_NAME = "faf-rabbitmq"
RATING_REQUEST_ROUTING_KEY = "success.gameResults.create"
RATING_UPDATE_ROUTING_KEY = "success.rating.update"
RATING_UPDATE_FAIL_ROUTING_KEY = "failure.rating.update"
