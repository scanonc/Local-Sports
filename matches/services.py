import logging

from django.contrib import messages

from users.models import Notification

from .models import ParticipantStatus

logger = logging.getLogger(__name__)


def notify_attendance_confirmation(match, player):
    """Notify the organizer that a participant confirmed attendance."""
    Notification.objects.create(
        user=match.organizer,
        match=match,
        message=(
            f'{player} confirmed attendance for the match "{match.title}".'
        ),
    )


def notify_match_cancellation(request, match):
    """FR9 - Internal notification service for match cancellation.

    Stores a local notification for each confirmed participant so they can see the
    cancellation in their app inbox without email or SMS.
    """
    confirmed_participants = match.participants.filter(
        status=ParticipantStatus.CONFIRMED
    ).select_related('player')

    recipients = [p.player for p in confirmed_participants]
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

    if recipients:
        Notification.objects.bulk_create([
            Notification(
                user=player,
                match=match,
                message=(
                    f'The match "{match.title}" scheduled for {match.date_time:%Y-%m-%d %H:%M} '
                    f'has been cancelled by the organizer.'
                ),
            )
            for player in recipients
        ])
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

