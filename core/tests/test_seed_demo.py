from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from core.management.commands.seed_demo import DEFAULT_PASSWORD, demo_usernames
from matches.context_processors import pending_match_result
from matches.models import (
	Invitation,
	JoinRequest,
	Match,
	MatchMessage,
	MatchParticipant,
	MatchResult,
	MatchSkillLevel,
	MatchStatus,
	MatchTeam,
	MatchTeamAssignment,
	ParticipantStatus,
	PlayerRating,
)
from matches.services.player_statistics import (
	calculate_player_skill_level,
	calculate_player_statistics,
	player_meets_match_skill_level,
)
from users.models import FavoritePlayer, Notification

User = get_user_model()


FAST_HASHER = ['django.contrib.auth.hashers.MD5PasswordHasher']  # keeps the tests fast


def seed(*args, **kwargs):
	call_command('seed_demo', *args, stdout=StringIO(), **kwargs)


@override_settings(PASSWORD_HASHERS=FAST_HASHER)
class SeedDemoUsersTests(TestCase):
	def test_creates_the_organizer_and_ten_players_with_the_password(self):
		seed()
		expected = ['organizer'] + [f'player{n}' for n in range(1, 11)]
		self.assertEqual(sorted(demo_usernames()), sorted(expected))
		for username in expected:
			user = User.objects.get(username=username)
			self.assertTrue(user.check_password('prueba123'), username)
			self.assertFalse(user.is_staff)
		self.assertEqual(DEFAULT_PASSWORD, 'prueba123')

	def test_the_demo_users_can_log_in(self):
		seed()
		self.assertTrue(self.client.login(username='player1', password='prueba123'))
		self.assertTrue(self.client.login(username='organizer', password='prueba123'))

	def test_password_can_be_changed_with_an_option(self):
		seed(password='another-password-1')
		self.assertTrue(User.objects.get(username='player3').check_password('another-password-1'))
		self.assertFalse(User.objects.get(username='player3').check_password('prueba123'))

	def test_running_twice_does_not_duplicate_anything(self):
		seed()
		counts = (
			User.objects.count(),
			Match.objects.count(),
			MatchParticipant.objects.count(),
			PlayerRating.objects.count(),
			MatchMessage.objects.count(),
			FavoritePlayer.objects.count(),
		)
		seed()
		self.assertEqual(
			counts,
			(
				User.objects.count(),
				Match.objects.count(),
				MatchParticipant.objects.count(),
				PlayerRating.objects.count(),
				MatchMessage.objects.count(),
				FavoritePlayer.objects.count(),
			),
		)
		self.assertEqual(User.objects.count(), 11)
		self.assertEqual(Match.objects.count(), 5)


@override_settings(PASSWORD_HASHERS=FAST_HASHER)
class SeedDemoExistingDataTests(TestCase):
	"""The superuser and the data created by hand must never be touched."""

	def setUp(self):
		self.superuser = User.objects.create_superuser('super', 'super@example.com', 'super-pass-1')
		self.person = User.objects.create_user('ismael', 'ismael@example.com', 'ismael-pass-1')
		self.match = Match.objects.create(
			organizer=self.person, title='Idioma',
			date_time=timezone.now() + timedelta(days=1), location='UPB',
			skill_level=MatchSkillLevel.BEGINNER, max_players=14,
		)

	def assert_untouched(self):
		self.superuser.refresh_from_db()
		self.person.refresh_from_db()
		self.assertTrue(self.superuser.is_superuser)
		self.assertTrue(self.superuser.check_password('super-pass-1'))
		self.assertTrue(self.person.check_password('ismael-pass-1'))
		self.assertTrue(Match.objects.filter(pk=self.match.pk, title='Idioma').exists())

	def test_seeding_keeps_existing_users_and_matches(self):
		seed()
		self.assert_untouched()

	def test_clear_removes_only_the_demo_data(self):
		seed()
		seed(clear=True)
		self.assert_untouched()
		self.assertFalse(User.objects.filter(username__in=demo_usernames()).exists())
		self.assertFalse(Match.objects.filter(title__startswith='[Demo]').exists())
		self.assertEqual(User.objects.count(), 2)
		self.assertEqual(Match.objects.count(), 1)

	def test_reset_recreates_the_demo_data_and_keeps_the_rest(self):
		seed()
		Match.objects.filter(title__startswith='[Demo] Open').delete()
		seed(reset=True)
		self.assert_untouched()
		self.assertEqual(Match.objects.filter(title__startswith='[Demo]').count(), 5)
		self.assertEqual(User.objects.count(), 13)

	def test_clear_also_removes_what_demo_players_did_in_other_matches(self):
		seed()
		player = User.objects.get(username='player7')
		MatchParticipant.objects.create(match=self.match, player=player)
		seed(clear=True)
		self.assertTrue(Match.objects.filter(pk=self.match.pk).exists())
		self.assertFalse(MatchParticipant.objects.filter(match=self.match).exists())

	def test_clear_without_demo_data_is_harmless(self):
		seed(clear=True)
		self.assert_untouched()


@override_settings(PASSWORD_HASHERS=FAST_HASHER)
class SeedDemoScenarioTests(TestCase):
	@classmethod
	def setUpTestData(cls):
		seed()
		cls.organizer = User.objects.get(username='organizer')
		cls.players = {n: User.objects.get(username=f'player{n}') for n in range(1, 11)}

	def match(self, fragment):
		return Match.objects.get(title__startswith='[Demo] ' + fragment)

	def test_finished_match_has_teams_result_and_ratings(self):
		match = self.match('Finished')
		self.assertTrue(match.has_started)
		self.assertEqual(match.status, MatchStatus.CLOSED)
		self.assertEqual(match.result, MatchResult.TEAM_A)
		self.assertEqual(match.team_assignments.count(), 6)
		self.assertEqual(match.team_assignments.filter(team=MatchTeam.A).count(), 3)
		self.assertEqual(match.player_ratings.count(), 30)
		self.assertFalse(match.awaiting_result)

	def test_player_profiles_get_statistics_and_levels(self):
		levels = {
			1: MatchSkillLevel.ADVANCED, 2: MatchSkillLevel.ADVANCED,
			3: MatchSkillLevel.INTERMEDIATE, 4: MatchSkillLevel.INTERMEDIATE,
			5: MatchSkillLevel.BEGINNER, 6: MatchSkillLevel.BEGINNER,
		}
		for number, level in levels.items():
			self.assertEqual(calculate_player_skill_level(self.players[number]), level, number)
		stats = calculate_player_statistics(self.players[1])
		self.assertEqual(stats.matches_played, 1)
		self.assertEqual(stats.rating_count, 5)
		wins = sum(calculate_player_statistics(self.players[n]).matches_won for n in range(1, 7))
		losses = sum(calculate_player_statistics(self.players[n]).matches_lost for n in range(1, 7))
		self.assertEqual((wins, losses), (3, 3))
		# Players that did not play have no statistics and are Beginners.
		self.assertEqual(calculate_player_statistics(self.players[8]).matches_played, 0)
		self.assertEqual(calculate_player_skill_level(self.players[8]), MatchSkillLevel.BEGINNER)

	def test_started_match_waits_for_the_organizer_result(self):
		match = self.match('Started')
		self.assertTrue(match.has_started)
		self.assertTrue(match.awaiting_result)
		self.assertEqual(match.team_assignments.count(), 6)
		self.assertEqual(match.chat_messages.count(), 3)
		request = RequestFactory().get('/')
		request.user = self.organizer
		self.assertEqual(pending_match_result(request)['pending_result_match'], match)
		request.user = self.players[1]
		self.assertIsNone(pending_match_result(request)['pending_result_match'])

	def test_started_match_teams_use_the_ratings(self):
		match = self.match('Started')
		teams = {
			assignment.participant.player.username: assignment.team
			for assignment in MatchTeamAssignment.objects.filter(match=match).select_related('participant__player')
		}
		self.assertEqual(
			teams,
			{
				'player1': 'A', 'player2': 'B', 'player3': 'B',
				'player4': 'A', 'player5': 'A', 'player6': 'B',
			},
		)

	def test_organizer_can_log_in_and_sees_the_result_pop_up(self):
		self.assertTrue(self.client.login(username='organizer', password='prueba123'))
		response = self.client.get('/matches/')
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['pending_result_match'], self.match('Started'))

	def test_open_match_has_one_free_spot_and_an_invitation(self):
		match = self.match('Open')
		self.assertFalse(match.has_started)
		self.assertEqual(match.confirmed_participants_count, 5)
		self.assertFalse(match.is_full)
		self.assertEqual(match.waiting_list_count, 0)
		invitation = Invitation.objects.get(match=match)
		self.assertEqual(invitation.player, self.players[9])
		self.assertTrue(Notification.objects.filter(user=self.players[9], match=match).exists())

	def test_join_waiting_list_and_replacement_work_on_the_open_match(self):
		match = self.match('Open')
		self.client.login(username='player6', password='prueba123')
		self.client.post(f'/matches/{match.pk}/join/')
		self.assertTrue(match.is_full)
		self.client.login(username='player7', password='prueba123')
		self.client.post(f'/matches/{match.pk}/join/')
		self.assertEqual(match.waiting_list_count, 1)
		self.client.login(username='player1', password='prueba123')
		self.client.post(f'/matches/{match.pk}/leave/')
		self.assertEqual(
			MatchParticipant.objects.get(match=match, player=self.players[7]).status,
			ParticipantStatus.CONFIRMED,
		)

	def test_private_match_has_a_pending_request(self):
		match = self.match('Private')
		request = JoinRequest.objects.get(match=match)
		self.assertEqual(request.player, self.players[8])
		self.assertEqual(request.request_status, 'pending')
		self.client.login(username='organizer', password='prueba123')
		self.client.post(f'/matches/{match.pk}/requests/{request.pk}/accept/')
		self.assertTrue(MatchParticipant.objects.filter(
			match=match, player=self.players[8], status=ParticipantStatus.CONFIRMED,
		).exists())

	def test_advanced_match_only_admits_advanced_players(self):
		match = self.match('Advanced')
		self.assertEqual(match.skill_level, MatchSkillLevel.ADVANCED)
		self.assertTrue(player_meets_match_skill_level(self.players[1], match))
		self.assertFalse(player_meets_match_skill_level(self.players[8], match))
		self.client.login(username='player8', password='prueba123')
		self.client.post(f'/matches/{match.pk}/join/')
		self.assertFalse(MatchParticipant.objects.filter(match=match, player=self.players[8]).exists())

	def test_favorites_are_ready_for_player1(self):
		favorites = set(FavoritePlayer.objects.filter(user=self.players[1]).values_list('favorite__username', flat=True))
		self.assertEqual(favorites, {'player2', 'player3'})
