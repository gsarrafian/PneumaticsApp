# app.py
from flask import Flask, render_template, request, jsonify
from gpio_driver import GPIOController
import threading, time, os

app = Flask(__name__)

gpio = GPIOController(mode="BOARD")  # using physical pin numbers
PINMAP = {
    "piston1_valve": 16,  # adjust to your wiring
    "piston2_valve": 18,
}

class PistonWorker:
    def __init__(self, valve_pin: int):
        self.valve_pin = valve_pin
        self.thread = None
        self._pause_evt = threading.Event()  # when set => PAUSED
        self._stop_evt = threading.Event()   # when set => STOP
        self._lock = threading.Lock()
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

    def _run(self, time_on: float, time_off: float, cycles: int):
        with self._lock:
            self.running = True
            self.current_cycle = 0
            self.total_cycles = cycles

        try:
            for c in range(1, cycles + 1):
                if self._stop_evt.is_set():
                    break

                # ON
                gpio.set(self.valve_pin, True)
                if not self._sleep_checking(time_on):
                    break

                # OFF
                gpio.set(self.valve_pin, False)
                if not self._sleep_checking(time_off):
                    break

                with self._lock:
                    self.current_cycle = c
        finally:
            # Ensure valve is OFF when finishing/stopping
            gpio.set(self.valve_pin, False)
            with self._lock:
                self.running = False

    def start(self, time_on: float, time_off: float, cycles: int):
        # If was stopped, clear flags. If was paused, unpause.
        self._stop_evt.clear()
        self._pause_evt.clear()

        # If thread is alive (paused), just resume
        if self.thread and self.thread.is_alive():
            return

        # Otherwise, (re)start a new thread
        self.thread = threading.Thread(
            target=self._run, args=(time_on, time_off, cycles), daemon=True
        )
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
    "piston1": PistonWorker(PINMAP["piston1_valve"]),
    "piston2": PistonWorker(PINMAP["piston2_valve"]),
}

@app.route("/")
def index():
    return render_template("index.html", title="Pneumatics Control")

@app.route("/api/piston/start", methods=["POST"])
def piston_start():
    data = request.get_json(force=True)
    piston = data.get("piston")  # "piston1" | "piston2"
    time_on = float(data.get("time_on", 0))
    time_off = float(data.get("time_off", 0))
    cycles = int(data.get("cycles", 0))
    if piston not in workers:
        return jsonify({"ok": False, "error": "Unknown piston"}), 400
    if time_on < 0 or time_off < 0 or cycles <= 0:
        return jsonify({"ok": False, "error": "Invalid parameters"}), 400
    workers[piston].start(time_on, time_off, cycles)
    return jsonify({"ok": True, "status": workers[piston].status()})

@app.route("/api/piston/pause", methods=["POST"])
def piston_pause():
    data = request.get_json(force=True)
    piston = data.get("piston")
    if piston not in workers:
        return jsonify({"ok": False, "error": "Unknown piston"}), 400
    workers[piston].pause()
    return jsonify({"ok": True, "status": workers[piston].status()})

@app.route("/api/piston/resume", methods=["POST"])
def piston_resume():
    data = request.get_json(force=True)
    piston = data.get("piston")
    if piston not in workers:
        return jsonify({"ok": False, "error": "Unknown piston"}), 400
    workers[piston].resume()
    return jsonify({"ok": True, "status": workers[piston].status()})

@app.route("/api/piston/reset", methods=["POST"])
def piston_reset():
    data = request.get_json(force=True)
    piston = data.get("piston")
    if piston not in workers:
        return jsonify({"ok": False, "error": "Unknown piston"}), 400
    workers[piston].reset()
    return jsonify({"ok": True, "status": workers[piston].status()})

@app.route("/api/piston/status", methods=["GET"])
def piston_status():
    piston = request.args.get("piston", "piston1")
    if piston not in workers:
        return jsonify({"ok": False, "error": "Unknown piston"}), 400
    return jsonify({"ok": True, "status": workers[piston].status()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
