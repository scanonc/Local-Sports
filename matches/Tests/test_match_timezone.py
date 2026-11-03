from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase

from ..forms import MatchForm
from ..sprint4_services import google_calendar_url


class MatchLocalTimeTests(TestCase):
    def form(self, value):
        return MatchForm(data={
            'title': 'Evening football', 'date_time': value,
            'location': 'Bogota', 'skill_level': 'beginner',
            'max_players': 6, 'visibility': 'public',
        })

    @patch('matches.models.timezone.now', return_value=datetime(2026, 11, 3, 22, 20, tzinfo=dt_timezone.utc))
    def test_five_minutes_ahead_in_colombia_is_valid(self, mocked_now):
        form = self.form('2026-11-03T17:25')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['date_time'].astimezone(dt_timezone.utc),
                         datetime(2026, 11, 3, 22, 25, tzinfo=dt_timezone.utc))
        self.assertIn('20261103T222500Z', google_calendar_url(form.instance))

    @patch('matches.models.timezone.now', return_value=datetime(2026, 11, 3, 22, 20, tzinfo=dt_timezone.utc))
    def test_past_colombia_time_still_rejected(self, mocked_now):
        form = self.form('2026-11-03T17:19')
        self.assertFalse(form.is_valid())
        self.assertIn('date_time', form.errors)
