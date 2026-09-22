from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from matches.models import Match, MatchVisibility

from .models import FavoritePlayer, Notification, User


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
