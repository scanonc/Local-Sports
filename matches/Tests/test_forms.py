from datetime import timedelta
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse
from django.test import TestCase
from django.utils import timezone

from users.models import Notification

from ..forms import MatchForm
from ..models import (
    Invitation,
    InvitationStatus,
    JoinRequest,
    JoinRequestStatus,
    Match,
    MatchParticipant,
    MatchStatus,
    MatchTeam,
    MatchTeamAssignment,
    MatchVisibility,
    ParticipantStatus,
)


User = get_user_model()


class MatchFormTests(TestCase):
    def test_valid_form_creates_clean_match_data(self):
        form = MatchForm(
            data={
                'title': 'Friday Match',
                'date_time': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
                'location': 'Central park',
                'skill_level': 'intermediate',
                'max_players': 12,
                'visibility': 'approval_required',
            }
        )

        self.assertTrue(form.is_valid())

    def test_form_accepts_even_limits_from_6_to_40(self):
        for max_players in [6, 8, 40]:
            with self.subTest(max_players=max_players):
                form = MatchForm(
                    data={
                        'title': 'Friday Match',
                        'date_time': (
                            timezone.now() + timedelta(days=2)
                        ).strftime('%Y-%m-%dT%H:%M'),
                        'location': 'Central park',
                        'skill_level': 'intermediate',
                        'max_players': max_players,
                        'visibility': 'approval_required',
                    }
                )

                self.assertTrue(form.is_valid(), form.errors)

    def test_form_rejects_invalid_player_limits(self):
        for max_players in [5, 7, 42, 4, 0, -2, 'not-a-number']:
            with self.subTest(max_players=max_players):
                form = MatchForm(
                    data={
                        'title': 'Friday Match',
                        'date_time': (
                            timezone.now() + timedelta(days=2)
                        ).strftime('%Y-%m-%dT%H:%M'),
                        'location': 'Central park',
                        'skill_level': 'intermediate',
                        'max_players': max_players,
                        'visibility': 'approval_required',
                    }
                )

                self.assertFalse(form.is_valid())
                self.assertIn('max_players', form.errors)

    def test_edit_form_rejects_invalid_player_limits(self):
        organizer = User.objects.create_user(
            username='form_organizer',
            email='form-organizer@example.com',
            password='testpass123',
        )
        match = Match.objects.create(
            organizer=organizer,
            title='Friday Match',
            date_time=timezone.now() + timedelta(days=2),
            location='Central park',
            skill_level='intermediate',
            max_players=6,
            visibility='approval_required',
        )
        form = MatchForm(
            data={
                'title': match.title,
                'date_time': match.date_time.strftime('%Y-%m-%dT%H:%M'),
                'location': match.location,
                'skill_level': match.skill_level,
                'max_players': 7,
                'visibility': match.visibility,
            },
            instance=match,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('max_players', form.errors)
