from model.repositories.user_repository import get_notification_count, get_notification_list


def fetch_notifications(status: str = "active", limit: int = None, offset: int = None):
    return get_notification_list(status=status, limit=limit, offset=offset)


def fetch_notification_count(status: str = "active"):
    return get_notification_count(status=status)
