from django.utils import timezone

from .models import Match, MatchStatus


def pending_match_result(request):
	"""FR20 - Expose the oldest completed match still awaiting its result.

	Only the organizer of the match is asked; the template shows a pop-up
	that cannot be dismissed until the result is registered.
	"""
	user = getattr(request, 'user', None)

	if user is None or not user.is_authenticated:
		return {'pending_result_match': None}

	match = (
		Match.objects.filter(
			organizer=user,
			status=MatchStatus.CLOSED,
			result='',
			date_time__lt=timezone.now(),
		)
		.order_by('date_time')
		.first()
	)

	return {'pending_result_match': match}
