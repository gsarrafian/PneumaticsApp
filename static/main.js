// static/main.js
async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return res.json();
}

document.addEventListener("DOMContentLoaded", () => {
  // Helpers to read a panel's inputs
  function getPanelValues(panelPrefix) {
    return {
      time_on: parseFloat(document.getElementById(`${panelPrefix}-time-on`).value || "0") || 0,
      time_off: parseFloat(document.getElementById(`${panelPrefix}-time-off`).value || "0") || 0,
      cycles: parseInt(document.getElementById(`${panelPrefix}-max-cycles`).value || "0", 10) || 0,
    };
  }

  // Wire a panel by its aria-labelledby id and piston name
  function wirePanel(ariaId, pistonName) {
    const panel = document.querySelector(`[aria-labelledby="${ariaId}"]`);
    if (!panel) return;

    const startBtn = panel.querySelector(".start-btn");
    const pauseBtn = panel.querySelector(".pause-btn");
    const resetBtn = panel.querySelector(".reset-btn");

    startBtn.addEventListener("click", async () => {
      const vals = getPanelValues(pistonName.replace("piston", "piston")); // keep prefix
      const payload = { piston: pistonName, time_on: vals.time_on, time_off: vals.time_off, cycles: vals.cycles };
      const resp = await postJSON("/api/piston/start", payload);
      if (!resp.ok) alert(resp.error || "Start failed");
    });

    pauseBtn.addEventListener("click", async () => {
      const resp = await postJSON("/api/piston/pause", { piston: pistonName });
      if (!resp.ok) alert(resp.error || "Pause failed");
    });

    resetBtn.addEventListener("click", async () => {
      const resp = await postJSON("/api/piston/reset", { piston: pistonName });
      if (!resp.ok) alert(resp.error || "Reset failed");
    });
  }

  // Piston 1 panel uses IDs: piston1-time-on/off/max-cycles
  // Piston 2 panel uses: piston2-time-on/off/max-cycles
  wirePanel("piston-1-title", "piston1");
  wirePanel("piston-2-title", "piston2");
});
