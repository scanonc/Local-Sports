from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from matches.models import Match, MatchVisibility

from .models import Notification, User


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
