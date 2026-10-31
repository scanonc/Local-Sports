from django import forms

from .models import Match, MatchMessage


class MatchForm(forms.ModelForm):
    max_players = forms.IntegerField(
        min_value=6,
        max_value=40,
        widget=forms.NumberInput(
            attrs={
                'class': 'form-control',
                'min': 6,
                'max': 40,
                'step': 2,
            }
        ),
    )

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
            'visibility': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean_max_players(self):
        max_players = self.cleaned_data['max_players']
        if max_players % 2 != 0:
            raise forms.ValidationError(
                'Maximum number of players must be an even number between 6 and 40.'
            )
        return max_players


class MatchMessageForm(forms.ModelForm):
    """FR22 - Form to publish a message in a match thread."""

    class Meta:
        model = MatchMessage
        fields = ['content']
        labels = {'content': 'Message'}
        widgets = {
            'content': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 2,
                    'maxlength': MatchMessage.MAX_LENGTH,
                    'placeholder': 'Write a message to the match thread...',
                }
            ),
        }
