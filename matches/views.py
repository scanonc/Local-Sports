from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
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
                status=ParticipantStatus.CONFIRMED,
            ).exists()
        )

        context['user_has_pending_request'] = (
            user.is_authenticated
            and JoinRequest.objects.filter(
                match=self.object,
                player=user,
                request_status=JoinRequestStatus.PENDING,
            ).exists()
        )

        waiting_participant = None
        if user.is_authenticated:
            waiting_participant = MatchParticipant.objects.filter(
                match=self.object,
                player=user,
                status=ParticipantStatus.WAITING,
            ).first()

        context['user_is_waiting'] = waiting_participant is not None
        if waiting_participant:
            context['user_waiting_position'] = self.object.waiting_participants.filter(
                updated_at__lte=waiting_participant.updated_at,
            ).count()

        context['waiting_list_count'] = self.object.waiting_list_count

        if user_is_organizer:
            context['pending_join_requests'] = JoinRequest.objects.filter(
                match=self.object,
                request_status=JoinRequestStatus.PENDING,
            ).select_related('player')
            context['waiting_list'] = self.object.waiting_participants.select_related('player')

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

    def form_valid(self, form):
        """FR11 - Automatic replacement.

        If the organizer increases max_players, promote waiting players
        into the newly opened spots right away.
        """
        response = super().form_valid(form)
        self.object.promote_from_waiting_list()
        return response


class MatchJoinView(LoginRequiredMixin, View):
    """FR5 - Join public match.

    FR10 - Waiting list: if the match is public but already full, the
    player is placed on the waiting list instead of being turned away.
    Capacity validation is protected against race conditions using transactions.
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

        with transaction.atomic():
            match = Match.objects.select_for_update().get(pk=pk)

            if match.visibility != MatchVisibility.PUBLIC:
                messages.error(
                    request,
                    'This match requires the organizer\'s approval to join.',
                )
                return redirect('matches:match_detail', pk=match.pk)

            if match.date_time < timezone.now():
                messages.error(request, 'This match has already started or finished.')
                return redirect('matches:match_detail', pk=match.pk)

            participant = MatchParticipant.objects.filter(
                match=match,
                player=request.user,
            ).first()

            if participant and participant.status == ParticipantStatus.CONFIRMED:
                messages.info(request, 'You already joined this match.')
                return redirect('matches:match_detail', pk=match.pk)

            if participant and participant.status == ParticipantStatus.WAITING:
                messages.info(request, 'You are already on the waiting list for this match.')
                return redirect('matches:match_detail', pk=match.pk)

            confirmed_count = MatchParticipant.objects.filter(
                match=match,
                status=ParticipantStatus.CONFIRMED,
            ).count()

            if confirmed_count >= match.max_players:
                if participant:
                    participant.status = ParticipantStatus.WAITING
                    participant.save(update_fields=['status', 'updated_at'])
                else:
                    participant = MatchParticipant.objects.create(
                        match=match,
                        player=request.user,
                        status=ParticipantStatus.WAITING,
                    )

                position = match.waiting_participants.filter(
                    updated_at__lte=participant.updated_at,
                ).count()
                messages.info(
                    request,
                    f'This match is full. You have been added to the waiting list (position {position}).',
                )
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

        confirmed_count = MatchParticipant.objects.filter(
            match=match,
            status=ParticipantStatus.CONFIRMED,
        ).count()

        if confirmed_count >= match.max_players:
            messages.error(
                request,
                'This match is already full and cannot accept new requests.',
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

        with transaction.atomic():
            match = Match.objects.select_for_update().get(pk=pk)

            if match.organizer_id != request.user.id:
                messages.error(
                    request,
                    'Only the organizer can accept join requests.',
                )
                return redirect('matches:match_detail', pk=match.pk)

            try:
                join_request = JoinRequest.objects.select_for_update().get(
                    id=request_id,
                    match=match,
                    request_status=JoinRequestStatus.PENDING,
                )
            except JoinRequest.DoesNotExist:
                messages.error(request, 'This join request is not available.')
                return redirect('matches:match_detail', pk=match.pk)

            if match.date_time < timezone.now():
                messages.error(
                    request,
                    'This match has already started or finished.',
                )
                return redirect('matches:match_detail', pk=match.pk)

            confirmed_count = MatchParticipant.objects.filter(
                match=match,
                status=ParticipantStatus.CONFIRMED,
            ).count()
            if confirmed_count >= match.max_players:
                messages.error(
                    request,
                    'This match is already full and cannot accept more requests.',
                )
                return redirect('matches:match_detail', pk=match.pk)

            participant = MatchParticipant.objects.filter(
                match=match,
                player=join_request.player,
            ).first()

            if participant:
                if participant.status != ParticipantStatus.CONFIRMED:
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
    """FR6 - Leave match (also used to leave the waiting list).

    FR11 - Automatic replacement: if a confirmed spot is freed, the
    longest-waiting player on the waiting list is promoted automatically.
    """

    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)

        participant = MatchParticipant.objects.filter(
            match=match,
            player=request.user,
            status__in=[ParticipantStatus.CONFIRMED, ParticipantStatus.WAITING],
        ).first()

        if not participant:
            messages.error(request, 'You are not currently part of this match.')
            return redirect('matches:match_detail', pk=match.pk)

        was_confirmed = participant.status == ParticipantStatus.CONFIRMED

        participant.status = ParticipantStatus.LEFT
        participant.save(update_fields=['status', 'updated_at'])

        if was_confirmed:
            match.promote_from_waiting_list()
            messages.success(request, 'You have left the match.')
        else:
            messages.success(request, 'You have left the waiting list.')

        return redirect('matches:match_detail', pk=match.pk)

