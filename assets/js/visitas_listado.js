// VisitaSegura - Listado de visitas en dos columnas (Dentro / Fuera)
(function () {
  const $ = (id) => document.getElementById(id);

  function getCookie(name) {
    const m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return m ? decodeURIComponent(m[2]) : '';
  }
  const CSRF = getCookie('csrftoken');

  function showMsg(text, kind = 'secondary', ttl = 8000) {
    const m = $("msg");
    if (!m) return;
    m.className = `alert alert-${kind} mt-3 mb-0`;
    m.textContent = text;
    if (ttl > 0) setTimeout(() => { m.className = 'alert alert-secondary mt-3 mb-0'; m.textContent = 'Listo.'; }, ttl);
  }

  async function fetchJson(url) {
    const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return await res.json();
  }

  function norm(s){ return (s||'').toString().toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu,''); }

  function renderTables(rows) {
    const tbodyDentro = $("tbodyDentro");
    const tbodyFuera  = $("tbodyFuera");
    const badgeTotal  = $("totalBadge");
    const cDentro     = $("countDentro");
    const cFuera      = $("countFuera");

    const q = norm(($("txtSearch")?.value || '').trim());

    // filtro texto
    const filtered = rows.filter(r => {
      const blob = `${r.nombre} ${r.rut} ${r.lugar} ${r.estado} ${r.entrada_at} ${r.salida_at}`;
      return norm(blob).includes(q);
    });

    const dentro = filtered.filter(r => !!r.abierta);
    const fuera  = filtered.filter(r => !r.abierta);

    // Render DENTRO
    if (dentro.length === 0) {
      tbodyDentro.innerHTML = `<tr><td colspan="5" class="text-muted">Sin resultados</td></tr>`;
    } else {
      tbodyDentro.innerHTML = dentro.map(r => `
        <tr>
          <td>${r.nombre || ''}</td>
          <td>${r.rut || ''}</td>
          <td>${r.lugar || ''}</td>
          <td>${r.entrada_at || ''}</td>
          <td class="text-nowrap">
            <button data-id="${r.id}" class="btn btn-sm btn-danger btnClose">🚪 Salida</button>
          </td>
        </tr>
      `).join('');
    }

    // Render FUERA
    if (fuera.length === 0) {
      tbodyFuera.innerHTML = `<tr><td colspan="5" class="text-muted">Sin resultados</td></tr>`;
    } else {
      tbodyFuera.innerHTML = fuera.map(r => `
        <tr>
          <td>${r.nombre || ''}</td>
          <td>${r.rut || ''}</td>
          <td>${r.lugar || ''}</td>
          <td>${r.entrada_at || ''}</td>
          <td>${r.salida_at || ''}</td>
        </tr>
      `).join('');
    }

    // Contadores y total
    if (badgeTotal) badgeTotal.textContent = `${filtered.length} resultado${filtered.length === 1 ? '' : 's'}`;
    if (cDentro) cDentro.textContent = dentro.length;
    if (cFuera)  cFuera.textContent  = fuera.length;

    // Wire-up botón Salida solo en "Dentro"
    tbodyDentro.querySelectorAll('.btnClose').forEach(btn => {
      btn.addEventListener('click', () => closeVisit(btn));
    });

    showMsg(filtered.length ? 'Listo.' : 'Sin registros para los filtros actuales.', 'secondary', 4000);
  }

  async function loadGrid() {
    const cfg = $("cfg");
    const listUrl = new URL(cfg.dataset.listUrl, window.location.origin);
    const q = ($("txtSearch")?.value || '').trim();
    if (q) listUrl.searchParams.set('q', q);

    try {
      const data = await fetchJson(listUrl.toString());
      if (!data.ok) { showMsg('No se pudo cargar el listado.', 'danger'); return; }
      renderTables(data.rows || []);
    } catch (e) {
      showMsg('Error de red al cargar el listado.', 'danger');
    }
  }

  async function closeVisit(btn) {
    const cfg = $("cfg");
    const url = new URL(cfg.dataset.closeUrl, window.location.origin).toString();
    btn.disabled = true;
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
        body: JSON.stringify({ visita_id: btn.dataset.id })
      });
      const data = await res.json();
      showMsg(data.message || (data.ok ? 'Salida registrada' : 'No se pudo registrar la salida'),
              data.ok ? 'success' : 'warning', 6000);
      await loadGrid();
    } catch {
      showMsg('Error de red al cerrar visita.', 'danger');
    } finally {
      btn.disabled = false;
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    $("txtSearch")?.addEventListener('input', () => loadGrid());
    loadGrid();
  });
})();
