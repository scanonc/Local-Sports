from django import forms
from django.core.exceptions import ValidationError

from .models import Match, ParticipantStatus


class MatchForm(forms.ModelForm):
    date_time = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local', 'class': 'form-control'},
            format='%Y-%m-%dT%H:%M',
        ),
        input_formats=['%Y-%m-%dT%H:%M'],
    )

    join_as_player = forms.BooleanField(required=False, label='I want to participate in this match')
    class Meta:
        model = Match
        fields = ['title', 'date_time', 'location', 'skill_level', 'max_players', 'visibility']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'skill_level': forms.Select(attrs={'class': 'form-select'}),
            'max_players': forms.NumberInput(attrs={'class': 'form-control', 'min': 2}),
            'visibility': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        # When editing an existing match, ensure max_players is not reduced below confirmed participants
        if self.instance.pk:
            confirmed_count = self.instance.participants.filter(
                status=ParticipantStatus.CONFIRMED
            ).count()
            max_players = cleaned_data.get('max_players')
            if max_players and max_players < confirmed_count:
                self.add_error(
                    'max_players',
                    f'Maximum players cannot be less than {confirmed_count} confirmed participants.'
                )
        return cleaned_data