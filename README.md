# 🛡️ FraudShield — AI-Powered Real-Time Fraud Detection System

A production-grade fraud detection platform with **JWT authentication**, **OTP email verification**, **ML-based risk scoring**, and a **WebSocket live transaction feed** on the dashboard.

---

## 📁 Project Structure

```
fraud_detection_system/
├── app.py                    # FastAPI entry point + WebSocket mount
├── core.py                   # JWT, password hashing, OTP, email
├── realtime.py               # WebSocket broadcast manager (NEW)
├── requirements.txt
├── .env.example              # Config template → copy to .env
├── setup.py
│
├── database/
│   ├── connection.py         # SQLAlchemy engine & session
│   └── models.py             # User, Transaction, OTPStore tables
│
├── ml/
│   └── fraud_model.py        # RandomForest trainer + predictor
│
├── routers/
│   ├── auth.py               # Register, Login, OTP, Password reset
│   ├── transaction.py        # Analyze + broadcast real-time event
│   └── websocket.py          # /ws/dashboard WebSocket endpoint (NEW)
│
├── templates/                # Jinja2 HTML pages
│   ├── login.html
│   ├── signup.html
│   ├── otp.html
│   ├── forgot_password.html
│   └── dashboard.html        # Live Feed tab added (NEW)
│
└── static/
    ├── css/
    └── js/
```

---

## 🚀 Quick Start

### 1. Clone / Extract

```bash
unzip fraud_detection_system.zip
cd fraud_detection_system
```

### 2. Create virtual environment

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
- **MySQL** (default): set `DATABASE_URL` with your MySQL credentials
- **SQLite** (easy dev): uncomment the SQLite line — no MySQL needed
- Set a strong `SECRET_KEY`
- Optionally configure `SMTP_*` for real emails (OTPs print to console if blank)

### 5. Run the server

```bash
python app.py
```

Or with uvicorn directly:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Open in browser

```
http://localhost:8000
```

---

## 📡 Real-Time Features (NEW)

### WebSocket Live Feed
Every transaction analyzed via `/api/transactions/analyze` is instantly broadcast to all connected dashboard clients.

**Endpoint:** `ws://localhost:8000/ws/dashboard?token=<JWT>`

**Events sent:**
| Type | Trigger |
|------|---------|
| `connected` | On WS connect |
| `transaction` | Every analyze call |
| `pong` | Response to client ping |

### Dashboard Live Feed Tab
A new **📡 Live Feed** tab on the dashboard shows incoming transactions in real time with color-coded status, fraud probability, and merchant info — no page refresh needed.

---

## 🔑 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/verify-otp` | Verify email OTP |
| POST | `/api/auth/login` | Login → JWT |
| POST | `/api/auth/refresh` | Refresh access token |
| POST | `/api/auth/forgot-password` | Send reset OTP |
| POST | `/api/auth/reset-password` | Reset with OTP |
| POST | `/api/transactions/analyze` | **Analyze + broadcast** |
| GET | `/api/transactions` | List transactions |
| GET | `/api/dashboard/stats` | Stats + trend |
| GET | `/api/ws/status` | Active WS clients |
| WS | `/ws/dashboard` | Live transaction feed |
| GET | `/api/health` | Health + WS count |

**Interactive docs:** `http://localhost:8000/docs`

---

## 🤖 ML Model

The fraud model trains automatically on first run using 10,000 synthetic samples. To use your own dataset, place a `fraud.csv` in `dataset/` with these columns:

```
amount, hour, is_foreign, is_new_device, transactions_today, velocity_score, Class
```

`Class=0` = genuine, `Class=1` = fraud

To retrain manually:

```bash
python ml/fraud_model.py
```

---

## 🗄️ Database

**MySQL (recommended for production):**
```
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/fraud_db
```

**SQLite (zero config for development):**
```
DATABASE_URL=sqlite:///./fraudshield.db
```

Tables are auto-created on startup via `init_db()`.

---

## 🔐 Security Features

- BCrypt password hashing (12 rounds)
- JWT access tokens (30 min) + refresh tokens (7 days)
- Email OTP verification (10 min expiry, single-use)
- Password reset via OTP
- Token type validation (`access` vs `refresh`)

---

## 🔧 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | MySQL | Database connection string |
| `SECRET_KEY` | (change this!) | JWT signing secret |
| `ALGORITHM` | HS256 | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 30 | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 7 | Refresh token TTL |
| `SMTP_HOST` | smtp.gmail.com | Email server |
| `SMTP_PORT` | 587 | Email port |
| `SMTP_USER` | — | Email username |
| `SMTP_PASSWORD` | — | Email password |
| `FROM_EMAIL` | SMTP_USER | Sender address |
