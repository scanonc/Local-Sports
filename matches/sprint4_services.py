from datetime import timedelta, timezone as datetime_timezone
from urllib.parse import urlencode

from .models import MatchStatus, ParticipantStatus


def can_rate_match(match, user):
    # Match completion follows FR20: its scheduled start time has passed.
    return (
        user.is_authenticated
        and match.has_started
        and match.status != MatchStatus.CANCELLED
        and match.participants.filter(
            player=user, status=ParticipantStatus.CONFIRMED,
        ).exists()
    )


def google_calendar_url(match):
    start = match.date_time.astimezone(datetime_timezone.utc)
    # Matches have no duration field; propose a one-hour event, editable in Google.
    end = start + timedelta(hours=1)
    return 'https://calendar.google.com/calendar/render?' + urlencode({
        'action': 'TEMPLATE',
        'text': match.title,
        'dates': f'{start:%Y%m%dT%H%M%SZ}/{end:%Y%m%dT%H%M%SZ}',
        'location': match.location,
    })
