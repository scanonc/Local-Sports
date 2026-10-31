from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import MatchForm
from .models import Match, MatchStatus
from .services import generate_match_invite_token


User = get_user_model()


class PastMatchSaveTests(TestCase):
	"""A match whose date already passed must still be saveable.

	Regression: cancelling an old match crashed with
	ValidationError {'date_time': ['Match date and time cannot be in the past.']}
	because Match.save() runs full_clean() and clean() rejected any past date.
	"""

	def setUp(self):
		self.organizer = User.objects.create_user(
			username='organizer', email='org@example.com', password='testpass123'
		)
		self.match = Match.objects.create(
			organizer=self.organizer,
			title='Old match',
			date_time=timezone.now() + timedelta(days=2),
			location='Central Stadium',
			skill_level='intermediate',
			max_players=10,
			visibility='public',
		)
		# The match was valid when created; time passes.
		Match.objects.filter(pk=self.match.pk).update(
			date_time=timezone.now() - timedelta(days=3)
		)
		self.match.refresh_from_db()

	# --- the bug itself -------------------------------------------------

	def test_organizer_can_cancel_a_past_match(self):
		self.client.login(username='organizer', password='testpass123')

		response = self.client.post(
			reverse('matches:match_cancel', kwargs={'pk': self.match.pk})
		)

		self.assertEqual(response.status_code, 302)
		self.match.refresh_from_db()
		self.assertEqual(self.match.status, MatchStatus.CANCELLED)

	def test_can_save_status_change_on_past_match(self):
		self.match.status = MatchStatus.CANCELLED
		self.match.save(update_fields=['status', 'updated_at'])

		self.match.refresh_from_db()
		self.assertEqual(self.match.status, MatchStatus.CANCELLED)

	def test_can_generate_invite_token_on_past_match(self):
		generate_match_invite_token(self.match)

		self.match.refresh_from_db()
		self.assertIsNotNone(self.match.invite_token)

	# --- the rule must still protect against real mistakes --------------

	def test_cannot_create_match_in_the_past(self):
		with self.assertRaises(ValidationError) as ctx:
			Match.objects.create(
				organizer=self.organizer,
				title='Time travel',
				date_time=timezone.now() - timedelta(hours=1),
				location='Nowhere',
				skill_level='beginner',
				max_players=6,
			)
		self.assertIn('date_time', ctx.exception.message_dict)

	def test_cannot_move_future_match_into_the_past(self):
		future = Match.objects.create(
			organizer=self.organizer,
			title='Future match',
			date_time=timezone.now() + timedelta(days=1),
			location='Central Stadium',
			skill_level='beginner',
			max_players=6,
		)
		future.date_time = timezone.now() - timedelta(hours=2)

		with self.assertRaises(ValidationError) as ctx:
			future.save()
		self.assertIn('date_time', ctx.exception.message_dict)

	def test_cannot_move_past_match_to_another_past_date(self):
		self.match.date_time = timezone.now() - timedelta(days=1)

		with self.assertRaises(ValidationError) as ctx:
			self.match.save()
		self.assertIn('date_time', ctx.exception.message_dict)

	def test_can_reschedule_past_match_to_the_future(self):
		self.match.date_time = timezone.now() + timedelta(days=5)
		self.match.save()

		self.match.refresh_from_db()
		self.assertGreater(self.match.date_time, timezone.now())

	def test_other_rules_still_apply_to_past_match(self):
		self.match.max_players = 1

		with self.assertRaises(ValidationError) as ctx:
			self.match.save()
		self.assertIn('max_players', ctx.exception.message_dict)
		self.assertNotIn('date_time', ctx.exception.message_dict)

	# --- edit form ------------------------------------------------------

	def test_form_rejects_new_past_date(self):
		form = MatchForm(
			data={
				'title': 'Old match',
				'date_time': (timezone.localtime() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
				'location': 'Central Stadium',
				'skill_level': 'intermediate',
				'max_players': 10,
				'visibility': 'public',
			},
			instance=self.match,
		)
		self.assertFalse(form.is_valid())
		self.assertIn('date_time', form.errors)

	def test_form_accepts_unchanged_past_date_with_minute_precision(self):
		"""The datetime-local input drops seconds; that alone is not a 'change'."""
		stored = timezone.localtime(self.match.date_time)
		form = MatchForm(
			data={
				'title': 'Old match (renamed)',
				'date_time': stored.strftime('%Y-%m-%dT%H:%M'),
				'location': 'Central Stadium',
				'skill_level': 'intermediate',
				'max_players': 10,
				'visibility': 'public',
			},
			instance=self.match,
		)
		self.assertTrue(form.is_valid(), form.errors)
