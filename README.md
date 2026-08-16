<div align="center">

# 📊 AttendanceDash Pro

### Smart Attendance Intelligence Platform for SRMCEM Students

A cloud-powered Progressive Web App (PWA) that helps students track attendance, forecast eligibility, optimize attendance strategy, and monitor quiz readiness through a modern, analytics-driven dashboard.

<p>
  <img src="https://img.shields.io/badge/version-2.x-blue" alt="Version">
  <img src="https://img.shields.io/badge/status-active-success" alt="Status">
  <img src="https://img.shields.io/badge/PWA-supported-purple" alt="PWA">
  <img src="https://img.shields.io/badge/Firebase-Authentication-orange" alt="Firebase">
  <img src="https://img.shields.io/badge/JavaScript-ES6+-yellow" alt="JavaScript">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

</div>

---

# 📖 Overview

AttendanceDash Pro is a modern attendance management platform developed specifically for **Shri Ramswaroop Memorial College of Engineering & Management (SRMCEM)** students.

Unlike traditional attendance calculators, AttendanceDash Pro combines attendance tracking, forecasting, quiz eligibility analysis, attendance optimization, cloud synchronization, offline support, and simulation tools into a single modern dashboard.

The project has evolved from a simple attendance tracker into a modular attendance intelligence platform with a dedicated calculation engine, cloud-backed architecture, and Progressive Web App support.

---

# ✨ Why AttendanceDash Pro?

Unlike conventional attendance calculators, AttendanceDash Pro provides:

- ✅ Cloud synchronization across devices
- ✅ Offline support with automatic synchronization
- ✅ Smart attendance forecasting
- ✅ Quiz eligibility prediction
- ✅ Attendance optimization engine
- ✅ Progressive Web App (PWA)
- ✅ Responsive modern interface
- ✅ Modular calculation engine
- ✅ Firebase Authentication & Firestore integration

---

# 🚀 Features

## 📚 Attendance Tracking

- Track attendance subject-wise
- Mark classes as:
  - ✅ Present
  - ❌ Absent
  - ⏳ Pending
- Automatic attendance percentage calculation
- Live dashboard updates
- Cloud synchronization

---

## 🎯 Quiz Eligibility Engine

Implements SRMCEM quiz attendance rules.

Features include:

- Subject-wise quiz eligibility
- Required attendance calculation
- Forecast-based eligibility prediction
- Lecture & Tutorial analysis
- Remaining classes analysis
- Automatic eligibility updates

---

## 📈 Attendance Forecasting

Forecast future attendance assuming all remaining scheduled classes are attended.

Displays:

- Current Overall Attendance
- Forecast Overall Attendance
- Remaining Classes
- Attendance Progress
- Attendance Trend

---

## 🧠 Attendance Optimizer

The optimization engine calculates:

- Minimum lectures required
- Minimum tutorials required
- Safe classes that can be skipped
- Best attendance strategy
- Attendance deficit

---

## 📅 Simulation Mode

Simulate attendance on future dates.

Simulation mode allows users to:

- Preview future attendance
- Test attendance scenarios
- Evaluate attendance strategies
- Plan attendance before quizzes

---

## ☁️ Cloud Synchronization

Powered by Firebase.

Supports:

- Email/Password Authentication
- Individual student accounts
- Firestore cloud storage
- Automatic synchronization
- Local-first architecture
- Persistent login sessions

---

## 📱 Progressive Web App (PWA)

Install AttendanceDash Pro on:

- Android
- Windows
- macOS
- Linux

Features include:

- Offline launch
- Local caching
- Fast loading
- Background synchronization
- Native app-like experience

---

## 🎨 Modern UI

- Dark Mode
- Light Mode
- Responsive Design
- Mobile-first layout
- Desktop dashboard
- Touch-friendly controls
- Modern glass-inspired interface

---

# 🛠 Technology Stack

## Frontend

- HTML5
- CSS3
- JavaScript (ES6 Modules)

## Backend & Cloud Services

- Firebase Authentication
- Cloud Firestore

## Architecture

- Modular JavaScript
- Pure Calculation Engine
- UI / Engine Separation
- Local-first State Management
- Progressive Web App

---

# 📂 Project Structure

```text
AttendanceDashPro/

├── assets/
│
├── css/
│   ├── styles.css
│   └── responsive.css
│
├── js/
│   ├── app.js
│   ├── attendance-engine.js
│   ├── auth.js
│   ├── storage.js
│   ├── ui.js
│   ├── utils.js
│   ├── validation.js
│   ├── firebase.js
│   ├── dateContext.js
│   ├── feedback.js
│   └── pwa.js
│
├── timetable.json
├── firestore.rules
├── manifest.json
├── service-worker.js
├── firebase.json
├── .firebaserc
├── index.html
└── README.md
```

---

# 🏗 Architecture

```text
                   User Actions
                        │
                        ▼
                Attendance Records
                        │
                        ▼
               Attendance Engine
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
Subject Statistics  Overall Statistics  Quiz Eligibility
        │               │               │
        └───────────────┼───────────────┘
                        ▼
               Dashboard Models
                        │
                        ▼
                 UI Rendering Layer
```

AttendanceDash Pro follows a modular architecture with a strict separation between business logic and presentation.

The UI only renders data. All attendance calculations, forecasting, optimization, and quiz eligibility logic are performed by dedicated engine modules.

---

# ⚙ Core Modules

## 📊 Attendance Engine

Responsible for:

- Attendance calculations
- Percentage calculations
- Forecast calculations
- Attendance optimization
- Subject statistics
- Overall statistics

---

## 🎯 Quiz Eligibility Engine

Responsible for:

- Quiz eligibility prediction
- Lecture analysis
- Tutorial analysis
- Attendance threshold validation
- Eligibility calculations

---

## ☁️ Storage Layer

Responsible for:

- Local Storage
- Firestore synchronization
- Offline persistence
- Conflict-safe synchronization

---

## 🖥 UI Layer

Responsible only for:

- Rendering
- DOM updates
- User interactions
- Theme management
- Responsive layout

---

# 🔒 Security

- Firebase Authentication
- Firestore Security Rules
- Per-user cloud documents
- Persistent login sessions
- Local-first synchronization
- Offline-safe state persistence

---

# 📋 Requirements

- Modern Web Browser
- Firebase Project
- Node.js *(optional for development)*
- Firebase CLI *(for deployment)*

---

# 🚀 Installation

## Clone the Repository

```bash
git clone https://github.com/realadityatiwari/AttendanceTrackerPro.git
```

```bash
cd AttendanceTrackerPro
```

---

## Configure Firebase

Create a Firebase project and enable:

- Authentication (Email/Password)
- Cloud Firestore

Update:

```text
js/firebase.js
```

with your Firebase configuration.

---

## Deploy Firestore Rules

```bash
firebase deploy --only firestore:rules
```

---

## Run Locally (Canonical Development Workflow)

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

# 🗺 Roadmap

## ✅ Completed

- Firebase Authentication
- Cloud Synchronization
- Attendance Engine
- Overall Attendance Engine
- Quiz Eligibility Engine
- Attendance Forecasting
- Attendance Optimizer
- Simulation Mode
- Responsive UI
- Progressive Web App
- Offline Support

---

## 🚧 In Progress

- Quiz Dashboard
- Practical Attendance Module
- Lab Session Support
- Academic Analytics

---

## 🔮 Planned

- Practical Assignment Tracking
- Semester Performance Analytics
- Attendance History
- Attendance Reports (PDF)
- Calendar View
- Push Notifications
- Multi-Semester Support
- Data Export
- Academic Insights Dashboard

---

# 📸 Screenshots

> Screenshots will be added soon.

---

# 🤝 Contributing

Contributions are welcome!

If you'd like to improve AttendanceDash Pro:

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