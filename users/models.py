from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserSkillLevel(models.TextChoices):
	BEGINNER = 'beginner', 'Beginner'
	INTERMEDIATE = 'intermediate', 'Intermediate'
	ADVANCED = 'advanced', 'Advanced'


class User(AbstractUser):
	email = models.EmailField(unique=True)
	skill_level = models.CharField(
		max_length=20,
		choices=UserSkillLevel.choices,
		default=UserSkillLevel.BEGINNER,
	)
	profile_picture = models.CharField(max_length=255, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return self.get_full_name() or self.username


class Notification(models.Model):
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='notifications',
	)
	match = models.ForeignKey(
		'matches.Match',
		on_delete=models.CASCADE,
		related_name='notifications',
		null=True,
		blank=True,
	)
	message = models.TextField()
	is_read = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'{self.user} - {self.message[:60]}'


class ReportReason(models.TextChoices):
	NO_SHOW = 'no_show', 'Did not show up'
	UNSPORTSMANLIKE_CONDUCT = 'unsportsmanlike_conduct', 'Unsportsmanlike conduct'
	ABUSIVE_LANGUAGE = 'abusive_language', 'Abusive language'
	OTHER = 'other', 'Other'


class Report(models.Model):
	"""FR18 - Report users."""

	reporter = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='reports_made',
	)
	reported_user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='reports_received',
	)
	reason = models.CharField(max_length=30, choices=ReportReason.choices)
	details = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']
		constraints = [
			models.CheckConstraint(
				condition=~models.Q(reporter=models.F('reported_user')),
				name='report_not_self',
			),
		]

	def __str__(self):
		return f'{self.reporter} reported {self.reported_user} ({self.get_reason_display()})'
