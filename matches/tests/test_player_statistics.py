from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from ..models import (
	Match,
	MatchParticipant,
	MatchResult,
	MatchSkillLevel,
	MatchStatus,
	MatchTeam,
	MatchTeamAssignment,
	ParticipantStatus,
	PlayerRating,
)
from ..services.player_statistics import (
	calculate_player_skill_level,
	calculate_player_statistics,
	rounded_average_rating,
)
from ..team_services import get_player_average_rating


User = get_user_model()


class PlayerStatisticsTests(TestCase):
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
		self.rating_batch = 0

	def create_match(self, *, status=MatchStatus.CLOSED, result=MatchResult.DRAW):
		match = Match.objects.create(
			organizer=self.organizer,
			title='Completed match',
			date_time=timezone.now() + timedelta(days=1),
			location='Local field',
			skill_level='beginner',
			max_players=6,
			status=status,
			result=result,
		)
		Match.objects.filter(pk=match.pk).update(
			date_time=timezone.now() - timedelta(days=1),
		)
		match.refresh_from_db()
		return match

	def assign_player(self, match, *, status=ParticipantStatus.CONFIRMED, team=MatchTeam.A):
		participant = MatchParticipant.objects.create(
			match=match,
			player=self.player,
			status=status,
		)
		if status == ParticipantStatus.CONFIRMED:
			MatchTeamAssignment.objects.create(
				match=match,
				participant=participant,
				team=team,
			)
		return participant

	def create_ratings(self, stars):
		batch = self.rating_batch
		self.rating_batch += 1
		match = self.create_match()
		self.assign_player(match)
		raters = [
			User.objects.create_user(
				username=f'rater_{batch}_{index}',
				email=f'rater_{batch}_{index}@example.com',
				password='testpass123',
			)
			for index in range(len(stars))
		]
		PlayerRating.objects.bulk_create(
			[
				PlayerRating(
					match=match,
					rater=rater,
					player=self.player,
					stars=value,
				)
				for rater, value in zip(raters, stars)
			]
		)

	def test_player_without_matches_has_zero_stats_and_no_rating(self):
		statistics = calculate_player_statistics(self.player)

		self.assertEqual(statistics.matches_played, 0)
		self.assertEqual(statistics.matches_won, 0)
		self.assertEqual(statistics.matches_drawn, 0)
		self.assertEqual(statistics.matches_lost, 0)
		self.assertIsNone(statistics.average_rating)
		self.assertEqual(statistics.rating_count, 0)

	def test_counts_wins_draws_and_losses(self):
		won = self.create_match(result=MatchResult.TEAM_A)
		self.assign_player(won, team=MatchTeam.A)
		drawn = self.create_match(result=MatchResult.DRAW)
		self.assign_player(drawn, team=MatchTeam.B)
		lost = self.create_match(result=MatchResult.TEAM_B)
		self.assign_player(lost, team=MatchTeam.A)

		statistics = calculate_player_statistics(self.player)

		self.assertEqual(statistics.matches_played, 3)
		self.assertEqual(statistics.matches_won, 1)
		self.assertEqual(statistics.matches_drawn, 1)
		self.assertEqual(statistics.matches_lost, 1)
		self.assertEqual(
			statistics.matches_played,
			statistics.matches_won
			+ statistics.matches_drawn
			+ statistics.matches_lost,
		)

	def test_excludes_cancelled_matches(self):
		match = self.create_match(status=MatchStatus.CANCELLED, result=MatchResult.TEAM_A)
		self.assign_player(match)

		self.assertEqual(calculate_player_statistics(self.player).matches_played, 0)

	def test_excludes_matches_player_left_before_teams_were_generated(self):
		match = self.create_match()
		self.assign_player(match, status=ParticipantStatus.LEFT)

		self.assertEqual(calculate_player_statistics(self.player).matches_played, 0)

	def test_excludes_matches_without_registered_result(self):
		match = self.create_match(result='')
		self.assign_player(match)

		self.assertEqual(calculate_player_statistics(self.player).matches_played, 0)

	def test_averages_all_received_ratings_not_match_averages(self):
		first_match = self.create_match()
		self.assign_player(first_match)
		second_match = self.create_match()
		self.assign_player(second_match)
		raters = [
			User.objects.create_user(
				username=f'rater{index}',
				email=f'rater{index}@example.com',
				password='testpass123',
			)
			for index in range(4)
		]
		PlayerRating.objects.bulk_create(
			[
				PlayerRating(match=first_match, rater=raters[0], player=self.player, stars=5),
				PlayerRating(match=first_match, rater=raters[1], player=self.player, stars=5),
				PlayerRating(match=second_match, rater=raters[2], player=self.player, stars=1),
				PlayerRating(match=second_match, rater=raters[3], player=self.player, stars=1),
			]
		)

		statistics = calculate_player_statistics(self.player)

		self.assertEqual(statistics.average_rating, Decimal('3'))
		self.assertEqual(statistics.rating_count, 4)

	def test_player_with_no_ratings_has_no_average(self):
		match = self.create_match()
		self.assign_player(match)

		statistics = calculate_player_statistics(self.player)

		self.assertIsNone(statistics.average_rating)
		self.assertEqual(statistics.rating_count, 0)

	def test_zero_one_and_two_ratings_are_beginner(self):
		for stars in [[], [5], [5, 5]]:
			with self.subTest(stars=stars):
				PlayerRating.objects.all().delete()
				if stars:
					self.create_ratings(stars)
				self.assertEqual(
					calculate_player_skill_level(self.player),
					MatchSkillLevel.BEGINNER,
				)

	def test_three_ratings_use_skill_level_boundaries(self):
		for stars, expected in [
			([3, 3, 3], MatchSkillLevel.BEGINNER),
			([3] * 9 + [4], MatchSkillLevel.INTERMEDIATE),
			([4, 4, 4], MatchSkillLevel.INTERMEDIATE),
			([4] * 9 + [5], MatchSkillLevel.ADVANCED),
			([5, 5, 5], MatchSkillLevel.ADVANCED),
			([1, 1, 1], MatchSkillLevel.BEGINNER),
		]:
			with self.subTest(stars=stars):
				PlayerRating.objects.all().delete()
				self.create_ratings(stars)
				self.assertEqual(calculate_player_skill_level(self.player), expected)

	def test_average_3_04_is_displayed_as_3_0_and_is_beginner(self):
		self.create_ratings([3] * 24 + [4])

		statistics = calculate_player_statistics(self.player)

		self.assertEqual(rounded_average_rating(statistics), Decimal('3.0'))
		self.assertEqual(
			calculate_player_skill_level(self.player),
			MatchSkillLevel.BEGINNER,
		)

	def test_fr24_rating_uses_real_average_and_neutral_default(self):
		self.assertEqual(get_player_average_rating(self.player), 3.0)

		self.create_ratings([5, 3, 4])

		self.assertEqual(get_player_average_rating(self.player), 4.0)
