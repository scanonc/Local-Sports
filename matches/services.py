import logging

from django.contrib import messages

from .models import ParticipantStatus

logger = logging.getLogger(__name__)


def notify_match_cancellation(request, match):
    """FR9 - Stub/Logger notification service for match cancellation.

    Retrieves confirmed participants for the cancelled match,
    logs the notification details, and adds user feedback via django.contrib.messages.
    """
    confirmed_participants = match.participants.filter(
        status=ParticipantStatus.CONFIRMED
    ).select_related('player')

    recipients = [p.player for p in confirmed_participants]
    recipient_usernames = [player.username for player in recipients]
    recipient_emails = [player.email for player in recipients if player.email]

    logger.info(
        "Match '%s' (ID: %s) scheduled for %s was cancelled by organizer '%s'. "
        "Notifying %d confirmed participant(s): %s (Emails: %s).",
        match.title,
        match.pk,
        match.date_time,
        match.organizer.username,
        len(recipients),
        ', '.join(recipient_usernames) if recipient_usernames else 'None',
        ', '.join(recipient_emails) if recipient_emails else 'None',
    )

    if recipients:
        messages.info(
            request,
            f"Notification sent to {len(recipients)} confirmed participant(s): "
            f"{', '.join(recipient_usernames)}.",
        )
    else:
        messages.info(
            request,
            'No confirmed participants to notify.',
        )

