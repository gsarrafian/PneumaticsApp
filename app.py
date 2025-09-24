# app.py
from flask import Flask, render_template, request, jsonify
from gpio_driver import GPIOController
from i2c_driver import set_pressure
import threading, time, os
from werkzeug.serving import WSGIRequestHandler
from db import load_state, save_state

class SilentHandler(WSGIRequestHandler):
    def log(self, type, message, *args):
        pass

app = Flask(__name__)

gpio = GPIOController(mode="BOARD")  # using physical pin numbers
PINMAP = {
    "piston1_valve": 16,  # adjust to your wiring
    "piston2_valve": 18,
}

class PistonWorker:
    def __init__(self, name: str, valve_pin: int):
        self.name = name
        self.valve_pin = valve_pin
        self.thread = None
        self._pause_evt = threading.Event()  # when set => PAUSED
        self._stop_evt = threading.Event()   # when set => STOP
        self._lock = threading.Lock()

        self.time_on = 0.0
        self.time_off = 0.0
        self.current_cycle = 0
        self.total_cycles = 0
        self.running = False

    def _sleep_checking(self, seconds: float):
        # Sleep in small slices so pause/stop is responsive
        end = time.time() + max(0.0, seconds)
        while time.time() < end:
            if self._stop_evt.is_set():
                return False
            while self._pause_evt.is_set() and not self._stop_evt.is_set():
                time.sleep(0.05)
            time.sleep(0.02)
        return not self._stop_evt.is_set()

    def _run(self):
        with self._lock:
            self.running = True

        try:
            while not self._stop_evt.is_set():
                # check stop/end-of-test
                with self._lock:
                    done = (0 < self.total_cycles <= self.current_cycle)
                    t_on = float(self.time_on)
                    t_off = float(self.time_off)
                if done:
                    break

                # ON
                gpio.set(self.valve_pin, True)
                if not self._sleep_checking(t_on):
                    break

                # OFF
                gpio.set(self.valve_pin, False)
                if not self._sleep_checking(t_off):
                    break

                with self._lock:
                    self.current_cycle += 1
        finally:
            gpio.set(self.valve_pin, False)
            with self._lock:
                self.running = False

    def start(self, time_on: float, time_off: float, cycles: int):
        self._stop_evt.clear()
        self._pause_evt.clear()
        with self._lock:
            self.time_on = float(time_on)
            self.time_off = float(time_off)
            self.total_cycles = int(cycles)
            self.current_cycle = 0  # fresh run
        if self.thread and self.thread.is_alive():
            return  # already running (e.g., paused). resume happens elsewhere
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def pause(self):
        self._pause_evt.set()

    def resume(self):
        self._pause_evt.clear()

    def reset(self):
        # stop the thread and reset counters
        self._stop_evt.set()
        self._pause_evt.clear()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        gpio.set(self.valve_pin, False)
        with self._lock:
            self.current_cycle = 0
            self.total_cycles = 0
            self.running = False

    def update(self, time_on=None, time_off=None, cycles=None):
        with self._lock:
            if time_on is not None:
                self.time_on = float(time_on)
            if time_off is not None:
                self.time_off = float(time_off)
            if cycles is not None:
                self.total_cycles = int(cycles)
                # If user shrinks the target below current progress, we’ll exit on next loop

    def status(self):
        with self._lock:
            return {
                "running": self.running,
                "paused": self._pause_evt.is_set(),
                "current_cycle": self.current_cycle,
                "total_cycles": self.total_cycles,
            }

# One worker per piston
workers = {
    "piston1": PistonWorker("piston1", PINMAP["piston1_valve"]),
    "piston2": PistonWorker("piston2", PINMAP["piston2_valve"]),
}

state = load_state()
workers["piston1"].current_cycle = int(state["piston1"]["current_cycle"])
workers["piston1"].total_cycles  = int(state["piston1"]["max_cycles"])
workers["piston2"].current_cycle = int(state["piston2"]["current_cycle"])
workers["piston2"].total_cycles  = int(state["piston2"]["max_cycles"])

@app.route("/")
def index():
    return render_template("index.html", title="Pneumatics Control")

@app.route("/api/state", methods=["GET"])
def api_state():
    return jsonify({"ok": True, "state": load_state()})

@app.route("/api/piston/update", methods=["POST"])
def piston_update():
    data = request.get_json(force=True)
    piston = data.get("piston")
    if piston not in workers:
        return jsonify({"ok": False, "error": "Unknown piston"}), 400

    # Pull optional fields
    time_on  = data.get("time_on")
    time_off = data.get("time_off")
    cycles   = data.get("cycles")
    desired_pressure = data.get("desired_pressure")

    # Validate if provided
    def _num(x): return float(x) if x is not None else None
    t_on  = _num(time_on)
    t_off = _num(time_off)
    cyc   = int(cycles) if cycles is not None else None

    for bad in [v for v in [t_on, t_off] if v is not None and v < 0]:
        return jsonify({"ok": False, "error": "Time values must be >= 0"}), 400
    if cyc is not None and cyc <= 0:
        return jsonify({"ok": False, "error": "Cycles must be > 0"}), 400

    # Update worker live settings
    workers[piston].update(time_on=t_on, time_off=t_off, cycles=cyc)

    # Persist to DB
    state = load_state()
    key = piston
    if t_on  is not None:  state[key]["time_on"]  = t_on
    if t_off is not None:  state[key]["time_off"] = t_off
    if cyc   is not None:
        state[key]["max_cycles"] = cyc
        # keep current_cycle as-is; worker will stop when hitting new target
    if desired_pressure is not None:
        state[key]["desired_pressure"] = float(desired_pressure)
    # also mirror runtime flags
    st = workers[piston].status()
    state[key]["running"] = bool(st["running"])
    state[key]["paused"]  = bool(st["paused"])
    state[key]["current_cycle"] = int(st["current_cycle"])
    save_state(state)

    return jsonify({"ok": True, "status": workers[piston].status()})

@app.route("/api/piston/start", methods=["POST"])
def piston_start():
    data = request.get_json(force=True)
    piston = data.get("piston")  # "piston1" | "piston2"
    time_on = float(data.get("time_on", 0))
    time_off = float(data.get("time_off", 0))
    cycles = int(data.get("cycles", 0))
    desired_pressure = data.get("desired_pressure")
    if piston not in workers:
        return jsonify({"ok": False, "error": "Unknown piston"}), 400
    if time_on < 0 or time_off < 0 or cycles <= 0:
        return jsonify({"ok": False, "error": "Invalid parameters"}), 400
    workers[piston].start(time_on, time_off, cycles)

    st = load_state()
    key = piston
    st[key]["time_on"] = time_on
    st[key]["time_off"] = time_off
    st[key]["max_cycles"] = cycles
    st[key]["current_cycle"] = 0
    st[key]["running"] = True
    st[key]["paused"] = False
    if desired_pressure is not None:
        state[key]["desired_pressure"] = float(desired_pressure)  # ← NEW
    save_state(state)
    save_state(st)

    return jsonify({"ok": True, "status": workers[piston].status()})

@app.route("/api/piston/pause", methods=["POST"])
def piston_pause():
    data = request.get_json(force=True)
    piston = data.get("piston")
    if piston not in workers:
        return jsonify({"ok": False, "error": "Unknown piston"}), 400
    workers[piston].pause()

    st = load_state()
    st[piston]["paused"] = True
    st[piston]["running"] = True
    st[piston]["current_cycle"] = workers[piston].current_cycle
    save_state(st)

    return jsonify({"ok": True, "status": workers[piston].status()})

@app.route("/api/piston/resume", methods=["POST"])
def piston_resume():
    data = request.get_json(force=True)
    piston = data.get("piston")
    if piston not in workers:
        return jsonify({"ok": False, "error": "Unknown piston"}), 400
    workers[piston].resume()

    st = load_state()
    st[piston]["paused"] = False
    st[piston]["running"] = True
    st[piston]["current_cycle"] = workers[piston].current_cycle
    save_state(st)

    return jsonify({"ok": True, "status": workers[piston].status()})

@app.route("/api/piston/reset", methods=["POST"])
def piston_reset():
    data = request.get_json(force=True)
    piston = data.get("piston")
    if piston not in workers:
        return jsonify({"ok": False, "error": "Unknown piston"}), 400
    workers[piston].reset()

    st = load_state()
    st[piston]["current_cycle"] = 0
    st[piston]["running"] = False
    st[piston]["paused"] = False
    save_state(st)

    return jsonify({"ok": True, "status": workers[piston].status()})

@app.route("/api/piston/status", methods=["GET"])
def piston_status():
    piston = request.args.get("piston", "piston1")
    if piston not in workers:
        return jsonify({"ok": False, "error": "Unknown piston"}), 400
    return jsonify({"ok": True, "status": workers[piston].status()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, request_handler=SilentHandler)