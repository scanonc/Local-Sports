from django.contrib import admin

from .models import (
	Invitation,
	Match,
	MatchMessage,
	MatchParticipant,
	MatchTeamAssignment,
)


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
	list_display = ('match', 'organizer', 'player', 'status', 'created_at')
	list_filter = ('status', 'created_at')
	search_fields = ('match__title', 'organizer__username', 'player__username')
	readonly_fields = ('created_at',)


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


@admin.register(MatchMessage)
class MatchMessageAdmin(admin.ModelAdmin):
	list_display = ('match', 'author', 'created_at')
	search_fields = ('match__title', 'author__username', 'content')
	readonly_fields = ('created_at',)


@admin.register(MatchParticipant)
class MatchParticipantAdmin(admin.ModelAdmin):
	list_display = ('match', 'player', 'status', 'attendance_confirmed', 'joined_at')
	list_filter = ('status', 'attendance_confirmed')
	search_fields = ('match__title', 'player__username', 'player__email')
	ordering = ('-joined_at',)
	readonly_fields = ('joined_at', 'updated_at')


@admin.register(MatchTeamAssignment)
class MatchTeamAssignmentAdmin(admin.ModelAdmin):
	list_display = ('match', 'participant', 'team')
	list_filter = ('team',)
	search_fields = ('match__title', 'participant__player__username')
