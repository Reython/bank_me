from django import forms
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path

from .models import Card, Error, Transfer
from .utils import format_card, format_phone, normalize_expire, parse_balance, read_simple_xlsx


class BalanceRangeFilter(admin.SimpleListFilter):
    title = "balance"
    parameter_name = "balance_range"

    def lookups(self, request, model_admin):
        return [
            ("zero", "0"),
            ("low", "0 - 10,000"),
            ("mid", "10,000 - 1,000,000"),
            ("high", "1,000,000+"),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value == "zero":
            return queryset.filter(balance=0)
        if value == "low":
            return queryset.filter(balance__gt=0, balance__lte=10_000)
        if value == "mid":
            return queryset.filter(balance__gt=10_000, balance__lte=1_000_000)
        if value == "high":
            return queryset.filter(balance__gt=1_000_000)
        return queryset


class CardImportForm(forms.Form):
    excel_file = forms.FileField(label="Excel file (.xlsx)")


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ("card_number_display", "expire", "phone_display", "status", "balance")
    list_filter = ("status", "expire", "phone", BalanceRangeFilter)
    search_fields = ("card_number", "phone")

    def card_number_display(self, obj):
        return format_card(obj.card_number)

    card_number_display.short_description = "Card number"

    def phone_display(self, obj):
        return format_phone(obj.phone)

    phone_display.short_description = "Phone"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("import-excel/", self.admin_site.admin_view(self.import_excel), name="cards-import"),
        ]
        return custom_urls + urls

    def import_excel(self, request):
        if request.method == "POST":
            form = CardImportForm(request.POST, request.FILES)
            if form.is_valid():
                excel_file = form.cleaned_data["excel_file"]
                created, errors = self._import_cards_from_excel(excel_file)
                if created:
                    messages.success(request, f"Imported {created} cards.")
                for error in errors:
                    messages.error(request, error)
                return HttpResponseRedirect("../")
        else:
            form = CardImportForm()

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "form": form,
            "title": "Import cards from Excel",
        }
        return TemplateResponse(request, "admin/cards_import.html", context)

    def _import_cards_from_excel(self, excel_file):
        rows = read_simple_xlsx(excel_file)
        if not rows:
            return 0, ["Excel file is empty."]

        header = [cell.strip().lower() for cell in rows[0]]
        expected = ["card_number", "expire", "phone", "status", "balance"]
        if header[: len(expected)] != expected:
            return 0, ["Invalid header. Expected: card_number, expire, phone, status, balance"]

        created = 0
        errors = []
        for index, row in enumerate(rows[1:], start=2):
            if not any(row):
                continue
            data = dict(zip(expected, row))
            card_number = format_card(data.get("card_number"), digits_only=True)
            expire = normalize_expire(data.get("expire"))
            phone = format_phone(data.get("phone"), digits_only=True)
            status = str(data.get("status", "")).strip().lower()
            balance = parse_balance(data.get("balance"))

            row_errors = []
            if len(card_number) != 16:
                row_errors.append("card_number must be 16 digits")
            if not expire or len(expire) != 7:
                row_errors.append("expire must be in YYYY-MM")
            if phone and len(phone) not in {9, 12}:
                row_errors.append("phone must be 9 or 12 digits")
            if status not in dict(Card.STATUS_CHOICES):
                row_errors.append("status must be active, inactive, or expired")
            if balance is None:
                row_errors.append("balance must be numeric")

            if row_errors:
                errors.append(f"Row {index}: {', '.join(row_errors)}")
                continue

            Card.objects.update_or_create(
                card_number=card_number,
                defaults={
                    "expire": expire,
                    "phone": phone,
                    "status": status,
                    "balance": balance,
                },
            )
            created += 1
        return created, errors


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = (
        "ext_id",
        "sender_card_number",
        "receiver_card_number",
        "state",
        "sending_amount",
        "currency",
        "created_at",
    )
    list_filter = ("state", "currency", "created_at")
    search_fields = ("ext_id", "sender_card_number", "receiver_card_number")


@admin.register(Error)
class ErrorAdmin(admin.ModelAdmin):
    list_display = ("code", "en", "ru", "uz")
    search_fields = ("code", "en", "ru", "uz")
