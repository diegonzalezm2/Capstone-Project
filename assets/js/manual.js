// assets/js/manual.js
(function () {
  console.log("manual.js v3 cargado"); // Útil para comprobar que esta versión se cargó

  const form     = document.getElementById("manualForm");
  const inpNom   = document.getElementById("inpNombre");
  const inpRut   = document.getElementById("inpRut");
  const selLugar = document.getElementById("selLugar");
  const inpHora  = document.getElementById("inpHora");
  const btn      = document.getElementById("btnGuardar");

  const cfgEl   = document.getElementById("cfg");
  const API_URL = cfgEl?.dataset?.url || "/visitas/api/manual/";

  // CSRF desde el <form>
  const csrfInput = form.querySelector("input[name=csrfmiddlewaretoken]");
  const CSRF = csrfInput ? csrfInput.value : "";

  // --- Toast Bootstrap ---
  const toastEl   = document.getElementById("vsToast");
  const toastBody = document.getElementById("vsToastBody");
  const getToast  = (opts={}) => bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 2200, ...opts });

  function notify(message, type = "success") {
    toastBody.textContent = message;
    toastEl.classList.remove("text-bg-success","text-bg-danger","text-bg-warning","text-bg-info");
    toastEl.classList.add(
      type === "danger" ? "text-bg-danger" :
      type === "warning" ? "text-bg-warning" :
      type === "info"    ? "text-bg-info"    :
                           "text-bg-success"
    );
    getToast().show();
  }
  // ------------------------

  const trim = s => (s || "").toString().trim();

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();

    form.classList.add("was-validated");
    if (!form.checkValidity()) return;

    const payload = {
      nombre:     trim(inpNom.value),
      rut:        trim(inpRut.value),
      destino_id: selLugar.value ? Number(selLugar.value) : null,
      hora:       trim(inpHora.value) || null,   // HH:MM opcional
    };

    btn.disabled = true;
    btn.textContent = "Guardando...";

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": CSRF,
          "X-Requested-With": "fetch"
        },
        body: JSON.stringify(payload),
      });

      const ct = res.headers.get("content-type") || "";
      const isJSON = ct.includes("application/json");
      const data = isJSON ? await res.json() : { ok:false, message:`Error ${res.status}` };

      if (!res.ok || !data.ok) {
        notify(data.message || `Error ${res.status}`, "danger");
        return;
      }

      notify("Ingreso manual registrado con éxito.", "success");
      form.reset();
      form.classList.remove("was-validated");
    } catch (err) {
      console.error(err);
      notify("Error de red o servidor.", "danger");
    } finally {
      btn.disabled = false;
      btn.textContent = "Guardar";
    }
  });
})();
