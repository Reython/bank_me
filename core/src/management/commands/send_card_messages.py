from django.core.management.base import BaseCommand

from src.models import Card
from src.utils import prepare_message, send_message


class Command(BaseCommand):
    help = "Send simulated messages to cards with optional filtering."

    def add_arguments(self, parser):
        parser.add_argument("--status", choices=[choice[0] for choice in Card.STATUS_CHOICES])
        parser.add_argument("--card-number")
        parser.add_argument("--phone")
        parser.add_argument("--chat-id", type=int, default=12345)

    def handle(self, *args, **options):
        queryset = Card.objects.all()
        status = options.get("status")
        card_number = options.get("card_number")
        phone = options.get("phone")
        chat_id = options["chat_id"]

        if status:
            queryset = queryset.filter(status=status)
        if card_number:
            queryset = queryset.filter(card_number__icontains=card_number.replace(" ", ""))
        if phone:
            queryset = queryset.filter(phone__icontains=phone.replace(" ", ""))

        count = 0
        for card in queryset:
            message = prepare_message(card.card_number, card.balance)
            send_message(message, chat_id=chat_id)
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Sent {count} messages."))
