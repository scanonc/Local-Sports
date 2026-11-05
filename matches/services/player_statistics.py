from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Avg, Count, Q

from ..models import (
	MatchResult,
	MatchStatus,
	MatchTeam,
	MatchTeamAssignment,
	ParticipantStatus,
	PlayerRating,
)


@dataclass(frozen=True)
class PlayerStatistics:
	matches_played: int
	matches_won: int
	matches_drawn: int
	matches_lost: int
	average_rating: Decimal | None
	rating_count: int


def calculate_player_statistics(player):
	"""Calculate match results and all ratings received by a player."""
	match_stats = MatchTeamAssignment.objects.filter(
		participant__player=player,
		participant__status=ParticipantStatus.CONFIRMED,
		match__status=MatchStatus.CLOSED,
		match__result__in=MatchResult.values,
	).aggregate(
		matches_played=Count('pk'),
		matches_won=Count(
			'pk',
			filter=Q(
				team=MatchTeam.A,
				match__result=MatchResult.TEAM_A,
			)
			| Q(
				team=MatchTeam.B,
				match__result=MatchResult.TEAM_B,
			),
		),
		matches_drawn=Count(
			'pk',
			filter=Q(match__result=MatchResult.DRAW),
		),
		matches_lost=Count(
			'pk',
			filter=Q(
				team=MatchTeam.A,
				match__result=MatchResult.TEAM_B,
			)
			| Q(
				team=MatchTeam.B,
				match__result=MatchResult.TEAM_A,
			),
		),
	)
	rating_stats = PlayerRating.objects.filter(player=player).aggregate(
		average_rating=Avg('stars'),
		rating_count=Count('pk'),
	)

	return PlayerStatistics(
		matches_played=match_stats['matches_played'] or 0,
		matches_won=match_stats['matches_won'] or 0,
		matches_drawn=match_stats['matches_drawn'] or 0,
		matches_lost=match_stats['matches_lost'] or 0,
		average_rating=rating_stats['average_rating'],
		rating_count=rating_stats['rating_count'] or 0,
	)
