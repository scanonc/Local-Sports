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

## Dependencies

`requirements.txt` only pins Django itself; `asgiref`, `sqlparse` and `tzdata` are internal dependencies that Django installs automatically (see the comments in `requirements.txt` for what each one is used for). We don't add any other third-party package - Bootstrap is loaded via CDN in the base template, not installed with pip.

If a new dependency is ever added, regenerate the file from inside the activated `venv` so it only reflects this project's packages:

```bash
pip install <package>
pip freeze > requirements.txt
```

`venv/` is excluded from version control via `.gitignore` - it is never pushed to GitHub, since anyone can recreate it locally from `requirements.txt`.
