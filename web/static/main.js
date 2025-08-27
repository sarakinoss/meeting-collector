(() => {
    'use strict';

    // ---------- Small helpers ----------
    const $ = (sel, root = document) => root.querySelector(sel);
    const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

    // ---- API endpoints (προσαρμόζεις αν τα έχεις με άλλο path)
    const API_ACCOUNTS = "api/v1/accounts"; // GET -> [{id,email,parse_enabled,last_full_parse_at,last_incremental_parse_at}, ...]
    const API_PARSE    = "/api/v1/meetings/actions/parse";   // κοινό endpoint

    const API_UPDATE   = "/update";         // POST -> {status:"update_triggered"}
    const API_FULL     = "/full-parse";     // POST -> {status:"full_parse_triggered"}

    // Αν θες το legacy shape για το grid:
    const API_MEETINGS = "/api/v1/meetings";      // ίδιο σχήμα με παλιό /meetings
// ή, αν θες το “πλουσιότερο”:
    const API_MEETINGS_DB = "/api/v1/meetings/db";


    const sidePanel   = $('#sidePanel');
    const sideOverlay = $('#sideOverlay');
    const btnToggle   = $('#btnSideToggle');

    function openSide() {
        sidePanel?.classList.remove('-translate-x-full');
        sideOverlay?.classList.remove('hidden');
    }

    function closeSide() {
        sidePanel?.classList.add('-translate-x-full');
        sideOverlay?.classList.add('hidden');
    }

    btnToggle?.addEventListener('click', () => {
        if (!sidePanel) return;
        const hidden = sidePanel.classList.contains('-translate-x-full');
        hidden ? openSide() : closeSide();
    });

    sideOverlay?.addEventListener('click', closeSide);


    function onReady(cb) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', cb, {once: true});
        } else {
            cb();
        }
    }

    function debounce(fn, wait = 150) {
        let t;
        return (...args) => {
            clearTimeout(t);
            t = setTimeout(() => fn(...args), wait);
        };
    }

    /*function platformBadge(p) {
        if (p === 'zoom') return '<span class="badge badge-zoom">Zoom</span>';
        if (p === 'teams') return '<span class="badge badge-teams">Teams</span>';
        if (p === 'google') return '<span class="badge badge-google">Google</span>';
        return '<span class="badge bg-slate-100 text-slate-700">Other</span>';
    }*/
    function platformBadge(p) {
        const base = "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium";
        const map = {
            zoom: "bg-blue-100 text-blue-700",
            teams: "bg-purple-100 text-purple-700",
            google: "bg-green-100 text-green-700",
            other: "bg-slate-100 text-slate-700"
        };
        const k = (p || 'other').toLowerCase();
        const label = k === 'google' ? 'Google' : k.charAt(0).toUpperCase() + k.slice(1);
        return `<span class="${base} ${map[k] || map.other}">${label}</span>`;
    }

    // Incoming format: RFC 2822-like e.g. "Fri, 18 Jul 2025 11:00:00 +0300"
    function toISO(dtStr) {
        const d = new Date(dtStr);
        return isNaN(d) ? null : d.toISOString();
    }

    function formatLocal(dtStr) {
        const d = new Date(dtStr);
        if (isNaN(d)) return '';
        return d.toLocaleString([], {dateStyle: 'medium', timeStyle: 'short'});
    }

    function googleCalendarUrl(ev) {
        // Build a Google Calendar template link (defaults to 60min duration if no end)
        const start = new Date(ev.start);
        const end = ev.extendedProps?.end ? new Date(ev.extendedProps.end) : new Date(start.getTime() + 60 * 60000);
        const fmt = d => d.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
        const text = encodeURIComponent(ev.title || 'Meeting');
        const details = encodeURIComponent((ev.extendedProps?.link || '') + '\n' + (ev.extendedProps?.subject || ''));
        const location = encodeURIComponent(ev.extendedProps?.platform || '');
        return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${text}&dates=${fmt(start)}/${fmt(end)}&details=${details}&location=${location}`;
    }

    function downloadICS(events) {
        const dtstamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
        const lines = [
            'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Meeting Collector//EN'
        ];
        for (const ev of events) {
            const start = new Date(ev.start);
            const end = ev.extendedProps?.end ? new Date(ev.extendedProps.end) : new Date(start.getTime() + 60 * 60000);
            const fmt = d => d.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
            lines.push(
                'BEGIN:VEVENT',
                `UID:${ev.id || crypto.randomUUID()}@meeting-collector`,
                `DTSTAMP:${dtstamp}`,
                `DTSTART:${fmt(start)}`,
                `DTEND:${fmt(end)}`,
                `SUMMARY:${(ev.title || '').replace(/\n/g, ' ')}`,
                `DESCRIPTION:${(ev.extendedProps?.link || '')}`,
                'END:VEVENT'
            );
        }
        lines.push('END:VCALENDAR');
        const blob = new Blob([lines.join('\r\n')], {type: 'text/calendar'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'meetings.ics';
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 5000);
    }

    // ---------- Data state ----------
    let ALL = [];      // raw meetings from API
    let EVENTS = [];   // transformed events with date & link
    let calendar = null; // FullCalendar instance
    let statusTimer = null;

    function deriveTitle(m) {
        const subject = m.msg_subject?.trim();
        if (subject) return subject;
        return (m.meet_platform || 'meeting').toUpperCase() + ' ' + (m.meet_id || '');
    }

    function transform(meetings) {
        return meetings
            .filter(m => /*!!m.meet_link &&*/ !!m.meet_date)
            .map(m => ({
                id: m.meet_id,
                title: deriveTitle(m),
                start: toISO(m.meet_date),
                url: m.meet_link,
                extendedProps: {
                    platform: m.meet_platform,
                    subject: m.msg_subject,
                    sender: m.msg_sender,
                    attendees: m.meet_attendants || m.msg_attendants,
                    account: m.msg_account,
                    folder: m.msg_folder,
                    link: m.meet_link,
                    rawDate: m.meet_date,
                    end: m.meet_end_date || null, // optional future field from API
                    msg_id: m.msg_id || null
                }
            }))
            .filter(e => !!e.start);
    }

    function rowsFromAll(meetings) {
        return meetings.map(m => ({
            id: m.meet_id,
            title: deriveTitle(m),
            start: m.meet_date ? toISO(m.meet_date) : null,
            url: m.meet_link,
            extendedProps: {
                platform: m.meet_platform,
                subject: m.msg_subject,
                sender: m.msg_sender,
                attendees: m.meet_attendants || m.msg_attendants,
                account: m.msg_account,
                folder: m.msg_folder,
                link: m.meet_link,
                rawDate: m.meet_date,
                end: m.meet_end_date || null,
                msg_id: m.msg_id || null
            }
        }));
    }

    const accountCbs = $$('#accountsList input[type="checkbox"]');
    const useAccountFilter = accountCbs.length > 0;         // μόνο αν έχουν φορτωθεί accounts
    const selectedAccs = useAccountFilter ? getSelectedAccounts() : null;

    function applyFilters(list) {
        const qEl = $('#q');
        const fromEl = $('#from');
        const toEl = $('#to');
        const q = qEl ? qEl.value.trim().toLowerCase() : '';
        const plats = $$('.platform').filter(x => x.checked).map(x => x.value);
        const from = fromEl && fromEl.value ? new Date(fromEl.value) : null;
        const to = toEl && toEl.value ? new Date(toEl.value + 'T23:59:59') : null;

        return list.filter(ev => {
            // platform
            if (plats.length && !plats.includes((ev.extendedProps.platform || '').toLowerCase())) return false;
            // date range
            const d = ev.start ? new Date(ev.start) : null;
            if (from && d && d < from) return false;
            if (to && d && d > to) return false;
            // query
            if (q) {
                const hay = `${ev.title} ${(ev.extendedProps.subject || '')} ${(ev.extendedProps.sender || '')} ${(ev.extendedProps.attendees || '')}`.toLowerCase();
                if (!hay.includes(q)) return false;
            }
            // --- Account filter ---
            if (useAccountFilter) {
                // Αν δεν έχει επιλεγεί κανένας λογαριασμός → μην εμφανίζεις κανένα meeting
                if (selectedAccs.size === 0) return false;

                // Πάρε το account id/email από τα extendedProps
                const accKey =
                    String(
                        ev.extendedProps?.account_id ??
                        ev.extendedProps?.accountId ??
                        ev.extendedProps?.account ??
                        ev.extendedProps?.email ??
                        ''
                    );

                // Αν το event έχει ταυτότητα account και ΔΕΝ είναι στη λίστα των επιλεγμένων → κόψ’ το
                if (accKey && !selectedAccs.has(accKey)) return false;
            }
            return true;
        });
    }

    async function fetchMeetings() {
        const status = $('#status');
        if (status) status.textContent = 'loading…';
        try {
            const res = await fetch('/api/v1/meetings');
            if (!res.ok) throw new Error('HTTP ' + res.status);
            ALL = await res.json();
            EVENTS = transform(ALL);
        } catch (err) {
            console.error(err);
            ALL = [];
            EVENTS = [];
        } finally {
            updateStatus();
            render(); // always render even if 0 events
        }
    }

    function updateStatus() {
        const status = $('#status');
        if (!status) return;
        const total = ALL.length;
        const withLink = ALL.filter(m => m.meet_link).length;
        const withDate = ALL.filter(m => m.meet_date).length;
        const withBoth = EVENTS.length;
        status.textContent = `events ${withBoth} • links ${withLink}/${total} • dates ${withDate}/${total}`;
    }

    function updateStatusCounts() {
        const status = $('#status');
        if (!status) return;
        const total = ALL.length;
        const withLink = ALL.filter(m => m.meet_link).length;
        const withDate = ALL.filter(m => m.meet_date).length;
        const withBoth = EVENTS.length;
        status.textContent = `events ${withBoth} • links ${withLink}/${total} • dates ${withDate}/${total}`;
    }

    const date = new Date();
    const day = date.getDate();
    const monthNames = ["ΙΑΝ", "ΦΕΒ", "ΜΑΡ", "ΑΠΡ", "ΜΑΪ", "ΙΟΥΝ", "ΙΟΥΛ", "ΑΥΓ", "ΣΕΠ", "ΟΚΤ", "ΝΟΕ", "ΔΕΚ"];

    document.getElementById("calendarDay").textContent = day;
    document.querySelector("#calendarIcon div:first-child").textContent = monthNames[date.getMonth()];

    // ---- NEW: poll /status and toggle loader/progress ----
    async function pollStatus() {
        try {
            const res = await fetch('/api/v1/meetings/status');
            if (!res.ok) throw new Error('HTTP ' + res.status);
            const s = await res.json();
            const loader = $('#loader');
            const bar = $('#progress');
            const fill = $('#progress-bar');
            const text = $('#loader-text');
            const st = s?.collector?.status || 'idle';
            const msg = s?.collector?.message || '';
            const prg = Number(s?.collector?.progress ?? 0);

            const running = st === 'running';
            if (loader) loader.classList.toggle('hidden', !running);
            if (bar) bar.classList.toggle('hidden', !running);
            if (fill) fill.style.width = `${Math.max(0, Math.min(100, prg))}%`;
            if (text) text.textContent = running ? (msg || 'collecting…') : 'idle';
        } catch (e) {
            // silent; keep previous UI
            console.debug('status poll failed');
        }
    }

    function startStatusPolling() {
        pollStatus();
        if (statusTimer) clearInterval(statusTimer);
        statusTimer = setInterval(pollStatus, 10000);
    }

    function render() {
        const calEl = $('#calendar');
        if (!calEl) return;

        const calEvents = applyFilters(EVENTS);

        // Create or update calendar
        if (!calendar) {
            calendar = new FullCalendar.Calendar(calEl, {
                timeZone: 'Europe/Athens',
                locale: 'el',
                height: '100%',
                expandRows: true,
                initialView: 'dayGridMonth',
                headerToolbar: {
                    left: 'prev,next today',
                    center: 'title',
                    right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek'
                },
                events: calEvents,
                eventClick(info) {
                    info.jsEvent?.preventDefault?.();
                    openDrawer(info.event);
                },
                eventContent(arg) {
                    const p = (arg.event.extendedProps.platform || '').toLowerCase();
                    const inner = document.createElement('div');
                    // const badge = p === 'zoom' ? 'badge-zoom' : p === 'teams' ? 'badge-teams' : p === 'google' ? 'badge-google' : 'bg-slate-100 text-slate-700';
                    // inner.innerHTML = `<div class="truncate">${arg.event.title}</div><div class="mt-0.5 ${badge} badge">${p || 'other'}</div>`;
                    const map = {
                        zoom: 'bg-blue-100 text-blue-700',
                        teams: 'bg-purple-100 text-purple-700',
                        google: 'bg-green-100 text-green-700'
                    };
                    const badge = map[p] || 'bg-slate-100 text-slate-700';
                    inner.innerHTML = `<div class="truncate">${arg.event.title}</div><div class="mt-0.5 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${badge}">${p || 'other'}</div>`;
                    return {domNodes: [inner]};
                }
            });
            calendar.render();

            // Keep calendar sized correctly
            if ('ResizeObserver' in window) {
                const ro = new ResizeObserver(() => {
                    if (calendar) calendar.updateSize();
                });
                ro.observe(calEl);
            } else {
                window.addEventListener('resize', debounce(() => {
                    if (calendar) calendar.updateSize();
                }), {passive: true});
            }

            // Optional: expose for debugging
            window.calendar = calendar;
        } else {
            calendar.removeAllEvents();
            calendar.addEventSource(calEvents);
        }

        // Table
        const tbody = $('#rows');
        if (!tbody) return;
        const showNoDate = $('#showNoDate')?.checked;
        const tableSource = showNoDate ? rowsFromAll(ALL) : EVENTS;
        const filteredTable = applyFilters(tableSource);

        tbody.innerHTML = '';
        for (const ev of filteredTable.sort((a, b) => (new Date(a.start || 0)) - (new Date(b.start || 0)))) {
            const when = ev.start ? formatLocal(ev.start) : '<span class="text-slate-400 italic">no date</span>';
            const tr = document.createElement('tr');
            tr.className = 'border-b hover:bg-slate-50';
            tr.innerHTML = `
        <td class="py-2 pr-2 whitespace-nowrap">${when}</td>
        <td class="py-2 pr-2">${ev.title}</td>
        <td class="py-2 pr-2">${platformBadge((ev.extendedProps.platform || '').toLowerCase())}</td>
        <td class="py-2 pr-2">${ev.extendedProps.sender || ''}</td>
        <td class="py-2 pr-2">${ev.extendedProps.attendees || ''}</td>
        <td class="py-2 pr-2">${ev.extendedProps.link ? `<a class="text-blue-600 underline" href="${ev.extendedProps.link}" target="_blank">Join</a>` : ''}</td>
      `;
            tr.addEventListener('click', () => openDrawer({...ev, extendedProps: ev.extendedProps}));
            tbody.appendChild(tr);
        }
    }

    function getSelectedAccounts() {
        const ids = [];
        $$('#accountsList input[type="checkbox"]').forEach(cb => {
            if (cb.checked) ids.push(cb.getAttribute('data-account-id'));
        });
        return new Set(ids);
    }

    function openDrawer(ev) {
        const drawer = $('#drawer');
        const body = $('#drawer-body');
        if (!drawer || !body) return;

        body.innerHTML = `
      <div><span class="text-slate-500">Subject</span><div class="font-medium">${ev.extendedProps.subject || ev.title || ''}</div></div>
      <div class="grid grid-cols-2 gap-3">
        <div><span class="text-slate-500">Start</span><div class="font-medium">${ev.start ? formatLocal(ev.start) : '-'}</div></div>
        <div><span class="text-slate-500">Platform</span><div class="font-medium">${platformBadge((ev.extendedProps.platform || '').toLowerCase())}</div></div>
      </div>
      <div><span class="text-slate-500">From</span><div class="font-medium">${ev.extendedProps.sender || ''}</div></div>
      <div><span class="text-slate-500">Attendees</span><div class="font-medium whitespace-pre-wrap">${ev.extendedProps.attendees || ''}</div></div>
      <div><span class="text-slate-500">Account / Folder</span><div class="font-medium">${ev.extendedProps.account || ''} · ${ev.extendedProps.folder || ''}</div></div>
      <div class="pt-2 flex gap-2">
        ${ev.extendedProps.link ? `<a href="${ev.extendedProps.link}" target="_blank" class="rounded-xl bg-slate-900 text-white px-3 py-2 text-sm hover:bg-slate-800">Join</a>` : ''}
        ${ev.start ? `<a href="${googleCalendarUrl(ev)}" target="_blank" class="rounded-xl border px-3 py-2 text-sm hover:bg-slate-50">Add to Google Calendar</a>` : ''}
        ${ev.extendedProps.msg_id ? `<a href="/emails/by-mid/${encodeURIComponent(ev.extendedProps.msg_id)}/preview" target="_blank" class="rounded-xl border px-3 py-2 text-sm hover:bg-slate-50">Preview email</a>` : ''}
        ${ev.extendedProps.msg_id ? `<a href="/emails/by-mid/${encodeURIComponent(ev.extendedProps.msg_id)}/download" class="rounded-xl border px-3 py-2 text-sm hover:bg-slate-50">Download .eml</a>` : ''}
      </div>
    `;

        // Close buttons / backdrop
        $$('#drawer [data-close]').forEach(el => el.addEventListener('click', () => drawer.classList.add('hidden')));
        drawer.classList.remove('hidden');
    }


    async function loadAccounts() {
        try {
            const res = await fetch(API_ACCOUNTS);
            if (!res.ok) throw new Error(`Accounts fetch failed: ${res.status}`);
            const accounts = await res.json();
            renderAccountList(accounts);
        } catch (e) {
            console.error(e);
            document.getElementById("accountsList").innerHTML =
                `<li class="text-sm text-red-600 px-2">Failed to load accounts.</li>`;
        }
    }


    function renderAccountList(accounts) {
        const ul = $('#accountsList');
        if (!ul) return;
        if (!Array.isArray(accounts) || accounts.length === 0) {
            ul.innerHTML = `<li class="text-sm text-slate-500 px-2">No accounts.</li>`;
            return;
        }
        ul.innerHTML = accounts.map(acc => {
            const tsISO = lastScanISO(acc);
            const tsLabel = tsISO ? humanize(tsISO) : "—";
            return `
      <li class="px-2">
        <label class="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-slate-100">
          <input type="checkbox" class="accent-blue-600"
                 data-account-id="${escapeHtml(String(acc.id ?? ""))}"
                 checked />
          <span class="text-sm font-medium">${escapeHtml(acc.email ?? "")}</span>
          <span class="ml-auto text-xs text-slate-500" title="${tsISO ?? ""}">${tsLabel}</span>
        </label>
      </li>`;
        }).join("");
    }

// Επιλογή timestamp: ο νεότερος από full/incremental
    function lastScanISO(acc) {
        const t1 = acc?.last_incremental_parse_at;
        const t2 = acc?.last_full_parse_at;
        const iso = newestISO(t1, t2);
        return iso;
    }

    function newestISO(a, b) {
        if (!a && !b) return null;
        if (a && !b) return a;
        if (!a && b) return b;
        return (new Date(a) > new Date(b)) ? a : b;
    }

    function humanize(iso) {
        // local human-readable: π.χ. Πέμ, 21 Αυγ 2025, 10:42
        try {
            const d = new Date(iso);
            return d.toLocaleString(undefined, {
                weekday: "short",
                year: "numeric", month: "short", day: "2-digit",
                hour: "2-digit", minute: "2-digit"
            });
        } catch { return iso; }
    }

    function escapeHtml(s) {
        return String(s).replace(/[&<>"'`=\/]/g, c => ({
            "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;",
            "`":"&#96;", "=":"&#61;", "/":"&#47;"
        }[c]));
    }

    // Προαιρετικό: ένδειξη busy σε κουμπιά
    function toggleBusy(btn, on) {
        if (!btn) return;
        btn.disabled = !!on;
        btn.classList.toggle("opacity-60", !!on);
    }

    // ---------- Boot ----------
    function init() {

        // Start polling collector status immediately
        startStatusPolling();

        // Fetch data immediately
        fetchMeetings();

        // Tabs
        $$('.tab-btn').forEach(btn => btn.addEventListener('click', () => {
            $$('.tab-btn').forEach(b => b.classList.remove('bg-slate-900', 'text-white', 'active'));
            btn.classList.add('bg-slate-900', 'text-white', 'active');
            const tab = btn.getAttribute('data-tab');
            $('#calendar-card').classList.toggle('hidden', tab !== 'calendar');
            $('#table-card').classList.toggle('hidden', tab !== 'table');
        }));

        // Filters
        const q = $('#q');
        if (q) q.addEventListener('input', render);
        $$('.platform').forEach(cb => cb.addEventListener('change', render));
        const from = $('#from');
        if (from) from.addEventListener('change', render);
        const to = $('#to');
        if (to) to.addEventListener('change', render);
        const clear = $('#btn-clear');
        if (clear) clear.addEventListener('click', () => {
            if (q) q.value = '';
            $$('.platform').forEach(cb => cb.checked = true);
            if (from) from.value = '';
            if (to) to.value = '';
            $$('#accountsList input[type="checkbox"]').forEach(cb => cb.checked = true);
            render();
        });

        // Refresh
        const refresh = $('#btn-refresh');
        if (refresh) refresh.addEventListener('click', fetchMeetings);

        // Export visible
        const exportBtn = $('#btn-export');
        if (exportBtn) exportBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const filtered = applyFilters(EVENTS);
            downloadICS(filtered);
        });

        // Include messages without date (table only)
        const noDate = $('#showNoDate');
        if (noDate) noDate.addEventListener('change', render, {passive: true});
    }

    onReady(() => {
        // const btn = document.getElementById('btnRunFullParse');
        // if (!btn) return;
        // btn.addEventListener('click', async () => {
        //     e.preventDefault();
        //     if (!confirm('Run full parse for all accounts?')) return;
        //     try {
        //         const res = await fetch('/full-parse', {method: 'POST'});
        //         alert(res.ok ? 'Full parse started.' : 'Error starting full parse');
        //     } catch (e) {
        //         alert('Error starting full parse');
        //     }
        // });

        // Handle account form submit
        const form = document.getElementById('formAddAccount');
        if (form) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const data = Object.fromEntries(new FormData(form).entries());
                // cast αριθμούς/booleans
                data.imap_port = parseInt(data.imap_port || "993");
                data.imap_ssl = true; // μπορείς να βάλεις checkbox αν θες
                data.can_parse = true;
                data.enabled = true;

                try {
                    const res = await fetch('/api/v1/accounts', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(data)
                    });
                    if (res.ok) {
                        alert('Account saved!');
                        form.reset();
                    } else {
                        alert('Error: ' + res.status);
                    }
                } catch (err) {
                    alert('Request failed: ' + err);
                }
            });
        }

        // ---- Accounts panel ----
        window.addEventListener("DOMContentLoaded", () => {
            loadAccounts();
        });

        // ---- Header buttons
        document.getElementById("btnUpdate")?.addEventListener("click", async () => {
            const b = document.getElementById("btnUpdate");
            toggleBusy(b, true);
            try {
                // await fetch(API_UPDATE, { method: "POST" });

                await fetch(`${API_PARSE}?force_full=false`, { method: "POST" });

                // Μετά από update, κάνε refresh τα meetings
                await reloadMeetings?.();
            } catch (e) {
                console.error(e);
            } finally {
                toggleBusy(b, false);
            }
        });

        document.getElementById("btnFullParse")?.addEventListener("click", async () => {
            const b = document.getElementById("btnFullParse");
            if (!confirm("Run FULL parse for all accounts?")) return;
            toggleBusy(b, true);
            try {
                // await fetch(API_FULL, { method: "POST" });

                await fetch(`${API_PARSE}?force_full=true`, { method: "POST" });

                // Μετά από full-parse, κάνε refresh τα meetings
                await reloadMeetings?.();
            } catch (e) {
                console.error(e);
            } finally {
                toggleBusy(b, false);
            }
        });

        init();
    });
})();
