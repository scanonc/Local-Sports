"""Demo data for the Sprint Review (a "seeder", like in Laravel).

    python manage.py seed_demo            # local machine (DEBUG on)
    python manage.py seed_demo --force    # server (DEBUG off)

WARNING: the command DELETES ALL THE DATA of the database (``flush``) and
fills it again with the same demo data every time. That includes superusers:
create one again with ``createsuperuser`` if you need the admin panel.

Nothing here sends emails: everything is created directly with the ORM.
"""
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test import RequestFactory
from django.utils import timezone

from matches.context_processors import pending_match_result
from matches.models import (
	Invitation,
	JoinRequest,
	JoinRequestStatus,
	Match,
	MatchMessage,
	MatchParticipant,
	MatchResult,
	MatchSkillLevel,
	MatchStatus,
	MatchTeam,
	MatchTeamAssignment,
	MatchVisibility,
	ParticipantStatus,
	PlayerRating,
)
from matches.services.player_statistics import (
	calculate_player_skill_level,
	calculate_player_statistics,
	player_meets_match_skill_level,
)
from matches.team_services import distribute_match_teams
from users.models import FavoritePlayer, Notification, Report, ReportReason

User = get_user_model()

DEFAULT_PASSWORD = 'prueba123'
PLAYERS = range(1, 11)

# Average stars that each player receives in the history matches (thresholds in
# matches/services/player_statistics.py: <= 3.0 Beginner, <= 4.0 Intermediate,
# > 4.0 Advanced, and fewer than 3 ratings is always Beginner). player10 gets none.
RATING_TARGETS = {1: 4.8, 2: 4.6, 3: 4.4, 4: 3.8, 5: 3.6, 6: 3.4, 7: 3.2, 8: 2.6, 9: 2.0}
EXPECTED_LEVEL = {
	**{n: MatchSkillLevel.ADVANCED for n in (1, 2, 3)},
	**{n: MatchSkillLevel.INTERMEDIATE for n in (4, 5, 6, 7)},
	**{n: MatchSkillLevel.BEGINNER for n in (8, 9, 10)},
}

# Past matches: players of team A (the other players are team B) and the result.
# Different teams and results make the profile statistics differ.
HISTORY = [
	# key, days ago, title, location, level, team A, result
	('A1', 30, 'DEMO historial y estadísticas 1 (FR13, FR23)', 'Cancha sintética EAFIT',
	 MatchSkillLevel.INTERMEDIATE, {1, 3, 5, 7, 9}, MatchResult.TEAM_A),
	('A2', 22, 'DEMO historial y estadísticas 2 (FR13, FR23)', 'Cancha UPB, Laureles',
	 MatchSkillLevel.BEGINNER, {1, 2, 4, 6, 8}, MatchResult.TEAM_A),
	('A3', 15, 'DEMO historial y estadísticas 3 (FR13, FR23)', 'Unidad Deportiva de Belén',
	 MatchSkillLevel.INTERMEDIATE, {1, 3, 6, 9, 10}, MatchResult.TEAM_A),
	('A4', 8, 'DEMO historial y estadísticas 4 (FR13, FR23)', 'Cancha sintética El Poblado',
	 MatchSkillLevel.BEGINNER, {2, 5, 7, 9, 10}, MatchResult.DRAW),
	('A5', 3, 'DEMO historial y estadísticas 5 (FR13, FR23)', 'Cancha sintética EAFIT',
	 MatchSkillLevel.INTERMEDIATE, {2, 4, 5, 8, 9}, MatchResult.TEAM_B),
]
LIVE_RATING_TEAM_A = {1, 2, 5, 6, 9}  # scenario I: ended yesterday, result team A


def local_at(moment, hour):
	return timezone.localtime(moment).replace(hour=hour, minute=0, second=0, microsecond=0)


class Command(BaseCommand):
	help = 'DELETE ALL DATA and load the demo data of the Sprint Review.'

	def add_arguments(self, parser):
		parser.add_argument(
			'--force', action='store_true',
			help='Required when DEBUG is False (for example on the AWS server).',
		)
		parser.add_argument(
			'--password', default=DEFAULT_PASSWORD,
			help=f'Password of the demo users (default: {DEFAULT_PASSWORD}).',
		)

	def handle(self, *args, **options):
		if not settings.DEBUG and not options['force']:
			raise CommandError(
				'This command deletes ALL the data of the database and DEBUG is False. '
				'Run it again with --force if you are sure.'
			)

		self.now = timezone.now()
		self.password_hash = make_password(options['password'])
		self.password = options['password']
		self.scenarios = []  # (letter, match, requirement)

		# One transaction for everything: if something fails, the flush is undone too.
		with transaction.atomic():
			call_command('flush', interactive=False, verbosity=0)
			self.create_users()
			self.create_history()
			self.create_live_rating_match()
			self.create_pending_result_match()
			self.create_ready_for_teams_match()
			self.create_full_match_with_waiting_list()
			self.create_approval_match()
			self.create_open_match()
			self.create_advanced_match()
			self.create_cancelled_match()
			self.create_calendar_match()
			self.create_extras()
			checks = self.verify()

		self.print_report(checks)

	# ------------------------------------------------------------------ users

	def create_users(self):
		self.organizer = User.objects.create(
			username='organizer', email='organizer@gmail.com', password=self.password_hash,
		)
		self.p = {}
		for n in PLAYERS:
			# No first/last name: the application then shows the username (player1, ...).
			self.p[n] = User.objects.create(
				username=f'player{n}', email=f'Player{n}@gmail.com', password=self.password_hash,
			)
		self.number = {user.pk: n for n, user in self.p.items()}

	# ---------------------------------------------------------------- helpers

	def new_match(self, title, date_time, *, location, skill_level=MatchSkillLevel.BEGINNER,
	              max_players=10, visibility=MatchVisibility.PUBLIC, status=MatchStatus.ACTIVE,
	              result='', invite_token=None):
		"""Create a match. Match.save() validates the date, so a past match is created
		with a future placeholder date and moved to the past with QuerySet.update()."""
		is_past = date_time < self.now
		match = Match.objects.create(
			organizer=self.organizer, title=title, location=location, skill_level=skill_level,
			max_players=max_players, visibility=visibility, status=status, result=result,
			invite_token=invite_token, invite_active=True,
			date_time=self.now + timedelta(days=1) if is_past else date_time,
		)
		if is_past:
			changes = {'date_time': date_time}
			if result:
				changes['result_registered_at'] = date_time + timedelta(hours=2)
			Match.objects.filter(pk=match.pk).update(**changes)
			match.refresh_from_db()
		return match

	@staticmethod
	def join(match, numbers, players, *, status=ParticipantStatus.CONFIRMED, attended=False):
		return [
			MatchParticipant.objects.create(
				match=match, player=players[n], status=status, attendance_confirmed=attended,
			)
			for n in numbers
		]

	def assign_teams(self, match, participants, team_a_numbers):
		MatchTeamAssignment.objects.bulk_create([
			MatchTeamAssignment(
				match=match, participant=participant,
				team=MatchTeam.A if self.number[participant.player_id] in team_a_numbers else MatchTeam.B,
			)
			for participant in participants
		])

	def say(self, match, author, content, minutes_ago):
		message = MatchMessage.objects.create(match=match, author=author, content=content)
		MatchMessage.objects.filter(pk=message.pk).update(
			created_at=self.now - timedelta(minutes=minutes_ago),
		)

	def finished_match(self, title, date_time, *, location, skill_level, team_a, result):
		match = self.new_match(
			title, date_time, location=location, skill_level=skill_level,
			status=MatchStatus.CLOSED, result=result,
		)
		participants = self.join(match, PLAYERS, self.p, attended=True)
		self.assign_teams(match, participants, team_a)
		return match

	# --------------------------------------------------------------- scenarios

	def create_history(self):
		"""A) Five past matches with teams, results and ratings."""
		history = []
		for key, days, title, location, level, team_a, result in HISTORY:
			match = self.finished_match(
				title, local_at(self.now - timedelta(days=days), 19),
				location=location, skill_level=level, team_a=team_a, result=result,
			)
			history.append(match)
			self.scenarios.append((key, match, 'Historial y estadísticas del perfil (FR13, FR23)'))
		self.create_ratings(history)

	def create_ratings(self, matches):
		"""Ratings whose averages give the levels of EXPECTED_LEVEL (nobody rates player10)."""
		counters = {n: 0 for n in RATING_TARGETS}
		rows = []
		for match in matches:
			for rated, target in RATING_TARGETS.items():
				for rater in PLAYERS:
					if rater == rated:
						continue
					k = counters[rated]
					# Whole stars whose running average is `target`.
					stars = int(target * (k + 1) + 0.5) - int(target * k + 0.5)
					counters[rated] += 1
					rows.append(PlayerRating(
						match=match, rater=self.p[rater], player=self.p[rated], stars=stars,
					))
		PlayerRating.objects.bulk_create(rows)

	def create_live_rating_match(self):
		"""I) Ended yesterday, result registered, no ratings: rate live as player1 or player2."""
		match = self.finished_match(
			'DEMO calificar jugadores (FR21)', local_at(self.now - timedelta(days=1), 20),
			location='Cancha La 70, Laureles', skill_level=MatchSkillLevel.BEGINNER,
			team_a=LIVE_RATING_TEAM_A, result=MatchResult.TEAM_A,
		)
		self.live_match = match
		self.scenarios.append(('I', match, 'Calificar jugadores en vivo (FR21)'))

	def create_pending_result_match(self):
		"""B) Started a few hours ago, teams generated, no result: the organizer sees the pop-up."""
		match = self.new_match(
			'DEMO resultado pendiente (FR20)', self.now + timedelta(days=1), location='Cancha sintética EAFIT',
			skill_level=MatchSkillLevel.INTERMEDIATE,
		)
		self.join(match, PLAYERS, self.p, attended=True)
		# Teams from the real service (pattern A, B, B, A, A, B, B, A by average rating),
		# generated while the match is still in the future, as in the application.
		distribute_match_teams(match)
		Match.objects.filter(pk=match.pk).update(date_time=self.now - timedelta(hours=3))
		match.refresh_from_db()
		self.say(match, self.organizer, 'Equipos listos, nos vemos en la cancha.', 200)
		self.say(match, self.p[3], 'Voy llegando, guarden puesto.', 190)
		self.pending_match = match
		self.scenarios.append(('B', match, 'Pop-up de resultado pendiente (FR20)'))

	def create_ready_for_teams_match(self):
		"""C) Active, in two days, exactly 10 confirmed, no teams yet: generate teams live."""
		match = self.new_match(
			'DEMO generar equipos (FR24)', local_at(self.now + timedelta(days=2), 18),
			location='Cancha sintética El Poblado', max_players=10,
		)
		participants = self.join(match, PLAYERS, self.p)
		for participant in participants[:6]:
			MatchParticipant.objects.filter(pk=participant.pk).update(attendance_confirmed=True)
		self.ready_match = match
		self.scenarios.append(('C', match, 'Generar equipos balanceados (FR24), asistencia (FR7)'))

	def create_full_match_with_waiting_list(self):
		"""D) Full match (6/6) with two players on the waiting list."""
		match = self.new_match(
			'DEMO lista de espera (FR10, FR11)', local_at(self.now + timedelta(days=3), 17),
			location='Unidad Deportiva de Belén', max_players=6,
		)
		self.join(match, range(1, 7), self.p)
		self.join(match, (7, 8), self.p, status=ParticipantStatus.WAITING)
		self.full_match = match
		self.scenarios.append(('D', match, 'Lista de espera y reemplazo automático (FR10, FR11)'))

	def create_approval_match(self):
		"""E) Approval required, two pending requests."""
		match = self.new_match(
			'DEMO aprobar solicitudes (FR4)', local_at(self.now + timedelta(days=2), 20),
			location='Cancha UdeA', visibility=MatchVisibility.APPROVAL_REQUIRED,
		)
		self.join(match, (4, 5), self.p)
		for n in (8, 9):
			JoinRequest.objects.create(match=match, player=self.p[n], request_status=JoinRequestStatus.PENDING)
		self.scenarios.append(('E', match, 'Aprobar o rechazar solicitudes (FR4)'))

	def create_open_match(self):
		"""F) Open match to join, with chat and a shareable link."""
		match = self.new_match(
			'DEMO unirse y chat (FR5, FR16, FR22)', local_at(self.now + timedelta(days=5), 10),
			location='Parque Lineal La Presidenta', max_players=10,
			invite_token=uuid.uuid5(uuid.NAMESPACE_URL, 'local-sports-demo-open-match'),
		)
		self.join(match, (2, 3, 4, 5), self.p)
		self.say(match, self.organizer, '¡Bienvenidos! Faltan 6 jugadores, inviten a sus amigos.', 300)
		self.say(match, self.p[2], 'Yo llevo los petos.', 240)
		self.say(match, self.p[3], '¿Se puede llegar en bus hasta la cancha?', 180)
		self.say(match, self.organizer, 'Sí, la ruta de Laureles pasa a dos cuadras.', 150)
		self.say(match, self.p[4], 'Perfecto, ahí nos vemos.', 90)
		self.say(match, self.p[5], 'Confirmo asistencia.', 30)
		self.open_match = match
		self.scenarios.append(('F', match, 'Unirse (FR5), chat (FR22), enlace de invitación (FR16)'))

	def create_advanced_match(self):
		"""G) Advanced level: players of a lower level cannot join."""
		match = self.new_match(
			'DEMO nivel requerido (FR23.1)', local_at(self.now + timedelta(days=4), 19),
			location='Estadio Atanasio Girardot', skill_level=MatchSkillLevel.ADVANCED,
		)
		self.join(match, (1, 2, 3), self.p)
		self.advanced_match = match
		self.scenarios.append(('G', match, 'Nivel requerido (FR23.1): player8 o player9 no pueden unirse'))

	def create_cancelled_match(self):
		"""H) Cancelled match with participants and a read-only chat."""
		match = self.new_match(
			'DEMO partido cancelado (FR9)', local_at(self.now + timedelta(days=3), 16),
			location='Cancha sintética EAFIT', status=MatchStatus.CANCELLED,
		)
		self.join(match, (1, 3, 5, 6, 7), self.p)
		self.say(match, self.p[5], '¿Sigue en pie con esta lluvia?', 600)
		self.say(match, self.organizer, 'Lo cancelo: la cancha está inundada.', 560)
		self.say(match, self.p[1], 'Entendido, avisen cuando lo reprogramen.', 520)
		self.cancelled_match = match
		self.scenarios.append(('H', match, 'Cancelación y chat de solo lectura (FR9, FR22)'))

	def create_calendar_match(self):
		"""J) Upcoming match where player1 is confirmed: Add to Google Calendar."""
		match = self.new_match(
			'DEMO agregar a calendario (FR19)', local_at(self.now + timedelta(days=4), 8),
			location='Cancha sintética EAFIT', max_players=10,
		)
		self.join(match, (1, 4, 6, 7), self.p)
		self.calendar_match = match
		self.scenarios.append(('J', match, 'Agregar a Google Calendar (FR19)'))

	# ----------------------------------------------------------------- extras

	def create_extras(self):
		for user, favorite in ((1, 2), (1, 3), (2, 1)):
			FavoritePlayer.objects.create(user=self.p[user], favorite=self.p[favorite])
		Report.objects.create(
			reporter=self.p[3], reported_user=self.p[9], reason=ReportReason.NO_SHOW,
			details='No se presentó al partido del viernes y no avisó a nadie.',
		)
		for match in (self.open_match, self.calendar_match):
			Invitation.objects.create(match=match, organizer=self.organizer, player=self.p[10])
			Notification.objects.create(
				user=self.p[10], match=match,
				message=f'You have been invited by {self.organizer} to the match "{match.title}".',
			)
		Notification.objects.create(
			user=self.p[1], match=self.calendar_match,
			message=f"The match '{self.calendar_match.title}' has been updated.",
		)
		Notification.objects.create(
			user=self.p[1], match=self.cancelled_match,
			message=f"The match '{self.cancelled_match.title}' has been cancelled.",
		)
		Notification.objects.create(
			user=self.p[1], match=self.advanced_match,
			message=f"The match '{self.advanced_match.title}' has been updated.",
		)

	# ----------------------------------------------------------- verification

	def verify(self):
		"""Check the demo against the real rules of the code. Any failure undoes everything."""
		checks = []

		def check(label, condition):
			checks.append((label, bool(condition)))
			if not condition:
				raise CommandError(f'Verification failed: {label}')

		request = RequestFactory().get('/')
		request.user = self.organizer
		check('B: the organizer gets the pending result pop-up (FR20)',
		      pending_match_result(request)['pending_result_match'] == self.pending_match)
		check('B: result empty, closed, teams generated, already started',
		      self.pending_match.awaiting_result and self.pending_match.has_generated_teams)
		check('C: FR24 conditions (active, future, 10 confirmed, no teams)',
		      self.ready_match.status == MatchStatus.ACTIVE and not self.ready_match.has_started
		      and self.ready_match.confirmed_participants_count == 10
		      and not self.ready_match.has_generated_teams)
		check('D: full with 2 waiting',
		      self.full_match.is_full and self.full_match.waiting_list_count == 2)
		check('F: invite link active', self.open_match.invite_token and self.open_match.invite_active)
		check('I: no ratings in the live rating match',
		      not PlayerRating.objects.filter(match=self.live_match).exists())
		check('player10 has no ratings', not PlayerRating.objects.filter(player=self.p[10]).exists())
		for n in PLAYERS:
			check(f'player{n} level is {EXPECTED_LEVEL[n].label}',
			      calculate_player_skill_level(self.p[n]) == EXPECTED_LEVEL[n])
		check('G: player1 can join the advanced match, player8 cannot',
		      player_meets_match_skill_level(self.p[1], self.advanced_match)
		      and not player_meets_match_skill_level(self.p[8], self.advanced_match))
		return checks

	# ----------------------------------------------------------------- output

	def table(self, headers, rows):
		widths = [max(len(str(row[i])) for row in [headers] + rows) for i in range(len(headers))]
		line = '  '.join(str(h).ljust(w) for h, w in zip(headers, widths))
		self.stdout.write(line)
		self.stdout.write('  '.join('-' * w for w in widths))
		for row in rows:
			self.stdout.write('  '.join(str(c).ljust(w) for c, w in zip(row, widths)))

	def print_report(self, checks):
		out = self.stdout.write
		out(self.style.SUCCESS('\nDemo data loaded (the database was flushed first).'))

		out(self.style.MIGRATE_HEADING('\n1. Users'))
		users = [self.organizer] + [self.p[n] for n in PLAYERS]
		self.table(('username', 'email', 'password'), [(u.username, u.email, self.password) for u in users])
		out('There is no superuser: run "python manage.py createsuperuser" if you need /admin/.')

		out(self.style.MIGRATE_HEADING('\n2. Scenarios'))
		rows = []
		for key, match, requirement in self.scenarios:
			rows.append((key, match.pk, match.title, timezone.localtime(match.date_time).strftime('%Y-%m-%d %H:%M'),
			             match.get_status_display(), requirement))
		self.table(('', 'id', 'title', 'date (Colombia)', 'status', 'demonstrates'), rows)

		out(self.style.MIGRATE_HEADING('\n3. Player levels (calculated with the real rules)'))
		rows = []
		for n in PLAYERS:
			stats = calculate_player_statistics(self.p[n])
			average = f'{stats.average_rating:.1f}' if stats.average_rating is not None else '-'
			rows.append((
				f'player{n}', calculate_player_skill_level(self.p[n]).label, average, stats.rating_count,
				f'{stats.matches_played}/{stats.matches_won}/{stats.matches_drawn}/{stats.matches_lost}',
			))
		self.table(('player', 'level', 'avg stars', 'ratings', 'played/won/drawn/lost'), rows)

		out(self.style.MIGRATE_HEADING('\n4. Who logs in for each requirement'))
		guide = [
			('organizer', 'Pop-up de resultado pendiente (FR20): partido B "%s"' % self.pending_match.title),
			('organizer', 'Generate teams (FR24): partido C "%s" (id %s)' % (self.ready_match.title, self.ready_match.pk)),
			('organizer', 'Aprobar solicitudes de player8 y player9 (FR4): partido E; compartir enlace (FR16): partido F'),
			('player1 o player2', 'Calificar jugadores en vivo (FR21): partido I "%s"' % self.live_match.title),
			('player1', 'Agregar a Google Calendar (FR19): partido J; perfil con nivel Advanced y favoritos (FR17, FR23)'),
			('player10', 'Unirse a un partido abierto (FR5), aceptar las 2 invitaciones pendientes (FR15), perfil sin calificaciones'),
			('player8 o player9', 'Intentar unirse al partido G (Advanced): no pueden (FR23.1); player9 tiene un reporte (FR18)'),
			('player6', 'Salir del partido D con lista de espera: entra player7 (FR10, FR11)'),
			('cualquiera de H', 'Ver el chat de solo lectura del partido cancelado (FR9, FR22)'),
		]
		self.table(('log in as', 'to show'), guide)

		out(self.style.MIGRATE_HEADING('\n5. Verifications'))
		for label, _passed in checks:
			out(f'  OK  {label}')
