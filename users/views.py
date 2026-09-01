from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView

from .forms import SignUpForm
from .models import Notification


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


class NotificationListView(LoginRequiredMixin, ListView):
	model = Notification
	template_name = 'users/notifications.html'
	context_object_name = 'notifications'

	def get_queryset(self):
		return Notification.objects.filter(user=self.request.user).order_by('-created_at')

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['notifications'] = context['notifications']
		self.request.user.notifications.filter(is_read=False).update(is_read=True)
		return context


def mark_notification_read(request, pk):
	if not request.user.is_authenticated:
		return redirect('users:login')

	try:
		notification = Notification.objects.get(pk=pk, user=request.user)
	except Notification.DoesNotExist:
		return redirect('users:notifications')

	notification.is_read = True
	notification.save(update_fields=['is_read'])

	if notification.match_id:
		return redirect('matches:match_detail', pk=notification.match_id)
	return redirect('users:notifications')
