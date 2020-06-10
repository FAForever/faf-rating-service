#!/usr/bin/env python3

import asyncio
import logging
import signal

from service import config, db
from service.message_queue_service import MessageQueueService, message_to_dict
from service.rating_service import RatingService


async def main():
    loop = asyncio.get_running_loop()
    done = asyncio.Future()

    def signal_handler(sig: int, _frame):
        logger.info("Received signal %s, shutting down", signal.Signals(sig))
        if not done.done():
            done.set_result(0)

    # Make sure we can shutdown gracefully
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    database = db.FAFDatabase(loop)
    await database.connect(
        host=config.DB_SERVER,
        port=int(config.DB_PORT),
        user=config.DB_LOGIN,
        password=config.DB_PASSWORD,
        maxsize=10,
        db=config.DB_NAME,
    )
    logger.info("Database connected.")

    mq_service = MessageQueueService()
    await mq_service.initialize()

    rating_service = RatingService(database)
    await rating_service.initialize()

    def on_message(message):
        logging.debug("received message: %s", message.body)
        try:
            parsed_dict = message_to_dict(message)
        except Exception as e:
            logging.debug("Failed to parse message %s: %s", message.body, e)
            message.ack()
        else:
            asyncio.create_task(rating_service.enqueue(parsed_dict))

    await mq_service.listen("test_exchange", "#", on_message)
    await done

    # Cleanup

    await rating_service.shutdown()
    await mq_service.shutdown()

    logger.info("Closing database connection...")
    await database.close()
    logger.info("All done. Exiting.")


if __name__ == "__main__":
    logger = logging.getLogger()
    stderr_handler = logging.StreamHandler()
    stderr_handler.setFormatter(
        logging.Formatter(
            fmt="%(levelname)-8s %(asctime)s %(name)-30s %(message)s",
            datefmt="%b %d  %H:%M:%S",
        )
    )
    logger.addHandler(stderr_handler)
    logger.setLevel(config.LOG_LEVEL)

    asyncio.run(main())
