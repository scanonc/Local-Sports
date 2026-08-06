from django.contrib import admin

from .models import Match


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
	list_display = (
		'title',
		'organizer',
		'date_time',
		'location',
		'skill_level',
		'max_players',
		'visibility',
	)
	list_filter = ('visibility', 'skill_level', 'date_time')
	search_fields = ('title', 'location', 'organizer__username', 'organizer__email')
	ordering = ('date_time',)
	readonly_fields = ('created_at', 'updated_at')
