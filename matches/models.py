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
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['date_time']

	def __str__(self):
		return f'{self.title} - {self.date_time:%Y-%m-%d %H:%M}'

	def get_absolute_url(self):
		return reverse('matches:match_detail', kwargs={'pk': self.pk})

	def clean(self):
		errors = {}

		if self.date_time and self.date_time < timezone.now():
			errors['date_time'] = 'Match date and time cannot be in the past.'

		if self.max_players is not None and self.max_players < 2:
			errors['max_players'] = 'Maximum number of players must be at least 2.'

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


class ParticipantStatus(models.TextChoices):
	CONFIRMED = 'confirmed', 'Confirmed'
	LEFT = 'left', 'Left'


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