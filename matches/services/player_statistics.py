from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Avg, Count, Q

from ..models import (
	MatchResult,
	MatchSkillLevel,
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


def player_meets_match_skill_level(player, match):
	"""Return whether a player's calculated level permits joining a match."""
	level_order = {
		MatchSkillLevel.BEGINNER: 0,
		MatchSkillLevel.INTERMEDIATE: 1,
		MatchSkillLevel.ADVANCED: 2,
	}
	return level_order[calculate_player_skill_level(player)] >= level_order[match.skill_level]


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
	average_rating = rating_stats['average_rating']
	if average_rating is not None:
		average_rating = Decimal(str(average_rating))

	return PlayerStatistics(
		matches_played=match_stats['matches_played'] or 0,
		matches_won=match_stats['matches_won'] or 0,
		matches_drawn=match_stats['matches_drawn'] or 0,
		matches_lost=match_stats['matches_lost'] or 0,
		average_rating=average_rating,
		rating_count=rating_stats['rating_count'] or 0,
	)


def rounded_average_rating(statistics):
	"""Return the displayed one-decimal average used for skill decisions."""
	if statistics.average_rating is None:
		return None

	average = Decimal(str(statistics.average_rating))
	return average.quantize(
		Decimal('0.1'),
		rounding=ROUND_HALF_UP,
	)


def calculate_player_skill_level(player):
	"""Calculate a player's skill level from their received ratings."""
	statistics = calculate_player_statistics(player)
	if statistics.rating_count < 3:
		return MatchSkillLevel.BEGINNER

	average = rounded_average_rating(statistics)
	if average <= Decimal('3.0'):
		return MatchSkillLevel.BEGINNER
	if average <= Decimal('4.0'):
		return MatchSkillLevel.INTERMEDIATE
	return MatchSkillLevel.ADVANCED
