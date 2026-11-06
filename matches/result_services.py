from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import Match, MatchResult, MatchStatus


class MatchResultError(ValueError):
	"""Raised when a match result cannot be registered."""


def register_match_result(match, result):
	"""FR20 - Persist the result of a completed match.

	A match is "completed" once its start time has passed. The result can
	only be registered for matches whose teams were generated (FR24), and
	only once: a registered result is final.
	"""
	if result not in MatchResult.values:
		raise MatchResultError(_('Select Team A, Team B or a draw.'))

	with transaction.atomic():
		locked = Match.objects.select_for_update().get(pk=match.pk)

		if locked.status == MatchStatus.CANCELLED:
			raise MatchResultError(_('Cancelled matches cannot have a result.'))

		if locked.status != MatchStatus.CLOSED or not locked.has_generated_teams:
			raise MatchResultError(
				_('Teams must be generated before the result can be registered.')
			)

		if not locked.has_started:
			raise MatchResultError(
				_('The result can only be registered once the match has started.')
			)

		if locked.has_result:
			raise MatchResultError(
				_('The result of this match has already been registered.')
			)

		locked.result = result
		locked.result_registered_at = timezone.now()
		locked.save(update_fields=['result', 'result_registered_at', 'updated_at'])

	return locked
