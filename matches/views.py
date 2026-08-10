from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import MatchForm
from .models import Match, MatchParticipant, MatchVisibility, ParticipantStatus


class MatchDetailView(DetailView):
    model = Match
    template_name = 'matches/match_detail.html'
    context_object_name = 'match'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['user_is_organizer'] = user.is_authenticated and self.object.organizer_id == user.id
        context['user_is_participant'] = (
            user.is_authenticated
            and MatchParticipant.objects.filter(
                match=self.object, player=user, status=ParticipantStatus.CONFIRMED
            ).exists()
        )
        return context


class MatchListView(ListView):
    model = Match
    template_name = 'matches/match_list.html'
    context_object_name = 'matches'


class MatchCreateView(LoginRequiredMixin, CreateView):
    model = Match
    form_class = MatchForm
    template_name = 'matches/match_form.html'

    def form_valid(self, form):
        form.instance.organizer = self.request.user
        return super().form_valid(form)


class MatchUpdateView(LoginRequiredMixin, UpdateView):
    model = Match
    form_class = MatchForm
    template_name = 'matches/match_form.html'

    def get_queryset(self):
        return Match.objects.filter(organizer=self.request.user)


class MatchJoinView(LoginRequiredMixin, View):
    """FR5 - Join public match.

    A player joins a match directly, without organizer approval, as long
    as the match is public, has not started yet, still has room, and the
    player is not the organizer or already an active participant.
    Matches that require approval are out of scope here (see FR4).
    """

    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)

        if match.organizer_id == request.user.id:
            messages.error(request, 'You are the organizer of this match.')
            return redirect('matches:match_detail', pk=match.pk)

        if match.visibility != MatchVisibility.PUBLIC:
            messages.error(
                request,
                'This match requires the organizer\'s approval to join.',
            )
            return redirect('matches:match_detail', pk=match.pk)

        if match.has_started:
            messages.error(request, 'This match has already started or finished.')
            return redirect('matches:match_detail', pk=match.pk)

        participant = MatchParticipant.objects.filter(match=match, player=request.user).first()

        if participant and participant.status == ParticipantStatus.CONFIRMED:
            messages.info(request, 'You already joined this match.')
            return redirect('matches:match_detail', pk=match.pk)

        if match.is_full:
            messages.error(request, 'This match is already full.')
            return redirect('matches:match_detail', pk=match.pk)

        if participant:
            participant.status = ParticipantStatus.CONFIRMED
            participant.save(update_fields=['status', 'updated_at'])
        else:
            MatchParticipant.objects.create(
                match=match,
                player=request.user,
                status=ParticipantStatus.CONFIRMED,
            )

        messages.success(request, 'You have joined the match.')
        return redirect('matches:match_detail', pk=match.pk)


class MatchLeaveView(LoginRequiredMixin, View):
    """FR6 - Leave match.

    A confirmed participant can leave a match they previously joined. The
    participant row is kept and its status is set to LEFT instead of being
    deleted, so historical information is preserved.
    """

    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)

        participant = MatchParticipant.objects.filter(
            match=match, player=request.user, status=ParticipantStatus.CONFIRMED
        ).first()

        if not participant:
            messages.error(request, 'You are not currently part of this match.')
            return redirect('matches:match_detail', pk=match.pk)

        participant.status = ParticipantStatus.LEFT
        participant.save(update_fields=['status', 'updated_at'])

        messages.success(request, 'You have left the match.')
        return redirect('matches:match_detail', pk=match.pk)
