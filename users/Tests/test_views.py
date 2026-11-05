from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from matches.models import Match, MatchVisibility

from ..models import FavoritePlayer, Notification, Report, ReportReason, User


class FavoritePlayerTests(TestCase):
    """FR17 - Favorite players."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='player1', email='player1@example.com', password='testpass123'
        )
        self.other = User.objects.create_user(
            username='player2', email='player2@example.com', password='testpass123'
        )

    def test_toggling_adds_player_to_favorites(self):
        self.client.login(username='player1', password='testpass123')

        self.client.post(reverse('users:favorite_toggle', kwargs={'pk': self.other.pk}))

        self.assertTrue(
            FavoritePlayer.objects.filter(user=self.user, favorite=self.other).exists()
        )

    def test_toggling_twice_removes_favorite(self):
        self.client.login(username='player1', password='testpass123')
        self.client.post(reverse('users:favorite_toggle', kwargs={'pk': self.other.pk}))

        self.client.post(reverse('users:favorite_toggle', kwargs={'pk': self.other.pk}))

        self.assertFalse(
            FavoritePlayer.objects.filter(user=self.user, favorite=self.other).exists()
        )

    def test_cannot_favorite_yourself(self):
        self.client.login(username='player1', password='testpass123')

        self.client.post(reverse('users:favorite_toggle', kwargs={'pk': self.user.pk}))

        self.assertFalse(
            FavoritePlayer.objects.filter(user=self.user, favorite=self.user).exists()
        )

    def test_favorite_toggle_requires_login(self):
        response = self.client.post(
            reverse('users:favorite_toggle', kwargs={'pk': self.other.pk})
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('/users/login/', response.url)

    def test_favorites_list_only_shows_own_favorites(self):
        third = User.objects.create_user(
            username='player3', email='player3@example.com', password='testpass123'
        )
        FavoritePlayer.objects.create(user=self.user, favorite=self.other)
        FavoritePlayer.objects.create(user=third, favorite=self.other)

        self.client.login(username='player1', password='testpass123')
        response = self.client.get(reverse('users:favorites'))

        self.assertEqual(len(response.context['favorites']), 1)
        self.assertEqual(response.context['favorites'][0].favorite, self.other)


class ReportUserTests(TestCase):
    """FR18 - Report users."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='player1', email='player1@example.com', password='testpass123'
        )
        self.other = User.objects.create_user(
            username='player2', email='player2@example.com', password='testpass123'
        )

    def test_submitting_report_records_reason(self):
        self.client.login(username='player1', password='testpass123')

        self.client.post(
            reverse('users:report_user', kwargs={'pk': self.other.pk}),
            data={'reason': ReportReason.NO_SHOW, 'details': 'Did not show up to the match.'},
        )

        report = Report.objects.get(reporter=self.user, reported_user=self.other)
        self.assertEqual(report.reason, ReportReason.NO_SHOW)
        self.assertEqual(report.details, 'Did not show up to the match.')

    def test_details_are_optional(self):
        self.client.login(username='player1', password='testpass123')

        self.client.post(
            reverse('users:report_user', kwargs={'pk': self.other.pk}),
            data={'reason': ReportReason.OTHER, 'details': ''},
        )

        self.assertTrue(
            Report.objects.filter(reporter=self.user, reported_user=self.other).exists()
        )

    def test_cannot_report_yourself(self):
        self.client.login(username='player1', password='testpass123')

        self.client.post(
            reverse('users:report_user', kwargs={'pk': self.user.pk}),
            data={'reason': ReportReason.OTHER, 'details': ''},
        )

        self.assertFalse(Report.objects.filter(reporter=self.user, reported_user=self.user).exists())

    def test_report_requires_login(self):
        response = self.client.post(
            reverse('users:report_user', kwargs={'pk': self.other.pk}),
            data={'reason': ReportReason.OTHER, 'details': ''},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('/users/login/', response.url)

    def test_can_submit_multiple_reports_for_different_incidents(self):
        self.client.login(username='player1', password='testpass123')

        self.client.post(
            reverse('users:report_user', kwargs={'pk': self.other.pk}),
            data={'reason': ReportReason.NO_SHOW, 'details': 'First incident.'},
        )
        self.client.post(
            reverse('users:report_user', kwargs={'pk': self.other.pk}),
            data={'reason': ReportReason.ABUSIVE_LANGUAGE, 'details': 'Second incident.'},
        )

        self.assertEqual(
            Report.objects.filter(reporter=self.user, reported_user=self.other).count(), 2
        )


class SignupViewTests(TestCase):
    def test_player_can_sign_up_without_skill_level(self):
        response = self.client.post(
            reverse('users:signup'),
            data={
                'username': 'new_player',
                'email': 'new_player@example.com',
                'first_name': 'New',
                'last_name': 'Player',
                'profile_picture': '',
                'password1': 'testpass123!',
                'password2': 'testpass123!',
            },
        )

        self.assertRedirects(response, reverse('home'))
        self.assertTrue(User.objects.filter(username='new_player').exists())
        self.assertNotContains(
            self.client.get(reverse('users:signup')),
            'Skill level',
        )
