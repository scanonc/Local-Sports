from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import Match, MatchTeam, MatchTeamAssignment, ParticipantStatus
from .team_services import (
	TEAM_PATTERN,
	TeamDistributionError,
	distribute_match_teams,
)


User = get_user_model()


class TeamDistributionServiceTests(TestCase):
	def setUp(self):
		self.organizer = User.objects.create_user(
			username='organizer',
			email='organizer@example.com',
			password='testpass123',
		)
		self.match = Match.objects.create(
			organizer=self.organizer,
			title='Sunday Match',
			date_time=timezone.now() + timedelta(days=1),
			location='Local field',
			skill_level='beginner',
			max_players=40,
			visibility='public',
		)

	def add_participants(self, count):
		participants = []
		for index in range(count):
			player = User.objects.create_user(
				username=f'player_{index}',
				email=f'player_{index}@example.com',
				password='testpass123',
			)
			participants.append(
				self.match.participants.create(
					player=player,
					status=ParticipantStatus.CONFIRMED,
				)
			)
		return participants

	def test_distributes_supported_participant_counts(self):
		for count in [6, 8, 10, 40]:
			with self.subTest(count=count):
				match = Match.objects.create(
					organizer=self.organizer,
					title=f'Match {count}',
					date_time=timezone.now() + timedelta(days=1),
					location='Local field',
					skill_level='beginner',
					max_players=count,
					visibility='public',
				)
				for index in range(count):
					player = User.objects.create_user(
						username=f'count_{count}_{index}',
						email=f'count_{count}_{index}@example.com',
						password='testpass123',
					)
					match.participants.create(player=player)

				assignments = distribute_match_teams(match)

				self.assertEqual(len(assignments), count)
				self.assertEqual(
					MatchTeamAssignment.objects.filter(
						match=match,
						team=MatchTeam.A,
					).count(),
					count // 2,
				)
				self.assertEqual(
					MatchTeamAssignment.objects.filter(
						match=match,
						team=MatchTeam.B,
					).count(),
					count // 2,
				)

	def test_orders_by_rating_before_applying_snake_pattern(self):
		participants = self.add_participants(6)
		ratings = {
			participants[0].player_id: 2.0,
			participants[1].player_id: 5.0,
			participants[2].player_id: 3.0,
			participants[3].player_id: 4.0,
			participants[4].player_id: 1.0,
			participants[5].player_id: 4.5,
		}

		with patch(
			'matches.team_services.get_player_average_rating',
			side_effect=lambda player: ratings[player.pk],
		):
			assignments = distribute_match_teams(self.match)

		ordered_player_ids = [
			assignment.participant.player_id
			for assignment in assignments
		]
		expected_order = [
			participants[1].player_id,
			participants[5].player_id,
			participants[3].player_id,
			participants[2].player_id,
			participants[0].player_id,
			participants[4].player_id,
		]
		self.assertEqual(ordered_player_ids, expected_order)

	def test_equal_ratings_use_registration_order_and_pattern(self):
		participants = self.add_participants(8)

		distribute_match_teams(self.match)

		assignments = MatchTeamAssignment.objects.filter(
			match=self.match
		).select_related('participant').order_by('participant__joined_at')
		self.assertEqual(
			[assignment.team for assignment in assignments],
			[TEAM_PATTERN[index % len(TEAM_PATTERN)] for index in range(8)],
		)
		self.assertEqual(
			[
				assignment.participant.player_id
				for assignment in assignments
			],
			[participant.player_id for participant in participants],
		)

	def test_waiting_participants_are_not_assigned(self):
		self.add_participants(6)
		waiting_player = User.objects.create_user(
			username='waiting',
			email='waiting@example.com',
			password='testpass123',
		)
		self.match.participants.create(
			player=waiting_player,
			status=ParticipantStatus.WAITING,
		)

		distribute_match_teams(self.match)

		self.assertFalse(
			MatchTeamAssignment.objects.filter(
				participant__player=waiting_player
			).exists()
		)

	def test_rejects_odd_or_small_participant_counts(self):
		for count in [4, 5]:
			with self.subTest(count=count):
				match = Match.objects.create(
					organizer=self.organizer,
					title=f'Invalid match {count}',
					date_time=timezone.now() + timedelta(days=1),
					location='Local field',
					skill_level='beginner',
					max_players=6,
					visibility='public',
				)
				for index in range(count):
					player = User.objects.create_user(
						username=f'invalid_{count}_{index}',
						email=f'invalid_{count}_{index}@example.com',
						password='testpass123',
					)
					match.participants.create(player=player)

				with self.assertRaises(TeamDistributionError):
					distribute_match_teams(match)
