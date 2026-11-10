"""Seed demo data for the Sprint Review (like a Laravel seeder).

    python manage.py seed_demo             # create the demo users and matches
    python manage.py seed_demo --reset     # delete the demo data and create it again
    python manage.py seed_demo --clear     # delete the demo data only

Only the demo data is touched: the users ``organizer`` and ``player1`` ..
``player10`` and the matches whose title starts with ``[Demo]``. Any other
user (for example a superuser) or match is left alone.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from matches.models import (
	Invitation,
	JoinRequest,
	Match,
	MatchMessage,
	MatchParticipant,
	MatchResult,
	MatchSkillLevel,
	MatchTeamAssignment,
	MatchVisibility,
	ParticipantStatus,
	PlayerRating,
)
from matches.result_services import register_match_result
from matches.team_services import distribute_match_teams
from users.models import FavoritePlayer, Notification

User = get_user_model()

DEFAULT_PASSWORD = 'prueba123'
ORGANIZER_USERNAME = 'organizer'
PLAYER_COUNT = 10
DEMO_PREFIX = '[Demo] '

# Stars that player1..player6 receive in the finished match. Every other
# participant gives the same stars to a player, so the average is exact:
# 5.0 and 5.0 -> Advanced, 4.0 and 4.0 -> Intermediate, 3.0 and 2.0 -> Beginner.
RATING_BY_PLAYER = {1: 5, 2: 5, 3: 4, 4: 4, 5: 3, 6: 2}


def demo_usernames():
	return [ORGANIZER_USERNAME] + [f'player{n}' for n in range(1, PLAYER_COUNT + 1)]


def _next_hour(moment):
	return (moment + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)


class Command(BaseCommand):
	help = 'Create (or remove) demo users and matches for the Sprint Review.'

	def add_arguments(self, parser):
		parser.add_argument(
			'--reset', action='store_true',
			help='Delete the demo data and create it again.',
		)
		parser.add_argument(
			'--clear', action='store_true',
			help='Delete the demo data and stop (use it after the demo).',
		)
		parser.add_argument(
			'--password', default=DEFAULT_PASSWORD,
			help=f'Password of the demo users (default: {DEFAULT_PASSWORD}).',
		)

	def handle(self, *args, **options):
		if options['reset'] or options['clear']:
			self.clear_demo_data()
			if options['clear']:
				return

		with transaction.atomic():
			users = self.create_users(options['password'])
			self.create_matches(users)

		self.stdout.write(self.style.SUCCESS(
			'Demo data ready. Log in as organizer or player1 .. player10 '
			f"(password: {options['password']})."
		))

	# ------------------------------------------------------------------ users

	def create_users(self, password):
		users = {}
		for username in demo_usernames():
			user, created = User.objects.get_or_create(
				username=username,
				defaults={'email': f'{username}@example.com'},
			)
			# Always set the password, so the demo logins work even if the
			# command is run again.
			user.set_password(password)
			user.save(update_fields=['password'])
			users[username] = user
			self.stdout.write(f"  user {username}: {'created' if created else 'updated'}")
		return users

	# ---------------------------------------------------------------- matches

	def create_matches(self, users):
		organizer = users[ORGANIZER_USERNAME]
		players = {n: users[f'player{n}'] for n in range(1, PLAYER_COUNT + 1)}
		now = timezone.now()

		self.finished_match(organizer, players, now)
		self.started_match(organizer, players, now)
		self.open_match(organizer, players, now)
		self.private_match(organizer, players, now)
		self.advanced_match(organizer, players, now)
		self.create_favorites(players)

	def _new_match(self, organizer, title, *, days_ahead, skill_level=MatchSkillLevel.BEGINNER,
	               visibility=MatchVisibility.PUBLIC, location='EAFIT', max_players=6):
		"""Create a match, or return None when it already exists."""
		title = DEMO_PREFIX + title
		if Match.objects.filter(organizer=organizer, title=title).exists():
			self.stdout.write(f'  match "{title}": already exists, skipped')
			return None
		# Match.save() validates the date, so every match starts in the future
		# and the past ones are moved back later (see _move_to_past).
		date_time = _next_hour(timezone.now() + timedelta(days=days_ahead))
		match = Match.objects.create(
			organizer=organizer, title=title, date_time=date_time, location=location,
			skill_level=skill_level, max_players=max_players, visibility=visibility,
		)
		self.stdout.write(f'  match "{title}": created')
		return match

	@staticmethod
	def _move_to_past(match, moment):
		# QuerySet.update() skips Match.save(), which refuses past dates.
		Match.objects.filter(pk=match.pk).update(date_time=moment)
		match.refresh_from_db()

	@staticmethod
	def _join(match, player, *, status=ParticipantStatus.CONFIRMED, attended=False):
		return MatchParticipant.objects.create(
			match=match, player=player, status=status, attendance_confirmed=attended,
		)

	def finished_match(self, organizer, players, now):
		"""A past match with teams, result and ratings: profiles get statistics."""
		match = self._new_match(organizer, 'Finished match (result and ratings)', days_ahead=1,
		                        location='UPB')
		if match is None:
			return
		for n in range(1, 7):
			self._join(match, players[n], attended=True)
		distribute_match_teams(match)
		self._move_to_past(match, now - timedelta(days=3))
		register_match_result(match, MatchResult.TEAM_A)
		for rated_n, stars in RATING_BY_PLAYER.items():
			for rater_n in range(1, 7):
				if rater_n != rated_n:
					PlayerRating.objects.create(
						match=match, rater=players[rater_n], player=players[rated_n], stars=stars,
					)
		MatchMessage.objects.create(match=match, author=players[1], content='Good game, everyone!')

	def started_match(self, organizer, players, now):
		"""A match that already started, with teams and no result yet.

		The organizer is asked for the result (FR20) as soon as they log in.
		Teams use the ratings of the finished match (FR24).
		"""
		match = self._new_match(organizer, 'Started match (register the result)', days_ahead=1,
		                        location='EAFIT')
		if match is None:
			return
		for n in range(1, 7):
			self._join(match, players[n], attended=True)
		distribute_match_teams(match)
		self._move_to_past(match, now - timedelta(hours=1))
		MatchMessage.objects.create(match=match, author=organizer, content='Teams are ready, see you on the field.')
		MatchMessage.objects.create(match=match, author=players[2], content='On my way!')
		MatchMessage.objects.create(match=match, author=players[4], content='Who brings the balls?')

	def open_match(self, organizer, players, now):
		"""A public match with one free spot: join, waiting list and replacement."""
		match = self._new_match(organizer, 'Open match (join and waiting list)', days_ahead=1,
		                        location='Parque Lleras')
		if match is None:
			return
		for n in range(1, 6):
			self._join(match, players[n])
		# player9 has a pending invitation (FR15).
		Invitation.objects.create(match=match, organizer=organizer, player=players[9])
		Notification.objects.create(
			user=players[9], match=match,
			message=f'You have been invited by {organizer} to the match "{match.title}".',
		)

	def private_match(self, organizer, players, now):
		"""A match that needs approval, with one pending request (FR4)."""
		match = self._new_match(organizer, 'Private match (approval required)', days_ahead=2,
		                        visibility=MatchVisibility.APPROVAL_REQUIRED, location='UdeA')
		if match is None:
			return
		JoinRequest.objects.create(match=match, player=players[8])

	def advanced_match(self, organizer, players, now):
		"""An Advanced match: only players with an Advanced level can join (FR23.1)."""
		match = self._new_match(organizer, 'Advanced match (level required)', days_ahead=3,
		                        skill_level=MatchSkillLevel.ADVANCED, location='Atanasio Girardot')
		if match is None:
			return
		self._join(match, players[1])
		self._join(match, players[2])

	@staticmethod
	def create_favorites(players):
		for favorite in (2, 3):
			FavoritePlayer.objects.get_or_create(user=players[1], favorite=players[favorite])

	# ------------------------------------------------------------------ clear

	def clear_demo_data(self):
		"""Delete only the demo matches and the demo users (and what they own)."""
		demo_users = User.objects.filter(username__in=demo_usernames())
		matches = Match.objects.filter(organizer__in=demo_users, title__startswith=DEMO_PREFIX)
		match_count = matches.count()
		matches.delete()
		user_count = demo_users.count()
		# Deleting a user also deletes what that user created or joined.
		demo_users.delete()
		self.stdout.write(f'Removed {match_count} demo matches and {user_count} demo users.')
