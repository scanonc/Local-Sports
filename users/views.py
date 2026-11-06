from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView
from django.utils.translation import gettext as _

from .forms import ReportForm, SignUpForm
from .models import FavoritePlayer, Notification, Report
from matches.models import MatchSkillLevel
from matches.services.player_statistics import (
	calculate_player_skill_level,
	calculate_player_statistics,
	get_recent_matches,
	rounded_average_rating,
)

User = get_user_model()


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


class PlayerProfileView(LoginRequiredMixin, DetailView):
	model = User
	template_name = 'users/player_profile.html'
	context_object_name = 'player'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		statistics = calculate_player_statistics(self.object)
		context['statistics'] = statistics
		context['average_rating_display'] = rounded_average_rating(statistics)
		context['rating_stars'] = int(context['average_rating_display'] or 0)
		context['skill_level'] = calculate_player_skill_level(self.object)
		context['skill_level_label'] = MatchSkillLevel(context['skill_level']).label
		context['recent_matches'] = get_recent_matches(self.object)
		context['is_own_profile'] = self.object.pk == self.request.user.pk
		if context['is_own_profile']:
			# FR17 - the favorites list is personal: only its owner sees it.
			context['favorite_players'] = [
				entry.favorite
				for entry in FavoritePlayer.objects.filter(user=self.request.user).select_related('favorite')
			]
		else:
			context['is_favorite'] = FavoritePlayer.objects.filter(
				user=self.request.user, favorite=self.object,
			).exists()
		return context


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


class FavoritePlayerToggleView(LoginRequiredMixin, View):
	"""FR17 - Favorite players.

	Adds the target player to the current user's favorites list, or
	removes them if they are already there (toggle behaviour).
	"""

	def post(self, request, pk):
		target_player = get_object_or_404(User, pk=pk)
		next_url = request.POST.get('next') or 'users:favorites'

		if target_player.pk == request.user.pk:
			messages.error(request, _('You cannot favorite yourself.'))
			return redirect(next_url)

		favorite, created = FavoritePlayer.objects.get_or_create(
			user=request.user,
			favorite=target_player,
		)

		if created:
			messages.success(request, _('%(player)s was added to your favorites.') % {'player': target_player})
		else:
			favorite.delete()
			messages.success(request, _('%(player)s was removed from your favorites.') % {'player': target_player})

		return redirect(next_url)


class FavoritePlayerListView(LoginRequiredMixin, ListView):
	model = FavoritePlayer
	template_name = 'users/favorites.html'
	context_object_name = 'favorites'

	def get_queryset(self):
		return FavoritePlayer.objects.filter(user=self.request.user).select_related('favorite')


class ReportUserView(LoginRequiredMixin, CreateView):
	"""FR18 - Report users."""

	model = Report
	form_class = ReportForm
	template_name = 'users/report_form.html'

	def dispatch(self, request, *args, **kwargs):
		self.reported_user = get_object_or_404(User, pk=kwargs['pk'])

		if self.reported_user.pk == request.user.pk:
			messages.error(request, _('You cannot report yourself.'))
			return redirect('home')

		return super().dispatch(request, *args, **kwargs)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['reported_user'] = self.reported_user
		return context

	def form_valid(self, form):
		form.instance.reporter = self.request.user
		form.instance.reported_user = self.reported_user
		response = super().form_valid(form)
		messages.success(
			self.request,
			_('Your report about %(player)s was submitted.') % {'player': self.reported_user},
		)
		return response

	def get_success_url(self):
		next_url = self.request.POST.get('next')
		return next_url or reverse_lazy('home')