# Cold Email Automation — Setup Guide
## For Soumya Kumari | Data Scientist & AI Engineer

---

## What This Does
Sends **62 personalized cold emails per day** to 1,842 HR contacts from your Excel file.
Runs 24/7 on a **free Render server** kept alive by **Upstash** pings.
Tracks every email in a database — if it crashes, it **resumes exactly where it stopped**.

---

## STEP 1 — Gmail App Password (5 minutes)

> ⚠️ You CANNOT use your normal Gmail password. Google requires an "App Password" for this.

1. Go to [myaccount.google.com](https://myaccount.google.com)
2. Click **Security** → **2-Step Verification** → Turn ON (if not already)
3. Go back to Security → scroll down → **App Passwords**
4. Select: App = **Mail**, Device = **Windows Computer**
5. Click **Generate** → Copy the 16-character password (e.g., `abcd efgh ijkl mnop`)

Save this — you'll need it in Step 3.

---

## STEP 2 — Push Code to GitHub (5 minutes)

```bash
# In your project folder (cold_email_automate), open PowerShell:

git init
git add .
git commit -m "Initial cold email system"
git branch -M main

# Create a new repo on github.com/new (name: cold-email-soumya)
# Then:
git remote add origin https://github.com/YOUR_USERNAME/cold-email-soumya.git
git push -u origin main
```

> ⚠️ Make sure `.env` is NOT pushed (it's in .gitignore). Only `.env.example` should be there.

---

## STEP 3 — Deploy to Render (5 minutes)

1. Go to [render.com](https://render.com) → Sign in with GitHub
2. Click **New +** → **Web Service**
3. Connect your `cold-email-soumya` GitHub repo
4. Settings:
   - Name: `cold-email-soumya`
   - Region: **Singapore**
   - Branch: `main`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 600`
   - Instance Type: **Free**
5. Scroll down to **Environment Variables** — add these:

| Key | Value |
|-----|-------|
| `GMAIL_USER` | `jhasoumya934@gmail.com` |
| `GMAIL_APP_PASSWORD` | `abcd efgh ijkl mnop` (your app password) |
| `API_KEY` | any random string like `soumya-email-secret-2026` |
| `DAILY_LIMIT` | `62` |

6. Click **Create Web Service**
7. Wait ~3 minutes for first deploy
8. Your dashboard URL will be: `https://cold-email-soumya.onrender.com`

---

## STEP 4 — Set Up Upstash (Keep Alive + Cron) (10 minutes)

Render's free tier **sleeps after 15 minutes**. Upstash will ping it every 10 minutes.

1. Go to [console.upstash.com](https://console.upstash.com) → Sign up free
2. Click **QStash** → **Schedules** tab → **New Schedule**

Add these 3 schedules:

### Schedule 1: Keep-Alive (every 10 minutes)
- URL: `https://cold-email-soumya.onrender.com/health`
- Cron: `*/10 * * * *`
- Method: GET
- Header: `X-API-Key: soumya-email-secret-2026`

### Schedule 2: Morning Batch (10:00 AM IST = 04:30 UTC)
- URL: `https://cold-email-soumya.onrender.com/api/send-batch?type=morning`
- Cron: `30 4 * * *`
- Method: POST
- Header: `X-API-Key: soumya-email-secret-2026`

### Schedule 3: Evening Batch (3:00 PM IST = 09:30 UTC)
- URL: `https://cold-email-soumya.onrender.com/api/send-batch?type=evening`
- Cron: `30 9 * * *`
- Method: POST
- Header: `X-API-Key: soumya-email-secret-2026`

---

## STEP 5 — Test (2 minutes)

1. Open your dashboard: `https://cold-email-soumya.onrender.com`
2. Click **"Send 3 Test Emails"** button
3. Check your Gmail inbox — you should receive 3 emails with different templates
4. Check [mail-tester.com](https://mail-tester.com) to verify spam score (aim for 8+/10)

If all 3 arrive in inbox (not spam) → you're live! 🎉

---

## STEP 6 — Monitor

| What to check | Where |
|---|---|
| Progress, stats | `https://cold-email-soumya.onrender.com` |
| Server alive | `https://cold-email-soumya.onrender.com/health` |
| Pause sending | Dashboard → "Pause Sending" button |
| Resume sending | Dashboard → "Resume Sending" button |
| Force a batch | Dashboard → "Trigger Batch Now" |

---

## How Many Days?

| Contacts | Per Day | Days |
|---|---|---|
| 1,842 | 62 | ~30 days |

Morning batch: **30 emails** (10:00 AM IST)
Evening batch: **32 emails** (3:00 PM IST)
Delay between emails: **90–240 seconds** (random, looks human)

---

## Troubleshooting

**Emails going to spam?**
- Check spam score at [mail-tester.com](https://mail-tester.com)
- Reduce DAILY_LIMIT to 40 in Render env vars

**Gmail authentication error?**
- Regenerate App Password at myaccount.google.com → Security → App Passwords

**Server not waking up?**
- Check Upstash QStash → confirm schedules are active
- Go to Render dashboard → check logs

**Resume not attaching?**
- The system auto-downloads from Google Drive on startup
- Check Render logs for "Resume downloaded" message
- If it fails, manually upload `resume.pdf` via Render's shell

---

## File Structure

```
cold_email_automate/
├── app.py                  ← Flask app + scheduler
├── config.py               ← Settings from env variables
├── database.py             ← SQLite contact tracker
├── email_engine.py         ← Gmail SMTP sender
├── email_templates.py      ← 5 personalized templates
├── requirements.txt        ← Python dependencies
├── Procfile                ← Render start command
├── render.yaml             ← Render deployment config
├── .env.example            ← Copy to .env for local testing
├── templates/
│   └── dashboard.html      ← Web dashboard UI
└── Company Wise HR Contacts - HR Contacts.xlsx
```
