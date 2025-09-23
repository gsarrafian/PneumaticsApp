// static/main.js
async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return res.json();
}

async function getJSON(url) {
  const res = await fetch(url);
  return res.json();
}

document.addEventListener("DOMContentLoaded", () => {
  function getPanelValues(panelPrefix) {
    return {
      time_on: parseFloat(document.getElementById(`${panelPrefix}-time-on`).value || "0") || 0,
      time_off: parseFloat(document.getElementById(`${panelPrefix}-time-off`).value || "0") || 0,
      cycles: parseInt(document.getElementById(`${panelPrefix}-max-cycles`).value || "0", 10) || 0,
    };
  }

  function statusElFor(pistonName) {
    return document.getElementById(`${pistonName}-status`);
  }

  async function fetchStatus(pistonName) {
    const resp = await getJSON(`/api/piston/status?piston=${encodeURIComponent(pistonName)}`);
    if (!resp.ok) throw new Error(resp.error || "Status failed");
    return resp.status; // { running, paused, current_cycle, total_cycles }
  }

  async function startOrResume(pistonName) {
    const st = await fetchStatus(pistonName);
    if (st.paused) {
      return postJSON("/api/piston/resume", { piston: pistonName });
    }
    const vals = getPanelValues(pistonName); // piston1 / piston2 prefix matches input ids
    return postJSON("/api/piston/start", {
      piston: pistonName,
      time_on: vals.time_on,
      time_off: vals.time_off,
      cycles: vals.cycles,
    });
  }

  function wirePanel(ariaId, pistonName) {
    const panel = document.querySelector(`[aria-labelledby="${ariaId}"]`);
    if (!panel) return;

    const startBtn = panel.querySelector(".start-btn");
    const pauseBtn = panel.querySelector(".pause-btn");
    const resetBtn = panel.querySelector(".reset-btn");
    const statusEl = statusElFor(pistonName);

    startBtn.addEventListener("click", async () => {
      try {
        const resp = await startOrResume(pistonName);
        if (!resp.ok) alert(resp.error || "Start/Resume failed");
      } catch (e) {
        alert(e.message);
      }
    });

    pauseBtn.addEventListener("click", async () => {
      const resp = await postJSON("/api/piston/pause", { piston: pistonName });
      if (!resp.ok) alert(resp.error || "Pause failed");
    });

    resetBtn.addEventListener("click", async () => {
      const resp = await postJSON("/api/piston/reset", { piston: pistonName });
      if (!resp.ok) alert(resp.error || "Reset failed");
    });

    // status poller
    setInterval(async () => {
      try {
        const s = await fetchStatus(pistonName);
        const state = s.running ? (s.paused ? "Paused" : "Running") : "Idle";
        const progress =
          s.total_cycles > 0 ? ` (${s.current_cycle}/${s.total_cycles})` : "";
        statusEl.textContent = `${state}${progress}`;
      } catch (e) {
        statusEl.textContent = "Status unavailable";
      }
    }, 500);
  }

  wirePanel("piston-1-title", "piston1");
  wirePanel("piston-2-title", "piston2");
});
