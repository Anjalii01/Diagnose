# Disease Prediction System — Full Stack (with Auth & Security)

A full-stack disease prediction app: React frontend, FastAPI backend, a real
database, JWT-based authentication, rate limiting, and per-user history with
soft-delete recovery.

```
disease-prediction-app/
├── backend/
│   ├── data/                  CSV source data + the trained model (svc.pkl)
│   ├── config.py              Centralized settings, loaded from .env
│   ├── database.py            DB connection (SQLite by default, Postgres-ready)
│   ├── models.py              SQLAlchemy tables: User, PredictionHistory, etc.
│   ├── auth.py                Password hashing + JWT creation/verification
│   ├── schemas.py             Pydantic request/response shapes
│   ├── migrate_csv_to_db.py   One-time script: CSVs -> database
│   ├── main.py                FastAPI app — all endpoints
│   ├── .env.example           Template for required environment variables
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── AuthContext.jsx     Login/signup/logout/token state
    │   ├── LoginScreen.jsx     Auth UI
    │   ├── App.jsx             Main UI (symptom picker, results, history)
    │   ├── HistoryPanel.jsx    Search/filter/paginate/delete/export history
    │   ├── index.css
    │   └── main.jsx
    ├── index.html
    ├── package.json
    └── vite.config.js
```

---

## Step-by-step setup, from absolute zero

### 0. Prerequisites
- **Python 3.10+** — https://www.python.org/downloads/
- **Node.js 18+** — https://nodejs.org/

```bash
python --version
node --version
```

### 1. Unzip and open a terminal in the project folder.

### 2. Backend — install dependencies
```bash
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Backend — set up your environment file
```bash
# Windows:
copy .env.example .env
# Mac/Linux:
cp .env.example .env
```
Open `.env` and replace `SECRET_KEY` with a real random value:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
Paste the output into `.env` as `SECRET_KEY=...`. This key signs login
tokens — without a fixed one, everyone gets logged out every time the
server restarts.

### 4. Backend — load the CSV data into the database
```bash
python migrate_csv_to_db.py
```

### 5. Backend — start the API server
```bash
uvicorn main:app --reload
```
Visit **http://localhost:8000/docs** to try every endpoint interactively.

### 6. Frontend — install and run
Open a **second terminal**:
```bash
cd frontend
npm install
npm run dev
```
Open **http://localhost:5173**. You'll land on a login screen — sign up
with any email/password (min 8 characters, at least one letter and one
number), and you're in.

---

## What changed in this version (and why it matters for interviews)

| Before | Now |
|---|---|
| "User" was a random browser ID in localStorage — anyone could spoof it | Real accounts: email + bcrypt-hashed password, JWT-based login |
| Anyone could call `/predict` or read anyone's history | Every sensitive endpoint requires a valid bearer token; history is scoped to `current_user.id` server-side, not a client-supplied ID |
| CORS was `allow_origins=["*"]` (any website could call the API) | CORS restricted to explicit origins set in `.env` |
| No rate limiting — `/predict` or `/auth/login` could be spammed | `slowapi` rate limits auth (10/min) and prediction (20/min) per IP |
| Secrets (JWT key, DB url) didn't exist / weren't configurable | All secrets loaded from `.env`, never hardcoded, `.env` is gitignored |
| Deleting history was permanent | Soft delete: entries are hidden, not destroyed, and can be restored (the UI shows a 6-second "undo" after every delete) |
| Model gave one hard prediction, no sense of certainty | `/predict` returns a confidence score (0-100%) and the top 3 candidate diseases, derived from the SVM's decision function |
| Passwords/login didn't exist | Passwords are validated for strength (8+ chars, letter + number) and hashed with bcrypt — never stored in plain text |

## Honest remaining limitations

No system is "fully secure" — being able to name what's still missing is
itself a strong signal in an interview. These are the trade-offs left in
this build:

- **No email verification or password reset flow.** Signing up only checks
  that the email is well-formed, not that it's real or owned by the
  signer. Adding email verification (a confirmation link) and a "forgot
  password" flow would be the natural next step.
- **Tokens are stored in `localStorage`, not an httpOnly cookie.** This is
  simpler to implement but is technically vulnerable to XSS (a malicious
  script on the page could read the token). For a production deployment,
  httpOnly cookies + CSRF protection is the more robust pattern.
- **No refresh tokens.** Sessions expire after `ACCESS_TOKEN_EXPIRE_MINUTES`
  (default 60) and the user simply has to log in again — there's no silent
  refresh.
- **SQLite under concurrent writes.** Fine for a single demo user; under
  real concurrent traffic, switch to Postgres (see below) — this project
  is already built for that with a one-line config change.
- **Confidence scores are an approximation, not calibrated probabilities.**
  The underlying SVM was trained without `probability=True`, so the score
  shown is derived from its decision function via softmax — useful for
  relative ranking, not a clinically meaningful probability.
- **No admin/moderation tooling.** There's no way to view or manage all
  users from an admin panel; everything is self-service.

If asked about any of these in an interview, the honest answer ("I scoped
this deliberately and know what the next iteration would add") tends to
land better than claiming the project has zero gaps.

---

## Switching from SQLite to PostgreSQL / Supabase (for deployment)

1. Create a free Postgres database on [Supabase](https://supabase.com).
2. Copy the connection string.
3. In `backend/.env`, set:
   ```
   DATABASE_URL=postgresql://postgres:<password>@<host>:5432/postgres
   ```
4. Install the driver:
   ```bash
   pip install psycopg2-binary
   ```
5. Re-run the migration:
   ```bash
   python migrate_csv_to_db.py
   ```
6. Restart the server — `database.py` picks up the new URL automatically.

## Deploying

- **Backend**: Render or Railway (FastAPI deploys directly from a GitHub
  repo). Set `SECRET_KEY`, `DATABASE_URL`, and `CORS_ORIGINS` as
  environment variables in the host's dashboard — never commit `.env`.
- **Database**: Supabase (managed Postgres).
- **Frontend**: Vercel or Netlify. Build command `npm run build`, output
  directory `dist`. Set `VITE_API_BASE` to your deployed backend's URL.
- Once deployed, set `CORS_ORIGINS` on the backend to your real frontend
  URL (e.g. `https://your-app.vercel.app`) — not `*`.

---

## Admin dashboard — seeing aggregate usage

By default every account is a regular user who can only see their own
history — that's intentional, for privacy. To see **everyone's** activity
(total users, total diagnoses run, most commonly predicted diseases, a
searchable list of every user and every prediction across the whole app),
you need an admin account.

**No one is an admin by default** — including the first person to sign up.
This is deliberate: it stops a stranger from registering and granting
themselves dashboard access. To promote an account to admin, you need
direct access to the server/database, and run:

```bash
cd backend
python make_admin.py you@example.com
```

That account must already exist (sign up normally first). After running
the script, log out and back in on the frontend — a new "03 / admin" tab
appears, showing:

- **Stat cards** — total users, total diagnoses run, and how many of each
  happened in the last 7 days.
- **Most predicted conditions** — a ranked bar chart of which diseases
  come up most often across all users.
- **Users tab** — every registered account, searchable by email, with
  each person's diagnosis count and join date.
- **All diagnoses tab** — every prediction ever run, searchable by disease
  name or filterable by a specific user's email.

All of this is protected server-side by the `require_admin` dependency in
`auth.py` — a non-admin token gets a 403 even if they find the admin API
URLs directly, not just a hidden UI tab.

---

## API reference

| Method | Endpoint | Auth required | Description |
|---|---|---|---|
| GET | `/` | No | Health check |
| GET | `/symptoms` | No | All symptoms + severity weights |
| POST | `/auth/signup` | No | Create an account, returns a token |
| POST | `/auth/login` | No | Log in, returns a token |
| GET | `/auth/me` | Yes | Current logged-in user's info |
| POST | `/predict` | Yes | Body: `{"symptoms": [...]}` → prediction, confidence, top 3 candidates, description, precautions, medications, diet, workout |
| GET | `/history` | Yes | Your own history. Query params: `search`, `start_date`, `end_date`, `skip`, `limit` |
| DELETE | `/history/{id}` | Yes | Soft-delete one entry (recoverable) |
| POST | `/history/{id}/restore` | Yes | Undo a soft-delete |
| DELETE | `/history` | Yes | Soft-delete all of your history |
| GET | `/history/export` | Yes | Download your history as `?format=csv` or `?format=pdf` |
| GET | `/admin/stats` | Admin only | Aggregate counts + top predicted diseases |
| GET | `/admin/users` | Admin only | All users, searchable by email, with each user's diagnosis count |
| GET | `/admin/predictions` | Admin only | Every prediction across all users, filterable by disease/user/date |

All protected endpoints require an `Authorization: Bearer <token>` header,
which the frontend handles automatically once you're logged in. Admin
endpoints additionally require the account to have `is_admin = true` (see
above) — a regular logged-in user gets a 403, not just a hidden UI.
