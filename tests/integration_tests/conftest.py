import aio_pika
import pytest

import mock
from service import config
from service.decorators import with_logger


@with_logger
class Consumer:
    def __init__(self):
        self._callback = mock.Mock()
        self.received_messages = []

    async def initialize(self):
        self.connection = await aio_pika.connect(
            "amqp://{user}:{password}@localhost/{vhost}".format(
                user=config.MQ_USER, password=config.MQ_PASSWORD, vhost=config.MQ_VHOST
            )
        )
        channel = await self.connection.channel()
        exchange = await channel.declare_exchange(
            config.EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC
        )
        self.queue = await channel.declare_queue("test_queue", exclusive=True)

        await self.queue.bind(exchange, routing_key="#")
        self.consumer_tag = await self.queue.consume(self.callback)

    def callback(self, message):
        self.received_messages.append(message)
        self._logger.debug("Received message %r", message)
        self._callback()

    def callback_count(self):
        return self._callback.call_count

    async def shutdown(self):
        await self.queue.cancel(self.consumer_tag)
        await self.connection.close()


@pytest.fixture
async def consumer():
    consumer = Consumer()
    await consumer.initialize()

    yield consumer

    await consumer.shutdown()
