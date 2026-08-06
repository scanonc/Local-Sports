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
