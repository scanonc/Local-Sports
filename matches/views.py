from datetime import datetime
import uuid

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import MatchForm, MatchMessageForm
from .models import (
    JoinRequest,
    JoinRequestStatus,
    Invitation,
    InvitationStatus,
    Match,
    MatchParticipant,
    MatchSkillLevel,
    MatchStatus,
    MatchTeamAssignment,
    MatchVisibility,
    ParticipantStatus,
)
from .services import (
    build_match_invite_url,
    generate_match_invite_token,
    notify_attendance_confirmation,
    notify_match_cancellation,
    notify_match_update,
    process_link_invitation,
)
from .team_services import TeamDistributionError, distribute_match_teams

from users.models import FavoritePlayer
from users.models import Notification

User = get_user_model()


def user_can_use_match_chat(match, user):
    """FR22 - Only the organizer and confirmed participants use the match chat."""
    if not user.is_authenticated:
        return False

    if match.organizer_id == user.id:
        return True

    return MatchParticipant.objects.filter(
        match=match,
        player=user,
        status=ParticipantStatus.CONFIRMED,
    ).exists()


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
        context['attendance_participants'] = self.object.participants.filter(
            status=ParticipantStatus.CONFIRMED,
        ).select_related('player')
        context['team_a_assignments'] = self.object.team_assignments.filter(
            team='A',
        ).select_related('participant__player')
        context['team_b_assignments'] = self.object.team_assignments.filter(
            team='B',
        ).select_related('participant__player')

        if self.object.is_closed:
            context['team_generation_block_reason'] = (
                'Teams have already been generated.'
            )
        elif self.object.has_started:
            context['team_generation_block_reason'] = (
                'Teams can only be generated before the match starts.'
            )
        elif self.object.confirmed_participants_count < 6:
            context['team_generation_block_reason'] = (
                'At least 6 confirmed participants are required.'
            )
        elif self.object.confirmed_participants_count % 2:
            context['team_generation_block_reason'] = (
                'The number of confirmed participants must be even.'
            )
        elif self.object.status == MatchStatus.CANCELLED:
            context['team_generation_block_reason'] = (
                'Cancelled matches cannot generate teams.'
            )
        else:
            context['team_generation_block_reason'] = None

        context['can_generate_teams'] = (
            user_is_organizer
            and context['team_generation_block_reason'] is None
        )

        context['favorite_player_ids'] = (
            set(
                FavoritePlayer.objects.filter(user=user).values_list('favorite_id', flat=True)
            )
            if user.is_authenticated
            else set()
        )

        context['user_has_confirmed_attendance'] = (
            user.is_authenticated
            and MatchParticipant.objects.filter(
                match=self.object,
                player=user,
                status=ParticipantStatus.CONFIRMED,
                attendance_confirmed=True,
            ).exists()
        )

        context['pending_invitation'] = (
            Invitation.objects.filter(
                match=self.object,
                player=user,
                status=InvitationStatus.PENDING,
            ).select_related('organizer').first()
            if user.is_authenticated
            else None
        )

        user_can_use_chat = user_can_use_match_chat(self.object, user)
        context['user_can_use_chat'] = user_can_use_chat
        if user_can_use_chat:
            context['chat_messages'] = self.object.chat_messages.select_related('author')
            context['chat_form'] = MatchMessageForm()

        if user_is_organizer:
            context['pending_join_requests'] = JoinRequest.objects.filter(
                match=self.object,
                request_status=JoinRequestStatus.PENDING,
            ).select_related('player')
            context['waiting_list'] = self.object.waiting_participants.select_related('player')
            invited_player_ids = Invitation.objects.filter(
                match=self.object,
                status=InvitationStatus.PENDING,
            ).values_list('player_id', flat=True)
            context['has_pending_invitations'] = Invitation.objects.filter(
                match=self.object,
                status=InvitationStatus.PENDING,
            ).exists()
            if self.object.invite_token and self.object.invite_active:
                context['invite_url'] = self.request.build_absolute_uri(
                    reverse('matches:match_join_via_link', kwargs={'token': str(self.object.invite_token)})
                )

        return context


class MatchHistoryView(LoginRequiredMixin, ListView):
    model = Match
    template_name = 'matches/match_history.html'
    context_object_name = 'matches'

    def get_queryset(self):
        user = self.request.user
        return (
            Match.objects.filter(
                Q(organizer=user)
                | Q(
                    participants__player=user,
                    participants__status=ParticipantStatus.CONFIRMED,
                ),
            )
            .filter(
                Q(date_time__lt=timezone.now())
                | Q(status=MatchStatus.CANCELLED),
            )
            .select_related('organizer')
            .prefetch_related('participants')
            .distinct()
            .order_by('-date_time')
        )


class MatchInviteLinkView(LoginRequiredMixin, View):
    """FR16 - Exclusive view for match organizers to generate or retrieve a shareable invitation link."""

    def _generate_link(self, request, pk):
        match = get_object_or_404(Match, pk=pk)

        is_json = (
            request.headers.get('x-requested-with') == 'XMLHttpRequest'
            or 'application/json' in request.headers.get('Accept', '')
            or request.content_type == 'application/json'
            or request.GET.get('format') == 'json'
        )

        if match.organizer_id != request.user.id:
            if is_json:
                return JsonResponse({'error': 'Only the organizer can generate invitation links.'}, status=403)
            messages.error(request, 'Only the organizer can generate invitation links.')
            return redirect('matches:match_detail', pk=match.pk)

        if match.status == MatchStatus.CANCELLED:
            if is_json:
                return JsonResponse({'error': 'This match has been cancelled.'}, status=400)
            messages.error(request, 'This match has been cancelled.')
            return redirect('matches:match_detail', pk=match.pk)

        if match.status == MatchStatus.CLOSED:
            if is_json:
                return JsonResponse({'error': 'This match is closed.'}, status=400)
            messages.error(request, 'This match is closed and cannot accept invitations.')
            return redirect('matches:match_detail', pk=match.pk)

        if match.has_started:
            if is_json:
                return JsonResponse({'error': 'This match has already started or finished.'}, status=400)
            messages.error(request, 'This match has already started or finished.')
            return redirect('matches:match_detail', pk=match.pk)

        invite_url = build_match_invite_url(match, request)

        if is_json:
            return JsonResponse({
                'invite_url': invite_url,
                'invite_token': str(match.invite_token),
                'status': 'success',
            })

        messages.success(request, f'Shareable invitation link generated: {invite_url}')
        return redirect('matches:match_detail', pk=match.pk)

    def post(self, request, pk):
        return self._generate_link(request, pk)

    def get(self, request, pk):
        return self._generate_link(request, pk)


class MatchJoinViaLinkView(LoginRequiredMixin, View):
    """FR16 - Public match invitation landing page accessible via invite token."""

    def _get_match_and_status(self, token):
        try:
            token_uuid = uuid.UUID(str(token))
        except (ValueError, TypeError, AttributeError):
            return None, 'invalid'

        match = Match.objects.filter(invite_token=token_uuid).first()
        if not match:
            return None, 'invalid'

        if not match.invite_active:
            return match, 'inactive'

        return match, 'valid'

    def get(self, request, token):
        match, token_status = self._get_match_and_status(token)

        if token_status == 'invalid':
            return render(request, 'matches/match_invite.html', {
                'error_message': 'This invitation link is invalid.',
                'token': token,
            })

        if token_status == 'inactive':
            return render(request, 'matches/match_invite.html', {
                'error_message': 'This invitation link has been deactivated.',
                'match': match,
                'token': token,
            })

        if match.status == MatchStatus.CANCELLED:
            return render(request, 'matches/match_invite.html', {
                'error_message': 'This match has been cancelled by the organizer.',
                'match': match,
                'token': token,
            })

        if match.status == MatchStatus.CLOSED:
            return render(request, 'matches/match_invite.html', {
                'error_message': 'This match is closed and cannot accept new participants.',
                'match': match,
                'token': token,
            })

        if match.has_started:
            return render(request, 'matches/match_invite.html', {
                'error_message': 'This match has already started or finished.',
                'match': match,
                'token': token,
            })

        user = request.user
        user_is_organizer = match.organizer_id == user.id

        participant = MatchParticipant.objects.filter(
            match=match,
            player=user,
        ).first()

        user_is_confirmed = (
            participant is not None
            and participant.status == ParticipantStatus.CONFIRMED
        )
        user_is_waiting = (
            participant is not None
            and participant.status == ParticipantStatus.WAITING
        )

        can_join = True
        notice_message = None

        if match.is_full:
            if match.visibility != MatchVisibility.PUBLIC:
                can_join = False
                notice_message = 'This match is full and no longer admits participants.'
            else:
                notice_message = 'This match is currently full. Accepting this invitation will place you on the waiting list.'

        context = {
            'match': match,
            'token': token,
            'user_is_organizer': user_is_organizer,
            'user_is_confirmed': user_is_confirmed,
            'user_is_waiting': user_is_waiting,
            'can_join': can_join,
            'notice_message': notice_message,
        }
        return render(request, 'matches/match_invite.html', context)

    def post(self, request, token):
        match, token_status = self._get_match_and_status(token)

        if token_status == 'invalid':
            messages.error(request, 'This invitation link is invalid.')
            return redirect('matches:match_list')

        if token_status == 'inactive':
            messages.error(request, 'This invitation link has been deactivated.')
            return redirect('matches:match_detail', pk=match.pk) if match else redirect('matches:match_list')

        action = request.POST.get('action', 'accept').strip().lower()

        success, message, participant = process_link_invitation(match, request.user, action)

        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)

        return redirect('matches:match_detail', pk=match.pk)


class MatchInvitePlayersView(LoginRequiredMixin, View):
    """Send persistent invitations from a match organizer to registered players."""

    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)

        if match.organizer_id != request.user.id:
            messages.error(request, 'Only the organizer can invite players.')
            return redirect('matches:match_detail', pk=match.pk)

        player_identifier = request.POST.get('player_identifier', '').strip()
        if not player_identifier:
            messages.error(request, 'Enter a username or email address to invite.')
            return redirect('matches:match_detail', pk=match.pk)

        with transaction.atomic():
            match = Match.objects.select_for_update().get(pk=pk)

            if match.status == MatchStatus.CANCELLED:
                messages.error(request, 'This match has been cancelled.')
                return redirect('matches:match_detail', pk=match.pk)

            if match.status == MatchStatus.CLOSED:
                messages.error(request, 'This match is closed and cannot accept invitations.')
                return redirect('matches:match_detail', pk=match.pk)

            if match.has_started:
                messages.error(request, 'This match has already started or finished.')
                return redirect('matches:match_detail', pk=match.pk)

            confirmed_count = MatchParticipant.objects.filter(
                match=match,
                status=ParticipantStatus.CONFIRMED,
            ).count()
            available_slots = match.max_players - confirmed_count
            if available_slots <= 0:
                messages.error(request, 'This match is full and cannot accept invitations.')
                return redirect('matches:match_detail', pk=match.pk)

            player = User.objects.filter(
                Q(username__iexact=player_identifier) | Q(email__iexact=player_identifier),
                is_active=True,
            ).first()
            participant_ids = set(match.participants.filter(
                status__in=[ParticipantStatus.CONFIRMED, ParticipantStatus.WAITING],
            ).values_list('player_id', flat=True))
            pending_invitation_ids = set(Invitation.objects.filter(
                match=match,
                status=InvitationStatus.PENDING,
            ).values_list('player_id', flat=True))
            if (
                player is None
                or player.pk in participant_ids
                or player.pk in pending_invitation_ids
                or match.organizer_id == player.pk
            ):
                messages.error(request, 'This player cannot be invited.')
                return redirect('matches:match_detail', pk=match.pk)

            Invitation.objects.create(match=match, organizer=request.user, player=player)
            Notification.objects.create(
                user=player,
                match=match,
                message=f'You have been invited by {request.user} to the match "{match.title}".',
            )

        messages.success(request, f'Invitation sent to {player}.')
        return redirect('matches:match_detail', pk=match.pk)


class MatchInvitationResponseView(LoginRequiredMixin, View):
    """Accept or decline a pending invitation as its intended player."""

    def post(self, request, pk, invitation_id, action):
        with transaction.atomic():
            match = get_object_or_404(
                Match.objects.select_for_update(),
                pk=pk,
            )
            invitation = get_object_or_404(
                Invitation.objects.select_for_update(),
                pk=invitation_id,
                match=match,
                player=request.user,
                status=InvitationStatus.PENDING,
            )

            if action == 'decline':
                invitation.status = InvitationStatus.DECLINED
                invitation.save(update_fields=['status'])
                messages.success(request, 'The invitation has been declined.')
                return redirect('matches:match_detail', pk=match.pk)

            if action != 'accept':
                messages.error(request, 'This invitation action is not available.')
                return redirect('matches:match_detail', pk=match.pk)

            if match.status == MatchStatus.CANCELLED:
                messages.error(request, 'This match has been cancelled.')
                return redirect('matches:match_detail', pk=match.pk)

            if match.status == MatchStatus.CLOSED:
                messages.error(request, 'This match is closed and cannot accept invitations.')
                return redirect('matches:match_detail', pk=match.pk)

            if match.has_started:
                messages.error(request, 'This match has already started or finished.')
                return redirect('matches:match_detail', pk=match.pk)

            participant = MatchParticipant.objects.filter(
                match=match,
                player=request.user,
            ).first()
            if participant and participant.status in [
                ParticipantStatus.CONFIRMED,
                ParticipantStatus.WAITING,
            ]:
                messages.error(request, 'You are already participating in this match.')
                return redirect('matches:match_detail', pk=match.pk)

            confirmed_count = MatchParticipant.objects.filter(
                match=match,
                status=ParticipantStatus.CONFIRMED,
            ).count()
            if confirmed_count >= match.max_players:
                if match.visibility != MatchVisibility.PUBLIC:
                    messages.error(request, 'This match is full and cannot accept the invitation.')
                    return redirect('matches:match_detail', pk=match.pk)
                participant_status = ParticipantStatus.WAITING
                message = 'The invitation was accepted. You were added to the waiting list.'
            else:
                participant_status = ParticipantStatus.CONFIRMED
                message = 'The invitation was accepted. You joined the match.'

            if participant:
                participant.status = participant_status
                participant.attendance_confirmed = False
                participant.save(update_fields=['status', 'attendance_confirmed', 'updated_at'])
            else:
                MatchParticipant.objects.create(
                    match=match,
                    player=request.user,
                    status=participant_status,
                )

            invitation.status = InvitationStatus.ACCEPTED
            invitation.save(update_fields=['status'])

        messages.success(request, message)
        return redirect('matches:match_detail', pk=match.pk)


class MatchMessageCreateView(LoginRequiredMixin, View):
    """FR22 - Publish a message in the thread of a match."""

    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)
        detail_url = f"{reverse('matches:match_detail', kwargs={'pk': match.pk})}#match-chat"

        if not user_can_use_match_chat(match, request.user):
            messages.error(
                request,
                'Only the organizer and confirmed participants can use the match chat.',
            )
            return redirect(detail_url)

        if match.status == MatchStatus.CANCELLED:
            messages.error(
                request,
                'This match has been cancelled, so its chat is read-only.',
            )
            return redirect(detail_url)

        form = MatchMessageForm(request.POST)

        if form.is_valid():
            message = form.save(commit=False)
            message.match = match
            message.author = request.user
            message.save()
        else:
            messages.error(
                request,
                'The message cannot be empty or longer than 500 characters.',
            )

        return redirect(detail_url)


class MatchListView(ListView):
    """FR3 & FR12 - Browse and filter active matches."""

    model = Match
    template_name = 'matches/match_list.html'
    context_object_name = 'matches'

    def get_queryset(self):
        queryset = Match.objects.filter(status=MatchStatus.ACTIVE)

        location = self.request.GET.get('location', '').strip()
        if location:
            queryset = queryset.filter(location__icontains=location)

        skill_level = self.request.GET.get('skill_level', '').strip()
        if skill_level and skill_level in MatchSkillLevel.values:
            queryset = queryset.filter(skill_level=skill_level)

        date_str = self.request.GET.get('date', '').strip()
        if date_str:
            try:
                filter_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(date_time__date__gte=filter_date)
            except ValueError:
                pass

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        location_query = self.request.GET.get('location', '').strip()
        skill_level_query = self.request.GET.get('skill_level', '').strip()
        date_query = self.request.GET.get('date', '').strip()

        context['location_query'] = location_query
        context['skill_level_query'] = skill_level_query
        context['date_query'] = date_query
        context['skill_level_choices'] = MatchSkillLevel.choices
        context['is_filtered'] = bool(
            location_query or skill_level_query or date_query
        )
        return context


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

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.status == MatchStatus.CANCELLED:
            messages.error(request, 'Cancelled matches cannot be edited.')
            return redirect('matches:match_detail', pk=obj.pk)
        if obj.status == MatchStatus.CLOSED:
            messages.error(request, 'Closed matches cannot be edited.')
            return redirect('matches:match_detail', pk=obj.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """FR11 - Automatic replacement & FR14 - Match update notifications.

        If the organizer increases max_players, promote waiting players
        into the newly opened spots right away.
        Notify affected participants if relevant match fields were updated.
        """
        old_match = Match.objects.get(pk=self.object.pk)
        relevant_fields = ['title', 'date_time', 'location', 'max_players', 'skill_level', 'status']

        def _field_changed(field):
            old_val = getattr(old_match, field)
            new_val = getattr(form.instance, field)
            if isinstance(old_val, datetime) and isinstance(new_val, datetime):
                return old_val.replace(second=0, microsecond=0) != new_val.replace(second=0, microsecond=0)
            return old_val != new_val

        changed_fields = [f for f in relevant_fields if _field_changed(f)]

        response = super().form_valid(form)
        self.object.promote_from_waiting_list()

        if changed_fields:
            notify_match_update(self.object, changed_fields=changed_fields)

        return response


class MatchCancelView(LoginRequiredMixin, View):
    """FR9 - Cancel match by organizer."""

    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)

        if match.organizer_id != request.user.id:
            messages.error(request, 'Only the organizer can cancel this match.')
            return redirect('matches:match_detail', pk=match.pk)

        if match.status == MatchStatus.CANCELLED:
            messages.warning(request, 'This match is already cancelled.')
            return redirect('matches:match_detail', pk=match.pk)

        match.status = MatchStatus.CANCELLED
        match.save(update_fields=['status', 'updated_at'])

        notify_match_cancellation(request, match)
        messages.success(request, 'The match has been cancelled successfully.')

        return redirect('matches:match_detail', pk=match.pk)


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

        if match.status == MatchStatus.CANCELLED:
            messages.error(request, 'This match has been cancelled.')
            return redirect('matches:match_detail', pk=match.pk)

        if match.status == MatchStatus.CLOSED:
            messages.error(request, 'This match is closed and cannot accept new participants.')
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

            if match.status == MatchStatus.CANCELLED:
                messages.error(request, 'This match has been cancelled.')
                return redirect('matches:match_detail', pk=match.pk)

            if match.status == MatchStatus.CLOSED:
                messages.error(request, 'This match is closed and cannot accept new participants.')
                return redirect('matches:match_detail', pk=match.pk)

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


class MatchAttendanceView(LoginRequiredMixin, View):
    """FR1 - Confirm attendance for a match the player has joined."""

    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)

        if match.organizer_id == request.user.id:
            messages.error(request, 'The organizer cannot confirm attendance.')
            return redirect('matches:match_detail', pk=match.pk)

        if match.status == MatchStatus.CANCELLED:
            messages.error(request, 'This match has been cancelled.')
            return redirect('matches:match_detail', pk=match.pk)

        if match.has_started:
            messages.error(
                request,
                'Attendance cannot be confirmed after the match has started.',
            )
            return redirect('matches:match_detail', pk=match.pk)

        try:
            participant = MatchParticipant.objects.get(
                match=match,
                player=request.user,
                status=ParticipantStatus.CONFIRMED,
            )
        except MatchParticipant.DoesNotExist:
            messages.error(
                request,
                'Only confirmed participants can confirm attendance.',
            )
            return redirect('matches:match_detail', pk=match.pk)

        if participant.attendance_confirmed:
            messages.info(request, 'You have already confirmed attendance.')
            return redirect('matches:match_detail', pk=match.pk)

        participant.attendance_confirmed = True
        participant.save(update_fields=['attendance_confirmed', 'updated_at'])
        notify_attendance_confirmation(match, request.user)
        messages.success(request, 'Your attendance has been confirmed.')
        return redirect('matches:match_detail', pk=match.pk)


class MatchRequestJoinView(LoginRequiredMixin, View):
    """FR4 - Request to join a match that requires organizer approval."""

    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)

        if match.organizer_id == request.user.id:
            messages.error(request, 'You are the organizer of this match.')
            return redirect('matches:match_detail', pk=match.pk)

        if match.status == MatchStatus.CANCELLED:
            messages.error(request, 'This match has been cancelled.')
            return redirect('matches:match_detail', pk=match.pk)

        if match.status == MatchStatus.CLOSED:
            messages.error(request, 'This match is closed and cannot accept join requests.')
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

        if match.status == MatchStatus.CANCELLED:
            messages.error(
                request,
                'This match has been cancelled.',
            )
            return redirect('matches:match_detail', pk=match.pk)

        if match.status == MatchStatus.CLOSED:
            messages.error(request, 'This match is closed and cannot accept join requests.')
            return redirect('matches:match_detail', pk=match.pk)

        with transaction.atomic():
            match = Match.objects.select_for_update().get(pk=pk)

            if match.organizer_id != request.user.id:
                messages.error(
                    request,
                    'Only the organizer can accept join requests.',
                )
                return redirect('matches:match_detail', pk=match.pk)

            if match.status == MatchStatus.CLOSED:
                messages.error(request, 'This match is closed and cannot accept join requests.')
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
                    participant.attendance_confirmed = False
                    participant.save(
                        update_fields=['status', 'attendance_confirmed', 'updated_at']
                    )
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
        with transaction.atomic():
            match = get_object_or_404(
                Match.objects.select_for_update(),
                pk=pk,
            )
            participant = MatchParticipant.objects.select_for_update().filter(
                match=match,
                player=request.user,
                status__in=[ParticipantStatus.CONFIRMED, ParticipantStatus.WAITING],
            ).first()

            if not participant:
                messages.error(request, 'You are not currently part of this match.')
                return redirect('matches:match_detail', pk=match.pk)

            was_confirmed = participant.status == ParticipantStatus.CONFIRMED

            if was_confirmed and match.has_generated_teams:
                MatchTeamAssignment.objects.filter(match=match).delete()
                match.status = MatchStatus.ACTIVE
                match.save(update_fields=['status', 'updated_at'])

            participant.status = ParticipantStatus.LEFT
            participant.attendance_confirmed = False
            participant.save(
                update_fields=['status', 'attendance_confirmed', 'updated_at']
            )

            if was_confirmed:
                match.promote_from_waiting_list()
                message = 'You have left the match.'
            else:
                message = 'You have left the waiting list.'

        messages.success(request, message)
        return redirect('matches:match_detail', pk=match.pk)


class MatchTeamGenerationView(LoginRequiredMixin, View):
    """FR24 - Generate and persist teams for a match."""

    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)

        if match.organizer_id != request.user.id:
            messages.error(request, 'Only the organizer can generate teams.')
            return redirect('matches:match_detail', pk=match.pk)

        if request.POST.get('confirm') != 'yes':
            messages.error(request, 'Team generation requires confirmation.')
            return redirect('matches:match_detail', pk=match.pk)

        try:
            with transaction.atomic():
                match = Match.objects.select_for_update().get(pk=pk)

                if match.status == MatchStatus.CANCELLED:
                    raise TeamDistributionError('This match has been cancelled.')
                if match.status == MatchStatus.CLOSED:
                    raise TeamDistributionError('Teams have already been generated.')
                if match.has_started:
                    raise TeamDistributionError(
                        'Teams can only be generated before the match starts.'
                    )

                distribute_match_teams(match)
        except TeamDistributionError as error:
            messages.error(request, str(error))
            return redirect('matches:match_detail', pk=match.pk)

        messages.success(request, 'Teams have been generated successfully.')
        return redirect('matches:match_detail', pk=match.pk)
