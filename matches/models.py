from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone


class MatchSkillLevel(models.TextChoices):
	BEGINNER = 'beginner', 'Beginner'
	INTERMEDIATE = 'intermediate', 'Intermediate'
	ADVANCED = 'advanced', 'Advanced'


class MatchVisibility(models.TextChoices):
	PUBLIC = 'public', 'Public'
	APPROVAL_REQUIRED = 'approval_required', 'Approval required'


class MatchStatus(models.TextChoices):
	ACTIVE = 'active', 'Active'
	CLOSED = 'closed', 'Closed'
	CANCELLED = 'cancelled', 'Cancelled'


class Match(models.Model):
	organizer = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='organized_matches',
	)
	title = models.CharField(max_length=120)
	date_time = models.DateTimeField()
	location = models.CharField(max_length=255)
	skill_level = models.CharField(max_length=20, choices=MatchSkillLevel.choices)
	max_players = models.PositiveSmallIntegerField()
	visibility = models.CharField(
		max_length=20,
		choices=MatchVisibility.choices,
		default=MatchVisibility.PUBLIC,
	)
	status = models.CharField(
		max_length=20,
		choices=MatchStatus.choices,
		default=MatchStatus.ACTIVE,
	)
	invite_token = models.UUIDField(
		null=True,
		blank=True,
		unique=True,
	)
	invite_active = models.BooleanField(
		default=True,
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['date_time']

	def __str__(self):
		return f'{self.title} - {self.date_time:%Y-%m-%d %H:%M}'

	def get_absolute_url(self):
		return reverse('matches:match_detail', kwargs={'pk': self.pk})

	def _date_time_is_being_set(self):
		"""True when date_time is new or differs from what is stored.

		The "cannot be in the past" rule exists to stop people from
		scheduling a match in the past. It must not block saving a match
		whose date was already valid and has simply passed in the
		meantime (cancelling it, changing its status, storing its
		invite token, registering its result, ...).
		"""
		if self.pk is None or self._state.adding:
			return True

		stored = (
			Match.objects.filter(pk=self.pk)
			.values_list('date_time', flat=True)
			.first()
		)
		if stored is None:
			return True

		# The edit form only has minute precision, so compare at that level.
		def to_minute(value):
			return value.replace(second=0, microsecond=0)

		return to_minute(stored) != to_minute(self.date_time)

	def clean(self):
		errors = {}

		if (
			self.date_time
			and self.date_time < timezone.now()
			and self._date_time_is_being_set()
		):
			errors['date_time'] = 'Match date and time cannot be in the past.'

		if (
			self.max_players is not None
			and (
				self.max_players < 6
				or self.max_players > 40
				or self.max_players % 2 != 0
			)
		):
			errors['max_players'] = (
				'Maximum number of players must be an even number between 6 and 40.'
			)

		if self.pk is not None:
			confirmed_count = self.participants.filter(
				status=ParticipantStatus.CONFIRMED
			).count()
			if self.max_players is not None and self.max_players < confirmed_count:
				errors['max_players'] = (
					f'Maximum players cannot be less than {confirmed_count} confirmed participants.'
				)

		if errors:
			raise ValidationError(errors)

	def save(self, *args, **kwargs):
		self.full_clean()
		return super().save(*args, **kwargs)

	@property
	def confirmed_participants_count(self):
		return self.participants.filter(status=ParticipantStatus.CONFIRMED).count()

	@property
	def is_full(self):
		return self.confirmed_participants_count >= self.max_players

	@property
	def has_started(self):
		return self.date_time < timezone.now()

	@property
	def is_cancelled(self):
		return self.status == MatchStatus.CANCELLED

	@property
	def is_closed(self):
		return self.status == MatchStatus.CLOSED

	@property
	def has_generated_teams(self):
		return self.team_assignments.exists()

	@property
	def waiting_participants(self):
		return self.participants.filter(status=ParticipantStatus.WAITING).order_by('updated_at')

	@property
	def waiting_list_count(self):
		return self.waiting_participants.count()

	def promote_from_waiting_list(self):
		"""FR11 - Automatic replacement.

		Fills any open confirmed spots with the longest-waiting players,
		in the order they joined the waiting list (FIFO). Called whenever
		a spot may have opened up: a participant leaving, or the organizer
		increasing max_players. Returns the participants that were promoted.
		"""
		promoted = []

		while not self.is_full:
			next_in_line = self.waiting_participants.first()

			if not next_in_line:
				break

			next_in_line.status = ParticipantStatus.CONFIRMED
			next_in_line.save(update_fields=['status', 'updated_at'])
			promoted.append(next_in_line)

		return promoted


class ParticipantStatus(models.TextChoices):
	CONFIRMED = 'confirmed', 'Confirmed'
	LEFT = 'left', 'Left'
	WAITING = 'waiting', 'Waiting'


class MatchParticipant(models.Model):
	match = models.ForeignKey(
		Match,
		on_delete=models.CASCADE,
		related_name='participants',
	)
	player = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='match_participations',
	)
	status = models.CharField(
		max_length=20,
		choices=ParticipantStatus.choices,
		default=ParticipantStatus.CONFIRMED,
	)
	attendance_confirmed = models.BooleanField(default=False)
	joined_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['joined_at']
		constraints = [
			models.UniqueConstraint(fields=['match', 'player'], name='unique_match_player'),
		]

	def __str__(self):
		return f'{self.player} - {self.match} ({self.status})'


class MatchTeam(models.TextChoices):
	A = 'A', 'A'
	B = 'B', 'B'


class MatchTeamAssignment(models.Model):
	match = models.ForeignKey(
		Match,
		on_delete=models.CASCADE,
		related_name='team_assignments',
	)
	participant = models.OneToOneField(
		MatchParticipant,
		on_delete=models.CASCADE,
		related_name='team_assignment',
	)
	team = models.CharField(max_length=1, choices=MatchTeam.choices)

	class Meta:
		ordering = ['team', 'participant__joined_at']

	def clean(self):
		if (
			self.match_id
			and self.participant_id
			and self.participant.match_id != self.match_id
		):
			raise ValidationError(
				'The participant must belong to the assigned match.'
			)

	def __str__(self):
		return f'{self.participant.player} - Team {self.team} ({self.match})'


class MatchMessage(models.Model):
	"""FR22 - Match chat system.

	A simple message thread attached to a match (no real time: messages are
	read when the match page is opened or reloaded).
	"""

	MAX_LENGTH = 500

	match = models.ForeignKey(
		Match,
		on_delete=models.CASCADE,
		related_name='chat_messages',
	)
	author = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='match_messages',
	)
	content = models.TextField(max_length=MAX_LENGTH)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['created_at', 'pk']

	def __str__(self):
		return f'{self.author} in {self.match}: {self.content[:40]}'


class JoinRequestStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    ACCEPTED = 'accepted', 'Accepted'
    REJECTED = 'rejected', 'Rejected'


class JoinRequest(models.Model):
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='join_requests',
    )
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name='join_requests',
    )
    request_date = models.DateTimeField(auto_now_add=True)
    request_status = models.CharField(
        max_length=20,
        choices=JoinRequestStatus.choices,
        default=JoinRequestStatus.PENDING,
    )

    class Meta:
        ordering = ['-request_date']
        constraints = [
            models.UniqueConstraint(
                fields=['match', 'player'],
                condition=models.Q(request_status=JoinRequestStatus.PENDING),
                name='unique_pending_join_request',
            ),
        ]

    def __str__(self):
        return f'{self.player} -> {self.match} ({self.request_status})'


class InvitationStatus(models.TextChoices):
	PENDING = 'pending', 'Pending'
	ACCEPTED = 'accepted', 'Accepted'
	DECLINED = 'declined', 'Declined'


class Invitation(models.Model):
	match = models.ForeignKey(
		Match,
		on_delete=models.CASCADE,
		related_name='invitations',
	)
	organizer = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='sent_invitations',
	)
	player = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='received_invitations',
	)
	status = models.CharField(
		max_length=20,
		choices=InvitationStatus.choices,
		default=InvitationStatus.PENDING,
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']
		constraints = [
			models.UniqueConstraint(
				fields=['match', 'player'],
				condition=models.Q(status=InvitationStatus.PENDING),
				name='unique_pending_invitation',
			),
		]

	def __str__(self):
		return f'{self.organizer} invited {self.player} to {self.match} ({self.status})'