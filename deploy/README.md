# Deploying Local Sports on AWS EC2

Target: one Ubuntu 24.04 EC2 instance (AWS Academy Learner Lab or a regular AWS account).

```
Browser --HTTP:80--> nginx --127.0.0.1:8000--> gunicorn --> Django --> SQLite (db.sqlite3)
                       |
                       +-- /static/  (served directly from /srv/local-sports/staticfiles/)
```

Django 6 needs Python 3.12 or newer, which is what Ubuntu 24.04 ships. Do not pick Ubuntu 22.04.

## 1. Create the instance (AWS console)

1. Region: **N. Virginia (us-east-1)**. The Learner Lab only allows us-east-1 and us-west-2.
2. EC2 > Launch instance. Name: `local-sports`.
3. AMI: **Ubuntu Server 24.04 LTS**. Instance type: **t3.micro** (or t2.micro).
4. Key pair: `vockey` (Learner Lab) or create one.
5. Network settings > create a security group with:
   - SSH (22) from **Anywhere-IPv4 (0.0.0.0/0)**. The browser-based EC2 Instance Connect of step 2 connects
     from AWS's own address range, not from your IP, so **My IP** makes it fail. Access still needs the
     temporary key that Instance Connect pushes, so this is acceptable for a course lab. If you prefer a
     narrower rule, use the Instance Connect range of us-east-1, `18.206.107.24/29`.
   - HTTP (80) from **Anywhere (0.0.0.0/0)**
6. Storage: 8 to 16 GiB. Launch.
7. EC2 > Elastic IPs > Allocate Elastic IP address > Associate it with the instance.
   Without it the public IP changes every time the instance is stopped and started.

## 2. Connect

EC2 > Instances > select the instance > **Connect** > **EC2 Instance Connect** > Connect.
This opens a terminal in the browser, so no key file is needed.

## 3. Install and configure

```bash
sudo apt update
sudo apt install -y python3-venv git nginx

sudo mkdir /srv/local-sports
sudo chown ubuntu:ubuntu /srv/local-sports
git clone https://github.com/scanonc/Local-Sports.git /srv/local-sports
cd /srv/local-sports

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # copy the value
nano .env
```

In `.env` set the following (remove the `#` from the production lines):

```
RESEND_API_KEY=<your Resend key>
DEFAULT_FROM_EMAIL=Local Sports <onboarding@resend.dev>
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<the random value printed above>
DJANGO_ALLOWED_HOSTS=<the Elastic IP>
```

Save with `Ctrl+O`, `Enter`, and exit with `Ctrl+X`. Then:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

## 4. Start gunicorn (systemd)

```bash
sudo cp deploy/local-sports.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now local-sports
sudo systemctl status local-sports      # must say "active (running)"; leave with q
```

## 5. Start nginx

```bash
sudo cp deploy/nginx-local-sports.conf /etc/nginx/sites-available/local-sports
sudo ln -s /etc/nginx/sites-available/local-sports /etc/nginx/sites-enabled/local-sports
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t                           # must say "syntax is ok"
sudo systemctl restart nginx
```

Open `http://<Elastic IP>/` in a browser.

## Updating the deployed version

```bash
cd /srv/local-sports
git pull
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart local-sports
```

## AWS Academy Learner Lab notes

- A session lasts 4 hours. When it ends, running instances are stopped, and they normally start again the
  next time the lab is started. Check in EC2 > Instances that the state is **Running**.
- The site is only up while the lab session is running. Start the lab before a demo.
- With the Elastic IP associated, the address stays the same after a restart.
  The gunicorn and nginx services are enabled, so they start by themselves at boot.
- Stop the lab when you are done and keep an eye on the budget shown in the lab page.

## Troubleshooting

| Symptom | What to check |
|---|---|
| EC2 Instance Connect says "Failed to connect to your instance" | The security group must allow SSH (22) from `0.0.0.0/0` or `18.206.107.24/29`, not only from My IP; the instance must be Running |
| Browser cannot connect | Security group has HTTP 80 open; instance is Running; you used the Elastic IP |
| 502 Bad Gateway | gunicorn is not running: `sudo systemctl status local-sports` and `sudo journalctl -u local-sports -n 50` |
| 400 Bad Request | The address in the URL is not in `DJANGO_ALLOWED_HOSTS` in `.env`; fix it and `sudo systemctl restart local-sports` |
| Page without styles | Run `python manage.py collectstatic --noinput`; check `sudo tail /var/log/nginx/error.log` |
| 500 error | `sudo journalctl -u local-sports -n 100` |
| Service does not start after editing `.env` | `DJANGO_DEBUG=False` needs `DJANGO_SECRET_KEY`; read the error in `journalctl` |

## Known limitations

- The site is served over HTTP only. `python manage.py check --deploy` reports the HTTPS-related warnings
  (HSTS, SSL redirect, secure cookies) for this reason. To add HTTPS, a domain name is needed (for example a
  free DuckDNS name) plus Let's Encrypt; then set `DJANGO_CSRF_TRUSTED_ORIGINS=https://<domain>`.
- SQLite lives in `/srv/local-sports/db.sqlite3` on the instance disk. Back it up before destroying the instance.
- A single small instance is not meant for many concurrent users.
