from django.contrib import admin

from .models import Match, MatchParticipant


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
	list_display = (
		'title',
		'organizer',
		'status',
		'date_time',
		'location',
		'skill_level',
		'max_players',
		'visibility',
	)
	list_filter = ('status', 'visibility', 'skill_level', 'date_time')
	search_fields = ('title', 'location', 'organizer__username', 'organizer__email')
	ordering = ('date_time',)
	readonly_fields = ('created_at', 'updated_at')


@admin.register(MatchParticipant)
class MatchParticipantAdmin(admin.ModelAdmin):
	list_display = ('match', 'player', 'status', 'attendance_confirmed', 'joined_at')
	list_filter = ('status', 'attendance_confirmed')
	search_fields = ('match__title', 'player__username', 'player__email')
	ordering = ('-joined_at',)
	readonly_fields = ('joined_at', 'updated_at')
