"""
Skill Spammer Background - Motor 4RTools
Fixes aplicados:
  1. lParam con scan code real  (MapVirtualKeyW)
  2. AttachThreadInput           (sincroniza hilo con ventana del juego)
  3. Escaneo de ventana hija     (el motor gráfico recibe input en child HWND)
  4. Auto-reconexión             (re-escanea si el HWND se vuelve inválido)
  5. Auto-elevacion UAC          (se relanza como Admin si no lo es)
"""
import sys
import ctypes
import os

# ── Auto-elevación a Administrador ───────────────────────────────────────────
# AttachThreadInput + PostMessage a procesos con GameGuard REQUIEREN admin.
# Si no somos admin, relanzamos el script pidiendo UAC automáticamente.
def _is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def _relaunch_as_admin():
    """Relanza este mismo script con ShellExecute 'runas' (UAC prompt)."""
    if getattr(sys, 'frozen', False):
        # Si es un .exe compilado por PyInstaller
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1
        )
    else:
        # Si se ejecuta como .py
        script = os.path.abspath(sys.argv[0])
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}" {params}', None, 1
        )
    sys.exit(0)

if not _is_admin():
    _relaunch_as_admin()
# ─────────────────────────────────────────────────────────────────────────────

import tkinter as tk
from tkinter import ttk
import ctypes.wintypes as wt
import time
import threading

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

PostMessageW = user32.PostMessageW
PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
PostMessageW.restype = wt.BOOL

SendNotifyMessageW = user32.SendNotifyMessageW
SendNotifyMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
SendNotifyMessageW.restype = wt.BOOL

MapVirtualKeyW = user32.MapVirtualKeyW
MapVirtualKeyW.argtypes = [wt.UINT, wt.UINT]
MapVirtualKeyW.restype = wt.UINT

AttachThreadInput = user32.AttachThreadInput
AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
AttachThreadInput.restype = wt.BOOL

GetCurrentThreadId = kernel32.GetCurrentThreadId
GetCurrentThreadId.restype = wt.DWORD

GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
GetWindowThreadProcessId.restype = wt.DWORD

# ── Win32 ────────────────────────────────────────────────────────────────────
WM_KEYDOWN = 0x0100
WM_KEYUP   = 0x0101

VK_CODES = {
    '0':0x30,'1':0x31,'2':0x32,'3':0x33,'4':0x34,
    '5':0x35,'6':0x36,'7':0x37,'8':0x38,'9':0x39,
    'F1':0x70,'F2':0x71,'F3':0x72,'F4':0x73,'F5':0x74,'F6':0x75,
    'F7':0x76,'F8':0x77,'F9':0x78,'F10':0x79,'F11':0x7A,'F12':0x7B,
    'A':0x41,'B':0x42,'C':0x43,'D':0x44,'E':0x45,'F':0x46,'G':0x47,
    'H':0x48,'I':0x49,'J':0x4A,'K':0x4B,'L':0x4C,'M':0x4D,'N':0x4E,
    'O':0x4F,'P':0x50,'Q':0x51,'R':0x52,'S':0x53,'T':0x54,'U':0x55,
    'V':0x56,'W':0x57,'X':0x58,'Y':0x59,'Z':0x5A,
    'INSERT':0x2D,'DELETE':0x2E,'HOME':0x24,'END':0x23,
    'PAGEUP':0x21,'PAGEDOWN':0x22,
    'NUMPAD0':0x60,'NUMPAD1':0x61,'NUMPAD2':0x62,'NUMPAD3':0x63,
    'NUMPAD4':0x64,'NUMPAD5':0x65,'NUMPAD6':0x66,'NUMPAD7':0x67,
    'NUMPAD8':0x68,'NUMPAD9':0x69,
    'TAB':0x09,'SPACE':0x20,'ESCAPE':0x1B,
}
TRIGGER_VK = {
    'CAPS_LOCK':0x14,'SCROLL_LOCK':0x91,'PAUSE':0x13,
    'F1':0x70,'F2':0x71,'F3':0x72,'F4':0x73,'F5':0x74,
    'F6':0x75,'F7':0x76,'F8':0x77,'F9':0x78,'F10':0x79,
    'F11':0x7A,'F12':0x7B,
    'NUMPAD0':0x60,'NUMPAD1':0x61,'NUMPAD2':0x62,
    'INSERT':0x2D,'HOME':0x24,'PAGEUP':0x21,
}

# ── Helpers Win32 ─────────────────────────────────────────────────────────────

def _is_hwnd_valid(hwnd: int) -> bool:
    return bool(user32.IsWindow(hwnd))

def get_hwnds_by_title(title: str):
    results = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, ctypes.c_void_p)
    def _cb(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if n > 0:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if title.lower() in buf.value.lower():
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                results.append((hwnd, buf.value, pid.value))
        return True
    user32.EnumWindows(WNDENUMPROC(_cb), 0)
    return results


# Códigos de error Win32 comunes para PostMessage
_WIN32_ERRORS = {
    0:    "OK",
    5:    "ERROR_ACCESS_DENIED — proceso elevado, ejecuta como Admin",
    6:    "ERROR_INVALID_HANDLE — HWND inválido",
    1400: "ERROR_INVALID_WINDOW_HANDLE — ventana cerrada o recreada",
    1816: "ERROR_NOT_ENOUGH_QUOTA — cola de mensajes llena (juego bloqueado)",
    8:    "ERROR_NOT_ENOUGH_MEMORY",
}

_post_stats = {"ok": 0, "fail": 0}   # contador global para el watchdog

def make_lparam(vk: int, is_keyup: bool) -> int:
    scan_code = MapVirtualKeyW(vk, 0)
    repeat = 1
    extended = 0
    context = 0
    prev_state = 1 if is_keyup else 0
    transition = 1 if is_keyup else 0

    lparam = (repeat & 0xFFFF) | \
             ((scan_code & 0xFF) << 16) | \
             ((extended & 1) << 24) | \
             ((context & 1) << 29) | \
             ((prev_state & 1) << 30) | \
             ((transition & 1) << 31)
    return lparam & 0xFFFFFFFF

def post_key(hwnd: int, vk: int) -> tuple[bool, int]:
    """
    Motor v2: lParam scan_code + AttachThreadInput + WM_KEYDOWN/UP
    Devuelve (exito: bool, error_code: int)
    """
    my_tid = GetCurrentThreadId()
    target_tid = GetWindowThreadProcessId(hwnd, None)
    
    attached = False
    if target_tid != 0 and target_tid != my_tid:
        attached = AttachThreadInput(my_tid, target_tid, True)

    lp_down = make_lparam(vk, False)
    lp_up   = make_lparam(vk, True)

    r1 = SendNotifyMessageW(hwnd, WM_KEYDOWN, vk, lp_down)
    err1 = ctypes.get_last_error()
    
    time.sleep(0.01) # Pequeño delay entre down/up
    
    r2 = SendNotifyMessageW(hwnd, WM_KEYUP, vk, lp_up)
    err2 = ctypes.get_last_error()

    if attached:
        AttachThreadInput(my_tid, target_tid, False)

    ok = bool(r1 and r2)
    if ok:
        _post_stats["ok"] += 1
    else:
        _post_stats["fail"] += 1
        
    return ok, err1 if not r1 else err2


def post_sequence(hwnd: int, vk_list: list, delay_s: float) -> list[tuple]:
    """Envía secuencia y retorna lista de (vk, ok, err) para logging."""
    results = []
    for vk in vk_list:
        ok, err = post_key(hwnd, vk)
        results.append((vk, ok, err))
        time.sleep(delay_s)
    return results


def diagnose_hwnd(hwnd: int) -> dict:
    """Diagnóstico completo de una ventana: retorna dict con todos los estados."""
    valid   = bool(user32.IsWindow(hwnd))
    visible = bool(user32.IsWindowVisible(hwnd)) if valid else False
    enabled = bool(user32.IsWindowEnabled(hwnd))  if valid else False
    iconic  = bool(user32.IsIconic(hwnd))          if valid else False  # minimizada

    # Obtener título actual
    title = ""
    if valid:
        n = user32.GetWindowTextLengthW(hwnd)
        if n > 0:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            title = buf.value

    # Obtener PID y TID
    pid = ctypes.c_ulong(0)
    tid = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)) if valid else 0

    # Enviar tecla de prueba (VK_F15 — tecla que el juego no usa)
    test_ok, test_err = (False, 0)
    if valid:
        # Forzar creación de message queue para este hilo (requerido para AttachThreadInput a veces)
        msg = wt.MSG()
        user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 0)

        vk_test = 0x7E # VK_F15
        lp_down = make_lparam(vk_test, False)
        lp_up   = make_lparam(vk_test, True)

        # Prueba 1: SIN AttachThreadInput (Usando SendNotifyMessageW)
        r_noatt_1 = SendNotifyMessageW(hwnd, WM_KEYDOWN, vk_test, lp_down)
        e_noatt_1 = ctypes.get_last_error()
        r_noatt_2 = SendNotifyMessageW(hwnd, WM_KEYUP, vk_test, lp_up)
        e_noatt_2 = ctypes.get_last_error()

        # Prueba 2: CON AttachThreadInput
        my_tid = GetCurrentThreadId()
        target_tid = tid
        attached = False
        if target_tid != 0 and target_tid != my_tid:
            attached = AttachThreadInput(my_tid, target_tid, True)

        r_att_1 = SendNotifyMessageW(hwnd, WM_KEYDOWN, vk_test, lp_down)
        e_att_1 = ctypes.get_last_error()
        r_att_2 = SendNotifyMessageW(hwnd, WM_KEYUP, vk_test, lp_up)
        e_att_2 = ctypes.get_last_error()

        if attached:
            AttachThreadInput(my_tid, target_tid, False)

        test_ok = bool(r_att_1 and r_att_2) or bool(r_noatt_1 and r_noatt_2)
        test_err = e_att_1 if not r_att_1 else e_att_2
        desc_str = f"SNM_NOATT: r1={bool(r_noatt_1)}({e_noatt_1}) r2={bool(r_noatt_2)}({e_noatt_2}) | SNM_ATT: r1={bool(r_att_1)}({e_att_1}) r2={bool(r_att_2)}({e_att_2})"

    return {
        "hwnd":    hwnd,
        "valid":   valid,
        "visible": visible,
        "enabled": enabled,
        "iconic":  iconic,
        "title":   title,
        "pid":     pid.value,
        "tid":     tid,
        "post_ok": test_ok,
        "post_err": test_err,
        "err_desc": desc_str,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  GUI
# ══════════════════════════════════════════════════════════════════════════════
BG = "#1a1a2e"; PANEL = "#16213e"; ACCENT = "#0f3460"
HIGHLIGHT = "#e94560"; FG = "#eaeaea"
GREEN = "#4caf50"; RED = "#f44336"; YELLOW = "#f9a825"; GREY = "#888888"


class SkillSpammerApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Skill Spammer Engine v1.1 - Presets")
        self.geometry("620x760")
        self.resizable(False, False)
        self.configure(bg=BG)

        self._clients      = []
        self._spam_active  = False
        self.presets       = self._load_presets()

        self._build_ui()
        self._start_hwnd_watchdog()

    def _load_presets(self):
        import json
        try:
            with open("skill_spammer_presets.json", "r") as f:
                return json.load(f)
        except:
            return {"Default": "F1"}

    def _save_presets(self):
        import json
        try:
            with open("skill_spammer_presets.json", "w") as f:
                json.dump(self.presets, f, indent=4)
        except Exception as e:
            self._log_msg(f"Error guardando presets: {e}")

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("P.TLabelframe",       background=PANEL, padding=8)
        s.configure("P.TLabelframe.Label", background=PANEL, foreground=HIGHLIGHT,
                    font=("Segoe UI", 9, "bold"))
        s.configure("TLabel",      background=PANEL, foreground=FG)
        s.configure("TEntry",      fieldbackground=ACCENT, foreground=FG, insertcolor=FG)
        s.configure("TCheckbutton",background=PANEL, foreground=FG)
        s.configure("TCombobox",   fieldbackground=ACCENT, foreground=FG)
        s.map("TCombobox", fieldbackground=[("readonly", ACCENT)])
        s.configure("TScrollbar",  troughcolor=PANEL, background=ACCENT)
        s.configure("TRadiobutton",background=PANEL, foreground=FG)

        w = tk.Frame(self, bg=BG, padx=12, pady=10)
        w.pack(fill="both", expand=True)

        # Header
        h = tk.Frame(w, bg=BG)
        h.pack(fill="x", pady=(0, 8))
        tk.Label(h, text="⚡ Skill Spammer Background", bg=BG, fg=HIGHLIGHT,
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        tk.Label(h, text="Github  Darkfelipow-dot", bg=BG, fg=GREY,
                 font=("Segoe UI", 8)).pack(side="right", pady=6)

        # ── Presets ────────────────────────────────────────────────────────────
        fp = ttk.LabelFrame(w, text="1. Presets de Secuencias", style="P.TLabelframe")
        fp.pack(fill="x", pady=4)
        
        pr_f = tk.Frame(fp, bg=PANEL); pr_f.pack(fill="x", pady=2)
        tk.Label(pr_f, text="Nombre:", bg=PANEL, fg=FG).pack(side="left", padx=2)
        self._preset_name_var = tk.StringVar()
        ttk.Entry(pr_f, textvariable=self._preset_name_var, width=14).pack(side="left", padx=2)
        
        tk.Label(pr_f, text="Teclas:", bg=PANEL, fg=FG).pack(side="left", padx=2)
        self._preset_keys_var = tk.StringVar()
        ttk.Entry(pr_f, textvariable=self._preset_keys_var, width=18).pack(side="left", padx=2)
        
        tk.Button(pr_f, text="💾 Guardar", command=self._save_preset,
                  bg=ACCENT, fg=FG, activebackground=HIGHLIGHT, relief="flat", padx=6).pack(side="left", padx=4)
        tk.Button(pr_f, text="❌ Borrar", command=self._delete_preset,
                  bg=RED, fg="#fff", relief="flat", padx=4).pack(side="left", padx=2)

        # ── 1. Escanear ────────────────────────────────────────────────────────
        f1 = ttk.LabelFrame(w, text="2. Clientes Ragnarok", style="P.TLabelframe")
        f1.pack(fill="x", pady=4)

        sr = tk.Frame(f1, bg=PANEL); sr.pack(fill="x")
        tk.Label(sr, text="Título:", bg=PANEL, fg=FG).pack(side="left")
        self._title_var = tk.StringVar(value="Ragnarok")
        ttk.Entry(sr, textvariable=self._title_var, width=16).pack(side="left", padx=6)
        tk.Button(sr, text="🔍 Escanear", command=self._scan,
                  bg=ACCENT, fg=FG, activebackground=HIGHLIGHT,
                  relief="flat", padx=8).pack(side="left")

        # tabla
        self._canvas = tk.Canvas(f1, bg=PANEL, height=140, highlightthickness=0)
        _sb = ttk.Scrollbar(f1, orient="vertical", command=self._canvas.yview)
        self._tbl = tk.Frame(self._canvas, bg=PANEL)
        self._tbl.bind("<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.create_window((0,0), window=self._tbl, anchor="nw")
        self._canvas.configure(yscrollcommand=_sb.set)
        self._canvas.pack(side="left", fill="both", expand=True, pady=(4,0))
        _sb.pack(side="right", fill="y", pady=(4,0))

        hdr = tk.Frame(self._tbl, bg=PANEL); hdr.pack(fill="x")
        for t,ww in [("✓",2),("HWND",8),("Ventana",14),("Preset",12),("Teclas",12),("Estado",8)]:
            tk.Label(hdr, text=t, bg=PANEL, fg=GREY, font=("Segoe UI",8,"bold"), width=ww).pack(side="left", padx=2)

        # ── 2. Config ──────────────────────────────────────────────────────────
        f2 = ttk.LabelFrame(w, text="3. Configuración", style="P.TLabelframe")
        f2.pack(fill="x", pady=4)

        for r,(lbl,attr,val) in enumerate([
            ("Delay entre teclas (ms):","delay_ms","100"),
            ("Repeticiones por disparo:","reps","1"),
        ]):
            tk.Label(f2, text=lbl, bg=PANEL, fg=FG).grid(row=r,column=0,sticky="e",padx=8,pady=3)
            v = tk.StringVar(value=val)
            setattr(self, f"_{attr}_var", v)
            ttk.Entry(f2, textvariable=v, width=8).grid(row=r,column=1,sticky="w",padx=4)

        # ── 3. Disparador ──────────────────────────────────────────────────────
        f3 = ttk.LabelFrame(w, text="4. Disparador (hotkey global)", style="P.TLabelframe")
        f3.pack(fill="x", pady=4)

        tk.Label(f3, text="Tecla:", bg=PANEL, fg=FG).grid(row=0,column=0,padx=8,pady=4,sticky="e")
        self._trig_var = tk.StringVar(value="CAPS_LOCK")
        ttk.Combobox(f3, textvariable=self._trig_var,
                     values=list(TRIGGER_VK.keys()), state="readonly", width=14
                     ).grid(row=0,column=1,padx=4,pady=4,sticky="w")

        self._mode_var = tk.StringVar(value="hold")
        tk.Label(f3, text="Modo:", bg=PANEL, fg=FG).grid(row=0,column=2,padx=8)
        fm = tk.Frame(f3, bg=PANEL); fm.grid(row=0,column=3,padx=4)
        for t,v in [("Mantener","hold"),("Toggle","toggle")]:
            ttk.Radiobutton(fm, text=t, variable=self._mode_var, value=v).pack(side="left",padx=4)

        # ── Estado ────────────────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="⬛  Inactivo")
        self._status_lbl = tk.Label(w, textvariable=self._status_var,
                                    bg=BG, fg=GREY, font=("Segoe UI",11,"bold"))
        self._status_lbl.pack(pady=4)

        # ── Botones ───────────────────────────────────────────────────────────
        br = tk.Frame(w, bg=BG); br.pack(fill="x", pady=2)
        self._btn_fire = tk.Button(br, text="▶ UNA VEZ",
                                   command=self._fire_once,
                                   bg=ACCENT, fg=FG, activebackground=HIGHLIGHT,
                                   font=("Segoe UI",10,"bold"), relief="flat",
                                   padx=6, pady=6)
        self._btn_fire.pack(side="left", padx=4, expand=True, fill="x")

        self._btn_loop = tk.Button(br, text="⏺ ACTIVAR LOOP",
                                   command=self._toggle_loop,
                                   bg=GREEN, fg="#fff", activebackground="#388e3c",
                                   font=("Segoe UI",10,"bold"), relief="flat",
                                   padx=6, pady=6)
        self._btn_loop.pack(side="left", padx=4, expand=True, fill="x")

        self._btn_diag = tk.Button(br, text="🔬 Diagnosticar",
                                   command=self._run_diagnostics,
                                   bg="#4a148c", fg=FG, activebackground="#6a1b9a",
                                   font=("Segoe UI",10,"bold"), relief="flat",
                                   padx=6, pady=6)
        self._btn_diag.pack(side="left", padx=4, expand=True, fill="x")

        self._stats_var = tk.StringVar(value="Enviados: 0 OK | 0 FAIL")
        tk.Label(w, textvariable=self._stats_var, bg=BG, fg=GREY,
                 font=("Consolas", 8)).pack(anchor="e", padx=6)

        # ── Log ───────────────────────────────────────────────────────────────
        fl = ttk.LabelFrame(w, text="Log de Diagnóstico", style="P.TLabelframe")
        fl.pack(fill="both", expand=True, pady=4)
        self._log = tk.Text(fl, bg=PANEL, fg=FG, height=6, insertbackground=FG,
                            relief="flat", font=("Consolas",8), state="disabled")
        self._log.tag_configure("ok",   foreground="#4caf50")
        self._log.tag_configure("fail", foreground="#f44336")
        self._log.tag_configure("warn", foreground="#f9a825")
        self._log.tag_configure("info", foreground="#64b5f6")
        self._log.tag_configure("sep",  foreground="#444466")
        sbl = ttk.Scrollbar(fl, command=self._log.yview)
        self._log.configure(yscrollcommand=sbl.set)
        self._log.pack(side="left", fill="both", expand=True)
        sbl.pack(side="right", fill="y")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Presets ───────────────────────────────────────────────────────────────
    def _save_preset(self):
        name = self._preset_name_var.get().strip()
        keys = self._preset_keys_var.get().strip()
        if name and keys:
            self.presets[name] = keys
            self._save_presets()
            self._log_msg(f"✅ Preset '{name}' guardado ({keys}).")
            self._update_all_comboboxes()

    def _delete_preset(self):
        name = self._preset_name_var.get().strip()
        if name in self.presets:
            del self.presets[name]
            self._save_presets()
            self._preset_name_var.set("")
            self._preset_keys_var.set("")
            self._log_msg(f"🗑 Preset '{name}' eliminado.")
            self._update_all_comboboxes()
            
    def _update_all_comboboxes(self):
        for c in self._clients:
            if "cb_preset" in c:
                c["cb_preset"]['values'] = list(self.presets.keys())

    # ── helpers ───────────────────────────────────────────────────────────────
    def _log_msg(self, msg, tag=""):
        self._log.configure(state="normal")
        ts = time.strftime("%H:%M:%S")
        full = f"[{ts}] {msg}\n"
        if tag:
            self._log.insert("end", full, tag)
        else:
            self._log.insert("end", full)
        self._log.see("end")
        self._log.configure(state="disabled")
        self.after(0, lambda: self._stats_var.set(
            f"Enviados: {_post_stats['ok']} OK | {_post_stats['fail']} FAIL"
        ))

    def _set_status(self, text, color):
        self.after(0, lambda: [
            self._status_var.set(text),
            self._status_lbl.configure(fg=color)
        ])

    def _get_cfg(self):
        try:    delay = max(10, int(self._delay_ms_var.get())) / 1000.0
        except: delay = 0.1
        try:    reps = max(1, int(self._reps_var.get()))
        except: reps = 1
        return delay, reps

    def _collect_targets(self):
        out = []
        for c in self._clients:
            if not c["var_chk"].get(): continue
            raw = [k.strip().upper() for k in c["var_seq"].get().split(",") if k.strip()]
            vks = [VK_CODES[k] for k in raw if k in VK_CODES]
            if vks:
                out.append((c["hwnd"], vks))
        return out

    # ── HWND watchdog ─────────────────────────────────────────────────────────
    def _start_hwnd_watchdog(self):
        def _watch():
            while True:
                time.sleep(3)
                for c in self._clients:
                    valid = _is_hwnd_valid(c["hwnd"])
                    color = GREEN if valid else RED
                    text  = "OK" if valid else "INVALID"
                    lbl: tk.Label = c.get("lbl_status")
                    if lbl:
                        try:
                            self.after(0, lambda l=lbl, cl=color, tx=text:
                                       l.configure(fg=cl, text=tx))
                        except: pass
                    if not valid and self._clients:
                        self.after(0, self._silent_rescan)
        threading.Thread(target=_watch, daemon=True).start()

    def _silent_rescan(self):
        title = self._title_var.get().strip()
        results = get_hwnds_by_title(title)
        for c in self._clients:
            for hwnd, wt_title, _ in results:
                if c["title"][:22] in wt_title or wt_title in c["title"]:
                    if c["hwnd"] != hwnd:
                        self._log_msg(f"♻  HWND actualizado: {c['hwnd']} → {hwnd}")
                        c["hwnd"] = hwnd

    # ── escanear ─────────────────────────────────────────────────────────────
    def _scan(self):
        children = self._tbl.winfo_children()
        for ch in children[1:]:
            ch.destroy()
        self._clients.clear()

        results = get_hwnds_by_title(self._title_var.get().strip())
        if not results:
            self._log_msg("❌ No se encontraron ventanas.")
            return

        for hwnd, title, pid in results:
            var_chk = tk.BooleanVar(value=True)
            var_seq = tk.StringVar(value="F1")
            
            rf = tk.Frame(self._tbl, bg=PANEL); rf.pack(fill="x")
            ttk.Checkbutton(rf, variable=var_chk).pack(side="left", padx=2)
            tk.Label(rf, text=str(hwnd), bg=PANEL, fg=GREY, font=("Consolas",8), width=8).pack(side="left", padx=2)
            tk.Label(rf, text=title[:16], bg=PANEL, fg=FG, font=("Segoe UI",8), width=16, anchor="w").pack(side="left",padx=2)
            
            cb_preset = ttk.Combobox(rf, values=list(self.presets.keys()), state="readonly", width=12)
            cb_preset.pack(side="left", padx=2)
            
            ttk.Entry(rf, textvariable=var_seq, width=12).pack(side="left", padx=2)
            
            lbl_ok = tk.Label(rf, text="OK", fg=GREEN, bg=PANEL, font=("Segoe UI",8,"bold"), width=8)
            lbl_ok.pack(side="left", padx=2)
            
            def on_preset_select(e, v=var_seq, cb=cb_preset):
                preset_name = cb.get()
                if preset_name in self.presets:
                    v.set(self.presets[preset_name])
                    self._preset_name_var.set(preset_name)
                    self._preset_keys_var.set(self.presets[preset_name])
                    
            cb_preset.bind("<<ComboboxSelected>>", on_preset_select)

            self._clients.append({
                "hwnd": hwnd, "title": title,
                "var_chk": var_chk, "var_seq": var_seq,
                "lbl_status": lbl_ok, "cb_preset": cb_preset
            })
            self._log_msg(f"✅ [{hwnd}] {title[:30]}")

    # ── Diagnóstico ───────────────────────────────────────────────────────────
    def _run_diagnostics(self):
        if not self._clients:
            self._log_msg("⚠  Escanea primero.", "warn")
            return
        def _diag():
            self._log_msg("─" * 48, "sep")
            self._log_msg("🔬 DIAGNÓSTICO COMPLETO", "info")
            for c in self._clients:
                hwnd = c["hwnd"]
                d = diagnose_hwnd(hwnd)
                self._log_msg(f"HWND [{hwnd}] — {d['title'][:28]}", "info")
                vs = "✅ Válida"   if d["valid"]   else "❌ INVÁLIDA"
                es = "✅ Activa"   if d["enabled"] else "❌ Desactivada (bloqueada?)"
                is_ = "⚠  Minimizada" if d["iconic"] else "✅ Normal"
                self._log_msg(f"  Ventana : {vs}", "ok" if d["valid"] else "fail")
                self._log_msg(f"  Estado  : {es}  {is_}",
                              "ok" if d["enabled"] and not d["iconic"] else "warn")
                self._log_msg(f"  PID/TID : {d['pid']} / {d['tid']}", "info")
                if d["post_ok"]:
                    self._log_msg(f"  PostMsg : ✅ OK — {d['err_desc']}", "ok")
                else:
                    self._log_msg(f"  PostMsg : ❌ FALLO — {d['err_desc']}", "fail")
            self._log_msg(f"  Stats   : {_post_stats['ok']} OK / {_post_stats['fail']} FAIL",
                          "ok" if _post_stats["fail"] == 0 else "warn")
            self._log_msg("─" * 48, "sep")
        threading.Thread(target=_diag, daemon=True).start()

    # ── disparar una vez ──────────────────────────────────────────────────────
    def _fire_once(self):
        targets = self._collect_targets()
        if not targets:
            self._log_msg("⚠  Escanea y configura una secuencia primero.", "warn")
            return
        delay, reps = self._get_cfg()
        self._btn_fire.configure(state="disabled")

        def _run():
            def _spam_one(hwnd, vks):
                for _ in range(reps):
                    results = post_sequence(hwnd, vks, delay)
                    fails = [(vk, err) for vk, ok, err in results if not ok]
                    if fails:
                        for vk, err in fails:
                            desc = _WIN32_ERRORS.get(err, f"#{err}")
                            self._log_msg(f"❌ [{hwnd}] VK=0x{vk:02X} FAIL — {desc}", "fail")
                    else:
                        self._log_msg(f"✅ [{hwnd}] Enviado OK", "ok")

            threads = []
            for hwnd, vks in targets:
                t = threading.Thread(target=_spam_one, args=(hwnd, vks), daemon=True)
                t.start()
                threads.append(t)
            
            for t in threads:
                t.join()

            self.after(0, lambda: self._btn_fire.configure(state="normal"))

        threading.Thread(target=_run, daemon=True).start()

    # ── loop ──────────────────────────────────────────────────────────────────
    def _toggle_loop(self):
        if self._spam_active:
            self._spam_active = False
            self._btn_loop.configure(text="⏺ ACTIVAR LOOP",
                                     bg=GREEN, activebackground="#388e3c")
            self._log_msg("🔴 Loop detenido.")
            self._set_status("⬛  Inactivo", GREY)
        else:
            targets = self._collect_targets()
            if not targets:
                self._log_msg("⚠  Escanea y configura una secuencia primero.")
                return
            self._spam_active = True
            self._btn_loop.configure(text="⏹ DETENER LOOP",
                                     bg=RED, activebackground="#c62828")
            self._log_msg("🟢 Loop activado.")
            delay, reps = self._get_cfg()
            trigger_vk  = TRIGGER_VK.get(self._trig_var.get(), 0x14)
            mode        = self._mode_var.get()

            def _monitor():
                toggle_on = False
                was_down  = False
                while self._spam_active:
                    pressed = bool(user32.GetAsyncKeyState(trigger_vk) & 0x8000)
                    if mode == "hold":
                        active = pressed
                    else:
                        if pressed and not was_down:
                            toggle_on = not toggle_on
                        active = toggle_on
                    was_down = pressed

                    if active:
                        self._set_status("🟢  SPAMEANDO", GREEN)
                        cur_targets = self._collect_targets()
                        
                        def _spam_one(h, v):
                            for _ in range(reps):
                                if not self._spam_active: break
                                post_sequence(h, v, delay)

                        threads = []
                        for hwnd, vks in cur_targets:
                            if not self._spam_active: break
                            t = threading.Thread(target=_spam_one, args=(hwnd, vks), daemon=True)
                            t.start()
                            threads.append(t)
                        
                        for t in threads:
                            t.join()
                    else:
                        self._set_status("🟡  Esperando disparador", YELLOW)
                    time.sleep(0.02)
                self._set_status("⬛  Inactivo", GREY)

            threading.Thread(target=_monitor, daemon=True).start()

    def _on_close(self):
        self._spam_active = False
        self.destroy()


if __name__ == "__main__":
    app = SkillSpammerApp()
    app.mainloop()
