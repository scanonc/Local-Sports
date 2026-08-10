from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.test import TestCase
from django.utils import timezone

from .forms import MatchForm
from .models import Match, MatchParticipant, ParticipantStatus


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

    def test_cannot_join_full_match(self):
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

        self.assertFalse(
            MatchParticipant.objects.filter(match=self.public_match, player=third_player).exists()
        )

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
