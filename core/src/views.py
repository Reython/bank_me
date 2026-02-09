import json
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from jsonrpcserver import Error, method, dispatch

from .models import Card, Error as ErrorMessage, Transfer
from .utils import (
    calculate_exchange,
    format_card,
    format_phone,
    generate_otp,
    get_transfer_by_ext_id,
    normalize_expire,
    send_telegram_message,
    validate_card,
)

logger = logging.getLogger(__name__)
OTP_EXPIRY_MINUTES = 5


def _get_error_message(code, lang="en"):
    error = ErrorMessage.objects.filter(code=code).first()
    if not error:
        return "Unknown error occurred"
    return getattr(error, lang, error.en)


def _error(code, lang="en"):
    return Error(code=code, message=_get_error_message(code, lang))


@method
def transfer_create(
    ext_id,
    sender_card_number,
    sender_card_expiry,
    receiver_card_number,
    sending_amount,
    currency,
    sender_phone="",
    receiver_phone="",
    lang="en",
):
    try:
        if not ext_id:
            return _error(32700, lang)
        if Transfer.objects.filter(ext_id=ext_id).exists():
            return _error(32701, lang)

        sender_card_number = format_card(sender_card_number, digits_only=True)
        receiver_card_number = format_card(receiver_card_number, digits_only=True)
        sender_card_expiry = normalize_expire(sender_card_expiry)

        if not validate_card(sender_card_number) or not validate_card(receiver_card_number):
            return _error(32706, lang)

        sender_card = Card.objects.filter(card_number=sender_card_number).first()
        receiver_card = Card.objects.filter(card_number=receiver_card_number).first()

        if not sender_card or sender_card.expire != sender_card_expiry:
            return _error(32704, lang)
        if sender_card.status != Card.STATUS_ACTIVE:
            return _error(32705, lang)
        sending_amount = Decimal(sending_amount)
        if sender_card.balance < sending_amount:
            return _error(32702, lang)
        if not (sender_card.phone or sender_phone):
            return _error(32703, lang)
        if not receiver_card:
            return _error(32706, lang)
        if int(currency) not in {643, 840}:
            return _error(32707, lang)
        if sending_amount <= 0:
            return _error(32709, lang)
        if sending_amount > 1_200_000_000:
            return _error(32708, lang)

        receiving_amount = calculate_exchange(sending_amount, currency)
        if receiving_amount is None:
            return _error(32707, lang)

        otp = generate_otp()
        transfer = Transfer.objects.create(
            ext_id=ext_id,
            sender_card_number=sender_card_number,
            receiver_card_number=receiver_card_number,
            sender_card_expiry=sender_card_expiry,
            sender_phone=format_phone(sender_phone or sender_card.phone, digits_only=True),
            receiver_phone=format_phone(receiver_phone or receiver_card.phone, digits_only=True),
            sending_amount=sending_amount,
            currency=currency,
            receiving_amount=receiving_amount,
            otp=otp,
        )
        message = f"Your OTP is {otp} for transfer {transfer.ext_id}."
        send_telegram_message(transfer.sender_phone, message)
        return {"ext_id": transfer.ext_id, "state": transfer.state, "otp_sent": True}
    except Exception:
        logger.exception("transfer.create failed")
        return _error(32706, lang)


@method
def transfer_confirm(ext_id, otp, lang="en"):
    try:
        transfer = get_transfer_by_ext_id(ext_id)
        if not transfer:
            return _error(32706, lang)
        if transfer.state != Transfer.STATE_CREATED:
            return {"ext_id": transfer.ext_id, "state": transfer.state}
        if transfer.try_count >= 3:
            return _error(32711, lang)
        expiry_time = transfer.created_at + timedelta(minutes=OTP_EXPIRY_MINUTES)
        if timezone.now() > expiry_time:
            return _error(32710, lang)
        if transfer.otp != str(otp):
            transfer.try_count += 1
            transfer.save(update_fields=["try_count", "updated_at"])
            return Error(
                code=32712,
                message=f"OTP is wrong, left try count is {max(0, 3 - transfer.try_count)}",
            )
        transfer.state = Transfer.STATE_CONFIRMED
        transfer.confirmed_at = timezone.now()
        transfer.save(update_fields=["state", "confirmed_at", "updated_at"])
        return {"ext_id": transfer.ext_id, "state": transfer.state}
    except Exception:
        logger.exception("transfer.confirm failed")
        return _error(32706, lang)


@method
def transfer_cancel(ext_id, lang="en"):
    try:
        transfer = get_transfer_by_ext_id(ext_id)
        if not transfer:
            return _error(32706, lang)
        if transfer.state == Transfer.STATE_CREATED:
            transfer.state = Transfer.STATE_CANCELLED
            transfer.cancelled_at = timezone.now()
            transfer.save(update_fields=["state", "cancelled_at", "updated_at"])
        return {"ext_id": transfer.ext_id, "state": transfer.state}
    except Exception:
        logger.exception("transfer.cancel failed")
        return _error(32706, lang)


@method
def transfer_state(ext_id, lang="en"):
    try:
        transfer = get_transfer_by_ext_id(ext_id)
        if not transfer:
            return _error(32706, lang)
        return {"ext_id": transfer.ext_id, "state": transfer.state}
    except Exception:
        logger.exception("transfer.state failed")
        return _error(32706, lang)


@method
def transfer_history(card_number=None, start_date=None, end_date=None, status=None, lang="en"):
    try:
        queryset = Transfer.objects.all()
        if card_number:
            normalized = format_card(card_number, digits_only=True)
            queryset = queryset.filter(Q(sender_card_number=normalized) | Q(receiver_card_number=normalized))
        if status:
            queryset = queryset.filter(state=status)
        if start_date:
            start = date.fromisoformat(start_date)
            queryset = queryset.filter(created_at__date__gte=start)
        if end_date:
            end = date.fromisoformat(end_date)
            queryset = queryset.filter(created_at__date__lte=end)

        results = [
            {
                "ext_id": transfer.ext_id,
                "sending_amount": float(transfer.sending_amount),
                "state": transfer.state,
                "created_at": transfer.created_at.isoformat(),
            }
            for transfer in queryset
        ]
        return results
    except Exception:
        logger.exception("transfer.history failed")
        return _error(32706, lang)


@csrf_exempt
def jsonrpc_endpoint(request):
    if request.method != "POST":
        response = {
            "jsonrpc": "2.0",
            "error": {"code": 32713, "message": _get_error_message(32713)},
            "id": None,
        }
        return HttpResponse(json.dumps(response), content_type="application/json", status=405)
    response = dispatch(request.body.decode())
    return HttpResponse(response, content_type="application/json")
