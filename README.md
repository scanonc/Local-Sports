# Local Sports

Local Sports is a web application that simplifies the organization of recreational sports matches by connecting players with others who share similar skill levels, availability, and interests. Instead of relying on scattered WhatsApp groups or social media, users can create and join matches, manage teams, and receive recommendations through a statistics-based matchmaking system. Our goal with whis project is to make it easier for people to find compatible teammates and opponents, reduce the effort required to organize games, and encourage participation in recreational sports.

## Setup (local development)

We use a Python virtual environment (`venv`) so every teammate's machine installs the exact same dependencies, isolated from anything else installed globally.

```bash
# 1. Clone the repository
git clone https://github.com/scanonc/Local-Sports.git
cd Local-Sports

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Apply database migrations
python manage.py migrate

# 5. (Optional) Create an admin user
python manage.py createsuperuser

# 6. Run the test suite
python manage.py test

# 7. Run the development server
python manage.py runserver
```

Then open `http://127.0.0.1:8000/` in the browser.

## Languages (EN / ES)

The navbar has an **EN | ES** button. English is the default; the choice is stored in a cookie (the browser language is ignored on purpose). Translations live in `locale/es/` and the compiled `django.mo` is committed, so nothing extra has to be installed. See [`locale/README.md`](locale/README.md) to add or update texts.

## Demo data (`seed_demo`)

`python manage.py seed_demo` loads the demo data of the Sprint Review, like a Laravel seeder.

> **It deletes ALL the data of the database** (`flush`, superusers and sessions included) and loads the same data every time, so it can be run as many times as needed. Create a superuser again with `createsuperuser` if the admin panel is needed.

```bash
python manage.py seed_demo            # local machine (DEBUG on)
python manage.py seed_demo --force    # server (DEBUG off): --force is required
python manage.py seed_demo --password other-password   # another password for the demo users
```

It creates the users `organizer` and `player1` .. `player10` (password `prueba123`) and 14 matches. No email is sent: everything is created directly with the ORM, and the whole command runs in one transaction. At the end it prints the credentials, the matches, the level of every player, which user to log in with for each requirement, and the checks it made.

| Match | What it is for |
|---|---|
| A1 .. A5 | Five past matches (3 to 30 days ago) with teams, results and ratings: the profiles get different statistics and levels (FR13, FR23, FR23.1). |
| I | Ended yesterday with its result and no ratings: `player1` or `player2` can rate live (FR21). |
| B | Started a few hours ago, with teams and no result: the organizer gets the result pop-up (FR20). |
| C | In two days, exactly 10 confirmed and no teams: *Generate teams* (FR24). |
| D | Full (6/6) with two players on the waiting list (FR10, FR11). |
| E | Approval required, with two pending requests (FR4). |
| F | Open match with chat and a shareable link; `player10` has a pending invitation (FR5, FR15, FR16, FR22). |
| G | Advanced level: a player of a lower level cannot join (FR23.1). |
| H | Cancelled, with a read-only chat (FR9, FR22). |
| J | Upcoming, with `player1` confirmed: Add to Google Calendar (FR19). |

Levels: `player1` to `player3` Advanced, `player4` to `player7` Intermediate, `player8` and `player9` Beginner, and `player10` has no ratings. The password is public (it is in this file), so do not leave this data on a server that stays online.

## Email notifications

Match update and cancellation emails are sent through Resend. Copy `.env.example`
to `.env`, set `RESEND_API_KEY`, and use a sender that is verified in your Resend
account through `DEFAULT_FROM_EMAIL`. With a Resend test API key, the recipient
may also need to be the email address associated with that Resend account.

## Dependencies

`requirements.txt` lists the libraries the project needs (Django's own internal dependencies, such as `asgiref`, `sqlparse` and `tzdata`, are installed automatically):

| Library | Purpose |
|---|---|
| Django | Web framework |
| python-dotenv | Loads the settings of the `.env` file |
| resend | Sends the email notifications |
| gunicorn | Production web server (used in the AWS deployment) |

Bootstrap and the fonts are loaded from a CDN in the base template, so they are not installed with pip.

If a new library is needed, install it inside the activated `venv` and add its name to `requirements.txt`.

`venv/` is excluded from version control via `.gitignore` - it is never pushed to GitHub, since anyone can recreate it locally from `requirements.txt`.

## Deployment (AWS EC2)

The production setup (Ubuntu 24.04 on EC2, nginx, gunicorn and SQLite) and its step-by-step instructions are in [`deploy/README.md`](deploy/README.md). In production the settings are read from the `.env` file (`DJANGO_DEBUG`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`); for local development none of them is needed.
