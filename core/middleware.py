from django.conf import settings
from django.middleware.locale import LocaleMiddleware
from django.utils import translation


class CookieLocaleMiddleware(LocaleMiddleware):
    """Pick the language only from the cookie set by the EN / ES button.

    Django's LocaleMiddleware also reads the browser's Accept-Language header,
    which would show the site in Spanish to anyone whose browser is in Spanish.
    Here the site stays in LANGUAGE_CODE (English) until the user presses ES.
    To follow the browser language instead, use
    'django.middleware.locale.LocaleMiddleware' in settings.MIDDLEWARE.
    """

    def process_request(self, request):
        language = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if language not in dict(settings.LANGUAGES):
            language = settings.LANGUAGE_CODE
        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()
