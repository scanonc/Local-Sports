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


class MatchModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='organizer',
            email='organizer@example.com',
            password='testpass123',
        )

    def test_match_requires_future_date_and_valid_capacity(self):
        match = Match(
            organizer=self.user,
            title='Sunday Match',
            date_time=timezone.now() - timedelta(days=1),
            location='Local field',
            skill_level='beginner',
            max_players=1,
            visibility='public',
        )

        with self.assertRaises(ValidationError):
            match.full_clean()

    def test_match_can_be_created_with_valid_data(self):
        match = Match.objects.create(
            organizer=self.user,
            title='Sunday Match',
            date_time=timezone.now() + timedelta(days=1),
            location='Local field',
            skill_level='beginner',
            max_players=10,
            visibility='public',
        )

        self.assertEqual(match.organizer, self.user)

    def test_closed_match_status_and_team_assignment_are_persisted(self):
        match = Match.objects.create(
            organizer=self.user,
            title='Sunday Match',
            date_time=timezone.now() + timedelta(days=1),
            location='Local field',
            skill_level='beginner',
            max_players=6,
            visibility='public',
            status=MatchStatus.CLOSED,
        )
        participant = MatchParticipant.objects.create(
            match=match,
            player=User.objects.create_user(
                username='player',
                email='player@example.com',
                password='testpass123',
            ),
        )
        assignment = MatchTeamAssignment.objects.create(
            match=match,
            participant=participant,
            team=MatchTeam.A,
        )

        match.refresh_from_db()
        self.assertTrue(match.is_closed)
        self.assertTrue(match.has_generated_teams)
        self.assertEqual(match.team_assignments.get(), assignment)

    def test_match_rejects_invalid_player_limits(self):
        invalid_limits = [5, 7, 42, 4, 0, -2]

        for max_players in invalid_limits:
            with self.subTest(max_players=max_players):
                match = Match(
                    organizer=self.user,
                    title='Sunday Match',
                    date_time=timezone.now() + timedelta(days=1),
                    location='Local field',
                    skill_level='beginner',
                    max_players=max_players,
                    visibility='public',
                )

                with self.assertRaises(ValidationError):
                    match.full_clean()
