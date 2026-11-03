import logging, threading
from datetime import timedelta
import requests
from django.conf import settings
from django.db import close_old_connections, transaction
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.utils import timezone
from .models import Article, Category, Video, Author, Tag, Revalidation

log = logging.getLogger(__name__)
_lock = threading.Lock()


def deliver_pending():
    if not settings.FRONTEND_URL or not settings.REVALIDATE_SECRET:
        return
    if not _lock.acquire(blocking=False):
        return
    try:
        for event in Revalidation.objects.filter(
            delivered_at__isnull=True, due_at__lte=timezone.now()
        ).order_by("due_at")[:100]:
            try:
                response = requests.post(
                    settings.FRONTEND_URL + "/api/revalidate",
                    json={"tags": event.tags},
                    headers={"x-revalidate-secret": settings.REVALIDATE_SECRET},
                    timeout=5,
                )
                response.raise_for_status()
                event.delivered_at = timezone.now()
            except requests.RequestException:
                log.warning("Revalidation %s failed; queued for retry", event.pk)
                event.attempts += 1
                event.due_at = timezone.now() + timedelta(
                    seconds=min(300, 2 ** min(event.attempts, 8))
                )
            event.save()
    finally:
        _lock.release()


def background():
    close_old_connections()
    try:
        deliver_pending()
    except Exception:
        log.exception("Revalidation worker failed")
    finally:
        close_old_connections()


def enqueue(tags, due=None):
    Revalidation.objects.create(tags=tags, due_at=due or timezone.now())
    if not settings.TESTING:
        transaction.on_commit(
            lambda: threading.Thread(target=background, daemon=True).start()
        )


@receiver(post_save)
@receiver(post_delete)
def changed(sender, instance, **kwargs):
    if sender not in {Article, Category, Video, Author, Tag}:
        return
    tags = ["articles"]
    if sender == Article:
        tags += [f"article:{instance.slug}"]
        if (
            instance.status == "published"
            and instance.published_at > timezone.now()
            and not instance.archived_at
        ):
            enqueue(tags, instance.published_at)
    if sender == Category:
        tags += ["categories"]
    enqueue(tags)


@receiver(m2m_changed, sender=Article.tags.through)
def tags_changed(sender, instance, action, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        enqueue(["articles", f"article:{instance.slug}"])
