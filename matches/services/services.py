"""Compatibility facade for match services.

New code should import from the focused service modules directly.
"""

from .invitation_services import (
    build_match_invite_url,
    generate_match_invite_token,
    process_link_invitation,
)
from .notification_services import (
    notify_attendance_confirmation,
    notify_match_cancellation,
    notify_match_update,
)

__all__ = [
    'build_match_invite_url',
    'generate_match_invite_token',
    'notify_attendance_confirmation',
    'notify_match_cancellation',
    'notify_match_update',
    'process_link_invitation',
]
