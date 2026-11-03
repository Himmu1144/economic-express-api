import logging
import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import DatabaseError, close_old_connections
from news.signals import deliver_pending
from news.models import RateBucket


class Command(BaseCommand):
    help = "Run durable webhook retries and scheduled publication invalidation every 2 seconds."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        while True:
            close_old_connections()
            try:
                deliver_pending()
                RateBucket.objects.filter(expires_at__lt=timezone.now()).delete()
            except DatabaseError:
                logging.getLogger(__name__).exception(
                    "Worker database unavailable; retrying"
                )
                if options["once"]:
                    raise
            if options["once"]:
                return
            time.sleep(2)
