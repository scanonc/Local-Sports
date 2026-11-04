import logging

from django.conf import settings
from django.contrib import messages
import resend

from users.models import Notification

from ..models import ParticipantStatus


logger = logging.getLogger('matches.services')


def _send_resend_email(to_email, subject, html_content, text_content=None):
    """Send an email using the Resend API."""
    if getattr(settings, 'RESEND_API_KEY', None):
        resend.api_key = settings.RESEND_API_KEY

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'Local Sports <onboarding@resend.dev>'
    params = {
        'from': from_email,
        'to': [to_email],
        'subject': subject,
        'html': html_content,
    }
    if text_content:
        params['text'] = text_content

    try:
        return resend.Emails.send(params)
    except Exception as e:
        logger.exception("Failed to send email via Resend to %s: %s", to_email, e)
        return None


def notify_attendance_confirmation(match, player):
    """Notify the organizer that a participant confirmed attendance."""
    Notification.objects.create(
        user=match.organizer,
        match=match,
        message=f'{player} confirmed attendance for the match "{match.title}".',
    )


def notify_match_update(match, changed_fields=None):
    """Notify confirmed and waiting participants about a match update."""
    affected_participants = match.participants.filter(
        status__in=[ParticipantStatus.CONFIRMED, ParticipantStatus.WAITING]
    ).select_related('player')
    recipients = [participant.player for participant in affected_participants]
    recipient_usernames = [player.username for player in recipients]

    logger.info(
        "Match '%s' (ID: %s) was updated. Notifying %d affected participant(s): %s.",
        match.title,
        match.pk,
        len(recipients),
        ', '.join(recipient_usernames) if recipient_usernames else 'None',
    )

    if not recipients:
        return

    Notification.objects.bulk_create([
        Notification(
            user=player,
            match=match,
            message=f"The match '{match.title}' has been updated.",
            is_read=False,
        )
        for player in recipients
    ])

    subject = f"Match Updated: {match.title}"
    for player in recipients:
        if player.email:
            greeting = player.first_name or player.username
            _send_resend_email(
                to_email=player.email,
                subject=subject,
                html_content=(
                    f"<p>Hello {greeting},</p>"
                    f"<p>The match '<strong>{match.title}</strong>' has been updated.</p>"
                    f"<p><strong>Date & Time:</strong> {match.date_time:%Y-%m-%d %H:%M}</p>"
                    f"<p><strong>Location:</strong> {match.location}</p>"
                    f"<p>Check the latest details on Local Sports.</p>"
                ),
                text_content=(
                    f"Hello {greeting},\n\n"
                    f"The match '{match.title}' has been updated.\n"
                    f"Date & Time: {match.date_time:%Y-%m-%d %H:%M}\n"
                    f"Location: {match.location}\n\n"
                    f"Check the latest details on Local Sports."
                ),
            )


def notify_match_cancellation(request, match=None):
    """Notify confirmed and waiting participants about a cancellation."""
    if match is None and hasattr(request, 'participants'):
        match = request
        request = None

    affected_participants = match.participants.filter(
        status__in=[ParticipantStatus.CONFIRMED, ParticipantStatus.WAITING]
    ).select_related('player')
    recipients = [participant.player for participant in affected_participants]
    recipient_usernames = [player.username for player in recipients]

    logger.info(
        "Match '%s' (ID: %s) scheduled for %s was cancelled by organizer '%s'. "
        "Notifying %d confirmed participant(s): %s.",
        match.title,
        match.pk,
        match.date_time,
        match.organizer.username,
        len(recipients),
        ', '.join(recipient_usernames) if recipient_usernames else 'None',
    )

    if not recipients:
        if request:
            messages.info(request, 'No confirmed participants to notify.')
        return

    cancellation_message = (
        f'The match "{match.title}" scheduled for {match.date_time:%Y-%m-%d %H:%M} '
        f'has been cancelled by the organizer.'
    )
    Notification.objects.bulk_create([
        Notification(
            user=player,
            match=match,
            message=cancellation_message,
            is_read=False,
        )
        for player in recipients
    ])

    subject = f"Match Cancelled: {match.title}"
    for player in recipients:
        if player.email:
            greeting = player.first_name or player.username
            _send_resend_email(
                to_email=player.email,
                subject=subject,
                html_content=f"<p>Hello {greeting},</p><p>{cancellation_message}</p>",
                text_content=f"Hello {greeting},\n\n{cancellation_message}",
            )

    if request:
        messages.info(
            request,
            f"Notification sent to {len(recipients)} confirmed participant(s): "
            f"{', '.join(recipient_usernames)}.",
        )
