# Dorito Vault — Passwordless Bank Authentication

> **TechRush Hackathon Project | Team: Destructive Dorito**

> A secure, passwordless authentication prototype for banking applications using **FIDO2/WebAuthn passkeys, hashed email OTPs, QR-based cross-device login, device recognition, step-up authentication, and server-side session management**.

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

The server stores the **public credential key**, not the user's biometric information.

### Alternative authentication

**Email OTP**

A six-digit, time-limited OTP is generated and sent to the user's email. Only the **bcrypt hash** of the OTP is stored in the database.

### Cross-device authentication

**QR Login**

An untrusted device can display a temporary QR token. An already-authorized device can approve that login, allowing the new device to receive its own authenticated session.

### Additional protection

**Step-Up Authentication**

For sensitive actions such as a high-value transfer, an already-authenticated user can be asked for an additional OTP verification before the action is allowed to proceed.

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
| Step-Up Authentication | Adds OTP verification for sensitive operations |
| Secure Sessions | Signed, HTTP-only session cookies |
| Logout | Supports current-session logout |
| Logout All | Revokes all active sessions for the user |
| Login History | Records authentication method, result, IP and device information |
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

Example:

```text
Authenticated User
       │
       ▼
Sensitive Action
       │
       ▼
Request OTP
       │
       ▼
Enter OTP
       │
       ▼
Verify OTP
       │
       ▼
Sensitive Action Allowed
```

The current demo uses a simulated high-value wire transfer flow in the dashboard.

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

### Login auditing

Successful and failed authentication attempts are recorded with:

- Authentication method
- Success/failure status
- IP address
- Device information
- UTC timestamp

Supported authentication method values are:

```text
webauthn
otp
qr
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

    D --> K[Device Recognition]
    D --> L[Security Alerts]

    F --> M[Session Management]
    F --> N[Login History]

    C --> O[SQLAlchemy ORM]
    O --> P[(PostgreSQL / Supabase)]
```

### Backend organization

The backend is divided into three logical areas:

**Section A — Entry Checks**

- Registration
- Device recognition
- Security alerts

**Section B — Security Measures**

- WebAuthn
- OTP
- QR authentication
- Step-up authentication

**Section C — Sessions**

- Current session
- Logout
- Logout from all devices
- Login history
- Profile management

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
- **SQLAlchemy**
- **Pydantic**
- **Uvicorn**

### Database

- **PostgreSQL**
- **Supabase**
- **Alembic** for database migrations

### Authentication & Security

- **WebAuthn / FIDO2**
- `webauthn` Python package
- **Passlib + bcrypt**
- Python `secrets`
- **itsdangerous** signed session cookies

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
├── .env
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
│   └── session_utils.py
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

- Python 3.10+
- PostgreSQL database or Supabase project
- Git
- A browser supporting WebAuthn for passkey testing

For email delivery, a Resend API key is optional during local development.

---

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd Destructive_Dorito_TechRush
```

---

### 2. Create a virtual environment

#### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

#### macOS / Linux

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

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://user:password@host:port/dbname
SECRET_KEY=your-secret-key
RESEND_API_KEY=your-resend-api-key

WEBAUTHN_RP_ID=localhost
WEBAUTHN_RP_NAME=SecureBank Demo
WEBAUTHN_ORIGIN=http://localhost:8000

SESSION_COOKIE_NAME=session_token
SESSION_EXPIRE_MINUTES=1440
OTP_EXPIRE_MINUTES=5

ENVIRONMENT=development
```

---

### 5. Start the application

```bash
uvicorn main:app --reload
```

The application will be available at:

```text
http://localhost:8000
```

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
| `POST` | `/api/security/step-up/verify` | Verify an additional OTP for a sensitive action |

### Session Management

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/sessions/me` | Get the current authenticated user |
| `POST` | `/api/sessions/logout` | Logout current session |
| `POST` | `/api/sessions/logout-all` | Revoke all user sessions |
| `GET` | `/api/sessions/login-history` | Retrieve authentication history |
| `GET` | `/api/sessions/profile` | Retrieve profile |
| `POST` | `/api/sessions/profile/update` | Update profile |

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
 └── otp_codes

login_tokens
```

### `users`

Stores basic account information.

- `id`
- `email`
- `name`
- `created_at`

### `credentials`

Stores WebAuthn credential information.

- Public key
- WebAuthn credential ID
- Signature counter
- Device label
- Last-used timestamp

### `devices`

Tracks recognized devices.

- Device fingerprint
- Trusted/untrusted state
- First seen timestamp
- Last seen timestamp

### `sessions`

Stores active server-side sessions.

- User
- Device
- Creation time
- Expiry time
- Revocation status

### `login_history`

Creates an audit trail of authentication attempts.

### `otp_codes`

Stores only hashed OTP values with expiration and single-use state.

### `login_tokens`

Stores temporary QR cross-device login tokens.

---

## Testing

### Security Test Console

Open:

```text
http://localhost:8000/test/security
```

The test console provides controls for:

- WebAuthn registration
- WebAuthn login
- OTP generation
- OTP verification
- QR token generation
- QR approval
- QR status polling
- Step-up OTP verification

### FastAPI Swagger UI

Open:

```text
http://localhost:8000/docs
```

This provides an interactive interface for testing the backend API endpoints.

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

1. **Protect QR approval with an authenticated existing device session**
   - The current demo identifies the approving user using their email for simplicity.
   - Production should require the approving phone/device to already possess a valid authenticated session.

2. **Move WebAuthn challenges out of process memory**
   - Challenges are currently stored in an in-memory dictionary.
   - A multi-worker deployment should use Redis or a persistent shared store.

3. **Use HTTPS everywhere**
   - Production WebAuthn and secure cookie configuration should use HTTPS.

4. **Use proper database migrations**
   - Alembic should be used for controlled production schema changes instead of relying on startup `create_all()`.

5. **Add rate limiting**
   - OTP requests, OTP verification, QR generation and authentication attempts should be rate-limited.

6. **Strengthen device recognition**
   - The current fingerprint is a browser-derived identifier and should not be considered a hardware-backed identity by itself.

7. **Improve authorization and CSRF protections**
   - Sensitive banking actions should have strict authorization, CSRF protection where applicable, and transaction-specific verification.

8. **Add monitoring and alerting**
   - Production systems should integrate centralized security logging, anomaly detection and operational monitoring.

---

## Unique Selling Propositions

The project is designed around six key differentiators:

### 1. Passwordless Authentication

Authentication is based on **WebAuthn, OTP and QR-based authentication**, reducing the risks associated with:

- Phishing
- Password reuse
- Credential theft
- Brute-force attacks

**USP:** No passwords to remember, manage, or steal.

### 2. Device Trust

Every login device is classified based on its trust state:

- Trusted Device
- Known Device
- Unknown Device

Unknown devices can automatically trigger additional verification.

**USP:** Authentication is based on device trust, not just user credentials.

### 3. Continuous Security

Security does not stop after authentication. The system continues monitoring:

- Active sessions
- Login history
- New devices
- Security alerts

**USP:** Security continues even after the user logs in.

### 4. Session Control

Users can:

- View active sessions
- Log out from a specific device
- Log out from all devices remotely

**USP:** Users have complete visibility and control over their account sessions.

### 5. Real-Time Alerts

The system identifies and alerts users about:

- Untrusted devices
- Suspicious login attempts
- New device access

**USP:** Proactive security instead of reactive security.

### 6. Modular Architecture

The backend is organized into independent modules for:

- Authentication
- Device Management
- Session Management
- Security Monitoring

**USP:** The system can be extended without redesigning the entire application.

---

## Future Scope

The project can be extended beyond the current hackathon implementation in the following directions.

### AI Fraud Detection

- Detect suspicious login patterns and assign a real-time risk score.
- Automatically trigger additional verification for high-risk logins.

### Location-Aware Authentication

- Detect logins from unfamiliar cities or countries.
- Request additional authentication only when the login location is unusual.

### Admin Security Dashboard

Provide administrators with real-time monitoring of:

- Active sessions
- Failed login attempts
- Trusted and untrusted devices
- Security alerts

### Mobile Authentication

Integrate:

- Fingerprint authentication
- Face ID
- Push notification approval

This would enable a more seamless mobile banking authentication experience.

### Cloud Deployment

The application can be prepared for scalable cloud deployment using:

- Docker for containerization
- Kubernetes for orchestration
- Load balancing for distributing traffic
- Redis caching for shared, high-speed temporary state

This would allow the system to scale toward large numbers of users.

### Multi-Factor Authentication (MFA)

Implement adaptive MFA using a combination of:

- Email OTP
- SMS OTP
- Authenticator applications
- Passkeys

The authentication method can be selected based on login risk and device trust.

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

The core idea is simple:

---

## Hackathon Highlights

### What makes the project stand out

- Multiple passwordless authentication mechanisms in one system
- FIDO2/WebAuthn public-key authentication
- No traditional passwords stored
- OTPs protected with bcrypt hashing
- Cross-device authentication through QR authorization
- Device recognition and security alerts
- Step-up verification for sensitive operations
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
