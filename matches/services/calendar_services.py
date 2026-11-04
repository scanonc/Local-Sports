from datetime import timedelta, timezone as datetime_timezone
from urllib.parse import urlencode

from ..models import MatchStatus, ParticipantStatus


def can_rate_match(match, user):
    """Return whether a user can rate a completed match."""
    return (
        user.is_authenticated
        and match.has_started
        and match.status != MatchStatus.CANCELLED
        and match.participants.filter(
            player=user, status=ParticipantStatus.CONFIRMED,
        ).exists()
    )


def google_calendar_url(match):
    """Build a one-hour Google Calendar event URL for a match."""
    start = match.date_time.astimezone(datetime_timezone.utc)
    end = start + timedelta(hours=1)
    return 'https://calendar.google.com/calendar/render?' + urlencode({
        'action': 'TEMPLATE',
        'text': match.title,
        'dates': f'{start:%Y%m%dT%H%M%SZ}/{end:%Y%m%dT%H%M%SZ}',
        'location': match.location,
    })
