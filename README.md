# 🛡️ Dorito Vault — Enterprise Passwordless Security Core

![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688.svg?style=flat&logo=FastAPI&logoColor=white)
![FIDO2 WebAuthn](https://img.shields.io/badge/FIDO2-WebAuthn_v2.2-00599C.svg?style=flat&logo=w3c&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E.svg?style=flat&logo=supabase&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg?style=flat&logo=python&logoColor=white)
![Bootstrap](https://img.shields.io/badge/UI_Theme-Natural_Bootstrap_5-7952B3.svg?style=flat&logo=bootstrap&logoColor=white)

**Dorito Vault** is a zero-trust, passwordless authentication and security core designed to eliminate traditional passwords—and the phishing, credential-stuffing, and database leakage vulnerabilities associated with them.

Built with **FastAPI**, **W3C WebAuthn (FIDO2)**, **Supabase PostgreSQL**, and modern cryptographic primitives.

---

## ✨ Features

- 🛡️ **FIDO2 / WebAuthn Hardware Passkeys**: Public-key cryptography using TPM 2.0 / Secure Enclave hardware chips (Windows Hello, TouchID, FaceID, YubiKey). Private keys never leave user hardware.
- 🔑 **Bcrypt Hashed Email OTP**: 5-minute time-bound ephemeral codes salted and hashed using Bcrypt before storage.
- 📱 **QR Cross-Device Sync**: Stateless, short-polling QR authentication allowing untrusted desktop terminals to be authorized via a logged-in mobile phone.
- ⚡ **Step-Up Multi-Factor Authentication**: Secondary factor verification required before executing high-risk financial transactions (e.g., $10,000 wire transfers).
- 🖥️ **Hardware Device Fingerprinting**: Client-side browser & environment hashing to detect untrusted devices.
- 📜 **Cryptographic Audit Log**: Immutable record of authentication events, IP addresses, and hardware trust metrics.

---

## 🏗️ Architecture & Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Backend Framework** | [FastAPI](https://fastapi.tiangolo.com/) (Asynchronous ASGI Web Framework) |
| **ASGI Server** | [Uvicorn](https://www.uvicorn.org/) (High-performance server using `uvloop` & `httptools`) |
| **Database ORM** | [SQLAlchemy 2.0](https://www.sqlalchemy.org/) + `psycopg3` driver |
| **Database Infrastructure** | [Supabase PostgreSQL](https://supabase.com/) (Cloud DB cluster) / SQLite fallback |
| **Security Standards** | W3C WebAuthn / FIDO2, Bcrypt, Passlib |
| **Frontend UI** | Jinja2 Templates, Vanilla CSS Design System, Modern Client JS Engine (`app.js`), QRCode.js |

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.10+ installed on your machine.
- Git installed.

### Step 1: Clone the Repository
```bash
git clone https://github.com/shreyank26pal-dev/Destructive_Dorito_TechRush.git
cd Destructive_Dorito_TechRush
```

### Step 2: Create & Activate a Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables (`.env`)
Create a `.env` file in the root project directory:

```env
DATABASE_URL=postgresql://postgres.xxx:pass@aws-0-region.pooler.supabase.com:6543/postgres
SECRET_KEY=13d1189519d9ed1534b9e5515593e252d2e5513a03ce2a140df3d4d40033a629
WEBAUTHN_RP_ID=localhost
WEBAUTHN_RP_NAME=Dorito Vault
WEBAUTHN_ORIGIN=http://localhost:8000
SESSION_COOKIE_NAME=session_token
SESSION_EXPIRE_MINUTES=1440
OTP_EXPIRE_MINUTES=5
ENVIRONMENT=development
```

### Step 5: Run the Application Server
```bash
python -m uvicorn main:app --reload
```

Open your browser and navigate to **[http://localhost:8000](http://localhost:8000)**!

---

## 📂 Project Structure

```
Destructive_Dorito_TechRush/
├── main.py                  # FastAPI app entrypoint & static routes
├── database.py              # SQLAlchemy database setup & Supabase connection engine
├── models.py                # Relational database models (Users, Credentials, OTPs, Logs)
├── schemas.py               # Pydantic request/response validation schemas
├── requirements.txt         # Project dependencies
├── CONTRACT.md              # Backend & frontend API specification contract
├── .env.example             # Environment variables template
├── lib/
│   └── session_utils.py     # Auth session management & audit logging helper
├── routers/
│   ├── auth_entry.py        # Registration, fingerprint check & alerts endpoints
│   ├── security.py          # WebAuthn ceremonies, OTP, QR sync & Step-Up Auth
│   └── sessions.py          # User session validation, profile update & login history
├── static/
│   ├── css/style.css        # Natural Bootstrap 5 design system
│   └── js/app.js            # Client-side WebAuthn ceremonies, QR polling & particle engine
└── templates/
    ├── base.html            # Core layout template & modals
    ├── index.html           # Login terminal & registration UI
    └── dashboard.html       # Executive balance card, risk center & audit trail
```

---

## 🔒 Security Best Practices Implemented

1. **Origin Binding**: WebAuthn requests dynamically resolve the active hostname to prevent domain mismatch attacks and phishing.
2. **Zero Password Storage**: No master passwords stored; authentication relies on hardware TPM 2.0 public key signatures.
3. **Prepared Statement Handling**: Configured `prepare_threshold=None` for Supabase PgBouncer pooled connections.
4. **Environment Protection**: `.env` is listed in `.gitignore` to prevent credential exposure.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.