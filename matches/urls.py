from django.urls import path

from .views import MatchCreateView, MatchDetailView, MatchListView, MatchUpdateView

app_name = 'matches'

urlpatterns = [
    path('', MatchListView.as_view(), name='match_list'),
    path('create/', MatchCreateView.as_view(), name='match_create'),
    path('<int:pk>/', MatchDetailView.as_view(), name='match_detail'),
    path('<int:pk>/edit/', MatchUpdateView.as_view(), name='match_update'),
]