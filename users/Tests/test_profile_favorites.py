from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from users.models import FavoritePlayer

User = get_user_model()


class ProfileFavoritesTests(TestCase):
    """FR17 - favorite players inside the profile and a link in the account menu."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='ana', email='ana@example.com', password='testpass123',
            first_name='Ana', last_name='Torres',
        )
        cls.friend = User.objects.create_user(
            username='luis', email='luis@example.com', password='testpass123',
            first_name='Luis', last_name='Gomez',
        )
        cls.stranger = User.objects.create_user(
            username='marta', email='marta@example.com', password='testpass123',
        )

    def own_profile(self):
        return reverse('users:player_profile', args=[self.user.pk])

    def profile_of(self, player):
        return reverse('users:player_profile', args=[player.pk])

    # --- own profile: the favorites list ----------------------------------

    def test_own_profile_lists_my_favorite_players(self):
        FavoritePlayer.objects.create(user=self.user, favorite=self.friend)
        self.client.force_login(self.user)

        response = self.client.get(self.own_profile())

        self.assertContains(response, 'id="favorite-players"')
        self.assertContains(response, 'Luis Gomez')
        self.assertContains(response, f'href="{self.profile_of(self.friend)}"')
        self.assertEqual(response.context['favorite_players'], [self.friend])

    def test_own_profile_has_a_remove_button_that_returns_to_the_profile(self):
        FavoritePlayer.objects.create(user=self.user, favorite=self.friend)
        self.client.force_login(self.user)

        page = self.client.get(self.own_profile())
        self.assertContains(page, f'action="{reverse("users:favorite_toggle", args=[self.friend.pk])}"')
        self.assertContains(page, f'name="next" value="{self.own_profile()}"')

        response = self.client.post(
            reverse('users:favorite_toggle', args=[self.friend.pk]), {'next': self.own_profile()},
        )

        self.assertRedirects(response, self.own_profile())
        self.assertFalse(FavoritePlayer.objects.filter(user=self.user, favorite=self.friend).exists())

    def test_own_profile_without_favorites_shows_an_empty_state(self):
        self.client.force_login(self.user)

        response = self.client.get(self.own_profile())

        self.assertContains(response, "You haven't added any favorite players yet.")
        self.assertContains(response, 'Use the star next to a player in a match')
        self.assertEqual(response.context['favorite_players'], [])

    def test_own_profile_does_not_list_other_peoples_favorites(self):
        FavoritePlayer.objects.create(user=self.stranger, favorite=self.friend)
        self.client.force_login(self.user)

        response = self.client.get(self.own_profile())

        self.assertNotContains(response, 'Luis Gomez')
        self.assertEqual(response.context['favorite_players'], [])

    def test_own_profile_has_no_favorite_button_for_yourself(self):
        self.client.force_login(self.user)

        response = self.client.get(self.own_profile())

        self.assertNotContains(response, 'profile-favorite-button')
        self.assertTrue(response.context['is_own_profile'])

    # --- someone else's profile: the star ---------------------------------

    def test_another_profile_offers_to_add_the_player(self):
        self.client.force_login(self.user)

        response = self.client.get(self.profile_of(self.friend))

        self.assertContains(response, 'Add to favorites')
        self.assertNotContains(response, 'Remove from favorites')
        self.assertFalse(response.context['is_favorite'])
        self.assertContains(response, f'name="next" value="{self.profile_of(self.friend)}"')

    def test_another_profile_offers_to_remove_a_favorite_player(self):
        FavoritePlayer.objects.create(user=self.user, favorite=self.friend)
        self.client.force_login(self.user)

        response = self.client.get(self.profile_of(self.friend))

        self.assertContains(response, 'Remove from favorites')
        self.assertNotContains(response, 'Add to favorites')
        self.assertTrue(response.context['is_favorite'])

    def test_star_on_a_profile_adds_the_player_and_comes_back(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('users:favorite_toggle', args=[self.friend.pk]),
            {'next': self.profile_of(self.friend)},
        )

        self.assertRedirects(response, self.profile_of(self.friend))
        self.assertTrue(FavoritePlayer.objects.filter(user=self.user, favorite=self.friend).exists())

    def test_another_profile_never_shows_that_players_favorites(self):
        FavoritePlayer.objects.create(user=self.friend, favorite=self.stranger)
        self.client.force_login(self.user)

        response = self.client.get(self.profile_of(self.friend))

        self.assertNotContains(response, 'id="favorite-players"')
        self.assertNotIn('favorite_players', response.context)

    def test_profile_still_requires_login(self):
        response = self.client.get(self.own_profile())

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('users:login'), response['Location'])

    # --- account menu and favorites page -----------------------------------

    def test_account_menu_links_to_the_favorites_page(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('home'))

        self.assertContains(response, f'href="{reverse("users:favorites")}"')
        self.assertContains(response, 'Favorites</a>')

    def test_visitor_menu_has_no_favorites_link(self):
        response = self.client.get(reverse('home'))

        self.assertNotContains(response, f'href="{reverse("users:favorites")}"')

    def test_favorites_page_names_link_to_the_profile(self):
        FavoritePlayer.objects.create(user=self.user, favorite=self.friend)
        self.client.force_login(self.user)

        response = self.client.get(reverse('users:favorites'))

        self.assertContains(response, f'href="{self.profile_of(self.friend)}"')

    # --- Spanish ------------------------------------------------------------

    def test_profile_favorites_in_spanish(self):
        FavoritePlayer.objects.create(user=self.user, favorite=self.friend)
        self.client.force_login(self.user)
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'es'

        own = self.client.get(self.own_profile())
        other = self.client.get(self.profile_of(self.friend))
        menu = self.client.get(reverse('home'))

        self.assertContains(own, 'Jugadores favoritos')
        self.assertNotContains(own, 'Favorite players')
        self.assertContains(other, 'Quitar de favoritos')
        self.assertContains(menu, 'Favoritos</a>')

    def test_empty_favorites_hint_in_spanish(self):
        self.client.force_login(self.user)
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'es'

        response = self.client.get(self.own_profile())

        self.assertContains(response, 'Aún no has agregado jugadores favoritos.')
        self.assertContains(response, 'Usa la estrella junto a un jugador en un partido')
