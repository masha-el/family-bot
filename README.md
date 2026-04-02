# 🤖 FamilyBot

A Telegram bot for household coordination — shared reminders, Google Calendar integration, and birthday notifications for couples and small families.

Built with Python, deployed on GCP with Docker and a fully automated CI/CD pipeline via GitHub Actions.

---

## Features

- **Google Calendar sync** — each family member links their personal calendar; the bot reads upcoming events on demand
- **Reminders** — set date and time reminders via a guided conversation flow; APScheduler fires them at the right time
- **Birthday tracking** — add birthdays with automatic yearly Google Calendar events and morning notifications to all family members
- **Button-based UI** — reply keyboard for navigation, inline buttons for contextual actions; no commands to memorize
- **Admin error alerts** — unhandled exceptions are sent directly to the admin's Telegram chat
- **Daily database backup** — automated SQLite backup via GitHub Actions, stored as artifacts with 7-day rotation

---

## Who is this for?

FamilyBot works best for **couples or small families** who want a shared coordination space in Telegram.

Since the bot operates in a group chat, all messages and responses are visible to everyone in the group. This is intentional — the value comes from shared visibility, not privacy.

**Recommended setup:** Create one shared Google Calendar for household events (appointments, school pickups, family plans) and have each person link that shared calendar to the bot. This way:
- Any event one person adds is visible to everyone
- Reminders fire for all group members
- Birthday notifications reach the whole family

Individual personal calendars can also be linked, but keep in mind that all event details will be visible to everyone in the group chat.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Bot runtime | Python 3.11, python-telegram-bot v20+ |
| Scheduler | APScheduler |
| Database | SQLite |
| Calendar | Google Calendar API (service account) |
| Infra | GCP e2-micro VM, Docker, Docker Compose |
| CI/CD | GitHub Actions, GHCR |
| Networking | GCP Cloud NAT, IAP tunneling |

---

## Architecture

```
Family members (Telegram)
        │
        ▼
Python bot (polling mode)
        │
   ┌────┴────┐
   │         │
APScheduler  Google Calendar API
   │         │
   ▼         ▼
SQLite    Service Account
(reminders,
 birthdays,
 user mappings)
```

The bot runs in polling mode — no inbound ports, no public domain needed. All outbound traffic goes through GCP Cloud NAT. SSH access is via IAP tunnel only, with no port 22 exposed to the internet.

---

## Project Structure

```
family-bot/
├── bot/
│   ├── main.py              # Entry point, handler registration
│   ├── handlers.py          # Button-triggered command handlers
│   ├── conversations.py     # ConversationHandlers (remind, bday, register)
│   ├── callbacks.py         # Inline button press logic
│   ├── keyboards.py         # Reply and inline keyboard definitions
│   ├── scheduler.py         # APScheduler jobs (reminders, birthdays)
│   ├── calendar_client.py   # Google Calendar API wrapper
│   └── database.py          # SQLite operations and schema
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── .github/
    └── workflows/
        ├── deploy.yml       # Build, push, deploy on push to main
        └── backup.yml       # Daily SQLite backup
```

---

## Bot Commands

| Button / Command | Description |
|---|---|
| 🗓️ Events | Shows your next 7 days from Google Calendar |
| ⏰ Remind me | Guided flow to set a reminder (date → time → message) |
| 🎂 Birthdays | View, add, and delete birthdays |
| 📋 Reminders | View and delete upcoming reminders |
| ⚙️ Settings | Link your Google Calendar |
| ❓ Help | List of available commands |

---

## CI/CD Pipeline

Every push to `main` triggers:

1. **Build** — Docker image built and pushed to GitHub Container Registry (`ghcr.io`)
2. **Deploy** — GitHub Actions SSHes into the GCP VM via IAP tunnel, pulls the new image, restarts the container

```yaml
# Simplified deploy step
gcloud compute ssh $VM_USER@$INSTANCE \
  --tunnel-through-iap \
  --ssh-key-file=/tmp/deploy_key \
  -- "docker compose pull && docker compose up -d"
```

A separate `backup.yml` workflow runs daily at 02:00 UTC, extracts the SQLite database from the Docker volume, and uploads it as a GitHub Actions artifact with 7-day retention.

---

## Setup

### Prerequisites

- GCP project with a VM instance (e2-micro works fine)
- Google Cloud NAT configured for outbound internet access
- GitHub repository with Actions enabled
- Telegram bot token from @BotFather

### 1. Google Calendar Setup

Create a GCP service account:

```bash
# Enable Calendar API
gcloud services enable calendar-api

# Create service account
gcloud iam service-accounts create family-bot-sa \
  --display-name="Family Bot Service Account"

# Download credentials
gcloud iam service-accounts keys create credentials.json \
  --iam-account=family-bot-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

Each family member shares their Google Calendar with the service account email and grants "Make changes to events" permission.

### 2. Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
GOOGLE_CREDENTIALS_PATH=/app/credentials.json
DB_PATH=/app/data/family_bot.db
REMINDER_CHECK_INTERVAL_MINUTES=5
BIRTHDAY_CHECK_HOUR=8
TZ=Asia/Jerusalem
ADMIN_TELEGRAM_ID=your_telegram_id
```

### 3. VM Setup

```bash
# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# Create bot directory
sudo mkdir -p /opt/family-bot
sudo chown -R $USER:docker /opt/family-bot

# Copy files to VM
gcloud compute scp credentials.json INSTANCE:/opt/family-bot/ --tunnel-through-iap
gcloud compute scp docker-compose.yml INSTANCE:/opt/family-bot/ --tunnel-through-iap
gcloud compute scp .env INSTANCE:/opt/family-bot/ --tunnel-through-iap
```

### 4. GitHub Actions Secrets

| Secret | Value |
|---|---|
| `GCP_SA_KEY` | Service account JSON for GitHub Actions deployment |
| `GCP_DEPLOY_SSH_KEY` | Private SSH key registered with the deployment service account |
| `GCP_INSTANCE_NAME` | VM instance name |
| `GCP_ZONE` | GCP zone (e.g. `us-central1-a`) |
| `GCP_VM_USER` | OS Login username (`sa_XXXX`) |
| `GCP_VM_BOT_DIR` | `/opt/family-bot` |
| `CR_PAT` | GitHub Personal Access Token with `read:packages` scope |

### 5. First Deploy

Push to `main` — GitHub Actions builds the image and deploys automatically.

```bash
git push origin main
# Watch: GitHub repo → Actions tab
```

---

## User Onboarding

Each family member:

1. Opens the bot in Telegram and taps **Start**
2. Taps ⚙️ **Settings** and follows the guided flow to link their Google Calendar
3. Shares their Google Calendar with the service account email (one-time setup)

To find the Calendar ID: Google Calendar → Settings → click calendar name → Integrate calendar → copy Calendar ID.

---

## Local Development

```bash
# Clone and set up
git clone https://github.com/YOUR_USERNAME/family-bot.git
cd family-bot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy and fill in env file
cp .env.example .env

# Run locally
python -m bot.main
```

---

## Monitoring

```bash
# Live logs
docker compose -f /opt/family-bot/docker-compose.yml logs -f

# Container stats
docker stats family-bot-bot-1

# VM memory
free -h
```

---

## Security

- No inbound ports open — bot runs in polling mode
- SSH access via GCP IAP tunnel only (no port 22 exposed)
- `credentials.json` and `.env` owned by the deployment service account with `chmod 600`
- Sensitive files never committed — `.gitignore` covers `.env`, `credentials.json`, and `*.db`
- Docker named volume for SQLite persistence across deployments

---

## License

MIT