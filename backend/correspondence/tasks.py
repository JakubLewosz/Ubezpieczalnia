from celery import shared_task


@shared_task(queue="mail", acks_late=True, reject_on_worker_lost=True, soft_time_limit=210, time_limit=230)
def sync_mailbox(mailbox_id):
    from .sync import synchronize
    return synchronize(mailbox_id)


@shared_task(queue="maintenance")
def poll_mailboxes():
    from .sync import request_sync
    # Periodic execution is independent of any browser; expired leases are
    # recovered by the same atomic reservation used for the ordinary next run.
    return request_sync()


@shared_task(queue="maintenance")
def cleanup_mail_files():
    from .storage import cleanup_stale_files
    return cleanup_stale_files()
