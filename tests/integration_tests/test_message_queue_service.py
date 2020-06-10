import asyncio

import aio_pika
import pytest

from service import config
from service.message_queue_service import MessageQueueService, message_to_dict

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def mq_service():
    service = MessageQueueService()
    await service.initialize()

    await service.declare_exchange("test_exchange")
    await service.declare_exchange(config.EXCHANGE_NAME)

    yield service

    await service.shutdown()


async def test_connect(mq_service):
    await mq_service.declare_exchange("test_topic", aio_pika.ExchangeType.TOPIC)

    assert "test_topic" in mq_service._exchanges


async def test_publish_wrong_exchange(mq_service):
    bad_exchange = "nonexistent_exchange"
    with pytest.raises(KeyError):
        await mq_service.publish(bad_exchange, "", {})


async def test_consumer_receives(mq_service, consumer):
    payload = {"msg": "test message"}
    exchange_name = config.EXCHANGE_NAME
    routing_key = "test.routing.key"
    delivery_mode = aio_pika.DeliveryMode.NOT_PERSISTENT

    await mq_service.publish(exchange_name, routing_key, payload, delivery_mode)

    await asyncio.sleep(0.1)

    assert consumer.callback_count() == 1


async def test_reconnect(mq_service):
    await mq_service.declare_exchange("test_topic", aio_pika.ExchangeType.TOPIC)
    await mq_service.declare_exchange("test_direct", aio_pika.ExchangeType.DIRECT)

    await mq_service.reconnect()

    assert "test_topic" in mq_service._exchanges
    assert mq_service._exchange_types["test_topic"] == aio_pika.ExchangeType.TOPIC
    assert "test_direct" in mq_service._exchanges
    assert mq_service._exchange_types["test_direct"] == aio_pika.ExchangeType.DIRECT


async def test_incorrect_credentials(mocker, caplog):
    mocker.patch("service.config.MQ_PASSWORD", "bad_password")
    service = MessageQueueService()

    await service.initialize()
    expected_warning = "Unable to connect to RabbitMQ. Incorrect credentials?"
    assert expected_warning in [rec.message for rec in caplog.records]
    caplog.clear()

    await service.declare_exchange("test_exchange")
    expected_warning = "Not connected to RabbitMQ, unable to declare exchange."
    assert expected_warning in [rec.message for rec in caplog.records]
    caplog.clear()

    payload = {"msg": "test message"}
    exchange_name = "test_exchange"
    routing_key = "test.routing.key"
    delivery_mode = aio_pika.DeliveryMode.NOT_PERSISTENT
    await service.publish(exchange_name, routing_key, payload, delivery_mode)
    expected_warning = "Not connected to RabbitMQ, unable to publish message."
    assert expected_warning in [rec.message for rec in caplog.records]

    await service.shutdown()


async def test_incorrect_username(mocker, caplog):
    mocker.patch("service.config.MQ_USER", "bad_user")
    service = MessageQueueService()

    await service.initialize()

    expected_warning = "Unable to connect to RabbitMQ. Incorrect credentials?"
    assert expected_warning in [rec.message for rec in caplog.records]


async def test_incorrect_vhost(mocker, caplog):
    mocker.patch("service.config.MQ_VHOST", "bad_vhost")
    service = MessageQueueService()

    await service.initialize()

    assert any("Incorrect vhost?" in rec.message for rec in caplog.records)


async def test_parse_incoming_message(mq_service, consumer):
    payload = {"msg": "test message", "another_key": "value"}
    exchange_name = config.EXCHANGE_NAME
    routing_key = "test.routing.key"
    delivery_mode = aio_pika.DeliveryMode.NOT_PERSISTENT

    await mq_service.publish(exchange_name, routing_key, payload, delivery_mode)

    await asyncio.sleep(0.1)

    received_message = consumer.received_messages[0]
    parsed_message = message_to_dict(received_message)

    for key, value in payload.items():
        assert parsed_message[key] == value
    assert parsed_message["_exchange"] == exchange_name
    assert parsed_message["_routing_key"] == routing_key
    assert parsed_message["_ack"] == received_message.ack
