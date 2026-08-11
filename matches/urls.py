from django.urls import path

from .views import (
    MatchCreateView,
    MatchDetailView,
    MatchJoinView,
    MatchLeaveView,
    MatchListView,
    MatchRequestAcceptView,
    MatchRequestJoinView,
    MatchRequestRejectView,
    MatchUpdateView,
)

app_name = 'matches'

urlpatterns = [
    path('', MatchListView.as_view(), name='match_list'),
    path('create/', MatchCreateView.as_view(), name='match_create'),
    path('<int:pk>/', MatchDetailView.as_view(), name='match_detail'),
    path('<int:pk>/edit/', MatchUpdateView.as_view(), name='match_update'),
    path('<int:pk>/join/', MatchJoinView.as_view(), name='match_join'),
    path('<int:pk>/request-join/', MatchRequestJoinView.as_view(), name='match_request_join'),
    path('<int:pk>/requests/<int:request_id>/accept/',MatchRequestAcceptView.as_view(),name='match_request_accept',),
    path('<int:pk>/requests/<int:request_id>/reject/',MatchRequestRejectView.as_view(),name='match_request_reject',),
    path('<int:pk>/leave/', MatchLeaveView.as_view(), name='match_leave'),
]