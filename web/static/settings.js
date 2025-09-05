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



loadAccounts();