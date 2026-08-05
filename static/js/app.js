/**
 * iProov Biometric Authentication Client Engine
 * Follows CONTRACT.md conventions
 */

// Global State
let currentUser = null;
let deviceFingerprint = null;
let pendingChallenge = null;

// Cookie Banner Dismissal
function dismissCookieBanner() {
  const banner = document.getElementById('cookie-banner');
  if (banner) {
    banner.style.display = 'none';
  }
}

// Helper: Convert ArrayBuffer to Base64URL string
function bufferToBase64URL(buffer) {
  const bytes = new Uint8Array(buffer);
  let string = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    string += String.fromCharCode(bytes[i]);
  }
  return btoa(string)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}

// Helper: Convert Base64URL string to ArrayBuffer
function base64URLToBuffer(base64url) {
  let base64 = base64url.replace(/-/g, '+').replace(/_/g, '/');
  while (base64.length % 4) {
    base64 += '=';
  }
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray.buffer;
}

// Compute client device fingerprint
function computeDeviceFingerprint() {
  const components = [
    navigator.userAgent,
    navigator.language,
    screen.width + 'x' + screen.height,
    screen.colorDepth,
    new Date().getTimezoneOffset(),
    navigator.platform || ''
  ].join('||');
  
  let hash = 0;
  for (let i = 0; i < components.length; i++) {
    const char = components.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash |= 0;
  }
  return 'fp_' + Math.abs(hash).toString(16);
}

// Toast Notifications
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast-item toast-item-${type}`;
  
  let icon = 'fa-info-circle';
  if (type === 'success') icon = 'fa-shield-check';
  if (type === 'error') icon = 'fa-circle-exclamation';

  toast.innerHTML = `<i class="fas ${icon} fs-5"></i> <span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Generic API wrapper
async function apiCall(url, method = 'GET', data = null) {
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (data) {
    options.body = JSON.stringify(data);
  }

  try {
    const response = await fetch(url, options);
    const resData = await response.json();
    return resData;
  } catch (err) {
    console.error(`API Call failed (${url}):`, err);
    return { status: 'error', message: err.message || 'Network connectivity error' };
  }
}

// DOM Loaded Initialization
document.addEventListener('DOMContentLoaded', async () => {
  deviceFingerprint = computeDeviceFingerprint();

  const fpDisplay = document.getElementById('fp-display');
  if (fpDisplay) {
    fpDisplay.innerText = deviceFingerprint;
  }

  await checkAuthSession();
});

// Check active session (/api/sessions/me)
async function checkAuthSession() {
  const res = await apiCall('/api/sessions/me');
  const path = window.location.pathname;

  if (res.status === 'success' && res.data) {
    currentUser = res.data;

    const userBadge = document.getElementById('nav-user-badge');
    const userNameEl = document.getElementById('nav-user-name');
    if (userBadge && userNameEl) {
      userNameEl.innerText = (currentUser.name || currentUser.email).toUpperCase();
      userBadge.classList.remove('d-none');
    }

    if (path === '/' || path === '/index.html') {
      const authBanner = document.getElementById('auth-banner');
      if (authBanner) {
        authBanner.classList.remove('d-none');
      }
    } else if (path === '/dashboard' || path === '/dashboard.html') {
      initDashboard();
    }
  } else {
    currentUser = null;
    if (path === '/dashboard' || path === '/dashboard.html') {
      window.location.href = '/';
    }
  }
}

// Register New User
async function handleRegister(event) {
  event.preventDefault();
  const name = document.getElementById('reg-name').value.trim();
  const email = document.getElementById('reg-email').value.trim();

  if (!email) {
    showToast('Please enter a valid email address.', 'error');
    return;
  }

  const btn = document.getElementById('btn-register');
  btn.disabled = true;
  btn.innerText = 'ENROLLING USER...';

  // 1. Register User
  const res = await apiCall('/api/entry/register', 'POST', { name, email });
  if (res.status !== 'success') {
    showToast(res.message || 'Registration failed.', 'error');
    btn.disabled = false;
    btn.innerText = 'CREATE ACCOUNT & ENROLL BIOMETRICS';
    return;
  }

  const userId = res.data.id;
  showToast('Account registered successfully!', 'success');

  // 2. Register Device
  await apiCall('/api/entry/check-device', 'POST', {
    user_id: userId,
    fingerprint: deviceFingerprint
  });

  // Prompt for WebAuthn passkey
  const setupPasskey = confirm('User registered! Enroll biometric FIDO2 Passkey now for passwordless authentication?');
  if (setupPasskey) {
    await registerWebAuthn(email);
  }

  btn.disabled = false;
  btn.innerText = 'CREATE ACCOUNT & ENROLL BIOMETRICS';
  switchTab('login');
}

// WebAuthn Passkey Registration
async function registerWebAuthn(email) {
  if (!email) {
    showToast('Email required for passkey enrollment.', 'error');
    return;
  }

  try {
    showToast('Initiating FIDO2 Passkey registration ceremony...', 'info');

    const optionsRes = await apiCall('/api/security/webauthn/register-options', 'POST', { email });
    if (optionsRes.status !== 'success') {
      showToast(optionsRes.message || 'Failed to fetch registration options.', 'error');
      return;
    }

    const options = optionsRes.data;
    options.challenge = base64URLToBuffer(options.challenge);
    options.user.id = base64URLToBuffer(options.user.id);
    if (options.excludeCredentials) {
      options.excludeCredentials = options.excludeCredentials.map(c => ({
        ...c,
        id: base64URLToBuffer(c.id)
      }));
    }

    const credential = await navigator.credentials.create({ publicKey: options });

    const credentialJSON = {
      id: credential.id,
      rawId: bufferToBase64URL(credential.rawId),
      type: credential.type,
      response: {
        attestationObject: bufferToBase64URL(credential.response.attestationObject),
        clientDataJSON: bufferToBase64URL(credential.response.clientDataJSON),
      }
    };

    const verifyRes = await apiCall('/api/security/webauthn/register-verify', 'POST', {
      email,
      credential: credentialJSON
    });

    if (verifyRes.status === 'success') {
      showToast('Biometric Passkey registered successfully!', 'success');
    } else {
      showToast(verifyRes.message || 'Passkey verification failed.', 'error');
    }
  } catch (err) {
    console.error("WebAuthn Register Error:", err);
    showToast(err.message || 'Passkey enrollment cancelled.', 'error');
  }
}

// WebAuthn Passkey Login
async function handleWebAuthnLogin(event) {
  if (event) event.preventDefault();
  const email = document.getElementById('login-email').value.trim();
  if (!email) {
    showToast('Please enter your account email address.', 'error');
    return;
  }

  try {
    showToast('Requesting biometric authentication clearance...', 'info');

    const optionsRes = await apiCall('/api/security/webauthn/login-options', 'POST', { email });
    if (optionsRes.status !== 'success') {
      showToast(optionsRes.message || 'No passkey registered for this account.', 'error');
      return;
    }

    const options = optionsRes.data;
    options.challenge = base64URLToBuffer(options.challenge);
    if (options.allowCredentials) {
      options.allowCredentials = options.allowCredentials.map(c => ({
        ...c,
        id: base64URLToBuffer(c.id)
      }));
    }

    const assertion = await navigator.credentials.get({ publicKey: options });

    const credentialJSON = {
      id: assertion.id,
      rawId: bufferToBase64URL(assertion.rawId),
      type: assertion.type,
      response: {
        authenticatorData: bufferToBase64URL(assertion.response.authenticatorData),
        clientDataJSON: bufferToBase64URL(assertion.response.clientDataJSON),
        signature: bufferToBase64URL(assertion.response.signature),
        userHandle: assertion.response.userHandle ? bufferToBase64URL(assertion.response.userHandle) : null
      }
    };

    const verifyRes = await apiCall('/api/security/webauthn/login-verify', 'POST', {
      email,
      credential: credentialJSON,
      device_fingerprint: deviceFingerprint
    });

    if (verifyRes.status === 'success') {
      showToast('Biometric verification success! Opening portal...', 'success');
      setTimeout(() => { window.location.href = '/dashboard'; }, 800);
    } else {
      showToast(verifyRes.message || 'Biometric verification failed.', 'error');
    }
  } catch (err) {
    console.error("WebAuthn Login Error:", err);
    showToast(err.message || 'Biometric authentication cancelled.', 'error');
  }
}

// Send Hashed OTP
let otpCountdownTimer = null;
async function handleSendOTP() {
  const email = document.getElementById('login-email').value.trim();
  if (!email) {
    showToast('Please enter your email to receive an OTP.', 'error');
    return;
  }

  const btnSend = document.getElementById('btn-send-otp');
  btnSend.disabled = true;
  btnSend.innerText = 'SENDING OTP...';

  const res = await apiCall('/api/security/otp/send', 'POST', { email });
  if (res.status === 'success') {
    showToast('5-minute Ephemeral Hashed OTP sent!', 'success');
    document.getElementById('otp-section').classList.remove('d-none');
    
    let secondsLeft = 60;
    btnSend.innerText = `RESEND (${secondsLeft}s)`;
    clearInterval(otpCountdownTimer);
    otpCountdownTimer = setInterval(() => {
      secondsLeft--;
      if (secondsLeft <= 0) {
        clearInterval(otpCountdownTimer);
        btnSend.disabled = false;
        btnSend.innerText = 'SEND HASHED EMAIL OTP';
      } else {
        btnSend.innerText = `RESEND (${secondsLeft}s)`;
      }
    }, 1000);
  } else {
    showToast(res.message || 'Failed to send OTP.', 'error');
    btnSend.disabled = false;
    btnSend.innerText = 'SEND HASHED EMAIL OTP';
  }
}

// Verify OTP
async function handleVerifyOTP(event) {
  event.preventDefault();
  const email = document.getElementById('login-email').value.trim();
  const code = document.getElementById('otp-code').value.trim();

  if (!email || !code) {
    showToast('Please enter email and 6-digit code.', 'error');
    return;
  }

  const btnVerify = document.getElementById('btn-verify-otp');
  btnVerify.disabled = true;
  btnVerify.innerText = 'VERIFYING...';

  const res = await apiCall('/api/security/otp/verify', 'POST', {
    email,
    code,
    device_fingerprint: deviceFingerprint
  });

  if (res.status === 'success') {
    showToast('OTP verified! Opening portal...', 'success');
    setTimeout(() => { window.location.href = '/dashboard'; }, 800);
  } else {
    showToast(res.message || 'Invalid or expired OTP code.', 'error');
    btnVerify.disabled = false;
    btnVerify.innerText = 'VERIFY';
  }
}

// Tab Switcher
function switchTab(tabName) {
  const tabLogin = document.getElementById('tab-login-btn');
  const tabReg = document.getElementById('tab-reg-btn');
  const formLogin = document.getElementById('form-login');
  const formReg = document.getElementById('form-reg');

  if (!formLogin || !formReg) return;

  if (tabName === 'login') {
    tabLogin.classList.add('active', 'text-warning');
    tabReg.classList.remove('active', 'text-warning');
    tabReg.classList.add('text-light');
    formLogin.classList.remove('d-none');
    formReg.classList.add('d-none');
  } else {
    tabReg.classList.add('active', 'text-warning');
    tabLogin.classList.remove('active', 'text-warning');
    tabLogin.classList.add('text-light');
    formReg.classList.remove('d-none');
    formLogin.classList.add('d-none');
  }
}

// ---------------------------------------------------------------------------
// DASHBOARD LOGIC
// ---------------------------------------------------------------------------

async function initDashboard() {
  if (!currentUser) return;

  document.getElementById('dash-user-name').innerText = currentUser.name || 'Security Admin';
  document.getElementById('dash-user-email').innerText = currentUser.email;
  document.getElementById('profile-name-input').value = currentUser.name || '';
  document.getElementById('profile-email-input').value = currentUser.email;

  fetchSecurityAlerts(currentUser.id);
  fetchLoginHistory();
}

// Fetch Risk Alerts
async function fetchSecurityAlerts(userId) {
  const container = document.getElementById('alerts-container');
  if (!container) return;

  const res = await apiCall(`/api/entry/alerts/${userId}`);
  if (res.status === 'success' && res.data) {
    const alerts = res.data;
    if (alerts.length === 0) {
      container.innerHTML = `
        <div class="p-3 bg-success bg-opacity-10 border border-success text-success rounded d-flex align-items-center gap-3">
          <i class="fas fa-shield-check fs-4"></i>
          <div>
            <h6 class="fw-bold mb-0">Liveness Security Status: OPTIMAL</h6>
            <small>No untrusted devices or suspicious authentication spikes detected.</small>
          </div>
        </div>
      `;
    } else {
      container.innerHTML = alerts.map(a => {
        if (a.type === 'untrusted_device') {
          return `
            <div class="p-3 bg-warning bg-opacity-10 border border-warning text-dark rounded d-flex align-items-start gap-3 mb-2">
              <i class="fas fa-exclamation-triangle text-warning fs-4 mt-1"></i>
              <div>
                <h6 class="fw-bold mb-1">Untrusted Device Registered</h6>
                <small class="d-block text-secondary">Fingerprint: <code class="bg-dark text-warning px-1 rounded">${a.fingerprint}</code></small>
                <small class="text-muted">First Seen: ${new Date(a.first_seen_at).toLocaleString()}</small>
              </div>
            </div>
          `;
        } else if (a.type === 'repeated_failed_logins') {
          return `
            <div class="p-3 bg-danger bg-opacity-10 border border-danger text-danger rounded d-flex align-items-start gap-3 mb-2">
              <i class="fas fa-shield-exclamation text-danger fs-4 mt-1"></i>
              <div>
                <h6 class="fw-bold mb-1">Alert: ${a.count} Failed Authentication Attempts</h6>
                <small>Multiple unauthorized authentication attempts within the last ${a.window_minutes} minutes.</small>
              </div>
            </div>
          `;
        }
        return '';
      }).join('');
    }
  }
}

// Fetch Audit History
async function fetchLoginHistory() {
  const tbody = document.getElementById('history-tbody');
  if (!tbody) return;

  const res = await apiCall('/api/sessions/login-history?limit=25');
  if (res.status === 'success' && res.data) {
    const logs = res.data;
    if (logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-muted small">No authentication logs recorded yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = logs.map(log => {
      let badgeClass = 'bg-primary';
      let icon = 'fa-fingerprint';
      if (log.method === 'otp') { badgeClass = 'bg-info text-dark'; icon = 'fa-envelope-open-text'; }
      if (log.method === 'qr') { badgeClass = 'bg-success'; icon = 'fa-qrcode'; }

      const statusBadge = log.success
        ? `<span class="badge bg-success"><i class="fas fa-check-circle me-1"></i> VERIFIED</span>`
        : `<span class="badge bg-danger"><i class="fas fa-times-circle me-1"></i> REJECTED</span>`;

      return `
        <tr>
          <td>
            <span class="badge ${badgeClass} font-mono">
              <i class="fas ${icon} me-1"></i> ${log.method.toUpperCase()}
            </span>
          </td>
          <td>${statusBadge}</td>
          <td class="font-mono small text-secondary">${log.ip_address || '127.0.0.1'}</td>
          <td class="font-mono small text-secondary text-truncate" style="max-width: 200px;">${log.device_info || '—'}</td>
          <td class="small text-secondary">${new Date(log.created_at).toLocaleString()}</td>
        </tr>
      `;
    }).join('');
  }
}

// Profile update
async function handleUpdateProfile(event) {
  event.preventDefault();
  const name = document.getElementById('profile-name-input').value.trim();

  const res = await apiCall('/api/sessions/profile/update', 'POST', { name });
  if (res.status === 'success') {
    showToast('Profile updated successfully!', 'success');
    currentUser.name = name;
    document.getElementById('dash-user-name').innerText = name || 'Security Admin';
    document.getElementById('nav-user-name').innerText = (name || currentUser.email).toUpperCase();
  } else {
    showToast(res.message || 'Profile update failed.', 'error');
  }
}

// Passkey register from dashboard
async function handleDashboardRegisterPasskey() {
  if (!currentUser || !currentUser.email) return;
  await registerWebAuthn(currentUser.email);
}

// Logout
async function handleLogout() {
  const res = await apiCall('/api/sessions/logout', 'POST');
  if (res.status === 'success') {
    showToast('Terminated portal session.', 'info');
    setTimeout(() => { window.location.href = '/'; }, 500);
  } else {
    showToast(res.message || 'Logout failed.', 'error');
  }
}

// Logout All
async function handleLogoutAll() {
  if (!confirm('Revoke all active sessions across all devices?')) return;

  const res = await apiCall('/api/sessions/logout-all', 'POST');
  if (res.status === 'success') {
    showToast('Revoked all active sessions. Redirecting...', 'info');
    setTimeout(() => { window.location.href = '/'; }, 800);
  } else {
    showToast(res.message || 'Failed to revoke sessions.', 'error');
  }
}
