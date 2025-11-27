from ..sql import Movement
from .global_vars import (
    LISTENING_QUEUES,
    PUBLIC_KEY,
    PUBLISHING_QUEUES,
    RABBITMQ_CONFIG,
)
from chassis.messaging import (
    MessageType,
    register_queue_handler,
    RabbitMQPublisher,
)
from ..sql.crud import try_create_payment
from chassis.sql import SessionLocal
from chassis.logging.rabbitmq_logging import log_with_context
import logging

logger = logging.getLogger("payment")   # ✔ servicio = payment


# =====================================================================================
# PAYMENT REQUEST
# =====================================================================================
@register_queue_handler(LISTENING_QUEUES["request"])
async def request(message: MessageType) -> None:

    logger.info(f"EVENT: Payment requested --> Message: {message}")

    # Monitoring event
    with RabbitMQPublisher(
        queue="events.payment",
        rabbitmq_config=RABBITMQ_CONFIG,
        exchange="events.exchange",
        exchange_type="topic",
        routing_key="events.payment",
    ) as publisher:
        publisher.publish({
            "service_name": "payment",
            "event_type": "Listen",
            "message": f"EVENT: Payment requested --> Message: {message}"
        })

    # Required fields
    assert (client_id := message.get("client_id")) is not None
    assert (order_id := message.get("order_id")) is not None
    assert (amount := message.get("amount")) is not None

    client_id = int(client_id)
    order_id = int(order_id)
    amount = float(amount)

    # Log audit data
    log_with_context(
        logger,
        logging.INFO,
        "Payment request received",
        client_id=client_id,
        order_id=order_id
    )

    response = {
        "client_id": client_id,
        "order_id": order_id,
    }

    try:
        async with SessionLocal() as db:
            # ❗ BUG FIX: before you used amount=order_id (incorrect)
            await try_create_payment(db, Movement(client_id=client_id, amount=amount))
        response["status"] = "OK"

    except Exception as e:
        response["status"] = f"Error: {e}"
        logger.warning(f"Payment error: {e}")

    # Send confirmation
    with RabbitMQPublisher(
        queue=PUBLISHING_QUEUES["confirmation"],
        rabbitmq_config=RABBITMQ_CONFIG,
    ) as publisher:
        publisher.publish(response)

    log_with_context(
        logger,
        logging.INFO,
        f"EVENT: Confirm payment --> {response}",
        client_id=client_id,
        order_id=order_id
    )

    # Monitoring event
    with RabbitMQPublisher(
        queue="events.payment",
        rabbitmq_config=RABBITMQ_CONFIG,
        exchange="events.exchange",
        exchange_type="topic",
        routing_key="events.payment",
    ) as publisher:
        publisher.publish({
            "service_name": "payment",
            "event_type": "Publish",
            "message": f"EVENT: Confirm payment --> {response}"
        })


# =====================================================================================
# PUBLIC KEY UPDATE
# =====================================================================================
@register_queue_handler(
    queue=LISTENING_QUEUES["public_key"],
    exchange="public_key",
    exchange_type="fanout"
)
def public_key(message: MessageType) -> None:

    logger.info(f"EVENT: Public key updated --> Message: {message}")

    with RabbitMQPublisher(
        queue="events.payment",
        rabbitmq_config=RABBITMQ_CONFIG,
        exchange="events.exchange",
        exchange_type="topic",
        routing_key="events.payment",
    ) as publisher:
        publisher.publish({
            "service_name": "payment",
            "event_type": "Listen",
            "message": f"EVENT: Public key updated --> Message: {message}"
        })

    assert (public_key := message.get("public_key"))
    PUBLIC_KEY["key"] = str(public_key)

    log_with_context(
        logger,
        logging.INFO,
        "Public key updated"
    )


# =====================================================================================
# CMD HANDLER
# =====================================================================================
def cmd(message: MessageType) -> None:

    logger.info(f"EVENT: cmd --> Message: {message}")

    assert (response_destination := message.get("response_destination")) is not None
    assert (client_id := message.get("client_id")) is not None
    assert (amount := message.get("amount")) is not None

    client_id = int(client_id)
    amount = float(amount)

    # Audit log
    log_with_context(
        logger,
        logging.INFO,
        "CMD executed",
        client_id=client_id
    )

    with RabbitMQPublisher(
        queue=response_destination,
        rabbitmq_config=RABBITMQ_CONFIG,
    ) as publisher:
        publisher.publish({
            "status": try_create_payment(client_id, amount),
        })
