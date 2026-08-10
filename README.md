# 🛡️ Dorito Vault — Passwordless Bank Authentication

![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688.svg?style=flat&logo=FastAPI&logoColor=white)
![FIDO2 WebAuthn](https://img.shields.io/badge/FIDO2-WebAuthn_v2.2-00599C.svg?style=flat&logo=w3c&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E.svg?style=flat&logo=supabase&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg?style=flat&logo=python&logoColor=white)
![Bootstrap](https://img.shields.io/badge/UI_Theme-Natural_Bootstrap_5-7952B3.svg?style=flat&logo=bootstrap&logoColor=white)

> **TechRush Hackathon Project | Team: Destructive Dorito**

A secure, passwordless authentication prototype for banking applications using **FIDO2/WebAuthn passkeys, hashed email OTPs, QR-based cross-device login, device recognition, step-up authentication, and server-side session management**.

---

## Table of Contents

- [Overview](#overview)
- [Problem Statement](#problem-statement)
- [Our Solution](#our-solution)
- [Key Features](#key-features)
- [Authentication Flows](#authentication-flows)
- [Security Design](#security-design)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Database Design](#database-design)
- [Testing](#testing)
- [Production Considerations](#production-considerations)
- [Future Scope](#future-scope)
- [Team](#team)

---

## Overview

Traditional banking authentication depends heavily on passwords, which can be reused, leaked, phished, or targeted through credential-stuffing and brute-force attacks.

**Dorito Vault** demonstrates a passwordless authentication architecture where users can authenticate through multiple secure mechanisms without storing a traditional account password.

The project combines:

- **WebAuthn/FIDO2 passkeys** for phishing-resistant authentication
- **Email OTPs** as an alternative authentication factor
- **QR cross-device login** for signing in on an untrusted terminal using an already-authorized device
- **Device fingerprinting and trust detection**
- **Step-up authentication** for sensitive actions
- **Signed HTTP-only session cookies**
- **Login history and security alerts**

The project is implemented as a FastAPI application with a PostgreSQL database hosted through Supabase.

---

## Problem Statement

Banking systems need authentication that is:

- Secure against phishing and credential theft
- Convenient for users
- Resistant to brute-force and replay attempts
- Capable of handling new or untrusted devices
- Able to provide additional verification for sensitive operations
- Auditable through login and security history

The goal of this project is to demonstrate how passwordless authentication can address these requirements while keeping the user experience simple.

---

## Our Solution

Dorito Vault removes the need for a traditional password and provides several authentication paths.

### Primary authentication

**WebAuthn/FIDO2 Passkey**

The browser uses a platform authenticator such as:

- Fingerprint / Touch ID
- Face ID
- Windows Hello
- Security keys such as YubiKey

The server stores the **public credential key**, not the user's biometric information. Private keys never leave user hardware.

### Alternative authentication

**Email OTP**

A six-digit, time-limited OTP is generated and sent to the user's email. Only the **bcrypt hash** of the OTP is stored in the database.

### Cross-device authentication

**QR Login**

An untrusted device can display a temporary QR token. An already-authorized device can approve that login, allowing the new device to receive its own authenticated session.

### Additional protection

**Step-Up Authentication**

For sensitive actions such as a high-value transfer, an already-authenticated user can be asked for an additional, transaction-bound OTP verification before the action is allowed to proceed.

---

## Key Features

| Feature | Description |
|---|---|
| Passwordless Registration | Creates an account without storing a traditional password |
| FIDO2/WebAuthn Passkeys | Uses browser-supported public-key authentication |
| Biometric Authentication | Uses the device's platform authenticator through WebAuthn |
| Email OTP | Six-digit OTP with bcrypt hashing and expiry |
| QR Cross-Device Login | Authorizes a new device from an existing device |
| Device Recognition | Computes a browser/device fingerprint and tracks known devices |
| Security Alerts | Detects untrusted devices and repeated failed logins |
| Step-Up Authentication | Adds transaction-bound OTP verification for sensitive operations |
| Secure Sessions | Signed, HTTP-only session cookies |
| Logout | Supports current-session logout |
| Logout All | Revokes all active sessions for the user |
| Login History | Records authentication method, result, hashed IP, and device information |
| Profile Management | Allows the authenticated user to update their name |
| Security Test Console | Provides a dedicated page for manually testing security flows |

---

## Authentication Flows

### 1. WebAuthn / Passkey Login

```text
User
  │
  │ Enter email
  ▼
FastAPI Backend
  │
  │ Generate WebAuthn challenge
  ▼
Browser / Platform Authenticator
  │
  │ Fingerprint / Face / PIN / Security Key
  ▼
Signed Assertion
  │
  ▼
FastAPI Backend
  │
  │ Verify challenge + origin + RP ID + public key
  ▼
Create authenticated session
  │
  ▼
Bank Dashboard
```

The server never receives or stores the user's raw biometric data.

---

### 2. Email OTP Login

```text
User enters email
       │
       ▼
Generate 6-digit OTP
       │
       ├──► Hash OTP with bcrypt
       │
       ▼
Store hash + expiry + unused status
       │
       ▼
Send OTP through Resend
       │
       ▼
User enters OTP
       │
       ▼
Verify against stored bcrypt hash
       │
       ▼
Create session
```

OTP configuration:

- 6 digits
- 5-minute expiry by default
- Stored only as a bcrypt hash
- Single-use after successful verification

For local development without a Resend API key, the OTP is printed to the backend console.

---

### 3. QR Cross-Device Login

```text
Untrusted Device
      │
      │ Generate temporary token
      ▼
QR Code displayed
      │
      │ Scan with authorized device
      ▼
Authorized Device approves token
      │
      ▼
Token status → approved
      │
      ▼
Untrusted Device polls status
      │
      ▼
Session created
      │
      ▼
Dashboard
```

QR tokens expire after **5 minutes** and are deleted after successful use.

---

### 4. Step-Up Authentication

Step-up authentication is used when an already-authenticated user needs an additional verification step for a sensitive operation.

```text
Authenticated User
       │
       ▼
Sensitive Action
       │
       ▼
Request OTP, bound to a hash of the transaction's details
       │
       ▼
Enter OTP
       │
       ▼
Verify OTP against that specific transaction
       │
       ▼
Sensitive Action Allowed
```

Binding the challenge to a hash of the transaction means a completed step-up can't be replayed to authorize a *different* action than the one the user was shown. The current demo uses a simulated high-value wire transfer flow in the dashboard.

---

## Security Design

### Passwordless by design

No traditional password is stored for user authentication.

### WebAuthn public-key cryptography

During passkey registration, the server stores the credential's public key and metadata. During login, the browser signs a server-generated challenge using the authenticator.

The application does **not** store raw fingerprint or Face ID data.

### OTP protection

OTP values are generated using Python's `secrets` module and hashed with bcrypt before database storage.

```text
Plain OTP → bcrypt hash → Database
```

The plaintext OTP is never stored in the `otp_codes` table.

### IP address protection

Raw IP addresses are never stored. Each login attempt's IP is put through a keyed hash (HMAC-SHA256, keyed with `SECRET_KEY`) before it touches the database, and separately resolved once to a rough city/country for human-readable display. If the database were ever leaked, no raw IP addresses would be exposed.

### Session security

Authenticated sessions use:

- Signed session cookies
- `HttpOnly`
- `SameSite=Lax`
- `Secure=True` in production
- Server-side session records
- Expiration timestamps
- Session revocation

Authentication state is not stored in `localStorage` or `sessionStorage`.

### Account lockout

Three failed login attempts within a 30-minute window temporarily locks the account for 15 minutes and emails the user a notification (with a resolved rough location, never a raw IP).

### Login auditing

Successful and failed authentication attempts are recorded with:

- Authentication method
- Success/failure status
- Hashed IP address + resolved city/country
- Device information
- UTC timestamp

Supported authentication method values are:

```text
webauthn
otp
qr
recovery_code
```

### Security alerts

The application currently flags:

- Untrusted devices
- 3 or more failed login attempts within a 30-minute window

---

## System Architecture

```
flowchart TD
    A[User Browser] --> B[Jinja2 UI + Vanilla JavaScript]
    B --> C[FastAPI Application]

    C --> D[Entry Router]
    C --> E[Security Router]
    C --> F[Session Router]

    E --> G[WebAuthn / FIDO2]
    E --> H[OTP + Resend]
    E --> I[QR Login]
    E --> J[Step-Up Authentication]
    E --> K2[Email Verification]
    E --> L2[Recovery Codes]

    D --> K[Device Recognition]
    D --> L[Security Alerts]

    F --> M[Session Management]
    F --> N[Login History]
    F --> O2[Admin Audit Log]

    C --> O[SQLAlchemy ORM]
    O --> P[(PostgreSQL / Supabase)]
```

### Backend organization

The backend is divided into three logical areas:

**Section A — Entry Checks**

- Registration
- Device recognition
- Security alerts
- Account lockout
- Transaction-bound step-up challenges

**Section B — Security Measures**

- WebAuthn
- OTP
- QR authentication
- Step-up verification
- Email verification
- Backup recovery codes

**Section C — Sessions**

- Current session
- Logout
- Logout from all devices
- Login history (with hashed IP + resolved location)
- Profile management
- Admin audit log

Shared session functionality lives in:

```text
lib/session_utils.py
```

This prevents the different authentication modules from implementing session handling independently.

---

## Tech Stack

### Backend

- **Python**
- **FastAPI**
- **SQLAlchemy 2.0** + `psycopg3` driver
- **Pydantic**
- **Uvicorn**

### Database

- **PostgreSQL**
- **Supabase**
- **Alembic** for database migrations

### Authentication & Security

- **WebAuthn / FIDO2** — `webauthn` Python package
- **Passlib + bcrypt**
- Python `secrets`
- **itsdangerous** signed session cookies
- **slowapi** rate limiting

### Frontend

- **Jinja2**
- **HTML/CSS**
- **Vanilla JavaScript**
- **Tailwind CSS via CDN**
- Font Awesome
- QRCode JavaScript library

### Email

- **Resend**
- Development fallback through backend console output

### Deployment

- **Docker** + **docker-compose**

---

## Project Structure

```text
Destructive_Dorito_TechRush/
│
├── main.py
├── database.py
├── models.py
├── schemas.py
├── requirements.txt
├── CONTRACT.md
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
│
├── routers/
│   ├── __init__.py
│   ├── auth_entry.py
│   ├── security.py
│   └── sessions.py
│
├── lib/
│   ├── __init__.py
│   ├── session_utils.py
│   ├── email_utils.py
│   ├── lockout_utils.py
│   ├── ip_utils.py
│   └── rate_limit.py
│
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── dashboard.html
│   └── security_test.html
│
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
│
└── alembic/
    └── versions/
```

---

## Getting Started

### Prerequisites

Make sure you have:

- Python 3.11 or 3.12 (avoid 3.13+ for now — some dependencies lack prebuilt wheels for newer versions)
- PostgreSQL database or Supabase project
- Git
- A browser supporting WebAuthn for passkey testing

For email delivery, a Resend API key is optional during local development.

---

### 1. Clone the repository

```bash
git clone https://github.com/shreyank26pal-dev/Destructive_Dorito_TechRush.git
cd Destructive_Dorito_TechRush
```

---

### 2. Create a virtual environment

**Windows:**

```powershell
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

---

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Configure environment variables

Copy `.env.example` to `.env` and fill in real values:

```env
DATABASE_URL=postgresql://user:password@host:port/dbname
SECRET_KEY=<get the real shared value from your team — never generate your own or commit one>
RESEND_API_KEY=your-resend-api-key

WEBAUTHN_RP_ID=localhost
WEBAUTHN_RP_NAME=Dorito Vault
WEBAUTHN_ORIGIN=http://localhost:8000

SESSION_COOKIE_NAME=session_token
SESSION_EXPIRE_MINUTES=1440
OTP_EXPIRE_MINUTES=5

ENVIRONMENT=development
```

**Never commit a real `.env` file or paste real secrets into a README, chat, or commit message.** `.env` is already listed in `.gitignore`.

---

### 5. Start the application

```bash
uvicorn main:app --reload
```

The application will be available at:

```text
http://localhost:8000
```

Use `localhost`, not `127.0.0.1` — WebAuthn treats them as different origins, and passkey registration will fail on the latter.

---

## Application Pages

| Route | Purpose |
|---|---|
| `/` | Registration and passwordless login |
| `/dashboard` | Authenticated user dashboard |
| `/test/security` | Manual WebAuthn, OTP, QR and step-up testing |
| `/docs` | FastAPI interactive API documentation |
| `/health` | Application health check |

---

## API Reference

### Entry & Device Management

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/entry/register` | Register a new user |
| `POST` | `/api/entry/check-device` | Check/register a device fingerprint |
| `GET` | `/api/entry/alerts/{user_id}` | Retrieve security alerts |
| `POST` | `/api/entry/step-up/challenge` | Issue a transaction-bound step-up challenge |

### WebAuthn

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/security/webauthn/register-options` | Generate passkey registration options |
| `POST` | `/api/security/webauthn/register-verify` | Verify and store WebAuthn credential |
| `POST` | `/api/security/webauthn/login-options` | Generate login challenge |
| `POST` | `/api/security/webauthn/login-verify` | Verify passkey authentication |

### OTP

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/security/otp/send` | Generate and send OTP |
| `POST` | `/api/security/otp/verify` | Verify OTP and create session |

### QR Authentication

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/security/qr/generate` | Generate temporary QR login token |
| `GET` | `/api/security/qr/status/{token}` | Check QR authorization status |
| `POST` | `/api/security/qr/approve` | Approve QR login |

### Step-Up Authentication

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/security/step-up/verify` | Verify an additional, transaction-bound OTP |

### Email Verification & Account Recovery

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/security/email/send-verification` | Send registration verification email |
| `POST` | `/api/security/email/verify` | Confirm email verification code |
| `POST` | `/api/security/recovery-codes/generate` | Generate backup recovery codes |
| `POST` | `/api/security/recovery-codes/verify` | Log in using a recovery code |
| `GET` | `/api/security/devices/nudge/{identifier}` | Nudge user to register a second device/credential |

### Session Management

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/sessions/me` | Get the current authenticated user |
| `POST` | `/api/sessions/logout` | Logout current session |
| `POST` | `/api/sessions/logout-all` | Revoke all user sessions |
| `GET` | `/api/sessions/login-history` | Retrieve the current user's authentication history |
| `GET` | `/api/sessions/profile` | Retrieve profile |
| `POST` | `/api/sessions/profile/update` | Update profile |
| `GET` | `/api/sessions/admin/audit-log` | Cross-user login history for an admin view (no raw or hashed IP exposed) — **note: does not yet enforce real admin-role access control** |

---

## Database Design

The application uses PostgreSQL through SQLAlchemy.

### Core tables

```text
users
 ├── credentials
 ├── devices
 ├── sessions
 ├── login_history
 ├── otp_codes
 ├── email_verification_codes
 └── recovery_codes

login_tokens
step_up_challenges
```

### `users`

Stores basic account information, plus `locked_until` (account lockout) and `is_verified` (email verification status).

### `credentials`

Stores WebAuthn credential information: public key, credential ID, signature counter, device label, last-used timestamp.

### `devices`

Tracks recognized devices: fingerprint, trusted/untrusted state, first/last seen timestamps.

### `sessions`

Stores active server-side sessions: user, device, creation time, expiry time, revocation status.

### `login_history`

Audit trail of authentication attempts. `ip_address` holds a **keyed hash**, never a raw IP; `city`/`country` hold a best-effort resolved location.

### `otp_codes`

Stores only bcrypt-hashed OTP values with expiration and single-use state.

### `login_tokens`

Temporary QR cross-device login tokens.

### `step_up_challenges`

Binds a step-up OTP verification to a hash of one specific transaction's details, so it can't be replayed against a different action.

### `email_verification_codes` / `recovery_codes`

Hashed codes for registration email confirmation and emergency account recovery.

---

## Testing

### Security Test Console

Open:

```text
http://localhost:8000/test/security
```

The test console provides controls for WebAuthn registration/login, OTP generation/verification, QR generation/approval/status polling, and step-up OTP verification.

### FastAPI Swagger UI

Open:

```text
http://localhost:8000/docs
```

Interactive interface for testing every backend endpoint directly.

### Health Check

```http
GET /health
```

Expected response:

```json
{
  "status": "ok"
}
```

---

## Production Considerations

This project is a **hackathon prototype** and should not be treated as production banking infrastructure without additional hardening.

Important improvements before real-world deployment include:

1. **Enforce real admin-role access control** on `/api/sessions/admin/audit-log` — it currently only requires being logged in as *any* user, since there's no `is_admin` concept in the schema yet.
2. **Protect QR approval with an authenticated existing device session** — the current demo identifies the approving user by email for simplicity; production should require a valid authenticated session on the approving device.
3. **Move WebAuthn challenges out of process memory** — currently stored in an in-memory dictionary; a multi-worker deployment should use Redis or a persistent shared store.
4. **Use HTTPS everywhere** — production WebAuthn and secure cookie configuration require it.
5. **Use proper database migrations** — Alembic should drive schema changes instead of relying on startup `create_all()`.
6. **Extend rate limiting beyond the current global/single-route limits** — login and OTP-verify endpoints specifically need brute-force protection, ideally per-user as well as per-IP.
7. **Strengthen device recognition** — the current fingerprint is browser-derived and shouldn't be treated as a hardware-backed identity by itself.
8. **Improve authorization and CSRF protections** for sensitive banking actions.
9. **Add monitoring and alerting** — centralized security logging and anomaly detection.
10. **Enforce multiple authentication factors** — the system currently supports several login *methods*, but doesn't yet require a user to register/use more than one.
11. **Decide on the account-recovery model** — the system currently supports backup recovery codes; if identity-document-based recovery (e.g. government ID linkage) is required, that's a separate, not-yet-built feature.

---

## Unique Selling Propositions

### 1. Passwordless Authentication

Authentication is based on **WebAuthn, OTP and QR-based authentication**, reducing the risks associated with phishing, password reuse, credential theft, and brute-force attacks.

**USP:** No passwords to remember, manage, or steal.

### 2. Device Trust

Every login device is classified as Trusted, Known, or Unknown. Unknown devices can automatically trigger additional verification.

**USP:** Authentication is based on device trust, not just user credentials.

### 3. Continuous Security

Security does not stop after authentication — the system continues monitoring active sessions, login history, new devices, and security alerts.

**USP:** Security continues even after the user logs in.

### 4. Session Control

Users can view active sessions, log out from a specific device, or log out from all devices remotely.

**USP:** Users have complete visibility and control over their account sessions.

### 5. Real-Time Alerts

The system identifies and alerts users about untrusted devices, suspicious login attempts, and new device access.

**USP:** Proactive security instead of reactive security.

### 6. Privacy-Preserving Auditing

Login history never stores a raw IP address — only a keyed hash plus a resolved rough location.

**USP:** Full auditability without creating a new privacy liability if the database is ever exposed.

### 7. Modular Architecture

The backend is organized into independent modules for authentication, device management, session management, and security monitoring.

**USP:** The system can be extended without redesigning the entire application.

---

## Future Scope

### AI Fraud Detection

Detect suspicious login patterns and assign a real-time risk score, automatically triggering additional verification for high-risk logins.

### Location-Aware Authentication

Detect logins from unfamiliar cities or countries (building on the existing city/country resolution) and request additional authentication only when the login location is unusual.

### Admin Security Dashboard

A proper role-gated admin view of active sessions, failed login attempts, trusted/untrusted devices, and security alerts, building on the existing (currently ungated) audit-log endpoint.

### Mobile Authentication

Fingerprint authentication, Face ID, and push notification approval for a more seamless mobile banking authentication experience.

### Cloud Deployment

Docker for containerization, Kubernetes for orchestration, load balancing, and Redis caching for shared, high-speed temporary state (e.g. WebAuthn challenges), allowing the system to scale toward large numbers of users.

### Enforced Multi-Factor Authentication (MFA)

Require a combination of authentication methods (passkey + OTP, or similar) rather than allowing any single method to fully authenticate a user, with the method combination adaptable based on login risk and device trust.

### Identity-Linked Account Recovery

Extend the current backup-recovery-code model to support recovery linked to a verified government ID or phone number, for cases where backup codes alone aren't sufficient.

---

## Why Passwordless?

Traditional:

```text
Password
   ↓
Can be stolen / reused / phished
   ↓
Account compromise
```

Dorito Vault:

```text
Passkey / OTP / Authorized Device
             ↓
      Cryptographic or
      time-limited verification
             ↓
       Authenticated Session
```

---

## Hackathon Highlights

- Multiple passwordless authentication mechanisms in one system
- FIDO2/WebAuthn public-key authentication
- No traditional passwords stored
- OTPs protected with bcrypt hashing
- Cross-device authentication through QR authorization
- Device recognition and security alerts
- Transaction-bound step-up verification for sensitive operations
- IP addresses never stored in raw form — keyed hash + resolved location only
- Centralized session and login-history management
- Clear separation between authentication, security and session modules

---

## Team

**Team:** Destructive Dorito

**Project:** Dorito Vault — Passwordless Bank Authentication

**Hackathon:** TechRush

### Contributors

- Sharmad Kulkarni
- Shreyank Pal
- Sujal Dhonsale

## License

This project was developed as a hackathon prototype for educational and demonstration purposes.

If you intend to reuse the project, review and adapt the authentication, authorization, cryptography, session management and deployment configuration for your target environment.
