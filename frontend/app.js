const state = { token: localStorage.getItem('token') || '', user: null };
const $ = (id) => document.getElementById(id);

const toast = (message) => {
  $('toast').textContent = message;
  setTimeout(() => {
    if ($('toast').textContent === message) $('toast').textContent = '';
  }, 3000);
};

async function api(path, options = {}, expectJson = true) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;

  const response = await fetch(path, { ...options, headers });
  const payload = expectJson ? await response.json().catch(() => ({})) : null;
  if (!response.ok) throw new Error((payload && payload.detail) || `Request failed (${response.status})`);
  return payload;
}

function statusClass(status) {
  if (status === 'Approved' || status === 'resolved') return 'approved';
  if (status === 'Rejected') return 'rejected';
  return 'pending';
}

function renderList(id, items, mapper) {
  const root = $(id);
  root.innerHTML = items.length ? items.map(mapper).join('') : '<p class="muted">No records found.</p>';
}

function stars(count) {
  return '★'.repeat(count) + '☆'.repeat(5 - count);
}

async function loadPublicContent() {
  try {
    const [stats, partners, reviews, faqs] = await Promise.all([
      api('/api/public/stats'),
      api('/api/public/partners'),
      api('/api/public/reviews'),
      api('/api/public/faqs'),
    ]);

    $('publicStats').innerHTML = `
      <div class="metric"><b>${stats.total_applications}</b><span>Total Applications</span></div>
      <div class="metric"><b>${stats.approval_rate}%</b><span>Loan Success Rate</span></div>
      <div class="metric"><b>${stats.approved_applications}</b><span>Approved</span></div>
      <div class="metric"><b>₹${Number(stats.total_disbursed_amount).toLocaleString('en-IN')}</b><span>Total Disbursed</span></div>
    `;

    renderList('partnersList', partners, (p) => `<article class="tilt"><h3>${p.name}</h3><p class="muted">${p.category}</p></article>`);
    renderList('reviewsList', reviews, (r) => `<article class="tilt"><h3>${r.customer_name}</h3><p class="muted">${r.product}</p><p>${stars(r.rating)}</p><p>${r.text}</p></article>`);
    $('faqList').innerHTML = faqs.map((f) => `<details><summary>${f.question}</summary><p class="muted">${f.answer}</p></details>`).join('');
  } catch (error) {
    toast(error.message);
  }
}

async function refreshUser() {
  const loggedIn = Boolean(state.token);
  $('logoutBtn').classList.toggle('hidden', !loggedIn);
  $('authBox').classList.toggle('hidden', loggedIn);
  $('emiPanel').classList.toggle('hidden', !loggedIn);

  if (!loggedIn) {
    state.user = null;
    $('userState').textContent = 'Not signed in';
    $('clientPanel').classList.add('hidden');
    $('adminPanel').classList.add('hidden');
    $('superAdminPanel').classList.add('hidden');
    return;
  }

  try {
    state.user = await api('/api/auth/me');
    $('userState').textContent = `${state.user.role.toUpperCase()}: ${state.user.name}`;

    $('clientPanel').classList.toggle('hidden', state.user.role !== 'client');
    $('adminPanel').classList.toggle('hidden', !['admin', 'super_admin'].includes(state.user.role));
    $('superAdminPanel').classList.toggle('hidden', state.user.role !== 'super_admin');

    if (state.user.role === 'client') await loadClientData();
    if (['admin', 'super_admin'].includes(state.user.role)) await loadAdminData();
    if (state.user.role === 'super_admin') await loadSuperAdminData();
  } catch {
    state.token = '';
    localStorage.removeItem('token');
    await refreshUser();
  }
}

async function loadClientData() {
  const [apps, tickets] = await Promise.all([api('/api/applications/my'), api('/api/tickets/my')]);

  renderList(
    'myApplications',
    apps,
    (a) => `<div class="item"><b>#${a.id} ${a.loan_type}</b> • ₹${Number(a.amount).toLocaleString('en-IN')} <span class="${statusClass(a.status)}">${a.status}</span>
      <div class="muted">Purpose: ${a.purpose}</div>
      <div class="muted">Documents: ${a.documents.join(', ') || 'None'}</div>
      <div class="muted">Extra Documents: ${a.additional_documents.join(', ') || 'None'}</div>
      <div class="muted">Admin note: ${a.admin_note || 'Pending review'}</div>
      ${a.requires_additional_docs ? `<div class="pending">Additional docs requested: ${a.required_docs_note || 'Please upload requested documents.'}</div>` : ''}
    </div>`,
  );

  renderList(
    'myTickets',
    tickets,
    (t) => `<div class="item"><b>${t.subject}</b> <span class="${statusClass(t.status)}">${t.status}</span>
      <div>${t.message}</div>
      <div class="muted">Priority: ${t.priority} • Assigned admin: ${t.assigned_admin_name || 'Pending assignment'}</div></div>`,
  );
}

async function loadAdminData() {
  const [apps, tickets] = await Promise.all([api('/api/applications'), api('/api/tickets')]);

  renderList(
    'adminApplications',
    apps,
    (a) => `<div class="item"><b>#${a.id} ${a.loan_type}</b> • ₹${Number(a.amount).toLocaleString('en-IN')} <span class="${statusClass(a.status)}">${a.status}</span>
      <div class="muted">Client: ${a.client_name} (${a.client_email})</div>
      <div class="muted">Purpose: ${a.purpose}</div>
      <div style="display:flex; gap:.4rem; margin-top:.45rem; flex-wrap: wrap;">
        <button class="btn" onclick="setApplicationStatus(${a.id}, 'Approved')">Approve</button>
        <button class="btn ghost" onclick="setApplicationStatus(${a.id}, 'Rejected')">Reject</button>
        <button class="btn ghost" onclick="requestAdditionalDocs(${a.id})">Request More Docs</button>
      </div>
    </div>`,
  );

  renderList(
    'adminTickets',
    tickets,
    (t) => `<div class="item"><b>#${t.id} ${t.subject}</b> <span class="${statusClass(t.status)}">${t.status}</span>
      <div>${t.message}</div>
      <div class="muted">Client: ${t.owner_name} (${t.owner_email}) • Priority: ${t.priority} • Assigned: ${t.assigned_admin_name || 'None'}</div>
      <div style="display:flex; gap:.4rem; margin-top:.45rem; flex-wrap: wrap;">
        <button class="btn" onclick="setTicketStatus(${t.id}, 'in_progress')">In Progress</button>
        <button class="btn ghost" onclick="setTicketStatus(${t.id}, 'resolved')">Resolve</button>
        <button class="btn ghost" onclick="setTicketStatus(${t.id}, 'open')">Reopen</button>
      </div>
    </div>`,
  );
}

async function loadSuperAdminData() {
  try {
    const traffic = await api('/api/super-admin/traffic');
    $('trafficStats').innerHTML = `
      <article class="tilt"><h4>${traffic.total_api_events}</h4><p class="muted">Total API Events</p></article>
      <article class="tilt"><h4>${traffic.open_tickets}</h4><p class="muted">Open Tickets</p></article>
      <article class="tilt"><h4>${traffic.in_progress_tickets}</h4><p class="muted">In Progress Tickets</p></article>
      <article class="tilt"><h4>${traffic.resolved_tickets}</h4><p class="muted">Resolved Tickets</p></article>
    `;

    renderList('topPaths', traffic.top_paths || [], (p) => `<div class="item"><b>${p.path}</b><div class="muted">Hits: ${p.count}</div></div>`);
    renderList('roleBreakdown', traffic.role_breakdown || [], (r) => `<div class="item"><b>${r.role}</b><div class="muted">Hits: ${r.count}</div></div>`);
  } catch (error) {
    toast(error.message);
  }
}

window.setApplicationStatus = async (id, status) => {
  const admin_note = prompt(`Admin note for ${status}:`) || '';
  try {
    await api(`/api/applications/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, admin_note, requires_additional_docs: false, required_docs_note: '' }),
    });
    toast(`Application ${status}`);
    await Promise.all([loadAdminData(), loadPublicContent()]);
  } catch (error) {
    toast(error.message);
  }
};

window.requestAdditionalDocs = async (id) => {
  const note = prompt('What additional documents are required?') || '';
  try {
    await api(`/api/applications/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'Pending', admin_note: 'Need more documents', requires_additional_docs: true, required_docs_note: note }),
    });
    toast('Additional document request sent to client');
    await loadAdminData();
  } catch (error) {
    toast(error.message);
  }
};

window.setTicketStatus = async (id, status) => {
  try {
    await api(`/api/tickets/${id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    toast(`Ticket moved to ${status}`);
    await Promise.all([loadAdminData(), state.user?.role === 'super_admin' ? loadSuperAdminData() : Promise.resolve()]);
  } catch (error) {
    toast(error.message);
  }
};

$('registerForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(event.target);
  try {
    await api('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: formData.get('name'), email: formData.get('email'), password: formData.get('password') }),
    });
    toast('Registration successful. Please login.');
    event.target.reset();
  } catch (error) {
    toast(error.message);
  }
});

$('loginForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(event.target);
  try {
    const token = await api('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: formData.get('email'), password: formData.get('password') }),
    });
    state.token = token.access_token;
    localStorage.setItem('token', state.token);
    toast('Logged in successfully');
    await refreshUser();
  } catch (error) {
    toast(error.message);
  }
});

$('logoutBtn').addEventListener('click', async () => {
  state.token = '';
  localStorage.removeItem('token');
  toast('Logged out');
  await refreshUser();
});

$('emiForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(event.target);
  try {
    const result = await api('/api/emi/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        principal: Number(formData.get('principal')),
        annual_rate: Number(formData.get('annual_rate')),
        months: Number(formData.get('months')),
      }),
    });
    $('emiResult').textContent = `EMI: ₹${result.emi.toFixed(2)} | Total: ₹${result.total_payment.toFixed(2)} | Interest: ₹${result.total_interest.toFixed(2)}`;
  } catch (error) {
    toast(error.message);
  }
});

$('contactForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(event.target);
  try {
    const result = await api('/api/contact', { method: 'POST', body: formData });
    $('contactResult').textContent = result.message;
    toast('Contact request submitted');
    event.target.reset();
  } catch (error) {
    toast(error.message);
  }
});

$('applicationForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(event.target);
  try {
    await api('/api/applications', { method: 'POST', body: formData });
    toast('Application submitted');
    event.target.reset();
    await Promise.all([loadClientData(), loadPublicContent()]);
  } catch (error) {
    toast(error.message);
  }
});

$('additionalDocForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(event.target);
  const appId = formData.get('application_id');
  const upload = new FormData();
  upload.append('document', formData.get('document'));
  try {
    await api(`/api/applications/${appId}/additional-documents`, { method: 'POST', body: upload });
    toast('Additional document uploaded');
    event.target.reset();
    await loadClientData();
  } catch (error) {
    toast(error.message);
  }
});

$('ticketForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(event.target);
  try {
    await api('/api/tickets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subject: formData.get('subject'), message: formData.get('message'), priority: formData.get('priority') }),
    });
    toast('Ticket created and auto-assigned to admin');
    event.target.reset();
    await loadClientData();
  } catch (error) {
    toast(error.message);
  }
});

loadPublicContent();
refreshUser();
