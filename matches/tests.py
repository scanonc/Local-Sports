from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse
from django.test import TestCase
from django.utils import timezone

from .forms import MatchForm
from .models import (
    JoinRequest,
    JoinRequestStatus,
    Match,
    MatchParticipant,
    MatchStatus,
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


class MatchViewTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username='organizer',
            email='organizer@example.com',
            password='testpass123',
        )
        self.other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='testpass123',
        )

    def test_create_view_requires_login(self):
        response = self.client.get(reverse('matches:match_create'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/users/login/', response.url)

    def test_logged_in_user_can_create_match_and_becomes_organizer(self):
        self.client.login(username='organizer', password='testpass123')

        response = self.client.post(
            reverse('matches:match_create'),
            data={
                'title': 'Friday Match',
                'date_time': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
                'location': 'Central park',
                'skill_level': 'intermediate',
                'max_players': 12,
                'visibility': 'approval_required',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Match.objects.count(), 1)
        match = Match.objects.first()
        self.assertEqual(match.organizer, self.organizer)

    def test_only_organizer_can_edit_match(self):
        match = Match.objects.create(
            organizer=self.organizer,
            title='Saturday Match',
            date_time=timezone.now() + timedelta(days=3),
            location='Local field',
            skill_level='beginner',
            max_players=10,
            visibility='public',
        )

        self.client.login(username='other', password='testpass123')
        response = self.client.get(reverse('matches:match_update', kwargs={'pk': match.pk}))

        self.assertEqual(response.status_code, 404)

    def test_match_list_shows_created_matches(self):
        Match.objects.create(
            organizer=self.organizer,
            title='Sunday Match',
            date_time=timezone.now() + timedelta(days=4),
            location='Community pitch',
            skill_level='advanced',
            max_players=14,
            visibility='public',
        )

        response = self.client.get(reverse('matches:match_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sunday Match')


class MatchJoinViewTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username='organizer',
            email='organizer@example.com',
            password='testpass123',
        )
        self.player = User.objects.create_user(
            username='player',
            email='player@example.com',
            password='testpass123',
        )
        self.public_match = Match.objects.create(
            organizer=self.organizer,
            title='Public Match',
            date_time=timezone.now() + timedelta(days=1),
            location='Local field',
            skill_level='beginner',
            max_players=2,
            visibility='public',
        )
        self.approval_match = Match.objects.create(
            organizer=self.organizer,
            title='Approval Match',
            date_time=timezone.now() + timedelta(days=1),
            location='Local field',
            skill_level='beginner',
            max_players=10,
            visibility='approval_required',
        )

    def test_join_requires_login(self):
        response = self.client.post(reverse('matches:match_join', kwargs={'pk': self.public_match.pk}))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/users/login/', response.url)

    def test_authenticated_player_can_join_public_match(self):
        self.client.login(username='player', password='testpass123')

        response = self.client.post(reverse('matches:match_join', kwargs={'pk': self.public_match.pk}))

        self.assertRedirects(response, reverse('matches:match_detail', kwargs={'pk': self.public_match.pk}))
        self.assertTrue(
            MatchParticipant.objects.filter(
                match=self.public_match, player=self.player, status=ParticipantStatus.CONFIRMED
            ).exists()
        )

    def test_cannot_join_approval_required_match(self):
        self.client.login(username='player', password='testpass123')

        self.client.post(reverse('matches:match_join', kwargs={'pk': self.approval_match.pk}))

        self.assertFalse(
            MatchParticipant.objects.filter(match=self.approval_match, player=self.player).exists()
        )

    def test_cannot_join_twice(self):
        self.client.login(username='player', password='testpass123')
        self.client.post(reverse('matches:match_join', kwargs={'pk': self.public_match.pk}))

        self.client.post(reverse('matches:match_join', kwargs={'pk': self.public_match.pk}))

        self.assertEqual(
            MatchParticipant.objects.filter(match=self.public_match, player=self.player).count(), 1
        )

    def test_organizer_cannot_join_own_match(self):
        self.client.login(username='organizer', password='testpass123')

        self.client.post(reverse('matches:match_join', kwargs={'pk': self.public_match.pk}))

        self.assertFalse(
            MatchParticipant.objects.filter(match=self.public_match, player=self.organizer).exists()
        )

    def test_joining_full_match_goes_to_waiting_list(self):
        other_player = User.objects.create_user(
            username='other_player', email='other_player@example.com', password='testpass123'
        )
        MatchParticipant.objects.create(match=self.public_match, player=self.player)
        MatchParticipant.objects.create(match=self.public_match, player=other_player)
        third_player = User.objects.create_user(
            username='third_player', email='third_player@example.com', password='testpass123'
        )

        self.client.login(username='third_player', password='testpass123')
        self.client.post(reverse('matches:match_join', kwargs={'pk': self.public_match.pk}))

        participant = MatchParticipant.objects.get(match=self.public_match, player=third_player)
        self.assertEqual(participant.status, ParticipantStatus.WAITING)

    def test_cannot_join_past_match(self):
        past_match = Match.objects.create(
            organizer=self.organizer,
            title='Past Match',
            date_time=timezone.now() + timedelta(days=1),
            location='Local field',
            skill_level='beginner',
            max_players=10,
            visibility='public',
        )
        Match.objects.filter(pk=past_match.pk).update(date_time=timezone.now() - timedelta(days=1))

        self.client.login(username='player', password='testpass123')
        self.client.post(reverse('matches:match_join', kwargs={'pk': past_match.pk}))

        self.assertFalse(
            MatchParticipant.objects.filter(match=past_match, player=self.player).exists()
        )


class MatchAttendanceViewTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username='organizer',
            email='organizer@example.com',
            password='testpass123',
        )
        self.player = User.objects.create_user(
            username='player',
            email='player@example.com',
            password='testpass123',
        )
        self.match = Match.objects.create(
            organizer=self.organizer,
            title='Attendance Match',
            date_time=timezone.now() + timedelta(days=1),
            location='Local field',
            skill_level='beginner',
            max_players=10,
            visibility='public',
        )
        MatchParticipant.objects.create(
            match=self.match,
            player=self.player,
            status=ParticipantStatus.CONFIRMED,
        )

    def test_confirmed_player_can_confirm_attendance(self):
        self.client.login(username='player', password='testpass123')

        response = self.client.post(
            reverse('matches:match_attendance', kwargs={'pk': self.match.pk})
        )

        self.assertRedirects(response, reverse('matches:match_detail', kwargs={'pk': self.match.pk}))
        self.assertTrue(
            MatchParticipant.objects.get(
                match=self.match,
                player=self.player,
            ).attendance_confirmed
        )

    def test_confirm_attendance_is_idempotently_rejected(self):
        participant = MatchParticipant.objects.get(match=self.match, player=self.player)
        participant.attendance_confirmed = True
        participant.save(update_fields=['attendance_confirmed'])
        self.client.login(username='player', password='testpass123')

        self.client.post(reverse('matches:match_attendance', kwargs={'pk': self.match.pk}))

        self.assertEqual(
            MatchParticipant.objects.filter(
                match=self.match,
                player=self.player,
                attendance_confirmed=True,
            ).count(),
            1,
        )

    def test_rejoining_after_leaving_requires_new_attendance_confirmation(self):
        participant = MatchParticipant.objects.get(match=self.match, player=self.player)
        participant.attendance_confirmed = True
        participant.save(update_fields=['attendance_confirmed'])

        self.client.login(username='player', password='testpass123')
        self.client.post(reverse('matches:match_leave', kwargs={'pk': self.match.pk}))

        participant.refresh_from_db()
        self.assertFalse(participant.attendance_confirmed)

        join_request = JoinRequest.objects.create(
            match=self.match,
            player=self.player,
        )
        self.client.login(username='organizer', password='testpass123')
        self.client.post(
            reverse(
                'matches:match_request_accept',
                kwargs={'pk': self.match.pk, 'request_id': join_request.pk},
            )
        )

        participant.refresh_from_db()
        self.assertEqual(participant.status, ParticipantStatus.CONFIRMED)
        self.assertFalse(participant.attendance_confirmed)

    def test_unconfirmed_player_cannot_confirm_attendance(self):
        other_player = User.objects.create_user(
            username='other_player',
            email='other_player@example.com',
            password='testpass123',
        )
        self.client.login(username='other_player', password='testpass123')

        self.client.post(reverse('matches:match_attendance', kwargs={'pk': self.match.pk}))

        self.assertFalse(
            MatchParticipant.objects.filter(
                match=self.match,
                player=other_player,
                attendance_confirmed=True,
            ).exists()
        )

    def test_detail_shows_participants_and_attendance_status_for_this_match(self):
        other_match = Match.objects.create(
            organizer=self.organizer,
            title='Other Match',
            date_time=timezone.now() + timedelta(days=2),
            location='Other field',
            skill_level='beginner',
            max_players=10,
            visibility='public',
        )
        other_player = User.objects.create_user(
            username='other_player',
            email='other_player@example.com',
            password='testpass123',
        )
        MatchParticipant.objects.create(
            match=self.match,
            player=other_player,
            status=ParticipantStatus.CONFIRMED,
            attendance_confirmed=False,
        )
        MatchParticipant.objects.create(
            match=other_match,
            player=other_player,
            status=ParticipantStatus.CONFIRMED,
            attendance_confirmed=True,
        )

        response = self.client.get(reverse('matches:match_detail', kwargs={'pk': self.match.pk}))

        self.assertContains(response, 'player')
        self.assertContains(response, 'Pending Confirmation')
        self.assertContains(response, 'Attendance confirmed')
        self.assertNotContains(response, 'other_player')


class MatchLeaveViewTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username='organizer',
            email='organizer@example.com',
            password='testpass123',
        )
        self.player = User.objects.create_user(
            username='player',
            email='player@example.com',
            password='testpass123',
        )
        self.match = Match.objects.create(
            organizer=self.organizer,
            title='Public Match',
            date_time=timezone.now() + timedelta(days=1),
            location='Local field',
            skill_level='beginner',
            max_players=10,
            visibility='public',
        )

    def test_leave_requires_login(self):
        response = self.client.post(reverse('matches:match_leave', kwargs={'pk': self.match.pk}))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/users/login/', response.url)

    def test_participant_can_leave_match(self):
        MatchParticipant.objects.create(match=self.match, player=self.player)
        self.client.login(username='player', password='testpass123')

        response = self.client.post(reverse('matches:match_leave', kwargs={'pk': self.match.pk}))

        self.assertRedirects(response, reverse('matches:match_detail', kwargs={'pk': self.match.pk}))
        participant = MatchParticipant.objects.get(match=self.match, player=self.player)
        self.assertEqual(participant.status, ParticipantStatus.LEFT)

    def test_leaving_frees_a_spot_to_rejoin(self):
        MatchParticipant.objects.create(match=self.match, player=self.player)
        self.client.login(username='player', password='testpass123')
        self.client.post(reverse('matches:match_leave', kwargs={'pk': self.match.pk}))

        self.client.post(reverse('matches:match_join', kwargs={'pk': self.match.pk}))

        participant = MatchParticipant.objects.get(match=self.match, player=self.player)
        self.assertEqual(participant.status, ParticipantStatus.CONFIRMED)
        self.assertEqual(MatchParticipant.objects.filter(match=self.match, player=self.player).count(), 1)

    def test_non_participant_cannot_leave(self):
        self.client.login(username='player', password='testpass123')

        response = self.client.post(reverse('matches:match_leave', kwargs={'pk': self.match.pk}))

        self.assertRedirects(response, reverse('matches:match_detail', kwargs={'pk': self.match.pk}))
        self.assertFalse(MatchParticipant.objects.filter(match=self.match, player=self.player).exists())


class MatchValidationRegressionTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(
            username='organizer',
            email='organizer@example.com',
            password='testpass123',
        )
        self.player_one = User.objects.create_user(
            username='player_one',
            email='player_one@example.com',
            password='testpass123',
        )
        self.player_two = User.objects.create_user(
            username='player_two',
            email='player_two@example.com',
            password='testpass123',
        )

    def test_model_rejects_max_players_below_confirmed_participants(self):
        match = Match.objects.create(
            organizer=self.organizer,
            title='Capacity Validation Match',
            date_time=timezone.now() + timedelta(days=2),
            location='Local field',
            skill_level='beginner',
            max_players=3,
            visibility='public',
        )
        MatchParticipant.objects.create(
            match=match,
            player=self.player_one,
            status=ParticipantStatus.CONFIRMED,
        )
        MatchParticipant.objects.create(
            match=match,
            player=self.player_two,
            status=ParticipantStatus.CONFIRMED,
        )

        match.max_players = 1

        with self.assertRaises(ValidationError):
            match.full_clean()

    def test_save_rejects_invalid_capacity_when_editing_match(self):
        match = Match.objects.create(
            organizer=self.organizer,
            title='Edit Capacity Match',
            date_time=timezone.now() + timedelta(days=3),
            location='Local field',
            skill_level='beginner',
            max_players=4,
            visibility='public',
        )
        MatchParticipant.objects.create(
            match=match,
            player=self.player_one,
            status=ParticipantStatus.CONFIRMED,
        )
        MatchParticipant.objects.create(
            match=match,
            player=self.player_two,
            status=ParticipantStatus.CONFIRMED,
        )

        match.max_players = 1

        with self.assertRaises(ValidationError):
            match.save()

    def test_pending_join_request_unique_constraint_avoids_duplicates(self):
        match = Match.objects.create(
            organizer=self.organizer,
            title='Request Validation Match',
            date_time=timezone.now() + timedelta(days=4),
            location='Local field',
            skill_level='beginner',
            max_players=5,
            visibility='approval_required',
        )

        JoinRequest.objects.create(
            match=match,
            player=self.player_one,
            request_status=JoinRequestStatus.PENDING,
        )

        with self.assertRaises(IntegrityError):
            JoinRequest.objects.create(
                match=match,
                player=self.player_one,
                request_status=JoinRequestStatus.PENDING,
            )


class WaitingListTests(TestCase):
    """FR10 - Waiting list."""

    def setUp(self):
        self.organizer = User.objects.create_user(
            username='organizer', email='organizer@example.com', password='testpass123'
        )
        self.player_a = User.objects.create_user(
            username='player_a', email='player_a@example.com', password='testpass123'
        )
        self.player_b = User.objects.create_user(
            username='player_b', email='player_b@example.com', password='testpass123'
        )
        self.player_c = User.objects.create_user(
            username='player_c', email='player_c@example.com', password='testpass123'
        )
        self.player_a2 = User.objects.create_user(
            username='player_a2', email='player_a2@example.com', password='testpass123'
        )
        self.match = Match.objects.create(
            organizer=self.organizer,
            title='Small Match',
            date_time=timezone.now() + timedelta(days=1),
            location='Local field',
            skill_level='beginner',
            max_players=2,
            visibility='public',
        )
        MatchParticipant.objects.create(
            match=self.match, player=self.player_a, status=ParticipantStatus.CONFIRMED
        )
        MatchParticipant.objects.create(
            match=self.match, player=self.player_a2, status=ParticipantStatus.CONFIRMED
        )

    def test_joining_full_match_adds_to_waiting_list(self):
        self.client.login(username='player_b', password='testpass123')

        self.client.post(reverse('matches:match_join', kwargs={'pk': self.match.pk}))

        participant = MatchParticipant.objects.get(match=self.match, player=self.player_b)
        self.assertEqual(participant.status, ParticipantStatus.WAITING)

    def test_cannot_join_waiting_list_twice(self):
        self.client.login(username='player_b', password='testpass123')
        self.client.post(reverse('matches:match_join', kwargs={'pk': self.match.pk}))

        self.client.post(reverse('matches:match_join', kwargs={'pk': self.match.pk}))

        self.assertEqual(
            MatchParticipant.objects.filter(match=self.match, player=self.player_b).count(), 1
        )

    def test_waiting_list_keeps_join_order(self):
        MatchParticipant.objects.create(
            match=self.match, player=self.player_b, status=ParticipantStatus.WAITING
        )
        MatchParticipant.objects.create(
            match=self.match, player=self.player_c, status=ParticipantStatus.WAITING
        )

        waiting = list(self.match.waiting_participants)

        self.assertEqual(waiting, [
            MatchParticipant.objects.get(match=self.match, player=self.player_b),
            MatchParticipant.objects.get(match=self.match, player=self.player_c),
        ])

    def test_player_can_leave_waiting_list(self):
        MatchParticipant.objects.create(
            match=self.match, player=self.player_b, status=ParticipantStatus.WAITING
        )
        self.client.login(username='player_b', password='testpass123')

        self.client.post(reverse('matches:match_leave', kwargs={'pk': self.match.pk}))

        participant = MatchParticipant.objects.get(match=self.match, player=self.player_b)
        self.assertEqual(participant.status, ParticipantStatus.LEFT)


class AutomaticReplacementTests(TestCase):
    """FR11 - Automatic replacement."""

    def setUp(self):
        self.organizer = User.objects.create_user(
            username='organizer', email='organizer@example.com', password='testpass123'
        )
        self.player_a = User.objects.create_user(
            username='player_a', email='player_a@example.com', password='testpass123'
        )
        self.player_a2 = User.objects.create_user(
            username='player_a2', email='player_a2@example.com', password='testpass123'
        )
        self.player_b = User.objects.create_user(
            username='player_b', email='player_b@example.com', password='testpass123'
        )
        self.player_c = User.objects.create_user(
            username='player_c', email='player_c@example.com', password='testpass123'
        )
        self.match = Match.objects.create(
            organizer=self.organizer,
            title='Small Match',
            date_time=timezone.now() + timedelta(days=1),
            location='Local field',
            skill_level='beginner',
            max_players=2,
            visibility='public',
        )
        MatchParticipant.objects.create(
            match=self.match, player=self.player_a, status=ParticipantStatus.CONFIRMED
        )
        MatchParticipant.objects.create(
            match=self.match, player=self.player_a2, status=ParticipantStatus.CONFIRMED
        )
        MatchParticipant.objects.create(
            match=self.match, player=self.player_b, status=ParticipantStatus.WAITING
        )
        MatchParticipant.objects.create(
            match=self.match, player=self.player_c, status=ParticipantStatus.WAITING
        )

    def test_leaving_promotes_first_waiting_player(self):
        self.client.login(username='player_a', password='testpass123')

        self.client.post(reverse('matches:match_leave', kwargs={'pk': self.match.pk}))

        player_b = MatchParticipant.objects.get(match=self.match, player=self.player_b)
        player_c = MatchParticipant.objects.get(match=self.match, player=self.player_c)
        self.assertEqual(player_b.status, ParticipantStatus.CONFIRMED)
        self.assertEqual(player_c.status, ParticipantStatus.WAITING)

    def test_leaving_waiting_list_does_not_promote_anyone(self):
        self.client.login(username='player_c', password='testpass123')

        self.client.post(reverse('matches:match_leave', kwargs={'pk': self.match.pk}))

        player_a = MatchParticipant.objects.get(match=self.match, player=self.player_a)
        player_a2 = MatchParticipant.objects.get(match=self.match, player=self.player_a2)
        player_b = MatchParticipant.objects.get(match=self.match, player=self.player_b)
        self.assertEqual(player_a.status, ParticipantStatus.CONFIRMED)
        self.assertEqual(player_a2.status, ParticipantStatus.CONFIRMED)
        self.assertEqual(player_b.status, ParticipantStatus.WAITING)

    def test_increasing_max_players_promotes_from_waiting_list(self):
        self.client.login(username='organizer', password='testpass123')

        self.client.post(
            reverse('matches:match_update', kwargs={'pk': self.match.pk}),
            data={
                'title': self.match.title,
                'date_time': self.match.date_time.strftime('%Y-%m-%dT%H:%M'),
                'location': self.match.location,
                'skill_level': self.match.skill_level,
                'max_players': 3,
                'visibility': self.match.visibility,
            },
        )

        player_b = MatchParticipant.objects.get(match=self.match, player=self.player_b)
        player_c = MatchParticipant.objects.get(match=self.match, player=self.player_c)
        self.assertEqual(player_b.status, ParticipantStatus.CONFIRMED)
        self.assertEqual(player_c.status, ParticipantStatus.WAITING)


class MatchCancelViewTests(TestCase):
    """FR9 - Cancel match and notification tests."""

    def setUp(self):
        self.organizer = User.objects.create_user(
            username='organizer',
            email='organizer@example.com',
            password='testpass123',
        )
        self.player_one = User.objects.create_user(
            username='player_one',
            email='player1@example.com',
            password='testpass123',
        )
        self.player_two = User.objects.create_user(
            username='player_two',
            email='player2@example.com',
            password='testpass123',
        )
        self.other_user = User.objects.create_user(
            username='other_user',
            email='other@example.com',
            password='testpass123',
        )
        self.match = Match.objects.create(
            organizer=self.organizer,
            title='Weekend Cup Match',
            date_time=timezone.now() + timedelta(days=2),
            location='Central Stadium',
            skill_level='intermediate',
            max_players=10,
            visibility='public',
        )

    def test_default_status_is_active(self):
        self.assertEqual(self.match.status, MatchStatus.ACTIVE)
        self.assertFalse(self.match.is_cancelled)

    def test_cancel_requires_login(self):
        response = self.client.post(
            reverse('matches:match_cancel', kwargs={'pk': self.match.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/users/login/', response.url)

    def test_only_organizer_can_cancel_match(self):
        self.client.login(username='other_user', password='testpass123')
        response = self.client.post(
            reverse('matches:match_cancel', kwargs={'pk': self.match.pk})
        )
        self.assertRedirects(
            response, reverse('matches:match_detail', kwargs={'pk': self.match.pk})
        )
        self.match.refresh_from_db()
        self.assertEqual(self.match.status, MatchStatus.ACTIVE)

    def test_organizer_can_cancel_match_and_status_becomes_cancelled(self):
        self.client.login(username='organizer', password='testpass123')
        response = self.client.post(
            reverse('matches:match_cancel', kwargs={'pk': self.match.pk})
        )
        self.assertRedirects(
            response, reverse('matches:match_detail', kwargs={'pk': self.match.pk})
        )
        self.match.refresh_from_db()
        self.assertEqual(self.match.status, MatchStatus.CANCELLED)
        self.assertTrue(self.match.is_cancelled)

    def test_cannot_cancel_already_cancelled_match(self):
        self.match.status = MatchStatus.CANCELLED
        self.match.save(update_fields=['status'])

        self.client.login(username='organizer', password='testpass123')
        response = self.client.post(
            reverse('matches:match_cancel', kwargs={'pk': self.match.pk})
        )
        self.assertRedirects(
            response, reverse('matches:match_detail', kwargs={'pk': self.match.pk})
        )
        self.match.refresh_from_db()
        self.assertEqual(self.match.status, MatchStatus.CANCELLED)

    def test_cancellation_triggers_notification_and_logs(self):
        MatchParticipant.objects.create(
            match=self.match,
            player=self.player_one,
            status=ParticipantStatus.CONFIRMED,
        )
        MatchParticipant.objects.create(
            match=self.match,
            player=self.player_two,
            status=ParticipantStatus.CONFIRMED,
        )

        self.client.login(username='organizer', password='testpass123')

        with self.assertLogs('matches.services', level='INFO') as log:
            response = self.client.post(
                reverse('matches:match_cancel', kwargs={'pk': self.match.pk}),
                follow=True,
            )

        self.assertIn('Weekend Cup Match', log.output[0])
        self.assertIn('player_one', log.output[0])
        self.assertIn('player_two', log.output[0])
        self.assertContains(response, 'The match has been cancelled successfully.')
        self.assertContains(response, 'Notification sent to 2 confirmed participant(s)')

    def test_cancellation_with_no_participants_notifies_correctly(self):
        self.client.login(username='organizer', password='testpass123')
        response = self.client.post(
            reverse('matches:match_cancel', kwargs={'pk': self.match.pk}),
            follow=True,
        )
        self.assertContains(response, 'No confirmed participants to notify.')

    def test_cannot_join_cancelled_match(self):
        self.match.status = MatchStatus.CANCELLED
        self.match.save(update_fields=['status'])

        self.client.login(username='player_one', password='testpass123')
        response = self.client.post(
            reverse('matches:match_join', kwargs={'pk': self.match.pk}),
            follow=True,
        )
        self.assertContains(response, 'This match has been cancelled.')
        self.assertFalse(
            MatchParticipant.objects.filter(
                match=self.match, player=self.player_one
            ).exists()
        )

    def test_cannot_request_join_cancelled_match(self):
        approval_match = Match.objects.create(
            organizer=self.organizer,
            title='Approval Cancelled Match',
            date_time=timezone.now() + timedelta(days=2),
            location='Central Stadium',
            skill_level='intermediate',
            max_players=10,
            visibility='approval_required',
            status=MatchStatus.CANCELLED,
        )

        self.client.login(username='player_one', password='testpass123')
        response = self.client.post(
            reverse('matches:match_request_join', kwargs={'pk': approval_match.pk}),
            follow=True,
        )
        self.assertContains(response, 'This match has been cancelled.')
        self.assertFalse(
            JoinRequest.objects.filter(
                match=approval_match, player=self.player_one
            ).exists()
        )

    def test_cannot_edit_cancelled_match(self):
        self.match.status = MatchStatus.CANCELLED
        self.match.save(update_fields=['status'])

        self.client.login(username='organizer', password='testpass123')
        response = self.client.get(
            reverse('matches:match_update', kwargs={'pk': self.match.pk}),
            follow=True,
        )
        self.assertContains(response, 'Cancelled matches cannot be edited.')

    def test_match_detail_shows_cancelled_banner_and_disables_actions(self):
        self.match.status = MatchStatus.CANCELLED
        self.match.save(update_fields=['status'])

        self.client.login(username='player_one', password='testpass123')
        response = self.client.get(
            reverse('matches:match_detail', kwargs={'pk': self.match.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This match has been cancelled by the organizer.')
        self.assertContains(response, 'Cancelled')
        self.assertNotContains(response, 'Join match')
        self.assertNotContains(response, 'Cancel match')


class MatchFilterListViewTests(TestCase):
    """FR12 - Search and filtering of matches."""

    def setUp(self):
        self.organizer = User.objects.create_user(
            username='organizer',
            email='organizer@example.com',
            password='testpass123',
        )
        self.base_time = timezone.now()

        # Match 1: Active, Central Park, Beginner, Date: Day + 2
        self.match_1 = Match.objects.create(
            organizer=self.organizer,
            title='Central Beginner Match',
            date_time=self.base_time + timedelta(days=2),
            location='Central Park Court 1',
            skill_level='beginner',
            max_players=10,
            visibility='public',
            status=MatchStatus.ACTIVE,
        )

        # Match 2: Active, Central Stadium, Intermediate, Date: Day + 4
        self.match_2 = Match.objects.create(
            organizer=self.organizer,
            title='Central Intermediate Match',
            date_time=self.base_time + timedelta(days=4),
            location='Central Stadium',
            skill_level='intermediate',
            max_players=12,
            visibility='public',
            status=MatchStatus.ACTIVE,
        )

        # Match 3: Active, North Field, Advanced, Date: Day + 6
        self.match_3 = Match.objects.create(
            organizer=self.organizer,
            title='North Advanced Match',
            date_time=self.base_time + timedelta(days=6),
            location='North Field Arena',
            skill_level='advanced',
            max_players=14,
            visibility='public',
            status=MatchStatus.ACTIVE,
        )

        # Match 4: Cancelled, Central Park, Beginner, Date: Day + 3
        self.match_cancelled = Match.objects.create(
            organizer=self.organizer,
            title='Cancelled Central Match',
            date_time=self.base_time + timedelta(days=3),
            location='Central Park Court 2',
            skill_level='beginner',
            max_players=10,
            visibility='public',
            status=MatchStatus.CANCELLED,
        )

    def test_list_view_automatically_excludes_cancelled_matches(self):
        response = self.client.get(reverse('matches:match_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Central Beginner Match')
        self.assertContains(response, 'Central Intermediate Match')
        self.assertContains(response, 'North Advanced Match')
        self.assertNotContains(response, 'Cancelled Central Match')

    def test_filter_by_location_partial_and_case_insensitive(self):
        response = self.client.get(reverse('matches:match_list'), {'location': 'cEnTrAl'})
        self.assertEqual(response.status_code, 200)
        matches = list(response.context['matches'])
        self.assertIn(self.match_1, matches)
        self.assertIn(self.match_2, matches)
        self.assertNotIn(self.match_3, matches)
        self.assertNotIn(self.match_cancelled, matches)

    def test_filter_by_skill_level_exact(self):
        response = self.client.get(reverse('matches:match_list'), {'skill_level': 'intermediate'})
        self.assertEqual(response.status_code, 200)
        matches = list(response.context['matches'])
        self.assertEqual(matches, [self.match_2])

    def test_filter_by_date_from_gte(self):
        filter_date = (self.base_time + timedelta(days=4)).strftime('%Y-%m-%d')
        response = self.client.get(reverse('matches:match_list'), {'date': filter_date})
        self.assertEqual(response.status_code, 200)
        matches = list(response.context['matches'])
        self.assertNotIn(self.match_1, matches)
        self.assertIn(self.match_2, matches)
        self.assertIn(self.match_3, matches)

    def test_combined_filters(self):
        filter_date = (self.base_time + timedelta(days=3)).strftime('%Y-%m-%d')
        response = self.client.get(
            reverse('matches:match_list'),
            {
                'location': 'central',
                'skill_level': 'intermediate',
                'date': filter_date,
            },
        )
        self.assertEqual(response.status_code, 200)
        matches = list(response.context['matches'])
        self.assertEqual(matches, [self.match_2])

    def test_context_preserves_filter_parameters(self):
        filter_date = (self.base_time + timedelta(days=2)).strftime('%Y-%m-%d')
        response = self.client.get(
            reverse('matches:match_list'),
            {
                'location': 'Central',
                'skill_level': 'beginner',
                'date': filter_date,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['location_query'], 'Central')
        self.assertEqual(response.context['skill_level_query'], 'beginner')
        self.assertEqual(response.context['date_query'], filter_date)
        self.assertTrue(response.context['is_filtered'])
        self.assertContains(response, 'value="Central"')
        self.assertContains(response, 'selected>Beginner</option>')
        self.assertContains(response, f'value="{filter_date}"')

    def test_no_matches_found_shows_empty_filter_message(self):
        response = self.client.get(
            reverse('matches:match_list'),
            {'location': 'NonExistentLocationXYZ'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No matches found matching your filter criteria.')
        self.assertContains(response, 'Clear filters')



