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
from chassis.consul import ConsulClient
import logging
import requests
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


def public_key(message: MessageType) -> None:
    logger.info(f"EVENT: Public key updated: {message}")
    global PUBLIC_KEY

    assert "public_key" in message, "'public_key' field should be present."
    assert message["public_key"] == "AVAILABLE", (
        f"'public_key' value is '{message['public_key']}', expected 'AVAILABLE'"
    )

    consul = ConsulClient(logger)
    auth_base_url = consul.get_service_url("auth-service")
    if not auth_base_url:
        logger.error("The auth service couldn't be found")
        return

    target_url = f"{auth_base_url}/auth-service/key"

    try:
        response = requests.get(target_url, timeout=5)

        if response.status_code == 200:
            data = response.json()
            new_key = data.get("public_key")

            assert new_key is not None, (
                "Auth response did not contain expected 'public_key' field."
            )

            PUBLIC_KEY["key"] = str(new_key)
            logger.info("Public key updated")

        else:
            logger.warning(f"Auth answered with an error: {response.status_code}")

    except Exception as e:
        logger.error(f"Problem in the auth request: {e}")


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
