import gettext
import re
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone, translation

from matches.models import (
    Match,
    MatchSkillLevel,
    MatchStatus,
    MatchVisibility,
)
from users.models import Notification

User = get_user_model()
SPANISH = {settings.LANGUAGE_COOKIE_NAME: 'es'}


class LanguageSwitchTests(TestCase):
    """The EN / ES button of the navbar and the Spanish translation of the pages."""

    @classmethod
    def setUpTestData(cls):
        cls.organizer = User.objects.create_user(
            username='organizer', email='organizer@example.com', password='testpass123',
            first_name='Olga', last_name='Organizer',
        )
        cls.player = User.objects.create_user(
            username='player', email='player@example.com', password='testpass123',
        )
        cls.match = Match.objects.create(
            organizer=cls.organizer,
            title='Friday game',
            date_time=timezone.now() + timedelta(days=2),
            location='Local field',
            skill_level=MatchSkillLevel.BEGINNER,
            max_players=6,
            visibility=MatchVisibility.PUBLIC,
        )

    def get(self, url, language=None, **extra):
        if language:
            self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = language
        return self.client.get(url, **extra)

    # --- the button -------------------------------------------------------

    def test_site_is_in_english_by_default(self):
        response = self.client.get(reverse('home'))

        self.assertContains(response, '<html lang="en">')
        self.assertContains(response, 'Browse matches')
        self.assertNotContains(response, 'Ver partidos')

    def test_browser_language_does_not_change_the_default(self):
        response = self.client.get(reverse('home'), headers={'accept-language': 'es-CO,es;q=0.9'})

        self.assertContains(response, 'Browse matches')
        self.assertNotContains(response, 'Ver partidos')

    def test_navbar_has_en_and_es_buttons_posting_to_set_language(self):
        response = self.client.get(reverse('matches:match_list'))

        self.assertContains(response, f'action="{reverse("set_language")}"')
        self.assertContains(response, 'name="language" value="en"')
        self.assertContains(response, 'name="language" value="es"')
        self.assertContains(response, 'name="next" value="/matches/"')

    def test_pressed_button_follows_the_current_language(self):
        english = self.client.get(reverse('home')).content.decode()
        spanish = self.get(reverse('home'), language='es').content.decode()

        self.assertRegex(english, r'value="en"[^>]*aria-pressed="true"')
        self.assertRegex(english, r'value="es"[^>]*aria-pressed="false"')
        self.assertRegex(spanish, r'value="es"[^>]*aria-pressed="true"')
        self.assertRegex(spanish, r'value="en"[^>]*aria-pressed="false"')

    def test_pressing_es_sets_the_cookie_and_returns_to_the_same_page(self):
        response = self.client.post(
            reverse('set_language'), {'language': 'es', 'next': '/matches/'},
        )

        self.assertRedirects(response, '/matches/', fetch_redirect_response=False)
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, 'es')

        page = self.client.get('/matches/')
        self.assertContains(page, '<html lang="es">')
        self.assertContains(page, 'Crear partido')

    def test_pressing_en_goes_back_to_english(self):
        self.client.post(reverse('set_language'), {'language': 'es', 'next': '/'})
        self.client.post(reverse('set_language'), {'language': 'en', 'next': '/'})

        page = self.client.get(reverse('home'))

        self.assertContains(page, '<html lang="en">')
        self.assertContains(page, 'Create match')

    def test_unknown_language_is_ignored(self):
        self.client.post(reverse('set_language'), {'language': 'xx', 'next': '/'})

        self.assertContains(self.client.get(reverse('home')), '<html lang="en">')

    def test_unknown_cookie_value_falls_back_to_english(self):
        page = self.get(reverse('home'), language='fr')

        self.assertContains(page, '<html lang="en">')

    def test_next_url_pointing_to_another_site_is_not_followed(self):
        response = self.client.post(
            reverse('set_language'), {'language': 'es', 'next': 'https://evil.example.com/'},
        )

        self.assertEqual(response.headers['Location'], '/')

    # --- translated pages -------------------------------------------------

    def test_home_page_in_spanish(self):
        page = self.get(reverse('home'), language='es')

        self.assertContains(page, 'Menos organizar, más jugar.')
        self.assertContains(page, 'Crear un partido')
        self.assertContains(page, 'Iniciar sesión')

    def test_match_list_in_spanish_translates_choices_and_filters(self):
        page = self.get(reverse('matches:match_list'), language='es')

        self.assertContains(page, 'Todos los niveles')
        self.assertContains(page, 'Principiante')
        self.assertContains(page, 'Filtrar')
        self.assertNotContains(page, 'All skill levels')

    def test_match_detail_in_spanish_for_visitor_and_organizer(self):
        url = reverse('matches:match_detail', args=[self.match.pk])

        visitor = self.get(url, language='es')
        self.assertContains(visitor, 'Información del partido')
        self.assertContains(visitor, 'Inicia sesión para unirte')

        self.client.force_login(self.organizer)
        organizer = self.get(url, language='es')
        self.assertContains(organizer, 'Editar partido')
        self.assertContains(organizer, 'Cancelar partido')
        self.assertContains(organizer, 'Generar enlace para compartir')
        self.assertNotContains(organizer, 'Edit match')

    def test_match_status_badge_uses_the_translated_label(self):
        self.match.status = MatchStatus.CANCELLED
        self.match.save()
        url = reverse('matches:match_detail', args=[self.match.pk])

        self.assertContains(self.get(url, language='es'), 'Cancelado')
        self.assertContains(self.get(url, language='en'), 'Cancelled')

    def test_blocktrans_with_variables_in_spanish(self):
        token = uuid.uuid4()
        Match.objects.filter(pk=self.match.pk).update(invite_token=token, invite_active=True)
        self.client.force_login(self.player)
        url = reverse('matches:match_join_via_link', args=[str(token)])

        page = self.get(url, language='es')

        self.assertContains(page, 'Organizado por')
        self.assertContains(page, '0 / 6 confirmados')
        self.assertNotContains(page, 'Organized by')

    def test_flash_messages_are_translated(self):
        self.client.force_login(self.player)
        url = reverse('matches:match_cancel', args=[self.match.pk])
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'es'

        response = self.client.post(url, follow=True)

        self.assertContains(response, 'Solo el organizador puede cancelar este partido.')
        self.assertNotContains(response, 'Only the organizer can cancel this match.')

    def test_flash_messages_stay_in_english_by_default(self):
        self.client.force_login(self.player)

        response = self.client.post(reverse('matches:match_cancel', args=[self.match.pk]), follow=True)

        self.assertContains(response, 'Only the organizer can cancel this match.')

    def test_form_validation_errors_are_translated(self):
        self.client.force_login(self.organizer)
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'es'
        future = (timezone.localtime() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')

        response = self.client.post(reverse('matches:match_create'), {
            'title': 'Odd', 'date_time': future, 'location': 'Field',
            'skill_level': 'beginner', 'max_players': 7, 'visibility': 'public',
        })

        self.assertContains(
            response, 'El número máximo de jugadores debe ser un número par entre 6 y 40.',
        )

    def test_profile_page_in_spanish(self):
        self.client.force_login(self.organizer)

        page = self.get(reverse('users:player_profile', args=[self.player.pk]), language='es')

        self.assertContains(page, 'Estadísticas del jugador')
        self.assertContains(page, 'Principiante')
        self.assertContains(page, 'Sin calificaciones')

    def test_django_own_texts_come_in_spanish_too(self):
        page = self.get(reverse('users:signup'), language='es')

        self.assertContains(page, 'Crear cuenta')

    def test_dates_use_the_active_language(self):
        url = reverse('matches:match_detail', args=[self.match.pk])
        months_es = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
                     'septiembre', 'octubre', 'noviembre', 'diciembre')

        page = self.get(url, language='es').content.decode().lower()

        self.assertTrue(any(month in page for month in months_es))

    def test_notification_date_is_written_in_the_active_language(self):
        notification = Notification.objects.create(user=self.player, message='Hello')
        Notification.objects.filter(pk=notification.pk).update(
            created_at=datetime(2026, 11, 5, 15, 30, tzinfo=dt_timezone.utc),
        )
        self.client.force_login(self.player)
        url = reverse('users:notifications')

        self.assertContains(self.get(url, language='en'), '05 Nov 2026, 10:30')
        self.assertContains(self.get(url, language='es'), '5 Nov 2026, 10:30')

    def test_choice_labels_are_lazy_and_follow_the_active_language(self):
        with translation.override('es'):
            self.assertEqual(str(MatchSkillLevel.ADVANCED.label), 'Avanzado')
        with translation.override('en'):
            self.assertEqual(str(MatchSkillLevel.ADVANCED.label), 'Advanced')


def parse_po(path):
    """Minimal .po reader: returns {(msgctxt, msgid): msgstr or [plural forms]}."""
    entries, current, field = {}, {}, None

    def flush():
        if 'msgid' in current and current['msgid'] != '':
            plural = [current[k] for k in sorted(k for k in current if k.startswith('msgstr['))]
            entries[(current.get('msgctxt'), current['msgid'])] = plural or current.get('msgstr', '')
        current.clear()

    for raw in open(path, encoding='utf-8'):
        line = raw.strip()
        if not line:
            flush(); field = None
            continue
        if line.startswith('#'):
            continue
        match = re.match(r'^(msgctxt|msgid_plural|msgid|msgstr\[\d\]|msgstr)\s+"(.*)"$', line)
        if match:
            field = match.group(1)
            if field == 'msgctxt' and current.get('msgid') is not None:
                flush()
            current[field] = match.group(2)
        elif line.startswith('"') and field:
            current[field] += line[1:-1]
    flush()
    return entries


class SpanishCatalogTests(SimpleTestCase):
    """The committed locale/es files must be complete and in sync."""

    po_path = settings.BASE_DIR / 'locale' / 'es' / 'LC_MESSAGES' / 'django.po'
    mo_path = settings.BASE_DIR / 'locale' / 'es' / 'LC_MESSAGES' / 'django.mo'

    def test_every_message_has_a_spanish_translation(self):
        entries = parse_po(self.po_path)
        untranslated = [
            msgid for (_ctx, msgid), msgstr in entries.items()
            if not msgstr or (isinstance(msgstr, list) and not all(msgstr))
        ]

        self.assertGreater(len(entries), 200)
        self.assertEqual(untranslated, [])

    def test_translations_keep_the_placeholders_of_the_original(self):
        placeholders = lambda text: sorted(re.findall(r'%\(\w+\)[sd]', text))
        for (_ctx, msgid), msgstr in parse_po(self.po_path).items():
            for form in (msgstr if isinstance(msgstr, list) else [msgstr]):
                self.assertEqual(placeholders(form), placeholders(msgid), msgid)

    def test_compiled_catalog_matches_the_po_file(self):
        with open(self.mo_path, 'rb') as handle:
            catalog = gettext.GNUTranslations(handle)

        for (ctx, msgid), msgstr in parse_po(self.po_path).items():
            if isinstance(msgstr, list):
                continue
            if ctx:
                self.assertEqual(catalog.pgettext(ctx, msgid), msgstr, msgid)
            else:
                self.assertEqual(catalog.gettext(msgid), msgstr, msgid)
