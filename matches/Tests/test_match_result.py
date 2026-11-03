from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import (
	Match,
	MatchParticipant,
	MatchResult,
	MatchStatus,
	MatchTeamAssignment,
	ParticipantStatus,
)
from ..result_services import MatchResultError, register_match_result
from ..team_services import distribute_match_teams


User = get_user_model()


class MatchResultTestCase(TestCase):
	"""Shared fixtures: an organizer, six players and helpers to build matches."""

	def setUp(self):
		self.organizer = User.objects.create_user(
			username='organizer',
			email='organizer@example.com',
			password='testpass123',
		)
		self.player = User.objects.create_user(
			username='player_0',
			email='player_0@example.com',
			password='testpass123',
		)
		self.match = self.make_match(title='Finished match')

	def make_match(self, title, finished=True, with_teams=True):
		"""Build a 6-player match; optionally with teams, optionally in the past."""
		match = Match.objects.create(
			organizer=self.organizer,
			title=title,
			date_time=timezone.now() + timedelta(days=1),
			location='Local field',
			skill_level='beginner',
			max_players=6,
			visibility='public',
		)
		for index in range(6):
			if index == 0:
				player = self.player
			else:
				player, _ = User.objects.get_or_create(
					username=f'extra_{index}',
					defaults={'email': f'extra_{index}@example.com'},
				)
			MatchParticipant.objects.create(match=match, player=player)

		if with_teams:
			distribute_match_teams(match)

		if finished:
			# The match was valid when created; time simply passes.
			Match.objects.filter(pk=match.pk).update(
				date_time=timezone.now() - timedelta(hours=3)
			)

		match.refresh_from_db()
		return match

	def post_result(self, user, match=None, follow=False, **data):
		self.client.force_login(user)
		match = match or self.match
		return self.client.post(
			reverse('matches:match_result', kwargs={'pk': match.pk}),
			data=data,
			follow=follow,
		)


class MatchResultModelTests(MatchResultTestCase):
	def test_new_match_has_no_result(self):
		self.assertEqual(self.match.result, '')
		self.assertIsNone(self.match.result_registered_at)
		self.assertFalse(self.match.has_result)

	def test_finished_closed_match_is_awaiting_result(self):
		self.assertTrue(self.match.awaiting_result)

	def test_future_match_is_not_awaiting_result(self):
		future = self.make_match('Future match', finished=False)
		self.assertFalse(future.awaiting_result)

	def test_match_without_teams_is_not_awaiting_result(self):
		no_teams = self.make_match('No teams', with_teams=False)
		self.assertFalse(no_teams.awaiting_result)

	def test_cancelled_match_is_not_awaiting_result(self):
		Match.objects.filter(pk=self.match.pk).update(status=MatchStatus.CANCELLED)
		self.match.refresh_from_db()
		self.assertFalse(self.match.awaiting_result)


class RegisterMatchResultServiceTests(MatchResultTestCase):
	def test_registers_each_valid_result(self):
		for value in MatchResult.values:
			with self.subTest(result=value):
				match = self.make_match(f'Match {value}')
				register_match_result(match, value)

				match.refresh_from_db()
				self.assertEqual(match.result, value)
				self.assertIsNotNone(match.result_registered_at)
				self.assertTrue(match.has_result)
				self.assertFalse(match.awaiting_result)

	def test_rejects_invalid_result(self):
		for value in ('', 'team_c', 'TEAM_A', None):
			with self.subTest(result=value):
				with self.assertRaises(MatchResultError):
					register_match_result(self.match, value)

		self.match.refresh_from_db()
		self.assertEqual(self.match.result, '')

	def test_rejects_match_without_teams(self):
		no_teams = self.make_match('No teams', with_teams=False)

		with self.assertRaises(MatchResultError):
			register_match_result(no_teams, MatchResult.DRAW)

		no_teams.refresh_from_db()
		self.assertEqual(no_teams.result, '')

	def test_rejects_match_that_has_not_started(self):
		future = self.make_match('Future match', finished=False)

		with self.assertRaises(MatchResultError):
			register_match_result(future, MatchResult.TEAM_A)

		future.refresh_from_db()
		self.assertEqual(future.result, '')

	def test_rejects_cancelled_match(self):
		Match.objects.filter(pk=self.match.pk).update(status=MatchStatus.CANCELLED)

		with self.assertRaises(MatchResultError):
			register_match_result(self.match, MatchResult.TEAM_A)

	def test_result_is_final(self):
		register_match_result(self.match, MatchResult.TEAM_A)

		with self.assertRaises(MatchResultError):
			register_match_result(self.match, MatchResult.TEAM_B)

		self.match.refresh_from_db()
		self.assertEqual(self.match.result, MatchResult.TEAM_A)


class MatchResultViewTests(MatchResultTestCase):
	def test_organizer_can_register_result(self):
		response = self.post_result(self.organizer, result='team_b')

		self.assertRedirects(
			response,
			reverse('matches:match_detail', kwargs={'pk': self.match.pk}),
		)
		self.match.refresh_from_db()
		self.assertEqual(self.match.result, MatchResult.TEAM_B)

	def test_success_message_is_shown(self):
		response = self.post_result(self.organizer, follow=True, result='draw')
		self.assertContains(response, 'Match result registered.')

	def test_only_organizer_can_register_result(self):
		response = self.post_result(self.player, result='team_a')

		self.assertEqual(response.status_code, 302)
		self.match.refresh_from_db()
		self.assertEqual(self.match.result, '')

	def test_anonymous_user_is_sent_to_login(self):
		response = self.client.post(
			reverse('matches:match_result', kwargs={'pk': self.match.pk}),
			data={'result': 'team_a'},
		)

		self.assertEqual(response.status_code, 302)
		self.assertIn('login', response['Location'])
		self.match.refresh_from_db()
		self.assertEqual(self.match.result, '')

	def test_invalid_choice_is_rejected_with_message(self):
		response = self.post_result(self.organizer, follow=True, result='nobody')

		self.assertContains(response, 'Select Team A, Team B or a draw.')
		self.match.refresh_from_db()
		self.assertEqual(self.match.result, '')

	def test_missing_choice_is_rejected(self):
		self.post_result(self.organizer)
		self.match.refresh_from_db()
		self.assertEqual(self.match.result, '')

	def test_cannot_overwrite_registered_result(self):
		self.post_result(self.organizer, result='team_a')
		response = self.post_result(self.organizer, follow=True, result='team_b')

		self.assertContains(response, 'already been registered')
		self.match.refresh_from_db()
		self.assertEqual(self.match.result, MatchResult.TEAM_A)

	def test_get_is_not_allowed(self):
		self.client.force_login(self.organizer)
		response = self.client.get(
			reverse('matches:match_result', kwargs={'pk': self.match.pk})
		)
		self.assertEqual(response.status_code, 405)


class MatchResultModalTests(MatchResultTestCase):
	MODAL_ID = 'id="match-result-modal"'

	def test_organizer_sees_modal_on_any_page(self):
		self.client.force_login(self.organizer)

		for url in (reverse('matches:match_list'), reverse('home')):
			with self.subTest(url=url):
				response = self.client.get(url)
				self.assertContains(response, self.MODAL_ID)
				self.assertContains(response, 'Finished match')

	def test_modal_has_no_close_button(self):
		self.client.force_login(self.organizer)
		response = self.client.get(reverse('matches:match_list'))

		self.assertNotContains(response, 'btn-close')
		self.assertNotContains(response, 'data-bs-dismiss')

	def test_modal_offers_both_teams_and_a_draw(self):
		self.client.force_login(self.organizer)
		response = self.client.get(reverse('matches:match_list'))

		for value in ('team_a', 'team_b', 'draw'):
			self.assertContains(response, f'value="{value}"')

	def test_participant_does_not_see_modal(self):
		self.client.force_login(self.player)
		response = self.client.get(reverse('matches:match_list'))
		self.assertNotContains(response, self.MODAL_ID)

	def test_anonymous_user_does_not_see_modal(self):
		response = self.client.get(reverse('matches:match_list'))
		self.assertNotContains(response, self.MODAL_ID)

	def test_modal_disappears_once_result_is_registered(self):
		register_match_result(self.match, MatchResult.DRAW)

		self.client.force_login(self.organizer)
		response = self.client.get(reverse('matches:match_list'))
		self.assertNotContains(response, self.MODAL_ID)

	def test_modal_not_shown_for_future_match(self):
		Match.objects.filter(pk=self.match.pk).update(
			date_time=timezone.now() + timedelta(days=1)
		)

		self.client.force_login(self.organizer)
		response = self.client.get(reverse('matches:match_list'))
		self.assertNotContains(response, self.MODAL_ID)

	def test_modal_not_shown_for_finished_match_without_teams(self):
		Match.objects.filter(pk=self.match.pk).update(status=MatchStatus.CANCELLED)
		self.make_match('Active without teams', with_teams=False)

		self.client.force_login(self.organizer)
		response = self.client.get(reverse('matches:match_list'))
		self.assertNotContains(response, self.MODAL_ID)

	def test_oldest_pending_match_is_asked_first(self):
		newer = self.make_match('Newer finished match')
		Match.objects.filter(pk=self.match.pk).update(
			date_time=timezone.now() - timedelta(days=5)
		)
		Match.objects.filter(pk=newer.pk).update(
			date_time=timezone.now() - timedelta(days=1)
		)

		self.client.force_login(self.organizer)
		response = self.client.get(reverse('matches:match_list'))
		self.assertContains(response, reverse('matches:match_result', kwargs={'pk': self.match.pk}))
		self.assertNotContains(response, reverse('matches:match_result', kwargs={'pk': newer.pk}))

		register_match_result(self.match, MatchResult.TEAM_A)
		response = self.client.get(reverse('matches:match_list'))
		self.assertContains(response, reverse('matches:match_result', kwargs={'pk': newer.pk}))


class MatchResultDetailPageTests(MatchResultTestCase):
	def test_detail_shows_result_label(self):
		cases = {
			MatchResult.TEAM_A: 'Team A won',
			MatchResult.TEAM_B: 'Team B won',
			MatchResult.DRAW: 'Draw',
		}

		for value, label in cases.items():
			with self.subTest(result=value):
				match = self.make_match(f'Detail {value}')
				register_match_result(match, value)

				self.client.force_login(self.player)
				response = self.client.get(
					reverse('matches:match_detail', kwargs={'pk': match.pk})
				)
				self.assertContains(response, label)

	def test_detail_shows_pending_before_result(self):
		self.client.force_login(self.player)
		response = self.client.get(
			reverse('matches:match_detail', kwargs={'pk': self.match.pk})
		)
		self.assertContains(response, 'Pending')


class LeavingStartedMatchTests(MatchResultTestCase):
	def test_participant_cannot_leave_after_match_started(self):
		"""Leaving deletes the teams (FR24); that must not happen once the match is over."""
		self.client.force_login(self.player)
		response = self.client.post(
			reverse('matches:match_leave', kwargs={'pk': self.match.pk}),
			follow=True,
		)

		self.assertContains(response, 'already started')
		self.match.refresh_from_db()
		self.assertEqual(self.match.status, MatchStatus.CLOSED)
		self.assertEqual(MatchTeamAssignment.objects.filter(match=self.match).count(), 6)
		self.assertTrue(
			MatchParticipant.objects.filter(
				match=self.match,
				player=self.player,
				status=ParticipantStatus.CONFIRMED,
			).exists()
		)
