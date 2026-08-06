from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.test import TestCase
from django.utils import timezone

from .forms import MatchForm
from .models import Match


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
