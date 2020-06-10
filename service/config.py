import logging

import trueskill

# Logging setup
TRACE = 5
logging.addLevelName(TRACE, "TRACE")
logging.getLogger("aiomeasures").setLevel(logging.INFO)

# Constants
FFA_TEAM = 1

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

MQ_USER = "faf-lobby"
MQ_PASSWORD = "banana"
MQ_PORT = 5672
MQ_VHOST = "/faf-lobby"
