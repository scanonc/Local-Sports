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
