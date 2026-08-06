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

		if errors:
			raise ValidationError(errors)

	def save(self, *args, **kwargs):
		self.full_clean()
		return super().save(*args, **kwargs)
