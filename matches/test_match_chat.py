from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Match,
    MatchMessage,
    MatchParticipant,
    MatchStatus,
    ParticipantStatus,
)


User = get_user_model()


class MatchChatTests(TestCase):
    """FR22 - Match chat system."""

    def setUp(self):
        self.organizer = self._create_user('organizer')
        self.player = self._create_user('player')
        self.waiting_player = self._create_user('waiting')
        self.left_player = self._create_user('left')
        self.outsider = self._create_user('outsider')

        self.match = Match.objects.create(
            organizer=self.organizer,
            title='Sunday Match',
            date_time=timezone.now() + timedelta(days=2),
            location='Local field',
            skill_level='beginner',
            max_players=2,
            visibility='public',
        )
        self._join(self.player, ParticipantStatus.CONFIRMED)
        self._join(self.waiting_player, ParticipantStatus.WAITING)
        self._join(self.left_player, ParticipantStatus.LEFT)

        self.post_url = reverse('matches:match_message_create', kwargs={'pk': self.match.pk})
        self.detail_url = reverse('matches:match_detail', kwargs={'pk': self.match.pk})

    def _create_user(self, username):
        return User.objects.create_user(
            username=username,
            email=f'{username}@example.com',
            password='testpass123',
        )

    def _join(self, user, status):
        return MatchParticipant.objects.create(match=self.match, player=user, status=status)

    def _post(self, user, content):
        self.client.login(username=user.username, password='testpass123')
        return self.client.post(self.post_url, data={'content': content})

    def test_organizer_can_publish_a_message(self):
        response = self._post(self.organizer, 'See you all at 5.')

        self.assertRedirects(response, f'{self.detail_url}#match-chat', fetch_redirect_response=False)
        message = MatchMessage.objects.get()
        self.assertEqual(message.match, self.match)
        self.assertEqual(message.author, self.organizer)
        self.assertEqual(message.content, 'See you all at 5.')

    def test_confirmed_participant_can_publish_a_message(self):
        self._post(self.player, 'I will bring the ball.')

        message = MatchMessage.objects.get()
        self.assertEqual(message.author, self.player)

    def test_author_and_match_come_from_the_request_not_the_form(self):
        self.client.login(username='player', password='testpass123')

        self.client.post(
            self.post_url,
            data={'content': 'Hi', 'author': self.organizer.pk, 'match': 999},
        )

        message = MatchMessage.objects.get()
        self.assertEqual(message.author, self.player)
        self.assertEqual(message.match, self.match)

    def test_waiting_list_player_cannot_publish(self):
        self._post(self.waiting_player, 'Let me in!')

        self.assertFalse(MatchMessage.objects.exists())

    def test_player_who_left_cannot_publish(self):
        self._post(self.left_player, 'Still here?')

        self.assertFalse(MatchMessage.objects.exists())

    def test_user_outside_the_match_cannot_publish(self):
        self._post(self.outsider, 'Hello?')

        self.assertFalse(MatchMessage.objects.exists())

    def test_publishing_requires_login(self):
        response = self.client.post(self.post_url, data={'content': 'Anonymous'})

        self.assertEqual(response.status_code, 302)
        self.assertIn('/users/login/', response.url)
        self.assertFalse(MatchMessage.objects.exists())

    def test_message_endpoint_does_not_accept_get(self):
        self.client.login(username='player', password='testpass123')

        response = self.client.get(self.post_url)

        self.assertEqual(response.status_code, 405)

    def test_empty_or_blank_message_is_rejected(self):
        self._post(self.player, '')
        self._post(self.player, '    ')

        self.assertFalse(MatchMessage.objects.exists())

    def test_message_longer_than_the_limit_is_rejected(self):
        self._post(self.player, 'x' * (MatchMessage.MAX_LENGTH + 1))

        self.assertFalse(MatchMessage.objects.exists())

    def test_message_with_exactly_the_limit_is_accepted(self):
        self._post(self.player, 'x' * MatchMessage.MAX_LENGTH)

        self.assertEqual(MatchMessage.objects.count(), 1)

    def test_cannot_publish_in_a_cancelled_match(self):
        Match.objects.filter(pk=self.match.pk).update(status=MatchStatus.CANCELLED)

        self._post(self.player, 'Is it still on?')

        self.assertFalse(MatchMessage.objects.exists())

    def test_can_publish_after_the_match_has_started(self):
        Match.objects.filter(pk=self.match.pk).update(
            date_time=timezone.now() - timedelta(hours=3)
        )

        self._post(self.player, 'Great game, thanks!')

        self.assertEqual(MatchMessage.objects.count(), 1)

    def test_thread_is_shown_oldest_first_to_participants(self):
        MatchMessage.objects.create(match=self.match, author=self.organizer, content='first')
        MatchMessage.objects.create(match=self.match, author=self.player, content='second')
        MatchMessage.objects.create(match=self.match, author=self.organizer, content='third')

        self.client.login(username='player', password='testpass123')
        response = self.client.get(self.detail_url)

        self.assertTrue(response.context['user_can_use_chat'])
        self.assertEqual(
            [message.content for message in response.context['chat_messages']],
            ['first', 'second', 'third'],
        )

    def test_thread_only_contains_messages_of_that_match(self):
        other_match = Match.objects.create(
            organizer=self.organizer,
            title='Other Match',
            date_time=timezone.now() + timedelta(days=3),
            location='Other field',
            skill_level='beginner',
            max_players=2,
            visibility='public',
        )
        MatchMessage.objects.create(match=other_match, author=self.organizer, content='elsewhere')

        self.client.login(username='organizer', password='testpass123')
        response = self.client.get(self.detail_url)

        self.assertEqual(len(response.context['chat_messages']), 0)

    def test_thread_is_hidden_from_users_who_are_not_in_the_match(self):
        MatchMessage.objects.create(match=self.match, author=self.player, content='private talk')

        self.client.login(username='outsider', password='testpass123')
        outsider_response = self.client.get(self.detail_url)
        self.client.logout()
        anonymous_response = self.client.get(self.detail_url)

        for response in (outsider_response, anonymous_response):
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.context['user_can_use_chat'])
            self.assertNotContains(response, 'private talk')

    def test_cancelled_match_thread_is_still_visible_but_read_only(self):
        MatchMessage.objects.create(match=self.match, author=self.organizer, content='see you')
        Match.objects.filter(pk=self.match.pk).update(status=MatchStatus.CANCELLED)

        self.client.login(username='player', password='testpass123')
        response = self.client.get(self.detail_url)

        self.assertContains(response, 'see you')
        self.assertContains(response, 'the chat is read-only')
        self.assertNotContains(response, 'Send message')

    def test_message_content_is_escaped(self):
        MatchMessage.objects.create(
            match=self.match,
            author=self.player,
            content='<script>alert(1)</script>',
        )

        self.client.login(username='player', password='testpass123')
        response = self.client.get(self.detail_url)

        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
