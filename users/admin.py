from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
	readonly_fields = ('created_at',)
	list_display = (
		'username',
		'email',
		'first_name',
		'last_name',
		'skill_level',
		'is_staff',
		'created_at',
	)
	list_filter = ('is_staff', 'is_superuser', 'is_active', 'skill_level')
	search_fields = ('username', 'first_name', 'last_name', 'email')

	fieldsets = UserAdmin.fieldsets + (
		('Local Sports', {'fields': ('skill_level', 'profile_picture', 'created_at')}),
	)
	add_fieldsets = UserAdmin.add_fieldsets + (
		('Local Sports', {'fields': ('skill_level', 'profile_picture')}),
	)
