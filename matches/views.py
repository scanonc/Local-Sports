from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import MatchForm
from .models import (
    JoinRequest,
    JoinRequestStatus,
    Match,
    MatchParticipant,
    MatchVisibility,
    ParticipantStatus,
)


class MatchDetailView(DetailView):
    model = Match
    template_name = 'matches/match_detail.html'
    context_object_name = 'match'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        user_is_organizer = (
            user.is_authenticated
            and self.object.organizer_id == user.id
        )

        context['user_is_organizer'] = user_is_organizer

        context['user_is_participant'] = (
            user.is_authenticated
            and MatchParticipant.objects.filter(
                match=self.object,
                player=user,
                status=ParticipantStatus.CONFIRMED
            ).exists()
        )

        if user_is_organizer:
            context['pending_join_requests'] = JoinRequest.objects.filter(
                match=self.object,
                request_status=JoinRequestStatus.PENDING,
            ).select_related('player')

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

class MatchRequestJoinView(LoginRequiredMixin, View):
    """FR4 - Request to join a match that requires organizer approval."""

    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)

        if match.organizer_id == request.user.id:
            messages.error(request, 'You are the organizer of this match.')
            return redirect('matches:match_detail', pk=match.pk)

        if match.visibility != MatchVisibility.APPROVAL_REQUIRED:
            messages.error(
                request,
                'This match does not require approval to join.',
            )
            return redirect('matches:match_detail', pk=match.pk)

        if match.has_started:
            messages.error(
                request,
                'This match has already started or finished.',
            )
            return redirect('matches:match_detail', pk=match.pk)

        participant = MatchParticipant.objects.filter(
            match=match,
            player=request.user,
            status=ParticipantStatus.CONFIRMED,
        ).exists()

        if participant:
            messages.info(request, 'You already joined this match.')
            return redirect('matches:match_detail', pk=match.pk)

        existing_request = JoinRequest.objects.filter(
            match=match,
            player=request.user,
            request_status=JoinRequestStatus.PENDING,
        ).exists()

        if existing_request:
            messages.info(
                request,
                'You already have a pending request for this match.',
            )
            return redirect('matches:match_detail', pk=match.pk)

        JoinRequest.objects.create(
            match=match,
            player=request.user,
        )

        messages.success(
            request,
            'Your request to join the match has been sent.',
        )
        return redirect('matches:match_detail', pk=match.pk)


class MatchRequestAcceptView(LoginRequiredMixin, View):
    """FR4 - Accept a player's request to join a match."""

    def post(self, request, pk, request_id):
        match = get_object_or_404(Match, pk=pk)

        if match.organizer_id != request.user.id:
            messages.error(
                request,
                'Only the organizer can accept join requests.',
            )
            return redirect('matches:match_detail', pk=match.pk)

        join_request = get_object_or_404(
            JoinRequest,
            id=request_id,
            match=match,
            request_status=JoinRequestStatus.PENDING,
        )

        if match.has_started:
            messages.error(
                request,
                'This match has already started or finished.',
            )
            return redirect('matches:match_detail', pk=match.pk)

        if match.is_full:
            messages.error(
                request,
                'This match is already full.',
            )
            return redirect('matches:match_detail', pk=match.pk)

        participant = MatchParticipant.objects.filter(
            match=match,
            player=join_request.player,
        ).first()

        if participant:
            participant.status = ParticipantStatus.CONFIRMED
            participant.save(update_fields=['status', 'updated_at'])
        else:
            MatchParticipant.objects.create(
                match=match,
                player=join_request.player,
                status=ParticipantStatus.CONFIRMED,
            )

        join_request.request_status = JoinRequestStatus.ACCEPTED
        join_request.save(update_fields=['request_status'])

        messages.success(
            request,
            'The join request has been accepted.',
        )
        return redirect('matches:match_detail', pk=match.pk)


class MatchRequestRejectView(LoginRequiredMixin, View):
    """FR4 - Reject a player's request to join a match."""

    def post(self, request, pk, request_id):
        match = get_object_or_404(Match, pk=pk)

        if match.organizer_id != request.user.id:
            messages.error(
                request,
                'Only the organizer can reject join requests.',
            )
            return redirect('matches:match_detail', pk=match.pk)

        join_request = get_object_or_404(
            JoinRequest,
            id=request_id,
            match=match,
            request_status=JoinRequestStatus.PENDING,
        )

        join_request.request_status = JoinRequestStatus.REJECTED
        join_request.save(update_fields=['request_status'])

        messages.success(
            request,
            'The join request has been rejected.',
        )
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
