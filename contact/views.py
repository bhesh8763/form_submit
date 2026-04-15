import json
import logging
import urllib.request
from datetime import datetime, timezone

from django.conf import settings
from django.core.mail import EmailMessage, send_mail
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils.timezone import now
from django.views.decorators.http import require_POST

from .models import ContactSubmission

logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_client_ip(request):
    """Extract real client IP, respecting reverse proxies."""
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def get_geo_location(ip):
    """
    Resolve approximate location from IP using the free ip-api.com service.
    Returns a string like "Kathmandu, Bagmati Province, NP" or empty string.
    Falls back gracefully if offline or rate-limited.
    """
    if not ip or ip in ('127.0.0.1', '::1', 'localhost'):
        return 'Localhost / Development'
    try:
        url = f'http://ip-api.com/json/{ip}?fields=status,city,regionName,country,countryCode'
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read())
        if data.get('status') == 'success':
            parts = [data.get('city', ''), data.get('regionName', ''), data.get('countryCode', '')]
            return ', '.join(p for p in parts if p)
    except Exception as e:
        logger.warning(f"GeoIP lookup failed: {e}")
    return 'Unknown'


def send_notification_email(submission, request):
    """
    Send the admin notification email with all metadata.
    Supports CC to multiple recipients.
    """
    primary = getattr(settings, 'FORMSUBMIT_PRIMARY_EMAIL', 'admin@example.com')
    cc_list = getattr(settings, 'FORMSUBMIT_CC_EMAILS', [])

    subject = f"[FormSubmit] New message from {submission.name}"
    body = f"""
New contact form submission received.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SUBMISSION DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Name        : {submission.name}
Email       : {submission.email}
Submitted   : {submission.submitted_at.strftime('%Y-%m-%d %H:%M:%S UTC')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TECHNICAL INFO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IP Address  : {submission.ip_address or 'N/A'}
Location    : {submission.location or 'N/A'}
Device      : {submission.device_info or 'N/A'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  MESSAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{submission.message}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Reply directly to this email to respond to {submission.name}.
"""

    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[primary],
        cc=cc_list,
        reply_to=[submission.email],
    )
    email.send(fail_silently=True)


def send_auto_reply(submission):
    """Send an automated acknowledgement to the sender."""
    subject = getattr(settings, 'FORMSUBMIT_AUTO_REPLY_SUBJECT', 'Thanks for reaching out!')
    template = getattr(
        settings,
        'FORMSUBMIT_AUTO_REPLY_MESSAGE',
        "Hi {name},\n\nThank you for your message. We'll be in touch soon.\n\nBest regards,\nThe Team"
    )
    body = template.format(name=submission.name, email=submission.email)

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[submission.email],
            fail_silently=True,
        )
        submission.auto_reply_sent = True
        submission.save(update_fields=['auto_reply_sent'])
    except Exception as e:
        logger.error(f"Auto-reply failed: {e}")


def trigger_webhook(submission):
    """
    POST submission data to a configured webhook URL (e.g. Slack, Zapier, n8n).
    """
    webhook_url = getattr(settings, 'FORMSUBMIT_WEBHOOK_URL', '')
    if not webhook_url:
        return

    payload = json.dumps({
        'id': submission.pk,
        'name': submission.name,
        'email': submission.email,
        'message': submission.message,
        'ip_address': submission.ip_address,
        'location': submission.location,
        'device': submission.device_info,
        'submitted_at': submission.submitted_at.isoformat(),
    }).encode('utf-8')

    try:
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            submission.webhook_triggered = (resp.status == 200)
            submission.save(update_fields=['webhook_triggered'])
    except Exception as e:
        logger.error(f"Webhook failed: {e}")


# ─── Views ────────────────────────────────────────────────────────────────────

def contact_form(request):
    """Render the contact form page."""
    return render(request, 'contact/form.html')


@require_POST
def submit_form(request):
    """
    Handle form submission:
    1. Honeypot check
    2. Collect IP / device / location
    3. Save to DB
    4. Send admin notification (with CC)
    5. Send auto-reply
    6. Trigger webhook
    7. Redirect to thank-you page
    """
    # ── 1. Honeypot ───────────────────────────────────────────────────────────
    honeypot = request.POST.get('_honey', '')
    if honeypot:
        # Silently redirect; bots think submission succeeded
        return redirect('thank_you')

    # ── 2. Validate required fields ───────────────────────────────────────────
    name = request.POST.get('name', '').strip()
    email = request.POST.get('email', '').strip()
    message = request.POST.get('message', '').strip()

    if not all([name, email, message]):
        return render(request, 'contact/form.html', {
            'error': 'All fields are required.',
            'name': name,
            'email': email,
            'message': message,
        })

    # ── 3. Collect metadata ───────────────────────────────────────────────────
    ip = get_client_ip(request)
    location = get_geo_location(ip)
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

    # ── 4. Save to database ───────────────────────────────────────────────────
    submission = ContactSubmission.objects.create(
        name=name,
        email=email,
        message=message,
        ip_address=ip or None,
        device_info=user_agent,
        location=location,
    )

    # ── 5. Admin notification email (with CC) ─────────────────────────────────
    send_notification_email(submission, request)

    # ── 6. Auto-reply ─────────────────────────────────────────────────────────
    send_auto_reply(submission)

    # ── 7. Webhook ────────────────────────────────────────────────────────────
    trigger_webhook(submission)

    return redirect('thank_you')


def thank_you(request):
    """Thank-you / confirmation page."""
    return render(request, 'contact/thank_you.html')
