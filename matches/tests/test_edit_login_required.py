from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import Match


User = get_user_model()


class MatchEditLoginRequiredTests(TestCase):
	"""Regression: opening /matches/<id>/edit/ while logged out crashed with
	TypeError "Field 'id' expected a number but got AnonymousUser", because
	MatchUpdateView.dispatch() loaded the match before the login check ran.
	"""

	def setUp(self):
		self.organizer = User.objects.create_user(
			username='organizer',
			email='organizer@example.com',
			password='testpass123',
		)
		self.other = User.objects.create_user(
			username='other',
			email='other@example.com',
			password='testpass123',
		)
		self.match = Match.objects.create(
			organizer=self.organizer,
			title='Editable match',
			date_time=timezone.now() + timedelta(days=2),
			location='Central Stadium',
			skill_level='beginner',
			max_players=10,
			visibility='public',
		)
		self.url = reverse('matches:match_update', kwargs={'pk': self.match.pk})

	def test_anonymous_user_is_redirected_to_login(self):
		response = self.client.get(self.url)

		self.assertEqual(response.status_code, 302)
		self.assertIn(reverse('users:login'), response['Location'])
		self.assertIn(f'next={self.url}', response['Location'])

	def test_anonymous_post_is_redirected_to_login(self):
		response = self.client.post(self.url, data={'title': 'Hacked'})

		self.assertEqual(response.status_code, 302)
		self.assertIn(reverse('users:login'), response['Location'])
		self.match.refresh_from_db()
		self.assertEqual(self.match.title, 'Editable match')

	def test_organizer_can_still_open_the_edit_form(self):
		self.client.force_login(self.organizer)
		response = self.client.get(self.url)
		self.assertEqual(response.status_code, 200)

	def test_other_user_still_gets_404(self):
		self.client.force_login(self.other)
		response = self.client.get(self.url)
		self.assertEqual(response.status_code, 404)
