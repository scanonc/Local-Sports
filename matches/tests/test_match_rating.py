from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import Match, MatchParticipant, PlayerRating
from ..team_services import get_player_average_rating


class MatchRatingTests(TestCase):
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
        self.rating_url = reverse(
            'matches:match_player_rating',
            args=[self.match.pk, self.users[1].pk],
        )

    def finish_match(self):
        Match.objects.filter(pk=self.match.pk).update(
            date_time=timezone.now() - timedelta(hours=2),
        )
        self.match.refresh_from_db()

    def test_participant_can_save_and_update_player_rating(self):
        self.finish_match()
        self.client.force_login(self.users[0])

        self.assertContains(self.client.get(self.detail_url), 'Rate players')
        self.assertEqual(
            self.client.post(self.rating_url, {'stars': 5}).status_code,
            302,
        )
        self.assertEqual(get_player_average_rating(self.users[1]), 5)

        self.client.post(self.rating_url, {'stars': 2})

        self.assertEqual(PlayerRating.objects.count(), 1)
        self.assertEqual(get_player_average_rating(self.users[1]), 2)
        self.assertEqual(get_player_average_rating(self.users[0]), 3)

    def test_future_match_rejects_rating(self):
        self.client.force_login(self.users[0])

        self.assertNotContains(self.client.get(self.detail_url), 'Rate players')
        self.assertEqual(
            self.client.post(self.rating_url, {'stars': 5}).status_code,
            403,
        )

    def test_invalid_rating_values_are_not_saved(self):
        self.finish_match()
        self.client.force_login(self.users[0])

        for stars in ['', '0', '6', '-1', '2.5', 'invalid']:
            self.client.post(self.rating_url, {'stars': stars})

        self.assertFalse(PlayerRating.objects.exists())

    def test_only_eligible_users_can_rate_eligible_players(self):
        self.finish_match()

        self.assertEqual(
            self.client.post(self.rating_url, {'stars': 5}).status_code,
            302,
        )
        for user in self.users[2:]:
            self.client.force_login(user)
            self.assertEqual(
                self.client.post(self.rating_url, {'stars': 5}).status_code,
                403,
            )

        self.client.force_login(self.users[0])
        for target, expected in [
            (self.users[0], 403),
            (self.users[2], 404),
            (self.users[3], 404),
        ]:
            url = reverse(
                'matches:match_player_rating',
                args=[self.match.pk, target.pk],
            )
            self.assertEqual(
                self.client.post(url, {'stars': 5}).status_code,
                expected,
            )
        self.assertFalse(PlayerRating.objects.exists())

    def test_rating_endpoint_does_not_accept_get(self):
        self.client.force_login(self.users[0])

        self.assertEqual(self.client.get(self.rating_url).status_code, 405)

    def test_database_rejects_invalid_range_and_self_rating(self):
        for player, stars in [(self.users[1], 6), (self.users[0], 3)]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                PlayerRating.objects.bulk_create(
                    [
                        PlayerRating(
                            match=self.match,
                            rater=self.users[0],
                            player=player,
                            stars=stars,
                        ),
                    ],
                )

    def test_participant_can_submit_and_update_multiple_ratings(self):
        self.finish_match()
        self.client.force_login(self.users[0])
        bulk_url = reverse(
            'matches:match_player_rating',
            args=[self.match.pk],
        )

        response = self.client.post(
            bulk_url,
            {f'stars_{self.users[1].pk}': 4},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_player_average_rating(self.users[1]), 4)

        self.client.post(
            bulk_url,
            {f'stars_{self.users[1].pk}': 2},
        )

        self.assertEqual(PlayerRating.objects.count(), 1)
        self.assertEqual(get_player_average_rating(self.users[1]), 2)
