import csv
import logging
import random
import re
import zipfile
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

logger = logging.getLogger(__name__)


CARD_DIGITS_RE = re.compile(r"\D+")
PHONE_DIGITS_RE = re.compile(r"\D+")


def format_card(raw_card, digits_only=False):
    if raw_card is None:
        return ""
    digits = CARD_DIGITS_RE.sub("", str(raw_card))
    if digits_only:
        return digits
    return " ".join(digits[i : i + 4] for i in range(0, len(digits), 4))


def format_phone(raw_phone, digits_only=False):
    if not raw_phone:
        return ""
    digits = PHONE_DIGITS_RE.sub("", str(raw_phone))
    if digits_only:
        return digits
    if len(digits) == 9:
        return f"{digits[:2]} {digits[2:5]} {digits[5:7]} {digits[7:]}"
    if len(digits) == 12:
        return f"+{digits[:3]} {digits[3:5]} {digits[5:8]} {digits[8:10]} {digits[10:]}"
    return digits


def card_mask(card_number):
    digits = format_card(card_number, digits_only=True)
    if len(digits) <= 4:
        return digits
    masked = "*" * (len(digits) - 4) + digits[-4:]
    return " ".join(masked[i : i + 4] for i in range(0, len(masked), 4))


def phone_mask(phone):
    digits = format_phone(phone, digits_only=True)
    if len(digits) <= 2:
        return digits
    return "*" * (len(digits) - 2) + digits[-2:]


def normalize_expire(raw_expire):
    if not raw_expire:
        return ""
    value = str(raw_expire).strip()
    match = re.match(r"^(?P<year>\\d{4})[-./](?P<month>\\d{1,2})$", value)
    if match:
        month = int(match.group("month"))
        year = match.group("year")
        return f"{year}-{month:02d}"
    match = re.match(r"^(?P<month>\\d{1,2})[-./](?P<year>\\d{2,4})$", value)
    if match:
        month = int(match.group("month"))
        year = match.group("year")
        if len(year) == 2:
            year = f"20{year}"
        return f"{year}-{month:02d}"
    return value


def parse_balance(raw_balance):
    if raw_balance is None or raw_balance == "":
        return None
    value = str(raw_balance).replace(",", "").strip()
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def prepare_message(card_number, balance, lang="UZ"):
    if lang.upper() != "UZ":
        lang = "UZ"
    balance_value = f"{Decimal(balance):,.2f}"
    return (
        f"Sizning kartangiz {card_mask(card_number)} aktiv va foydalanishga "
        f"{balance_value} UZS mavjud!"
    )


def send_message(message, chat_id=12345):
    logger.info("Sending message to %s: %s", chat_id, message)
    return True


def generate_otp(length=6):
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def send_telegram_message(phone, message, chat_id=123456):
    logger.info("Sending telegram to %s (%s): %s", phone, chat_id, message)
    return True


def validate_card(card_number):
    digits = format_card(card_number, digits_only=True)
    if not digits:
        return False
    total = 0
    reverse_digits = list(map(int, digits[::-1]))
    for idx, digit in enumerate(reverse_digits):
        if idx % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def calculate_exchange(amount, currency):
    rates = {
        860: Decimal("1.0"),
        643: Decimal("140.0"),
        840: Decimal("12600.0"),
    }
    rate = rates.get(int(currency))
    if rate is None:
        return None
    return Decimal(amount) * rate


def get_transfer_by_ext_id(ext_id):
    from .models import Transfer

    return Transfer.objects.filter(ext_id=ext_id).first()


def read_simple_xlsx(file_obj):
    with zipfile.ZipFile(file_obj) as workbook:
        sheet_data = workbook.read("xl/worksheets/sheet1.xml")
    root = ElementTree.fromstring(sheet_data)
    namespace = {"sheet": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows = []
    for row in root.findall("sheet:sheetData/sheet:row", namespace):
        current = []
        for cell in row.findall("sheet:c", namespace):
            cell_type = cell.get("t")
            value = None
            if cell_type == "inlineStr":
                text_node = cell.find("sheet:is/sheet:t", namespace)
                if text_node is not None:
                    value = text_node.text
            else:
                value_node = cell.find("sheet:v", namespace)
                if value_node is not None:
                    value = value_node.text
            current.append(value or "")
        rows.append(current)
    return rows


def write_cards_csv(rows, file_obj):
    writer = csv.writer(file_obj)
    for row in rows:
        writer.writerow(row)
