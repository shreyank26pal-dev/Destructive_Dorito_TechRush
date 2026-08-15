# 🛡️ Dorito Vault — Passwordless Bank Authentication

![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688.svg?style=flat&logo=FastAPI&logoColor=white)
![FIDO2 WebAuthn](https://img.shields.io/badge/FIDO2-WebAuthn_v2.2-00599C.svg?style=flat&logo=w3c&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E.svg?style=flat&logo=supabase&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg?style=flat&logo=python&logoColor=white)
![UI Theme](https://img.shields.io/badge/UI_Theme-Warm_Editorial_/_Matrix_Green-C8552B.svg?style=flat&logo=css3&logoColor=white)

> **TechRush Hackathon Project | Team: Destructive Dorito**

A secure, passwordless authentication prototype for banking applications featuring **FIDO2/WebAuthn passkeys, delegated co-signer authentication, hashed email OTPs, QR-based cross-device login, IP/timezone geolocation firewalls, role-gated admin auditing, and dynamic theme state management**.

---

## Table of Contents

- [Overview](#overview)
- [Problem Statement](#problem-statement)
- [Our Solution](#our-solution)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Authentication & Security Flows](#authentication--security-flows)
  - [1. WebAuthn Passkey Login](#1-webauthn-passkey-login)
  - [2. Email OTP Login](#2-email-otp-login)
  - [3. QR Cross-Device Login](#3-qr-cross-device-login)
  - [4. Transaction-Bound Step-Up Authentication](#4-transaction-bound-step-up-authentication)
  - [5. Delegated Co-Signer Passkey Flow](#5-delegated-co-signer-passkey-flow)
  - [6. Geolocation Firewall Security Check](#6-geolocation-firewall-security-check)
- [Security & Privacy Design](#security--privacy-design)
- [Role-Gated Admin Portal](#role-gated-admin-portal)
- [Premium Visual Design & Aesthetics](#premium-visual-design--aesthetics)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Database Design](#database-design)
- [Testing & Diagnostics](#testing--diagnostics)
- [Production Considerations](#production-considerations)
- [Unique Selling Propositions (USPs)](#unique-selling-propositions-usps)
- [Future Scope](#future-scope)
- [Team](#team)

---

## Overview

Traditional banking authentication depends heavily on passwords, which are easily phished, reused, or compromised via credential-stuffing and database leaks.

**Dorito Vault** demonstrates a robust passwordless authentication architecture where users authenticate through multiple secure, modern mechanisms without storing traditional passwords.

The project combines:
- **WebAuthn/FIDO2 Passkeys** for phishing-resistant, platform-native authentication.
- **Delegated Co-Signer Passkeys** to allow designated co-signers (e.g., family members/guardians) to approve high-risk operations from their own devices.
- **Bcrypt-Hashed Email OTPs** with multi-tier email sending fallback resilience (Resend + domain fallbacks).
- **QR Cross-Device Login** for authorizing untrusted terminals using an already-authenticated device.
- **Automatic Geolocation Firewall** that blocks sensitive operations (like wire transfers) originating outside the home country (India), built with reverse-proxy header resilience (`X-Forwarded-For`).
- **Role-Gated Security Auditing** through an Admin Portal displaying anonymized cross-user login history and real-time step-up action feeds.
- **Visual Theme Customization** featuring a dual "Warm Editorial" (Light) / "Emerald Fintech" (Dark) aesthetic with mouse trail micro-animations and theme flash prevention.

---

## Problem Statement

Modern banking platforms require authentication mechanisms that are:
- Resistant to phishing and credential theft.
- Convenient and platform-agnostic for the user.
- Resistant to brute-force, replay, and session hijacking attempts.
- Capable of recognizing and grading device trustworthiness.
- Able to restrict cross-border transaction risks.
- Auditable through location-resolved logs while preserving user privacy.

Dorito Vault eliminates passwords entirely, providing secure and auditable passwordless authentication paths suited to modern digital banking.

---

## Our Solution

Dorito Vault replaces the password field with a secure token, public-key verification, and multi-device coordination framework.

### Primary Authentication: FIDO2/WebAuthn Passkeys
Uses browser-supported platform authenticators (Touch ID, Face ID, Windows Hello, YubiKeys). The server stores only the public key; private keys never leave the hardware.

### Alternative Authentication: Hashed Email OTP
A time-limited 6-digit OTP is sent via Resend. The server stores only the bcrypt hash of the OTP, making it resilient to database interception.

### Cross-Device Authentication: QR Login
Untrusted devices display a temporary QR token. A logged-in, trusted device scans/approves the token, allowing the untrusted terminal to securely establish its own authenticated session.

### Co-Signer Authorization: Delegated Security
Vulnerable or elderly users can delegate transaction authorization. When a high-risk operation is triggered, a co-signer must approve the request using their registered passkey.

---

## Key Features

| Feature | Description |
|---|---|
| **Passwordless Registration** | Registers new accounts without asking for or storing traditional passwords. |
| **FIDO2/WebAuthn Passkeys** | Implements standard public-key cryptography via the browser's credentials API. |
| **Delegated Co-Signer Approval** | Allows a linked guardian to sign off on high-risk transfers from their own device. |
| **Bcrypt-Hashed Email OTP** | Protects alternative sign-ins; generated OTP is bcrypt-hashed before database storage. |
| **QR Cross-Device Sign-In** | Logs in a secondary device by scanning a QR code with an authorized device. |
| **Geolocation Firewall** | Restricts step-up challenges and wire transfers to the home country (India), blocking foreign origins. |
| **Reverse Proxy Support** | Resolves user IP via `X-Forwarded-For` to support CDNs, Nginx, or Supabase. |
| **Role-Gated Admin Dashboard** | Admin-exclusive views for audit logs and sensitive transaction feeds. |
| **Dual-Theme Design System** | Smooth switching between "Warm Editorial" (Light) and "Emerald Fintech" (Dark) modes. |
| **Micro-Interactions** | Dynamic cursor particle trails and smooth UI animations to elevate UX. |
| **Anti-Theme-Flash** | Fast inline script execution preventing bright page flashes when reloading dark mode. |
| **Privacy-Preserving Audit** | Logs keyed IP hashes (HMAC-SHA256) and rough city/country details instead of raw IPs. |
| **Step-Up Authentication** | Prompts for dynamic, transaction-bound OTP verification before sensitive actions. |
| **Multi-Tier Email Fallback** | Tries custom domain emails, falls back to onboarding senders, redirects, or prints to CLI. |

---

## System Architecture

```mermaid
flowchart TD
    A["User Browser"] -->|HTML / Tailwind / Vanilla JS| B["Web Interface"]
    B -->|FastAPI Server| C["Application Backend"]

    C --> D["Entry Router (auth_entry.py)"]
    C --> E["Security Router (security.py)"]
    C --> F["Session Router (sessions.py)"]
    C --> G["Co-Signer Router (co_signer.py)"]

    D --> H["Device Fingerprinting"]
    D --> I["Lockout & Alerts"]
    D --> J["Automatic Geolocation Firewall"]

    E --> K["WebAuthn Passkeys"]
    E --> L["Hashed Email OTPs"]
    E --> M["QR Cross-Device Login"]
    E --> N["Step-Up Verification"]

    G --> O["Co-Signer Invites"]
    G --> P["Co-Signer WebAuthn Registration"]
    G --> Q["Delegated Transaction Approval"]

    F --> R["Session Management & Revocation"]
    F --> S["Login History & Geolocation Lookup"]
    F --> T["Role-Gated Admin Portal & Audit Log"]

    C --> U["SQLAlchemy 2.0 ORM"]
    U --> V[("Supabase PostgreSQL / SQLite")]
```

### Backend Structure
- **Section A (Entry Checks):** Handles device checks, registration, account lockouts, alerts, and transaction-bound step-up challenges.
- **Section B (Security Measures):** Coordinates WebAuthn, OTP, QR, co-signer approvals, email verification, and recovery codes.
- **Section C (Sessions & Admin):** Manages cookies, active sessions, profiles, history auditing, and the role-gated admin portal.
- **Shared Utilities (`lib/`):** Contains centralized session helpers, rate limiters, email delivery fallback loops, and IP hashing tools.

---

## Authentication & Security Flows

### 1. WebAuthn Passkey Login
```text
User Input Email ──► Request Challenge ──► Generate WebAuthn Challenge
                                                     │
Bank Dashboard ◄── Create Session ◄── Verify Signature ◄── Platform Authenticator
                                                    (Touch ID / Face ID / PIN)
```

### 2. Email OTP Login
```text
User Input Email ──► Generate OTP ──► Hash with Bcrypt ──► Send via Resend
                                                              │
Bank Dashboard ◄── Create Session ◄── Match Hash ◄── User Enters 6-Digit OTP
```

### 3. QR Cross-Device Login
```text
Secondary Device (Untrusted)       Primary Device (Authorized)
      │                                       │
      ├─► Generates QR Token                  │
      ├─► Displays QR Code                    │
      │                                       ├─► Scans QR / Enters Token
      │                                       ├─► Confirms approval with Session
      │                                       └─► Approves Token (API)
      │                                               │
      ▼                                               ▼
Polls Token Status (Pending) ─────────────────► Token Approved ──► Creates Session
```

### 4. Transaction-Bound Step-Up Authentication
```text
Sensitive Action (e.g. Wire Transfer) ──► Generate Step-Up Challenge
                                                    │
Action Allowed ◄── Verify OTP against Hash ◄── Bind OTP to JSON Transaction Hash
```
*Note: Because the challenge is bound to the SHA-256 hash of the transaction payload, step-up tokens cannot be replayed or used to authorize a different transaction than what the user consented to.*

### 5. Delegated Co-Signer Passkey Flow
Designed to assist vulnerable users or delegate authentication for high-risk operations.
```text
1. Primary User invites Co-Signer ──► Sends Email with Secure Registration Link
                                                   │
2. Co-Signer opens on their device ──► Registers WebAuthn Passkey (Stored to Database)
                                                   │
3. Primary User triggers High-Risk Transfer ──► Challenge Created + Co-Signer Emailed Link
                                                   │
4. Co-Signer opens Link on own device ──► Approves with Passkey (Signs Verification)
                                                   │
5. Primary User Frontend polls Status ──► Clears Transaction when BOTH approvals pass
```

### 6. Geolocation Firewall Security Check
```text
User requests Step-Up/Transfer ──► Check Timezone, Locale, and Country Code (XFF-resilient)
                                                 │
      ┌──────────────────────────────────────────┴──────────────────────────────────────────┐
      ▼ (Home country "IN" / Localhost)                                                     ▼ (Foreign Timezone/Locale)
Request Allowed (Challenge Issued)                                                    403 Forbidden (Firewall Banned)
```

---

## Security & Privacy Design

### Public-Key Cryptography
Raw biometrics never reach the server. The authenticator generates a cryptographic signature using a device-secured private key, which is verified on the backend with the registered public key.

### Keyed IP Auditing (HMAC-SHA256)
To satisfy banking compliance without creating data privacy liabilities, raw client IP addresses are never written to the database. The system hashes each IP using HMAC-SHA256 keyed with `SECRET_KEY`. A single lookup resolves the IP to a rough city/country description for display.

### Geolocation Firewall
Evaluates timezone identifiers (`Asia/Kolkata` vs. foreign inputs like `London`, `Shanghai`, `America`, etc.) and language settings (`en-US`, `en-IN` vs. `zh-CN`, `ja-JP`). Step-up authorization is automatically denied for origins outside India (`IN`) to prevent remote fraud. The client's IP is read using `X-Forwarded-For` headers, preventing spoofing and ensuring compatibility with cloud gateways.

### Multi-Tier Email Resilience
Email notifications use the Resend SDK. To prevent delivery failure blocks during review or local testing:
1. **Primary Send:** Sends from verified branded domain (`security@doritovault.in`).
2. **First Fallback:** Sends from default Resend onboarding domain (`security@send.doritovault.in` or `onboarding@resend.dev`).
3. **Second Fallback:** Automatically forwards target emails to the registered administrator (`ADMIN_EMAIL`) as a demo header payload.
4. **Local Fallback:** Prints the plaintext message contents directly to the CLI backend console.

---

## Role-Gated Admin Portal

The application supports Role-Based Access Control (RBAC) to restrict administrative operations.

### Access Control
- **`role` Column:** Added to the `users` table (`'user'` or `'admin'`).
- **Endpoint Protection:** The `_require_admin` dependency gates access to admin-only API routes.
- **Dynamic UI Navigation:** The navbar template dynamically displays the "Admin Portal" link only when the authenticated session belongs to an administrator.

### Admin Dashboard (`/admin`)
Provides a security operations center for administrators to:
1. **View Cross-User Audit Logs:** Shows login histories, methods (`webauthn`, `otp`, `qr`, `recovery_code`), outcomes, and resolved locations.
2. **Review Sensitive Action Feeds:** Displays transaction step-up histories showing timestamps, transaction hashes, and status logs.
3. **Privacy Compliance:** In compliance with security standards, neither raw nor hashed IP addresses are exposed within the administrative UI.

---

## Premium Visual Design & Aesthetics

The UI features a customized layout built using custom CSS styling variables mapping into dynamic Tailwind configurations.

### Dynamic Themes
- **Warm Editorial (Light Mode):** Inspired by premium editorial designs. Uses cream/sand backgrounds (`#faf6ef`), terracotta/rust accents (`#c8552b`), custom card frames (`#f4ebdc`), and elegant `Fraunces` serif headings.
- **Emerald Fintech (Dark Mode):** Features slate-charcoal surfaces (`#0d0e12` body, `#15171e` panels) with neon matrix green accents (`#10b981`).

### UX Enhancements
- **Persistent Selection:** Theme settings are stored in `localStorage` and synchronized automatically across reloads.
- **Anti-Flash Scripting:** An inline blocking script executes in `<head>` to evaluate stored theme choices before the DOM paints, preventing bright white flashes for dark mode users.
- **Cursor Particle Trail:** An interactive mouse trail animation renders small fading particle trails on cursor movements.
- **Micro-Animations:** Fluid transitions, card hover scales, and soft backdrop blurs are applied globally.

---

## Tech Stack

- **Backend Framework:** FastAPI (v0.115.0)
- **Programming Language:** Python 3.11 / 3.12 (Python 3.11.9 pinned for precompiled bcrypt wheels)
- **Database ORM:** SQLAlchemy 2.0 + `psycopg3` driver
- **Database Engine:** PostgreSQL (hosted via Supabase) / SQLite fallback
- **Authentication Standards:** FIDO2 / WebAuthn (via the `webauthn` library)
- **Encryption & Hashing:** Passlib + bcrypt, Python `secrets`, HMAC-SHA256
- **Signed Sessions:** `itsdangerous` (HTTP-only, SameSite=Lax, Secure cookies)
- **Email Delivery:** Resend SDK
- **Rate Limiting:** `slowapi`
- **Frontend Engine:** Jinja2 Templates + Vanilla JS + Tailwind CSS CDN + FontAwesome 6

---

## Project Structure

```text
Destructive_Dorito_TechRush/
│
├── main.py                     # Entry point & app routes
├── database.py                 # SQLAlchemy connection & session setup
├── models.py                   # SQLAlchemy database schemas
├── schemas.py                  # Pydantic data schemas
├── requirements.txt            # Python dependencies
├── CONTRACT.md                 # Security compliance rules
├── Dockerfile                  # Application build setup
├── docker-compose.yml          # Container configuration
├── .env.example                # Example environment variables
│
├── routers/
│   ├── __init__.py
│   ├── auth_entry.py           # Section A (Registration, lockout, step-up challenges)
│   ├── security.py             # Section B (WebAuthn, OTP, QR authentication)
│   ├── co_signer.py            # Round 2 (Co-signer passkeys & approval workflows)
│   └── sessions.py             # Section C (Sessions, profiles, history, admin logging)
│
├── lib/
│   ├── __init__.py
│   ├── session_utils.py        # Centralized HTTP cookie session handlers
│   ├── email_utils.py          # Email delivery loops & Resend fallbacks
│   ├── lockout_utils.py        # Account brute force & lockout checks
│   ├── ip_utils.py             # Keyed HMAC IP hashing & geolocator
│   └── rate_limit.py           # Slowapi rate limit rules
│
├── templates/
│   ├── base.html               # Head, navbar, modals, design system tokens
│   ├── index.html              # Landing, registration, passwordless logins
│   ├── dashboard.html          # Primary account dashboard
│   ├── admin_dashboard.html    # Role-gated admin portal
│   └── security_test.html      # Sandbox testing console
│
├── static/
│   ├── css/
│   │   └── style.css           # Design tokens, variables, & cursor trail
│   └── js/
│       └── app.js              # WebAuthn, QR polling, co-signer hooks
│
└── alembic/                    # Database migrations
```

---

## Getting Started

### Prerequisites
- Python 3.11.x (Recommended: Python 3.11.9 for wheel stability)
- PostgreSQL database instance or Supabase project URL
- Git
- WebAuthn-compliant browser (Chrome, Safari, Edge, Firefox)

---

### 1. Clone the Repository
```bash
git clone https://github.com/shreyank26pal-dev/Destructive_Dorito_TechRush.git
cd Destructive_Dorito_TechRush
```

### 2. Configure a Virtual Environment
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

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the root directory using `.env.example`:
```env
DATABASE_URL=postgresql://user:password@host:port/dbname
SECRET_KEY=your-highly-secure-shared-secret-key-goes-here
RESEND_API_KEY=re_your_resend_api_key

WEBAUTHN_RP_ID=localhost
WEBAUTHN_RP_NAME=Dorito Vault
WEBAUTHN_ORIGIN=http://localhost:8000

SESSION_COOKIE_NAME=session_token
SESSION_EXPIRE_MINUTES=1440
OTP_EXPIRE_MINUTES=5

ENVIRONMENT=development
ADMIN_EMAIL=your-email@example.com
```
> [!WARNING]
> Do not commit real `.env` secrets. The `.env` file is excluded via `.gitignore`.

### 5. Run the Server
```bash
uvicorn main:app --reload
```
Navigate to:
```text
http://localhost:8000
```
> [!IMPORTANT]
> Access the site via **`localhost`**, not `127.0.0.1`. WebAuthn validates RP IDs strictly against the browser origin, and registration will fail on numeric IPs.

---

## API Reference

### Entry & Device Recognition

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/entry/register` | Register a new user profile |
| `POST` | `/api/entry/check-device` | Calculate/record browser fingerprint |
| `GET` | `/api/entry/alerts/{user_id}` | Fetch active alerts for a profile |
| `POST` | `/api/entry/step-up/challenge` | Create transaction-bound step-up challenge |

### WebAuthn Passkeys

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/security/webauthn/register-options` | Generate WebAuthn passkey registration challenge |
| `POST` | `/api/security/webauthn/register-verify` | Verify and save public passkey credential |
| `POST` | `/api/security/webauthn/login-options` | Generate WebAuthn assertion challenge |
| `POST` | `/api/security/webauthn/login-verify` | Verify passkey signature and start session |

### Hashed Email OTP

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/security/otp/send` | Send 6-digit OTP code to verified email |
| `POST` | `/api/security/otp/verify` | Verify OTP code and start session |

### QR Cross-Device Login

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/security/qr/generate` | Create temporary QR cross-device token |
| `GET` | `/api/security/qr/status/{token}` | Poll registration status of QR token |
| `POST` | `/api/security/qr/approve` | Approve secondary device sign-in |

### Co-Signer Operations

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/security/co-signer/invite` | Invite a delegated co-signer via email |
| `POST` | `/api/security/co-signer/register-options` | Generate passkey registration options for co-signer |
| `POST` | `/api/security/co-signer/register-verify` | Verify and save co-signer public passkey |
| `POST` | `/api/security/co-signer/approve-options` | Generate approval challenge for high-risk transfer |
| `POST` | `/api/security/co-signer/approve-verify` | Verify co-signer approval signature |
| `POST` | `/api/security/co-signer/deny` | Decline transaction approval request |
| `GET` | `/api/security/co-signer/approval-status/{request_id}` | Poll co-signer approval state |
| `GET` | `/api/security/co-signer/transaction-status/{challenge_id}`| Unified verification status (User OTP + Co-Signer passkey) |

### Sessions & Admin Operations

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/sessions/me` | Fetch active user context |
| `POST` | `/api/sessions/logout` | Terminate current session cookie |
| `POST` | `/api/sessions/logout-all` | Revoke all session records for a profile |
| `GET` | `/api/sessions/login-history` | View current user audit trail |
| `GET` | `/api/sessions/admin/audit-log` | Admin-only cross-user audit log (IP-anonymized) |
| `GET` | `/api/sessions/admin/sensitive-actions` | Admin-only feed of step-up authenticated actions |

---

## Database Design

The application utilizes PostgreSQL managed via SQLAlchemy.

### Database Tables Diagram
```text
users (Profile details, lockout status, user/admin role)
 ├── credentials (Passkey credentials, public keys, counters)
 ├── devices (Recognized user browsers and trust status)
 ├── sessions (Active browser session state, expiry, revocation)
 ├── login_history (Audit logs, HMAC-hashed IPs, resolved locations)
 ├── otp_codes (Bcrypt-hashed single-use email login codes)
 ├── email_verification_codes (Hashed sign-up confirmations)
 ├── recovery_codes (Emergency backup access hashes)
 ├── co_signers (Designated co-signer profiles and invites)
 ├── co_signer_credentials (Co-signer WebAuthn public keys)
 └── co_signer_approval_requests (Delegated approval records)
```

### Core Schema Definitions
- **`users`**: Contains email, name, role (`admin` or `user`), and `locked_until` (brute-force protection).
- **`co_signers`**: Stores co-signer contacts, invite tokens (`invite_token`), and validation state (`registered`).
- **`co_signer_credentials`**: Stores co-signer WebAuthn credentials (`public_key` as binary, signature counters).
- **`co_signer_approval_requests`**: Stores approval entries linked to high-risk transaction hashes, including their status (`pending`, `approved`, `denied`, `expired`).
- **`login_history`**: Records authentication events. The `ip_address` field stores an HMAC-SHA256 string for privacy compliance, while `city` and `country` store lookup information.

> [!IMPORTANT]
> **Database Schema Migration Note**
> If you recreate or reset the Supabase database, execute the following SQL commands to verify columns:
> ```sql
> ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR NOT NULL DEFAULT 'user';
> ALTER TABLE login_history ADD COLUMN IF NOT EXISTS city TEXT;
> ALTER TABLE login_history ADD COLUMN IF NOT EXISTS country TEXT;
> ```

---

## Testing & Diagnostics

### Security Sandbox `/test/security`
An interactive control center containing visual debuggers for:
- Passkey registration and login.
- Email OTP triggering and local console verification.
- Cross-device QR login generation, polling, and approval.
- High-risk transaction inputs and co-signer approval request status trackers.

### Interactive OpenAPI Documentation `/docs`
FastAPI's automatically generated Swagger UI allows for direct execution of endpoints, parameter testing, and schema validation.

### Health Endpoints
- **Endpoint:** `GET /health`
- **Response:**
  ```json
  {"status": "ok"}
  ```

---

## Production Considerations

As a **hackathon prototype**, the following hardening steps are recommended before deploying Dorito Vault in a production environment:

1. **Move WebAuthn Challenges to Shared Memory:** PENDING challenges are currently stored in an in-memory dictionary. Multi-worker setups must replace this with a Redis store.
2. **Require Session Authorization for QR Approvals:** Ensure the device approving a secondary QR login owns a fully authenticated and active session cookie.
3. **Use HTTPS Everywhere:** Strict cookie options (`Secure`) and WebAuthn signatures require HTTPS transport layer security outside of local development.
4. **Implement Formal Migrations:** Transition schema generation from automatic startup hooks (`create_all()`) to managed Alembic scripts.
5. **Implement Adaptive MFA:** Enforce combination rules (e.g., Passkey + OTP) dynamically based on calculated risk models rather than allowing single-factor login alternatives.
6. **Enhance CSRF Protections:** Implement secure request routing with CSRF state assertions on all banking dashboards.

---

## Unique Selling Propositions (USPs)

- **Biometric Security, Zero Privacy Risk:** WebAuthn public keys are stored, never users' raw biometric data.
- **Privacy-Preserving Auditing:** IP audit logs store keyed hashes, preventing compliance issues if database tables leak.
- **Delegated Vulnerability Shield:** Co-signers can secure high-risk actions for elderly or vulnerable users on their own devices.
- **Reverse Proxy Resilience:** The IP-timezone geolocation firewall handles remote reverse-proxy headers reliably to prevent spoofing.
- **Dynamic UX Aesthetics:** Clean Editorial theme options with page flash prevention and custom animations.

---

## Future Scope

- **AI-Driven Fraud Detection:** Evaluates behavior patterns to assign real-time risk ratings, triggering step-up workflows on suspicious requests.
- **Mobile Push Auth:** Replaces email notifications with push notifications to speed up approvals.
- **Multi-Node Deployment Configurations:** Cloud-optimized Redis caching configurations for shared temporary challenge objects.
- **Admin Dashboard Role-Gating:** Further gates all administrative pages behind cryptographic MFA challenges.

---

## Team

**Team:** Destructive Dorito
**Project:** Dorito Vault — Passwordless Bank Authentication
**Hackathon:** TechRush

### Contributors
- Sharmad Kulkarni
- Shreyank Pal
- Sujal Dhonsale

---

## License

This project was developed as a hackathon prototype for educational and demonstration purposes. Review and adapt all security, cryptography, and session configurations before deployment.
