from django.db import transaction

from .models import (
	Match,
	MatchStatus,
	MatchTeam,
	MatchTeamAssignment,
	ParticipantStatus,
)


TEAM_PATTERN = (
	MatchTeam.A,
	MatchTeam.B,
	MatchTeam.B,
	MatchTeam.A,
)


class TeamDistributionError(ValueError):
	"""Raised when a match cannot be distributed into two teams."""


def get_player_average_rating(player):
	"""Return the player's average rating until FR21 provides real ratings."""
	return 3.0


def distribute_match_teams(match):
	"""Persist two teams for the confirmed participants of a match."""
	with transaction.atomic():
		participants = list(
			match.participants.filter(
				status=ParticipantStatus.CONFIRMED,
			).select_related('player').order_by('joined_at', 'pk')
		)

		if len(participants) < 6 or len(participants) % 2:
			raise TeamDistributionError(
				'Team distribution requires an even number of at least 6 participants.'
			)

		if MatchTeamAssignment.objects.filter(match=match).exists():
			raise TeamDistributionError(
				'Teams have already been generated for this match.'
			)

		participants.sort(
			key=lambda participant: (
				-get_player_average_rating(participant.player),
				participant.joined_at,
				participant.pk,
			)
		)

		assignments = [
			MatchTeamAssignment(
				match=match,
				participant=participant,
				team=TEAM_PATTERN[index % len(TEAM_PATTERN)],
			)
			for index, participant in enumerate(participants)
		]
		MatchTeamAssignment.objects.bulk_create(assignments)
		match.status = MatchStatus.CLOSED
		match.save(update_fields=['status', 'updated_at'])

	return assignments
