// ==========================================================================
// CENTRALIZED REACTIVE FINANCIAL LEDGER (Dynamic Balances, Gold & Escrow)
// ==========================================================================
const VaultState = {
  getBankBalance() {
    const val = localStorage.getItem('vault_bank_balance');
    return val !== null ? parseFloat(val) : 248590.00;
  },
  setBankBalance(val) {
    const clean = Math.max(0, val);
    localStorage.setItem('vault_bank_balance', clean.toFixed(2));
    this.renderBankBalance();
  },
  modifyBankBalance(delta) {
    const current = this.getBankBalance();
    const updated = Math.max(0, current + delta);
    this.setBankBalance(updated);
    return updated;
  },
  renderBankBalance() {
    const el = document.getElementById('main-bank-balance');
    if (!el) return;
    const val = this.getBankBalance();
    el.innerText = `₹${val.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    el.classList.add('text-emerald-400');
    setTimeout(() => el.classList.remove('text-emerald-400'), 500);
  },

  getGoldGrams() {
    const val = localStorage.getItem('vault_gold_grams');
    return val !== null ? parseFloat(val) : 3.42;
  },
  addGold(grams) {
    const current = this.getGoldGrams();
    const updated = +(current + grams).toFixed(3);
    localStorage.setItem('vault_gold_grams', updated);
    this.renderGold();
    return updated;
  },
  renderGold() {
    const grams = this.getGoldGrams();
    const gramsEl = document.getElementById('gold-grams-val');
    const valEl = document.getElementById('gold-market-val');
    if (gramsEl) {
      gramsEl.innerText = `${grams}g`;
      gramsEl.classList.add('text-emerald-300');
      setTimeout(() => gramsEl.classList.remove('text-emerald-300'), 500);
    }
    if (valEl) valEl.innerText = `₹${Math.round(grams * 7200).toLocaleString('en-IN')}`;
  },

  getEscrowLocked() {
    const val = localStorage.getItem('vault_escrow_locked');
    return val !== null ? parseFloat(val) : 0;
  },
  addEscrow(amount) {
    const total = this.getEscrowLocked() + amount;
    localStorage.setItem('vault_escrow_locked', total);
    this.renderEscrow();
    return total;
  },
  renderEscrow() {
    const locked = this.getEscrowLocked();
    const el = document.getElementById('escrow-locked-val');
    if (el) {
      el.innerText = `Locked: ₹${locked.toLocaleString('en-IN')}`;
      if (locked > 0) {
        el.className = 'text-[10px] font-mono-code text-emerald-300 bg-emerald-950/50 px-2 py-0.5 rounded border border-emerald-500/40 font-bold';
      }
    }
  },

  getCreditAvailable() {
    const val = localStorage.getItem('vault_credit_avail');
    return val !== null ? parseInt(val) : 50000;
  },
  setCreditAvailable(val) {
    localStorage.setItem('vault_credit_avail', val);
    const limitEl = document.getElementById('credit-avail-val');
    if (limitEl) limitEl.innerText = `₹${val.toLocaleString('en-IN')}`;
  },

  getCreditScore() {
    const val = localStorage.getItem('vault_credit_score');
    return val !== null ? parseInt(val) : 785;
  },
  setCreditScore(val) {
    localStorage.setItem('vault_credit_score', val);
    const scoreEl = document.getElementById('credit-score-val');
    if (scoreEl) scoreEl.innerText = val;
  }
};

window.VaultState = VaultState;

// --- Initialize FinTech Engine ---
document.addEventListener('DOMContentLoaded', () => {
  VaultState.renderBankBalance();
  VaultState.renderGold();
  VaultState.renderEscrow();
  loadCreditSummary();
  loadGoldSummary();
});

// --- 1. UPI 2.0 Passkey Payments & Deep Links ---
async function handleUPIPayment(e) {
  if (e) e.preventDefault();
  
  const vpa = document.getElementById('upi-vpa-input')?.value || 'merchant@okicici';
  const name = document.getElementById('upi-name-input')?.value || 'Starbucks India';
  const amount = parseInt(document.getElementById('upi-amount-input')?.value || '450');
  const appUsed = document.getElementById('upi-app-select')?.value || 'Google Pay';

  const btn = document.getElementById('btn-upi-pay');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-fingerprint animate-pulse mr-1"></i> Pre-Authorizing Passkey...';
  }

  try {
    const res = await fetch('/api/fintech/upi/pay', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        vpa: vpa,
        merchant_name: name,
        amount: amount,
        app_used: appUsed,
        biometric_verified: true
      })
    });
    
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'UPI payment pre-authorization failed');

    // Dynamic Balance Deductions
    const totalDeducted = amount + (data.roundup_invested || 0);
    VaultState.modifyBankBalance(-totalDeducted);

    if (data.roundup_invested > 0) {
      const addedGrams = +(data.roundup_invested / 7200).toFixed(3);
      VaultState.addGold(addedGrams > 0 ? addedGrams : 0.007);
    }

    // Display Payment Modal & Render Dynamic QR Code
    const modal = document.getElementById('upi-receipt-modal');
    if (modal) {
      document.getElementById('upi-receipt-amount').innerText = `₹${totalDeducted}`;
      document.getElementById('upi-receipt-app').innerText = appUsed;
      document.getElementById('upi-receipt-vpa').innerText = vpa;
      document.getElementById('upi-receipt-hash').innerText = data.tx_hash;
      document.getElementById('upi-deeplink-btn').href = data.upi_deeplink;

      // Render Dynamic UPI QR Code
      const qrBox = document.getElementById('upi-qr-container');
      if (qrBox) {
        qrBox.innerHTML = '';
        new QRCode(qrBox, {
          text: data.upi_deeplink,
          width: 140,
          height: 140,
          colorDark: '#0d0e12',
          colorLight: '#ffffff'
        });
      }
      modal.classList.remove('hidden');
    }
    
    showToast(`Passkey Authorized! ₹${amount} sent to ${name} (Balance Updated)`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-qrcode mr-1.5"></i> Pre-Authorize & Pay via UPI';
    }
  }
}

function closeUPIModal() {
  document.getElementById('upi-receipt-modal')?.classList.add('hidden');
}

// --- 2. Instant Micro-Lending & Credit Score ---
async function loadCreditSummary() {
  try {
    const res = await fetch('/api/fintech/credit/summary');
    if (!res.ok) return;
    const data = await res.json();

    const score = VaultState.getCreditScore();
    const avail = VaultState.getCreditAvailable();

    const scoreEl = document.getElementById('credit-score-val');
    if (scoreEl) scoreEl.innerText = score;
    
    const limitEl = document.getElementById('credit-avail-val');
    if (limitEl) limitEl.innerText = `₹${avail.toLocaleString('en-IN')}`;
  } catch (err) {
    console.error('Credit summary error:', err);
  }
}

async function handleApplyLoan(amount, months) {
  try {
    const res = await fetch('/api/fintech/credit/apply-loan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ loan_amount: amount, tenure_months: months })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Loan application failed');

    // Dynamically add disbursed loan to main bank balance!
    VaultState.modifyBankBalance(+amount);

    // Update remaining credit line & boost trust score
    const currentAvail = VaultState.getCreditAvailable();
    const newAvail = Math.max(0, currentAvail - amount);
    VaultState.setCreditAvailable(newAvail);

    const newScore = Math.min(850, VaultState.getCreditScore() + 5);
    VaultState.setCreditScore(newScore);

    showToast(`Instant ₹${amount.toLocaleString('en-IN')} Disbursed to Bank Balance! Trust Score +5`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// --- 3. 24K Digital Gold & Spare-Change Round-Up ---
async function loadGoldSummary() {
  VaultState.renderGold();
}

async function handleToggleGoldRoundup() {
  try {
    const res = await fetch('/api/fintech/gold/roundup-toggle', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Toggle failed');

    showToast(data.message, 'info');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// --- 4. Biometric Co-Signed Escrow Commerce ---
async function handleCreateEscrow(e) {
  if (e) e.preventDefault();
  
  const title = document.getElementById('escrow-title-input')?.value || 'Used Laptop Purchase';
  const seller = document.getElementById('escrow-seller-input')?.value || 'seller@store.com';
  const amount = parseInt(document.getElementById('escrow-amount-input')?.value || '12000');

  try {
    const res = await fetch('/api/fintech/escrow/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ item_title: title, seller_email: seller, amount: amount })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Escrow creation failed');

    // Deduct from main balance and lock in escrow
    VaultState.modifyBankBalance(-amount);
    VaultState.addEscrow(amount);

    showToast(`Escrow Locked: ₹${amount.toLocaleString('en-IN')} for '${title}' (Balance Deducted)`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}


// --- 5. Merchant Digital Invoice Generator ---
async function handleCreateInvoice(e) {
  if (e) e.preventDefault();
  
  const client = document.getElementById('inv-client-input')?.value || 'Rahul Sharma';
  const email = document.getElementById('inv-email-input')?.value || 'rahul@client.com';
  const amount = parseInt(document.getElementById('inv-amount-input')?.value || '8500');
  const desc = document.getElementById('inv-desc-input')?.value || 'Web Development & Security Services';

  try {
    const res = await fetch('/api/fintech/merchant/invoice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_name: client, client_email: email, amount: amount, item_description: desc })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Invoice creation failed');

    showToast(`Invoice generated! Payment Link: ${data.payment_link}`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// --- 6. Regional Multi-Language (Hindi/English) & Voice Assistant ---
function toggleLanguage(lang) {
  currentLanguage = lang;
  document.querySelectorAll('[data-lang-en]').forEach(el => {
    if (lang === 'hi' && el.dataset.langHi) {
      el.innerText = el.dataset.langHi;
    } else {
      el.innerText = el.dataset.langEn;
    }
  });
  showToast(lang === 'hi' ? 'भाषा बदलकर हिन्दी की गई' : 'Language switched to English', 'info');
}

let activeRecognition = null;

function closeVoiceModal() {
  const modal = document.getElementById('voice-assistant-modal');
  if (modal) modal.classList.add('hidden');
  if (activeRecognition) {
    try { activeRecognition.stop(); } catch (e) {}
    activeRecognition = null;
  }
}

function speakFeedback(text) {
  if ('speechSynthesis' in window) {
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = currentLanguage === 'hi' ? 'hi-IN' : 'en-US';
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn('TTS error:', e);
    }
  }
}

function highlightCard(cardId) {
  const card = document.getElementById(cardId);
  if (!card) return;
  card.scrollIntoView({ behavior: 'smooth', block: 'center' });
  card.classList.add('ring-2', 'ring-emerald-400', 'shadow-[0_0_30px_rgba(16,185,129,0.4)]', 'scale-[1.02]');
  setTimeout(() => {
    card.classList.remove('ring-2', 'ring-emerald-400', 'shadow-[0_0_30px_rgba(16,185,129,0.4)]', 'scale-[1.02]');
  }, 2500);
}

function executeVoiceAction(commandText) {
  const text = (commandText || '').trim();
  const lower = text.toLowerCase();
  const transcriptEl = document.getElementById('voice-modal-transcript');
  const statusEl = document.getElementById('voice-modal-status');
  
  if (transcriptEl) transcriptEl.innerText = `Heard: "${text}"`;
  if (statusEl) statusEl.innerText = 'Processing command...';

  // Check language triggers first (ultra broad match)
  if (lower.includes('hindi') || lower.includes('hind') || text.includes('हिन्दी') || text.includes('हिंदी')) {
    if (statusEl) statusEl.innerText = 'Switching to हिन्दी...';
    speakFeedback('भाषा बदलकर हिन्दी की गई');
    toggleLanguage('hi');
    setTimeout(() => closeVoiceModal(), 800);
    return;
  }
  
  if (lower.includes('english') || lower.includes('angrezi') || text.includes('अंग्रेजी') || lower === 'en') {
    if (statusEl) statusEl.innerText = 'Switching to English...';
    speakFeedback('Language switched to English');
    toggleLanguage('en');
    setTimeout(() => closeVoiceModal(), 800);
    return;
  }

  if (lower.includes('gold') || lower.includes('sona') || text.includes('सोना') || lower.includes('24k')) {
    if (statusEl) statusEl.innerText = 'Opening 24K Gold Vault...';
    speakFeedback('Opening 24 karat digital gold vault');
    loadGoldSummary();
    setTimeout(() => {
      closeVoiceModal();
      highlightCard('card-digital-gold');
    }, 800);
    return;
  }

  if (lower.includes('credit') || lower.includes('loan') || lower.includes('score') || text.includes('ऋण') || lower.includes('limit')) {
    if (statusEl) statusEl.innerText = 'Fetching Credit Score...';
    speakFeedback('Fetching vault trust credit rating');
    loadCreditSummary();
    setTimeout(() => {
      closeVoiceModal();
      highlightCard('card-credit-line');
    }, 800);
    return;
  }

  if (lower.includes('pay') || lower.includes('upi') || text.includes('पे') || text.includes('भुगतान') || lower.includes('starbucks')) {
    if (statusEl) statusEl.innerText = 'Opening UPI 2.0 Drawer...';
    speakFeedback('Opening UPI payment drawer');
    setTimeout(() => {
      closeVoiceModal();
      highlightCard('card-upi-pay');
      document.getElementById('upi-amount-input')?.focus();
    }, 800);
    return;
  }

  if (lower.includes('escrow') || text.includes('एस्क्रो') || lower.includes('deal') || lower.includes('contract')) {
    if (statusEl) statusEl.innerText = 'Opening Escrow Commerce...';
    speakFeedback('Navigating to biometric escrow commerce');
    setTimeout(() => {
      closeVoiceModal();
      highlightCard('card-escrow-commerce');
    }, 800);
    return;
  }

  if (statusEl) statusEl.innerText = `Heard "${text}". Try clicking a chip:`;
}

function simulateVoiceCommand(cmd) {
  executeVoiceAction(cmd);
}

function startVoiceAssistant() {
  const modal = document.getElementById('voice-assistant-modal');
  const statusEl = document.getElementById('voice-modal-status');
  const transcriptEl = document.getElementById('voice-modal-transcript');
  
  if (modal) modal.classList.remove('hidden');
  if (statusEl) statusEl.innerText = '🎙️ Listening... Speak now!';
  if (transcriptEl) transcriptEl.innerText = '"Say Hindi, Check Gold, Credit Score, Pay UPI..."';

  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    if (statusEl) statusEl.innerText = 'Microphone API unavailable in this browser';
    if (transcriptEl) transcriptEl.innerText = 'Please click one of the command chips below:';
    return;
  }
  
  try {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    
    // Indian English locale recognizes both English and Hindi terms with highest accuracy
    recognition.lang = currentLanguage === 'hi' ? 'hi-IN' : 'en-IN';
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.maxAlternatives = 3;

    activeRecognition = recognition;

    recognition.onstart = () => {
      if (statusEl) statusEl.innerText = '🎙️ Listening to microphone... Speak now!';
    };

    recognition.onresult = (event) => {
      let currentWords = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        currentWords += event.results[i][0].transcript;
      }

      if (transcriptEl && currentWords) {
        transcriptEl.innerText = `Heard: "${currentWords}"`;
      }

      // Check if keyword is found early in interim speech
      const lower = currentWords.toLowerCase();
      if (lower.includes('hindi') || lower.includes('gold') || lower.includes('credit') || lower.includes('pay') || lower.includes('escrow') || lower.includes('english')) {
        try { recognition.stop(); } catch (e) {}
        executeVoiceAction(currentWords);
        return;
      }

      if (event.results[event.results.length - 1].isFinal) {
        executeVoiceAction(currentWords);
      }
    };

    recognition.onerror = (err) => {
      console.warn('Speech Recognition error event:', err.error);
      if (err.error === 'no-speech') {
        if (statusEl) statusEl.innerText = 'No speech detected yet. Speak clearly into mic:';
      } else {
        if (statusEl) statusEl.innerText = 'Click any quick command chip below:';
      }
    };

    recognition.onend = () => {
      activeRecognition = null;
    };

    recognition.start();
  } catch (err) {
    console.error('Error starting recognition:', err);
    if (statusEl) statusEl.innerText = 'Click a quick command below:';
  }
}

// Window global bindings
window.startVoiceAssistant = startVoiceAssistant;
window.closeVoiceModal = closeVoiceModal;
window.simulateVoiceCommand = simulateVoiceCommand;
window.toggleLanguage = toggleLanguage;
window.handleUPIPayment = handleUPIPayment;
window.handleApplyLoan = handleApplyLoan;
window.handleToggleGoldRoundup = handleToggleGoldRoundup;
window.handleCreateEscrow = handleCreateEscrow;
window.closeUPIModal = closeUPIModal;







