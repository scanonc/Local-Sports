from django import forms

from .models import Match


class MatchForm(forms.ModelForm):
    date_time = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local', 'class': 'form-control'},
            format='%Y-%m-%dT%H:%M',
        ),
        input_formats=['%Y-%m-%dT%H:%M'],
    )

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