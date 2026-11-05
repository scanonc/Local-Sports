from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from matches.models import (
	Match,
	MatchParticipant,
	MatchResult,
	MatchTeam,
	MatchTeamAssignment,
	PlayerRating,
)

from ..models import User


class PlayerProfileViewTests(TestCase):
	def setUp(self):
		self.viewer = User.objects.create_user(
			username='viewer',
			email='viewer@example.com',
			password='testpass123',
		)
		self.player = User.objects.create_user(
			username='player',
			email='player@example.com',
			password='testpass123',
			first_name='Player',
			last_name='One',
		)

	def create_completed_match(self, title, result=MatchResult.TEAM_A):
		match = Match.objects.create(
			organizer=self.viewer,
			title=title,
			date_time=timezone.now() + timedelta(days=1),
			location='Local field',
			skill_level='beginner',
			max_players=6,
			result=result,
			status='closed',
		)
		Match.objects.filter(pk=match.pk).update(
			date_time=timezone.now() - timedelta(days=1),
		)
		participant = MatchParticipant.objects.create(
			match=match,
			player=self.player,
		)
		MatchTeamAssignment.objects.create(
			match=match,
			participant=participant,
			team=MatchTeam.A,
		)
		return match

	def profile_url(self):
		return reverse('users:player_profile', kwargs={'pk': self.player.pk})

	def test_player_can_view_another_players_profile(self):
		self.client.force_login(self.viewer)

		response = self.client.get(self.profile_url())

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Player One')
		self.assertContains(response, '@player')

	def test_player_can_view_own_profile(self):
		self.client.force_login(self.player)

		response = self.client.get(
			reverse('users:player_profile', kwargs={'pk': self.player.pk})
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Player Statistics')

	def test_empty_profile_shows_beginner_and_no_ratings(self):
		self.client.force_login(self.viewer)

		response = self.client.get(self.profile_url())

		self.assertContains(response, 'No ratings')
		self.assertContains(response, 'Beginner')
		self.assertContains(response, 'No completed matches with a registered result.')

	def test_profile_shows_stats_average_and_only_three_recent_matches(self):
		matches = [
			self.create_completed_match(f'Match {index}')
			for index in range(4)
		]
		raters = [
			User.objects.create_user(
				username=f'rater{index}',
				email=f'rater{index}@example.com',
				password='testpass123',
			)
			for index in range(5)
		]
		PlayerRating.objects.bulk_create(
			[
				PlayerRating(
					match=matches[0],
					rater=rater,
					player=self.player,
					stars=stars,
				)
				for rater, stars in zip(raters, [5, 4, 4, 4, 4])
			]
		)

		self.client.force_login(self.viewer)
		response = self.client.get(self.profile_url())

		self.assertContains(response, '4.2')
		self.assertContains(response, '(5 ratings)')
		self.assertContains(response, 'Matches Played')
		self.assertContains(response, 'Won')
		self.assertContains(response, 'Match 3')
		self.assertContains(response, 'Match 2')
		self.assertContains(response, 'Match 1')
		self.assertNotContains(response, 'Match 0')
		self.assertNotContains(response, 'rater0')
