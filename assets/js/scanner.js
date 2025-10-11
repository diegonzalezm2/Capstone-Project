(() => {
  const $ = (id) => document.getElementById(id);

  let reader = null;
  let running = false;
  let currentDeviceId = null;

  const els = {
    video:  $('preview'),
    tip:    $('overlay-tip'),
    scan:   $('btnScan'),
    stop:   $('btnStop'),
    select: $('camera-select'),
    result: $('result'),
  };

  function setMsg(text, ok = true) {
    const el = els.result;
    el.classList.remove('d-none', 'alert-success', 'alert-danger');
    el.classList.add(ok ? 'alert-success' : 'alert-danger');
    el.textContent = text;
  }

  function showTip(show) {
    if (els.tip) els.tip.style.display = show ? 'block' : 'none';
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

  // lector compatible
  function buildReader() {
    try {
      if (ZXingBrowser.DecodeHintType && ZXingBrowser.BarcodeFormat) {
        const hints = new Map();
        hints.set(ZXingBrowser.DecodeHintType.POSSIBLE_FORMATS, [
          ZXingBrowser.BarcodeFormat.QR_CODE,
          ZXingBrowser.BarcodeFormat.PDF_417,
        ]);
        hints.set(ZXingBrowser.DecodeHintType.TRY_HARDER, true);
        return new ZXingBrowser.BrowserMultiFormatReader(hints, 500);
      }
    } catch (_) {}
    return new ZXingBrowser.BrowserMultiFormatReader();
  }

  function hdConstraints(deviceId) {
    const base = {
      width:  { ideal: 1920 },
      height: { ideal: 1080 },
      focusMode: 'continuous'
    };
    if (deviceId) base.deviceId = { exact: deviceId };
    return { video: base, audio: false };
  }

  async function start(apiUrl, csrfToken) {
    if (running) return;

    try {
      if (!currentDeviceId) {
        const count = await listCameras();
        if (!count) {
          setMsg('No se encontraron cámaras.', false);
          return;
        }
      }

      reader = buildReader();
      running = true;
      els.scan.disabled = true;

      const cb = onFrame(apiUrl, csrfToken);

      // forzar HD y enfrentar environment
      const constraints = hdConstraints(currentDeviceId);
      await reader.decodeFromConstraints(constraints, els.video, cb);

      showTip(true);
      setMsg('Cámara lista. Apunta al QR/Carnet.', true);

    } catch (e) {
      console.error(e);
      running = false;
      els.scan.disabled = false;
      setMsg('No se pudo iniciar la cámara. Revisa permisos/origen.', false);
    }
  }

  function onFrame(apiUrl, csrfToken) {
    return async (res, err) => {
      if (res) {
        showTip(false);
        stop();
        const raw = res.getText();

        try {
          const r = await fetch(apiUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ raw })
          });
          const data = await r.json();
          setMsg(data.msg || (data.ok ? 'OK' : 'Error'), !!data.ok);
        } catch (e) {
          console.error(e);
          setMsg('Error de red.', false);
        } finally {
          setTimeout(() => start(apiUrl, csrfToken), 1000);
        }
      } else if (err && err.name !== 'NotFoundException') {
        // nada, se ignora
      }
    };
  }

  function stop() {
    try { reader?.reset(); } catch {}
    if (els.video?.srcObject) {
      els.video.srcObject.getTracks().forEach(t => t.stop());
      els.video.srcObject = null;
    }
    running = false;
    reader = null;
    els.scan.disabled = false;
    showTip(true);
    setMsg('Cámara detenida.', true);
  }

  function bindUI(apiUrl, csrfToken) {
    els.scan.addEventListener('click', () => start(apiUrl, csrfToken));
    els.stop.addEventListener('click', () => stop());
    els.select.addEventListener('change', () => {
      currentDeviceId = els.select.value || null;
      if (running) { stop(); start(apiUrl, csrfToken); }
    });
  }

  window.initScanner = async ({ apiUrl, csrfToken, autoStart = true }) => {
    bindUI(apiUrl, csrfToken);
    if (autoStart) {
      try {
        await navigator.mediaDevices.getUserMedia({ video: true });
        start(apiUrl, csrfToken);
      } catch {
        setMsg('Pulsa “Escanear” para iniciar la cámara.', true);
      }
    } else {
      setMsg('Pulsa “Escanear” para iniciar la cámara.', true);
    }
    try { await listCameras(); } catch {}
  };
})();
