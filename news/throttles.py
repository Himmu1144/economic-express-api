import hashlib, time
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.throttling import BaseThrottle
from .models import RateBucket


class DatabaseThrottle(BaseThrottle):
    scope, limit, period = "view", 30, 60

    def allow_request(self, request, view):
        # REMOTE_ADDR only: configure the ingress to supply the verified client IP.
        ident = request.META.get("REMOTE_ADDR", "unknown")
        window = int(time.time()) // self.period
        key = hashlib.sha256(
            f"{settings.SECRET_KEY}:{self.scope}:{ident}:{window}".encode()
        ).hexdigest()
        with transaction.atomic():
            row, _ = RateBucket.objects.get_or_create(
                key=key,
                defaults={
                    "expires_at": timezone.now() + timedelta(seconds=self.period * 2)
                },
            )
            row = RateBucket.objects.select_for_update().get(pk=row.pk)
            if row.count >= self.limit:
                return False
            row.count += 1
            row.save(update_fields=["count"])
        return True

    def wait(self):
        return self.period


class NewsletterThrottle(DatabaseThrottle):
    scope, limit, period = "newsletter", 5, 3600
