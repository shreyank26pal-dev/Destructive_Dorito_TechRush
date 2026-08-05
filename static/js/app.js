/**
 * ==========================================================================
 * DORITO VAULT — NATURAL BOOTSTRAP 5 CLIENT ENGINE
 * Fully compliant with CONTRACT.md and FastAPI backend specifications.
 * ==========================================================================
 */

// Global State (CONTRACT.md Section 8)
let currentUser = null;
let deviceFingerprint = null;
let pendingChallenge = null;
let qrPollingInterval = null;

// ==========================================================================
// 1. WEBAUTHN / FIDO2 BASE64URL & ARRAYBUFFER HELPERS
// ==========================================================================

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

// ==========================================================================
// 2. HARDWARE DEVICE FINGERPRINTING & TOAST ENGINE
// ==========================================================================

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
  return 'hw_' + Math.abs(hash).toString(16);
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  let icon = 'fa-circle-info text-info';
  if (type === 'success') icon = 'fa-circle-check text-success';
  if (type === 'error') icon = 'fa-circle-exclamation text-danger';

  toast.innerHTML = `<i class="fas ${icon} text-base"></i> <span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.25s ease';
    setTimeout(() => toast.remove(), 250);
  }, 4500);
}

// ==========================================================================
// 3. GENERIC API WRAPPER
// ==========================================================================

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
    console.error(`[API Error] (${url}):`, err);
    return { status: 'error', message: err.message || 'Network communication error' };
  }
}

// ==========================================================================
// 4. INITIALIZATION, ENTRY ANIMATION & SESSION CHECK
// ==========================================================================

document.addEventListener('DOMContentLoaded', async () => {
  deviceFingerprint = computeDeviceFingerprint();
  console.log("Hardware Fingerprint Computed:", deviceFingerprint);

  const fpDisplay = document.getElementById('fp-display');
  if (fpDisplay) {
    fpDisplay.innerText = deviceFingerprint;
  }

  const regFpPreview = document.getElementById('reg-fp-preview');
  if (regFpPreview) {
    regFpPreview.innerText = deviceFingerprint;
  }

  initParticleCanvas();
  runIntroAnimation();
  await checkAuthSession();
});

function runIntroAnimation() {
  const overlay = document.getElementById('intro-overlay');
  const statusText = document.getElementById('intro-status-text');
  if (!overlay) return;

  setTimeout(() => {
    if (statusText) statusText.innerText = 'AUTHENTICATING BOOTSTRAP CORE...';
  }, 700);

  setTimeout(() => {
    if (statusText) statusText.innerText = 'ACCESS GRANTED TO DORITO VAULT';
  }, 1400);

  setTimeout(() => {
    overlay.classList.add('fade-out');
  }, 2000);
}

async function checkAuthSession() {
  const res = await apiCall('/api/sessions/me');
  const path = window.location.pathname;

  if (res.status === 'success' && res.data) {
    currentUser = res.data;
    console.log("Authenticated User:", currentUser);

    const userBadge = document.getElementById('nav-user-badge');
    const userNameEl = document.getElementById('nav-user-name');
    if (userBadge && userNameEl) {
      userNameEl.innerText = currentUser.name || currentUser.email;
      userBadge.classList.remove('hidden');
    }

    if (path === '/' || path === '/index.html') {
      const authBanner = document.getElementById('auth-banner');
      if (authBanner) {
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

// ==========================================================================
// 5. REGISTRATION & WEBAUTHN / FIDO2 BIOMETRICS
// ==========================================================================

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
  btn.innerText = 'Creating Account...';

  // 1. Register User in backend (/api/entry/register)
  const res = await apiCall('/api/entry/register', 'POST', { name, email });
  if (res.status !== 'success') {
    showToast(res.message || 'Registration failed.', 'error');
    btn.disabled = false;
    btn.innerText = 'Create Account';
    return;
  }

  const userId = res.data.id;
  showToast('Account created successfully!', 'success');

  // 2. Check & Register Device (/api/entry/check-device)
  await apiCall('/api/entry/check-device', 'POST', {
    user_id: userId,
    fingerprint: deviceFingerprint
  });

  // Prompt to register WebAuthn passkey
  const setupPasskey = confirm('Account created! Would you like to register a Hardware Biometrics / Passkey (TouchID, FaceID, Windows Hello) for instant passwordless logins?');
  if (setupPasskey) {
    await registerWebAuthn(email);
  }

  btn.disabled = false;
  btn.innerText = 'Create Account';
  switchTab('login');
  document.getElementById('login-email').value = email;
}

async function registerWebAuthn(email) {
  if (!email) {
    showToast('Email is required for passkey registration.', 'error');
    return;
  }

  try {
    showToast('Requesting FIDO2 passkey registration challenge...', 'info');

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

    // 2. Trigger browser WebAuthn prompt
    const credential = await navigator.credentials.create({ publicKey: options });

    // 3. Format response JSON payload
    const credentialJSON = {
      id: credential.id,
      rawId: bufferToBase64URL(credential.rawId),
      type: credential.type,
      response: {
        attestationObject: bufferToBase64URL(credential.response.attestationObject),
        clientDataJSON: bufferToBase64URL(credential.response.clientDataJSON),
      }
    };

    // 4. Send to backend for verification (/api/security/webauthn/register-verify)
    const verifyRes = await apiCall('/api/security/webauthn/register-verify', 'POST', {
      email,
      credential: credentialJSON
    });

    if (verifyRes.status === 'success') {
      showToast('Hardware Passkey registered successfully!', 'success');
    } else {
      showToast(verifyRes.message || 'Passkey registration failed verification.', 'error');
    }
  } catch (err) {
    console.error("WebAuthn Register Error:", err);
    showToast(err.message || 'Passkey registration cancelled or unsupported.', 'error');
  }
}

async function handleWebAuthnLogin(event) {
  if (event) event.preventDefault();
  const email = document.getElementById('login-email').value.trim();
  if (!email) {
    showToast('Please enter your account email first.', 'error');
    return;
  }

  try {
    showToast('Initiating biometric hardware authentication...', 'info');

    // 1. Get login options (/api/security/webauthn/login-options)
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

    // 4. Verify login with backend (/api/security/webauthn/login-verify)
    const verifyRes = await apiCall('/api/security/webauthn/login-verify', 'POST', {
      email,
      credential: credentialJSON,
      device_fingerprint: deviceFingerprint
    });

    if (verifyRes.status === 'success') {
      showToast('Biometric verification passed! Accessing Dorito Vault...', 'success');
      setTimeout(() => { window.location.href = '/dashboard'; }, 800);
    } else {
      showToast(verifyRes.message || 'Biometric authentication failed.', 'error');
    }
  } catch (err) {
    console.error("WebAuthn Login Error:", err);
    showToast(err.message || 'Biometric login cancelled or failed.', 'error');
  }
}

// ==========================================================================
// 6. HASHED EMAIL OTP FLOW
// ==========================================================================

let otpCountdownTimer = null;
async function handleSendOTP() {
  const email = document.getElementById('login-email').value.trim();
  if (!email) {
    showToast('Please enter your account email to receive an OTP.', 'error');
    return;
  }

  const btnSend = document.getElementById('btn-send-otp');
  btnSend.disabled = true;
  btnSend.innerText = 'Sending...';

  const res = await apiCall('/api/security/otp/send', 'POST', { email });
  if (res.status === 'success') {
    showToast('OTP code sent to your email! (Check backend console if in dev mode)', 'success');
    document.getElementById('otp-section').classList.remove('hidden');
    
    let secondsLeft = 60;
    btnSend.innerText = `Resend (${secondsLeft}s)`;
    clearInterval(otpCountdownTimer);
    otpCountdownTimer = setInterval(() => {
      secondsLeft--;
      if (secondsLeft <= 0) {
        clearInterval(otpCountdownTimer);
        btnSend.disabled = false;
        btnSend.innerText = 'Send Code';
      } else {
        btnSend.innerText = `Resend (${secondsLeft}s)`;
      }
    }, 1000);
  } else {
    showToast(res.message || 'Failed to send OTP.', 'error');
    btnSend.disabled = false;
    btnSend.innerText = 'Send Code';
  }
}

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
    showToast('OTP verified! Accessing Dorito Vault...', 'success');
    setTimeout(() => { window.location.href = '/dashboard'; }, 800);
  } else {
    showToast(res.message || 'Invalid or expired OTP code.', 'error');
    btnVerify.disabled = false;
    btnVerify.innerText = 'Verify & Login';
  }
}

// ==========================================================================
// 7. QR CROSS-DEVICE SYNC & POLLING
// ==========================================================================

async function toggleQrSection() {
  const qrSection = document.getElementById('qr-section');
  if (!qrSection) return;

  if (qrSection.classList.contains('hidden')) {
    qrSection.classList.remove('hidden');
    await startQrGeneration();
  } else {
    qrSection.classList.add('hidden');
    clearInterval(qrPollingInterval);
  }
}

async function startQrGeneration() {
  const qrContainer = document.getElementById('qr-container');
  const statusText = document.getElementById('qr-status-text');
  if (!qrContainer) return;

  qrContainer.innerHTML = '';
  statusText.innerText = 'Generating token...';

  const res = await apiCall('/api/security/qr/generate', 'POST', {
    device_fingerprint: deviceFingerprint
  });

  if (res.status === 'success' && res.data) {
    const token = res.data.token;
    statusText.innerText = 'Waiting for phone authorization...';

    // Render QR Code using QRCode library
    new QRCode(qrContainer, {
      text: token,
      width: 140,
      height: 140,
      colorDark: "#121416",
      colorLight: "#FFFFFF",
      correctLevel: QRCode.CorrectLevel.H
    });

    // Poll status every 2 seconds (/api/security/qr/status/{token})
    clearInterval(qrPollingInterval);
    qrPollingInterval = setInterval(async () => {
      const statusRes = await apiCall(`/api/security/qr/status/${token}`);
      if (statusRes.status === 'success' && statusRes.data) {
        const st = statusRes.data.status;
        if (st === 'approved') {
          clearInterval(qrPollingInterval);
          statusText.innerText = 'QR Authorized! Logging in...';
          showToast('Cross-device login approved by your mobile phone!', 'success');
          setTimeout(() => { window.location.href = '/dashboard'; }, 1000);
        } else if (st === 'expired' || st === 'denied') {
          clearInterval(qrPollingInterval);
          statusText.innerText = `Token ${st}. Refreshing...`;
          showToast(`QR session ${st}.`, 'error');
        }
      }
    }, 2000);
  } else {
    statusText.innerText = 'Failed to generate QR token.';
    showToast(res.message || 'QR generation error', 'error');
  }
}

function openQrApprovalModal() {
  const modal = document.getElementById('qr-approve-modal');
  if (modal) modal.classList.add('active');
  if (currentUser && currentUser.email) {
    document.getElementById('qr-approve-email').value = currentUser.email;
  }
}

function closeQrApprovalModal() {
  const modal = document.getElementById('qr-approve-modal');
  if (modal) modal.classList.remove('active');
}

async function handleApproveQrToken(event) {
  event.preventDefault();
  const email = document.getElementById('qr-approve-email').value.trim();
  const token = document.getElementById('qr-approve-token').value.trim();

  if (!email || !token) {
    showToast('Please fill in both email and QR token.', 'error');
    return;
  }

  const res = await apiCall('/api/security/qr/approve', 'POST', { token, email });
  if (res.status === 'success') {
    showToast('Login approved for the other device!', 'success');
    closeQrApprovalModal();
  } else {
    showToast(res.message || 'QR approval failed.', 'error');
  }
}

// ==========================================================================
// 8. STEP-UP AUTHENTICATION (FOR WIRE TRANSFERS & SENSITIVE ACTIONS)
// ==========================================================================

function triggerWireTransferStepUp() {
  if (!currentUser) return;
  const modal = document.getElementById('step-up-modal');
  document.getElementById('step-up-email').value = currentUser.email;
  document.getElementById('step-up-code').value = '';
  modal.classList.add('active');
}

function closeStepUpModal() {
  const modal = document.getElementById('step-up-modal');
  if (modal) modal.classList.remove('active');
}

async function handleSendStepUpOtp() {
  if (!currentUser || !currentUser.email) return;
  const res = await apiCall('/api/security/otp/send', 'POST', { email: currentUser.email });
  if (res.status === 'success') {
    showToast('Step-Up OTP code sent to your email!', 'success');
  } else {
    showToast(res.message || 'Failed to send Step-Up OTP.', 'error');
  }
}

async function handleExecuteStepUp(event) {
  event.preventDefault();
  const email = document.getElementById('step-up-email').value.trim();
  const code = document.getElementById('step-up-code').value.trim();

  if (!code) {
    showToast('Please enter the 6-digit Step-Up code.', 'error');
    return;
  }

  const res = await apiCall('/api/security/step-up/verify', 'POST', { email, code });
  if (res.status === 'success') {
    showToast('Step-Up verification passed! Wire transfer of $10,000 executed.', 'success');
    closeStepUpModal();
  } else {
    showToast(res.message || 'Step-Up verification failed.', 'error');
  }
}

// ==========================================================================
// 9. DASHBOARD INITIALIZATION & AUDIT TRAIL
// ==========================================================================

async function initDashboard() {
  if (!currentUser) return;

  document.getElementById('dash-user-name').innerText = currentUser.name || 'Vault Member';
  document.getElementById('dash-user-email').innerText = currentUser.email;
  document.getElementById('profile-name-input').value = currentUser.name || '';
  document.getElementById('profile-email-input').value = currentUser.email;

  await fetchSecurityAlerts(currentUser.id);
  await fetchLoginHistory();
}

async function fetchSecurityAlerts(userId) {
  const container = document.getElementById('alerts-container');
  if (!container) return;

  const res = await apiCall(`/api/entry/alerts/${userId}`);
  if (res.status === 'success' && res.data) {
    const alerts = res.data;
    if (alerts.length === 0) {
      container.innerHTML = `
        <div class="flex items-center gap-3 p-3.5 rounded bg-gray-800 border border-gray-700 text-gray-200 text-xs">
          <i class="fas fa-shield-check text-lg text-blue-400"></i>
          <div>
            <p class="font-bold text-white">Hardware & Account Integrity Nominal</p>
            <p class="text-[11px] text-gray-400 mt-0.5">All connected hardware fingerprints and login attempts pass Dorito Vault security policies.</p>
          </div>
        </div>
      `;
    } else {
      container.innerHTML = alerts.map(a => {
        if (a.type === 'untrusted_device') {
          return `
            <div class="flex items-start gap-3 p-3.5 rounded bg-yellow-900/30 border border-yellow-700/40 text-yellow-300 text-xs">
              <i class="fas fa-triangle-exclamation text-yellow-400 text-base mt-0.5"></i>
              <div>
                <p class="font-bold text-white">Untrusted Hardware Fingerprint Detected</p>
                <p class="text-xs text-yellow-200/80 mt-1">Fingerprint: <code class="font-mono-code bg-black/40 px-2 py-0.5 rounded text-yellow-300">${a.fingerprint}</code></p>
                <p class="text-[11px] text-yellow-200/60 mt-0.5">First active: ${new Date(a.first_seen_at).toLocaleString()}</p>
              </div>
            </div>
          `;
        } else if (a.type === 'repeated_failed_logins') {
          return `
            <div class="flex items-start gap-3 p-3.5 rounded bg-red-900/30 border border-red-700/40 text-red-300 text-xs">
              <i class="fas fa-shield-exclamation text-red-400 text-base mt-0.5"></i>
              <div>
                <p class="font-bold text-white">Security Alert: ${a.count} Repeated Failed Login Attempts</p>
                <p class="text-xs text-red-200/80 mt-1">Multiple authentication failures detected in the last ${a.window_minutes} minutes.</p>
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

  const res = await apiCall('/api/sessions/login-history?limit=50');
  if (res.status === 'success' && res.data) {
    const logs = res.data;
    if (logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="py-6 text-center text-gray-500 text-xs font-mono-code">No cryptographic login events recorded yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = logs.map(log => {
      let badgeClass = 'bg-blue-500/20 text-blue-400 border border-blue-500/30';
      let icon = 'fa-fingerprint';
      if (log.method === 'otp') { badgeClass = 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'; icon = 'fa-envelope-open-text'; }
      if (log.method === 'qr') { badgeClass = 'bg-red-500/20 text-red-400 border border-red-500/30'; icon = 'fa-qrcode'; }

      const statusBadge = log.success
        ? `<span class="px-2 py-0.5 text-xs rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-bold font-mono-code flex items-center gap-1 w-fit"><i class="fas fa-circle-check text-[10px]"></i> Success</span>`
        : `<span class="px-2 py-0.5 text-xs rounded bg-red-500/20 text-red-400 border border-red-500/30 font-bold font-mono-code flex items-center gap-1 w-fit"><i class="fas fa-circle-xmark text-[10px]"></i> Failed</span>`;

      return `
        <tr class="border-b border-gray-800 hover:bg-gray-800/40 transition-all">
          <td class="py-3 px-3">
            <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-bold font-mono-code ${badgeClass}">
              <i class="fas ${icon}"></i> ${log.method.toUpperCase()}
            </span>
          </td>
          <td class="py-3 px-3">${statusBadge}</td>
          <td class="py-3 px-3 text-xs font-mono-code text-gray-300">${log.ip_address || '127.0.0.1'}</td>
          <td class="py-3 px-3 text-xs font-mono-code text-gray-400 truncate max-w-xs">${log.device_info || '—'}</td>
          <td class="py-3 px-3 text-xs font-mono-code text-gray-400">${new Date(log.created_at).toLocaleString()}</td>
        </tr>
      `;
    }).join('');
  }
}

async function handleUpdateProfile(event) {
  event.preventDefault();
  const name = document.getElementById('profile-name-input').value.trim();

  const res = await apiCall('/api/sessions/profile/update', 'POST', { name });
  if (res.status === 'success') {
    showToast('Profile updated successfully!', 'success');
    currentUser.name = name;
    document.getElementById('dash-user-name').innerText = name || 'Vault Member';
    document.getElementById('nav-user-name').innerText = name || currentUser.email;
  } else {
    showToast(res.message || 'Failed to update profile.', 'error');
  }
}

async function handleDashboardRegisterPasskey() {
  if (!currentUser || !currentUser.email) return;
  await registerWebAuthn(currentUser.email);
}

async function handleLogout() {
  const res = await apiCall('/api/sessions/logout', 'POST');
  if (res.status === 'success') {
    showToast('Logged out successfully.', 'info');
    setTimeout(() => { window.location.href = '/'; }, 400);
  } else {
    showToast(res.message || 'Logout failed.', 'error');
  }
}

async function handleLogoutAll() {
  if (!confirm('Are you sure you want to revoke all active sessions across all devices?')) return;

  const res = await apiCall('/api/sessions/logout-all', 'POST');
  if (res.status === 'success') {
    showToast('Revoked all active sessions across all devices.', 'info');
    setTimeout(() => { window.location.href = '/'; }, 800);
  } else {
    showToast(res.message || 'Failed to revoke sessions.', 'error');
  }
}

function switchTab(tabName) {
  const tabLogin = document.getElementById('tab-login-btn');
  const tabReg = document.getElementById('tab-reg-btn');
  const formLogin = document.getElementById('form-login');
  const formReg = document.getElementById('form-reg');

  if (!formLogin || !formReg) return;

  if (tabName === 'login') {
    tabLogin.classList.add('border-blue-500', 'text-blue-400');
    tabLogin.classList.remove('border-transparent', 'text-gray-400');
    tabReg.classList.remove('border-blue-500', 'text-blue-400');
    tabReg.classList.add('border-transparent', 'text-gray-400');
    formLogin.classList.remove('hidden');
    formReg.classList.add('hidden');
  } else {
    tabReg.classList.add('border-blue-500', 'text-blue-400');
    tabReg.classList.remove('border-transparent', 'text-gray-400');
    tabLogin.classList.remove('border-blue-500', 'text-blue-400');
    tabLogin.classList.add('border-transparent', 'text-gray-400');
    formReg.classList.remove('hidden');
    formLogin.classList.add('hidden');
  }
}

// ==========================================================================
// 10. BACKGROUND CANVAS ANIMATION (BOOTSTRAP BLUE PARTICLES)
// ==========================================================================

function initParticleCanvas() {
  const canvas = document.getElementById('bg-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  let width = canvas.width = window.innerWidth;
  let height = canvas.height = window.innerHeight;

  window.addEventListener('resize', () => {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  });

  const particles = [];
  const particleCount = 40;

  for (let i = 0; i < particleCount; i++) {
    particles.push({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      radius: Math.random() * 1.8 + 0.8,
      alpha: Math.random() * 0.35 + 0.15
    });
  }

  function draw() {
    ctx.clearRect(0, 0, width, height);

    for (let i = 0; i < particleCount; i++) {
      const p = particles[i];
      p.x += p.vx;
      p.y += p.vy;

      if (p.x < 0 || p.x > width) p.vx *= -1;
      if (p.y < 0 || p.y > height) p.vy *= -1;

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(13, 110, 253, ${p.alpha})`;
      ctx.fill();

      for (let j = i + 1; j < particleCount; j++) {
        const p2 = particles[j];
        const dx = p.x - p2.x;
        const dy = p.y - p2.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < 130) {
          ctx.beginPath();
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.strokeStyle = `rgba(13, 110, 253, ${0.1 * (1 - dist / 130)})`;
          ctx.lineWidth = 0.7;
          ctx.stroke();
        }
      }
    }

    requestAnimationFrame(draw);
  }

  draw();
}
