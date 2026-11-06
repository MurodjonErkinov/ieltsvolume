from .models import Notification


def enqueue(recipient, event, key, payload):
    """Write the outbox in the caller's transaction. A worker delivers later."""
    for channel in Notification.Channel.values:
        Notification.objects.get_or_create(
            recipient=recipient, channel=channel, deduplication_key=key,
            defaults={"event": event, "payload": payload},
        )
