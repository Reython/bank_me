from django.test import SimpleTestCase

from .utils import format_card, format_phone, generate_otp, validate_card


class UtilsTests(SimpleTestCase):
    def test_format_card(self):
        assert format_card("8600123412341234") == "8600 1234 1234 1234"

    def test_format_phone(self):
        assert format_phone("99 973 03 03") == "99 973 03 03"

    def test_generate_otp(self):
        otp = generate_otp()
        assert len(otp) == 6
        assert otp.isdigit()

    def test_validate_card(self):
        assert validate_card("4532015112830366") is True
        assert validate_card("4532015112830367") is False
