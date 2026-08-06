from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import SignUpForm


class UserLoginView(LoginView):
	template_name = 'users/login.html'


class UserLogoutView(LogoutView):
	next_page = reverse_lazy('home')


class SignUpView(CreateView):
	form_class = SignUpForm
	template_name = 'users/signup.html'
	success_url = reverse_lazy('home')

	def form_valid(self, form):
		response = super().form_valid(form)
		login(self.request, self.object)
		return response
