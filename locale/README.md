# Translations (EN / ES)

Local Sports is written in English and translated to Spanish. The visitor picks the
language with the **EN | ES** button of the navbar (a `POST` to Django's `set_language`
view). The choice is saved in the `django_language` cookie; without it the site is in
English, whatever the browser language is (`core.middleware.CookieLocaleMiddleware`).

```
locale/es/LC_MESSAGES/django.po   <- source of the Spanish texts (edit this one)
locale/es/LC_MESSAGES/django.mo   <- compiled version that Django reads (committed)
```

The `.mo` file is committed on purpose, so running or deploying the project does **not**
need GNU gettext.

## How texts are marked in the code

| Where | How |
|---|---|
| Templates | `{% load i18n %}` and `{% trans "Text" %}` or `{% blocktrans %}...{% endblocktrans %}` (variables, plurals) |
| Views and services (run per request) | `from django.utils.translation import gettext as _` |
| Models and forms (run at import time) | `from django.utils.translation import gettext_lazy as _` |
| Date formats | `{{ value\|date:_("d M Y, H:i") }}`, so Spanish can reorder day and month |

## Adding or changing a text

1. Wrap the English text as shown above.
2. Regenerate the catalog. On a machine with GNU gettext (Linux/macOS, or Windows with
   gettext installed):

   ```bash
   python manage.py makemessages -l es --no-location --no-obsolete
   ```

   then write the Spanish text in the empty `msgstr ""` of `django.po` and compile:

   ```bash
   python manage.py compilemessages
   ```

   Without gettext you can edit `django.po` by hand and compile it with the `polib`
   package (`pip install polib`):

   ```bash
   python -c "import polib; polib.pofile('locale/es/LC_MESSAGES/django.po').save_as_mofile('locale/es/LC_MESSAGES/django.mo')"
   ```
3. Commit **both** `django.po` and `django.mo`.
4. Run `python manage.py test core.tests.test_language_switch`. It fails if a message has
   no Spanish text, if a `%(name)s` placeholder was lost, or if the `.mo` is out of date.

## Known limitation

Notifications saved in the database and the emails sent through Resend are written in
English: they are created once, when the recipient's language is not known. Everything
shown directly on a page (labels, buttons, messages after an action, form errors, dates)
follows the selected language, as do Django's own texts (login errors, admin).
