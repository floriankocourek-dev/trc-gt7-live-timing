from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["TRC_DB_PATH"] = str(Path(tempfile.gettempdir()) / "trc_sector_logic_test.sqlite3")

from server.app import main as app  # noqa: E402


def check(name: str, ok: bool, detail: str = "") -> None:
    marker = "PASS" if ok else "FAIL"
    print(f"[{marker}] {name}{f' - {detail}' if detail else ''}")
    if not ok:
        raise AssertionError(name)


def seed_race(conn, race_id: str, sector_count: int) -> None:
    now = app.now_iso()
    conn.execute(
        """
        INSERT INTO races (race_id, name, track_id, duration_minutes, start_time, event_type,
                           drivers_per_team, classes_json, sector_count, red_threshold_ms, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (race_id, race_id, "test_track", 60, None, "team", 1, json.dumps(["GT3"]), sector_count, 500, "running", now),
    )
    conn.execute(
        """
        INSERT INTO entries (entry_id, race_id, car_number, team_name, car_model, car_class,
                             drivers_json, team_code_hash, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"{race_id}_car",
            race_id,
            23,
            "Sector Test",
            "Test Car",
            "GT3",
            json.dumps([{"driver_id": "florian", "display_name": "Florian"}]),
            app.hash_value("TEST"),
            "active",
            now,
        ),
    )


def main() -> int:
    db_path = Path(os.environ["TRC_DB_PATH"])
    if db_path.exists():
        db_path.unlink()
    app.init_db()

    with app.db() as conn:
        seed_race(conn, "SEC3", 3)
        seed_race(conn, "SEC4", 4)

        sec3 = app.ensure_sector_definitions(conn, "SEC3")
        sec4 = app.ensure_sector_definitions(conn, "SEC4")
        check("race with sector_count=3 creates S1/S2/S3", [row["sector_number"] for row in sec3] == [1, 2, 3])
        check("race with sector_count=4 creates S1/S2/S3/S4", [row["sector_number"] for row in sec4] == [1, 2, 3, 4])
        check("sector 4 boundaries use progress", sec4[1]["start_progress"] == 0.25 and sec4[1]["end_progress"] == 0.5)

        points = app.add_reference_progress(
            [
                {"x": 0.0, "y": 0.0, "z": 0.0},
                {"x": 1.0, "y": 0.0, "z": 0.0},
                {"x": 4.0, "y": 0.0, "z": 0.0},
            ]
        )
        check("reference progress is distance based", points[1]["progress"] == 0.25, f"progress={points[1]['progress']}")

        now = app.now_iso()
        app.insert_sector_crossing(conn, "SEC3", "SEC3_car", "florian", 12, 1, 25521, now)
        app.insert_sector_crossing(conn, "SEC3", "SEC3_car", "florian", 12, 2, 58221, now)
        app.insert_sector_crossing(conn, "SEC3", "SEC3_car", "florian", 12, 2, 58221, now)
        app.finalize_lap_sectors(conn, "SEC3", "SEC3_car", "florian", 12, 80566, now)

        crossings = conn.execute(
            "SELECT * FROM sector_crossings WHERE entry_id = ? AND lap = ? ORDER BY sector_number",
            ("SEC3_car", 12),
        ).fetchall()
        check("no duplicate crossing events", len(crossings) == 3)
        sector_times = [row["sector_time_ms"] for row in crossings]
        check("sector times are differences, not cumulative splits", sector_times == [25521, 32700, 22345], str(sector_times))

        summary = conn.execute(
            "SELECT * FROM lap_sector_summaries WHERE entry_id = ? AND lap = ?",
            ("SEC3_car", 12),
        ).fetchone()
        check("complete lap sector summary is stored", summary["sector_status"] == "complete")

    display = app.build_sector_display("SEC3", "SEC3_car", 13, 0.1, "public")
    check("public current sector shows calc.", display["sector_display"][0]["state"] == "calculating")
    check("public future sectors use previous lap", display["sector_display"][1]["source"] == "previous_lap")

    engineer = app.build_sector_display("SEC3", "SEC3_car", 13, 0.1, "engineer")
    check("engineer future sectors show not reached", engineer["sector_display"][1]["state"] == "not_reached")

    print("Sector logic checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
