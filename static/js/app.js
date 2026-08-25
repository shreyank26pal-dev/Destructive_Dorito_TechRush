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
let pendingRegEmail = null;

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
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  const lang = navigator.language || "";

  const options = {
    method,
    credentials: 'include', // Ensure mobile browsers (iOS Safari / Android Chrome) attach session cookies
    headers: { 
      'Content-Type': 'application/json',
      'X-Client-Timezone': timezone,
      'X-Client-Language': lang
    },
  };
  if (data) {
    options.body = JSON.stringify(data);
  }

  try {
    const response = await fetch(url, options);
    const text = await response.text();
    let resData;
    try {
      resData = JSON.parse(text);
    } catch (parseErr) {
      console.error(`[Non-JSON Response] (${url}):`, text);
      return { 
        status: 'error', 
        message: response.ok ? text : `Server Error (${response.status}): ${text.substring(0, 100)}` 
      };
    }
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

    const adminBtn = document.getElementById('nav-admin-btn');
    if (adminBtn) {
      if (currentUser.role === 'admin') {
        adminBtn.classList.remove('hidden');
      } else {
        adminBtn.classList.add('hidden');
      }
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
// 5. STRICT 3-STEP SEQUENTIAL REGISTRATION WORKFLOW
// ==========================================================================

// STEP 1: Enter Name & Email -> Dispatch Verification Code
async function handleSendVerificationStep(event) {
  if (event) event.preventDefault();
  const email = document.getElementById('reg-email').value.trim();
  const name = document.getElementById('reg-name').value.trim() || email.split('@')[0];

  if (!email || !email.includes('@') || !email.includes('.')) {
    showToast('Please enter a valid email address with @ (e.g. name@gmail.com).', 'error');
    return;
  }

  const btn = document.getElementById('btn-send-verification-code');

  btn.disabled = true;
  btn.innerText = 'Sending Code...';

  // Call send-verification
  const res = await apiCall('/api/security/email/send-verification', 'POST', { email });
  
  if (res.status === 'success') {
    pendingRegEmail = email;
    showToast(`Verification code sent to ${email}. Please check your email inbox.`, 'success');
    
    // Hide Step 1, Show Step 2
    document.getElementById('reg-step-1').classList.add('hidden');
    const step2 = document.getElementById('reg-step-2');
    step2.classList.remove('hidden');
    const codeInput = document.getElementById('email-verify-code-input');
    if (codeInput) {
      codeInput.value = '';
      codeInput.focus();
    }
  } else {
    showToast(res.message || 'Failed to send verification email.', 'error');
  }

  btn.disabled = false;
  btn.innerText = 'Step 1: Send Verification Code to Email';
}


// STEP 2: Verify 6-Digit Email OTP Code
async function handleVerifyEmailStep(event) {
  if (event) event.preventDefault();
  const email = pendingRegEmail || document.getElementById('reg-email').value.trim();
  const code = document.getElementById('email-verify-code-input').value.trim();

  if (!email || !code) {
    showToast('Please enter the 6-digit verification code.', 'error');
    return;
  }

  const btn = document.getElementById('btn-submit-email-verify');
  btn.disabled = true;
  btn.innerText = 'Verifying Code...';

  const res = await apiCall('/api/security/email/verify', 'POST', { email, code });
  if (res.status === 'success') {
    showToast('Email verified successfully!', 'success');

    // Also register user device binding
    if (res.data && res.data.id) {
      await apiCall('/api/entry/check-device', 'POST', {
        user_id: res.data.id,
        fingerprint: deviceFingerprint
      });
    }

    // Hide Step 2, Show Step 3 (Passkey setup)
    document.getElementById('reg-step-2').classList.add('hidden');
    document.getElementById('reg-step-3').classList.remove('hidden');
  } else {
    showToast(res.message || 'Invalid or expired verification code.', 'error');
  }

  btn.disabled = false;
  btn.innerText = 'Verify Code & Continue';
}

// STEP 3: Setup WebAuthn Passkey
async function handlePasskeySetupStep(event) {
  if (event) event.preventDefault();
  const email = pendingRegEmail || document.getElementById('reg-email').value.trim();
  
  if (!email) {
    showToast('Email is required for passkey setup.', 'error');
    return;
  }

  await registerWebAuthn(email);
  finishRegistrationWorkflow();
}

function finishRegistrationWorkflow() {
  const email = pendingRegEmail || document.getElementById('reg-email').value.trim();
  showToast('Registration complete! Please sign in.', 'success');

  // Reset reg forms
  document.getElementById('reg-step-1').classList.remove('hidden');
  document.getElementById('reg-step-2').classList.add('hidden');
  document.getElementById('reg-step-3').classList.add('hidden');

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

// ==========================================================================
// 6. WEBAUTHN LOGIN FLOW
// ==========================================================================

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
      showToast(optionsRes.message || 'Biometric login failed.', 'error');
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

    // 2. Prompt user for biometric scan
    const assertion = await navigator.credentials.get({ publicKey: options });

    // 3. Format assertion payload
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

    // 4. Send to backend (/api/security/webauthn/login-verify)
    const verifyRes = await apiCall('/api/security/webauthn/login-verify', 'POST', {
      email,
      credential: credentialJSON,
      device_fingerprint: deviceFingerprint
    });

    if (verifyRes.status === 'success') {
      showToast('Passkey login successful!', 'success');
      setTimeout(() => { window.location.href = '/dashboard'; }, 600);
    } else {
      showToast(verifyRes.message || 'Biometric verification failed.', 'error');
    }
  } catch (err) {
    console.error("WebAuthn Login Error:", err);
    showToast(err.message || 'Biometric login cancelled or unsupported.', 'error');
  }
}

// ==========================================================================
// 7. HASHED EMAIL OTP LOGIN FLOW
// ==========================================================================

async function handleSendOTP() {
  const email = document.getElementById('login-email').value.trim();
  if (!email || !email.includes('@') || !email.includes('.')) {
    showToast('Please enter a valid email address with @ (e.g. name@gmail.com).', 'error');
    return;
  }


  const btn = document.getElementById('btn-send-otp');
  btn.disabled = true;
  btn.innerText = 'Sending...';

  const res = await apiCall('/api/security/otp/send', 'POST', { email });
  if (res.status === 'success') {
    showToast(`Ephemeral OTP code emailed to ${email}. Please check your inbox.`, 'success');
    document.getElementById('otp-section').classList.remove('hidden');
    const otpInput = document.getElementById('otp-code');
    if (otpInput) {
      otpInput.value = '';
      otpInput.focus();
    }
  } else {
    showToast(res.message || 'Failed to send OTP code.', 'error');
  }

  btn.disabled = false;
  btn.innerText = 'Send Code';
}


async function handleVerifyOTP(event) {
  if (event) event.preventDefault();
  const email = document.getElementById('login-email').value.trim();
  const code = document.getElementById('otp-code').value.trim();

  if (!email || !code) {
    showToast('Email and 6-digit OTP code are required.', 'error');
    return;
  }

  const btn = document.getElementById('btn-verify-otp');
  btn.disabled = true;
  btn.innerText = 'Verifying...';

  const res = await apiCall('/api/security/otp/verify', 'POST', {
    email,
    code,
    device_fingerprint: deviceFingerprint
  });

  if (res.status === 'success') {
    showToast('OTP verification successful! Logging in...', 'success');
    setTimeout(() => { window.location.href = '/dashboard'; }, 600);
  } else {
    showToast(res.message || 'Invalid or expired OTP code.', 'error');
  }

  btn.disabled = false;
  btn.innerText = 'Verify & Login';
}

// ==========================================================================
// 8. QR CODE CROSS-DEVICE AUTHORIZATION ENGINE
// ==========================================================================

function toggleQrSection() {
  const section = document.getElementById('qr-section');
  if (!section) return;

  if (section.classList.contains('hidden')) {
    section.classList.remove('hidden');
    generateQrToken();
  } else {
    section.classList.add('hidden');
    if (qrPollingInterval) clearInterval(qrPollingInterval);
  }
}

async function generateQrToken() {
  const container = document.getElementById('qr-container');
  const statusText = document.getElementById('qr-status-text');
  if (!container) return;

  container.innerHTML = '<i class="fas fa-circle-notch fa-spin text-xl text-blue-500"></i>';
  if (statusText) statusText.innerText = 'Generating token...';

  const fp = typeof computeDeviceFingerprint === 'function' ? computeDeviceFingerprint() : (window.deviceFingerprint || 'default_fp');
  const res = await apiCall('/api/security/qr/generate', 'POST', { device_fingerprint: fp });
  if (res.status === 'success' && res.data) {
    const token = res.data.token;
    container.innerHTML = '';
    
    // Render QR Code canvas
    if (window.QRCode) {
      new QRCode(container, {
        text: token,
        width: 140,
        height: 140,
        colorDark: '#0d6efd',
        colorLight: '#ffffff',
        correctLevel: QRCode.CorrectLevel.H
      });
    } else {
      container.innerText = token;
    }

    // Always display plain text token below QR code for easy mobile approval
    const tokenTextEl = document.getElementById('qr-token-display') || document.createElement('div');
    tokenTextEl.id = 'qr-token-display';
    tokenTextEl.className = 'mt-2 p-2 rounded bg-gray-900 border border-gray-800 text-[11px] font-mono-code text-blue-400 break-all select-all';
    tokenTextEl.innerText = token;
    if (!document.getElementById('qr-token-display')) {
      container.parentNode.appendChild(tokenTextEl);
    }

    if (statusText) statusText.innerText = 'Awaiting mobile approval...';
    startQrPolling(token);
  } else {
    if (statusText) statusText.innerText = res.message || 'QR Token generation failed.';
  }
}

function startQrPolling(token) {
  if (qrPollingInterval) clearInterval(qrPollingInterval);

  qrPollingInterval = setInterval(async () => {
    const res = await apiCall(`/api/security/qr/status/${token}`);
    if (res.status === 'success' && res.data) {
      const qrStatus = res.data.status;
      const statusText = document.getElementById('qr-status-text');

      if (qrStatus === 'approved') {
        clearInterval(qrPollingInterval);
        if (statusText) statusText.innerText = '✅ Sign-in approved on mobile!';
        showToast('QR Sign-in approved on mobile device!', 'success');
        
        // Log in session
        if (res.data.user) {
          setTimeout(() => { window.location.href = '/dashboard'; }, 800);
        }
      } else if (qrStatus === 'expired') {
        clearInterval(qrPollingInterval);
        if (statusText) statusText.innerText = '❌ QR Token expired.';
      }
    }
  }, 2000);
}

function openQrApprovalModal() {
  const modal = document.getElementById('qr-approve-modal');
  if (modal) {
    modal.classList.add('active');
    modal.classList.remove('hidden');
    if (currentUser && currentUser.email) {
      const emailInput = document.getElementById('qr-approve-email');
      if (emailInput) emailInput.value = currentUser.email;
    }
    const tokenInput = document.getElementById('qr-token-input') || document.getElementById('qr-approve-token');
    if (tokenInput) {
      tokenInput.value = '';
      setTimeout(() => tokenInput.focus(), 100);
    }
  }
}

function closeQrApprovalModal() {
  const modal = document.getElementById('qr-approve-modal');
  if (modal) {
    modal.classList.remove('active');
    modal.classList.add('hidden');
  }
}

async function submitQrApproval() {
  const input = document.getElementById('qr-token-input') || document.getElementById('qr-approve-token');
  const emailInput = document.getElementById('qr-approve-email');
  const token = input ? input.value.trim() : '';
  const email = (currentUser && currentUser.email) ? currentUser.email : (emailInput ? emailInput.value.trim() : '');

  if (!token) {
    showToast('Please enter a QR Token.', 'warning');
    return;
  }

  if (!email) {
    showToast('You must be logged in to approve a QR sign-in.', 'error');
    return;
  }

  showToast('Approving QR sign-in...', 'info');
  const res = await apiCall('/api/security/qr/approve', 'POST', { 
    email: email, 
    token: token 
  });

  if (res.status === 'success') {
    showToast('✅ QR Sign-in approved successfully!', 'success');
    closeQrApprovalModal();
  } else {
    showToast(res.message || 'QR Approval failed.', 'error');
  }
}

async function handleApproveQRModal() {
  openQrApprovalModal();
}

// Expose handlers globally on window object for mobile touch events
window.openQrApprovalModal = openQrApprovalModal;
window.closeQrApprovalModal = closeQrApprovalModal;
window.submitQrApproval = submitQrApproval;
window.handleApproveQRModal = handleApproveQRModal;

// ==========================================================================
// 9. DASHBOARD LOGIC, WIRE TRANSFER STEP-UP & AUDIT LOGS
// ==========================================================================

async function initDashboard() {
  if (!currentUser) return;

  const nameEl = document.getElementById('dash-user-name');
  const emailEl = document.getElementById('dash-user-email');
  const profileNameInput = document.getElementById('profile-name-input');
  const profileEmailInput = document.getElementById('profile-email-input');

  if (nameEl) nameEl.innerText = currentUser.name || 'Vault Member';
  if (emailEl) emailEl.innerText = currentUser.email || '';
  if (profileNameInput) profileNameInput.value = currentUser.name || '';
  if (profileEmailInput) profileEmailInput.value = currentUser.email || '';

  await fetchSecurityAlerts(currentUser.id);
  await fetchLoginHistory();
  if (currentUser.email) {
    fetchMultiDeviceNudge(currentUser.email);
  }

  // Update Geolocation Firewall Status
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "unknown";
  const lang = navigator.language || "unknown";
  const isLocalIndian = !(["Shanghai", "London", "Tokyo", "Europe", "America", "GMT"].some(kw => tz.includes(kw)));
  
  const geoLoc = document.getElementById('geo-location-display');
  const geoDetails = document.getElementById('geo-details-display');
  const geoContainer = document.getElementById('geo-firewall-container');
  if (geoLoc && geoDetails) {
    geoDetails.innerText = `${tz} (${lang})`;
    if (isLocalIndian) {
      geoLoc.innerHTML = "Mumbai, India (Secure)";
      if (geoContainer) {
        geoContainer.className = "mt-3.5 p-2 rounded bg-emerald-950/20 border border-emerald-500/30 text-emerald-300 text-[10px] font-mono-code flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-4 max-w-[450px] inline-flex";
      }
    } else {
      geoLoc.innerHTML = "Foreign Origin (Banned)";
      if (geoContainer) {
        geoContainer.className = "mt-3.5 p-2 rounded bg-red-950/20 border border-red-500/30 text-red-300 text-[10px] font-mono-code flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-4 max-w-[450px] inline-flex";
      }
    }
  }
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
            <p class="text-xs text-gray-400 mt-0.5">Zero security alerts or untrusted device anomalies detected.</p>
          </div>
        </div>
      `;
      return;
    }

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

async function fetchLoginHistory() {
  const tbody = document.getElementById('history-tbody');
  if (!tbody) return;

  const res = await apiCall('/api/sessions/login-history');
  if (res.status === 'success' && res.data) {
    const history = res.data;
    if (history.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="py-4 text-center text-gray-500 text-xs font-mono-code">No audit records found.</td></tr>';
      return;
    }

    tbody.innerHTML = history.map(h => `
      <tr class="border-b border-gray-800/60 hover:bg-gray-800/40 text-xs font-mono-code transition-all">
        <td class="py-2.5 px-3 uppercase font-bold ${h.method === 'webauthn' ? 'text-blue-400' : 'text-emerald-400'}">
          <i class="fas ${h.method === 'webauthn' ? 'fa-fingerprint' : 'fa-envelope-open-text'} mr-1"></i> ${h.method}
        </td>
        <td class="py-2.5 px-3 font-semibold ${h.success ? 'text-emerald-400' : 'text-red-400'}">
          ${h.success ? '✓ SUCCESS' : '✗ FAILED'}
        </td>
        <td class="py-2.5 px-3 text-gray-300">📍 ${h.city || 'Local'}, ${h.country || 'India'}</td>
        <td class="py-2.5 px-3 text-gray-400">${h.device_info ? h.device_info.substring(0, 16) + '...' : 'n/a'}</td>
        <td class="py-2.5 px-3 text-gray-400">${new Date(h.created_at).toLocaleString()}</td>
      </tr>
    `).join('');
  }
}

async function triggerWireTransferStepUp() {
  if (!currentUser) return;

  const amountInput = document.getElementById('transfer-amount-input');
  const amount = amountInput ? parseFloat(amountInput.value) : 10000;
  if (isNaN(amount) || amount <= 0) {
    showToast('Invalid transfer amount.', 'error');
    return;
  }

  const recipient = "Global Reserve Vault #4810";
  const transaction = { action: "wire_transfer", amount: amount, recipient: recipient };

  // 1. Create Step-Up Challenge (/api/entry/step-up/challenge)
  showToast('Creating transaction-bound Step-Up challenge...', 'info');
  const challengeRes = await apiCall('/api/entry/step-up/challenge', 'POST', {
    user_id: currentUser.id,
    transaction: transaction
  });

  if (challengeRes.status !== 'success' || !challengeRes.data) {
    showToast(challengeRes.message || 'Failed to create Step-Up challenge.', 'error');
    return;
  }

  const challengeId = challengeRes.data.challenge_id;

  // 2. Request OTP Code to be sent to user email
  const otpRes = await apiCall('/api/security/otp/send', 'POST', { email: currentUser.email });
  if (otpRes.status !== 'success') {
    showToast('Failed to send Step-Up OTP code.', 'error');
    return;
  }

  showToast(`Step-Up OTP code sent to ${currentUser.email}!`, 'info');

  const code = prompt(`SECURE WIRE TRANSFER AUTHORIZATION\nTransfer: $${amount.toLocaleString()} to ${recipient}\n\nEnter the 6-digit OTP code sent to ${currentUser.email}:`);
  if (!code) {
    showToast('Wire transfer cancelled.', 'warning');
    return;
  }

  // 3. Verify Step-Up Code with bound challenge_id
  const verifyRes = await apiCall('/api/security/step-up/verify', 'POST', {
    email: currentUser.email,
    code: code.trim(),
    challenge_id: challengeId
  });

  if (verifyRes.status === 'success') {
    if (challengeRes.data.co_signer_approval_required) {
      showToast('Step-Up OTP verified. Awaiting Co-Signer approval (check their email)...', 'info');
      
      let polling = true;
      let count = 0;
      while (polling && count < 60) {
        await new Promise(r => setTimeout(r, 2000));
        const statusRes = await apiCall(`/api/security/co-signer/transaction-status/${challengeId}`);
        if (statusRes.status === 'success' && statusRes.data) {
          const d = statusRes.data;
          if (d.fully_cleared) {
            polling = false;
            showToast(`✅ WIRE TRANSFER FULLY AUTHORIZED! Co-signer approved the transfer of $${amount.toLocaleString()}.`, 'success');
          } else if (d.co_signer_status === 'denied') {
            polling = false;
            showToast('❌ WIRE TRANSFER REJECTED: Co-signer declined the transaction.', 'error');
          } else if (d.co_signer_status === 'expired') {
            polling = false;
            showToast('❌ WIRE TRANSFER EXPIRED: Co-signer approval request expired.', 'error');
          }
        }
        count++;
      }
      if (window.VaultState) window.VaultState.modifyBankBalance(-amount);
      showToast(`WIRE TRANSFER AUTHORIZED! ₹${amount.toLocaleString('en-IN')} transferred (Balance Updated).`, 'success');
    }
  } else {
    showToast(verifyRes.message || 'Step-Up verification failed. Wire transfer rejected.', 'error');
  }

}

async function handleCoSignerInvite(event) {
  event.preventDefault();
  if (!currentUser) return;
  const email = document.getElementById('cosigner-email-input').value.trim();
  const label = document.getElementById('cosigner-label-input').value.trim();

  if (!email || !label) {
    showToast('Please enter both email and label.', 'error');
    return;
  }

  showToast('Sending co-signer invitation...', 'info');
  const res = await apiCall('/api/security/co-signer/invite', 'POST', {
    primary_user_id: currentUser.id,
    notify_email: email,
    label: label
  });

  if (res.status === 'success') {
    showToast('Co-signer invitation sent!', 'success');
    document.getElementById('cosigner-email-input').value = '';
    document.getElementById('cosigner-label-input').value = '';
  } else {
    showToast(res.message || 'Failed to invite co-signer.', 'error');
  }
}
window.handleCoSignerInvite = handleCoSignerInvite;

async function handleDashboardRegisterPasskey() {
  if (!currentUser || !currentUser.email) return;
  await registerWebAuthn(currentUser.email);
}

async function handleUpdateProfile(event) {
  event.preventDefault();
  const name = document.getElementById('profile-name-input').value.trim();
  if (!name) return;

  const res = await apiCall('/api/sessions/profile/update', 'POST', { name });
  if (res.status === 'success') {
    showToast('Profile updated successfully!', 'success');
    currentUser.name = name;
    initDashboard();
  } else {
    showToast(res.message || 'Failed to update profile.', 'error');
  }
}

async function handleLogout() {
  const res = await apiCall('/api/sessions/logout', 'POST');
  if (res.status === 'success') {
    showToast('Logged out of Dorito Vault session.', 'info');
    setTimeout(() => { window.location.href = '/'; }, 600);
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
// 10. RECOVERY CODES & MULTI-DEVICE NUDGE
// ==========================================================================

function toggleRecoverySection() {
  const section = document.getElementById('recovery-section');
  if (section) section.classList.toggle('hidden');
}

async function handleVerifyRecoveryCode(event) {
  if (event) event.preventDefault();
  const email = document.getElementById('login-email').value.trim();
  const code = document.getElementById('recovery-code-input').value.trim();

  if (!email || !code) {
    showToast('Please enter your account email and emergency recovery code.', 'error');
    return;
  }

  showToast('Verifying single-use emergency recovery code...', 'info');

  const res = await apiCall('/api/security/recovery-codes/verify', 'POST', {
    email,
    code,
    device_fingerprint: deviceFingerprint
  });

  if (res.status === 'success') {
    showToast('Authenticated via emergency recovery code!', 'success');
    setTimeout(() => { window.location.href = '/dashboard'; }, 800);
  } else {
    showToast(res.message || 'Invalid or already used recovery code.', 'error');
  }
}

async function handleGenerateRecoveryCodes() {
  if (!currentUser || !currentUser.email) {
    showToast('Please sign in first.', 'error');
    return;
  }

  if (!confirm('Generate new emergency recovery codes? Any previous un-used recovery codes will be invalidated.')) return;

  const res = await apiCall('/api/security/recovery-codes/generate', 'POST', { email: currentUser.email });
  if (res.status === 'success' && res.data && res.data.recovery_codes) {
    showToast('Generated 8 emergency recovery codes! Store them safely.', 'success');
    const displayBox = document.getElementById('recovery-codes-display');
    const grid = document.getElementById('recovery-codes-grid');
    if (displayBox && grid) {
      grid.innerHTML = res.data.recovery_codes.map(c => `
        <div class="p-1.5 rounded bg-black/50 border border-purple-500/20 text-center font-mono-code">${c}</div>
      `).join('');
      displayBox.classList.remove('hidden');
    }
  } else {
    showToast(res.message || 'Failed to generate recovery codes.', 'error');
  }
}

async function fetchMultiDeviceNudge(email) {
  const badge = document.getElementById('nudge-badge');
  const messageEl = document.getElementById('nudge-message');
  if (!badge || !messageEl) return;

  const res = await apiCall(`/api/security/devices/nudge/${email}`);
  if (res.status === 'success' && res.data) {
    const d = res.data;
    if (d.nudge_recommended) {
      badge.className = 'px-2 py-0.5 rounded text-[10px] font-bold bg-yellow-500/20 text-yellow-300 border border-yellow-500/30';
      badge.innerText = '⚠️ Action Recommended';
    } else {
      badge.className = 'px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30';
      badge.innerText = '🟢 Healthy Setup';
    }
    messageEl.innerText = d.message;
  }
}

// ==========================================================================
// 11. BACKGROUND CANVAS ANIMATION (BOOTSTRAP BLUE PARTICLES)
// ==========================================================================

function initParticleCanvas() {
  const canvas = document.getElementById('bg-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  let width = canvas.width = window.innerWidth;
  let height = canvas.height = window.innerHeight;

  let mouseX = width / 2;
  let mouseY = height / 2;
  let targetMouseX = width / 2;
  let targetMouseY = height / 2;

  window.addEventListener('resize', () => {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  });

  window.addEventListener('mousemove', (e) => {
    targetMouseX = e.clientX;
    targetMouseY = e.clientY;
  });

  function draw() {
    ctx.clearRect(0, 0, width, height);

    const isDark = document.documentElement.classList.contains('dark');
    const baseColor = isDark ? "16, 185, 129" : "200, 85, 43"; // Green vs Terracotta

    // Smooth mouse coordinates interpolation
    mouseX += (targetMouseX - mouseX) * 0.08;
    mouseY += (targetMouseY - mouseY) * 0.08;

    // Horizon line height
    const horizon = height * 0.45;
    const vanishingX = width / 2;

    ctx.lineWidth = 1.0;

    // 1. Draw glowing background grid spotlight at cursor position (increased brightness)
    const gradient = ctx.createRadialGradient(mouseX, mouseY, 0, mouseX, mouseY, 300);
    gradient.addColorStop(0, `rgba(${baseColor}, 0.28)`);
    gradient.addColorStop(0.5, `rgba(${baseColor}, 0.08)`);
    gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);

    // 2. Draw Layer 1: Deep Background Grid (Slower movement, smaller scale)
    ctx.lineWidth = 0.8;
    const spacing1 = 90;
    const offsetX1 = (mouseX - width / 2) * -0.02;
    const offsetY1 = (mouseY - height / 2) * -0.02;

    ctx.strokeStyle = `rgba(${baseColor}, 0.06)`;
    // Vertical lines
    for (let x = offsetX1 % spacing1; x < width; x += spacing1) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    // Horizontal lines
    for (let y = offsetY1 % spacing1; y < height; y += spacing1) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    // 3. Draw Layer 2: Foreground Interactive Grid (Faster movement, larger scale)
    ctx.lineWidth = 1.2;
    const spacing2 = 60;
    const offsetX2 = (mouseX - width / 2) * -0.05;
    const offsetY2 = (mouseY - height / 2) * -0.05;

    // Vertical lines
    for (let x = offsetX2 % spacing2; x < width + spacing2; x += spacing2) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);

      // Distance-based fade
      const dist = Math.abs(mouseX - x);
      const alpha = Math.max(0.12, Math.min(0.5, 0.7 * (1 - dist / (width * 0.4))));
      ctx.strokeStyle = `rgba(${baseColor}, ${alpha})`;
      ctx.stroke();
    }

    // Horizontal lines
    for (let y = offsetY2 % spacing2; y < height + spacing2; y += spacing2) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);

      // Distance-based fade
      const distY = Math.abs(mouseY - y);
      const alpha = Math.max(0.12, Math.min(0.5, 0.6 * (1 - distY / (height * 0.3))));
      ctx.strokeStyle = `rgba(${baseColor}, ${alpha})`;
      ctx.stroke();
    }

    // 4. Highlight the hovered grid intersection (increased size and glow)
    ctx.beginPath();
    ctx.arc(mouseX, mouseY, 5, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(${baseColor}, 0.85)`;
    ctx.shadowBlur = 18;
    ctx.shadowColor = `rgb(${baseColor})`;
    ctx.fill();
    
    // Reset shadow values for next cycles
    ctx.shadowBlur = 0;

    requestAnimationFrame(draw);
  }

  draw();
}

// ==========================================================================
// 12. EYE-CATCHING CURSOR PARTICLE TRAIL (LUMINA STYLE)
// ==========================================================================

function initCursorTrail() {
  const isMobile = window.matchMedia("(max-width: 768px)").matches;
  if (isMobile) return; // Disable on mobile/touch screens to save performance

  window.addEventListener('mousemove', (e) => {
    // Throttle particle creation slightly to maintain high fps
    if (Math.random() > 0.35) return;

    const particle = document.createElement('div');
    particle.className = 'cursor-trail-dot';
    
    // Position at mouse coordinates
    particle.style.left = `${e.clientX}px`;
    particle.style.top = `${e.clientY}px`;
    
    // Slightly randomize dot sizes
    const scale = Math.random() * 0.6 + 0.4;
    particle.style.transform = `translate(-50%, -50%) scale(${scale})`;
    
    const duration = Math.random() * 400 + 400; // 400ms - 800ms
    particle.style.animation = `cursorTrailFade ${duration}ms cubic-bezier(0.1, 0.8, 0.3, 1) forwards`;

    document.body.appendChild(particle);

    setTimeout(() => {
      particle.remove();
    }, duration);
  });
}

// Automatically trigger on page load
document.addEventListener('DOMContentLoaded', () => {
  initThemeSwitcher();
  initCursorTrail();
});

// ==========================================================================
// 13. DYNAMIC THEME SWITCHER (LIGHT/DARK)
// ==========================================================================

function initThemeSwitcher() {
  const currentTheme = localStorage.getItem('theme') || 'light';
  if (currentTheme === 'dark') {
    document.documentElement.classList.add('dark');
    document.documentElement.setAttribute('data-bs-theme', 'dark');
  } else {
    document.documentElement.classList.remove('dark');
    document.documentElement.setAttribute('data-bs-theme', 'light');
  }
  updateThemeToggleBtnUI();
}

function toggleTheme() {
  const html = document.documentElement;
  if (html.classList.contains('dark')) {
    html.classList.remove('dark');
    html.setAttribute('data-bs-theme', 'light');
    localStorage.setItem('theme', 'light');
  } else {
    html.classList.add('dark');
    html.setAttribute('data-bs-theme', 'dark');
    localStorage.setItem('theme', 'dark');
  }
  updateThemeToggleBtnUI();
}

function updateThemeToggleBtnUI() {
  const btn = document.getElementById('theme-toggle-btn');
  if (!btn) return;
  const isDark = document.documentElement.classList.contains('dark');
  if (isDark) {
    btn.innerHTML = `<i class="fas fa-sun text-yellow-400"></i> <span class="hidden sm:inline">Light Mode</span>`;
  } else {
    btn.innerHTML = `<i class="fas fa-moon text-indigo-400"></i> <span class="hidden sm:inline">Dark Mode</span>`;
  }
}

// Expose theme switcher functions globally
window.toggleTheme = toggleTheme;
window.initThemeSwitcher = initThemeSwitcher;

