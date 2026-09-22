from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Report, User


class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = (
            'username',
            'first_name',
            'last_name',
            'email',
            'skill_level',
            'profile_picture',
        )


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ('reason', 'details')
        widgets = {
            'details': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Optional details'}),
        }