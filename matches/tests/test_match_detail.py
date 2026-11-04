from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import Match, MatchParticipant, MatchStatus


class MatchDetailTests(TestCase):
    def setUp(self):
        self.users = [
            get_user_model().objects.create_user(
                username=f'user{i}',
                email=f'user{i}@example.com',
            )
            for i in range(4)
        ]
        self.match = Match.objects.create(
            organizer=self.users[3],
            title='Football & friends / final',
            location='Field #2, Bogotá',
            date_time=timezone.now() + timedelta(days=1),
            skill_level='beginner',
            max_players=6,
        )
        for user in self.users[:2]:
            MatchParticipant.objects.create(match=self.match, player=user)
        MatchParticipant.objects.create(
            match=self.match,
            player=self.users[2],
            status='waiting',
        )
        self.detail_url = reverse(
            'matches:match_detail',
            args=[self.match.pk],
        )

    def finish_match(self):
        Match.objects.filter(pk=self.match.pk).update(
            date_time=timezone.now() - timedelta(hours=2),
        )
        self.match.refresh_from_db()

    def test_calendar_contains_encoded_match_data_and_utc_dates(self):
        self.client.force_login(self.users[0])

        response = self.client.get(self.detail_url)
        calendar_url = response.context['google_calendar_url']
        query = parse_qs(urlparse(calendar_url).query)
        start, end = query['dates'][0].split('/')

        self.assertEqual(query['text'], [self.match.title])
        self.assertEqual(query['location'], [self.match.location])
        self.assertEqual(
            start,
            self.match.date_time.strftime('%Y%m%dT%H%M%SZ'),
        )
        self.assertEqual(
            end,
            (self.match.date_time + timedelta(hours=1)).strftime(
                '%Y%m%dT%H%M%SZ',
            ),
        )
        self.assertContains(response, 'Add to Google Calendar')

    def test_calendar_is_hidden_for_anonymous_waiting_and_nonparticipants(self):
        for user in [None, self.users[2], self.users[3]]:
            self.client.logout()
            if user:
                self.client.force_login(user)

            self.assertNotContains(
                self.client.get(self.detail_url),
                'Add to Google Calendar',
            )

    def test_cancelled_match_hides_calendar_and_ratings(self):
        self.finish_match()
        Match.objects.filter(pk=self.match.pk).update(
            status=MatchStatus.CANCELLED,
        )
        self.client.force_login(self.users[0])

        response = self.client.get(self.detail_url)

        self.assertNotContains(response, 'Add to Google Calendar')
        self.assertNotContains(response, 'Rate players')

    def test_finished_match_shows_finished_status_and_hides_leave_action(self):
        self.finish_match()
        self.client.force_login(self.users[0])

        response = self.client.get(self.detail_url)

        self.assertContains(response, 'Finished')
        self.assertNotContains(response, '>Leave match<')
        self.assertNotContains(response, 'Add to Google Calendar')
