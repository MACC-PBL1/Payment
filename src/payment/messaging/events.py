from ..sql import (
    create_deposit_from_movement,
    Movement,
)
from ..global_vars import (
    LISTENING_QUEUES,
    PUBLIC_KEY,
    RABBITMQ_CONFIG,
)
from ..sql.crud import try_create_payment
from chassis.consul import ConsulClient
from chassis.logging import get_logger
from chassis.messaging import (
    MessageType,
    RabbitMQPublisher,
    register_queue_handler,
)
from chassis.sql import SessionLocal
import requests

logger = get_logger(__name__)

@register_queue_handler(
    queue=LISTENING_QUEUES["sagas_reserve"],
    exchange="cmd",
    exchange_type="topic",
    routing_key="payment.reserve"
)
async def reserve_payment(message: MessageType) -> None:
    assert (client_id := message.get("client_id")) is not None, "'client_id' should exist"
    assert (total_amount := message.get("total_amount")) is not None, "'total_amount' should exist"
    assert (response_exchange := message.get("response_exchange")) is not None, "'response_exchange' should exist"
    assert (response_exchange_type := message.get("response_exchange_type")) is not None, "'response_exchange_type' should exist"
    assert (response_routing_key := message.get("response_routing_key")) is not None, "'response_routing_key' should exist"

    client_id = int(client_id)
    total_amount = float(total_amount)
    response_exchange = str(response_exchange)
    response_exchange_type = str(response_exchange_type)
    response_routing_key = str(response_routing_key)
    response = {}

    logger.info(
        "[CMD:PAYMENT_RESERVE:RECEIVED] - Received reserve command: "
        f"client_id={client_id}, "
        f"amount={total_amount} "
    )

    try:
        async with SessionLocal() as db:
            await try_create_payment(db, Movement(client_id=client_id, amount=total_amount))
            await db.commit() 
        response["status"] = "OK"
        logger.info(
            "[EVENT:PAYMENT_RESERVE:SUCCESS] - Payment reserved: "
            f"client_id={client_id}, "
            f"amount={total_amount} "
        )
    except Exception as e:
        response["status"] = f"Error: {e}"
        logger.info(
            "[EVENT:PAYMENT_RESERVE:FAILED] - Payment reserve failed: "
            f"client_id={client_id}, "
            f"amount={total_amount}, "
            f"status='{e}'"
        )

    with RabbitMQPublisher(
        queue="",
        rabbitmq_config=RABBITMQ_CONFIG,
        exchange=response_exchange,
        exchange_type=response_exchange_type,
        routing_key=response_routing_key
    ) as publisher:
        publisher.publish(response)


@register_queue_handler(
    queue=LISTENING_QUEUES["sagas_release"],
    exchange="cmd",
    exchange_type="topic",
    routing_key="payment.release"
)
async def release_payment(message: MessageType) -> None:
    assert (client_id := message.get("client_id")) is not None, "'client_id' should exist."
    assert (order_id := message.get("order_id")) is not None, "'order_id' should exist."
    assert (total_amount := message.get("total_amount")) is not None, "'total_amount' should exist."

    client_id = int(client_id)
    order_id = int(order_id)
    total_amount = float(total_amount)

    logger.info(
        "[CMD:PAYMENT_RELEASE:RECEIVED] - Received release command: "
        f"order_id={order_id}, "
        f"client_id={client_id}, "
        f"amount={total_amount}"
    )

    try:
        async with SessionLocal() as db:
            await create_deposit_from_movement(
                db,
                Movement(client_id=client_id, amount=total_amount)
            )
            await db.commit()

        logger.info(
            "[EVENT:PAYMENT_RELEASE:SUCCESS] - order_id=%s",
            order_id,
        )

        with RabbitMQPublisher(
            queue="",
            exchange="evt",
            exchange_type="topic",
            routing_key="payment.released",
            rabbitmq_config=RABBITMQ_CONFIG,
        ) as publisher:
            publisher.publish({
                "type": "payment.released",
                "order_id": order_id,
                "client_id": client_id,
                "amount": total_amount,
            })

    except Exception as e:
        logger.exception("[PAYMENT_RELEASE:FAILED]")

        with RabbitMQPublisher(
            queue="",
            exchange="evt",
            exchange_type="topic",
            routing_key="payment.failed",
            rabbitmq_config=RABBITMQ_CONFIG,
        ) as publisher:
            publisher.publish({
                "type": "payment.failed",
                "order_id": order_id,
                "reason": str(e),
            })

@register_queue_handler(
    queue=LISTENING_QUEUES["public_key"],
    exchange="public_key",
    exchange_type="fanout"
)
def public_key(message: MessageType) -> None:
    global PUBLIC_KEY
    assert (auth_base_url := ConsulClient(logger).get_service_url("auth")) is not None, (
        "The 'auth' service should be accesible"
    )
    assert "public_key" in message, "'public_key' field should be present."
    assert message["public_key"] == "AVAILABLE", (
        f"'public_key' value is '{message['public_key']}', expected 'AVAILABLE'"
    )
    response = requests.get(f"{auth_base_url}/auth/key", timeout=5)
    assert response.status_code == 200, (
        f"Public key request returned '{response.status_code}', should return '200'"
    )
    data: dict = response.json()
    new_key = data.get("public_key")
    assert new_key is not None, (
        "Auth response did not contain expected 'public_key' field."
    )
    PUBLIC_KEY["key"] = str(new_key)
    logger.info(
        "[EVENT:PUBLIC_KEY:UPDATED] - Public key updated: "
        f"key={PUBLIC_KEY["key"]}"
    )
