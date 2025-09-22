"""Database helper functions for the pneumatics control application."""

import sqlite3
from typing import Any, Tuple

DB_PATH = "/home/qa/pneumatic_control.db"


def get_db_connection() -> sqlite3.Connection:
    """Open a new database connection."""

    return sqlite3.connect(DB_PATH)

def create_table() -> None:
    """Create the control_data table if it doesn't exist."""

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS control_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            desired_pressure1 REAL,
            desired_pressure2 REAL,
            max_cycles1 INTEGER,
            max_cycles2 INTEGER,
            cycles1 INTEGER,
            cycles2 INTEGER,
            time_on1 REAL,
            time_off1 REAL,
            time_on2 REAL,
            time_off2 REAL,
            toggle_state1 BOOLEAN,
            toggle_state2 BOOLEAN,
            piston1_on BOOLEAN,
            piston1_off BOOLEAN,
            piston2_on BOOLEAN,
            piston2_off BOOLEAN,
            running1 BOOLEAN,
            running2 BOOLEAN
        )
        """
    )
    conn.commit()
    conn.close()


def insert_initial_record() -> None:
    """Insert an initial record into the control_data table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO control_data (
            desired_pressure1,
            desired_pressure2,
            max_cycles1,
            max_cycles2,
            cycles1,
            cycles2,
            time_on1,
            time_off1,
            time_on2,
            time_off2,
            toggle_state1,
            toggle_state2,
            piston1_on,
            piston1_off,
            piston2_on,
            piston2_off,
            running1,
            running2
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            75.0,
            75.0,
            1000,
            1000,
            0,
            0,
            1.0,
            1.0,
            1.0,
            1.0,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
        ),
    )
    conn.commit()
    conn.close()


def update_database(
    desired_pressure1: float,
    desired_pressure2: float,
    max_cycles1: int,
    max_cycles2: int,
    cycles1: int,
    cycles2: int,
    time_on1: float,
    time_off1: float,
    time_on2: float,
    time_off2: float,
    toggle_state1: bool,
    toggle_state2: bool,
    piston1_on: bool,
    piston1_off: bool,
    piston2_on: bool,
    piston2_off: bool,
    running1: bool,
    running2: bool,
) -> None:
    """Update an existing record in the database."""

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE control_data
        SET desired_pressure1 = ?,
            desired_pressure2 = ?,
            max_cycles1 = ?,
            max_cycles2 = ?,
            cycles1 = ?,
            cycles2 = ?,
            time_on1 = ?,
            time_off1 = ?,
            time_on2 = ?,
            time_off2 = ?,
            toggle_state1 = ?,
            toggle_state2 = ?,
            piston1_on = ?,
            piston1_off = ?,
            piston2_on = ?,
            piston2_off = ?,
            running1 = ?,
            running2 = ?
        WHERE id = 1
        """,
        (
            desired_pressure1,
            desired_pressure2,
            max_cycles1,
            max_cycles2,
            cycles1,
            cycles2,
            time_on1,
            time_off1,
            time_on2,
            time_off2,
            toggle_state1,
            toggle_state2,
            piston1_on,
            piston1_off,
            piston2_on,
            piston2_off,
            running1,
            running2,
        ),
    )
    conn.commit()
    conn.close()


def fetch_latest_record() -> Tuple[Any, ...]:
    """Fetch the latest record from the control_data table."""

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM control_data ORDER BY id DESC LIMIT 1")
    record = cursor.fetchone()
    conn.close()
    if not record:
        insert_initial_record()
        return fetch_latest_record()
    return record


# Ensure the database is ready when this module is imported.
create_table()
if not fetch_latest_record():
    insert_initial_record()