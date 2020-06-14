import asyncio
import json
from typing import Dict

import aio_pika
from aio_pika import DeliveryMode, ExchangeType
from aio_pika.exceptions import ProbableAuthenticationError
from pamqp import specification

from service import config
from service.decorators import with_logger


@with_logger
class MessageQueueService:
    def __init__(self) -> None:
        """
        Service handling connection to the message queue
        and providing an interface to publish messages.
        """
        self._logger.info("Message queue service created.")
        self._connection = None
        self._channel = None
        self._exchanges = {}
        self._exchange_types = {}

    async def initialize(self) -> None:
        if self._connection is not None:
            return

        await self._connect()

    async def _connect(self) -> None:
        try:
            self._connection = await aio_pika.connect_robust(
                "amqp://{user}:{password}@localhost:{port}/{vhost}".format(
                    user=config.MQ_USER,
                    password=config.MQ_PASSWORD,
                    vhost=config.MQ_VHOST,
                    port=config.MQ_PORT,
                ),
                loop=asyncio.get_running_loop(),
            )
        except ConnectionError:
            self._logger.warning("Unable to connect to RabbitMQ. Is it running?")
            return
        except ProbableAuthenticationError:
            self._logger.warning(
                "Unable to connect to RabbitMQ. Incorrect credentials?"
            )
            return
        except Exception as e:
            self._logger.warning(
                "Unable to connect to RabbitMQ due to unhandled excpetion %s. Incorrect vhost?",
                e,
            )
            return

        self._channel = await self._connection.channel()
        if config.MQ_PREFETCH_COUNT:
            await self._channel.set_qos(prefetch_count=config.MQ_PREFETCH_COUNT)
        self._logger.debug("Connected to RabbitMQ %r", self._connection)

    async def declare_exchange(
        self, exchange_name: str, exchange_type: ExchangeType = ExchangeType.TOPIC
    ) -> None:
        if self._connection is None:
            self._logger.warning(
                "Not connected to RabbitMQ, unable to declare exchange."
            )
            return

        new_exchange = await self._channel.declare_exchange(
            exchange_name, exchange_type
        )

        self._exchanges[exchange_name] = new_exchange
        self._exchange_types[exchange_name] = exchange_type

    async def shutdown(self) -> None:
        if self._channel is not None:
            await self._channel.close()
            self._channel = None

        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def publish(
        self,
        exchange_name: str,
        routing: str,
        payload: Dict,
        delivery_mode: DeliveryMode = DeliveryMode.PERSISTENT,
    ) -> None:
        if self._connection is None:
            self._logger.warning(
                "Not connected to RabbitMQ, unable to publish message."
            )
            return

        exchange = self._exchanges.get(exchange_name)
        if exchange is None:
            raise KeyError(f"Unknown exchange {exchange_name}.")

        message = aio_pika.Message(
            json.dumps(payload).encode(), delivery_mode=delivery_mode
        )

        confirmation = await exchange.publish(message, routing_key=routing)
        if not isinstance(confirmation, specification.Basic.Ack):
            self._logger.warning(
                "Message could not be delivered to %s, received %s",
                routing,
                confirmation,
            )

    async def listen(
        self,
        exchange_name: str,
        routing_key: str,
        callback,
        exchange_type=ExchangeType.TOPIC,
    ) -> None:
        if exchange_name not in self._exchanges:
            await self.declare_exchange(exchange_name, exchange_type)

        queue = await self._channel.declare_queue("", exclusive=True, durable=True)

        await queue.bind(exchange=exchange_name, routing_key=routing_key)

        await queue.consume(callback)

    async def reconnect(self) -> None:
        await self.shutdown()
        await self.initialize()

        for exchange_name in list(self._exchanges.keys()):
            await self.declare_exchange(
                exchange_name, self._exchange_types[exchange_name]
            )


def message_to_dict(message: aio_pika.IncomingMessage) -> Dict:
    decoded_dict = json.loads(message.body.decode())
    decoded_dict.update(
        {
            "_ack": message.ack,
            "_nack": message.nack,
            "_exchange": message.exchange,
            "_id": message.message_id,
            "_routing_key": message.routing_key,
        }
    )
    return decoded_dict
