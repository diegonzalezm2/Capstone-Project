// assets/js/scanner.v6.js
(() => {
  const $ = (id) => document.getElementById(id);

  let reader = null;
  let running = false;
  let currentDeviceId = null;
  let lastRaw = "";

  const els = {
    video:  $('preview'),
    tip:    $('overlay-tip'),
    scan:   $('btnScan'),
    stop:   $('btnStop'),
    select: $('camera-select'),
    result: $('result'),
    // modal + campos
    modalInst: null,
    raw:    $('rawField'),
    rut:    $('rutField'),
    fecha:  $('fechaField'),
    destino:$('destinoField'),
    nombres:$('nombresField'),
    apellidos:$('apellidosField'),
    confirm: $('confirmBtn'),
  };

  function setMsg(text, ok = true) {
    const el = els.result;
    el.classList.remove('d-none', 'alert-success', 'alert-danger');
    el.classList.add(ok ? 'alert-success' : 'alert-danger');
    el.textContent = text;
  }

  function showTip(show) {
    if (!els.tip) return;
    els.tip.style.display = show ? 'block' : 'none';
  }

  function ensureModal() {
    if (!els.modalInst) {
      // usa bootstrap si existe; si no, crea un fallback simple
      const el = document.getElementById('scanModal');
      if (window.bootstrap && bootstrap.Modal) {
        els.modalInst = new bootstrap.Modal(el);
      } else {
        // fallback mínimo
        els.modalInst = {
          show() { el.classList.add('show'); el.style.display = 'block'; },
          hide() { el.classList.remove('show'); el.style.display = 'none'; }
        };
      }
    }
  }

  function extractRut(text) {
    // sólo para mostrar (el backend valida de verdad)
    const m = (text || "").replace(/\s+/g,'').match(/(\d{1,2}\.?\d{3}\.?\d{3})-?([0-9Kk])/);
    if (!m) return "";
    const body = m[1].replace(/\D/g,'');
    const dv   = m[2].toUpperCase();
    return body.replace(/\B(?=(\d{3})+(?!\d))/g, ".") + "-" + dv;
  }

  async function listCameras() {
    try { await navigator.mediaDevices.getUserMedia({ video: true }); } catch {}
    const devices = await ZXingBrowser.BrowserCodeReader.listVideoInputDevices();
    els.select.innerHTML = '';
    devices.forEach((d, i) => {
      const opt = document.createElement('option');
      opt.value = d.deviceId;
      opt.textContent = d.label || `Cámara ${i + 1}`;
      els.select.appendChild(opt);
    });
    const back = devices.find(d => /back|rear|environment|trás|trasera/i.test((d.label || '')));
    currentDeviceId = (back || devices[0])?.deviceId || null;
    if (currentDeviceId) {
      els.select.value = currentDeviceId;
      els.select.style.display = devices.length > 1 ? 'block' : 'none';
    }
    return devices.length;
  }

  function buildHints() {
    const hints = new Map();
    const fmts = [
      ZXingBrowser.BarcodeFormat.QR_CODE,
      ZXingBrowser.BarcodeFormat.PDF_417,
      ZXingBrowser.BarcodeFormat.CODE_128,
    ];
    hints.set(ZXingBrowser.DecodeHintType.POSSIBLE_FORMATS, fmts);
    hints.set(ZXingBrowser.DecodeHintType.TRY_HARDER, true);
    return hints;
  }

  async function start(apiUrl, csrfToken, preferEnv = true) {
    if (running) return;
    try {
      const count = await listCameras();
      if (!count) { setMsg('No se encontraron cámaras.', false); return; }

      reader = new ZXingBrowser.BrowserMultiFormatReader(buildHints(), 250);
      running = true;
      els.scan.disabled = true;

      const onFrame = async (res, err) => {
        if (res) {
          showTip(false);
          stop();

          lastRaw = res.getText();
          ensureModal();

          // rellena modal
          els.raw.value   = lastRaw;
          els.rut.value   = extractRut(lastRaw) || '(no detectado)';
          els.fecha.value = new Date().toLocaleString();
          els.destino.value = "";
          els.nombres.value = "";
          els.apellidos.value = "";

          els.modalInst.show();
        } else if (err && String(err?.name) !== 'NotFoundException') {
          // en algunas builds ZXing no expone la clase → evitamos instanceof
          console.warn('[scanner] frame error', err);
        }
      };

      if (currentDeviceId) {
        await reader.decodeFromVideoDevice(currentDeviceId, els.video, onFrame);
      } else if (preferEnv) {
        await reader.decodeFromConstraints({ video: { facingMode: { ideal: 'environment' } } }, els.video, onFrame);
      } else {
        await reader.decodeFromVideoDevice(undefined, els.video, onFrame);
      }

      showTip(true);
      setMsg('Cámara lista. Apunta al QR/Carnet.', true);

      els.confirm.onclick = async () => {
        const destinoId = els.destino.value;
        if (!destinoId) { setMsg('Debes seleccionar un destino.', false); return; }

        const nameManual = [els.nombres.value.trim(), els.apellidos.value.trim()].filter(Boolean).join(' ');
        try {
          const r = await fetch(apiUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': window.SCAN_CFG?.csrf || ''
            },
            body: JSON.stringify({
              raw: lastRaw,
              destino_id: parseInt(destinoId),
              nombre_manual: nameManual
            })
          });
          const data = await r.json();
          setMsg(data.msg || (data.ok ? 'OK' : 'Error'), !!data.ok);
        } catch (e) {
          console.error(e);
          setMsg('Error de red.', false);
        } finally {
          els.modalInst.hide();
          setTimeout(() => start(apiUrl, csrfToken), 700);
        }
      };

    } catch (e) {
      console.error('[scanner] start error', e);
      running = false;
      els.scan.disabled = false;
      setMsg('No se pudo iniciar la cámara. Revisa permisos/origen.', false);
    }
  }

  function stop() {
    if (!reader) return;
    try { reader.reset(); } catch {}
    if (els.video.srcObject) {
      els.video.srcObject.getTracks().forEach(t => t.stop());
      els.video.srcObject = null;
    }
    running = false;
    reader = null;
    els.scan.disabled = false;
    showTip(true);
  }

  function bindUI(apiUrl, csrfToken) {
    els.scan.addEventListener('click', () => start(apiUrl, csrfToken));
    els.stop.addEventListener('click', () => stop());
    els.select.addEventListener('change', () => {
      currentDeviceId = els.select.value || null;
      if (running) { stop(); start(apiUrl, csrfToken); }
    });
  }

  window.initScanner = ({ apiUrl, csrfToken, autoStart = true }) => {
    window.SCAN_CFG = { csrf: csrfToken, apiUrl };
    bindUI(apiUrl, csrfToken);
    if (autoStart) {
      navigator.mediaDevices.getUserMedia({ video: true })
        .then(() => start(apiUrl, csrfToken))
        .catch(() => setMsg('Pulsa “Escanear” para iniciar la cámara.', true));
    } else {
      setMsg('Pulsa “Escanear” para iniciar la cámara.', true);
    }
  };
})();
