import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


def load_settings(**env):
    """Import config.settings in a fresh interpreter with the given environment."""
    environment = {
        key: value for key, value in os.environ.items()
        if not key.startswith('DJANGO_')
    }
    environment['DJANGO_SETTINGS_MODULE'] = 'config.settings'
    environment.update(env)
    # Ignore the real .env file so the result only depends on the given environment.
    script = (
        'import dotenv, json;'
        'dotenv.load_dotenv = lambda *args, **kwargs: False;'
        'import config.settings as s;'
        'print(json.dumps([s.DEBUG, s.ALLOWED_HOSTS, s.CSRF_TRUSTED_ORIGINS]))'
    )
    return subprocess.run(
        [sys.executable, '-c', script],
        cwd=settings.BASE_DIR,
        env=environment,
        capture_output=True,
        text=True,
    )


class ProductionSettingsTests(SimpleTestCase):
    def test_debug_off_requires_a_secret_key(self):
        result = load_settings(DJANGO_DEBUG='False')

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DJANGO_SECRET_KEY must be set', result.stderr)

    def test_production_values_are_read_from_the_environment(self):
        result = load_settings(
            DJANGO_DEBUG='False',
            DJANGO_SECRET_KEY='a-real-secret-for-this-test',
            DJANGO_ALLOWED_HOSTS='203.0.113.10, example.com',
            DJANGO_CSRF_TRUSTED_ORIGINS='https://example.com',
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            '[false, ["203.0.113.10", "example.com"], ["https://example.com"]]',
        )

    def test_development_defaults_need_no_environment(self):
        result = load_settings()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '[true, [], []]')

    def test_static_files_are_collected_into_staticfiles(self):
        self.assertEqual(settings.STATIC_ROOT, settings.BASE_DIR / 'staticfiles')
