from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from matches.models import Match, MatchVisibility

from .models import Notification, Report, ReportReason, User


class UserModelTests(TestCase):
    def test_user_str_uses_full_name_or_username(self):
        user = User.objects.create_user(
            username='player1',
            email='player1@example.com',
            password='testpass123',
            first_name='Alex',
            last_name='Morgan',
        )

        self.assertEqual(str(user), 'Alex Morgan')


class NotificationModelTests(TestCase):
    def test_notification_tracks_read_state_for_a_user(self):
        organizer = User.objects.create_user(
            username='organizer',
            email='organizer@example.com',
            password='testpass123',
        )
        user = User.objects.create_user(
            username='player1',
            email='player1@example.com',
            password='testpass123',
        )
        match = Match.objects.create(
            organizer=organizer,
            title='Cancelled match',
            date_time=timezone.now() + timedelta(days=2),
            location='Court 1',
            skill_level='beginner',
            max_players=4,
            visibility=MatchVisibility.PUBLIC,
        )

        notification = Notification.objects.create(
            user=user,
            match=match,
            message='The match “Cancelled match” was cancelled.',
        )

        self.assertEqual(notification.user, user)
        self.assertFalse(notification.is_read)
        self.assertEqual(notification.match, match)


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
