# db_simple.py
import sqlite3, json, os, threading, time

DB_PATH = os.path.join(os.path.dirname(__file__), "pneumatics.db")
_LOCK = threading.Lock()

DEFAULT_STATE = {
    "piston1": {
        "desired_pressure": 75.0,
        "max_cycles": 1000,
        "time_on": 1.0,
        "time_off": 1.0,
        "current_cycle": 0,
        "running": False,
        "paused": False,
    },
    "piston2": {
        "desired_pressure": 75.0,
        "max_cycles": 1000,
        "time_on": 1.0,
        "time_off": 1.0,
        "current_cycle": 0,
        "running": False,
        "paused": False,
    },
    # add button/toggle flags here if you want:
    "ui": {"piston1_on": False, "piston1_off": False, "piston2_on": False, "piston2_off": False}
}

def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_state (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          blob TEXT NOT NULL,
          updated_at INTEGER NOT NULL
        )""")
    # ensure row exists
    cur = conn.execute("SELECT 1 FROM app_state WHERE id=1")
    if not cur.fetchone():
        conn.execute(
            "INSERT INTO app_state (id, blob, updated_at) VALUES (1, ?, ?)",
            (json.dumps(DEFAULT_STATE), int(time.time()))
        )
        conn.commit()
    return conn

def load_state() -> dict:
    with _LOCK:
        conn = _connect()
        (blob,) = conn.execute("SELECT blob FROM app_state WHERE id=1").fetchone()
        conn.close()
        return json.loads(blob)

def save_state(state: dict) -> None:
    with _LOCK:
        conn = _connect()
        conn.execute(
            "UPDATE app_state SET blob=?, updated_at=? WHERE id=1",
            (json.dumps(state), int(time.time()))
        )
        conn.commit()
        conn.close()
