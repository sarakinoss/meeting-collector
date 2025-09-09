//async function fetchAccounts() {
//    const res = await fetch('/api/v1/accounts');
//    const rows = await res.json();
//    const tb = document.querySelector('#acc-table tbody');
//    tb.innerHTML = '';
//    for (const r of rows) {
//        const tr = document.createElement('tr');
//        tr.innerHTML = `
//<td>${r.id}</td>
//<td>${r.display_name ?? ''}</td>
//<td>${r.email}</td>
//<td>${r.imap_host ?? ''}:${r.imap_port ?? ''} ${r.imap_ssl ? 'SSL' : ''}</td>
//<td>${r.smtp_host ?? ''}:${r.smtp_port ?? ''} ${r.smtp_ssl ? 'SSL' : ''}</td>
//<td><button class="btn btn-light" data-id="${r.id}">Διαγραφή</button></td>`;
//        tb.appendChild(tr);
//    }
//// bind delete
//    tb.querySelectorAll('button[data-id]').forEach(btn => {
//        btn.onclick = async () => {
//            if (!confirm('Σίγουρα;')) return;
//            const id = btn.getAttribute('data-id');
//            const resp = await fetch(`/api/v1/accounts/${id}`, {method: 'DELETE'});
//            if (resp.ok) {
//                fetchAccounts();
//            }
//        };
//    });
//}
//
//
//document.getElementById('acc-form').addEventListener('submit', async (e) => {
//    e.preventDefault();
//    const fd = new FormData(e.target);
//// Build payload respecting AccountIn schema
//    const payload = {
//        display_name: fd.get('display_name') || null,
//        email: fd.get('email'),
//        imap_host: fd.get('imap_host'),
//        imap_port: Number(fd.get('imap_port') || 993),
//        imap_ssl: String(fd.get('imap_ssl')) === 'true',
//        imap_user: fd.get('imap_user') || null,
//        imap_password: fd.get('imap_password'),
//        smtp_host: fd.get('smtp_host') || null,
//        smtp_port: fd.get('smtp_port') ? Number(fd.get('smtp_port')) : 465,
//        smtp_ssl: String(fd.get('smtp_ssl')) === 'true',
//        smtp_user: fd.get('smtp_user') || null,
//        smtp_password: fd.get('smtp_password') || null,
//        can_parse: true,
//        can_send: false,
//        enabled: true
//    };
//    const resp = await fetch('/api/v1/accounts', {
//        method: 'POST',
//        headers: {'Content-Type': 'application/json'},
//        body: JSON.stringify(payload)
//    });
//    const msg = document.getElementById('acc-msg');
//    if (resp.ok) {
//        msg.textContent = '✓ Προστέθηκε ο λογαριασμός.';
//        e.target.reset();
//        fetchAccounts();
//    } else {
//        const t = await resp.text();
//        msg.textContent = 'Σφάλμα: ' + t;
//    }
//});
//
////async function deleteUser(id){
////  if(!confirm("Να διαγραφεί ο χρήστης #"+id+";")) return;
////  const res = await fetch(`/auth/admin/users/${id}`, { method: "DELETE" });
////  if(res.ok){
////    const tr = document.querySelector(`tr[data-id="${id}"]`);
////    tr?.parentNode?.removeChild(tr);
////  }else{
////    const body = await res.json().catch(()=>({}));
////    alert("Σφάλμα: " + (body.detail || res.status));
////  }
////}
//
//
//fetchAccounts();

const API_ACCOUNTS = "/api/v1/accounts";
const SPRITE = '/static/icons/sprite.svg';
const API_PROFILE = '/api/v1/profile';

function banner(type, text){
  const el = document.createElement("div");
  el.className = "banner " + (type === "error" ? "error" : "success");
  el.textContent = text;
  document.getElementById("banner-area").appendChild(el);
  setTimeout(()=>el.remove(), 3500);
}

async function loadAccounts(){
  const res = await fetch(API_ACCOUNTS);
  if(!res.ok){ banner("error","Σφάλμα φόρτωσης λογαριασμών"); return; }
  const rows = await res.json();
  const tb = document.getElementById("accountsBody");
  if(!tb) return;
  tb.innerHTML = "";
  for(const r of rows){
    const tr = document.createElement("tr");
    tr.dataset.id = r.id;
    tr.innerHTML = `
      <td><span class="dot dot-gray" id="acc-dot-${r.id}" title="Unknown"></span></td>
      <td>${r.id}</td>
      <td>${r.display_name || ""}</td>
      <td>${r.email || ""}</td>
      <td>${r.imap_host}:${r.imap_port} ${r.imap_ssl ? "SSL" : ""}</td>
      <td>${r.smtp_host}:${r.smtp_port} ${r.smtp_ssl ? "SSL" : ""}</td>
      <!--<td><button class="btn btn-danger" onclick="deleteAccount(${r.id})">Διαγραφή</button></td>-->
      <td>
        <button class="btn btn-danger icon-btn inline-flex items-center gap-1"
                title="Διαγραφή" onclick="deleteAccount(${r.id})">
          <svg class="w-2 h-2" aria-hidden="true" focusable="false">
            <use href="${SPRITE}#delete"></use>
          </svg>
          <span class="btn-label">Διαγραφή</span>
        </button>
      </td>
    `;
    tb.appendChild(tr);

    // Προγραμμάτισε έλεγχο status για το συγκεκριμένο account
    scheduleStatusCheck(r.id);
  }
}

async function deleteAccount(id){
  if(!confirm("Να διαγραφεί ο λογαριασμός #"+id+";")) return;
  const res = await fetch(`${API_ACCOUNTS}/${id}`, { method: "DELETE" });
  if(res.ok){
    document.querySelector(`tr[data-id="${id}"]`)?.remove();
    banner("success","Ο λογαριασμός διαγράφηκε");
  }else{
    const body = await res.json().catch(()=>({}));
    banner("error","Σφάλμα: " + (body.detail || res.status));
  }
}

/*async function testImap() {
  const fd = new FormData(document.getElementById("formAddAccount"));
  const payload = {};
  for (const [k,v] of fd.entries()) {
    if(["imap_ssl","smtp_ssl"].includes(k)) payload[k] = (v === "true");
    else if(["imap_port","smtp_port"].includes(k)) payload[k] = Number(v);
    else payload[k] = v;
  }

  // μόνο IMAP credentials χρειάζονται
  const body = {
    email: payload.email,
    imap_host: payload.imap_host,
    imap_port: payload.imap_port,
    imap_ssl: payload.imap_ssl,
    imap_user: payload.imap_user,
    imap_password: payload.imap_password,
  };

  const res = await fetch("/api/v1/accounts/test-connection", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  });
  if(res.ok){
    const data = await res.json().catch(()=>({}));
    banner("success", data.detail || "IMAP σύνδεση επιτυχής");
  } else {
    const data = await res.json().catch(()=>({}));
    banner("error", data.detail || "Σφάλμα IMAP σύνδεσης");
  }
}*/
async function testImap() {
  const fd = new FormData(document.getElementById("formAddAccount"));
  const body = {
    email: fd.get("email") || "",
    imap_host: fd.get("imap_host") || "",
    imap_password: fd.get("imap_password") || "",
  };

  // optional πεδία (αν υπάρχουν στη φόρμα)
  const imap_user = fd.get("imap_user");
  if (imap_user) body.imap_user = imap_user;
  const imap_port = fd.get("imap_port");
  if (imap_port) body.imap_port = Number(imap_port);
  const imap_ssl = fd.get("imap_ssl");
  if (imap_ssl != null) body.imap_ssl = (imap_ssl === "true" || imap_ssl === true);

  // Disable κουμπί όσο τρέχει
  const btn = document.querySelector('button.btn.btn-secondary');
  if (btn) btn.disabled = true;

  const res = await fetch("/api/v1/accounts/test-connection", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  });

  let msg = "Σφάλμα IMAP σύνδεσης";
  try {
    // προτίμησε JSON.detail
    const data = await res.json();
    if (data && data.detail) msg = data.detail;
  } catch {
    // αν δεν είναι JSON, πάρε το raw text
    try { msg = await res.text(); } catch {}
  }

  if (btn) btn.disabled = false;

  if (res.ok) {
    banner("success", msg || "IMAP σύνδεση επιτυχής");
  } else {
    banner("error", msg || "Σφάλμα IMAP σύνδεσης");
  }
}

// μικρή ουρά ώστε να μη «σφυροκοπάμε» τον server (και να μη παγώνει το UI)
let statusQueue = [];
let draining = false;

function setDot(id, color, title){
  const el = document.getElementById(`acc-dot-${id}`);
  if(!el) return;
  el.classList.remove("dot-gray","dot-green","dot-red");
  el.classList.add(color);
  if(title) el.title = title;
}

async function refreshAccountStatus(id){
  try {
    const res = await fetch(`/api/v1/accounts/${id}/test-connection`, { method: "POST" });
    if(res.ok){
      const data = await res.json().catch(()=>({}));
      setDot(id, "dot-green", (data && data.detail) || "OK");
    } else {
      let msg = "Error";
      try {
        const data = await res.json();
        msg = data.detail || msg;
      } catch {}
      setDot(id, "dot-red", msg);
    }
  } catch (e){
    setDot(id, "dot-red", String(e));
  }
}

function scheduleStatusCheck(id){
  statusQueue.push(id);
  if(!draining) drainQueue();
}

async function drainQueue(){
  draining = true;
  while(statusQueue.length){
    const id = statusQueue.shift();
    await refreshAccountStatus(id);
    await new Promise(r => setTimeout(r, 150)); // μικρό stagger
  }
  draining = false;
}



document.getElementById("formAddAccount")?.addEventListener("submit", async (e)=>{
  e.preventDefault();
  const fd = new FormData(e.target);
  const payload = {};
  for(const [k,v] of fd.entries()){
    if(["imap_ssl","smtp_ssl"].includes(k)) payload[k] = (v === "true");
    else if(["imap_port","smtp_port"].includes(k)) payload[k] = Number(v);
    else payload[k] = v;
  }
  const res = await fetch(API_ACCOUNTS, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(payload)
  });
  if(res.ok){
    e.target.reset();
    banner("success","Ο λογαριασμός προστέθηκε");
    loadAccounts();
  }else{
    const body = await res.json().catch(()=>({}));
    banner("error","Σφάλμα: " + (body.detail || res.status));
  }
});


// ================== Notifications Settings ==================
(() => {
  const API_NOTIF = "/api/v1/notifications";
  const API_NOTIF_TEST = "/api/v1/notifications/test";
  const API_NOTIF_DAILY_NOW = "/api/v1/notifications/daily-now";
  const API_NOTIF_REMINDERS_NOW = "/api/v1/notifications/reminders-now";

  // Safe banner helper
  function notify(type, msg){
    if (typeof banner === "function") banner(type, msg);
    else console[type === "error" ? "error" : "log"](msg);
  }

  // Collect all checkbox values with given name
  function collectChecked(name){
    return Array.from(document.querySelectorAll(`input[name="${name}"]:checked`))
      .map(el => el.value);
  }

  // ---- Load prefs and fill the form ----
  async function loadNotifications(){
    const form = document.getElementById("formNotifications");
    if (!form) return;

    try{
      const res = await fetch(API_NOTIF, { credentials: "same-origin" });
      if(!res.ok) throw new Error(`GET ${API_NOTIF} -> ${res.status}`);
      const data = await res.json();

      // 1) Daily summary
      const t = document.getElementById("not_daily_hour");
      if (t && data.not_daily_hour) t.value = data.not_daily_hour;

      // Days
      const setAll = new Set(data.not_days || []);
      document.querySelectorAll('input[name="not_days"]').forEach(cb => {
        cb.checked = setAll.has(cb.value);
      });
      // Master checkbox reflects current state
      const all = document.getElementById("not_days_all");
      if (all){
        const items = Array.from(document.querySelectorAll('input[name="not_days"]'));
        all.checked = items.length>0 && items.every(cb => cb.checked);
      }

      // 2) Reminder before meeting
      const priorSel = document.getElementById("not_prior_minutes");
      if (priorSel){
        if (data.not_prior_minutes == null) priorSel.value = "off";
        else priorSel.value = String(data.not_prior_minutes);
      }

      // 3) SMTP sender
      const h = document.getElementById("not_smtp_host");
      const p = document.getElementById("not_smtp_port");
      const u = document.getElementById("not_user_smtp");
      const w = document.getElementById("not_pass_smtp");
      if (h) h.value = data.not_smtp_host ?? "";
      if (p) p.value = data.not_smtp_port ?? "";
      if (u) u.value = data.not_user_smtp ?? "";
      if (w){
        // Το API δεν επιστρέφει password. Αν υπάρχει αποθηκευμένο, παίρνουμε flag not_pass_set.
        w.value = "";
        w.placeholder = data.not_pass_set ? "•••• (saved)" : "••••••••";
      }

      // 4) Receiver
      const r = document.getElementById("not_receiver");
      if (r) r.value = data.not_receiver ?? "";

    }catch(err){
      notify("error", "Αποτυχία φόρτωσης ρυθμίσεων ειδοποιήσεων");
      console.error(err);
    }
  }

  // ---- Save handler (PUT) ----
  async function saveNotifications(e){
    e?.preventDefault?.();
    const form = document.getElementById("formNotifications");
    if (!form) return;

    // Build payload
    const daily = (document.getElementById("not_daily_hour")?.value || "").trim();

    const days = collectChecked("not_days");
    const priorRaw = document.getElementById("not_prior_minutes")?.value || "off";
    const prior = priorRaw === "off" ? null : parseInt(priorRaw, 10);

    const host = document.getElementById("not_smtp_host")?.value?.trim() || null;
    const portVal = document.getElementById("not_smtp_port")?.value?.trim();
    const port = portVal ? parseInt(portVal, 10) : null;
    const user = document.getElementById("not_user_smtp")?.value?.trim() || null;
    const pass = document.getElementById("not_pass_smtp")?.value ?? ""; // κενό = μην αλλάξεις
    const recv = document.getElementById("not_receiver")?.value?.trim() || null;

    const payload = {
      not_daily_hour: daily,
      not_days: days,
      not_prior_minutes: prior,
      not_smtp_host: host,
      not_smtp_port: port,
      not_user_smtp: user,
      not_receiver: recv
      // not_pass_smtp: (μόνο αν δόθηκε)
    };
    if (pass !== "") payload.not_pass_smtp = pass;

    // Disable buttons while saving
    const btnSave = document.getElementById("btnSaveNotifications");
    const btnTest = document.getElementById("btnTestNotif");
    const prevSaveTxt = btnSave ? btnSave.textContent : "";
    if (btnSave) { btnSave.disabled = true; btnSave.textContent = "Αποθήκευση…"; }
    if (btnTest) btnTest.disabled = true;

    try{
      const res = await fetch(API_NOTIF, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify(payload)
      });
      if(!res.ok){
        const errBody = await res.json().catch(()=> ({}));
        throw new Error(errBody.detail || `PUT failed (${res.status})`);
      }
      notify("success", "Οι ρυθμίσεις αποθηκεύτηκαν");
      // Μετά το save, ξανα-φορτώνουμε ώστε να φρεσκάρουμε το placeholder του password
      await loadNotifications();
    }catch(err){
      notify("error", String(err.message || err));
      console.error(err);
    }finally{
      if (btnSave) { btnSave.disabled = false; btnSave.textContent = prevSaveTxt || "Αποθήκευση"; }
      if (btnTest) btnTest.disabled = false;
    }
  }

  // ---- Wire UI (select-all days, change listeners, submit) ----
  function wireNotificationsUI(){
    const form = document.getElementById("formNotifications");
    if (!form) return;

    // Master "Όλες"
    const master = document.getElementById("not_days_all");
    const cbs = Array.from(document.querySelectorAll('input[name="not_days"]'));

    if (master){
      master.addEventListener("change", () => {
        cbs.forEach(cb => { cb.checked = master.checked; });
      });
    }
    // Όταν αλλάζει οποιοδήποτε day, ενημέρωσε το master
    cbs.forEach(cb => cb.addEventListener("change", () => {
      if (!master) return;
      master.checked = cbs.length>0 && cbs.every(x => x.checked);
    }));

    // Submit handler
    form.addEventListener("submit", saveNotifications);
  }


  async function testNotification(){
    const btn = document.getElementById("btnTestNotif");
    if (!btn) return;
    const prev = btn.textContent;
    btn.disabled = true; btn.textContent = "Αποστολή…";

    const to = document.getElementById("not_receiver")?.value?.trim();
    const payload = to ? { to } : {};

    try{
      const res = await fetch(API_NOTIF_TEST, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify(payload)
      });
      const data = await res.json().catch(()=> ({}));
      if(!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      if (typeof banner === "function")
        banner("success", `Στάλθηκε δοκιμαστικό στο ${data.to}`);
      else console.log("Test sent to", data.to);
    }catch(err){
      if (typeof banner === "function") banner("error", String(err.message || err));
      console.error(err);
    }finally{
      btn.disabled = false; btn.textContent = prev || "Δοκιμαστική αποστολή";
    }
  }

  async function sendDailyNow(){
    const btn = document.getElementById("btnSendSummaryNow");
    if (!btn) return;
    const prev = btn.textContent;
    btn.disabled = true; btn.textContent = "Αποστολή…";

    try{
      const res = await fetch(API_NOTIF_DAILY_NOW, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin"
      });
      const data = await res.json().catch(()=> ({}));
      if(!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      if (typeof banner === "function")
        banner("success", `Στάλθηκε σύνοψη (${data.count} meeting${data.count===1?"":"s"}) για ${data.date} στο ${data.to}`);
      else console.log("Daily summary sent:", data);
    }catch(err){
      if (typeof banner === "function") banner("error", String(err.message || err));
      console.error(err);
    }finally{
      btn.disabled = false; btn.textContent = prev || "Αποστολή τώρα";
    }
  }

  async function runRemindersNow(){
    const btn = document.getElementById("btnRemindersNow");
    if (!btn) return;
    const prev = btn.textContent;
    btn.disabled = true; btn.textContent = "Έλεγχος…";

    try{
      const res = await fetch(API_NOTIF_REMINDERS_NOW, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin"
      });
      const data = await res.json().catch(()=> ({}));
      if(!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

      const msg = `Υπενθυμίσεις: στάλθηκαν ${data.count} email(s) για στόχο ${data.target_local} (παράθυρο ${data.window_local[0]}–${data.window_local[1]}), στον ${data.to}.`;
      if (typeof banner === "function") banner("success", msg);
      else console.log(msg, data.sent_ids);
    }catch(err){
      if (typeof banner === "function") banner("error", String(err.message || err));
      console.error(err);
    }finally{
      btn.disabled = false; btn.textContent = prev || "Έλεγχος υπενθυμίσεων τώρα";
    }
  }



  // Boot
  window.addEventListener("DOMContentLoaded", () => {
    // τρέχει ΜΟΝΟ αν υπάρχει το form της καρτέλας notifications
    if (document.getElementById("formNotifications")){
      wireNotificationsUI();
      loadNotifications();
    }
  });

  // Test notification btn
  window.addEventListener("DOMContentLoaded", () => {
    document.getElementById("btnTestNotif")?.addEventListener("click", testNotification);
  });

  // Test Daily now
  window.addEventListener("DOMContentLoaded", () => {
    document.getElementById("btnSendSummaryNow")?.addEventListener("click", sendDailyNow);
  });

  window.addEventListener("DOMContentLoaded", () => {
    document.getElementById("btnRemindersNow")?.addEventListener("click", runRemindersNow);
  });
})();



(() => {
  const API_PROFILE = '/api/v1/profile';

  // μικρό helper banner (αν δεν υπάρχει ήδη)
  function say(kind, msg){
    if (typeof banner === 'function') { banner(kind, msg); return; }
    console[kind === 'error' ? 'error' : 'log'](msg);
  }

  // DOM refs (μόνο αν είμαστε στη σελίδα/καρτέλα profile)
  const form = document.getElementById('formProfile');
  if(!form) return;   // δεν είμαστε στο profile tab

  const inpRetention = document.getElementById('prof_retention_months');
  const wrapFolders  = document.getElementById('prof-folders');
  const btnLoad      = document.getElementById('btnLoadFolders');
  const btnSave      = document.getElementById('btnSaveProfile');

  // ---------------- API helpers ----------------
  async function getJSON(url){
    const r = await fetch(url);
    if(!r.ok) throw new Error(`${r.status} ${url}`);
    return r.json();
  }
  async function sendJSON(url, method, body){
    const r = await fetch(url, {
      method, headers: { 'Content-Type':'application/json' },
      body: JSON.stringify(body)
    });
    if(!r.ok){
      let detail = '';
      try{ const j=await r.json(); detail = j.detail || ''; }catch{}
      throw new Error(`${r.status} ${detail || url}`);
    }
    return r.json().catch(()=> ({}));
  }

  // ---------------- Load prefs ----------------
  async function loadProfilePrefs(){
    try{
      const prefs = await getJSON(`${API_PROFILE}/prefs`);
      if (prefs && typeof prefs.prof_retention_months !== 'undefined' && inpRetention){
        inpRetention.value = prefs.prof_retention_months ?? '';
      }
    }catch(e){
      say('error', 'Αποτυχία φόρτωσης profile preferences');
    }
  }

  // ---------------- Accounts + shells ----------------
  async function loadAccountsShells(){
    // καθάρισε
    if (wrapFolders) wrapFolders.innerHTML = '';
    let accounts = [];
    try{
      accounts = await getJSON(`${API_PROFILE}/accounts`);
    }catch(e){
      say('error', 'Αποτυχία φόρτωσης λογαριασμών');
      return [];
    }
    if (!accounts.length){
      wrapFolders.innerHTML = `<div class="placeholder">Δεν υπάρχουν λογαριασμοί email.</div>`;
      return [];
    }
    for(const acc of accounts){
      renderAccountShell(acc);
      // Φέρε τους ήδη επιλεγμένους (selected) για να τους τικάρουμε, χωρίς LIST ακόμα
      try{
        const data = await getJSON(`${API_PROFILE}/accounts/${acc.id}/folders`);
        renderSelectedOnly(acc.id, data.selected || []);
      }catch(e){
        // αθόρυβα—ο χρήστης θα πατήσει "Φόρτωση φακέλων"
      }
    }
    return accounts;
  }

  function renderAccountShell(acc){
    const el = document.createElement('div');
    el.className = 'account-block';
    el.dataset.accountId = String(acc.id);
    el.innerHTML = `
      <div class="acc-header">
        <div class="acc-title">${escapeHtml(acc.display_name || '')} — ${escapeHtml(acc.email || '')}</div>
        <button type="button" class="btn btn-ghost btn-sm" data-refresh-folders>Ανανέωση φακέλων</button>
      </div>
      <div class="folders-grid" data-folders></div>
    `;
    wrapFolders.appendChild(el);

    el.querySelector('[data-refresh-folders]')?.addEventListener('click', async () => {
      await refreshFoldersForAccount(acc.id);
    });
  }

  function escapeHtml(s){
    return (s||'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  // όταν έχουμε μόνο selected (χωρίς διαθέσιμους), δείξ’ τα σαν ticked items
  function renderSelectedOnly(accountId, selected){
    const block = wrapFolders.querySelector(`.account-block[data-account-id="${accountId}"]`);
    if(!block) return;
    const grid = block.querySelector('[data-folders]');
    grid.innerHTML = '';
    const set = new Set(selected || []);
    if(!set.size){
      grid.innerHTML = `<div class="muted">Δεν έχουν οριστεί φάκελοι. Πάτησε «Ανανέωση φακέλων».</div>`;
      return;
    }
    for(const f of set){
      grid.appendChild(folderTile(accountId, f, true));
    }
  }

  // φτιάχνει ένα checkbox-tile
  function folderTile(accountId, folderName, checked){
    const lbl = document.createElement('label');
    lbl.className = 'folder-check';
    lbl.innerHTML = `
      <input type="checkbox" data-folder value="${escapeHtml(folderName)}" ${checked ? 'checked' : ''}>
      <span class="label-text">${escapeHtml(folderName)}</span>
    `;
    lbl.dataset.accountId = String(accountId);
    return lbl;
  }

  // ---------------- IMAP LIST (per account) ----------------
  async function refreshFoldersForAccount(accountId){
    const block = wrapFolders.querySelector(`.account-block[data-account-id="${accountId}"]`);
    if(!block) return;
    const grid = block.querySelector('[data-folders]');
    grid.innerHTML = `<div class="muted">Φόρτωση φακέλων…</div>`;

    try{
      const data = await sendJSON(`${API_PROFILE}/accounts/${accountId}/folders/refresh`, 'POST', {});
      const available = Array.isArray(data.available) ? data.available : [];
      const selected  = new Set(Array.isArray(data.selected) ? data.selected : []);
      grid.innerHTML = '';
      if(!available.length){
        grid.innerHTML = `<div class="muted">Δεν επιστράφηκαν φάκελοι από τον IMAP server.</div>`;
        return;
      }
      for(const name of available){
        grid.appendChild(folderTile(accountId, name, selected.has(name)));
      }
    }catch(e){
      grid.innerHTML = `<div class="muted">Σφάλμα κατά τη φόρτωση φακέλων.</div>`;
      say('error', 'Αποτυχία «Ανανέωση φακέλων» (IMAP LIST)');
    }
  }

  // Γενικό: “Φόρτωση φακέλων” για ΟΛΑ τα accounts
  async function refreshAll(){
    const blocks = wrapFolders.querySelectorAll('.account-block');
    for (const b of blocks){
      const id = Number(b.dataset.accountId);
      await refreshFoldersForAccount(id);
    }
  }

  // ---------------- SAVE ----------------
  // Μαζεύει checked folders ανά account από το DOM
  function collectSelectedPerAccount(){
    const map = new Map(); // accId -> [folders]
    wrapFolders.querySelectorAll('.account-block').forEach(block => {
      const accId = Number(block.dataset.accountId);
      const arr = [];
      block.querySelectorAll('input[type="checkbox"][data-folder]:checked').forEach(ch => {
        arr.push(ch.value);
      });
      map.set(accId, arr);
    });
    return map;
  }

  async function saveAll(){
    // 1) prefs (retention)
    const retention = inpRetention?.value ? Number(inpRetention.value) : null;
    try{
      await sendJSON(`${API_PROFILE}/prefs`, 'PUT', { prof_retention_months: retention || null });
    }catch(e){
      say('error','Αποτυχία αποθήκευσης προτιμήσεων');
      return;
    }

    // 2) folders per account
    const map = collectSelectedPerAccount();
    for (const [accId, folders] of map.entries()){
      try{
        await sendJSON(`${API_PROFILE}/accounts/${accId}/folders`, 'POST', { folders });
      }catch(e){
        say('error', `Αποτυχία αποθήκευσης φακέλων για λογαριασμό #${accId}`);
        // συνεχίζουμε με τους υπόλοιπους
      }
    }
    say('success','Αποθηκεύτηκαν οι ρυθμίσεις του Profile');
  }

  // ---------------- Wire up ----------------
  btnLoad?.addEventListener('click', (e)=>{ e.preventDefault(); refreshAll(); });
  btnSave?.addEventListener('click', async (e)=>{ e.preventDefault(); await saveAll(); });

  // Init flow
  (async function init(){
    await loadProfilePrefs();
    await loadAccountsShells();  // φτιάχνει τα blocks + tics από selected
    // ο χρήστης μπορεί να πατήσει «Φόρτωση φακέλων» για πλήρη λίστα
  })();
})();





loadAccounts();