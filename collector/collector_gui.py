from __future__ import annotations

import json
import queue
import threading
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, Button, Checkbutton, Entry, Frame, IntVar, Label, StringVar, Tk, messagebox
from tkinter.ttk import Combobox

from collector import CollectorClient, fetch_collector_entries
from telemetry_sources import GT7TelemetrySource, MockTelemetrySource


CONFIG_PATH = Path.home() / "Documents" / "TRC GT7 Collector" / "collector_config.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


class CollectorApp:
    def __init__(self, root: Tk, default_server: str) -> None:
        self.root = root
        self.root.title("TRC GT7 Collector")
        self.root.geometry("720x560")
        self.root.minsize(620, 500)

        config = load_config()
        self.server_url = StringVar(value=config.get("server_url", default_server))
        self.race_code = StringVar(value=config.get("race_code", "TRC8H"))
        self.team_code = StringVar(value="")
        self.ps5_ip = StringVar(value=config.get("ps5_ip", ""))
        self.use_mock = IntVar(value=0)
        self.status_gt7 = StringVar(value="not connected")
        self.status_server = StringVar(value="not connected")
        self.status_sending = StringVar(value="NO")
        self.last_packet = StringVar(value="-")

        self.entries: list[dict] = []
        self.selected_entry = StringVar()
        self.selected_driver = StringVar()
        self.status_queue: queue.Queue[str] = queue.Queue()
        self.client: CollectorClient | None = None
        self.worker: threading.Thread | None = None

        self.build()
        self.root.after(200, self.poll_status)

    def build(self) -> None:
        outer = Frame(self.root, padx=16, pady=14)
        outer.pack(fill=BOTH, expand=True)

        Label(outer, text="TRC GT7 Collector", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        Label(
            outer,
            text="Reads GT7 telemetry from your local network and sends selected race telemetry to the timing server.",
            fg="#555555",
        ).pack(anchor="w", pady=(0, 14))

        self.row(outer, "Server", Entry(outer, textvariable=self.server_url))

        race_row = Frame(outer)
        race_row.pack(fill="x", pady=5)
        Label(race_row, text="Race Code", width=16, anchor="w").pack(side=LEFT)
        Entry(race_row, textvariable=self.race_code).pack(side=LEFT, fill="x", expand=True)
        Button(race_row, text="Connect", command=self.load_entries).pack(side=RIGHT, padx=(8, 0))

        self.team_box = Combobox(outer, textvariable=self.selected_entry, state="readonly")
        self.row(outer, "Team / Car", self.team_box)
        self.team_box.bind("<<ComboboxSelected>>", lambda _event: self.update_drivers())

        self.driver_box = Combobox(outer, textvariable=self.selected_driver, state="readonly")
        self.row(outer, "Current Driver", self.driver_box)

        self.row(outer, "Team PIN", Entry(outer, textvariable=self.team_code, show="*"))
        self.row(outer, "PlayStation IP", Entry(outer, textvariable=self.ps5_ip))

        mock_row = Frame(outer)
        mock_row.pack(fill="x", pady=6)
        Label(mock_row, text="", width=16).pack(side=LEFT)
        Checkbutton(mock_row, text="Use mock telemetry for testing", variable=self.use_mock).pack(side=LEFT)

        status = Frame(outer, pady=10)
        status.pack(fill="x")
        Label(status, text="Status", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.status_line(status, 1, "GT7 connection", self.status_gt7)
        self.status_line(status, 2, "Server connection", self.status_server)
        self.status_line(status, 3, "Sending data", self.status_sending)
        self.status_line(status, 4, "Last packet", self.last_packet)

        buttons = Frame(outer)
        buttons.pack(fill="x", pady=10)
        Button(buttons, text="Start Sending", command=self.start).pack(side=LEFT)
        Button(buttons, text="Stop", command=self.stop).pack(side=LEFT, padx=8)

        self.log = Entry(outer, state="readonly")
        self.log.pack(fill="x", pady=(10, 0))

        Label(
            outer,
            text=(
                "Not accessed: personal files, microphone, camera, keyboard input, screen capture, browser data. "
                "Only selected race telemetry is sent."
            ),
            wraplength=650,
            fg="#555555",
        ).pack(anchor="w", pady=(16, 0))

    def row(self, parent: Frame, label: str, widget) -> None:
        frame = Frame(parent)
        frame.pack(fill="x", pady=5)
        Label(frame, text=label, width=16, anchor="w").pack(side=LEFT)
        widget.pack(side=LEFT, fill="x", expand=True)

    def status_line(self, parent: Frame, row: int, label: str, value: StringVar) -> None:
        Label(parent, text=f"{label}:", width=18, anchor="w").grid(row=row, column=0, sticky="w")
        Label(parent, textvariable=value, anchor="w", font=("Segoe UI", 10, "bold")).grid(row=row, column=1, sticky="w")

    def load_entries(self) -> None:
        try:
            data = fetch_collector_entries(self.server_url.get(), self.race_code.get().strip().upper())
        except Exception as error:
            messagebox.showerror("Race not found", str(error))
            return

        self.entries = data["entries"]
        labels = [self.entry_label(entry) for entry in self.entries]
        self.team_box["values"] = labels
        if labels:
            self.selected_entry.set(labels[0])
            self.update_drivers()
        self.status_server.set("OK")
        self.set_log(f"Race loaded: {data['race']['name']}")
        self.save_current_config()

    def update_drivers(self) -> None:
        entry = self.current_entry()
        if not entry:
            self.driver_box["values"] = []
            return
        drivers = [f"{driver['driver_id']} - {driver['display_name']}" for driver in entry["drivers"]]
        self.driver_box["values"] = drivers
        if drivers:
            self.selected_driver.set(drivers[0])

    def current_entry(self) -> dict | None:
        selected = self.selected_entry.get()
        for entry in self.entries:
            if self.entry_label(entry) == selected:
                return entry
        return None

    def current_driver_id(self) -> str | None:
        selected = self.selected_driver.get()
        if not selected:
            return None
        return selected.split(" - ", 1)[0]

    def start(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Collector running", "The collector is already sending.")
            return
        entry = self.current_entry()
        driver_id = self.current_driver_id()
        if not entry or not driver_id:
            messagebox.showerror("Missing selection", "Please load a race and select a team and driver.")
            return
        if not self.team_code.get().strip():
            messagebox.showerror("Missing team PIN", "Please enter the team PIN provided by Race Control.")
            return

        source = (
            MockTelemetrySource(update_hz=1.0)
            if self.use_mock.get()
            else GT7TelemetrySource(playstation_ip=self.ps5_ip.get().strip() or None, update_hz=1.0)
        )
        self.client = CollectorClient(
            server_url=self.server_url.get(),
            race_code=self.race_code.get().strip().upper(),
            entry_id=entry["entry_id"],
            driver_id=driver_id,
            team_code=self.team_code.get().strip(),
            source=source,
            status_callback=self.status_queue.put,
        )
        self.status_sending.set("STARTING")
        self.worker = threading.Thread(target=self.run_client, daemon=True)
        self.worker.start()
        self.save_current_config()

    def run_client(self) -> None:
        try:
            self.status_queue.put("GT7 connection: waiting")
            assert self.client is not None
            self.client.run()
        except Exception as error:
            self.status_queue.put(f"ERROR: {error}")
        finally:
            self.status_queue.put("Sending data: NO")

    def stop(self) -> None:
        if self.client:
            self.client.stop()
        self.status_sending.set("NO")
        self.set_log("Collector stopped.")

    def poll_status(self) -> None:
        while True:
            try:
                message = self.status_queue.get_nowait()
            except queue.Empty:
                break
            self.apply_status_message(message)
        self.root.after(200, self.poll_status)

    def apply_status_message(self, message: str) -> None:
        if message.startswith("GT7 connection:"):
            self.status_gt7.set(message.split(":", 1)[1].strip())
        elif message.startswith("Sending data:"):
            self.status_sending.set(message.split(":", 1)[1].strip())
        elif message.startswith("sent "):
            self.status_gt7.set("OK")
            self.status_server.set("OK")
            self.status_sending.set("YES")
            self.last_packet.set(message.removeprefix("sent "))
        elif message.startswith("Connected to timing server"):
            self.status_server.set("OK")
        elif message.startswith("ERROR:"):
            self.status_sending.set("NO")
            self.set_log(message)
            messagebox.showerror("Collector error", message.removeprefix("ERROR: "))
        else:
            self.set_log(message)

    def set_log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.delete(0, END)
        self.log.insert(0, message)
        self.log.configure(state="readonly")

    def save_current_config(self) -> None:
        save_config(
            {
                "server_url": self.server_url.get(),
                "race_code": self.race_code.get().strip().upper(),
                "ps5_ip": self.ps5_ip.get().strip(),
            }
        )

    @staticmethod
    def entry_label(entry: dict) -> str:
        return f"#{entry['car_number']} - {entry['team_name']} - {entry['car_model']}"


def run_gui(default_server: str = "http://localhost:8000") -> None:
    root = Tk()
    CollectorApp(root, default_server)
    root.mainloop()

