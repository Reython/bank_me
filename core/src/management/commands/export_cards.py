import csv

from django.core.management.base import BaseCommand

from src.models import Card
from src.utils import format_card, format_phone


class Command(BaseCommand):
    help = "Export cards to CSV with optional filtering."

    def add_arguments(self, parser):
        parser.add_argument("--status", choices=[choice[0] for choice in Card.STATUS_CHOICES])
        parser.add_argument("--card-number")
        parser.add_argument("--phone")
        parser.add_argument("--output", default="cards_export.csv")

    def handle(self, *args, **options):
        queryset = Card.objects.all()
        status = options.get("status")
        card_number = options.get("card_number")
        phone = options.get("phone")
        output = options["output"]

        if status:
            queryset = queryset.filter(status=status)
        if card_number:
            queryset = queryset.filter(card_number__icontains=card_number.replace(" ", ""))
        if phone:
            queryset = queryset.filter(phone__icontains=phone.replace(" ", ""))

        with open(output, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["card_number", "expire", "phone", "status", "balance"])
            for card in queryset:
                writer.writerow(
                    [
                        format_card(card.card_number),
                        card.expire,
                        format_phone(card.phone),
                        card.status,
                        f"{card.balance:.2f}",
                    ]
                )

        self.stdout.write(self.style.SUCCESS(f"Exported {queryset.count()} cards to {output}"))
