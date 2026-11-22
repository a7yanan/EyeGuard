# -*- coding: utf-8 -*-
"""EyeGuard setup window. It shows the modern install pages and copies the program,
shortcuts and uninstall entry itself. If the window cannot start, it installs silently."""
import ctypes
import json
import shutil
import math
import os
import random
import subprocess
import sys
import threading
import time
import traceback
import webbrowser

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

# ══════════════════ EDIT ONLY THIS BLOCK FOR A NEW PROGRAM ══════════════════
APP = "EyeGuard"                       # program name: shown in the UI, Program Files folder, log names
EXE_NAME = "EyeGuard.exe"              # the installed program's exe
APP_VERSION = "1.2.55"
UNINSTALL_KEY = APP
CONFIG_DIR_NAME = "EyeGuard"           # %APPDATA%\<this>\config.json may hold {"theme": "emerald"} (accent color)
DEFAULT_THEME = "amber"                # emerald | indigo | cyan | violet | rose | amber
WELCOME_LINES = ("Protect your eyes from screen glare,",
                 "one warm light at a time.")
SETUP_SUBTITLE = "Choose how EyeGuard is installed."
LAUNCH_SUB = "Open EyeGuard right after setup"
DONE_LINE = "EyeGuard is installed and running in your tray."
AUTHOR_URL = "https://x.com/3omar_a7yanan"   # click target of the "made by a7yanan" credit
# ═════════════════════════════════════════════════════════════════════════════

LW, LH = 640, 420            # logical window size
CORNER = 30                  # window corner radius
KEY = (1, 1, 1)              # transparent key color (the corners)
BG_TOP, BG_BOT = (17, 19, 25), (11, 12, 16)
CARD, CARD_LINE = (24, 26, 33), (40, 43, 55)
TEXT, MUTED, DIM = (242, 244, 248), (139, 144, 160), (84, 88, 102)
RED = (244, 63, 94)
THEMES = {"emerald": "#10b981", "indigo": "#6366f1", "cyan": "#06b6d4",
          "violet": "#a855f7", "rose": "#f43f5e", "amber": "#f59e0b"}

BX, BY, BR = 566, 350, 34    # the round "Next" button (logical coords)
CX0, CW = 48, 544            # cards
CARD_Y = (126, 186, 246)
CARD_H = 50
CREATE_NO_WINDOW = 0x08000000

S = 1.0                      # DPI scale, set at start
MC = {}                      # mask cache
_FC = {}                     # font cache


# ───────────────────────────── helpers ─────────────────────────────
def px(v):
    return int(round(v * S))


def res(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(round(a[i] * (1 - t) + b[i] * t)) for i in range(3))


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def load_accent():
    try:
        p = os.path.join(os.environ.get("APPDATA", ""), CONFIG_DIR_NAME, "config.json")
        with open(p, "r", encoding="utf-8") as f:
            name = json.load(f).get("theme", DEFAULT_THEME)
    except Exception:
        name = DEFAULT_THEME
    return hex2rgb(THEMES.get(name, THEMES["emerald"]))


def font(size, bold=False):
    key = (size, bold, S)
    if key not in _FC:
        names = (["segoeuib.ttf", "seguisb.ttf", "DejaVuSans-Bold.ttf"] if bold
                 else ["segoeui.ttf", "DejaVuSans.ttf"])
        f = None
        for n in names:
            try:
                f = ImageFont.truetype(n, px(size))
                break
            except Exception:
                pass
        _FC[key] = f or ImageFont.load_default()
    return _FC[key]


def log(msg):
    try:
        p = os.path.join(os.environ.get("TEMP", "."), APP + "_setup_ui.log")
        with open(p, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")
    except Exception:
        pass


CHOSEN_DIR = None          # set when the user picks another folder on the options page


def install_dir():
    if CHOSEN_DIR:
        return CHOSEN_DIR
    base = os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles") or r"C:\Program Files"
    return os.path.join(base, APP)


def installed_exe():
    return os.path.join(install_dir(), EXE_NAME)


# ───────────────────────── masks & drawing ─────────────────────────
def m_rr(w, h, r):
    k = ("rr", w, h, r)
    if k not in MC:
        ss = 4
        im = Image.new("L", (max(1, w) * ss, max(1, h) * ss), 0)
        ImageDraw.Draw(im).rounded_rectangle((0, 0, max(1, w) * ss - 1, max(1, h) * ss - 1),
                                             radius=r * ss, fill=255)
        MC[k] = im.reduce(ss)
    return MC[k]


def m_circle(d):
    k = ("c", d)
    if k not in MC:
        ss = 4
        im = Image.new("L", (d * ss, d * ss), 0)
        ImageDraw.Draw(im).ellipse((0, 0, d * ss - 1, d * ss - 1), fill=255)
        MC[k] = im.reduce(ss)
    return MC[k]


def m_ring(d, wpx):
    k = ("ring", d, wpx)
    if k not in MC:
        ss = 4
        im = Image.new("L", (d * ss, d * ss), 0)
        dr = ImageDraw.Draw(im)
        dr.ellipse((0, 0, d * ss - 1, d * ss - 1), fill=255)
        w = int(wpx * ss)
        dr.ellipse((w, w, d * ss - 1 - w, d * ss - 1 - w), fill=0)
        MC[k] = im.reduce(ss)
    return MC[k]


def m_blob(d, blur):
    k = ("blob", d, blur)
    if k not in MC:
        pad = blur * 2
        size = d + pad * 2
        im = Image.new("L", (size, size), 0)
        ImageDraw.Draw(im).ellipse((pad, pad, pad + d - 1, pad + d - 1), fill=255)
        MC[k] = im.filter(ImageFilter.GaussianBlur(blur))
    return MC[k]


def m_text(txt, size, bold):
    k = ("t", txt, size, bold, S)
    if k not in MC:
        f = font(size, bold)
        tw = int(f.getlength(txt))
        asc, desc = f.getmetrics()
        im = Image.new("L", (tw + 8, asc + desc + 8), 0)
        ImageDraw.Draw(im).text((4, 4), txt, font=f, fill=255)
        MC[k] = (im, tw, asc + desc)
    return MC[k]


def m_gtext(txt, size, blur):
    k = ("gt", txt, size, blur, S)
    if k not in MC:
        f = font(size, True)
        tw = int(f.getlength(txt))
        asc, desc = f.getmetrics()
        pad = blur * 3
        im = Image.new("L", (tw + pad * 2, asc + desc + pad * 2), 0)
        ImageDraw.Draw(im).text((pad, pad), txt, font=f, fill=255)
        MC[k] = (im.filter(ImageFilter.GaussianBlur(blur)), pad, tw, asc + desc)
    return MC[k]


def m_cross(d, wpx):
    k = ("x", d, wpx)
    if k not in MC:
        ss = 4
        im = Image.new("L", (d * ss, d * ss), 0)
        dr = ImageDraw.Draw(im)
        m = d * ss * 0.18
        w = int(wpx * ss)
        dr.line((m, m, d * ss - m, d * ss - m), fill=255, width=w)
        dr.line((d * ss - m, m, m, d * ss - m), fill=255, width=w)
        MC[k] = im.reduce(ss)
    return MC[k]


def m_check(d, p_ring, p_tick):
    """Animated 'done' circle + tick, p_* in 0..1 (quantised so it caches)."""
    qr, qt = int(p_ring * 30), int(p_tick * 30)
    k = ("chk", d, qr, qt)
    if k not in MC:
        ss = 4
        im = Image.new("L", (d * ss, d * ss), 0)
        dr = ImageDraw.Draw(im)
        w = int(px(4) * ss)
        if qr > 0:
            dr.arc((w // 2, w // 2, d * ss - w // 2 - 1, d * ss - w // 2 - 1), -90, -90 + 360 * qr / 30,
                   fill=255, width=w)
        if qt > 0:
            c = d * ss / 2
            pts = [(c - d * ss * 0.20, c + d * ss * 0.02), (c - d * ss * 0.06, c + d * ss * 0.17),
                   (c + d * ss * 0.22, c - d * ss * 0.14)]
            seg1 = math.dist(pts[0], pts[1])
            seg2 = math.dist(pts[1], pts[2])
            tot = (seg1 + seg2) * qt / 30
            path = [pts[0]]
            if tot <= seg1:
                f = tot / seg1
                path.append((pts[0][0] + (pts[1][0] - pts[0][0]) * f, pts[0][1] + (pts[1][1] - pts[0][1]) * f))
            else:
                path.append(pts[1])
                f = (tot - seg1) / seg2
                path.append((pts[1][0] + (pts[2][0] - pts[1][0]) * f, pts[1][1] + (pts[2][1] - pts[1][1]) * f))
            tw = int(px(5) * ss)
            dr.line(path, fill=255, width=tw, joint="curve")
            for (x, y) in (path[0], path[-1]):
                dr.ellipse((x - tw / 2, y - tw / 2, x + tw / 2, y + tw / 2), fill=255)
        MC[k] = im.reduce(ss)
    return MC[k]


def ma(m, a):
    """mask scaled by alpha (cached)"""
    if a >= 0.995:
        return m
    q = int(round(a * 32))
    if q <= 0:
        return None
    k = ("a", id(m), q)
    if k not in MC:
        lut = [int(i * q / 32) for i in range(256)]
        MC[k] = m.point(lut)
    return MC[k]


def put(fr, fill, mask, x, y):
    if mask is None:
        return
    w, h = mask.size
    fw, fh = fr.size
    x0, y0, x1, y1 = max(0, x), max(0, y), min(fw, x + w), min(fh, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    m = mask.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    if isinstance(fill, tuple):
        fr.paste(fill, (x0, y0, x1, y1), m)
    else:
        fr.paste(fill.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0), m)


def T(fr, txt, size, bold, col, x, y, a=1.0, dx=0.0, align="l"):
    im, tw, _ = m_text(txt, size, bold)
    X, Y = px(x + dx), px(y)
    if align == "c":
        X -= tw // 2
    elif align == "r":
        X -= tw
    put(fr, col, ma(im, a), X - 4, Y - 4)


def tw_logical(txt, size, bold):
    return m_text(txt, size, bold)[1] / S


def RR(fr, x, y, w, h, r, col, a=1.0, dx=0.0):
    put(fr, col, ma(m_rr(px(w), px(h), px(r)), a), px(x + dx), px(y))


def CARDW(fr, x, y, w, h, a=1.0, dx=0.0):
    RR(fr, x, y, w, h, 14, CARD_LINE, a, dx)
    RR(fr, x + 1, y + 1, w - 2, h - 2, 13, CARD, a, dx)


def CIRCLE(fr, cx, cy, rad, col, a=1.0, dx=0.0):
    d = px(rad * 2)
    put(fr, col, ma(m_circle(d), a), px(cx + dx) - d // 2, px(cy) - d // 2)


def RING(fr, cx, cy, rad, width, col, a=1.0, dx=0.0):
    d = px(rad * 2)
    put(fr, col, ma(m_ring(d, max(1.0, width * S)), a), px(cx + dx) - d // 2, px(cy) - d // 2)


def GLOW(fr, cx, cy, d, blur, col, a=1.0, dx=0.0):
    dd, bb = px(d), px(blur)
    m = m_blob(dd, bb)
    put(fr, col, ma(m, a), px(cx + dx) - m.size[0] // 2, px(cy) - m.size[1] // 2)


_LOGO = {}


def logo_parts(size_px):
    if size_px not in _LOGO:
        try:
            im = Image.open(res("logo.png")).convert("RGBA").resize((size_px, size_px), Image.LANCZOS)
            _LOGO[size_px] = (im.convert("RGB"), im.getchannel("A"))
        except Exception:
            _LOGO[size_px] = None
    return _LOGO[size_px]


def LOGO(fr, cx, cy, size, a=1.0, dx=0.0):
    parts = logo_parts(px(size))
    if not parts:
        return
    rgb, al = parts
    put(fr, rgb, ma(al, a), px(cx + dx) - rgb.size[0] // 2, px(cy) - rgb.size[1] // 2)


def make_base(W, H):
    top = Image.new("RGB", (W, H), BG_TOP)
    bot = Image.new("RGB", (W, H), BG_BOT)
    grad = Image.linear_gradient("L").resize((W, H))
    base = Image.composite(bot, top, grad)
    border = ImageChops.subtract(m_rr(W, H, px(CORNER)), _inner(W, H))
    put(base, (44, 47, 60), border, 0, 0)
    return base


def _inner(W, H):
    inner = Image.new("L", (W, H), 0)
    inner.paste(m_rr(W - 2, H - 2, px(CORNER) - 1), (1, 1))
    return inner


# ───────────────────────────── the app ─────────────────────────────
class App:
    def __init__(self):
        global S
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        try:
            S = max(1.0, min(2.5, ctypes.windll.user32.GetDpiForSystem() / 96.0))
        except Exception:
            S = 1.0
        import tkinter as tk
        from PIL import ImageTk
        self.tk = tk
        self.W, self.H = px(LW), px(LH)
        self.acc = load_accent()
        self.acc_l = mix(self.acc, (255, 255, 255), 0.38)
        self.acc2 = mix(self.acc, (99, 102, 241), 0.55)

        self.page = 0
        self.trans = None            # (old, new, t0, dir)
        self.t0 = time.perf_counter()
        self.t = 0.0
        self.last = self.t0
        self.hover = None
        self.press = None
        self.mouse = None
        self.hv = {k: 0.0 for k in ("next", "back", "close", "author", "tog_desktop", "tog_launch")}
        self.pv = 0.0
        self.tog = {"desktop": [True, 1.0], "launch": [True, 1.0]}
        self.stepf = 0.0
        self.prog = 0.0
        self.install_t0 = None
        self.engine_rc = None
        self.install_started = False
        self.fail_text = ""
        self.done_t0 = None
        self.quitting = False
        self.drag = None
        self.cursor = ""
        rnd = random.Random(7)
        self.parts = [(rnd.random(), rnd.uniform(14, 30), rnd.uniform(2.0, 4.2), rnd.random() * 6.28,
                       rnd.uniform(0.07, 0.17)) for _ in range(9)]

        self.base = make_base(self.W, self.H)
        self.corner_inv = ImageChops.invert(m_rr(self.W, self.H, px(CORNER)))

        root = tk.Tk()
        self.root = root
        root.withdraw()
        root.title(APP + " Setup")
        root.overrideredirect(True)
        key_hex = "#%02x%02x%02x" % KEY
        root.configure(bg=key_hex)
        try:
            root.attributes("-transparentcolor", key_hex)
        except Exception:
            pass
        try:
            root.iconbitmap(res("app.ico"))
        except Exception:
            pass
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry("%dx%d+%d+%d" % (self.W, self.H, (sw - self.W) // 2, max(0, (sh - self.H) // 2 - 20)))
        cv = tk.Canvas(root, width=self.W, height=self.H, bg=key_hex, highlightthickness=0, bd=0)
        cv.pack()
        self.cv = cv
        self.photo = ImageTk.PhotoImage(Image.new("RGB", (self.W, self.H), KEY))
        cv.create_image(0, 0, image=self.photo, anchor="nw")
        cv.bind("<Motion>", self.on_move)
        cv.bind("<Leave>", self.on_leave)
        cv.bind("<Button-1>", self.on_press)
        cv.bind("<B1-Motion>", self.on_drag)
        cv.bind("<ButtonRelease-1>", self.on_release)
        root.bind("<Return>", lambda e: self.activate("next"))
        root.bind("<Escape>", lambda e: self.activate("close"))
        root.protocol("WM_DELETE_WINDOW", lambda: self.activate("close"))

    # ---- life cycle
    def run(self):
        self.tick()
        self.root.after(30, self._show)
        self.root.mainloop()

    def _show(self):
        try:
            u32 = ctypes.windll.user32
            u32.GetParent.restype = ctypes.c_void_p
            u32.GetParent.argtypes = [ctypes.c_void_p]
            u32.GetWindowLongW.restype = ctypes.c_long
            u32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
            u32.SetWindowLongW.restype = ctypes.c_long
            u32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
            hwnd = u32.GetParent(self.root.winfo_id())
            st = u32.GetWindowLongW(hwnd, -20)
            u32.SetWindowLongW(hwnd, -20, (st & ~0x80) | 0x40000)   # show in taskbar
        except Exception:
            pass
        self.root.deiconify()
        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(400, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
        except Exception:
            pass

    def quit(self):
        self.quitting = True
        try:
            self.root.destroy()
        except Exception:
            pass

    # ---- input
    def to_logical(self, e):
        return e.x / S, e.y / S

    def hit(self, lx, ly):
        if self.trans:
            return None
        p = self.page
        if math.hypot(lx - (LW - 34), ly - 34) <= 16:
            return "close"
        if p in (0, 1, 3) and math.hypot(lx - BX, ly - BY) <= BR:
            return "next"
        if p == 1:
            if 40 <= lx <= 116 and BY - 16 <= ly <= BY + 16:
                return "back"
            if CX0 <= lx <= CX0 + CW and CARD_Y[0] <= ly <= CARD_Y[0] + CARD_H:
                return "pick_dir"
            if CX0 <= lx <= CX0 + CW:
                if CARD_Y[1] <= ly <= CARD_Y[1] + CARD_H:
                    return "tog_desktop"
                if CARD_Y[2] <= ly <= CARD_Y[2] + CARD_H:
                    return "tog_launch"
            wa = tw_logical("Made by ", 12, False)
            wb = tw_logical("a7yanan", 12, True)
            x0 = LW / 2 - (wa + wb) / 2 + wa
            if x0 - 4 <= lx <= x0 + wb + 4 and 340 <= ly <= 364:
                return "author"
        return None

    def on_move(self, e):
        lx, ly = self.to_logical(e)
        self.mouse = (lx, ly)
        self.hover = self.hit(lx, ly)

    def on_leave(self, e):
        self.mouse = None
        self.hover = None

    def on_press(self, e):
        lx, ly = self.to_logical(e)
        self.press = self.hit(lx, ly)
        if self.press is None and ly < 64:
            self.drag = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def on_drag(self, e):
        if self.drag:
            self.root.geometry("+%d+%d" % (e.x_root - self.drag[0], e.y_root - self.drag[1]))

    def on_release(self, e):
        lx, ly = self.to_logical(e)
        name = self.hit(lx, ly)
        pressed, self.press, self.drag = self.press, None, None
        if name and name == pressed:
            self.activate(name)

    def activate(self, name):
        if self.trans:
            return
        p = self.page
        if name == "close":
            if p != 2:
                self.quit()
        elif name == "next":
            if p == 0:
                self.go(1)
            elif p == 1:
                self.start_install()
                self.go(2)
            elif p == 3:
                if self.fail_text == "" and self.tog["launch"][0]:
                    self.launch_app()
                self.quit()
        elif name == "back" and p == 1:
            self.go(0)
        elif name == "tog_desktop" and p == 1:
            self.tog["desktop"][0] = not self.tog["desktop"][0]
        elif name == "tog_launch" and p == 1:
            self.tog["launch"][0] = not self.tog["launch"][0]
        elif name == "author" and p == 1:
            webbrowser.open(AUTHOR_URL)
        elif name == "pick_dir" and p == 1:
            self.pick_folder()

    def pick_folder(self):
        global CHOSEN_DIR
        try:
            import tkinter.filedialog as fd
            base = os.path.dirname(install_dir()) or "C:\\"
            chosen = fd.askdirectory(parent=self.root, initialdir=base,
                                     title="Choose the folder where %s will be installed" % APP)
            if chosen:
                CHOSEN_DIR = os.path.normpath(os.path.join(chosen, APP))
                log("install folder: %s" % CHOSEN_DIR)
        except Exception:
            log("folder picker failed:\n" + traceback.format_exc())

    def go(self, new):
        if new == self.page:
            return
        d = 1 if new > self.page else -1
        self.trans = (self.page, new, self.t, d)
        self.old_page = self.page
        if new == 3:
            self.done_t0 = self.t + 0.25

    # ---- install engine
    def start_install(self):
        self.install_started = True
        self.install_t0 = self.t
        self.engine_rc = None
        threading.Thread(target=self._run_engine, daemon=True).start()

    def _run_engine(self):
        try:
            subprocess.run(["taskkill", "/F", "/IM", EXE_NAME], creationflags=CREATE_NO_WINDOW,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        try:
            install_files(self.tog["desktop"][0])
            self.engine_rc = 0
            log("install finished")
        except Exception:
            log("install error:\n" + traceback.format_exc())
            self.fail_text = "Could not copy the files. Try again as administrator."
            self.engine_rc = -1

    def launch_app(self):
        try:
            ctypes.windll.shell32.ShellExecuteW(None, "open", installed_exe(), None, None, 1)
        except Exception as ex:
            log("launch error: %r" % ex)

    # ---- animation loop
    def tick(self):
        if self.quitting:
            return
        t_start = time.perf_counter()
        now = t_start
        self.t = now - self.t0
        dt = min(0.1, now - self.last)
        self.last = now

        if self.trans and self.t - self.trans[2] >= 0.45:
            self.page = self.trans[1]
            self.trans = None

        # hover / press easing
        for k in self.hv:
            self.hv[k] += ((1.0 if self.hover == k else 0.0) - self.hv[k]) * min(1.0, dt * 12)
        self.pv += ((1.0 if (self.press == "next" and self.hover == "next") else 0.0) - self.pv) * min(1.0, dt * 20)
        for v in self.tog.values():
            v[1] += ((1.0 if v[0] else 0.0) - v[1]) * min(1.0, dt * 14)
        tgt = {0: 0, 1: 1, 2: 2, 3: 2}[(self.trans[1] if self.trans else self.page)]
        self.stepf += (tgt - self.stepf) * min(1.0, dt * 7)

        # install progress
        if self.install_started and not self.trans and self.page == 2:
            e = self.t - self.install_t0
            auto = 0.92 * (1 - math.exp(-e / 3.0))
            if self.engine_rc is None:
                self.prog += (auto - self.prog) * min(1.0, dt * 6)
            elif self.engine_rc == 0:
                self.prog += (1.0 - self.prog) * min(1.0, dt * 7)
                if self.prog > 0.995 and e > 2.2:
                    self.go(3)
            else:
                if not self.fail_text:
                    self.fail_text = "Setup failed (code %s)" % self.engine_rc
                self.go(3)

        try:
            self.photo.paste(self.render())
        except Exception:
            log("render error:\n" + traceback.format_exc())
        want = "hand2" if self.hover else ""
        if want != self.cursor:
            self.cursor = want
            try:
                self.cv.config(cursor=want)
            except Exception:
                pass
        spent = int((time.perf_counter() - t_start) * 1000)
        self.root.after(max(1, 33 - spent), self.tick)

    # ---- rendering
    def pa(self, page):
        """alpha of a page (handles the slide/fade transition)"""
        if self.trans:
            old, new, t0, _ = self.trans
            e = ease_out((self.t - t0) / 0.45)
            if page == old:
                return 1 - e
            if page == new:
                return e
            return 0.0
        return 1.0 if page == self.page else 0.0

    def pdx(self, page):
        if self.trans:
            old, new, t0, d = self.trans
            e = ease_out((self.t - t0) / 0.45)
            if page == old:
                return -d * 40 * e
            if page == new:
                return d * 40 * (1 - e)
        return 0.0

    def render(self):
        fr = self.base.copy()
        t = self.t
        acc = self.acc

        # ambient lights (slow drift)
        GLOW(fr, LW * 0.26 + math.sin(t / 9.0) * 70, LH * 0.30 + math.cos(t / 7.0) * 36, 300, 70, acc, 0.20)
        GLOW(fr, LW * 0.80 + math.cos(t / 11.0) * 60, LH * 0.82 + math.sin(t / 8.0) * 30, 260, 64, self.acc2, 0.14)
        for (x0, spd, size, ph, al) in self.parts:
            y = LH + 12 - ((t * spd + ph * 300) % (LH + 24))
            x = x0 * LW + math.sin(t * 0.5 + ph) * 14
            CIRCLE(fr, x, y, size / 2, mix(acc, (255, 255, 255), 0.5), al)

        # pages
        for p in (0, 1, 2, 3):
            a = self.pa(p)
            if a > 0.01:
                getattr(self, "page%d" % p)(fr, a, self.pdx(p))

        # brand row (top-left) + close button
        LOGO(fr, 40, 34, 22, 0.95)
        T(fr, APP, 13, True, MUTED, 58, 24)
        ch = self.hv["close"]
        cl_a = 0.3 if self.page == 2 else 1.0
        CIRCLE(fr, LW - 34, 34, 16, CARD, ch * cl_a)
        put(fr, mix(MUTED, TEXT, ch), ma(m_cross(px(12), 1.6 * S), cl_a), px(LW - 34) - px(12) // 2, px(34) - px(12) // 2)

        self.draw_next(fr)
        self.draw_back(fr, self.pa(1))
        self.draw_dots(fr)

        fr.paste(KEY, (0, 0), self.corner_inv)
        return fr

    # --- shared widgets
    def draw_next(self, fr):
        labels = {0: "Next", 1: "Install", 3: "Close" if self.fail_text else "Finish"}
        disk_a = min(1.0, sum(self.pa(p) for p in labels))
        if disk_a < 0.01:
            return
        t, h, acc = self.t, self.hv["next"], self.acc
        # blurred lights orbiting behind the black disk
        for ph, col in ((0.0, acc), (math.pi, self.acc_l)):
            ang = t * 0.55 + ph
            GLOW(fr, BX + math.cos(ang) * 17, BY + math.sin(ang) * 17, 84, 16, col, (0.48 + 0.38 * h) * disk_a)
        GLOW(fr, BX, BY, 84, 20, acc, (0.14 + 0.22 * h) * disk_a)
        rad = BR * (1 - 0.06 * self.pv) * (1 + 0.025 * h)
        CIRCLE(fr, BX, BY, rad, (0, 0, 0), disk_a)
        RING(fr, BX, BY, rad, 1.4, acc, (0.30 + 0.55 * h) * disk_a)
        for p, label in labels.items():
            a = self.pa(p)
            if a < 0.01:
                continue
            gm, pad, tw, th = m_gtext(label, 14, px(5))
            pulse = 0.60 + 0.25 * math.sin(t * 1.8) + 0.30 * h
            X, Y = px(BX) - tw // 2, px(BY) - th // 2
            put(fr, acc, ma(gm, min(1.0, pulse) * a), X - pad, Y - pad)
            im, tw2, _ = m_text(label, 14, True)
            put(fr, self.acc_l, ma(im, a), X - 4, Y - 4)

    def draw_back(self, fr, a):
        if a < 0.01:
            return
        h = self.hv["back"]
        RR(fr, 40, BY - 16, 76, 32, 16, CARD_LINE, h * a)
        RR(fr, 41, BY - 15, 74, 30, 15, CARD, h * a)
        T(fr, "Back", 13, False, mix(MUTED, TEXT, h), 78, BY - 10, a, 0, "c")

    def draw_dots(self, fr):
        x = LW / 2 - 28
        for i in range(3):
            k = max(0.0, 1 - abs(self.stepf - i))
            w = 8 + 16 * k
            RR(fr, x, LH - 26, w, 8, 4, mix((46, 49, 62), self.acc, k), 0.55 + 0.45 * k)
            x += w + 8

    # --- pages
    def page0(self, fr, a, dx):
        t, acc = self.t, self.acc
        GLOW(fr, 320, 124, 170, 46, acc, (0.34 + 0.10 * math.sin(t * 1.3)) * a, dx)
        LOGO(fr, 320, 124, 112, a, dx)
        T(fr, APP, 36, True, TEXT, 320, 196, a, dx, "c")
        T(fr, WELCOME_LINES[0], 14, False, MUTED, 320, 254, a, dx, "c")
        T(fr, WELCOME_LINES[1], 14, False, MUTED, 320, 276, a, dx, "c")

    def page1(self, fr, a, dx):
        acc = self.acc
        T(fr, "Setup", 26, True, TEXT, 48, 62, a, dx)
        T(fr, SETUP_SUBTITLE, 13, False, MUTED, 48, 98, a, dx)
        # card 1: location
        y = CARD_Y[0]
        CARDW(fr, CX0, y, CW, CARD_H, a, dx)
        RR(fr, CX0 + 14, y + 11, 28, 28, 9, mix(CARD, acc, 0.22), a, dx)
        RR(fr, CX0 + 21, y + 19, 14, 11, 3, acc, a, dx)
        T(fr, "INSTALL LOCATION  ·  click to change", 10, True, DIM, CX0 + 54, y + 8, a, dx)
        path = install_dir()
        while tw_logical(path, 13, False) > 440 and len(path) > 8:
            path = path[:-2]
        T(fr, path if path == install_dir() else path + "…", 13, False, TEXT, CX0 + 54, y + 24, a, dx)
        # cards 2,3: toggles
        for i, (key, title, sub) in enumerate((("desktop", "Desktop shortcut", "Add an icon to your desktop"),
                                               ("launch", "Launch when finished", LAUNCH_SUB))):
            y = CARD_Y[i + 1]
            hv = self.hv["tog_" + key]
            CARDW(fr, CX0, y, CW, CARD_H, a, dx)
            if hv > 0.02:
                RR(fr, CX0 + 1, y + 1, CW - 2, CARD_H - 2, 13, mix(CARD, (255, 255, 255), 0.04), hv * a, dx)
            T(fr, title, 14, True, TEXT, CX0 + 20, y + 7, a, dx)
            T(fr, sub, 11, False, MUTED, CX0 + 20, y + 28, a, dx)
            v = self.tog[key][1]
            tx, ty = CX0 + CW - 20 - 44, y + (CARD_H - 24) / 2
            GLOW(fr, tx + 22, ty + 12, 40, 12, acc, 0.40 * v * a, dx)
            RR(fr, tx, ty, 44, 24, 12, mix((46, 49, 62), acc, v), a, dx)
            CIRCLE(fr, tx + 12 + 20 * v, ty + 12, 9, mix((200, 204, 214), (255, 255, 255), v), a, dx)
        # signature (end of the settings page)
        wa = tw_logical("Made by ", 12, False)
        wb = tw_logical("a7yanan", 12, True)
        x0 = LW / 2 - (wa + wb) / 2
        h = self.hv["author"]
        T(fr, "Made by ", 12, False, DIM, x0, 344, a, dx)
        T(fr, "a7yanan", 12, True, mix(acc, self.acc_l, h), x0 + wa, 344, a, dx)
        if h > 0.05:
            RR(fr, x0 + wa, 360, wb, 1.4, 1, acc, h * a, dx)

    def page2(self, fr, a, dx):
        t, acc = self.t, self.acc
        GLOW(fr, 320, 120, 150, 40, acc, (0.30 + 0.14 * math.sin(t * 2.2)) * a, dx)
        LOGO(fr, 320, 120, 80, a, dx)
        T(fr, "Installing", 24, True, TEXT, 320, 176, a, dx, "c")
        pr = self.prog
        status = ("Preparing…" if pr < 0.12 else "Copying files…" if pr < 0.7
                  else "Creating shortcuts…" if pr < 0.93 else "Finishing up…")
        T(fr, status, 13, False, MUTED, 320, 214, a, dx, "c")
        bx, by, bw = 120, 262, 400
        RR(fr, bx, by, bw, 10, 5, (30, 33, 43), a, dx)
        fw = max(10.0, bw * pr)
        GLOW(fr, bx + fw - 5, by + 5, 28, 9, acc, 0.55 * a, dx)
        RR(fr, bx, by, fw, 10, 5, acc, a, dx)
        T(fr, "%d%%" % int(pr * 100), 13, True, mix(MUTED, TEXT, 0.4), 320, 284, a, dx, "c")

    def page3(self, fr, a, dx):
        t, acc = self.t, self.acc
        e = max(0.0, (t - self.done_t0) if self.done_t0 else 0.0)
        d = px(96)
        cx, cy = 320, 118
        if self.fail_text:
            GLOW(fr, cx, cy, 130, 36, RED, 0.28 * a, dx)
            RING(fr, cx, cy, 48, 4, RED, a, dx)
            T(fr, "!", 44, True, RED, cx, cy - 31, a, dx, "c")
            T(fr, "Setup failed", 28, True, TEXT, 320, 190, a, dx, "c")
            T(fr, self.fail_text, 13, False, MUTED, 320, 236, a, dx, "c")
            T(fr, "Details: %%TEMP%%\\%s_setup.log" % APP, 11, False, DIM, 320, 262, a, dx, "c")
            return
        pr, pt = min(1.0, e / 0.55), min(1.0, max(0.0, (e - 0.45) / 0.35))
        GLOW(fr, cx, cy, 150, 40, acc, 0.34 * min(1.0, e / 0.6) * a, dx)
        put(fr, acc, ma(m_check(d, ease_out(pr), ease_out(pt)), a), px(cx + dx) - d // 2, px(cy) - d // 2)
        T(fr, "You're all set", 28, True, TEXT, 320, 190, a, dx, "c")
        T(fr, DONE_LINE, 14, False, MUTED, 320, 236, a, dx, "c")


# ───────────────────────────── install / uninstall (plain Python) ─────────────────────────────
def _shortcut(path, target, icon, workdir):
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');"
          "$s.TargetPath='%s';$s.IconLocation='%s';$s.WorkingDirectory='%s';$s.Save()"
          % (path, target, icon, workdir))
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                   creationflags=CREATE_NO_WINDOW, check=True)


def start_menu_lnk():
    base = os.environ.get("ProgramData") or r"C:\ProgramData"
    d = os.path.join(base, r"Microsoft\Windows\Start Menu\Programs")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, APP + ".lnk")


def desktop_lnk():
    base = os.environ.get("PUBLIC") or r"C:\Users\Public"
    return os.path.join(base, "Desktop", APP + ".lnk")


UNINSTALL_PATH = r"Software\Microsoft\Windows\CurrentVersion\Uninstall" + "\\" + UNINSTALL_KEY
RUN_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def install_files(desktop):
    import winreg
    dest = install_dir()
    os.makedirs(dest, exist_ok=True)
    exe = os.path.join(dest, EXE_NAME)
    icon = os.path.join(dest, "app.ico")
    uninst = os.path.join(dest, "uninstall.exe")
    shutil.copy2(res(EXE_NAME), exe)
    shutil.copy2(res("app.ico"), icon)
    if getattr(sys, "frozen", False):
        shutil.copy2(sys.executable, uninst)          # this setup file also removes the app
    _shortcut(start_menu_lnk(), exe, icon, dest)
    if desktop:
        _shortcut(desktop_lnk(), exe, icon, dest)
    key = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_PATH, 0,
                             winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY)
    vals = [("DisplayName", APP, winreg.REG_SZ), ("DisplayVersion", APP_VERSION, winreg.REG_SZ),
            ("Publisher", "a7yanan", winreg.REG_SZ), ("InstallLocation", dest, winreg.REG_SZ),
            ("DisplayIcon", icon, winreg.REG_SZ), ("NoModify", 1, winreg.REG_DWORD),
            ("NoRepair", 1, winreg.REG_DWORD),
            ("UninstallString", '"%s" --uninstall' % uninst, winreg.REG_SZ)]
    for name, val, kind in vals:
        winreg.SetValueEx(key, name, 0, kind, val)
    winreg.CloseKey(key)


def uninstall():
    import winreg
    MB_YESNO_QUESTION, IDYES = 0x24, 6
    if ctypes.windll.user32.MessageBoxW(None, "Remove EyeGuard from this PC?", APP,
                                        MB_YESNO_QUESTION) != IDYES:
        return
    dest = install_dir()
    subprocess.run(["taskkill", "/F", "/IM", EXE_NAME], creationflags=CREATE_NO_WINDOW,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for p in (start_menu_lnk(), desktop_lnk()):
        try:
            os.remove(p)
        except OSError:
            pass
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(k, APP)
        winreg.CloseKey(k)
    except OSError:
        pass
    try:
        winreg.DeleteKeyEx(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_PATH, winreg.KEY_WOW64_64KEY)
    except OSError:
        pass
    shutil.rmtree(os.path.join(os.environ.get("APPDATA") or "", APP), ignore_errors=True)
    # the files in use are removed a moment later, after this window has closed
    subprocess.Popen('cmd /c "timeout /t 3 /nobreak >nul & rmdir /s /q "%s""' % dest,
                     creationflags=CREATE_NO_WINDOW)


def run_fallback():
    """If the window cannot start, install silently so the install is never blocked."""
    try:
        install_files(False)
    except Exception:
        log("fallback install failed:\n" + traceback.format_exc())


# ───────────────────────────── entry point ─────────────────────────────



def main():
    if "--uninstall" in sys.argv:
        uninstall()
        return
    app = None
    try:
        app = App()
        app.run()
    except Exception:
        log("UI error:\n" + traceback.format_exc())
        if app is None or not app.install_started:
            run_fallback()


if __name__ == "__main__":
    main()
