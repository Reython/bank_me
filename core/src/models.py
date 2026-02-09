from django.db import models

from .utils import format_card, format_phone, normalize_expire


class Card(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
        (STATUS_EXPIRED, "Expired"),
    ]

    card_number = models.CharField(max_length=16, db_index=True)
    expire = models.CharField(max_length=7, db_index=True)
    phone = models.CharField(max_length=15, blank=True, db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    balance = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        ordering = ["card_number"]

    def __str__(self):
        return f"{format_card(self.card_number)} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        self.card_number = format_card(self.card_number, digits_only=True)
        self.phone = format_phone(self.phone, digits_only=True)
        self.expire = normalize_expire(self.expire)
        super().save(*args, **kwargs)

    @property
    def card_number_readable(self):
        return format_card(self.card_number)

    @property
    def phone_readable(self):
        return format_phone(self.phone)


class Transfer(models.Model):
    STATE_CREATED = "created"
    STATE_CONFIRMED = "confirmed"
    STATE_CANCELLED = "cancelled"

    STATE_CHOICES = [
        (STATE_CREATED, "Created"),
        (STATE_CONFIRMED, "Confirmed"),
        (STATE_CANCELLED, "Cancelled"),
    ]

    ext_id = models.CharField(max_length=64, unique=True, db_index=True)
    sender_card_number = models.CharField(max_length=16)
    receiver_card_number = models.CharField(max_length=16)
    sender_card_expiry = models.CharField(max_length=7)
    sender_phone = models.CharField(max_length=15, blank=True)
    receiver_phone = models.CharField(max_length=15, blank=True)
    sending_amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.PositiveSmallIntegerField()
    receiving_amount = models.DecimalField(max_digits=15, decimal_places=2)
    state = models.CharField(max_length=10, choices=STATE_CHOICES, default=STATE_CREATED)
    try_count = models.PositiveSmallIntegerField(default=0)
    otp = models.CharField(max_length=6, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ext_id} ({self.state})"


class Error(models.Model):
    code = models.PositiveIntegerField(unique=True)
    en = models.CharField(max_length=255)
    ru = models.CharField(max_length=255)
    uz = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.code}: {self.en}"
