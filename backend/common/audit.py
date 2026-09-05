from .models import AuditEvent


def record(user, action, object_type, object_id, client_id=None, metadata=None):
    return AuditEvent.objects.create(
        actor=user if user and user.is_authenticated else None,
        action=action,
        object_type=object_type,
        object_id=object_id,
        client_id=client_id,
        metadata=metadata or {},
    )
