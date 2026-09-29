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

	@property
	def initials(self):
		first = self.first_name[:1]
		last = self.last_name[:1]
		combined = f'{first}{last}'.strip().upper()
		return combined or self.username[:2].upper()


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


class FavoritePlayer(models.Model):
	"""FR17 - Favorite players.

	Records that `user` has marked `favorite` as a favorite player.
	Directional (not mutual): each row is one player's own favorites list.
	"""

	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='favorite_players',
	)
	favorite = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='favorited_by',
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']
		constraints = [
			models.UniqueConstraint(fields=['user', 'favorite'], name='unique_favorite_player'),
			models.CheckConstraint(
				condition=~models.Q(user=models.F('favorite')),
				name='favorite_player_not_self',
			),
		]

	def __str__(self):
		return f'{self.user} favorited {self.favorite}'
