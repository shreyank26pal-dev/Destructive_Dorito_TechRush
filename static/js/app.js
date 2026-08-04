/**
 * SecureBank Passwordless Auth Client JS
 * Follows CONTRACT.md conventions
 */

// Global State (CONTRACT.md Section 8)
let currentUser = null;
let deviceFingerprint = null;
let pendingChallenge = null;

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

// Generate client device fingerprint
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
  toast.className = `toast toast-${type}`;
  
  let icon = 'fa-info-circle';
  if (type === 'success') icon = 'fa-check-circle';
  if (type === 'error') icon = 'fa-exclamation-circle';

  toast.innerHTML = `<i class="fas ${icon} text-lg"></i> <span>${message}</span>`;
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
    return { status: 'error', message: err.message || 'Network error occurred' };
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
  deviceFingerprint = computeDeviceFingerprint();
  console.log("Computed Device Fingerprint:", deviceFingerprint);

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
    console.log("Logged in user:", currentUser);

    const userBadge = document.getElementById('nav-user-badge');
    const userNameEl = document.getElementById('nav-user-name');
    if (userBadge && userNameEl) {
      userNameEl.innerText = currentUser.name || currentUser.email;
      userBadge.classList.remove('hidden');
    }

    if (path === '/' || path === '/index.html') {
      const loginCard = document.getElementById('login-card');
      const authBanner = document.getElementById('auth-banner');
      if (loginCard && authBanner) {
        authBanner.classList.remove('hidden');
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

// ---------------------------------------------------------------------------
// AUTHENTICATION LOGIC (INDEX PAGE)
// ---------------------------------------------------------------------------

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
  btn.innerText = 'Creating account...';

  // 1. Register User
  const res = await apiCall('/api/entry/register', 'POST', { name, email });
  if (res.status !== 'success') {
    showToast(res.message || 'Registration failed', 'error');
    btn.disabled = false;
    btn.innerText = 'Create Account';
    return;
  }

  const userId = res.data.id;
  showToast('Account created successfully!', 'success');

  // 2. Check & Register Device
  await apiCall('/api/entry/check-device', 'POST', {
    user_id: userId,
    fingerprint: deviceFingerprint
  });

  // Option to set up WebAuthn passkey immediately
  const setupPasskey = confirm('Account created! Would you like to register a Biometrics / Passkey (TouchID, FaceID, Windows Hello) for fast passwordless logins?');
  if (setupPasskey) {
    await registerWebAuthn(email);
  }

  btn.disabled = false;
  btn.innerText = 'Create Account';
  switchTab('login');
}

// WebAuthn Passkey Registration
async function registerWebAuthn(email) {
  if (!email) {
    showToast('Email is required for passkey registration.', 'error');
    return;
  }

  try {
    showToast('Preparing Passkey registration...', 'info');

    // 1. Get options from backend
    const optionsRes = await apiCall('/api/security/webauthn/register-options', 'POST', { email });
    if (optionsRes.status !== 'success') {
      showToast(optionsRes.message || 'Failed to initialize passkey registration.', 'error');
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

    // 2. Browser WebAuthn prompt
    const credential = await navigator.credentials.create({ publicKey: options });

    // 3. Prepare response JSON payload
    const credentialJSON = {
      id: credential.id,
      rawId: bufferToBase64URL(credential.rawId),
      type: credential.type,
      response: {
        attestationObject: bufferToBase64URL(credential.response.attestationObject),
        clientDataJSON: bufferToBase64URL(credential.response.clientDataJSON),
      }
    };

    // 4. Verify with backend
    const verifyRes = await apiCall('/api/security/webauthn/register-verify', 'POST', {
      email,
      credential: credentialJSON
    });

    if (verifyRes.status === 'success') {
      showToast('Biometrics / Passkey registered successfully!', 'success');
    } else {
      showToast(verifyRes.message || 'Passkey verification failed.', 'error');
    }
  } catch (err) {
    console.error("WebAuthn Register Error:", err);
    showToast(err.message || 'Passkey registration cancelled or failed.', 'error');
  }
}

// WebAuthn Passkey Login
async function handleWebAuthnLogin(event) {
  if (event) event.preventDefault();
  const email = document.getElementById('login-email').value.trim();
  if (!email) {
    showToast('Please enter your account email first.', 'error');
    return;
  }

  try {
    showToast('Requesting biometric prompt...', 'info');

    // 1. Get login options
    const optionsRes = await apiCall('/api/security/webauthn/login-options', 'POST', { email });
    if (optionsRes.status !== 'success') {
      showToast(optionsRes.message || 'Could not fetch passkey options.', 'error');
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

    // 2. Browser credentials prompt
    const assertion = await navigator.credentials.get({ publicKey: options });

    // 3. Format payload
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

    // 4. Verify login with backend
    const verifyRes = await apiCall('/api/security/webauthn/login-verify', 'POST', {
      email,
      credential: credentialJSON,
      device_fingerprint: deviceFingerprint
    });

    if (verifyRes.status === 'success') {
      showToast('Biometric login successful! Redirecting...', 'success');
      setTimeout(() => { window.location.href = '/dashboard'; }, 1000);
    } else {
      showToast(verifyRes.message || 'Biometric authentication failed.', 'error');
    }
  } catch (err) {
    console.error("WebAuthn Login Error:", err);
    showToast(err.message || 'Passkey login failed or was cancelled.', 'error');
  }
}

// Send OTP
let otpCountdownTimer = null;
async function handleSendOTP() {
  const email = document.getElementById('login-email').value.trim();
  if (!email) {
    showToast('Please enter your email to receive an OTP.', 'error');
    return;
  }

  const btnSend = document.getElementById('btn-send-otp');
  btnSend.disabled = true;
  btnSend.innerText = 'Sending...';

  const res = await apiCall('/api/security/otp/send', 'POST', { email });
  if (res.status === 'success') {
    showToast('OTP sent to your email! (Check console if demo server)', 'success');
    document.getElementById('otp-section').classList.remove('hidden');
    
    // Start 60s cooldown timer
    let secondsLeft = 60;
    btnSend.innerText = `Resend (${secondsLeft}s)`;
    clearInterval(otpCountdownTimer);
    otpCountdownTimer = setInterval(() => {
      secondsLeft--;
      if (secondsLeft <= 0) {
        clearInterval(otpCountdownTimer);
        btnSend.disabled = false;
        btnSend.innerText = 'Send OTP';
      } else {
        btnSend.innerText = `Resend (${secondsLeft}s)`;
      }
    }, 1000);
  } else {
    showToast(res.message || 'Failed to send OTP.', 'error');
    btnSend.disabled = false;
    btnSend.innerText = 'Send OTP';
  }
}

// Verify OTP Login
async function handleVerifyOTP(event) {
  event.preventDefault();
  const email = document.getElementById('login-email').value.trim();
  const code = document.getElementById('otp-code').value.trim();

  if (!email || !code) {
    showToast('Please enter both email and 6-digit OTP code.', 'error');
    return;
  }

  const btnVerify = document.getElementById('btn-verify-otp');
  btnVerify.disabled = true;
  btnVerify.innerText = 'Verifying...';

  const res = await apiCall('/api/security/otp/verify', 'POST', {
    email,
    code,
    device_fingerprint: deviceFingerprint
  });

  if (res.status === 'success') {
    showToast('OTP verified! Redirecting...', 'success');
    setTimeout(() => { window.location.href = '/dashboard'; }, 1000);
  } else {
    showToast(res.message || 'Invalid or expired OTP code.', 'error');
    btnVerify.disabled = false;
    btnVerify.innerText = 'Verify & Login';
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
    tabLogin.classList.add('border-indigo-500', 'text-indigo-400');
    tabLogin.classList.remove('border-transparent', 'text-gray-400');
    tabReg.classList.remove('border-indigo-500', 'text-indigo-400');
    tabReg.classList.add('border-transparent', 'text-gray-400');
    formLogin.classList.remove('hidden');
    formReg.classList.add('hidden');
  } else {
    tabReg.classList.add('border-indigo-500', 'text-indigo-400');
    tabReg.classList.remove('border-transparent', 'text-gray-400');
    tabLogin.classList.remove('border-indigo-500', 'text-indigo-400');
    tabLogin.classList.add('border-transparent', 'text-gray-400');
    formReg.classList.remove('hidden');
    formLogin.classList.add('hidden');
  }
}

// ---------------------------------------------------------------------------
// DASHBOARD LOGIC
// ---------------------------------------------------------------------------

async function initDashboard() {
  if (!currentUser) return;

  // 1. Fill Profile Data
  document.getElementById('dash-user-name').innerText = currentUser.name || 'Bank Customer';
  document.getElementById('dash-user-email').innerText = currentUser.email;
  document.getElementById('profile-name-input').value = currentUser.name || '';
  document.getElementById('profile-email-input').value = currentUser.email;

  // 2. Fetch Security Alerts
  fetchSecurityAlerts(currentUser.id);

  // 3. Fetch Login History Logs
  fetchLoginHistory();
}

async function fetchSecurityAlerts(userId) {
  const container = document.getElementById('alerts-container');
  if (!container) return;

  const res = await apiCall(`/api/entry/alerts/${userId}`);
  if (res.status === 'success' && res.data) {
    const alerts = res.data;
    if (alerts.length === 0) {
      container.innerHTML = `
        <div class="flex items-center gap-3 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm">
          <i class="fas fa-shield-check text-xl"></i>
          <div>
            <p class="font-semibold">All Clear</p>
            <p class="text-xs text-emerald-300/80">No suspicious devices or login anomalies detected on your account.</p>
          </div>
        </div>
      `;
    } else {
      container.innerHTML = alerts.map(a => {
        if (a.type === 'untrusted_device') {
          return `
            <div class="flex items-start gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-sm">
              <i class="fas fa-exclamation-triangle text-amber-400 text-xl mt-0.5"></i>
              <div>
                <p class="font-semibold">Untrusted Device Registered</p>
                <p class="text-xs text-amber-200/70 mt-1">Fingerprint: <code class="bg-black/30 px-1.5 py-0.5 rounded">${a.fingerprint}</code></p>
                <p class="text-xs text-amber-200/50 mt-0.5">First seen: ${new Date(a.first_seen_at).toLocaleString()}</p>
              </div>
            </div>
          `;
        } else if (a.type === 'repeated_failed_logins') {
          return `
            <div class="flex items-start gap-3 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm">
              <i class="fas fa-shield-exclamation text-rose-400 text-xl mt-0.5"></i>
              <div>
                <p class="font-semibold">Security Alert: ${a.count} Repeated Failed Logins</p>
                <p class="text-xs text-rose-200/70 mt-1">Multiple failed authentication attempts were detected in the last ${a.window_minutes} minutes.</p>
              </div>
            </div>
          `;
        }
        return '';
      }).join('');
    }
  }
}

async function fetchLoginHistory() {
  const tbody = document.getElementById('history-tbody');
  if (!tbody) return;

  const res = await apiCall('/api/sessions/login-history?limit=25');
  if (res.status === 'success' && res.data) {
    const logs = res.data;
    if (logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="py-6 text-center text-gray-500 text-sm">No login history recorded yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = logs.map(log => {
      let badgeClass = 'badge-webauthn';
      let icon = 'fa-fingerprint';
      if (log.method === 'otp') { badgeClass = 'badge-otp'; icon = 'fa-envelope-open-text'; }
      if (log.method === 'qr') { badgeClass = 'badge-qr'; icon = 'fa-qrcode'; }

      const statusBadge = log.success
        ? `<span class="px-2.5 py-1 text-xs rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"><i class="fas fa-check-circle mr-1"></i> Success</span>`
        : `<span class="px-2.5 py-1 text-xs rounded-full bg-rose-500/15 text-rose-400 border border-rose-500/30"><i class="fas fa-times-circle mr-1"></i> Failed</span>`;

      return `
        <tr class="border-b border-gray-800/50 hover:bg-white/5 transition-colors">
          <td class="py-3 px-4">
            <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium ${badgeClass}">
              <i class="fas ${icon}"></i> ${log.method.toUpperCase()}
            </span>
          </td>
          <td class="py-3 px-4">${statusBadge}</td>
          <td class="py-3 px-4 text-xs font-mono text-gray-400">${log.ip_address || 'unknown'}</td>
          <td class="py-3 px-4 text-xs text-gray-400 truncate max-w-xs">${log.device_info || '—'}</td>
          <td class="py-3 px-4 text-xs text-gray-400">${new Date(log.created_at).toLocaleString()}</td>
        </tr>
      `;
    }).join('');
  }
}

// Update Profile
async function handleUpdateProfile(event) {
  event.preventDefault();
  const name = document.getElementById('profile-name-input').value.trim();

  const res = await apiCall('/api/sessions/profile/update', 'POST', { name });
  if (res.status === 'success') {
    showToast('Profile updated successfully!', 'success');
    currentUser.name = name;
    document.getElementById('dash-user-name').innerText = name || 'Bank Customer';
    document.getElementById('nav-user-name').innerText = name || currentUser.email;
  } else {
    showToast(res.message || 'Failed to update profile.', 'error');
  }
}

// Passkey Registration from Dashboard
async function handleDashboardRegisterPasskey() {
  if (!currentUser || !currentUser.email) return;
  await registerWebAuthn(currentUser.email);
}

// Logout
async function handleLogout() {
  const res = await apiCall('/api/sessions/logout', 'POST');
  if (res.status === 'success') {
    showToast('Logged out successfully.', 'info');
    setTimeout(() => { window.location.href = '/'; }, 500);
  } else {
    showToast(res.message || 'Logout failed.', 'error');
  }
}

// Logout All
async function handleLogoutAll() {
  if (!confirm('Are you sure you want to revoke all active sessions across all devices?')) return;

  const res = await apiCall('/api/sessions/logout-all', 'POST');
  if (res.status === 'success') {
    showToast('Revoked all active sessions. Redirecting to home...', 'info');
    setTimeout(() => { window.location.href = '/'; }, 1000);
  } else {
    showToast(res.message || 'Failed to revoke sessions.', 'error');
  }
}
