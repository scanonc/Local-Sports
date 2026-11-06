import uuid

from django.db import transaction
from django.urls import reverse
from django.utils.translation import gettext as _

from ..models import (
    Invitation,
    InvitationStatus,
    MatchParticipant,
    MatchStatus,
    MatchVisibility,
    ParticipantStatus,
)
from .player_statistics import player_meets_match_skill_level


def generate_match_invite_token(match):
    """Generate or ensure an active unique invite token for the match."""
    if not match.invite_token:
        match.invite_token = uuid.uuid4()
        match.invite_active = True
        match.save(update_fields=['invite_token', 'invite_active'])
    elif not match.invite_active:
        match.invite_active = True
        match.save(update_fields=['invite_active'])
    return match.invite_token


def build_match_invite_url(match, request=None):
    """Build the absolute shareable invitation link for the match."""
    token = generate_match_invite_token(match)
    path = reverse('matches:match_join_via_link', kwargs={'token': str(token)})
    return request.build_absolute_uri(path) if request else path


def process_link_invitation(match, user, action):
    """Process accept or decline for an invitation link."""
    with transaction.atomic():
        if action == 'decline':
            invitation = Invitation.objects.filter(match=match, player=user).first()
            if invitation:
                invitation.status = InvitationStatus.DECLINED
                invitation.save(update_fields=['status'])
            else:
                Invitation.objects.create(
                    match=match,
                    organizer=match.organizer,
                    player=user,
                    status=InvitationStatus.DECLINED,
                )
            return True, _('The invitation has been declined.'), None

        if action != 'accept':
            return False, _('This invitation action is not available.'), None
        if match.status == MatchStatus.CANCELLED:
            return False, _('This match has been cancelled.'), None
        if match.has_started:
            return False, _('This match has already started or finished.'), None
        if match.organizer_id == user.id:
            return False, _('You are the organizer of this match.'), None
        if not player_meets_match_skill_level(user, match):
            return False, _('Your skill level is not high enough for this match.'), None

        participant = MatchParticipant.objects.filter(
            match=match, player=user,
        ).first()
        if participant and participant.status in [
            ParticipantStatus.CONFIRMED,
            ParticipantStatus.WAITING,
        ]:
            return False, _('You are already participating in this match.'), participant

        confirmed_count = MatchParticipant.objects.filter(
            match=match, status=ParticipantStatus.CONFIRMED,
        ).count()
        if confirmed_count >= match.max_players:
            if match.visibility != MatchVisibility.PUBLIC:
                return False, _('This match is full and cannot accept the invitation.'), None
            participant_status = ParticipantStatus.WAITING
            message = _('The invitation was accepted. You were added to the waiting list.')
        else:
            participant_status = ParticipantStatus.CONFIRMED
            message = _('The invitation was accepted. You joined the match.')

        if participant:
            participant.status = participant_status
            participant.attendance_confirmed = False
            participant.save(update_fields=['status', 'attendance_confirmed', 'updated_at'])
        else:
            participant = MatchParticipant.objects.create(
                match=match, player=user, status=participant_status,
            )

        invitation = Invitation.objects.filter(match=match, player=user).first()
        if invitation:
            invitation.status = InvitationStatus.ACCEPTED
            invitation.save(update_fields=['status'])
        else:
            Invitation.objects.create(
                match=match,
                organizer=match.organizer,
                player=user,
                status=InvitationStatus.ACCEPTED,
            )
        return True, message, participant
