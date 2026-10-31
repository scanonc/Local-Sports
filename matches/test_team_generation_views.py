from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
	JoinRequest,
	Match,
	MatchParticipant,
	MatchStatus,
	MatchTeamAssignment,
	ParticipantStatus,
)


User = get_user_model()


class MatchTeamGenerationViewTests(TestCase):
	def setUp(self):
		self.organizer = User.objects.create_user(
			username='organizer',
			email='organizer@example.com',
			password='testpass123',
		)
		self.other_user = User.objects.create_user(
			username='other',
			email='other@example.com',
			password='testpass123',
		)
		self.match = Match.objects.create(
			organizer=self.organizer,
			title='Sunday Match',
			date_time=timezone.now() + timedelta(days=1),
			location='Local field',
			skill_level='beginner',
			max_players=6,
			visibility='public',
		)
		for index in range(6):
			player = User.objects.create_user(
				username=f'player_{index}',
				email=f'player_{index}@example.com',
				password='testpass123',
			)
			self.match.participants.create(player=player)

	def post_generation(self, user, **data):
		self.client.force_login(user)
		return self.client.post(
			reverse('matches:match_generate_teams', kwargs={'pk': self.match.pk}),
			data=data,
		)

	def test_only_organizer_can_generate_teams(self):
		response = self.post_generation(self.other_user, confirm='yes')

		self.assertEqual(response.status_code, 302)
		self.assertEqual(MatchTeamAssignment.objects.count(), 0)
		self.match.refresh_from_db()
		self.assertEqual(self.match.status, MatchStatus.ACTIVE)

	def test_generation_requires_confirmation(self):
		response = self.post_generation(self.organizer)

		self.assertEqual(response.status_code, 302)
		self.assertEqual(MatchTeamAssignment.objects.count(), 0)
		self.match.refresh_from_db()
		self.assertEqual(self.match.status, MatchStatus.ACTIVE)

	def test_confirmed_generation_assigns_players_and_closes_match(self):
		response = self.post_generation(self.organizer, confirm='yes')

		self.assertEqual(response.status_code, 302)
		self.assertEqual(
			MatchTeamAssignment.objects.filter(match=self.match).count(),
			6,
		)
		self.match.refresh_from_db()
		self.assertEqual(self.match.status, MatchStatus.CLOSED)

	def test_generation_rejects_invalid_participant_counts(self):
		for count in [4, 5]:
			with self.subTest(count=count):
				match = Match.objects.create(
					organizer=self.organizer,
					title=f'Invalid {count}',
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

				self.client.force_login(self.organizer)
				response = self.client.post(
					reverse(
						'matches:match_generate_teams',
						kwargs={'pk': match.pk},
					),
					data={'confirm': 'yes'},
				)

				self.assertEqual(response.status_code, 302)
				self.assertFalse(
					MatchTeamAssignment.objects.filter(match=match).exists()
				)

	def test_generation_rejects_started_match(self):
		Match.objects.filter(pk=self.match.pk).update(
			date_time=timezone.now() - timedelta(hours=1)
		)

		response = self.post_generation(self.organizer, confirm='yes')

		self.assertEqual(response.status_code, 302)
		self.assertFalse(
			MatchTeamAssignment.objects.filter(match=self.match).exists()
		)

	def test_generation_rejects_match_with_existing_teams(self):
		participant = self.match.participants.first()
		MatchTeamAssignment.objects.create(
			match=self.match,
			participant=participant,
			team='A',
		)

		response = self.post_generation(self.organizer, confirm='yes')

		self.assertEqual(response.status_code, 302)
		self.assertEqual(
			MatchTeamAssignment.objects.filter(match=self.match).count(),
			1,
		)
		self.match.refresh_from_db()
		self.assertEqual(self.match.status, MatchStatus.ACTIVE)

	def test_closed_match_rejects_public_join_and_approval_request(self):
		self.match.status = MatchStatus.CLOSED
		self.match.save(update_fields=['status', 'updated_at'])

		self.client.force_login(self.other_user)
		join_response = self.client.post(
			reverse('matches:match_join', kwargs={'pk': self.match.pk})
		)
		request_response = self.client.post(
			reverse('matches:match_request_join', kwargs={'pk': self.match.pk})
		)

		self.assertEqual(join_response.status_code, 302)
		self.assertEqual(request_response.status_code, 302)
		self.assertFalse(
			MatchParticipant.objects.filter(
				match=self.match,
				player=self.other_user,
			).exists()
		)
		self.assertFalse(
			JoinRequest.objects.filter(
				match=self.match,
				player=self.other_user,
			).exists()
		)

	def test_closed_match_cannot_be_edited(self):
		self.match.status = MatchStatus.CLOSED
		self.match.save(update_fields=['status', 'updated_at'])
		self.client.force_login(self.organizer)

		response = self.client.get(
			reverse('matches:match_update', kwargs={'pk': self.match.pk})
		)

		self.assertEqual(response.status_code, 302)
		self.assertEqual(
			response.url,
			reverse('matches:match_detail', kwargs={'pk': self.match.pk}),
		)

	def test_leaving_confirmed_participant_undoes_teams_and_reopens_match(self):
		self.client.force_login(self.organizer)
		self.client.post(
			reverse('matches:match_generate_teams', kwargs={'pk': self.match.pk}),
			data={'confirm': 'yes'},
		)
		participant = self.match.participants.first()
		self.client.force_login(participant.player)

		response = self.client.post(
			reverse('matches:match_leave', kwargs={'pk': self.match.pk})
		)

		self.assertEqual(response.status_code, 302)
		self.match.refresh_from_db()
		self.assertEqual(self.match.status, MatchStatus.ACTIVE)
		self.assertFalse(
			MatchTeamAssignment.objects.filter(match=self.match).exists()
		)
		participant.refresh_from_db()
		self.assertEqual(participant.status, ParticipantStatus.LEFT)

	def test_leaving_without_teams_keeps_match_open(self):
		participant = self.match.participants.first()
		self.client.force_login(participant.player)

		response = self.client.post(
			reverse('matches:match_leave', kwargs={'pk': self.match.pk})
		)

		self.assertEqual(response.status_code, 302)
		self.match.refresh_from_db()
		self.assertEqual(self.match.status, MatchStatus.ACTIVE)
		self.assertFalse(self.match.has_generated_teams)

	def test_leaving_with_teams_promotes_waiting_player_after_reopening(self):
		waiting_player = User.objects.create_user(
			username='waiting',
			email='waiting@example.com',
			password='testpass123',
		)
		MatchParticipant.objects.create(
			match=self.match,
			player=waiting_player,
			status=ParticipantStatus.WAITING,
		)
		self.client.force_login(self.organizer)
		self.client.post(
			reverse('matches:match_generate_teams', kwargs={'pk': self.match.pk}),
			data={'confirm': 'yes'},
		)
		participant = self.match.participants.filter(
			status=ParticipantStatus.CONFIRMED
		).first()
		self.client.force_login(participant.player)

		self.client.post(
			reverse('matches:match_leave', kwargs={'pk': self.match.pk})
		)

		waiting_player_participant = MatchParticipant.objects.get(
			match=self.match,
			player=waiting_player,
		)
		self.assertEqual(
			waiting_player_participant.status,
			ParticipantStatus.CONFIRMED,
		)
		self.match.refresh_from_db()
		self.assertEqual(self.match.status, MatchStatus.ACTIVE)
		self.client.force_login(self.organizer)
		response = self.client.post(
			reverse('matches:match_generate_teams', kwargs={'pk': self.match.pk}),
			data={'confirm': 'yes'},
		)
		self.assertEqual(response.status_code, 302)
		self.match.refresh_from_db()
		self.assertEqual(self.match.status, MatchStatus.CLOSED)
