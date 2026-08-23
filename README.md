<div align="center">

# 📊 AttendanceDash Pro

### Smart Attendance Intelligence Platform for SRMCEM Students

A modern attendance management platform for **Shri Ramswaroop Memorial College of Engineering & Management (SRMCEM)** students that helps track attendance, forecast eligibility, optimize attendance strategy, and monitor quiz readiness through an analytics-driven dashboard.

<p>
  <img src="https://img.shields.io/badge/version-2.x-blue" alt="Version">
  <img src="https://img.shields.io/badge/status-active-success" alt="Status">
  <img src="https://img.shields.io/badge/PWA-supported-purple" alt="PWA">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

</div>

---

# 📖 Overview

AttendanceDash Pro is a full-stack attendance intelligence platform built on **PostgreSQL + FastAPI + JWT + Next.js**. It combines attendance tracking, forecasting, quiz eligibility analysis, attendance optimization, calendar/event management, laboratory tracking, notifications, and analytics into a single authenticated dashboard.

The project has evolved from a Firebase-era single-page JavaScript application into a modular attendance intelligence platform with a dedicated calculation engine, a PostgreSQL-backed API, and Progressive Web App support.

---

# 🏗 Current Architecture

```text
PostgreSQL
    ↓
FastAPI (SQLAlchemy + Alembic)
    ↓
JWT-authenticated API (/api/v1)
    ↓
Next.js (TypeScript + React)
    ↓
React UI
```

| Layer | Technology |
|---|---|
| Frontend | Next.js, TypeScript, React |
| Backend | FastAPI, Python |
| Database | PostgreSQL |
| ORM / Migrations | SQLAlchemy, Alembic |
| Authentication | JWT + PostgreSQL-native credentials (PBKDF2 password hashing) |
| Firebase | **RETIRED — no longer used by the active application** |

**Authentication flow:** login/registration is PostgreSQL-native. The backend verifies
the roll-number/password pair, issues a signed JWT, and every protected endpoint
resolves the authenticated user from the database (`get_current_user`). Authorization
roles (STUDENT / ADMIN) are resolved from PostgreSQL per request.

**Engines** (attendance, eligibility, calendar, analytics) remain authoritative
backend systems — the frontend renders engine output and never recomputes domain math.

---

# ✨ Features

- 📚 Subject-wise attendance tracking (Present / Absent / Pending)
- 📈 Attendance forecasting and optimization
- 🎯 Quiz eligibility engine (SRMCEM rules, per-cycle thresholds)
- 📅 Calendar with closures, events, and working-day resolution
- 🗓 Event management (holidays, extra classes, quiz days)
- 🧪 Laboratory experiment tracking and signatures
- 🔔 Notifications (class reminders, quiz approaching, threshold alerts)
- 📊 Analytics overview and per-subject intelligence
- 🎛 User preferences (reminders, auto-mark, week start)
- 📱 Progressive Web App (installable, offline-capable shell)
- 🔐 JWT authentication with ADMIN/STUDENT roles

---

# 📂 Repository Layout

```text
AttendanceDashPro/
├── backend/          FastAPI application (app/, alembic/, scripts/)
├── frontend/         Next.js application (src/, public/ — incl. the active PWA)
├── docs/             Project documentation (incl. historical reports)
├── prompts/          AI agent prompt templates
├── timetable.json    Canonical academic baseline data (used by backend seed/verify scripts)
└── start-dev.ps1 / stop-dev.ps1 / docker-compose.yml   Canonical dev workflow
```

The active application surface is `frontend/` + `backend/`. The original Firebase-era
legacy web application and legacy PWA (root `index.html`, `js/`, `css/`, `assets/`,
root `manifest.json`, root `service-worker.js`, `offline.html`) have been retired
(Phase 15). The current **Next.js PWA** (Phase 13, in `frontend/public/`) is the
active PWA.

---

# 🚀 Run Locally (Canonical Development Workflow)

**Prerequisites:**
- [Docker Desktop](https://www.docker.com/products/docker-desktop) installed and **running**
  (PostgreSQL runs inside a Docker container — Docker must be up before `start-dev.ps1`)
- Python virtual environment (`backend\.venv`)
  ```powershell
  python -m venv backend\.venv
  backend\.venv\Scripts\pip install -r backend\requirements.txt
  ```
- Node.js & npm (`frontend\node_modules`)
  ```powershell
  cd frontend ; npm install ; cd ..
  ```

### Start the Application

From the project root:

```powershell
.\start-dev.ps1
```

`start-dev.ps1` handles the complete startup sequence automatically:

1. Checks that Docker Desktop is running
2. Starts the PostgreSQL container (`attendancedashpro_db`) if it is not already running
3. Polls until PostgreSQL is accepting connections on `127.0.0.1:55432`
4. Starts the FastAPI backend on `127.0.0.1:8000`
5. Starts the Next.js frontend on `localhost:3100`

If any service is already running it is reused — no duplicate processes are launched.

**Expected URLs after startup:**

| Service | URL |
|---|---|
| Frontend | http://localhost:3100 |
| Backend | http://127.0.0.1:8000 |
| API | http://127.0.0.1:8000/api/v1 |
| API Docs | http://127.0.0.1:8000/docs |

### Stop the Application

```powershell
.\stop-dev.ps1
```

`stop-dev.ps1` stops the frontend (Node) and backend (Python) processes.
**PostgreSQL is left running** — its data lives in a persistent Docker named volume
(`attendancedashpro_attendancedash_data`) and is never deleted by the scripts.

To also stop PostgreSQL:
```powershell
docker stop attendancedashpro_db
```

> [!IMPORTANT]
> Never run `docker rm attendancedashpro_db` or `docker compose down -v` unless you intentionally want to destroy your local database.

*Note: For manual startup (e.g., debugging), you can run `npm run dev` in the frontend (defaults to port 3100) and `backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` in the backend directory.*

---

# 🔒 Security

- JWT authentication (signed tokens, resolved against PostgreSQL per request)
- PBKDF2-SHA256 password hashing with per-user salts
- ADMIN role resolved from the database (backend-authoritative, no self-assignment)
- Enrollment-scoped data access (no cross-user data leakage)
- Engine-authoritative calculations (no client-side domain math)

---

# 🤝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create a new feature branch
3. Commit your changes
4. Push to your branch
5. Open a Pull Request

---

# 📄 License

This project is licensed under the **MIT License**.

---

# 👨‍💻 Author

**Aditya Tiwari**

GitHub: https://github.com/realadityatiwari

---

<div align="center">

**Made with ❤️ for SRMCEM Students**

⭐ If you found this project useful, consider giving it a star!

</div>
