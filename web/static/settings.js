async function fetchAccounts() {
    const res = await fetch('/api/accounts');
    const rows = await res.json();
    const tb = document.querySelector('#acc-table tbody');
    tb.innerHTML = '';
    for (const r of rows) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
<td>${r.id}</td>
<td>${r.display_name ?? ''}</td>
<td>${r.email}</td>
<td>${r.imap_host ?? ''}:${r.imap_port ?? ''} ${r.imap_ssl ? 'SSL' : ''}</td>
<td>${r.smtp_host ?? ''}:${r.smtp_port ?? ''} ${r.smtp_ssl ? 'SSL' : ''}</td>
<td><button class="btn btn-light" data-id="${r.id}">Διαγραφή</button></td>`;
        tb.appendChild(tr);
    }
// bind delete
    tb.querySelectorAll('button[data-id]').forEach(btn => {
        btn.onclick = async () => {
            if (!confirm('Σίγουρα;')) return;
            const id = btn.getAttribute('data-id');
            const resp = await fetch(`/api/accounts/${id}`, {method: 'DELETE'});
            if (resp.ok) {
                fetchAccounts();
            }
        };
    });
}


document.getElementById('acc-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
// Build payload respecting AccountIn schema
    const payload = {
        display_name: fd.get('display_name') || null,
        email: fd.get('email'),
        imap_host: fd.get('imap_host'),
        imap_port: Number(fd.get('imap_port') || 993),
        imap_ssl: String(fd.get('imap_ssl')) === 'true',
        imap_user: fd.get('imap_user') || null,
        imap_password: fd.get('imap_password'),
        smtp_host: fd.get('smtp_host') || null,
        smtp_port: fd.get('smtp_port') ? Number(fd.get('smtp_port')) : 465,
        smtp_ssl: String(fd.get('smtp_ssl')) === 'true',
        smtp_user: fd.get('smtp_user') || null,
        smtp_password: fd.get('smtp_password') || null,
        can_parse: true,
        can_send: false,
        enabled: true
    };
    const resp = await fetch('/accounts', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });
    const msg = document.getElementById('acc-msg');
    if (resp.ok) {
        msg.textContent = '✓ Προστέθηκε ο λογαριασμός.';
        e.target.reset();
        fetchAccounts();
    } else {
        const t = await resp.text();
        msg.textContent = 'Σφάλμα: ' + t;
    }
});


fetchAccounts();