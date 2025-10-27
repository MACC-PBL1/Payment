from ..sql import try_create_payment
from ..sql import Movement
from .global_vars import (
    LISTENING_QUEUES,
    PUBLIC_KEY,
    PUBLISHING_QUEUES,
    RABBITMQ_CONFIG,
)
from fastapi import Depends
from typing import (
    Dict,
    Union,
)
from chassis.messaging import (
    MessageType,
    register_queue_handler,
    RabbitMQPublisher,
)
from chassis.sql import SessionLocal
import logging

logger = logging.getLogger(__name__)

@register_queue_handler(LISTENING_QUEUES["request"])
async def request(message: MessageType) -> None:
    logger.info(f"EVENT: Payment requested --> Message: {message}")
    with RabbitMQPublisher(
        queue="events.auth",
        rabbitmq_config=RABBITMQ_CONFIG,
        exchange="events.exchange",
        exchange_type="topic",
        routing_key="events.auth",
        ) as publisher:
            publisher.publish({
                "service_name": "auth",
                "event_type": "Listen",
                "message": f"EVENT: Payment requested --> Message: {message}"
            })


    assert (client_id := message.get("client_id")) is not None, "'client_id' field should exist."
    assert (order_id := message.get("order_id")) is not None, "'order_id' field should exist."
    assert (amount := message.get("amount")) is not None, "'amount' field should exist."

    client_id = int(client_id)
    order_id = int(order_id)
    amount = float(amount)

    response: Dict[str, Union[int, str]] = {
        "client_id": client_id,
        "order_id": order_id,
    }
    
    try:
        async with SessionLocal() as db:
            _ = await try_create_payment(db, Movement(client_id=client_id, amount=order_id))
        response["status"] = "OK"
    except Exception as e:
        response["status"] = f"Error: {e}"

    with RabbitMQPublisher(
        queue=PUBLISHING_QUEUES["confirmation"],
        rabbitmq_config=RABBITMQ_CONFIG,
    ) as publisher:
        publisher.publish(response)
        logger.info(f"EVENT: Confirm payment --> {response}")

    with RabbitMQPublisher(
        queue="events.auth",
        rabbitmq_config=RABBITMQ_CONFIG,
        exchange="events.exchange",
        exchange_type="topic",
        routing_key="events.auth",
        ) as publisher:
            publisher.publish({
                "service_name": "auth",
                "event_type": "Listen",
                "message": f"EVENT: Confirm payment --> {response}"
            })

@register_queue_handler(
    queue=LISTENING_QUEUES["public_key"],
    exchange="public_key",
    exchange_type="fanout"
)
def public_key(message: MessageType) -> None:
    logger.info(f"EVENT: Public key updated --> Message: {message}")
    with RabbitMQPublisher(
        queue="events.auth",
        rabbitmq_config=RABBITMQ_CONFIG,
        exchange="events.exchange",
        exchange_type="topic",
        routing_key="events.auth",
    ) as publisher:
            publisher.publish({
                "service_name": "auth",
                "event_type": "Listen",
                "message": f"EVENT: Public key updated --> Message: {message}"
            })

    global PUBLIC_KEY
    assert (public_key := message.get("public_key")) is not None, "'public_key' field should be present."
    PUBLIC_KEY["key"] = str(public_key)