// (() => {
//     'use strict';
//
//     // ---------- Small helpers ----------
//     const $ = (sel, root = document) => root.querySelector(sel);
//     const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
//
//     // ---- API endpoints (προσαρμόζεις αν τα έχεις με άλλο path)
//     const API_ACCOUNTS = "api/v1/accounts"; // GET -> [{id,email,parse_enabled,last_full_parse_at,last_incremental_parse_at}, ...]
//     const API_PARSE    = "/api/v1/meetings/actions/parse";   // κοινό endpoint
//
//
//     const sidePanel = document.getElementById('sidePanel');
//     const appMain   = document.getElementById('appMain');
//     const btnToggle = document.getElementById('btnSideToggle');
//
//     function isDesktop() {
//         return window.matchMedia('(min-width: 1024px)').matches;
//     }
//
// // Όταν ανοίγει: σε desktop σπρώξε και στένεψε το main, σε mobile απλώς δείξε το panel πάνω απ’ όλα
//     function openSide() {
//         if (!sidePanel) return;
//         sidePanel.classList.remove('-translate-x-full');
//
//         if (appMain && isDesktop()) {
//             // 20rem = w-80 — σπρώχνουμε και μειώνουμε το πλάτος ώστε να ΜΗΝ βγαίνει από το viewport
//             appMain.classList.add('lg:ml-80');
//             appMain.classList.add('lg:w-[calc(100%-20rem)]');
//         }
//     }
//
// // Όταν κλείνει: επαναφορά main
//     function closeSide() {
//         if (!sidePanel) return;
//         sidePanel.classList.add('-translate-x-full');
//
//         if (appMain) {
//             appMain.classList.remove('lg:ml-80');
//             appMain.classList.remove('lg:w-[calc(100%-20rem)]');
//         }
//     }
//
// // Toggle με το κάτω-αριστερά κουμπί
//     btnToggle?.addEventListener('click', () => {
//         if (!sidePanel) return;
//         const hidden = sidePanel.classList.contains('-translate-x-full');
//         hidden ? openSide() : closeSide();
//     });
//
// // Responsive guard: αν αλλάξει το μέγεθος, διόρθωσε πλάτος/περιθώριο
//     window.addEventListener('resize', () => {
//         if (!sidePanel || !appMain) return;
//         const isOpen = !sidePanel.classList.contains('-translate-x-full');
//
//         if (isDesktop()) {
//             if (isOpen) {
//                 appMain.classList.add('lg:ml-80', 'lg:w-[calc(100%-20rem)]');
//             } else {
//                 appMain.classList.remove('lg:ml-80', 'lg:w-[calc(100%-20rem)]');
//             }
//         } else {
//             // Σε mobile ποτέ δεν σπρώχνουμε – το panel καλύπτει την οθόνη
//             appMain.classList.remove('lg:ml-80', 'lg:w-[calc(100%-20rem)]');
//         }
//     }, { passive: true });
//
//
//     function onReady(cb) {
//         if (document.readyState === 'loading') {
//             document.addEventListener('DOMContentLoaded', cb, {once: true});
//         } else {
//             cb();
//         }
//     }
//
//     function platformBadge(p) {
//         const base = "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium";
//         const map = {
//             zoom: "bg-blue-100 text-blue-700",
//             teams: "bg-purple-100 text-purple-700",
//             google: "bg-green-100 text-green-700",
//             other: "bg-slate-100 text-slate-700"
//         };
//         const k = (p || 'other').toLowerCase();
//         const label = k === 'google' ? 'Google' : k.charAt(0).toUpperCase() + k.slice(1);
//         return `<span class="${base} ${map[k] || map.other}">${label}</span>`;
//     }
//
//     // Incoming format: RFC 2822-like e.g. "Fri, 18 Jul 2025 11:00:00 +0300"
//     function toISO(dtStr) {
//         const d = new Date(dtStr);
//         return isNaN(d) ? null : d.toISOString();
//     }
//
//     function formatLocal(dtStr) {
//         const d = new Date(dtStr);
//         if (isNaN(d)) return '';
//         return d.toLocaleString([], {dateStyle: 'medium', timeStyle: 'short'});
//     }
//
//     function googleCalendarUrl(ev) {
//         // Build a Google Calendar template link (defaults to 60min duration if no end)
//         const start = new Date(ev.start);
//         const end = ev.extendedProps?.end ? new Date(ev.extendedProps.end) : new Date(start.getTime() + 60 * 60000);
//         const fmt = d => d.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
//         const text = encodeURIComponent(ev.title || 'Meeting');
//         const details = encodeURIComponent((ev.extendedProps?.link || '') + '\n' + (ev.extendedProps?.subject || ''));
//         const location = encodeURIComponent(ev.extendedProps?.platform || '');
//         return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${text}&dates=${fmt(start)}/${fmt(end)}&details=${details}&location=${location}`;
//     }
//
//     function downloadICS(events) {
//         const dtstamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
//         const lines = [
//             'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Meeting Collector//EN'
//         ];
//         for (const ev of events) {
//             const start = new Date(ev.start);
//             const end = ev.extendedProps?.end ? new Date(ev.extendedProps.end) : new Date(start.getTime() + 60 * 60000);
//             const fmt = d => d.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
//             lines.push(
//                 'BEGIN:VEVENT',
//                 `UID:${ev.id || crypto.randomUUID()}@meeting-collector`,
//                 `DTSTAMP:${dtstamp}`,
//                 `DTSTART:${fmt(start)}`,
//                 `DTEND:${fmt(end)}`,
//                 `SUMMARY:${(ev.title || '').replace(/\n/g, ' ')}`,
//                 `DESCRIPTION:${(ev.extendedProps?.link || '')}`,
//                 'END:VEVENT'
//             );
//         }
//         lines.push('END:VCALENDAR');
//         const blob = new Blob([lines.join('\r\n')], {type: 'text/calendar'});
//         const url = URL.createObjectURL(blob);
//         const a = document.createElement('a');
//         a.href = url;
//         a.download = 'meetings.ics';
//         a.click();
//         setTimeout(() => URL.revokeObjectURL(url), 5000);
//     }
//
//     // ---------- Data state ----------
//     let ALL = [];      // raw meetings from API
//     let EVENTS = [];   // transformed events with date & link
//     let calendar = null; // FullCalendar instance
//     let statusTimer = null;
//
//     function deriveTitle(m) {
//         const subject = m.msg_subject?.trim();
//         if (subject) return subject;
//         return (m.meet_platform || 'meeting').toUpperCase() + ' ' + (m.meet_id || '');
//     }
//
//     function transform(meetings) {
//         return meetings
//             .filter(m => /*!!m.meet_link &&*/ !!m.meet_date)
//             .map(m => ({
//                 id: m.meet_id,
//                 title: deriveTitle(m),
//                 start: toISO(m.meet_date),
//                 url: m.meet_link,
//                 extendedProps: {
//                     platform: m.meet_platform,
//                     subject: m.msg_subject,
//                     sender: m.msg_sender,
//                     attendees: m.meet_attendants || m.msg_attendants,
//                     account: m.msg_account,
//                     folder: m.msg_folder,
//                     link: m.meet_link,
//                     rawDate: m.meet_date,
//                     end: m.meet_end_date || null, // optional future field from API
//                     msg_id: m.msg_id || null
//                 }
//             }))
//             .filter(e => !!e.start);
//     }
//
//     function rowsFromAll(meetings) {
//         return meetings.map(m => ({
//             id: m.meet_id,
//             title: deriveTitle(m),
//             start: m.meet_date ? toISO(m.meet_date) : null,
//             url: m.meet_link,
//             extendedProps: {
//                 platform: m.meet_platform,
//                 subject: m.msg_subject,
//                 sender: m.msg_sender,
//                 attendees: m.meet_attendants || m.msg_attendants,
//                 account: m.msg_account,
//                 folder: m.msg_folder,
//                 link: m.meet_link,
//                 rawDate: m.meet_date,
//                 end: m.meet_end_date || null,
//                 msg_id: m.msg_id || null
//             }
//         }));
//     }
//
//     const accountCbs = $$('#accountsList input[type="checkbox"]');
//     const useAccountFilter = accountCbs.length > 0;         // μόνο αν έχουν φορτωθεί accounts
//     const selectedAccs = useAccountFilter ? getSelectedAccounts() : null;
//
//     function applyFilters(list) {
//         const qEl = $('#q');
//         const fromEl = $('#from');
//         const toEl = $('#to');
//         const q = qEl ? qEl.value.trim().toLowerCase() : '';
//         const plats = $$('.platform').filter(x => x.checked).map(x => x.value);
//         const from = fromEl && fromEl.value ? new Date(fromEl.value) : null;
//         const to = toEl && toEl.value ? new Date(toEl.value + 'T23:59:59') : null;
//
//         return list.filter(ev => {
//             // platform
//             if (plats.length && !plats.includes((ev.extendedProps.platform || '').toLowerCase())) return false;
//             // date range
//             const d = ev.start ? new Date(ev.start) : null;
//             if (from && d && d < from) return false;
//             if (to && d && d > to) return false;
//             // query
//             if (q) {
//                 const hay = `${ev.title} ${(ev.extendedProps.subject || '')} ${(ev.extendedProps.sender || '')} ${(ev.extendedProps.attendees || '')}`.toLowerCase();
//                 if (!hay.includes(q)) return false;
//             }
//             // --- Account filter ---
//             if (useAccountFilter) {
//                 // Αν δεν έχει επιλεγεί κανένας λογαριασμός → μην εμφανίζεις κανένα meeting
//                 if (selectedAccs.size === 0) return false;
//
//                 // Πάρε το account id/email από τα extendedProps
//                 const accKey =
//                     String(
//                         ev.extendedProps?.account_id ??
//                         ev.extendedProps?.accountId ??
//                         ev.extendedProps?.account ??
//                         ev.extendedProps?.email ??
//                         ''
//                     );
//
//                 // Αν το event έχει ταυτότητα account και ΔΕΝ είναι στη λίστα των επιλεγμένων → κόψ’ το
//                 if (accKey && !selectedAccs.has(accKey)) return false;
//             }
//             return true;
//         });
//     }
//
//     async function fetchMeetings() {
//         const status = $('#status');
//         if (status) status.textContent = 'loading…';
//         try {
//             const res = await fetch('/api/v1/meetings');
//             if (!res.ok) throw new Error('HTTP ' + res.status);
//             ALL = await res.json();
//             EVENTS = transform(ALL);
//         } catch (err) {
//             console.error(err);
//             ALL = [];
//             EVENTS = [];
//         } finally {
//             updateStatus();
//             render(); // always render even if 0 events
//         }
//     }
//
//     function updateStatus() {
//         const status = $('#status');
//         if (!status) return;
//         const total = ALL.length;
//         const withLink = ALL.filter(m => m.meet_link).length;
//         const withDate = ALL.filter(m => m.meet_date).length;
//         const withBoth = EVENTS.length;
//         status.textContent = `events ${withBoth} • links ${withLink}/${total} • dates ${withDate}/${total}`;
//     }
//
//     function updateStatusCounts() {
//         const status = $('#status');
//         if (!status) return;
//         const total = ALL.length;
//         const withLink = ALL.filter(m => m.meet_link).length;
//         const withDate = ALL.filter(m => m.meet_date).length;
//         const withBoth = EVENTS.length;
//         status.textContent = `events ${withBoth} • links ${withLink}/${total} • dates ${withDate}/${total}`;
//     }
//
//     const date = new Date();
//     const day = date.getDate();
//     const monthNames = ["ΙΑΝ", "ΦΕΒ", "ΜΑΡ", "ΑΠΡ", "ΜΑΪ", "ΙΟΥΝ", "ΙΟΥΛ", "ΑΥΓ", "ΣΕΠ", "ΟΚΤ", "ΝΟΕ", "ΔΕΚ"];
//
//     document.getElementById("calendarDay").textContent = day;
//     document.querySelector("#calendarIcon div:first-child").textContent = monthNames[date.getMonth()];
//
//     // ---- NEW: poll /status and toggle loader/progress ----
//     async function pollStatus() {
//         try {
//             const res = await fetch('/api/v1/meetings/status');
//             if (!res.ok) throw new Error('HTTP ' + res.status);
//             const s = await res.json();
//             const loader = $('#loader');
//             const bar = $('#progress');
//             const fill = $('#progress-bar');
//             const text = $('#loader-text');
//             const st = s?.collector?.status || 'idle';
//             const msg = s?.collector?.message || '';
//             const prg = Number(s?.collector?.progress ?? 0);
//
//             const running = st === 'running';
//             if (loader) loader.classList.toggle('hidden', !running);
//             if (bar) bar.classList.toggle('hidden', !running);
//             if (fill) fill.style.width = `${Math.max(0, Math.min(100, prg))}%`;
//             if (text) text.textContent = running ? (msg || 'collecting…') : 'idle';
//         } catch (e) {
//             // silent; keep previous UI
//             console.debug('status poll failed');
//         }
//     }
//
//     function startStatusPolling() {
//         pollStatus();
//         if (statusTimer) clearInterval(statusTimer);
//         statusTimer = setInterval(pollStatus, 10000);
//     }
//
//     function render() {
//         const calEl = $('#calendar');
//         if (!calEl) return;
//
//         const calEvents = applyFilters(EVENTS);
//
//         // Create or update calendar
//         if (!calendar) {
//             calendar = new FullCalendar.Calendar(calEl, {
//                 timeZone: 'Europe/Athens',
//                 locale: 'el',
//                 height: '100%',
//                 expandRows: true,
//                 initialView: 'dayGridMonth',
//                 headerToolbar: {
//                     left: 'prev,next today',
//                     center: 'title',
//                     right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek'
//                 },
//                 events: calEvents,
//                 eventClick(info) {
//                     info.jsEvent?.preventDefault?.();
//                     openDrawer(info.event);
//                 },
//                 eventContent(arg) {
//                     const p = (arg.event.extendedProps.platform || '').toLowerCase();
//                     const inner = document.createElement('div');
//                     // const badge = p === 'zoom' ? 'badge-zoom' : p === 'teams' ? 'badge-teams' : p === 'google' ? 'badge-google' : 'bg-slate-100 text-slate-700';
//                     // inner.innerHTML = `<div class="truncate">${arg.event.title}</div><div class="mt-0.5 ${badge} badge">${p || 'other'}</div>`;
//                     const map = {
//                         zoom: 'bg-blue-100 text-blue-700',
//                         teams: 'bg-purple-100 text-purple-700',
//                         google: 'bg-green-100 text-green-700'
//                     };
//                     const badge = map[p] || 'bg-slate-100 text-slate-700';
//                     inner.innerHTML = `<div class="truncate">${arg.event.title}</div><div class="mt-0.5 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${badge}">${p || 'other'}</div>`;
//                     return {domNodes: [inner]};
//                 }
//             });
//             calendar.render();
//
//             // Keep calendar sized correctly
//             if ('ResizeObserver' in window) {
//                 const ro = new ResizeObserver(() => {
//                     if (calendar) calendar.updateSize();
//                 });
//                 ro.observe(calEl);
//             } else {
//                 /*window.addEventListener('resize', debounce(() => {
//                     if (calendar) calendar.updateSize();
//                 }), {passive: true});*/
//
//                 window.addEventListener('resize', () => {
//                     if (!appMain || !sidePanel) return;
//                     const isOpen = !sidePanel.classList.contains('-translate-x-full');
//                     const isDesktop = window.matchMedia('(min-width: 1024px)').matches;
//                     if (isOpen) {
//                         isDesktop ? appMain.classList.add('lg:ml-80') : appMain.classList.remove('lg:ml-80');
//                     }
//                 }, { passive: true });
//
//             }
//
//             // Optional: expose for debugging
//             window.calendar = calendar;
//         } else {
//             calendar.removeAllEvents();
//             calendar.addEventSource(calEvents);
//         }
//
//         // Table
//         const tbody = $('#rows');
//         if (!tbody) return;
//         const showNoDate = $('#showNoDate')?.checked;
//         const tableSource = showNoDate ? rowsFromAll(ALL) : EVENTS;
//         const filteredTable = applyFilters(tableSource);
//
//         tbody.innerHTML = '';
//         for (const ev of filteredTable.sort((a, b) => (new Date(a.start || 0)) - (new Date(b.start || 0)))) {
//             const when = ev.start ? formatLocal(ev.start) : '<span class="text-slate-400 italic">no date</span>';
//             const tr = document.createElement('tr');
//             tr.className = 'border-b hover:bg-slate-50';
//             tr.innerHTML = `
//         <td class="py-2 pr-2 whitespace-nowrap">${when}</td>
//         <td class="py-2 pr-2">${ev.title}</td>
//         <td class="py-2 pr-2">${platformBadge((ev.extendedProps.platform || '').toLowerCase())}</td>
//         <td class="py-2 pr-2">${ev.extendedProps.sender || ''}</td>
//         <td class="py-2 pr-2">${ev.extendedProps.attendees || ''}</td>
//         <td class="py-2 pr-2">${ev.extendedProps.link ? `<a class="text-blue-600 underline" href="${ev.extendedProps.link}" target="_blank">Join</a>` : ''}</td>
//       `;
//             tr.addEventListener('click', () => openDrawer({...ev, extendedProps: ev.extendedProps}));
//             tbody.appendChild(tr);
//         }
//     }
//
//     function getSelectedAccounts() {
//         const ids = [];
//         $$('#accountsList input[type="checkbox"]').forEach(cb => {
//             if (cb.checked) ids.push(cb.getAttribute('data-account-id'));
//         });
//         return new Set(ids);
//     }
//
//     function openDrawer(ev) {
//         const drawer = $('#drawer');
//         const body = $('#drawer-body');
//         if (!drawer || !body) return;
//
//         body.innerHTML = `
//       <div><span class="text-slate-500">Subject</span><div class="font-medium">${ev.extendedProps.subject || ev.title || ''}</div></div>
//       <div class="grid grid-cols-2 gap-3">
//         <div><span class="text-slate-500">Start</span><div class="font-medium">${ev.start ? formatLocal(ev.start) : '-'}</div></div>
//         <div><span class="text-slate-500">Platform</span><div class="font-medium">${platformBadge((ev.extendedProps.platform || '').toLowerCase())}</div></div>
//       </div>
//       <div><span class="text-slate-500">From</span><div class="font-medium">${ev.extendedProps.sender || ''}</div></div>
//       <div><span class="text-slate-500">Attendees</span><div class="font-medium whitespace-pre-wrap">${ev.extendedProps.attendees || ''}</div></div>
//       <div><span class="text-slate-500">Account / Folder</span><div class="font-medium">${ev.extendedProps.account || ''} · ${ev.extendedProps.folder || ''}</div></div>
//       <div class="pt-2 flex gap-2">
//         ${ev.extendedProps.link ? `<a href="${ev.extendedProps.link}" target="_blank" class="rounded-xl bg-slate-900 text-white px-3 py-2 text-sm hover:bg-slate-800">Join</a>` : ''}
//         ${ev.start ? `<a href="${googleCalendarUrl(ev)}" target="_blank" class="rounded-xl border px-3 py-2 text-sm hover:bg-slate-50">Add to Google Calendar</a>` : ''}
//         ${ev.extendedProps.msg_id ? `<a href="/emails/by-mid/${encodeURIComponent(ev.extendedProps.msg_id)}/preview" target="_blank" class="rounded-xl border px-3 py-2 text-sm hover:bg-slate-50">Preview email</a>` : ''}
//         ${ev.extendedProps.msg_id ? `<a href="/emails/by-mid/${encodeURIComponent(ev.extendedProps.msg_id)}/download" class="rounded-xl border px-3 py-2 text-sm hover:bg-slate-50">Download .eml</a>` : ''}
//       </div>
//     `;
//
//         // Close buttons / backdrop
//         $$('#drawer [data-close]').forEach(el => el.addEventListener('click', () => drawer.classList.add('hidden')));
//         drawer.classList.remove('hidden');
//     }
//
//
//     async function loadAccounts() {
//         try {
//             const res = await fetch(API_ACCOUNTS);
//             if (!res.ok) throw new Error(`Accounts fetch failed: ${res.status}`);
//             const accounts = await res.json();
//             renderAccountList(accounts);
//         } catch (e) {
//             console.error(e);
//             document.getElementById("accountsList").innerHTML =
//                 `<li class="text-sm text-red-600 px-2">Failed to load accounts.</li>`;
//         }
//     }
//
//
//     function renderAccountList(accounts) {
//         const ul = $('#accountsList');
//         if (!ul) return;
//         if (!Array.isArray(accounts) || accounts.length === 0) {
//             ul.innerHTML = `<li class="text-sm text-slate-500 px-2">No accounts.</li>`;
//             return;
//         }
//         ul.innerHTML = accounts.map(acc => {
//             const tsISO = lastScanISO(acc);
//             const tsLabel = tsISO ? humanize(tsISO) : "—";
//             return `
//       <li class="px-2">
//         <label class="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-slate-100">
//           <input type="checkbox" class="accent-blue-600"
//                  data-account-id="${escapeHtml(String(acc.id ?? ""))}"
//                  checked />
//           <span class="text-sm font-medium">${escapeHtml(acc.email ?? "")}</span>
//           <span class="ml-auto text-xs text-slate-500" title="${tsISO ?? ""}">${tsLabel}</span>
//         </label>
//       </li>`;
//         }).join("");
//     }
//
// // Επιλογή timestamp: ο νεότερος από full/incremental
//     function lastScanISO(acc) {
//         const t1 = acc?.last_incremental_parse_at;
//         const t2 = acc?.last_full_parse_at;
//         const iso = newestISO(t1, t2);
//         return iso;
//     }
//
//     function newestISO(a, b) {
//         if (!a && !b) return null;
//         if (a && !b) return a;
//         if (!a && b) return b;
//         return (new Date(a) > new Date(b)) ? a : b;
//     }
//
//     function humanize(iso) {
//         // local human-readable: π.χ. Πέμ, 21 Αυγ 2025, 10:42
//         try {
//             const d = new Date(iso);
//             return d.toLocaleString(undefined, {
//                 weekday: "short",
//                 year: "numeric", month: "short", day: "2-digit",
//                 hour: "2-digit", minute: "2-digit"
//             });
//         } catch { return iso; }
//     }
//
//     function escapeHtml(s) {
//         return String(s).replace(/[&<>"'`=\/]/g, c => ({
//             "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;",
//             "`":"&#96;", "=":"&#61;", "/":"&#47;"
//         }[c]));
//     }
//
//     // Προαιρετικό: ένδειξη busy σε κουμπιά
//     function toggleBusy(btn, on) {
//         if (!btn) return;
//         btn.disabled = !!on;
//         btn.classList.toggle("opacity-60", !!on);
//     }
//
//     // ---------- Boot ----------
//     function init() {
//
//         // Start polling collector status immediately
//         startStatusPolling();
//
//         // Fetch data immediately
//         fetchMeetings();
//
//         // Tabs
//         $$('.tab-btn').forEach(btn => btn.addEventListener('click', () => {
//             $$('.tab-btn').forEach(b => b.classList.remove('bg-slate-900', 'text-white', 'active'));
//             btn.classList.add('bg-slate-900', 'text-white', 'active');
//             const tab = btn.getAttribute('data-tab');
//             $('#calendar-card').classList.toggle('hidden', tab !== 'calendar');
//             $('#table-card').classList.toggle('hidden', tab !== 'table');
//         }));
//
//         // Filters
//         const q = $('#q');
//         if (q) q.addEventListener('input', render);
//         $$('.platform').forEach(cb => cb.addEventListener('change', render));
//         const from = $('#from');
//         if (from) from.addEventListener('change', render);
//         const to = $('#to');
//         if (to) to.addEventListener('change', render);
//         const clear = $('#btn-clear');
//         if (clear) clear.addEventListener('click', () => {
//             if (q) q.value = '';
//             $$('.platform').forEach(cb => cb.checked = true);
//             if (from) from.value = '';
//             if (to) to.value = '';
//             $$('#accountsList input[type="checkbox"]').forEach(cb => cb.checked = true);
//             render();
//         });
//
//         // Refresh
//         const refresh = $('#btn-refresh');
//         if (refresh) refresh.addEventListener('click', fetchMeetings);
//
//         // Export visible
//         const exportBtn = $('#btn-export');
//         if (exportBtn) exportBtn.addEventListener('click', (e) => {
//             e.preventDefault();
//             const filtered = applyFilters(EVENTS);
//             downloadICS(filtered);
//         });
//
//         // Include messages without date (table only)
//         const noDate = $('#showNoDate');
//         if (noDate) noDate.addEventListener('change', render, {passive: true});
//     }
//
//     onReady(() => {
//          // Handle account form submit
//         const form = document.getElementById('formAddAccount');
//         if (form) {
//             form.addEventListener('submit', async (e) => {
//                 e.preventDefault();
//                 const data = Object.fromEntries(new FormData(form).entries());
//                 // cast αριθμούς/booleans
//                 data.imap_port = parseInt(data.imap_port || "993");
//                 data.imap_ssl = true; // μπορείς να βάλεις checkbox αν θες
//                 data.can_parse = true;
//                 data.enabled = true;
//
//                 try {
//                     const res = await fetch('/api/v1/accounts', {
//                         method: 'POST',
//                         headers: {'Content-Type': 'application/json'},
//                         body: JSON.stringify(data)
//                     });
//                     if (res.ok) {
//                         alert('Account saved!');
//                         form.reset();
//                     } else {
//                         alert('Error: ' + res.status);
//                     }
//                 } catch (err) {
//                     alert('Request failed: ' + err);
//                 }
//             });
//         }
//
//         // ---- Accounts panel ----
//         window.addEventListener("DOMContentLoaded", () => {
//             loadAccounts();
//         });
//
//         // ---- Header buttons
//         document.getElementById("btnUpdate")?.addEventListener("click", async () => {
//             const b = document.getElementById("btnUpdate");
//             toggleBusy(b, true);
//             try {
//                 // await fetch(API_UPDATE, { method: "POST" });
//
//                 await fetch(`${API_PARSE}?force_full=false`, { method: "POST" });
//
//                 // Μετά από update, κάνε refresh τα meetings
//                 await reloadMeetings?.();
//             } catch (e) {
//                 console.error(e);
//             } finally {
//                 toggleBusy(b, false);
//             }
//         });
//
//         document.getElementById("btnFullParse")?.addEventListener("click", async () => {
//             const b = document.getElementById("btnFullParse");
//             if (!confirm("Run FULL parse for all accounts?")) return;
//             toggleBusy(b, true);
//             try {
//                 // await fetch(API_FULL, { method: "POST" });
//
//                 await fetch(`${API_PARSE}?force_full=true`, { method: "POST" });
//
//                 // Μετά από full-parse, κάνε refresh τα meetings
//                 await reloadMeetings?.();
//             } catch (e) {
//                 console.error(e);
//             } finally {
//                 toggleBusy(b, false);
//             }
//         });
//
//         init();
//     });
// })();


(() => {
    'use strict';

    // ---------- Helpers ----------
    const $  = (sel, root = document) => root.querySelector(sel);
    const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));


    function onReady(cb) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', cb, { once: true });
        } else {
            cb();
        }
    }

    function escapeHtml(s) {
        return String(s).replace(/[&<>"'`=\/]/g, c => ({
            "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;",
            "`":"&#96;", "=":"&#61;", "/":"&#47;"
        }[c]));
    }

    function parseEmails(input) {
        if (Array.isArray(input)) {
            input = input.join(', ');
        }
        const s = String(input || '');
        // πιάσε μόνο καθαρά emails (αγνοεί ονόματα, quotes, <...>, κλπ.)
        const matches = s.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/ig) || [];
        // αφαίρεσε διπλότυπα, κράτα τη σειρά που εμφανίστηκαν
        const seen = new Set();
        const out = [];
        for (const m of matches) {
            if (!seen.has(m)) { seen.add(m); out.push(m); }
        }
        return out;
    }

    function toggleBusy(btn, on) {
        if (!btn) return;
        btn.disabled = !!on;
        btn.classList.toggle("opacity-60", !!on);
    }

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

    function toISO(dtStr) {
        const d = new Date(dtStr);
        return isNaN(d) ? null : d.toISOString();
    }

    function formatLocal(dtStr) {
        const d = new Date(dtStr);
        if (isNaN(d)) return '';
        return d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
    }

    function googleCalendarUrl(ev) {
        const start = new Date(ev.start);
        const end = ev.extendedProps?.end
            ? new Date(ev.extendedProps.end)
            : new Date(start.getTime() + 60 * 60000);
        const fmt = d => d.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
        const text = encodeURIComponent(ev.title || 'Meeting');
        const details = encodeURIComponent((ev.extendedProps?.link || '') + '\n' + (ev.extendedProps?.subject || ''));
        const location = encodeURIComponent(ev.extendedProps?.platform || '');
        return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${text}&dates=${fmt(start)}/${fmt(end)}&details=${details}&location=${location}`;
    }

    function icsEscape(s = '') {
        return String(s)
            .replace(/\\/g, '\\\\')
            .replace(/;/g,  '\\;')
            .replace(/,/g,  '\\,')
            .replace(/\r?\n/g, '\\n');
    }
    function icsFmt(d) {
        // UTC σε μορφή YYYYMMDDTHHMMSSZ
        return new Date(d).toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
    }
    function slug(s='') {
        return s.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'').slice(0,60);
    }

    /*function downloadICS(events) {
        const dtstamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
        const lines = ['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Meeting Collector//EN'];
        for (const ev of events) {
            const start = new Date(ev.start);
            const end = ev.extendedProps?.end ? new Date(ev.extendedProps.end) : new Date(start.getTime() + 60*60000);
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
        const blob = new Blob([lines.join('\r\n')], {type:'text/calendar'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'meetings.ics';
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 5000);
    }
*/
    // ΤΩΡΑ: δέχεται είτε array είτε single event. Προαιρετικό filename.
    function downloadICS(input, filename) {
        const events = Array.isArray(input) ? input : [input];
        const dtstamp = icsFmt(new Date());
        const lines = ['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Meeting Collector//EN','CALSCALE:GREGORIAN'];

        for (const ev of events) {
            const start = new Date(ev.start);
            const end = ev.extendedProps?.end ? new Date(ev.extendedProps.end)
                : new Date(start.getTime() + 60*60000);
            const uid = `${ev.id || (crypto.randomUUID && crypto.randomUUID()) || Math.random().toString(36).slice(2)}@meeting-collector`;
            const title = icsEscape(ev.title || '');
            const url   = (ev.extendedProps?.link || '').trim();

            lines.push(
                'BEGIN:VEVENT',
                `UID:${uid}`,
                `DTSTAMP:${dtstamp}`,
                `DTSTART:${icsFmt(start)}`,
                `DTEND:${icsFmt(end)}`,
                `SUMMARY:${title}`,
                url ? `URL:${icsEscape(url)}` : '',
                // Προαιρετικά άφησε και στο DESCRIPTION το link, βοηθάει σε μερικούς clients:
                url ? `DESCRIPTION:${icsEscape(url)}` : 'DESCRIPTION:',
                'END:VEVENT'
            );
        }

        lines.push('END:VCALENDAR');
        const ics = lines.filter(Boolean).join('\r\n');
        const blob = new Blob([ics], {type:'text/calendar'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;

        // default filename
        if (!filename) {
            if (events.length === 1) {
                const ev = events[0];
                const when = ev.start ? new Date(ev.start) : new Date();
                const y = when.getFullYear();
                const m = String(when.getMonth()+1).padStart(2,'0');
                const d = String(when.getDate()).padStart(2,'0');
                a.download = `meeting-${d}_${m}_${y}-${slug(ev.title || 'event')}.ics`;
            } else {
                a.download = 'collected-meetings-${d}_${m}_${y}.ics';
            }
        } else {
            a.download = filename;
        }

        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 3000);
    }

    // ---------- UI state ----------
    const sidePanel = document.getElementById('sidePanel');
    const appMain   = document.getElementById('appMain');
    const btnToggle = document.getElementById('btnSideToggle');

    function isDesktop() {
        return window.matchMedia('(min-width: 1024px)').matches;
    }

    function openSide() {
        if (!sidePanel) return;
        sidePanel.classList.remove('-translate-x-full');
        if (appMain && isDesktop()) {
            appMain.classList.add('lg:ml-80','lg:w-[calc(100%-20rem)]');
        }
    }

    function closeSide() {
        if (!sidePanel) return;
        sidePanel.classList.add('-translate-x-full');
        if (appMain) {
            appMain.classList.remove('lg:ml-80','lg:w-[calc(100%-20rem)]');
        }
    }

    btnToggle?.addEventListener('click', () => {
        if (!sidePanel) return;
        const hidden = sidePanel.classList.contains('-translate-x-full');
        hidden ? openSide() : closeSide();
    });

    window.addEventListener('resize', () => {
        if (!sidePanel || !appMain) return;
        const isOpen = !sidePanel.classList.contains('-translate-x-full');
        if (isDesktop()) {
            if (isOpen) {
                appMain.classList.add('lg:ml-80','lg:w-[calc(100%-20rem)]');
            } else {
                appMain.classList.remove('lg:ml-80','lg:w-[calc(100%-20rem)]');
            }
        } else {
            appMain.classList.remove('lg:ml-80','lg:w-[calc(100%-20rem)]');
        }
    }, { passive:true });

    // ---------- Data state ----------
    let ALL = [];
    let EVENTS = [];
    let calendar = null;
    let statusTimer = null;

    function deriveTitle(m) {
        const subject = m.msg_subject?.trim();
        if (subject) return subject;
        return (m.meet_platform || 'meeting').toUpperCase() + ' ' + (m.meet_id || '');
    }

    function transform(meetings) {
        return meetings
            .filter(m => !!m.meet_date)
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
                    end: m.meet_end_date || null,
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

    // ---------- Filters ----------
    /*function getSelectedAccounts() {
        const ids = [];
        $$('#accountsList input[type="checkbox"]').forEach(cb => {
            if (cb.checked) ids.push(cb.getAttribute('data-account-id'));
        });
        return new Set(ids);
    }*/

    function getSelectedAccounts() {
        const keys = [];
        $$('#accountsList input[type="checkbox"]').forEach(cb => {
            if (!cb.checked) return;
            const mail = cb.getAttribute('data-account-key') || cb.getAttribute('data-account-email');
            if (mail) { keys.push(String(mail).trim()); return; }  // <- χωρίς lowercase
            const label = cb.closest('label');
            const el = label?.querySelector('.text-sm.font-medium');
            const text = el?.textContent?.trim();
            if (text) keys.push(text); // <- χωρίς lowercase
        });
        return new Set(keys);
    }


    // OPTIONAL: μόνο για να το καλείς από το console
    if (typeof window !== 'undefined') window.getSelectedAccounts = getSelectedAccounts;


    function applyFilters(list) {
        const qEl = $('#q');
        const fromEl = $('#from');
        const toEl = $('#to');
        const q = qEl ? qEl.value.trim().toLowerCase() : '';
        const plats = $$('.platform').filter(x => x.checked).map(x => x.value);
        const from = fromEl && fromEl.value ? new Date(fromEl.value) : null;
        const to = toEl && toEl.value ? new Date(toEl.value + 'T23:59:59') : null;

        const accountCbs = $$('#accountsList input[type="checkbox"]');
        const useAccountFilter = accountCbs.length > 0;
        const selectedAccs = useAccountFilter ? getSelectedAccounts() : null;

        return list.filter(ev => {
            // platform
            if (plats.length && !plats.includes((ev.extendedProps.platform || '').toLowerCase())) return false;
            // date range
            const d = ev.start ? new Date(ev.start) : null;
            if (from && d && d < from) return false;
            if (to && d && d > to) return false;
            // query
            if (q) {
                const hay = `${ev.title} ${(ev.extendedProps.subject||'')} ${(ev.extendedProps.sender||'')} ${(ev.extendedProps.attendees||'')}`.toLowerCase();
                if (!hay.includes(q)) return false;
            }

            if (useAccountFilter) {
                if (selectedAccs.size === 0) return false;
                const accKey = String(
                    ev.extendedProps?.account_id ??
                    ev.extendedProps?.accountId ??
                    ev.extendedProps?.account ??
                    ev.extendedProps?.email ?? ''
                );
                if (accKey && !selectedAccs.has(accKey)) return false;
            }

            /*if (useAccountFilter) {
                if (selectedAccs.size === 0) return false;  // αν δεν έχεις διαλέξει account -> τίποτα
                const evEmail = String(ev.extendedProps?.account || ''); // ΟΠΩΣ ΕΡΧΕΤΑΙ
                if (!evEmail) return false;
                if (!selectedAccs.has(evEmail)) return false;
            }*/

            return true;
        });
    }

    // ---------- Fetch & Status ----------
    const API_ACCOUNTS = "api/v1/accounts";
    const API_PARSE    = "/api/v1/meetings/actions/parse";

    async function fetchMeetings() {
        const status = $('#status');
        if (status) status.textContent = 'loading…';
        try {
            const res = await fetch('/api/v1/meetings/db');
            if (!res.ok) throw new Error('HTTP ' + res.status);
            ALL = await res.json();
            EVENTS = transform(ALL);
            window.EVENTS = EVENTS;
        } catch (err) {
            console.error(err);
            ALL = []; EVENTS = [];
        } finally {
            updateStatus();
            render();
        }
    }

    // function updateStatus() {
    //     const status = $('#status');
    //     if (!status) return;
    //     const total = ALL.length;
    //     const withLink = ALL.filter(m => m.meet_link).length;
    //     const withDate = ALL.filter(m => m.meet_date).length;
    //     const withBoth = EVENTS.length;
    //     status.textContent = `events ${withBoth} • links ${withLink}/${total} • dates ${withDate}/${total}`;
    // }

    function updateStatus() {
        const el = $('#status');
        if (!el) return;

        const total   = ALL.length;
        const links   = ALL.filter(m => m.meet_link).length;
        const dates   = ALL.filter(m => m.meet_date).length;
        const eventsN = EVENTS.length;

        el.classList.add('status-chips');
        el.innerHTML = `
    <span class="chip events"><span class="dot"></span>events <b>${eventsN}</b></span>
    <span class="chip links"><span class="dot"></span>links <b>${links}/${total}</b></span>
    <span class="chip dates"><span class="dot"></span>dates <b>${dates}/${total}</b></span>
  `;
    }




    // async function pollStatus() {
    //     try {
    //         const res = await fetch('/api/v1/meetings/status');
    //         if (!res.ok) throw new Error('HTTP ' + res.status);
    //         const s = await res.json();
    //         const loader = $('#loader');
    //         const bar = $('#progress');
    //         const fill = $('#progress-bar');
    //         const text = $('#loader-text');
    //         const st = s?.collector?.status || 'idle';
    //         const msg = s?.collector?.message || '';
    //         const prg = Number(s?.collector?.progress ?? 0);
    //         const running = st === 'running';
    //         if (loader) loader.classList.toggle('hidden', !running);
    //         if (bar) bar.classList.toggle('hidden', !running);
    //         if (fill) fill.style.width = `${Math.max(0, Math.min(100, prg))}%`;
    //         if (text) text.textContent = running ? (msg || 'collecting…') : 'idle';
    //     } catch {
    //         console.debug('status poll failed');
    //     }
    // }

    async function pollStatus() {
        try {
            const res = await fetch('/api/v1/meetings/status');
            if (!res.ok) throw new Error('HTTP ' + res.status);
            const s = await res.json();

            const st  = s?.collector?.status || 'idle';
            const msg = s?.collector?.message || '';
            const prg = Number(s?.collector?.progress ?? 0);
            const running = st === 'running';

            // --- παλιά στοιχεία (αν τα κρατάς ακόμη)
            const loader = $('#loader');
            const bar = $('#progress');
            const fill = $('#progress-bar');
            const text = $('#loader-text');
            if (loader) loader.classList.toggle('hidden', !running);
            if (bar) bar.classList.toggle('hidden', !running);
            if (fill) fill.style.width = `${Math.max(0, Math.min(100, prg))}%`;
            if (text) text.textContent = running ? (msg || 'collecting…') : 'idle';

            // --- header thin loader binding
            if (running) {
                startHeaderLoading(_loaderColor);
            } else if (_holdUntilIdle) {
                hideHeaderLoadingNow();
            }

            // --- compact sidebar status (αν έχεις βάλει το UI)
            const dot = document.getElementById('sideStatusDot');
            const txt = document.getElementById('sideStatusText');
            const pct = document.getElementById('sideStatusPct');
            const bar2 = document.getElementById('sideStatusBar');
            if (dot && txt && pct && bar2) {
                if (running) {
                    dot.classList.remove('bg-slate-400','bg-red-500');
                    dot.classList.add('bg-blue-600','is-running');
                    txt.textContent = msg || 'Working…';
                    pct.textContent = `${Math.max(0, Math.min(100, prg))}%`;
                    bar2.style.width = `${Math.max(0, Math.min(100, prg))}%`;
                } else if (st === 'error') {
                    dot.classList.remove('bg-slate-400','bg-blue-600','is-running');
                    dot.classList.add('bg-red-500');
                    txt.textContent = msg || 'Error';
                    pct.textContent = '';
                    bar2.style.width = '0%';
                } else {
                    dot.classList.remove('bg-blue-600','bg-red-500','is-running');
                    dot.classList.add('bg-slate-400');
                    txt.textContent = 'Idle';
                    pct.textContent = '';
                    bar2.style.width = '0%';
                }
            }
        } catch {
            console.debug('status poll failed');
        }
    }


 /*   async function pollStatus() {
        // === Compact sidebar status ===
        const dot = document.getElementById('sideStatusDot');
        const txt = document.getElementById('sideStatusText');
        const pct = document.getElementById('sideStatusPct');
        const bar2 = document.getElementById('sideStatusBar');

        if (dot && txt && pct && bar2) {
            if (running) {
                // χρώματα κατάστασης
                dot.classList.remove('bg-slate-400', 'bg-red-500');
                dot.classList.add('bg-blue-600', 'is-running');

                txt.textContent = msg || 'Working…';
                pct.textContent = `${Math.max(0, Math.min(100, prg))}%`;
                bar2.style.width = `${Math.max(0, Math.min(100, prg))}%`;
            } else if (st === 'error') {
                dot.classList.remove('bg-slate-400', 'bg-blue-600', 'is-running');
                dot.classList.add('bg-red-500');
                txt.textContent = msg || 'Error';
                pct.textContent = '';
                bar2.style.width = '0%';
            } else {
                // idle
                dot.classList.remove('bg-blue-600', 'bg-red-500', 'is-running');
                dot.classList.add('bg-slate-400');
                txt.textContent = 'Idle';
                pct.textContent = '';
                bar2.style.width = '0%';
            }
        }

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

            // >>> Header thin loader binding <<<
            if (running) {
                // Βεβαιώσου ότι ο header-loader είναι ορατός με το τρέχον χρώμα trigger
                startHeaderLoading(_loaderColor);
            } else {
                // Μόνο όταν το backend δηλώσει idle... σβήσε τον loader,
                // αλλά αν δεν είχαμε δώσει "κρατάμε μέχρι idle", απόφυγε τρεμόπαιγμα
                if (_holdUntilIdle) hideHeaderLoadingNow();
            }
        } catch {
            console.debug('status poll failed');
        }
    }*/


    function startStatusPolling() {
        pollStatus();
        if (statusTimer) clearInterval(statusTimer);
        statusTimer = setInterval(pollStatus, 2000);
    }

    // ---------- Rendering ----------
    function render() {
        const calEl = $('#calendar');
        if (!calEl) return;
        const calEvents = applyFilters(EVENTS);

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
                    const p = (arg.event.extendedProps.platform||'').toLowerCase();
                    const inner = document.createElement('div');
                    const map = {
                        zoom: 'bg-blue-100 text-blue-700',
                        teams: 'bg-purple-100 text-purple-700',
                        google: 'bg-green-100 text-green-700'
                    };
                    const badge = map[p] || 'bg-slate-100 text-slate-700';
                    inner.innerHTML = `<div class="truncate">${arg.event.title}</div>
                             <div class="mt-0.5 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${badge}">${p||'other'}</div>`;
                    return { domNodes: [inner] };
                }
            });
            calendar.render();
            setTimeout(() => calendar?.updateSize(), 0);  // ensure first sizing
            if ('ResizeObserver' in window) {
                const ro = new ResizeObserver(() => calendar?.updateSize());
                ro.observe(calEl);
            }
            window.calendar = calendar;
        } else {
            calendar.removeAllEvents();
            calendar.addEventSource(calEvents);
        }

        const tbody = $('#rows');
        if (!tbody) return;
        const showNoDate = $('#showNoDate')?.checked;
        const tableSource = showNoDate ? rowsFromAll(ALL) : EVENTS;
        const filteredTable = applyFilters(tableSource);
        tbody.innerHTML = '';
        for (const ev of filteredTable.sort((a,b)=> (new Date(a.start||0)) - (new Date(b.start||0)))) {
            const when = ev.start ? formatLocal(ev.start) : '<span class="text-slate-400 italic">no date</span>';
            const tr = document.createElement('tr');
            tr.className = 'border-b hover:bg-slate-50';
            tr.innerHTML = `
        <td class="py-2 pr-2 whitespace-nowrap">${when}</td>
        <td class="py-2 pr-2">${ev.title}</td>
        <td class="py-2 pr-2">${platformBadge((ev.extendedProps.platform||'').toLowerCase())}</td>
        <td class="py-2 pr-2">${ev.extendedProps.sender||''}</td>
        <td class="py-2 pr-2">${ev.extendedProps.attendees||''}</td>
        <td class="py-2 pr-2">${ev.extendedProps.link ? `<a class="text-blue-600 underline" href="${ev.extendedProps.link}" target="_blank">Join</a>`:''}</td>`;
            tr.addEventListener('click',()=>openDrawer({...ev,extendedProps:ev.extendedProps}));
            tbody.appendChild(tr);
        }
    }

    function openDrawer(ev) {
        const drawer = $('#drawer');
        const body = $('#drawer-body');
        if (!drawer || !body) return;
        body.innerHTML = `
        <div><span class="text-slate-500">Account</span><div class="font-medium">${ev.extendedProps.account||''}</div></div>
        <div><span class="text-slate-500">Folder</span><div class="font-medium">${ev.extendedProps.folder||''}</div></div>
        <div><span class="text-slate-500">From</span><div class="font-medium">${ev.extendedProps.sender||''}</div></div>
        <div><span class="text-slate-500">Subject</span><div class="font-medium">${ev.extendedProps.subject||ev.title||''}</div></div>
        <div class="grid grid-cols-2 gap-3">
            <div><span class="text-slate-500">Start</span><div class="font-medium">${ev.start?formatLocal(ev.start):'-'}</div></div>
            <div><span class="text-slate-500">Platform</span><div class="font-medium">${platformBadge((ev.extendedProps.platform||'').toLowerCase())}</div></div>
        </div>
        <!--<div><span class="text-slate-500">Attendees</span><div class="font-medium whitespace-pre-wrap">${ev.extendedProps.attendees||''}</div></div>-->
        <div><span class="text-slate-500">Attendees</span>${renderAttendeesList(ev.extendedProps.attendees)}</div>


        <div class="pt-2 flex gap-2">
            ${ev.extendedProps.link?`<a href="${ev.extendedProps.link}" target="_blank" class="rounded-xl bg-slate-900 text-white px-3 py-2 text-sm hover:bg-slate-800">Join</a>`:''}
            ${ev.start?`<a href="${googleCalendarUrl(ev)}" target="_blank" class="rounded-xl border px-3 py-2 text-sm hover:bg-slate-50">Add to Google Calendar</a>`:''}
            ${ev.extendedProps.msg_id?`<a href="/emails/by-mid/${encodeURIComponent(ev.extendedProps.msg_id)}/preview" target="_blank" class="rounded-xl border px-3 py-2 text-sm hover:bg-slate-50">Preview email</a>`:''}
            ${ev.extendedProps.msg_id?`<a href="/emails/by-mid/${encodeURIComponent(ev.extendedProps.msg_id)}/download" class="rounded-xl border px-3 py-2 text-sm hover:bg-slate-50">Download .eml</a>`:''}
            <button id="btn-export-ics-one" class="rounded-xl border px-3 py-2 text-sm hover:bg-slate-50">Download .ics</button>
        </div>
        `;
        $$('#drawer [data-close]').forEach(el => el.addEventListener('click', () => drawer.classList.add('hidden')));
        // listener για single export
        $('#btn-export-ics-one')?.addEventListener('click', (e) => {
            e.preventDefault();
            downloadICS(ev);        // ✅ single event (η downloadICS πλέον το δέχεται)
        });

        drawer.classList.remove('hidden');
    }

    function renderAttendeesList(attendees) {
        const emails = parseEmails(attendees);
        if (emails.length === 0) {
            return `<div class="text-slate-400 text-sm">—</div>`;
        }
        return `
    <ul class="mt-1 space-y-1">
      ${emails.map(e => `
        <li>
          <a href="mailto:${e}" class="text-blue-600 underline hover:text-blue-700">${escapeHtml(e)}</a>
        </li>
      `).join('')}
    </ul>`;
    }

    // ---------- Accounts ----------
    async function loadAccounts() {
        try {
            const res = await fetch(API_ACCOUNTS);
            if (!res.ok) throw new Error(`Accounts fetch failed: ${res.status}`);
            const accounts = await res.json();
            renderAccountList(accounts);
            render();
        } catch (e) {
            console.error(e);
            document.getElementById("accountsList").innerHTML =
                `<li class="text-sm text-red-600 px-2">Failed to load accounts.</li>`;
        }
    }

    /*function renderAccountList(accounts) {
        const ul = $('#accountsList');
        if (!ul) return;
        if (!Array.isArray(accounts) || accounts.length===0) {
            ul.innerHTML = `<li class="text-sm text-slate-500 px-2">No accounts.</li>`;
            return;
        }
        ul.innerHTML = accounts.map(acc => {
            const tsISO = lastScanISO(acc);
            const tsLabel = tsISO ? humanize(tsISO) : "—";
            return `
        <li class="px-2">
          <label class="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-slate-100">
            <!--<input type="checkbox" class="accent-blue-600"
                   data-account-id="${escapeHtml(String(acc.id ?? ""))}" checked /> -->
                   <input type="checkbox" class="accent-blue-600"
       data-account-key="${escapeHtml(acc.email ?? "")}"
       data-account-id="${escapeHtml(String(acc.id ?? ""))}"
       checked />
            <span class="text-sm font-medium">${escapeHtml(acc.email ?? "")}</span>
            <span class="ml-auto text-xs text-slate-500" title="${tsISO ?? ""}">${tsLabel}</span>
          </label>
        </li>`;
        }).join("");
    }*/

    // --- Helpers ---
    const MONTH_ABBR = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

    function formatAccDate(iso) {
        if (!iso) return "—";
        const d = new Date(iso);
        if (isNaN(d)) return "—";
        const dd = String(d.getDate()).padStart(2, "0");
        const mon = MONTH_ABBR[d.getMonth()];
        const yy = String(d.getFullYear()).slice(-2);
        const hh = String(d.getHours()).padStart(2, "0");
        const mm = String(d.getMinutes()).padStart(2, "0");
        return `${dd}/${mon}/${yy}-${hh}:${mm}`;
    }

    function renderAccountItem(acc) {
        const fullISO = acc?.last_full_parse_at ?? null;
        const incISO  = acc?.last_incremental_parse_at ?? null;

        const fullLabel = formatAccDate(fullISO);
        const incLabel  = formatAccDate(incISO);

        const email = (acc.email || acc.address || "").trim();

        return `
            <li class="px-2 py-1.5">
              <label class="flex items-start gap-2 rounded-md px-2 py-1.5 hover:bg-slate-100">
                <input type="checkbox" class="w-4 h-4 accent-blue-600 mt-0.5"
                       data-account-id="${String(acc.id ?? "")}"
                       checked />
                <div class="min-w-0 flex-1">
                  <div class="text-sm font-medium truncate">${escapeHtml(email)}</div>
            
                  <!-- Οι δύο ημερομηνίες κάτω από το email (στοίχιση με το header) -->
                  <div class="mt-0.5 grid grid-cols-2 text-xs text-slate-500">
                    <span title="${fullISO ?? ""}">${fullLabel}</span>
                    <span title="${incISO ?? ""}">${incLabel}</span>
                  </div>
                </div>
              </label>
            </li>`;
    }

    /*function renderAccountList(accounts) {
        const ul = $('#accountsList');
        if (!ul) return;
        if (!Array.isArray(accounts) || accounts.length===0) {
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
                data-account-key="${escapeHtml((acc.email || acc.address || '').trim())}"  checked />

          <span class="text-sm font-medium">${escapeHtml(acc.email ?? "")}</span>
          <span class="ml-auto text-xs text-slate-500" title="${tsISO ?? ""}">${tsLabel}</span>
        </label>
      </li>`;
        }).join("");
    }*/

    // --- Renderer ---
    function renderAccountList(accounts) {
        const ul = $('#accountsList');
        const hdr = $('#accColsHeader');
        if (!ul || !hdr) return;

        ul.style.marginLeft = '-12pt';

        if (!Array.isArray(accounts) || accounts.length === 0) {
            hdr.classList.add('hidden');
            ul.innerHTML = `<li class="text-sm text-slate-500 px-2">No accounts.</li>`;
            return;
        }

        hdr.classList.remove('hidden');
        ul.innerHTML = accounts.map(renderAccountItem).join('');
    }




    function lastScanISO(acc) {
        const t1 = acc?.last_incremental_parse_at;
        const t2 = acc?.last_full_parse_at;
        return newestISO(t1,t2);
    }
    function newestISO(a,b) {
        if (!a&&!b) return null;
        if (a&&!b) return a;
        if (!a&&b) return b;
        return (new Date(a) > new Date(b)) ? a : b;
    }
    function humanize(iso) {
        try {
            const d = new Date(iso);
            return d.toLocaleString(undefined,{
                weekday:"short",year:"numeric",month:"short",day:"2-digit",
                hour:"2-digit",minute:"2-digit"
            });
        } catch { return iso; }
    }

    // --- Header loader state (color decided by trigger) ---
    let _loaderCount = 0;
    let _holdUntilIdle = false;         // κρατάμε το loader μέχρι να γίνει idle το backend
    let _loaderColor = 'dark';          // 'dark' | 'blue' | 'orange'

    function startHeaderLoading(color = 'dark') {
        _loaderColor = color;
        const host = document.getElementById('headerLoader');
        if (!host) return;
        _loaderCount++;
        host.classList.remove('hidden', 'dark', 'blue', 'orange');
        host.classList.add(_loaderColor);
    }

    function hideHeaderLoadingNow() {
        const host = document.getElementById('headerLoader');
        if (!host) return;
        _loaderCount = 0;
        _holdUntilIdle = false;
        host.classList.add('hidden');
        host.classList.remove('dark', 'blue', 'orange');
    }

    function stopHeaderLoading() {
        const host = document.getElementById('headerLoader');
        if (!host) return;
        _loaderCount = Math.max(0, _loaderCount - 1);
        if (_loaderCount === 0) hideHeaderLoadingNow();
    }

    function setupResponsiveHeaderMenu() {
        const actions   = document.getElementById('headerActions');
        const account   = document.getElementById('accountNav');
        const rightWrap = document.getElementById('headerRight') || (actions && actions.parentElement);
        const btn       = document.getElementById('btnHeaderMenu');

        const panel     = document.getElementById('headerMenuPanel');
        const content   = document.getElementById('headerMenuContent');

        // Αν λείπει κάτι, μην κάνεις τίποτα — και σιγουρέψου ότι φαίνονται.
        if (!actions || !account) return;
        actions.classList.remove('hidden');
        account.classList.remove('hidden');
        if (!rightWrap || !btn || !panel || !content) return;

        const originalParent = rightWrap;
        let inMenu = false;

        const isMobile = () => window.innerWidth < 768;

        function openMenu() {
            if (!inMenu) {
                content.appendChild(actions);
                content.appendChild(account);
                inMenu = true;
            }
            actions.classList.remove('hidden');
            account.classList.remove('hidden');
            panel.classList.remove('hidden');
        }

        function closeMenu() {
            panel.classList.add('hidden');
        }

        function restoreToHeader() {
            if (!inMenu) return;
            // Επιστροφή ΠΡΙΝ το hamburger (ώστε να μένουν δεξιά)
            originalParent.insertBefore(actions, btn);
            originalParent.insertBefore(account, btn);
            inMenu = false;
        }

        function applyVisibility() {
            // Αν δεν υπάρχει hamburger/panel, κράτα τα πάντα όπως είναι (φαίνονται)
            if (!btn || !panel || !content) {
                actions.classList.remove('hidden');
                account.classList.remove('hidden');
                return;
            }

            if (isMobile()) {
                // Κλείσε panel για καθαρή εκκίνηση
                closeMenu();

                // ΣΕ MOBILE: κρύψε τα στο header (θα φανούν μέσα στο panel όταν πατηθεί)
                actions.classList.add('hidden');
                account.classList.add('hidden');

                // Αν είχαν μείνει μέσα στο panel από πριν, γύρισέ τα στο header αλλά κρατώντας τα κρυφά
                if (inMenu) {
                    restoreToHeader();
                    actions.classList.add('hidden');
                    account.classList.add('hidden');
                }

                // Το hamburger πρέπει να φαίνεται σε mobile
                btn.classList.remove('hidden');

            } else {
                // ΣΕ DESKTOP: όλα επιστρέφουν στο header και είναι ορατά
                closeMenu();
                restoreToHeader();
                actions.classList.remove('hidden');
                account.classList.remove('hidden');

                // Το hamburger κρύβεται σε desktop (έχεις ήδη md:hidden στο HTML; άσε και αυτό για σιγουριά)
                btn.classList.add('hidden');
            }
        }

        // Toggle
        btn.addEventListener('click', () => {
            if (panel.classList.contains('hidden')) {
                if (!inMenu) {
                    content.appendChild(actions);
                    content.appendChild(account);
                    inMenu = true;
                }
                actions.classList.remove('hidden');
                account.classList.remove('hidden');
                panel.classList.remove('hidden');
            } else {
                closeMenu();
            }
        });

        // Κλείσιμο εκτός panel
        document.addEventListener('click', (e) => {
            if (panel.classList.contains('hidden')) return;
            if (!panel.contains(e.target) && !btn.contains(e.target)) closeMenu();
        }, true);

        // Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeMenu();
        });

        // Resize (debounced)
        function onResize() {
            clearTimeout(onResize._t);
            onResize._t = setTimeout(applyVisibility, 80);
        }
        window.addEventListener('resize', onResize, { passive: true });

        // Πρώτη εφαρμογή
        applyVisibility();
    }






    // ---------- Boot ----------
    function init() {
        startStatusPolling();
        fetchMeetings();

        const date = new Date();
        const day = date.getDate();
        const monthNames = ["ΙΑΝ", "ΦΕΒ", "ΜΑΡ", "ΑΠΡ", "ΜΑΪ", "ΙΟΥΝ", "ΙΟΥΛ", "ΑΥΓ", "ΣΕΠ", "ΟΚΤ", "ΝΟΕ", "ΔΕΚ"];

        document.getElementById("calendarDay").textContent = day;
        document.querySelector("#calendarIcon div:first-child").textContent = monthNames[date.getMonth()];

        // Delegated listeners: πιάνουν το checkbox όπου κι αν είναι στο DOM
        document.addEventListener('change', (e) => {
            if (e.target && e.target.id === 'showNoDate') render();
        }, { capture: true });

        document.addEventListener('input', (e) => {
            if (e.target && e.target.id === 'showNoDate') render();
        }, { capture: true });


        /*$$('.tab-btn').forEach(btn => btn.addEventListener('click', () => {
            $$('.tab-btn').forEach(b => b.classList.remove('bg-slate-900','text-white','active'));
            btn.classList.add('bg-slate-900','text-white','active');
            const tab = btn.getAttribute('data-tab');
            $('#calendar-card').classList.toggle('hidden', tab!=='calendar');
            $('#table-card').classList.toggle('hidden', tab!=='table');
        }));*/

        $$('.tab-btn').forEach(btn => btn.addEventListener('click', () => {
            $$('.tab-btn').forEach(b => b.classList.remove('bg-slate-900','text-white','active'));
            btn.classList.add('bg-slate-900','text-white','active');
            const tab = btn.getAttribute('data-tab');
            $('#calendar-card').classList.toggle('hidden', tab!=='calendar');
            $('#table-card').classList.toggle('hidden', tab!=='table');
            if (tab === 'calendar') setTimeout(() => window.calendar?.updateSize(), 0);
        }));



        // const q=$('#q'); if (q) q.addEventListener('input', render);
        // $$('.platform').forEach(cb => cb.addEventListener('change', render));
        // const from=$('#from'); if (from) from.addEventListener('change', render);
        // const to=$('#to'); if (to) to.addEventListener('change', render);
        // const clear=$('#btn-clear'); if (clear) clear.addEventListener('click',()=>{
        //     if(q) q.value=''; $$('.platform').forEach(cb=>cb.checked=true);
        //     if(from) from.value=''; if(to) to.value='';
        //     $$('#accountsList input[type="checkbox"]').forEach(cb=>cb.checked=true);
        //     render();
        // });

        // ---- Sidebar filters: universal delegation ----
        const side = document.getElementById('sidePanel');
        function wantsRender(t) {
            if (!t) return false;
            if (t.id === 'q') return true;                              // search
            if (t.classList && t.classList.contains('platform')) return true; // platform checkboxes
            if (t.id === 'from' || t.id === 'to') return true;          // dates
            if (t.closest && t.closest('#accountsList') && t.type === 'checkbox') return true; // account cbs (loaded later)
            return false;
        }
        $('#accountsList')?.addEventListener('change', (e) => {
            if (e.target && e.target.matches('input[type="checkbox"]')) render();
        });

        side?.addEventListener('input',  (e) => { if (wantsRender(e.target)) render(); }, true);
        side?.addEventListener('change', (e) => { if (wantsRender(e.target)) render(); }, true);

        // ---- Clear filters (delegated click) ----
        document.addEventListener('click', (e) => {
            const t = e.target;
            // πιάνει είτε το ίδιο το button είτε εσωτερικό του στοιχείο
            if (t && (t.id === 'btn-clear' || t.closest?.('#btn-clear'))) {
                e.preventDefault();

                // Search
                const qEl = document.getElementById('q');
                if (qEl) qEl.value = '';

                // Platforms → όλα checked
                document.querySelectorAll('.platform').forEach(cb => cb.checked = true);

                // Date range
                const fromEl = document.getElementById('from');
                const toEl   = document.getElementById('to');
                if (fromEl) fromEl.value = '';
                if (toEl)   toEl.value   = '';

                // Accounts → όλα checked (ό,τι έχει φορτωθεί τώρα)
                document.querySelectorAll('#accountsList input[type="checkbox"]').forEach(cb => cb.checked = true);

                // Table-only flag (προαιρετικό: καθάρισέ το κι αυτό)
                const noDate = document.getElementById('showNoDate');
                if (noDate) noDate.checked = false;

                render();
            }
        }, true);






        $('#btn-refresh')?.addEventListener('click', fetchMeetings);
        $('#btn-export')?.addEventListener('click', e=>{
            e.preventDefault(); downloadICS(applyFilters(EVENTS));
        });
        // $('#showNoDate')?.addEventListener('change', render,{passive:true});
        // Include messages without date (table only)
        const noDate = $('#showNoDate');
        if (noDate) noDate.addEventListener('change', render, {passive: true});
    }

    onReady(() => {
        // Account form
        const form = document.getElementById('formAddAccount');
        if (form) {
            form.addEventListener('submit', async e => {
                e.preventDefault();
                const data = Object.fromEntries(new FormData(form).entries());
                data.imap_port = parseInt(data.imap_port || "993");
                data.imap_ssl = true;
                data.can_parse = true;
                data.enabled = true;
                try {
                    const res = await fetch('/api/v1/accounts',{
                        method:'POST',headers:{'Content-Type':'application/json'},
                        body: JSON.stringify(data)
                    });
                    if(res.ok){ alert('Account saved!'); form.reset();}
                    else { alert('Error: '+res.status);}
                } catch(err){ alert('Request failed: '+err);}
            });
        }

        //window.addEventListener("DOMContentLoaded", loadAccounts);
        loadAccounts();

        /*document.getElementById("btnUpdate")?.addEventListener("click", async () => {
            const b=document.getElementById("btnUpdate");
            toggleBusy(b,true);
            try {
                await fetch(`${API_PARSE}?force_full=false`, {method:"POST"});
                await reloadMeetings?.();
            } catch(e){console.error(e);}
            finally{toggleBusy(b,false);}
        });*/

        // document.getElementById("btnUpdate")?.addEventListener("click", async () => {
        //     const b = document.getElementById("btnUpdate");
        //     toggleBusy(b, true);
        //     startHeaderLoading('blue');          // light blue
        //     try {
        //         await fetch(`${API_PARSE}?force_full=false`, { method: "POST" });
        //         await reloadMeetings?.();
        //     } catch (e) {
        //         console.error(e);
        //     } finally {
        //         stopHeaderLoading();
        //         toggleBusy(b, false);
        //     }
        // });

        // Update
        document.getElementById("btnUpdate")?.addEventListener("click", async () => {
            const b = document.getElementById("btnUpdate");
            toggleBusy(b, true);
            _holdUntilIdle = true;            // κράτα μέχρι το /status να γίνει idle
            startHeaderLoading('blue');       // μπλε
            try {
                await fetch(`${API_PARSE}?force_full=false`, { method: "POST" });
                await reloadMeetings?.();
            } catch (e) {
                console.error(e);
            } finally {
                toggleBusy(b, false);
                // ΔΕΝ καλούμε stopHeaderLoading εδώ. Θα το κάνει το pollStatus όταν γίνει idle.
            }
        });


        /*document.getElementById("btnFullParse")?.addEventListener("click", async () => {
            const b=document.getElementById("btnFullParse");
            if(!confirm("Run FULL parse for all accounts?")) return;
            toggleBusy(b,true);
            try {
                await fetch(`${API_PARSE}?force_full=true`, {method:"POST"});
                await reloadMeetings?.();
            } catch(e){console.error(e);}
            finally{toggleBusy(b,false);}
        });*/

        // document.getElementById("btnFullParse")?.addEventListener("click", async () => {
        //     const b = document.getElementById("btnFullParse");
        //     if (!confirm("Run FULL parse for all accounts?")) return;
        //     toggleBusy(b, true);
        //     startHeaderLoading('orange');        // amber/orange
        //     try {
        //         await fetch(`${API_PARSE}?force_full=true`, { method: "POST" });
        //         await reloadMeetings?.();
        //     } catch (e) {
        //         console.error(e);
        //     } finally {
        //         stopHeaderLoading();
        //         toggleBusy(b, false);
        //     }
        // });

        // Full-Parse
        document.getElementById("btnFullParse")?.addEventListener("click", async () => {
            const b = document.getElementById("btnFullParse");
            if (!confirm("Run FULL parse for all accounts?")) return;
            toggleBusy(b, true);
            _holdUntilIdle = true;            // κράτα μέχρι idle
            startHeaderLoading('orange');     // πορτοκαλί
            try {
                await fetch(`${API_PARSE}?force_full=true`, { method: "POST" });
                await reloadMeetings?.();
            } catch (e) {
                console.error(e);
            } finally {
                toggleBusy(b, false);
                // ΔΕΝ καλούμε stopHeaderLoading εδώ.
            }
        });


        // document.getElementById("btnRefresh")?.addEventListener("click", async () => {
        //     startHeaderLoading('dark');          // slate/dark
        //     try {
        //         await fetchMeetings();
        //     } finally {
        //         stopHeaderLoading();
        //     }
        // });

        // Refresh (προαιρετικά κρατάμε λίγα ms μόνο, γιατί τελειώνει γρήγορα)
        document.getElementById("btnRefresh")?.addEventListener("click", async () => {
            _holdUntilIdle = false;           // όχι sticky
            startHeaderLoading('dark');
            try {
                await fetchMeetings();
            } finally {
                // μικρό grace period ώστε να “φαίνεται”
                setTimeout(() => stopHeaderLoading(), 250);
            }
        });


        init();
        setupResponsiveHeaderMenu();
    });

})();



