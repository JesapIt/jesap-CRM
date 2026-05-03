#!/usr/bin/env python
"""
Diagnostics: test email backend directly without Django.
Run: python manage.py shell < test_email_direct.py
"""
import os
import sys
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives

print("[TEST] Email Backend Configuration")
print(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
print(f"EMAIL_HOST: {settings.EMAIL_HOST}")
print(f"EMAIL_PORT: {settings.EMAIL_PORT}")
print(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
print(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER!r}")
print(f"EMAIL_HOST_PASSWORD: {'<SET>' if settings.EMAIL_HOST_PASSWORD else '<EMPTY>'}")
print(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")

print("\n[TEST] Attempting to send test email...")
try:
    msg = EmailMultiAlternatives(
        subject="Test Email from Django",
        body="This is a test email from the CRM.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=["test@example.com"],
    )
    msg.send(fail_silently=False)
    print("✅ Email sent successfully!")
except Exception as e:
    print(f"❌ Error sending email: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
