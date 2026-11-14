import ctypes
import ctypes.wintypes as wintypes
import json
import os
import struct
import threading
import time
import tkinter as tk
from tkinter import messagebox
import pymem
import pymem.process
import keyboard

PROCESS_NAME = "ocarina.exe"
PRESET_FILE = "nx2navi_preset.json"
TOGGLE_MENU_HOTKEY = "F2"
FULL_HEAL_HOTKEY = "F3"
MAX_RUPEES_HOTKEY = "F4"

DETERMINISTIC_SAVE_ADDR_1 = 0x1BDEEE134
DETERMINISTIC_SAVE_ADDR_2 = 0x1BDEEE138

MEM_COMMIT = 0x1000
PAGE_READWRITE = 0x04
PAGE_EXECUTE_READWRITE = 0x40
PAGE_READONLY = 0x02
PAGE_WRITECOPY = 0x08

EMBEDDED_CHEATS_DATA = {
    "builds": {
        "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348": {
            "save_data": {
                "stride": 40,
                "value_offset": "0x1c"
            },
            "cheats": {
                "inv.gold_skulltulas": {
                    "_name": "Gold Skulltula Tokens",
                    "resolver": "save_hash",
                    "hash": "0x04735978",
                    "index_offset": 103,
                    "type": "u32",
                    "min": 0,
                    "max": 100,
                    "default": 99
                },
                "inv.infinite_arrows": {
                    "_name": "Infinite Arrows",
                    "resolver": "save_hash",
                    "hash": "0x518ec74b",
                    "index_offset": 44,
                    "type": "u32",
                    "on": 99,
                    "freeze": True
                },
                "inv.infinite_beans": {
                    "_name": "Infinite Magic Beans",
                    "resolver": "save_hash",
                    "hash": "0xb003124d",
                    "index_offset": 70,
                    "type": "u32",
                    "on": 99,
                    "freeze": True
                },
                "inv.infinite_scrub_seeds": {
                    "_name": "Infinite Business Scrub Seeds",
                    "resolver": "save_hash",
                    "hash": "0x600e29eb",
                    "index_offset": 95,
                    "type": "u32",
                    "on": 99,
                    "freeze": True
                },
                "inv.infinite_bombchus": {
                    "_name": "Infinite Bombchus",
                    "resolver": "save_hash",
                    "hash": "0xdf7c517a",
                    "index_offset": 49,
                    "type": "u32",
                    "on": 99,
                    "freeze": True
                },
                "inv.infinite_bombs": {
                    "_name": "Infinite Bombs",
                    "resolver": "save_hash",
                    "hash": "0xdb1bcd4f",
                    "index_offset": 45,
                    "type": "u32",
                    "on": 99,
                    "freeze": True
                },
                "inv.infinite_deku_nuts": {
                    "_name": "Infinite Deku Nuts",
                    "resolver": "save_hash",
                    "hash": "0xf30d9f54",
                    "index_offset": 57,
                    "type": "u32",
                    "on": 99,
                    "freeze": True
                },
                "inv.infinite_deku_sticks": {
                    "_name": "Infinite Deku Sticks",
                    "resolver": "save_hash",
                    "hash": "0xb9494411",
                    "index_offset": 59,
                    "type": "u32",
                    "on": 99,
                    "freeze": True
                },
                "inv.infinite_slingshot": {
                    "_name": "Infinite Deku Seeds",
                    "resolver": "save_hash",
                    "hash": "0x5fadf7fc",
                    "index_offset": 58,
                    "type": "u32",
                    "on": 99,
                    "freeze": True
                },
                "player.infinite_health": {
                    "_name": "Infinite Health",
                    "resolver": "signature",
                    "signature": "8055ab31 {main+0x4b63438}",
                    "value_offset": -4,
                    "type": "u32",
                    "on_from_offset": 16,
                    "freeze": True
                },
                "player.infinite_magic": {
                    "_name": "Infinite Magic",
                    "resolver": "signature",
                    "signature": "82b176 973ad612 4933fa3a",
                    "value_offset": 11,
                    "type": "u32",
                    "on": 240,
                    "freeze": True
                },
                "player.infinite_rupees": {
                    "_name": "Infinite Rupees",
                    "resolver": "save_hash",
                    "hash": "0xa77921d7",
                    "index_offset": 0,
                    "type": "u32",
                    "on": 999,
                    "freeze": True
                },
                "player.set_hearts": {
                    "_name": "Heart Containers",
                    "resolver": "signature",
                    "signature": "8055ab31 {main+0x4b63438}",
                    "value_offset": 12,
                    "type": "u32",
                    "scale": 4,
                    "also_write": [-16],
                    "min": 1,
                    "max": 99,
                    "default": 3
                },
                "player.set_rupees": {
                    "_name": "Set Rupees",
                    "resolver": "save_hash",
                    "hash": "0xa77921d7",
                    "index_offset": 0,
                    "type": "u32",
                    "min": 0,
                    "max": 999,
                    "default": 99
                }
            }
        }
    }
}

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("PartitionId", wintypes.WORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]

class NX2NaviCheatEngine:
    def __init__(self):
        build_id = next(iter(EMBEDDED_CHEATS_DATA["builds"]))
        self.build_data = EMBEDDED_CHEATS_DATA["builds"][build_id]
        self.save_cfg = self.build_data["save_data"]
        self.cheats = self.build_data["cheats"]

        self.pm = None
        self.active_toggles = {}
        self.custom_values = {}
        self.cached_addresses = {}

        self.rupee_candidates = []
        self.save_table_rupee_addr = None
        self.status_message = "Initializing memory scanner..."
        self.status_color = "#f9e2af"

        for key, cfg in self.cheats.items():
            self.active_toggles[key] = False
            if "default" in cfg:
                self.custom_values[key] = cfg["default"]
            elif "on" in cfg:
                self.custom_values[key] = cfg["on"]
            else:
                self.custom_values[key] = 99

        self.load_preset()

    def attach(self):
        try:
            self.pm = pymem.Pymem(PROCESS_NAME)
        except Exception as e:
            raise RuntimeError(
                f"Could not find {PROCESS_NAME} running.\n"
                "Please launch NX2navi and load your savegame first."
            ) from e

    def save_preset(self):
        data = {
            "active_toggles": self.active_toggles,
            "custom_values": self.custom_values,
        }
        with open(PRESET_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_preset(self):
        if not os.path.exists(PRESET_FILE):
            return False
        try:
            with open(PRESET_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.get("custom_values", {}).items():
                if k in self.custom_values:
                    self.custom_values[k] = v
            for k, v in data.get("active_toggles", {}).items():
                if k in self.active_toggles:
                    self.active_toggles[k] = bool(v)
            return True
        except Exception:
            return False

    def iter_memory_regions(self):
        address = 0
        mbi = MEMORY_BASIC_INFORMATION()
        kernel32 = ctypes.windll.kernel32
        while kernel32.VirtualQueryEx(
            self.pm.process_handle,
            ctypes.c_void_p(address),
            ctypes.byref(mbi),
            ctypes.sizeof(mbi),
        ):
            if mbi.State == MEM_COMMIT and mbi.Protect in (
                PAGE_READWRITE,
                PAGE_EXECUTE_READWRITE,
                PAGE_READONLY,
                PAGE_WRITECOPY,
            ):
                if mbi.RegionSize and mbi.RegionSize <= 0x100000000:
                    yield mbi.BaseAddress, mbi.RegionSize
            step = mbi.RegionSize or 0x1000
            address += step
            if address >= 0x7FFFFFFFFFFF:
                break

    def auto_locate_save_table(self):
        rec_header = bytes.fromhex("700000000800000001000000000000000000000000000000")
        ammo_header = bytes.fromhex("700000002000000001000000000000000000000000000000")

        try:
            hdr = self.pm.read_bytes(DETERMINISTIC_SAVE_ADDR_1 - 24, 24)
            if hdr == rec_header:
                self.save_table_rupee_addr = DETERMINISTIC_SAVE_ADDR_1
                self.rupee_candidates = [DETERMINISTIC_SAVE_ADDR_1, DETERMINISTIC_SAVE_ADDR_2]
                live_r = self.pm.read_uint(DETERMINISTIC_SAVE_ADDR_1)
                self.status_message = f"Save Table Locked! | Live Rupees: {live_r}"
                self.status_color = "#a6e3a1"
                return
        except Exception:
            pass

        for base, size in self.iter_memory_regions():
            try:
                buf = self.pm.read_bytes(base, size)
                pos = 0
                while True:
                    idx = buf.find(rec_header, pos)
                    if idx == -1 or idx + 2500 > len(buf):
                        break
                    pos = idx + 4

                    if buf[idx + 40 : idx + 64] != rec_header:
                        continue
                    if buf[idx + (59 * 40) : idx + (59 * 40) + 24] != ammo_header:
                        continue

                    val1 = struct.unpack_from("<I", buf, idx + 24)[0]
                    next_val = struct.unpack_from("<I", buf, idx + 64)[0]
                    if 0 <= val1 <= 9999 and 1 <= next_val <= 1000:
                        r1_addr = base + idx + 24
                        r2_addr = base + idx + 28
                        self.save_table_rupee_addr = r1_addr
                        self.rupee_candidates = [r1_addr, r2_addr]
                        self.status_message = f"Save Table Locked! | Live Rupees: {val1}"
                        self.status_color = "#a6e3a1"
                        return
            except Exception:
                continue

        self.status_message = "Auto-scan missed - use Manual Sync below"
        self.status_color = "#f38ba8"

    def scan_rupees(self, target_val):
        target_bytes = struct.pack("<I", int(target_val))
        rec_header = bytes.fromhex("700000000800000001000000000000000000000000000000")

        if not self.rupee_candidates:
            found = []
            for base, size in self.iter_memory_regions():
                try:
                    buf = self.pm.read_bytes(base, size)
                    pos = 0
                    while True:
                        idx = buf.find(target_bytes, pos)
                        if idx == -1:
                            break
                        found.append(base + idx)
                        pos = idx + 4
                except Exception:
                    continue
            self.rupee_candidates = found
        else:
            filtered = []
            for addr in self.rupee_candidates:
                try:
                    if self.pm.read_uint(addr) == int(target_val):
                        filtered.append(addr)
                except Exception:
                    continue
            self.rupee_candidates = filtered

        for addr in self.rupee_candidates:
            try:
                if self.pm.read_bytes(addr - 24, 24) == rec_header:
                    self.save_table_rupee_addr = addr
                    break
                if self.pm.read_bytes(addr - 28, 24) == rec_header:
                    self.save_table_rupee_addr = addr - 4
                    break
            except Exception:
                continue

        if self.save_table_rupee_addr:
            live_r = self.pm.read_uint(self.save_table_rupee_addr)
            self.status_message = f"Save Table Locked! | Live Rupees: {live_r}"
            self.status_color = "#a6e3a1"
        else:
            self.status_message = f"Rupee Finder: {len(self.rupee_candidates)} match(es) - change Rupees & re-scan"
            self.status_color = "#f9e2af"

    def reset_rupee_scan(self):
        self.rupee_candidates = []
        self.save_table_rupee_addr = None
        self.cached_addresses.clear()
        self.status_message = "Scan reset - enter current Rupees & click Scan"
        self.status_color = "#f9e2af"

    def write_save_record_dual(self, base_rupee_addr, index_offset, value):
        stride = self.save_cfg["stride"]
        target_addr = base_rupee_addr + (index_offset * stride)
        self.pm.write_uint(target_addr, int(value))
        self.pm.write_uint(target_addr + 4, int(value))

    def resolve_signature(self, key, cfg):
        if key in self.cached_addresses:
            addr = self.cached_addresses[key]
            try:
                self.pm.read_uint(addr)
                return addr
            except Exception:
                del self.cached_addresses[key]

        sig_str = cfg["signature"]
        if "8055ab31" in sig_str:
            prefix = bytes.fromhex("8055ab31")
            for base, size in self.iter_memory_regions():
                try:
                    buf = self.pm.read_bytes(base, size)
                    pos = 0
                    while True:
                        idx = buf.find(prefix, pos)
                        if idx == -1 or idx + 20 > len(buf):
                            break
                        hit_addr = base + idx + cfg["value_offset"]
                        try:
                            if "on_from_offset" in cfg:
                                max_hp = self.pm.read_uint(hit_addr + cfg["on_from_offset"])
                                cur_hp = self.pm.read_uint(hit_addr)
                                if 4 <= max_hp <= 400 and 0 <= cur_hp <= max_hp:
                                    self.cached_addresses[key] = hit_addr
                                    return hit_addr
                            elif "scale" in cfg:
                                max_hp = self.pm.read_uint(hit_addr)
                                cur_hp = self.pm.read_uint(hit_addr - 16)
                                if 4 <= max_hp <= 400 and 0 <= cur_hp <= max_hp:
                                    self.cached_addresses[key] = hit_addr
                                    return hit_addr
                        except Exception:
                            pass
                        pos = idx + 1
                except Exception:
                    continue
        else:
            p1 = bytes.fromhex("82b176")
            p2 = bytes.fromhex("973ad6124933fa3a")
            for base, size in self.iter_memory_regions():
                try:
                    buf = self.pm.read_bytes(base, size)
                    pos = 0
                    while True:
                        idx = buf.find(p1, pos)
                        if idx == -1 or idx + 16 > len(buf):
                            break
                        if buf[idx + 4 : idx + 12] == p2:
                            hit_addr = base + idx + cfg["value_offset"]
                            self.cached_addresses[key] = hit_addr
                            return hit_addr
                        pos = idx + 1
                except Exception:
                    continue
        return None

    def trigger_instant_full_heal(self):
        if not self.pm:
            return False
        cfg = self.cheats["player.infinite_health"]
        addr = self.resolve_signature("player.infinite_health", cfg)
        if addr:
            max_hp = self.pm.read_uint(addr + cfg["on_from_offset"])
            if 4 <= max_hp <= 400:
                self.pm.write_uint(addr, max_hp)
                return True
        return False

    def trigger_instant_max_rupees(self):
        if not self.pm:
            return False
        wrote = False
        if self.save_table_rupee_addr:
            self.write_save_record_dual(self.save_table_rupee_addr, 0, 999)
            wrote = True
        for r_addr in self.rupee_candidates:
            try:
                self.pm.write_uint(r_addr, 999)
                wrote = True
            except Exception:
                pass
        return wrote

    def apply_tick(self):
        if not self.pm:
            return

        if self.save_table_rupee_addr:
            try:
                live_r = self.pm.read_uint(self.save_table_rupee_addr)
                self.status_message = f"Save Table Locked! | Live Rupees: {live_r}"
                self.status_color = "#a6e3a1"
            except Exception:
                pass

        for key, enabled in list(self.active_toggles.items()):
            if not enabled:
                continue

            cfg = self.cheats[key]
            resolver = cfg.get("resolver")
            val = self.custom_values.get(key)

            try:
                if resolver == "save_hash":
                    if key in ("player.infinite_rupees", "player.set_rupees"):
                        for r_addr in self.rupee_candidates:
                            try:
                                self.pm.write_uint(r_addr, int(val))
                            except Exception:
                                pass
                    if self.save_table_rupee_addr and "index_offset" in cfg:
                        self.write_save_record_dual(
                            self.save_table_rupee_addr, cfg["index_offset"], int(val)
                        )
                    if not cfg.get("freeze", False):
                        self.active_toggles[key] = False

                elif resolver == "signature":
                    addr = self.resolve_signature(key, cfg)
                    if addr:
                        if "on_from_offset" in cfg:
                            max_hp = self.pm.read_uint(addr + cfg["on_from_offset"])
                            if 4 <= max_hp <= 400:
                                self.pm.write_uint(addr, max_hp)
                        elif "scale" in cfg:
                            scaled_val = int(val) * cfg["scale"]
                            self.pm.write_uint(addr, scaled_val)
                            for rel in cfg.get("also_write", []):
                                self.pm.write_uint(addr + rel, scaled_val)
                            if not cfg.get("freeze", False):
                                self.active_toggles[key] = False
                        else:
                            self.pm.write_uint(addr, int(val))
                            if not cfg.get("freeze", False):
                                self.active_toggles[key] = False
            except Exception:
                pass


class TransparentHUDApp:
    def __init__(self, engine: NX2NaviCheatEngine):
        self.engine = engine
        self.root = tk.Tk()
        self.root.title("NX2navi Transparent HUD")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.90)
        self.root.configure(bg="#11111b")

        self.toggle_labels = {}
        self.entries = {}
        self.visible = True
        self._drag_x = 0
        self._drag_y = 0

        self.build_ui()
        self.snap_to_game_window()

        keyboard.add_hotkey(TOGGLE_MENU_HOTKEY, self.toggle_visibility)
        keyboard.add_hotkey(FULL_HEAL_HOTKEY, self.on_hotkey_full_heal)
        keyboard.add_hotkey(MAX_RUPEES_HOTKEY, self.on_hotkey_max_rupees)

    def start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def do_drag(self, event):
        x = self.root.winfo_x() + (event.x - self._drag_x)
        y = self.root.winfo_y() + (event.y - self._drag_y)
        self.root.geometry(f"+{x}+{y}")

    def snap_to_game_window(self):
        try:
            user32 = ctypes.windll.user32
            rect = wintypes.RECT()
            found_hwnd = None

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

            def enum_cb(hwnd, lparam):
                nonlocal found_hwnd
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value.lower()
                        if "ocarina" in title or "nx2navi" in title:
                            found_hwnd = hwnd
                            return False
                return True

            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
            if found_hwnd and user32.GetWindowRect(found_hwnd, ctypes.byref(rect)):
                x = max(0, rect.left + 14)
                y = max(0, rect.top + 38)
                self.root.geometry(f"+{x}+{y}")
                return
        except Exception:
            pass
        self.root.geometry("+20+20")

    def build_ui(self):
        outer = tk.Frame(self.root, bg="#1e1e2e", highlightbackground="#45475a", highlightthickness=1)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg="#181825", pady=6, padx=8)
        header.pack(fill="x")
        header.bind("<Button-1>", self.start_drag)
        header.bind("<B1-Motion>", self.do_drag)

        self.title_lbl = tk.Label(
            header,
            text="NX2navi Trainer",
            bg="#181825",
            fg="#cdd6f4",
            font=("Segoe UI", 10, "bold"),
        )
        self.title_lbl.pack(side="left")
        self.title_lbl.bind("<Button-1>", self.start_drag)
        self.title_lbl.bind("<B1-Motion>", self.do_drag)

        close_btn = tk.Button(
            header,
            text="✕",
            command=self.root.destroy,
            bg="#181825",
            fg="#f38ba8",
            bd=0,
            font=("Segoe UI", 9, "bold"),
            padx=4,
            cursor="hand2",
        )
        close_btn.pack(side="right")

        snap_btn = tk.Button(
            header,
            text="Snap",
            command=self.snap_to_game_window,
            bg="#313244",
            fg="#89b4fa",
            bd=0,
            font=("Segoe UI", 8, "bold"),
            padx=6,
            pady=2,
            cursor="hand2",
        )
        snap_btn.pack(side="right", padx=(0, 4))

        preset_btn = tk.Button(
            header,
            text="Save Preset",
            command=self.on_save_preset,
            bg="#313244",
            fg="#a6e3a1",
            bd=0,
            font=("Segoe UI", 8, "bold"),
            padx=6,
            pady=2,
            cursor="hand2",
        )
        preset_btn.pack(side="right", padx=(0, 4))

        self.status_lbl = tk.Label(
            outer,
            text=self.engine.status_message,
            bg="#1e1e2e",
            fg=self.engine.status_color,
            font=("Segoe UI", 8, "bold"),
            pady=4,
        )
        self.status_lbl.pack(fill="x")

        scan_frame = tk.Frame(outer, bg="#181825", pady=5, padx=8)
        scan_frame.pack(fill="x", padx=8, pady=(0, 4))

        tk.Label(
            scan_frame,
            text="Manual Sync:",
            bg="#181825",
            fg="#bac2de",
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left")

        self.rupee_scan_ent = tk.Entry(
            scan_frame, width=7, bg="#313244", fg="#cdd6f4", insertbackground="white", bd=0
        )
        self.rupee_scan_ent.pack(side="left", padx=5, ipady=2)

        tk.Button(
            scan_frame,
            text="Scan",
            command=self.on_scan_rupees,
            bg="#89b4fa",
            fg="#11111b",
            font=("Segoe UI", 8, "bold"),
            bd=0,
            padx=8,
            pady=2,
            cursor="hand2",
        ).pack(side="left", padx=(0, 4))

        tk.Button(
            scan_frame,
            text="Reset",
            command=self.on_reset_scan,
            bg="#45475a",
            fg="#cdd6f4",
            font=("Segoe UI", 8),
            bd=0,
            padx=6,
            pady=2,
            cursor="hand2",
        ).pack(side="left")

        container = tk.Frame(outer, bg="#1e1e2e", padx=10, pady=4)
        container.pack(fill="both", expand=True)

        for key, cfg in self.engine.cheats.items():
            row = tk.Frame(container, bg="#1e1e2e", pady=2)
            row.pack(fill="x")

            is_on = self.engine.active_toggles.get(key, False)
            box_txt = "☑" if is_on else "☐"
            box_fg = "#a6e3a1" if is_on else "#6c7086"

            btn_lbl = tk.Label(
                row,
                text=f" {box_txt}  {cfg['_name']}",
                bg="#1e1e2e",
                fg=box_fg if is_on else "#cdd6f4",
                font=("Segoe UI", 9, "bold" if is_on else "normal"),
                cursor="hand2",
                anchor="w",
            )
            btn_lbl.pack(side="left", fill="x", expand=True)
            btn_lbl.bind("<Button-1>", lambda e, k=key: self.on_toggle_click(k))
            self.toggle_labels[key] = btn_lbl

            if "min" in cfg:
                ent = tk.Entry(
                    row, width=6, bg="#313244", fg="#cdd6f4", insertbackground="white", bd=0
                )
                ent.insert(0, str(self.engine.custom_values[key]))
                ent.pack(side="right", ipady=1)
                self.entries[key] = ent

        footer = tk.Label(
            outer,
            text="F2: Hide/Show  |  F3: Full Heal  |  F4: 999 Rupees",
            bg="#181825",
            fg="#9399b2",
            font=("Segoe UI", 8),
            pady=5,
        )
        footer.pack(fill="x", pady=(4, 0))

        self.root.update_idletasks()
        w = max(360, self.root.winfo_reqwidth() + 12)
        h = self.root.winfo_reqheight() + 8
        self.root.geometry(f"{w}x{h}")

    def refresh_toggle_visual(self, key):
        lbl = self.toggle_labels.get(key)
        if not lbl:
            return
        is_on = self.engine.active_toggles.get(key, False)
        cfg = self.engine.cheats[key]
        box_txt = "☑" if is_on else "☐"
        lbl.config(
            text=f" {box_txt}  {cfg['_name']}",
            fg="#a6e3a1" if is_on else "#cdd6f4",
            font=("Segoe UI", 9, "bold" if is_on else "normal"),
        )

    def on_toggle_click(self, key):
        if key in self.entries:
            try:
                val = int(float(self.entries[key].get()))
                self.engine.custom_values[key] = val
            except ValueError:
                pass
        new_state = not self.engine.active_toggles.get(key, False)
        self.engine.active_toggles[key] = new_state
        self.refresh_toggle_visual(key)

    def on_save_preset(self):
        for key, ent in self.entries.items():
            try:
                self.engine.custom_values[key] = int(float(ent.get()))
            except ValueError:
                pass
        self.engine.save_preset()
        self.flash_banner("Preset Saved!", "#a6e3a1")

    def on_hotkey_full_heal(self):
        if self.engine.trigger_instant_full_heal():
            self.root.after(0, self.flash_banner, "F3: Full Health Restored!", "#a6e3a1")

    def on_hotkey_max_rupees(self):
        if self.engine.trigger_instant_max_rupees():
            self.root.after(0, self.flash_banner, "F4: Rupees Set to 999!", "#f9e2af")

    def flash_banner(self, text, color):
        self.title_lbl.config(text=text, fg=color)
        self.root.after(2000, lambda: self.title_lbl.config(text="NX2navi Trainer", fg="#cdd6f4"))

    def on_scan_rupees(self):
        try:
            val = int(self.rupee_scan_ent.get().strip())
        except ValueError:
            self.status_lbl.config(text="Enter a valid integer Rupee count", fg="#f38ba8")
            return
        self.engine.scan_rupees(val)
        self.status_lbl.config(text=self.engine.status_message, fg=self.engine.status_color)

    def on_reset_scan(self):
        self.engine.reset_rupee_scan()
        self.status_lbl.config(text=self.engine.status_message, fg=self.engine.status_color)

    def toggle_visibility(self):
        self.root.after(0, self._do_toggle)

    def _do_toggle(self):
        if self.visible:
            self.root.withdraw()
            self.visible = False
        else:
            self.root.deiconify()
            self.snap_to_game_window()
            self.visible = True

    def worker_loop(self):
        self.engine.auto_locate_save_table()
        while True:
            self.engine.apply_tick()
            self.root.after(
                0,
                lambda: self.status_lbl.config(
                    text=self.engine.status_message, fg=self.engine.status_color
                ),
            )
            for key in self.toggle_labels:
                self.root.after(0, self.refresh_toggle_visual, key)
            time.sleep(0.05)

    def run(self):
        t = threading.Thread(target=self.worker_loop, daemon=True)
        t.start()
        self.root.mainloop()


if __name__ == "__main__":
    try:
        engine = NX2NaviCheatEngine()
        engine.attach()
        app = TransparentHUDApp(engine)
        app.run()
    except Exception as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("NX2navi Trainer Error", str(e))
