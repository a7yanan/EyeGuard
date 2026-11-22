# -*- coding: utf-8 -*-
"""EyeGuard v1.2 - warms the screen colours (f.lux style) and reminds you to move your eyes.

Tray icon:
  * left click       -> pause / resume the colour filter
  * scroll over icon -> warmer / cooler colour
  * right click      -> menu
"""
import ctypes
import ctypes.wintypes as wt
import datetime
import json
import math
import os
import queue
import sys
import threading
import traceback
import time
import subprocess
import unicodedata
import urllib.request
import tkinter as tk
import tkinter.messagebox as mb
import webbrowser
import winreg

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageTk

from cities import CITIES

APP_NAME = "EyeGuard"
APP_VERSION = "1.0.0"           # إصدار التطبيق
AUTHOR_URL = "https://x.com/3omar_a7yanan"
# GitHub Releases: publish EyeGuard.portable.exe with each stable release.
GITHUB_REPO = "a7yanan/EyeGuard"         # owner/repo
UPDATE_ASSET = "EyeGuard.portable.exe"
UPDATE_CHECK_HOURS = 24                  # مرة كل يوم

ACCENT = "#f59e0b"
BG = "#0E1015"
CARD = "#171A22"
FIELD = "#232733"
TEXT = "#F2F4F8"
MUTED = "#8B90A0"
FONT = ("Segoe UI", 14)
FONT_SMALL = ("Segoe UI", 13)
FONT_BIG = ("Segoe UI", 28, "bold")
FONT_BOLD = ("Segoe UI", 14, "bold")
FONT_CHIP = ("Segoe UI", 11, "bold")

CONFIG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP_NAME)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
LOG_PATH = os.path.join(os.environ.get("TEMP") or CONFIG_DIR, "EyeGuard_app.log")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

PRESETS = [("Ember", 1200), ("Candle", 1900), ("Dim Incandescent", 2300), ("Incandescent", 2700),
           ("Halogen", 3400), ("Fluorescent", 4200)]
KMIN, KMAX = 1200, 4200                 # the warmest bulb .. the coolest bulb in the list
KWHEEL = 70                                    # colour change per wheel notch (40% faster than before)
COLOR_TICK_MS = 50                            # the colour is updated every 50 ms
COLOR_FADE_MS = 500                           # the screen colour changes over half a second
# Exe names (lowercase) that pause the filter by default (kept short on purpose)
DEFAULT_PAUSE_APPS = [
    "photos.exe", "microsoft.photos.exe",
    "photoshop.exe",
    "adobe premiere pro.exe", "premiere pro.exe",
    "afterfx.exe",
    "filmora.exe", "wondershare filmora.exe",
    "snippingtool.exe", "screensketch.exe", "screenclippinghost.exe",
]

DEFAULTS = {"version": APP_VERSION, "lang": "eg", "kelvin": 1200, "schedule_on": False,
            "start": "22:00", "end": "07:00",
            "remind_on": True, "remind_every": 20, "remind_skip_idle": True,
            "overlay_opacity": 95, "eye_speed": 38,
            "auto_sun": False, "lat": 31.2, "lon": 29.92, "pause_fullscreen": True,
            "city_key": "Alexandria", "city_label": "",
            "pause_apps": list(DEFAULT_PAUSE_APPS),
            "auto_update": True,
            "last_update_check": "",     # ISO datetime of last successful check
            "pending_update_note": ""}   # version string to announce after a successful update
REMIND_MIN, REMIND_MAX = 5, 120
EYE_SECONDS = 15
EYE_BASE_CYCLE = 2.27                          # seconds per swing at 100% speed
IDLE_LIMIT = 120               # seconds without keyboard/mouse = user is away
LANGS = [("eg", "مصري"), ("ar", "عربي فصحى"), ("en", "English")]
LANG = "eg"

PRESET_NAMES = {
    "eg": ["جمر", "شمعة", "لمبة خفيفة", "لمبة عادية", "هالوچين", "نيون"],
    "ar": ["جمري", "شمعي", "منخفض الإضاءة", "متوهّج", "هالوجين", "فلورسنت"],
    "en": [p[0] for p in PRESETS],
}

STRINGS = {
    "eg": {
        "auto_sun": "شغّال بالليل بس (حسب غروب الشمس)", "fullscreen": "يتوقف الفلتر والتذكيرات أثناء الأفلام والألعاب بملء الشاشة", "color_fail": "الشاشة دي ما بتقبلش تغيير الألوان",
        "am": "ص", "pm": "م", "opacity": "شفافية شاشة التحريك", "speed": "سرعة حركة العين",
        "tagline": "إحمي عينك من ضوء الشاشة",
        "on": "شغّال", "off": "مقفول",
        "colour": "اللون", "custom": "مخصص", "colour_tip": "أشر بالماوس على ايقونة البرنامج تحت ولف العجلة هتغيّر اللون.",
        "reminders": "تذكير العين", "remind_on": "ذكّرني أحرّك عيني",
        "remind_every": "كل", "minutes": "%d دقيقة", "skip_idle": "متظهرش التذكير لو أنا بعيد عن الجهاز",
        "try_now": "جرّب التحريك دلوقتي", "start": "ابدأ",
        "general": "عام", "start_win": "يبدأ مع الويندوز",
        "schedule": "يشتغل في ساعات محددة بس", "from": "من", "to": "لـ", "save": "حفظ",
        "language": "اللغة",
        "bad_time": "اكتب الوقت بالشكل HH:MM، مثلاً 22:00.",
        "autostart_fail": "مقدرتش أغيّر إعداد البدء مع الويندوز.",
        "pause": "إيقاف مؤقت", "resume": "تشغيل", "break_now": "تحريك العين دلوقتي",
        "settings": "الإعدادات", "exit": "خروج",
        "pause_when": "إيقاف مؤقتا عند استخدام",
        "pause_reset": "إعادة للافتراضي (صور / فوتوشوب / مونتاج / لقطات)",
        "pause_none": "(مفيش برامج مفتوحة مناسبة)",
        "check_update": "البحث عن تحديث",
        "auto_update": "تحديث تلقائي (مرة كل يوم)",
        "update_latest": "أنت على آخر نسخة (%s).",
        "update_fail": "مقدرناش نتحقق من التحديثات. اتأكد من النت.",
        "update_apply_fail": "التحميل تم بس التثبيت فشل. نزّل يدوي من GitHub.",
        "update_not_exe": "التحديث شغال بس على النسخة المثبتة (EyeGuard.exe).",
        "update_done": "تم تحديث EyeGuard إلى النسخة %s",
        "update_started": "في نسخة جديدة — جاري التحديث في الخلفية...",
        "tip_on": "شغّال - %dK %s", "tip_paused": "مقفول", "tip_sched": "مقفول (برا الساعات المحددة)",
        "break_title": "تحريك العين", "break_text": "حرّك عينك شمال ويمين وفوق وتحت",
        "break_left": "باقي %d ثانية", "skip": "تخطي", "snooze": "أجّل 5 دقايق",
    },
    "ar": {
        "auto_sun": "يعمل ليلاً فقط (حسب غروب الشمس)", "fullscreen": "يتوقف الفلتر والتذكيرات أثناء الأفلام والألعاب بملء الشاشة", "color_fail": "هذه الشاشة لا تدعم تغيير الألوان",
        "am": "ص", "pm": "م", "opacity": "شفافية شاشة التحريك", "speed": "سرعة حركة العين",
        "tagline": "احمِ عينيك من وهج الشاشة",
        "on": "مُفعَّل", "off": "متوقف",
        "colour": "اللون", "custom": "مخصص", "colour_tip": "نصيحة: مرّر المؤشر على أيقونة الشريط ثم حرّك عجلة الفأرة لتغيير اللون.",
        "reminders": "تذكير العين", "remind_on": "ذكّرني بتحريك عينيّ",
        "remind_every": "كل", "minutes": "%d دقيقة", "skip_idle": "لا تُظهر التذكير عندما أكون بعيدًا عن الجهاز",
        "try_now": "جرّب التحريك الآن", "start": "ابدأ",
        "general": "عام", "start_win": "التشغيل مع بدء Windows",
        "schedule": "العمل في أوقات محددة فقط", "from": "من", "to": "إلى", "save": "حفظ",
        "language": "اللغة",
        "bad_time": "اكتب الوقت بالشكل HH:MM، مثلًا 22:00.",
        "autostart_fail": "تعذّر تغيير إعداد البدء مع Windows.",
        "pause": "إيقاف مؤقت", "resume": "استئناف", "break_now": "تحريك العين الآن",
        "settings": "الإعدادات", "exit": "خروج",
        "pause_when": "إيقاف مؤقت عند استخدام",
        "pause_reset": "إعادة للافتراضي (صور / فوتوشوب / مونتاج / لقطات)",
        "pause_none": "(لا توجد برامج مفتوحة مناسبة)",
        "check_update": "البحث عن تحديث",
        "auto_update": "تحديث تلقائي (مرة كل يوم)",
        "update_latest": "أنت على أحدث إصدار (%s).",
        "update_fail": "تعذّر التحقق من التحديثات. تأكد من الاتصال بالإنترنت.",
        "update_apply_fail": "تم التنزيل لكن فشل التثبيت. نزّله يدويًا من GitHub.",
        "update_not_exe": "التحديث يعمل فقط مع النسخة المثبتة (EyeGuard.exe).",
        "update_done": "تم تحديث EyeGuard إلى الإصدار %s",
        "update_started": "يتوفر إصدار جديد — جارٍ التحديث في الخلفية...",
        "tip_on": "مُفعَّل - %dK %s", "tip_paused": "متوقف مؤقتًا", "tip_sched": "متوقف (خارج الأوقات المحددة)",
        "break_title": "تحريك العين", "break_text": "حرّك عينيك يمينًا ويسارًا ثم لأعلى ولأسفل",
        "break_left": "متبقٍ %d ثانية", "skip": "تخطٍّ", "snooze": "أجّل 5 دقائق",
    },
    "en": {
        "auto_sun": "Night only (by sunset and sunrise)", "fullscreen": "Pause the filter and reminders during full-screen movies and games", "color_fail": "This screen does not support colour changes",
        "am": "AM", "pm": "PM", "opacity": "Movement screen opacity", "speed": "Eye movement speed",
        "tagline": "Protect your eyes from screen glare",
        "on": "ON", "off": "OFF",
        "colour": "Colour", "custom": "Custom", "colour_tip": "Tip: hover the tray icon and scroll to change the colour.",
        "reminders": "Eye reminders", "remind_on": "Remind me to move my eyes",
        "remind_every": "Every", "minutes": "%d min", "skip_idle": "Skip when I'm away from the PC",
        "try_now": "Try the eye movement now", "start": "Start",
        "general": "General", "start_win": "Start with Windows",
        "schedule": "Work only during these hours", "from": "From", "to": "To", "save": "Save",
        "language": "Language",
        "bad_time": "Write the time as HH:MM, for example 22:00.",
        "autostart_fail": "Could not change the Windows startup setting.",
        "pause": "Pause", "resume": "Resume", "break_now": "Eye movement now",
        "settings": "Settings", "exit": "Exit",
        "pause_when": "Pause while using",
        "pause_reset": "Reset to defaults (Photos / Photoshop / editors / screenshots)",
        "pause_none": "(no suitable open programs)",
        "check_update": "Check for updates",
        "auto_update": "Auto-update (once a day)",
        "update_latest": "You are on the latest version (%s).",
        "update_fail": "Could not check for updates. Check your internet connection.",
        "update_apply_fail": "Download succeeded but install failed. Download manually from GitHub.",
        "update_not_exe": "Updates only work with the installed build (EyeGuard.exe).",
        "update_done": "EyeGuard was updated to version %s",
        "update_started": "A new version is available — updating in the background...",
        "tip_on": "ON - %dK %s", "tip_paused": "Paused", "tip_sched": "Off (outside scheduled hours)",
        "break_title": "Eye movement", "break_text": "Move your eyes left, right, up and down.",
        "break_left": "Done in %d s", "skip": "Skip", "snooze": "Snooze 5 min",
    },
}


STRINGS["eg"].update({
    "city": "المدينة", "city_pick": "اختار مدينتك", "city_search": "دوّر على مدينة أو دولة",
    "locating": "بحدد مكانك...", "located": "تم تحديد مكانك بدقة: %s",
    "locate_fail": "ما قدرتش أحدد مكانك. اتأكد إن النت شغّال وجرّب تاني.",
    "my_place": "مكاني", "city_none": "مفيش نتايج",
    "located_rough": "التحديد تقريبي من النت: %s. لو غلط اختار مدينتك من القايمة، أو شغّل الموقع في ويندوز.",
})
STRINGS["ar"].update({
    "city": "المدينة", "city_pick": "اختر مدينتك", "city_search": "ابحث عن مدينة أو دولة",
    "locating": "جارٍ تحديد موقعك...", "located": "تم تحديد موقعك بدقة: %s",
    "locate_fail": "تعذّر تحديد موقعك. تأكد من اتصال الإنترنت وحاول مجددًا.",
    "my_place": "موقعي", "city_none": "لا توجد نتائج",
    "located_rough": "التحديد تقريبي عبر الإنترنت: %s. إن كان خاطئًا فاختر مدينتك من القائمة أو فعّل الموقع في ويندوز.",
})
STRINGS["en"].update({
    "city": "City", "city_pick": "Choose your city", "city_search": "Search a city or country",
    "locating": "Finding your location...", "located": "Exact location set: %s",
    "locate_fail": "Could not find your location. Check your internet and try again.",
    "my_place": "My location", "city_none": "No results",
    "located_rough": "Rough location from the internet: %s. If it is wrong, pick your city from the list or turn on Location in Windows.",
})


def T(key, *args):
    s = STRINGS.get(LANG, STRINGS["en"]).get(key) or STRINGS["en"].get(key, key)
    return s % args if args else s


# ───────────────────────────── Windows API setup ─────────────────────────────
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_shell32 = ctypes.WinDLL("shell32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t)
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t)

_user32.DefWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
_user32.DefWindowProcW.restype = LRESULT
_user32.RegisterClassW.argtypes = [ctypes.c_void_p]
_user32.CreateWindowExW.argtypes = [ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
_user32.CreateWindowExW.restype = ctypes.c_void_p
_user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, ctypes.c_void_p, ctypes.c_uint]
_user32.SetWindowsHookExW.restype = ctypes.c_void_p
_user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t]
_user32.CallNextHookEx.restype = LRESULT
_user32.GetMessageW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
_user32.GetMessageW.restype = ctypes.c_int
_user32.TranslateMessage.argtypes = [ctypes.c_void_p]
_user32.DispatchMessageW.argtypes = [ctypes.c_void_p]
_user32.PostQuitMessage.argtypes = [ctypes.c_int]
_user32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
_user32.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
_user32.LoadImageW.restype = ctypes.c_void_p
_user32.LoadIconW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_user32.LoadIconW.restype = ctypes.c_void_p
_user32.GetSystemMetrics.argtypes = [ctypes.c_int]
_user32.RegisterWindowMessageW.argtypes = [ctypes.c_wchar_p]
_user32.RegisterWindowMessageW.restype = ctypes.c_uint
_user32.CreatePopupMenu.restype = ctypes.c_void_p
_user32.AppendMenuW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_wchar_p]
_user32.GetCursorPos.argtypes = [ctypes.c_void_p]
_user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
_user32.TrackPopupMenu.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
_user32.DestroyMenu.argtypes = [ctypes.c_void_p]
_user32.DestroyIcon.argtypes = [ctypes.c_void_p]
_user32.GetDC.argtypes = [ctypes.c_void_p]
_user32.GetDC.restype = ctypes.c_void_p
_user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_user32.GetForegroundWindow.restype = ctypes.c_void_p
_user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
_user32.GetWindowThreadProcessId.restype = ctypes.c_uint
_user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
_user32.IsWindowVisible.restype = ctypes.c_int
_user32.GetWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
_user32.GetWindow.restype = ctypes.c_void_p
_user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
_user32.GetWindowTextLengthW.restype = ctypes.c_int
_user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
_user32.GetWindowTextW.restype = ctypes.c_int
_user32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
_user32.GetClassNameW.restype = ctypes.c_int
_user32.EnumWindows.argtypes = [ctypes.c_void_p, ctypes.c_ssize_t]
_user32.EnumWindows.restype = ctypes.c_int
_gdi32.SetDeviceGammaRamp.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
_kernel32.GetModuleHandleW.restype = ctypes.c_void_p
_kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
_kernel32.CreateMutexW.restype = ctypes.c_void_p
_kernel32.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_uint]
_kernel32.OpenProcess.restype = ctypes.c_void_p
_kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
_kernel32.CloseHandle.restype = ctypes.c_int
_kernel32.QueryFullProcessImageNameW = _kernel32.QueryFullProcessImageNameW
_kernel32.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong)]
_kernel32.QueryFullProcessImageNameW.restype = ctypes.c_int
_shell32.Shell_NotifyIconW.argtypes = [ctypes.c_uint, ctypes.c_void_p]
_shell32.Shell_NotifyIconGetRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_shell32.Shell_NotifyIconGetRect.restype = ctypes.c_long


class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16), ("Data3", ctypes.c_uint16),
                ("Data4", ctypes.c_ubyte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint32), ("hWnd", ctypes.c_void_p), ("uID", ctypes.c_uint32),
                ("uFlags", ctypes.c_uint32), ("uCallbackMessage", ctypes.c_uint32),
                ("hIcon", ctypes.c_void_p), ("szTip", ctypes.c_wchar * 128),
                ("dwState", ctypes.c_uint32), ("dwStateMask", ctypes.c_uint32),
                ("szInfo", ctypes.c_wchar * 256), ("uVersion", ctypes.c_uint32),
                ("szInfoTitle", ctypes.c_wchar * 64), ("dwInfoFlags", ctypes.c_uint32),
                ("guidItem", GUID), ("hBalloonIcon", ctypes.c_void_p)]


class NOTIFYICONIDENTIFIER(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint32), ("hWnd", ctypes.c_void_p), ("uID", ctypes.c_uint32),
                ("guidItem", GUID)]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", ctypes.c_uint), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", ctypes.c_void_p), ("hIcon", ctypes.c_void_p),
                ("hCursor", ctypes.c_void_p), ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName", ctypes.c_wchar_p), ("lpszClassName", ctypes.c_wchar_p)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wt.POINT), ("mouseData", ctypes.c_uint32), ("flags", ctypes.c_uint32),
                ("time", ctypes.c_uint32), ("dwExtraInfo", ctypes.c_size_t)]


class _Ramp(ctypes.Structure):
    _fields_ = [("Red", ctypes.c_ushort * 256), ("Green", ctypes.c_ushort * 256),
                ("Blue", ctypes.c_ushort * 256)]


WM_APP = 0x8000
WM_TRAY = WM_APP + 1
WM_LBUTTONUP = 0x0202
WM_HOTKEY = 0x0312
MOD_CONTROL, MOD_ALT = 0x0002, 0x0001
HOTKEYS = {1: ("toggle", None), 2: ("preset", -1), 3: ("preset", 1)}   # Ctrl+Alt+E, Ctrl+Alt+Up/Down
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_MOUSEWHEEL = 0x020A
WM_COMMAND = 0x0111
WM_DESTROY = 0x0002
WH_MOUSE_LL = 14
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 1, 2, 4
IMAGE_ICON, LR_LOADFROMFILE = 1, 0x10
SM_CXSMICON, SM_CYSMICON = 49, 50
MF_SEPARATOR = 0x800
MF_STRING = 0x0000
MF_POPUP = 0x0010
MF_CHECKED = 0x0008
MF_GRAYED = 0x0001
TPM_RIGHTBUTTON = 0x0002
GW_OWNER = 4
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
HWND_MESSAGE = -3
TRAY_UID = 1
ID_TOGGLE, ID_SETTINGS, ID_EXIT = 1001, 1002, 1003
ID_BREAK = 1004
ID_PAUSE_RESET = 1099
ID_PAUSE_APP_BASE = 1100          # 1100 .. 1199 = dynamic pause-app toggles
ID_PAUSE_APP_MAX = 1199




# ───────────────────────────── helpers ─────────────────────────────
def log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (datetime.datetime.now().isoformat(timespec="seconds"), msg))
    except Exception:
        pass


def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def is_frozen():
    """True when running as the packaged EyeGuard.exe (PyInstaller)."""
    return bool(getattr(sys, "frozen", False)) or hasattr(sys, "_MEIPASS")


def _parse_version(text):
    """'v1.2.58' / '1.2.58' -> (1, 2, 58) for comparison."""
    s = str(text or "").strip().lstrip("vV")
    parts = []
    for p in s.split("."):
        try:
            parts.append(int("".join(ch for ch in p if ch.isdigit()) or "0"))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:4])


def fetch_latest_release():
    """GitHub latest release. Returns dict {version, tag, url, notes} or raises."""
    api = "https://api.github.com/repos/%s/releases/latest" % GITHUB_REPO
    req = urllib.request.Request(api, headers={
        "User-Agent": "EyeGuard/" + APP_VERSION,
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req, timeout=12) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    tag = str(data.get("tag_name") or "")
    ver = tag.lstrip("vV")
    url = ""
    for asset in data.get("assets") or []:
        name = str(asset.get("name") or "")
        if name.lower() == UPDATE_ASSET.lower():
            url = str(asset.get("browser_download_url") or "")
            break
    if not url:
        # fallback: any .exe
        for asset in data.get("assets") or []:
            name = str(asset.get("name") or "").lower()
            if name.endswith(".exe") and "setup" not in name:
                url = str(asset.get("browser_download_url") or "")
                break
    if not ver or not url:
        raise RuntimeError("no suitable release asset")
    return {
        "version": ver,
        "tag": tag,
        "url": url,
        "notes": str(data.get("body") or ""),
        "html_url": str(data.get("html_url") or ""),
    }


def download_update(url, dest_path):
    req = urllib.request.Request(url, headers={"User-Agent": "EyeGuard/" + APP_VERSION})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest_path, "wb") as out:
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            out.write(chunk)


def apply_update_and_restart(new_exe_path, version):
    """Elevate a PowerShell helper, replace the installed EXE, then relaunch."""
    if not is_frozen():
        return False

    current = os.path.abspath(sys.executable)
    helper = os.path.join(os.environ.get("TEMP") or os.path.dirname(current),
                          "EyeGuard_update.ps1")
    pid = os.getpid()
    ps = r"""$ErrorActionPreference = 'Stop'
$target = __TARGET__
$newFile = __NEWFILE__
$processId = __PID__
$version = __VERSION__
try {
    Wait-Process -Id $processId
    Start-Sleep -Milliseconds 700
    Copy-Item -LiteralPath $newFile -Destination $target -Force
    try {
        Set-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\EyeGuard' -Name DisplayVersion -Value $version -ErrorAction Stop
    } catch {}
    Start-Process -FilePath $target
    Remove-Item -LiteralPath $newFile -Force -ErrorAction SilentlyContinue
} catch {
    $_ | Out-String | Set-Content -LiteralPath (Join-Path $env:TEMP 'EyeGuard_update_error.txt')
}
Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
"""
    def ps_quote(value):
        return "'" + str(value).replace("'", "''") + "'"
    ps = (ps.replace('__TARGET__', ps_quote(current))
            .replace('__NEWFILE__', ps_quote(os.path.abspath(new_exe_path)))
            .replace('__PID__', str(pid))
            .replace('__VERSION__', ps_quote(version)))
    try:
        with open(helper, "w", encoding="utf-8") as f:
            f.write(ps)
        args = '-NoProfile -ExecutionPolicy Bypass -File "' + helper + '"'
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", args, None, 0)
        return int(result) > 32
    except Exception as e:
        log("could not launch elevated updater: %r" % (e,))
        return False

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def valid_time(text):
    try:
        h, m = str(text).strip().split(":")
        h, m = int(h), int(m)
        if 0 <= h < 24 and 0 <= m < 60:
            return "%02d:%02d" % (h, m)
    except Exception:
        pass
    return None


def in_window(now, start, end):
    s = int(start[:2]) * 60 + int(start[3:])
    e = int(end[:2]) * 60 + int(end[3:])
    n = now.hour * 60 + now.minute
    if s == e:
        return True
    if s < e:
        return s <= n < e
    return n >= s or n < e          # window crosses midnight


def kelvin_rgb(k):
    """Approximate colour of a light at k Kelvin, as 0-255 integers."""
    t = k / 100.0
    if t <= 66:
        r = 255
        g = 99.4708025861 * math.log(t) - 161.1195681661
    else:
        r = 329.698727446 * ((t - 60) ** -0.1332047592)
        g = 288.1221695283 * ((t - 60) ** -0.0755148492)
    if t >= 66:
        b = 255
    elif t <= 19:
        b = 0
    else:
        b = 138.5177312231 * math.log(t - 10) - 305.0447927307
    return tuple(int(round(clamp(c, 0, 255))) for c in (r, g, b))


_DAYLIGHT = kelvin_rgb(6500)


def sun_minutes(day, lat, lon):
    """Local minutes after midnight of sunrise and sunset for a day (NOAA method). None in polar days/nights."""
    n = day.timetuple().tm_yday
    g = 2 * math.pi / 365.0 * (n - 1)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                       - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
            + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    lat_r = math.radians(lat)
    arg = math.cos(math.radians(90.833)) / (math.cos(lat_r) * math.cos(decl)) - math.tan(lat_r) * math.tan(decl)
    if arg < -1 or arg > 1:
        return None
    ha = math.degrees(math.acos(arg))
    off = datetime.datetime.now().astimezone().utcoffset().total_seconds() / 60.0
    rise = 720 - 4 * (lon + ha) - eqtime + off
    sett = 720 - 4 * (lon - ha) - eqtime + off
    return rise % 1440, sett % 1440


def is_night(now, lat, lon):
    times = sun_minutes(now.date(), lat, lon)
    if times is None:
        return False
    rise, sett = times
    m = now.hour * 60 + now.minute
    return m >= sett or m < rise


# ───────────────────────────── city and location ─────────────────────────────
def norm(text):
    """Lower case, no accents or Arabic marks, and the same letter for the Arabic hamza forms (for searching)."""
    t = unicodedata.normalize("NFD", (text or "").lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return t.replace("ة", "ه").replace("ى", "ي")


def place_names(c):
    """(city, country) of one list entry, in the language of the screen."""
    return (c[0], c[2]) if LANG == "en" else (c[1], c[3])


def city_index(key):
    for i, c in enumerate(CITIES):
        if c[0] == key:
            return i
    return None


def city_label(cfg):
    if cfg.get("city_key") == "auto":
        return cfg.get("city_label") or T("my_place")
    i = city_index(cfg.get("city_key"))
    return place_names(CITIES[i if i is not None else 0])[0]


IP_SERVICES = [
    ("https://ipwho.is/", "latitude", "longitude", "city"),
    ("https://get.geojs.io/v1/ip/geo.json", "latitude", "longitude", "city"),
    ("https://ipapi.co/json/", "latitude", "longitude", "city"),
    ("https://ipinfo.io/json", "loc", "loc", "city"),  # special: loc is "lat,lon"
]


def _http_json(url, timeout=6):
    req = urllib.request.Request(url, headers={"User-Agent": "EyeGuard/" + APP_VERSION, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _valid_pos(lat, lon):
    return (lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180
            and not (abs(lat) < 0.001 and abs(lon) < 0.001))


def _windows_location():
    """The exact position from Windows Location (Wi-Fi / GPS). Returns (lat, lon) or None.
    Tries High accuracy first (up to ~15 s), then Default accuracy once more."""
    def _try(acc, wait_loops):
        ps = (
            "Add-Type -AssemblyName System.Device; "
            "$w = New-Object System.Device.Location.GeoCoordinateWatcher("
            "[System.Device.Location.GeoPositionAccuracy]::%s); "
            "$w.MovementThreshold = 1; "
            "$w.Start(); $i = 0; "
            "while ($w.Status -ne 'Ready' -and $w.Status -ne 'Disabled' "
            "-and $w.Permission -ne 'Denied' -and $i -lt %d) { "
            "Start-Sleep -Milliseconds 100; $i++ }; "
            "$l = $w.Position.Location; "
            "if ($w.Status -eq 'Ready' -and -not $l.IsUnknown) { "
            "[string]::Format([Globalization.CultureInfo]::InvariantCulture, "
            "'{0};{1};{2}', $l.Latitude, $l.Longitude, $l.HorizontalAccuracy) } "
            "else { 'STATUS ' + $w.Status + ' ' + $w.Permission }; "
            "$w.Stop()"
        ) % (acc, wait_loops)
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20,
            creationflags=0x08000000)
        best = None
        for line in (out.stdout or "").splitlines():
            line = line.strip()
            if line.count(";") >= 1 and not line.startswith("STATUS"):
                parts = line.split(";")
                try:
                    lat, lon = float(parts[0]), float(parts[1])
                    acc_m = float(parts[2]) if len(parts) > 2 else 99999.0
                except ValueError:
                    continue
                if _valid_pos(lat, lon):
                    if best is None or acc_m < best[2]:
                        best = (lat, lon, acc_m)
            elif line.startswith("STATUS"):
                log("windows location not available (%s): %s" % (acc, line))
        return best

    # High accuracy first (longer wait), then Default as fallback
    for accuracy, loops in (("High", 120), ("Default", 50)):
        try:
            result = _try(accuracy, loops)
            if result:
                lat, lon, acc_m = result
                log("windows location %s: %.5f, %.5f (accuracy ~%.0fm)" % (accuracy, lat, lon, acc_m))
                return lat, lon
        except Exception as e:
            log("windows location %s failed: %r" % (accuracy, e))
    return None


def _km(a, b):
    """Distance in km between two (lat, lon) points."""
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dl = math.radians(b[1] - a[1])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 12742.0 * math.asin(math.sqrt(h))


def _ip_location():
    """A position from the internet address (only a rough one). Returns (lat, lon, city name) or None.
    The services are asked one by one; as soon as two of them agree (within 50 km) their average is used."""
    found = []
    for url, klat, klon, kcity in IP_SERVICES:
        try:
            d = _http_json(url)
            if klat == "loc" and "loc" in d:          # ipinfo.io style "lat,lon"
                parts = str(d["loc"]).split(",")
                lat, lon = float(parts[0]), float(parts[1])
            else:
                lat, lon = float(d.get(klat)), float(d.get(klon))
            if not _valid_pos(lat, lon):
                continue
            city = str(d.get(kcity) or "")
            for a in found:
                if _km((a[0], a[1]), (lat, lon)) <= 50:
                    return (a[0] + lat) / 2.0, (a[1] + lon) / 2.0, a[2] or city
            found.append((lat, lon, city))
        except Exception as e:
            log("ip location %s failed: %r" % (url, e))
    return found[0] if found else None


def _reverse_name(lat, lon):
    """The place name for a position (OpenStreetMap), in the screen language. Empty text if it fails.
    zoom=14 gives neighbourhood / suburb level when available (more precise than city-only)."""
    url = ("https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=14&addressdetails=1"
           "&accept-language=%s&lat=%.6f&lon=%.6f" % ("en" if LANG == "en" else "ar", lat, lon))
    d = _http_json(url, 6)
    a = d.get("address") or {}
    # Prefer the most specific place name available
    for k in ("neighbourhood", "suburb", "quarter", "city_district", "district",
              "village", "town", "city", "municipality", "county", "state"):
        if a.get(k):
            name = str(a[k])
            # Append city if we only got a neighbourhood
            if k in ("neighbourhood", "suburb", "quarter", "city_district", "district"):
                city = a.get("city") or a.get("town") or a.get("municipality")
                if city and str(city) not in name:
                    name = "%s، %s" % (name, city) if LANG != "en" else "%s, %s" % (name, city)
            return name
    return str(d.get("name") or "")


def detect_location():
    """Finds where the user is. Windows Location first (exact), then the internet address.
    Returns {"lat", "lon", "label", "source"} or raises RuntimeError."""
    pos, source, ip_name = None, "", ""
    try:
        pos = _windows_location()
        source = "windows"
    except Exception as e:
        log("windows location failed: %r" % (e,))
    if pos is None:
        found = _ip_location()
        if found:
            pos, ip_name, source = (found[0], found[1]), found[2], "ip"
    if pos is None:
        raise RuntimeError("no location found")
    name = ""
    try:
        name = _reverse_name(pos[0], pos[1])
    except Exception as e:
        log("reverse name failed: %r" % (e,))
    label = name or ip_name or ("%.2f, %.2f" % pos)
    log("location %s: %.4f, %.4f (%s)" % (source, pos[0], pos[1], label))
    return {"lat": pos[0], "lon": pos[1], "label": label, "source": source, "exact": source == "windows"}


def kelvin_to_index(k):
    """Position of a colour on the bulb scale: 0 = first bulb, 1 = second bulb, ... (fractions in between)."""
    n = len(PRESETS)
    for i in range(n - 1):
        a, b = PRESETS[i][1], PRESETS[i + 1][1]
        if k <= b:
            return i + (k - a) / float(b - a)
    return float(n - 1)


def index_to_kelvin(idx):
    n = len(PRESETS)
    i = int(clamp(int(math.floor(idx)), 0, n - 2))
    frac = clamp(idx - i, 0.0, 1.0)
    a, b = PRESETS[i][1], PRESETS[i + 1][1]
    return a + (b - a) * frac


def channel_multipliers(k):
    """Per-colour multipliers for the screen. 6500K = no change."""
    rgb = kelvin_rgb(k)
    lo = (1.0, 0.45, 0.2)                 # never darken too far (keeps Windows happy)
    return [clamp(rgb[i] / float(_DAYLIGHT[i]), lo[i], 1.0) for i in range(3)]


def to12(hhmm):
    """"22:00" -> ("10:00", True) : the 12-hour text and whether it is PM."""
    h, m = int(hhmm[:2]), int(hhmm[3:])
    return "%02d:%02d" % (h % 12 or 12, m), h >= 12


def to24(text, pm):
    """("10:00", True) -> "22:00"; returns None when the text is not a valid 12-hour time."""
    try:
        h, m = str(text).strip().split(":")
        h, m = int(h), int(m)
    except Exception:
        return None
    if not (1 <= h <= 12 and 0 <= m < 60):
        return None
    return "%02d:%02d" % (h % 12 + (12 if pm else 0), m)


def nearest_index(k):
    return min(range(len(PRESETS)), key=lambda i: abs(PRESETS[i][1] - k))


def preset_name(k):
    return PRESET_NAMES.get(LANG, PRESET_NAMES["en"])[nearest_index(k)]


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        # A new version erases the settings saved by the previous version.
        if isinstance(saved, dict) and saved.get("version") == APP_VERSION:
            cfg.update(saved)
    except Exception:
        pass
    try:
        cfg["kelvin"] = int(clamp(int(cfg["kelvin"]), KMIN, KMAX))
        cfg["remind_every"] = int(clamp(int(cfg["remind_every"]), REMIND_MIN, REMIND_MAX))
    except Exception:
        cfg["kelvin"] = DEFAULTS["kelvin"]
        cfg["remind_every"] = DEFAULTS["remind_every"]
    if cfg.get("lang") not in ("eg", "ar", "en"):
        cfg["lang"] = "eg"
    try:
        cfg["overlay_opacity"] = int(clamp(int(cfg["overlay_opacity"]), 20, 100))
    except Exception:
        cfg["overlay_opacity"] = DEFAULTS["overlay_opacity"]
    try:
        cfg["eye_speed"] = int(clamp(int(cfg["eye_speed"]), 25, 200))
    except Exception:
        cfg["eye_speed"] = DEFAULTS["eye_speed"]
    try:
        cfg["lat"], cfg["lon"] = float(cfg["lat"]), float(cfg["lon"])
        if not _valid_pos(cfg["lat"], cfg["lon"]):
            raise ValueError("bad position")
    except Exception:
        cfg["lat"], cfg["lon"] = DEFAULTS["lat"], DEFAULTS["lon"]
    if cfg.get("city_key") != "auto" and city_index(cfg.get("city_key")) is None:
        cfg["city_key"], cfg["lat"], cfg["lon"] = DEFAULTS["city_key"], DEFAULTS["lat"], DEFAULTS["lon"]
    cfg["city_label"] = str(cfg.get("city_label") or "")
    cfg["schedule_on"] = bool(cfg.get("schedule_on"))
    cfg["remind_on"] = bool(cfg.get("remind_on"))
    cfg["remind_skip_idle"] = bool(cfg.get("remind_skip_idle"))
    cfg["pause_fullscreen"] = bool(cfg.get("pause_fullscreen", True))
    cfg["auto_update"] = bool(cfg.get("auto_update", True))
    cfg["last_update_check"] = str(cfg.get("last_update_check") or "")
    cfg["pending_update_note"] = str(cfg.get("pending_update_note") or "")
    cfg["start"] = valid_time(cfg.get("start")) or DEFAULTS["start"]
    cfg["end"] = valid_time(cfg.get("end")) or DEFAULTS["end"]
    # pause_apps: list of exe basenames (lowercase)
    apps = cfg.get("pause_apps")
    if not isinstance(apps, list):
        apps = list(DEFAULT_PAUSE_APPS)
    cleaned = []
    seen = set()
    for a in apps:
        s = str(a).strip().lower()
        if s and s not in seen:
            seen.add(s)
            cleaned.append(s)
    cfg["pause_apps"] = cleaned
    cfg["version"] = APP_VERSION
    return cfg


def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        log("save config failed: %r" % (e,))


def set_warmth(kelvin):
    """Set the screen colour. 6500K restores normal colours."""
    m = channel_multipliers(kelvin)
    ramp = _Ramp()
    for i in range(256):
        v = i * 257
        ramp.Red[i] = int(v * m[0])
        ramp.Green[i] = int(v * m[1])
        ramp.Blue[i] = int(v * m[2])
    hdc = _user32.GetDC(None)
    if hdc:
        try:
            return bool(_gdi32.SetDeviceGammaRamp(hdc, ctypes.byref(ramp)))
        finally:
            _user32.ReleaseDC(None, hdc)
    return False


def _process_basename(hwnd):
    """Executable file name (e.g. Photoshop.exe) of the process that owns hwnd, or ''."""
    if not hwnd:
        return ""
    pid = ctypes.c_ulong(0)
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    h = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(512)
        size = ctypes.c_ulong(512)
        if _kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
    finally:
        _kernel32.CloseHandle(h)
    return ""


def _window_title(hwnd):
    if not hwnd:
        return ""
    n = _user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    _user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value.strip()


def _window_class(hwnd):
    if not hwnd:
        return ""
    buf = ctypes.create_unicode_buffer(256)
    _user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


# Shell / desktop / taskbar — never treat as a real app and never as "fullscreen movie"
_SHELL_CLASSES = {
    "shell_traywnd", "shell_secondarytraywnd", "progman", "workerw",
    "dv2controlhost", "windows.ui.core.corewindow",  # sometimes Start / Search
}
_SHELL_EXES = {
    "explorer.exe", "searchhost.exe", "shellexperiencehost.exe",
    "startmenuexperiencehost.exe", "searchapp.exe", "textinputhost.exe",
    "runtimebroker.exe", "lockapp.exe", "logonui.exe", "sihost.exe",
    "widgets.exe", "widgetservice.exe",
}
# Background processes we never show in the "pause while using" menu
_SYSTEM_EXES = _SHELL_EXES | {
    "dwm.exe", "taskmgr.exe", "cmd.exe", "powershell.exe", "pwsh.exe", "conhost.exe",
    "eyeguard.exe", "python.exe", "pythonw.exe", "systemsettings.exe",
    "applicationframehost.exe", "ctfmon.exe", "securityhealthsystray.exe",
}


def _is_shell_window(hwnd):
    """Taskbar, desktop, Start, Search — not a real app the user is 'using'."""
    if not hwnd:
        return True
    cls = _window_class(hwnd).lower()
    if cls in _SHELL_CLASSES:
        return True
    exe = _process_basename(hwnd).lower()
    if exe in _SHELL_EXES:
        return True
    return False


def foreground_fullscreen():
    """True when the active window covers the whole screen (a movie, a game).
    Desktop / taskbar / shell are never treated as fullscreen."""
    hwnd = _user32.GetForegroundWindow()
    if not hwnd or _is_shell_window(hwnd):
        return False
    rect = wt.RECT()
    if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False
    sw, sh = _user32.GetSystemMetrics(0), _user32.GetSystemMetrics(1)
    return rect.left <= 0 and rect.top <= 0 and rect.right >= sw and rect.bottom >= sh


def _pause_key_for_hwnd(hwnd, pause_set):
    """If hwnd belongs to a paused app, return a stable key (exe name); else None."""
    if not hwnd or not pause_set:
        return None
    exe = _process_basename(hwnd)
    if not exe:
        return None
    low = exe.lower()
    if low in pause_set:
        return low
    if low == "applicationframehost.exe":
        title = _window_title(hwnd).lower()
        if any(k in title for k in ("photos", "صور", "gallery", "معرض")):
            if "photos.exe" in pause_set or "microsoft.photos.exe" in pause_set:
                return "photos.exe"
        if any(k in title for k in ("snip", "لقطة", "sketch", "screen sketch")):
            if "screensketch.exe" in pause_set or "snippingtool.exe" in pause_set:
                return "screensketch.exe"
    return None


def _process_still_running(exe_lower):
    """True if any visible top-level window still belongs to this exe (or UWP Photos key)."""
    if not exe_lower:
        return False
    found = []

    def _enum(hwnd, _lparam):
        try:
            if not _user32.IsWindowVisible(hwnd):
                return True
            if _user32.GetWindow(hwnd, GW_OWNER):
                return True
            key = _pause_key_for_hwnd(hwnd, {exe_lower, "photos.exe", "microsoft.photos.exe",
                                             "screensketch.exe", "snippingtool.exe"})
            if key == exe_lower:
                found.append(1)
                return False  # stop enum
        except Exception:
            pass
        return True

    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_ssize_t)
    cb = EnumProc(_enum)
    try:
        _user32.EnumWindows(cb, 0)
    except Exception:
        pass
    return bool(found)


def list_open_apps():
    """Visible top-level apps as [(exe_lower, display_name), ...], sorted by name."""
    results = {}

    def _enum(hwnd, _lparam):
        try:
            if not _user32.IsWindowVisible(hwnd):
                return True
            if _user32.GetWindow(hwnd, GW_OWNER):
                return True
            title = _window_title(hwnd)
            if not title:
                return True
            exe = _process_basename(hwnd)
            if not exe:
                return True
            low = exe.lower()
            if low in _SYSTEM_EXES:
                if low == "applicationframehost.exe":
                    tlow = title.lower()
                    if any(k in tlow for k in ("photos", "صور", "gallery", "معرض")):
                        results["photos.exe"] = ("photos.exe", title)
                    elif any(k in tlow for k in ("snip", "لقطة", "sketch")):
                        results["screensketch.exe"] = ("screensketch.exe", title)
                return True
            if low not in results:
                display = title if 0 < len(title) < 55 else exe
                results[low] = (low, display)
        except Exception:
            pass
        return True

    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_ssize_t)
    cb = EnumProc(_enum)
    try:
        _user32.EnumWindows(cb, 0)
    except Exception as e:
        log("list_open_apps failed: %r" % (e,))
    return sorted(results.values(), key=lambda x: x[1].lower())


def evaluate_app_pause(pause_apps, sticky_key):
    """Decide whether to pause for a listed app, ignoring taskbar/desktop flicker.

    Returns (should_pause: bool, new_sticky_key: str|None).

    - Foreground is a listed app  → pause, remember it
    - Foreground is taskbar/desktop/Start → keep previous sticky state
      (but clear if that app was closed)
    - Foreground is another real app → resume
    """
    pause_set = {str(p).lower() for p in (pause_apps or [])}
    if not pause_set:
        return False, None

    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        # No focus — keep sticky if the app is still open
        if sticky_key and _process_still_running(sticky_key):
            return True, sticky_key
        return False, None

    if _is_shell_window(hwnd):
        if sticky_key and _process_still_running(sticky_key):
            return True, sticky_key
        return False, None

    key = _pause_key_for_hwnd(hwnd, pause_set)
    if key:
        return True, key
    # Real app that is not in the pause list → resume
    return False, None


def idle_seconds():
    li = LASTINPUTINFO()
    li.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not _user32.GetLastInputInfo(ctypes.byref(li)):
        return 0.0
    return ((_kernel32.GetTickCount() - li.dwTime) & 0xFFFFFFFF) / 1000.0


NOTIFY_ROOT = r"Control Panel\NotifyIconSettings"


def _promote_entries(name):
    """Sets IsPromoted=1 on every tray entry that belongs to EyeGuard. Returns (found, promoted)."""
    found = ok = 0
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, NOTIFY_ROOT) as root:
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            try:
                with winreg.OpenKey(root, sub, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
                    low = str(winreg.QueryValueEx(k, "ExecutablePath")[0]).lower()
                    if os.path.basename(low) != name and "eyeguard" not in low:
                        continue
                    found += 1
                    try:
                        if winreg.QueryValueEx(k, "IsPromoted")[0] == 1:
                            ok += 1
                            continue
                    except OSError:
                        pass
                    winreg.SetValueEx(k, "IsPromoted", 0, winreg.REG_DWORD, 1)
                    if winreg.QueryValueEx(k, "IsPromoted")[0] == 1:
                        ok += 1
            except OSError:
                continue
    return found, ok


def pin_tray_icon():
    """Windows 11: shows the EyeGuard icon next to the clock instead of in the hidden-icons arrow.
    Windows registers the icon a few seconds after it appears, and it can reset the value,
    so the value is set again several times."""
    if not getattr(sys, "frozen", False):
        return
    try:
        name = os.path.basename(sys.executable).lower()
        try:
            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CURRENT_USER, NOTIFY_ROOT))
        except OSError:
            log("tray pin: no NotifyIconSettings key (Windows 10?)")
            return
        registered = False
        for _ in range(60):
            _, ok = _promote_entries(name)
            if ok:
                registered = True
                break
            time.sleep(1)
        if not registered:
            log("tray pin: icon entry not found after a minute")
            return
        for _ in range(10):
            time.sleep(2)
            _promote_entries(name)
        log("tray pin: done")
    except Exception:
        log("tray pin failed:\n%s" % traceback.format_exc())


def autostart_command():
    if getattr(sys, "frozen", False):
        return '"%s"' % sys.executable
    py = sys.executable.replace("python.exe", "pythonw.exe")
    return '"%s" "%s"' % (py, os.path.abspath(__file__))


def autostart_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except OSError:
        return False


def set_autostart(on):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError:
                pass


# ───────────────────────────── smooth images (anti-aliased) ─────────────────────────────
_IMG = {}
_FONTS = {}


def _pil_font(size, bold):
    key = (size, bold)
    if key not in _FONTS:
        names = ["segoeuib.ttf", "DejaVuSans-Bold.ttf"] if bold else ["segoeui.ttf", "DejaVuSans.ttf"]
        f = None
        for n in names:
            try:
                f = ImageFont.truetype(n, size)
                break
            except Exception:
                pass
        _FONTS[key] = f or ImageFont.load_default()
    return _FONTS[key]


def photo(key, make):
    """make() returns a PIL RGBA image; it is cached as a Tk photo."""
    if key not in _IMG:
        _IMG[key] = ImageTk.PhotoImage(make())
    return _IMG[key]


def ss_canvas(w, h, ss=4):
    return Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0)), ss


def pill_image(w, h, fill):
    im, ss = ss_canvas(w, h)
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), radius=h * ss // 2,
                                         fill=hex2rgb(fill) + (255,))
    return im.resize((w, h), Image.LANCZOS)


def switch_image(on, w=70, h=39):
    im, ss = ss_canvas(w, h)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), radius=h * ss // 2,
                        fill=hex2rgb(ACCENT if on else FIELD) + (255,))
    pad = max(1, int(round(h * 0.14))) * ss
    knob = h - 2 * int(round(h * 0.14))
    x = (w * ss - knob * ss - pad) if on else pad
    d.ellipse((x, pad, x + knob * ss, pad + knob * ss), fill=hex2rgb(TEXT if on else MUTED) + (255,))
    return im.resize((w, h), Image.LANCZOS)


# ───────────────────────────── tray icon (own thread) ─────────────────────────────
class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint32), ("dwTime", ctypes.c_uint32)]


_user32.GetLastInputInfo.argtypes = [ctypes.c_void_p]
_user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_user32.RegisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
_user32.UnregisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int]
_user32.GetDoubleClickTime.restype = ctypes.c_uint
_kernel32.GetTickCount.restype = ctypes.c_uint32


ANIM_STEP = 0.05                              # one frame every 50 ms
ANIM_LEN = 2.2                                # total length of the change: eye, two blinks, back to the icon


def _ease_in_out(u):
    u = clamp(u, 0.0, 1.0)
    return u * u * (3 - 2 * u)


def _ease_out_back(u, c1=1.4):
    c3 = c1 + 1
    return 1 + c3 * (u - 1) ** 3 + c1 * (u - 1) ** 2


# a yellow eye: the same in both states
EYE_PAL_ON = {"sclera": (255, 255, 255, 255), "edge": (30, 41, 59, 255), "iris": (245, 158, 11, 255),
              "pupil": (17, 24, 39, 255), "glow": (245, 158, 11, 255)}
EYE_PAL_OFF = dict(EYE_PAL_ON)


def _mix_col(a, b, m):
    return tuple(int(round(a[i] + (b[i] - a[i]) * m)) for i in range(len(a)))


def _tray_eye(on_from, on_to, m, opn, ring):
    """Only the eye, big, on a transparent background. Its colour goes from yellow to red (or back)
    as m goes from 0 to 1. opn = how open the eye is, ring = the pulse ring."""
    S, ss = 256, 2
    W = S * ss
    im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = cy = W / 2.0
    a, b = (EYE_PAL_ON if on_from else EYE_PAL_OFF), (EYE_PAL_ON if on_to else EYE_PAL_OFF)
    pal = {k: _mix_col(a[k], b[k], m) for k in a}
    vy = max(0.05, opn)
    if ring > 0:                                              # a pulse ring after each blink
        r = 126 * ss
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=pal["glow"][:3] + (int(ring * 230),), width=6 * ss)
    rx, ry = 126 * ss, 70 * ss * vy
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=pal["sclera"], outline=pal["edge"], width=7 * ss)
    ir = 60 * ss
    d.ellipse((cx - ir, cy - ir * vy, cx + ir, cy + ir * vy), fill=pal["iris"])
    pr = 28 * ss
    d.ellipse((cx - pr, cy - pr * vy, cx + pr, cy + pr * vy), fill=pal["pupil"])
    if opn > 0.5:
        d.ellipse((cx + 14 * ss, cy - 26 * ss, cx + 26 * ss, cy - 14 * ss), fill=(255, 255, 255, 255))
    return im.resize((S, S), Image.LANCZOS)


ANIM_LEN = 2.0                                # the eye blinks twice, then changes colour


def _anim_frame(t, on_from, on_to):
    """The change at time t: two blinks in the old colour, then the eye changes colour."""
    if t < 1.5:
        opn = 1.0 - max(blink_closed(t, s, 0.3) for s in (0.2, 0.7))
        ring = 0.0
        for e in (0.5, 1.0):
            if t >= e:
                ring = max(ring, 1.0 - min(1.0, (t - e) / 0.35))
        return _tray_eye(on_from, on_from, 0.0, opn, ring)
    m = _ease_in_out((t - 1.5) / 0.5)
    return _tray_eye(on_from, on_to, m, 1.0, 0.0)


def build_transition(on_from, on_to, out_dir, tag):
    paths = []
    n = int(round(ANIM_LEN / ANIM_STEP)) + 1
    for i in range(n):
        frame = _anim_frame(i * ANIM_STEP, on_from, on_to)
        p = os.path.join(out_dir, "%s_%02d.ico" % (tag, i))
        frame.save(p, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (256, 256)])
        paths.append(p)
    return paths


class Tray(threading.Thread):
    def __init__(self, events):
        super().__init__(daemon=True)
        self.events = events
        self.hwnd = None
        self.icon_handle = None
        self.icons = {}
        self.frames = {}                       # transition frames: {True: paths to "on", False: paths to "off"}
        self.animating = False
        self.anim_token = 0
        self._anim_handle = None
        self.tip = APP_NAME
        self.toggle_text = T("pause")
        self.pause_apps = list(DEFAULT_PAUSE_APPS)   # snapshot updated by App.refresh
        self._menu_app_map = {}                      # id -> exe_lower for the open submenu
        self.ready = threading.Event()
        self._taskbar_msg = 0
        self._click_timer = None
        self._after_double = False
        self._wndproc_ref = WNDPROC(self._wndproc)
        self._hook_ref = HOOKPROC(self._ll_hook)

    def run(self):
        try:
            hinst = _kernel32.GetModuleHandleW(None)
            wc = WNDCLASSW()
            wc.lpfnWndProc = self._wndproc_ref
            wc.hInstance = hinst
            wc.lpszClassName = "EyeGuardTrayWindow"
            _user32.RegisterClassW(ctypes.byref(wc))
            self.hwnd = _user32.CreateWindowExW(0, "EyeGuardTrayWindow", APP_NAME, 0,
                                                0, 0, 0, 0, ctypes.c_void_p(HWND_MESSAGE),
                                                None, hinst, None)
            self._taskbar_msg = _user32.RegisterWindowMessageW("TaskbarCreated")
            self.icons = {True: self._load_icon("tray_on.ico"), False: self._load_icon("tray_off.ico")}
            self.icon_handle = self.icons[True]
            self._add_icon()
            _user32.SetWindowsHookExW(WH_MOUSE_LL, self._hook_ref, hinst, 0)
            _user32.RegisterHotKey(self.hwnd, 1, MOD_CONTROL | MOD_ALT, ord("E"))
            _user32.RegisterHotKey(self.hwnd, 2, MOD_CONTROL | MOD_ALT, 0x26)     # Up
            _user32.RegisterHotKey(self.hwnd, 3, MOD_CONTROL | MOD_ALT, 0x28)     # Down
        except Exception as e:
            log("tray start failed: %r" % (e,))
        finally:
            self.ready.set()
        msg = wt.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))

    def _load_icon(self, name="app.ico"):
        h = None
        path = resource(name)
        if os.path.exists(path):
            w = _user32.GetSystemMetrics(SM_CXSMICON)
            hgt = _user32.GetSystemMetrics(SM_CYSMICON)
            h = _user32.LoadImageW(None, path, IMAGE_ICON, w, hgt, LR_LOADFROMFILE)
        if not h:
            h = _user32.LoadIconW(None, ctypes.c_void_p(32512))
        return h

    def _data(self, flags):
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = TRAY_UID
        nid.uFlags = flags
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = self.icon_handle
        nid.szTip = ""                       # no hover text: it would cover the bar above the icon
        return nid

    def _add_icon(self):
        nid = self._data(NIF_MESSAGE | NIF_ICON | NIF_TIP)
        _shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

    def set_tip(self, tip, toggle_text, on=True):
        self.tip = tip
        self.toggle_text = toggle_text
        if not self.animating:
            self.icon_handle = self.icons.get(bool(on)) or self.icon_handle
        if self.hwnd:
            nid = self._data(NIF_MESSAGE | NIF_ICON | NIF_TIP)
            _shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    def play(self, target_on):
        """Plays the change to the new state on the tray icon (in the background)."""
        paths = self.frames.get(bool(target_on))
        if not paths or not self.hwnd:
            return
        self.anim_token += 1
        threading.Thread(target=self._run_anim, args=(self.anim_token, bool(target_on), paths),
                         daemon=True).start()

    def _run_anim(self, token, target_on, paths):
        self.animating = True
        size_x, size_y = _user32.GetSystemMetrics(SM_CXSMICON), _user32.GetSystemMetrics(SM_CYSMICON)
        try:
            for p in paths:
                if token != self.anim_token:
                    return                              # a newer change replaced this one
                h = _user32.LoadImageW(None, p, IMAGE_ICON, size_x, size_y, LR_LOADFROMFILE)
                if h:
                    old, self._anim_handle = self._anim_handle, h
                    self.icon_handle = h
                    nid = self._data(NIF_MESSAGE | NIF_ICON | NIF_TIP)
                    _shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
                    if old:
                        _user32.DestroyIcon(old)
                time.sleep(ANIM_STEP)
        except Exception:
            log("tray animation failed:\n%s" % traceback.format_exc())
        finally:
            if token == self.anim_token:
                self.animating = False
                self.icon_handle = self.icons.get(target_on) or self.icon_handle
                if self._anim_handle:
                    _user32.DestroyIcon(self._anim_handle)
                    self._anim_handle = None
                if self.hwnd:
                    nid = self._data(NIF_MESSAGE | NIF_ICON | NIF_TIP)
                    _shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    def icon_rect(self):
        """Where the tray icon is on the screen: (left, top, right, bottom), or None."""
        if not self.hwnd:
            return None
        ident = NOTIFYICONIDENTIFIER()
        ident.cbSize = ctypes.sizeof(NOTIFYICONIDENTIFIER)
        ident.hWnd = self.hwnd
        ident.uID = TRAY_UID
        rect = wt.RECT()
        if _shell32.Shell_NotifyIconGetRect(ctypes.byref(ident), ctypes.byref(rect)) != 0:
            return None
        return (rect.left, rect.top, rect.right, rect.bottom)

    def remove_icon(self):
        if self.hwnd:
            nid = self._data(0)
            _shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
            self.hwnd = None

    def _wait_for_double_click(self):
        """A single click switches on/off only if no second click follows in time."""
        self._cancel_click()
        delay = max(0.1, _user32.GetDoubleClickTime() / 1000.0)
        self._click_timer = threading.Timer(delay, lambda: self.events.put(("toggle", None)))
        self._click_timer.daemon = True
        self._click_timer.start()

    def _cancel_click(self):
        if self._click_timer is not None:
            self._click_timer.cancel()
            self._click_timer = None

    def _show_menu(self):
        menu = _user32.CreatePopupMenu()
        _user32.AppendMenuW(menu, MF_STRING, ID_TOGGLE, self.toggle_text)
        _user32.AppendMenuW(menu, MF_STRING, ID_BREAK, T("break_now"))
        _user32.AppendMenuW(menu, MF_STRING, ID_SETTINGS, T("settings"))
        _user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)

        # Submenu: pause while using (open programs + checked selected ones)
        sub = _user32.CreatePopupMenu()
        pause_set = {str(p).lower() for p in (self.pause_apps or [])}
        open_apps = list_open_apps()
        # Also show already-selected apps that are not currently open (so user can uncheck)
        open_keys = {exe for exe, _ in open_apps}
        for exe in sorted(pause_set):
            if exe not in open_keys:
                open_apps.append((exe, exe))
        open_apps.sort(key=lambda x: x[1].lower())

        self._menu_app_map = {}
        if not open_apps:
            _user32.AppendMenuW(sub, MF_STRING | MF_GRAYED, 0, T("pause_none"))
        else:
            for i, (exe, display) in enumerate(open_apps):
                if i >= (ID_PAUSE_APP_MAX - ID_PAUSE_APP_BASE):
                    break
                mid = ID_PAUSE_APP_BASE + i
                self._menu_app_map[mid] = exe
                flags = MF_STRING | (MF_CHECKED if exe in pause_set else 0)
                label = display if display else exe
                _user32.AppendMenuW(sub, flags, mid, label)
        _user32.AppendMenuW(sub, MF_SEPARATOR, 0, None)
        _user32.AppendMenuW(sub, MF_STRING, ID_PAUSE_RESET, T("pause_reset"))
        _user32.AppendMenuW(menu, MF_POPUP, sub, T("pause_when"))

        _user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        _user32.AppendMenuW(menu, MF_STRING, ID_EXIT, T("exit"))
        pt = wt.POINT()
        _user32.GetCursorPos(ctypes.byref(pt))
        _user32.SetForegroundWindow(self.hwnd)
        _user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON, pt.x, pt.y, 0, self.hwnd, None)
        _user32.PostMessageW(self.hwnd, 0, 0, 0)
        _user32.DestroyMenu(menu)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TRAY:
                ev = lparam & 0xFFFF
                if ev == WM_LBUTTONUP:
                    if self._after_double:               # second half of a double click
                        self._after_double = False
                    else:
                        self._wait_for_double_click()
                elif ev == WM_LBUTTONDBLCLK:
                    self._cancel_click()
                    self._after_double = True
                    self.events.put(("settings", None))
                elif ev == WM_RBUTTONUP:
                    self._show_menu()
                return 0
            if msg == WM_COMMAND:
                cmd = wparam & 0xFFFF
                if cmd == ID_TOGGLE:
                    self.events.put(("toggle", None))
                elif cmd == ID_BREAK:
                    self.events.put(("break", None))
                elif cmd == ID_SETTINGS:
                    self.events.put(("settings", None))
                elif cmd == ID_EXIT:
                    self.events.put(("exit", None))
                elif cmd == ID_PAUSE_RESET:
                    self.events.put(("pause_reset", None))
                elif ID_PAUSE_APP_BASE <= cmd <= ID_PAUSE_APP_MAX:
                    exe = self._menu_app_map.get(cmd)
                    if exe:
                        self.events.put(("pause_toggle", exe))
                return 0
            if self._taskbar_msg and msg == self._taskbar_msg:
                self._add_icon()
                return 0
            if msg == WM_HOTKEY and wparam in HOTKEYS:
                self.events.put(HOTKEYS[wparam])
                return 0
            if msg == WM_DESTROY:
                _user32.PostQuitMessage(0)
                return 0
        except Exception as e:
            log("tray message error: %r" % (e,))
        return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _over_icon(self, x, y):
        if not self.hwnd:
            return False
        ident = NOTIFYICONIDENTIFIER()
        ident.cbSize = ctypes.sizeof(NOTIFYICONIDENTIFIER)
        ident.hWnd = self.hwnd
        ident.uID = TRAY_UID
        rect = wt.RECT()
        if _shell32.Shell_NotifyIconGetRect(ctypes.byref(ident), ctypes.byref(rect)) != 0:
            return False
        return rect.left <= x <= rect.right and rect.top <= y <= rect.bottom

    def _ll_hook(self, n_code, wparam, lparam):
        try:
            if n_code == 0 and wparam == WM_MOUSEWHEEL:
                info = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                if self._over_icon(info.pt.x, info.pt.y):
                    delta = ctypes.c_short((info.mouseData >> 16) & 0xFFFF).value
                    self.events.put(("preset", -1 if delta > 0 else 1))
                    return 1
        except Exception as e:
            log("hook error: %r" % (e,))
        return _user32.CallNextHookEx(None, n_code, wparam, lparam)


# ───────────────────────────── clickable modern controls ─────────────────────────────
CHIP_W, CHIP_H = 190, 50
ICON_KINDS = ["flame", "candle", "dimbulb", "bulb", "halogen", "tube"]   # one per bulb
SC = 1.4                                                                       # settings size scale


def bulb_image(kind, color, size=30):
    """Nine different icons, one per bulb type."""
    ss = 4
    S = size * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = tuple(color) + (255,)
    dark = (17, 19, 25, 255)

    def bulb(alpha=255, filament=True):
        cc = tuple(color) + (alpha,)
        d.ellipse((S * 0.2, S * 0.05, S * 0.8, S * 0.68), fill=cc)
        d.rounded_rectangle((S * 0.36, S * 0.62, S * 0.64, S * 0.78), radius=S * 0.03, fill=cc)
        d.rounded_rectangle((S * 0.39, S * 0.8, S * 0.61, S * 0.93), radius=S * 0.03, fill=cc)
        if filament:
            d.line([(S * 0.42, S * 0.32), (S * 0.47, S * 0.42), (S * 0.53, S * 0.3), (S * 0.58, S * 0.42)],
                   fill=dark, width=max(2, int(S * 0.035)))

    if kind == "flame":
        d.ellipse((S * 0.22, S * 0.42, S * 0.78, S * 0.95), fill=c)
        d.polygon([(S * 0.22, S * 0.72), (S * 0.5, S * 0.04), (S * 0.78, S * 0.72)], fill=c)
    elif kind == "candle":
        d.rounded_rectangle((S * 0.33, S * 0.38, S * 0.67, S * 0.95), radius=S * 0.04, fill=c)
        d.ellipse((S * 0.41, S * 0.06, S * 0.59, S * 0.32), fill=c)
    elif kind == "dimbulb":                       # soft light: a faint glow with rays around a small dot
        cx, cy = S / 2.0, S * 0.42
        for a in range(0, 360, 60):
            ca, sa = math.cos(math.radians(a + 30)), math.sin(math.radians(a + 30))
            d.line((cx + ca * S * 0.3, cy + sa * S * 0.3, cx + ca * S * 0.44, cy + sa * S * 0.44),
                   fill=tuple(color) + (150,), width=int(S * 0.05))
        d.ellipse((cx - S * 0.12, cy - S * 0.12, cx + S * 0.12, cy + S * 0.12), fill=c)
        d.rounded_rectangle((S * 0.4, S * 0.72, S * 0.6, S * 0.9), radius=S * 0.03, fill=tuple(color) + (150,))
    elif kind == "bulb":                          # classic bulb with filament
        bulb()
    elif kind == "halogen":                       # small upright capsule with two pins
        d.rounded_rectangle((S * 0.36, S * 0.08, S * 0.64, S * 0.78), radius=S * 0.13, fill=c)
        d.rectangle((S * 0.44, S * 0.3, S * 0.56, S * 0.62), fill=dark)
        d.rectangle((S * 0.4, S * 0.8, S * 0.46, S * 0.95), fill=c)
        d.rectangle((S * 0.54, S * 0.8, S * 0.6, S * 0.95), fill=c)
    elif kind == "tube":                          # fluorescent: long tube with end caps
        d.rounded_rectangle((S * 0.08, S * 0.4, S * 0.92, S * 0.6), radius=S * 0.1, fill=c)
        d.rectangle((S * 0.02, S * 0.34, S * 0.06, S * 0.66), fill=c)
        d.rectangle((S * 0.94, S * 0.34, S * 0.98, S * 0.66), fill=c)
    elif kind == "led":                           # LED: ring with a bright centre
        d.ellipse((S * 0.1, S * 0.1, S * 0.9, S * 0.9), outline=c, width=max(2, int(S * 0.1)))
        d.ellipse((S * 0.38, S * 0.38, S * 0.62, S * 0.62), fill=c)
    elif kind == "sun":                           # full sun with rays
        cx = cy = S / 2.0
        r = S * 0.2
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c)
        for a in range(0, 360, 45):
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            d.line((cx + ca * S * 0.3, cy + sa * S * 0.3, cx + ca * S * 0.46, cy + sa * S * 0.46),
                   fill=c, width=int(S * 0.07))
    else:                                         # horizon: sun rising over a line
        d.pieslice((S * 0.22, S * 0.25, S * 0.78, S * 0.81), 180, 360, fill=c)
        d.rounded_rectangle((S * 0.05, S * 0.7, S * 0.95, S * 0.79), radius=S * 0.04, fill=c)
        for a in (200, 270, 340):
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            d.line((S / 2 + ca * S * 0.33, S * 0.53 + sa * S * 0.33, S / 2 + ca * S * 0.44, S * 0.53 + sa * S * 0.44),
                   fill=c, width=int(S * 0.06))
    return im.resize((size, size), Image.LANCZOS)


def track_image(w, h=14):
    ss = 4
    bar = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bar)
    n = len(PRESETS)
    for x in range(w * ss):
        t = x / float(w * ss - 1)                             # left = daylight, right = ember
        k = index_to_kelvin((n - 1) * (1 - t))
        bd.line([(x, 0), (x, h * ss)], fill=kelvin_rgb(k) + (255,))
    mask = Image.new("L", bar.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, bar.size[0] - 1, bar.size[1] - 1), radius=h * ss // 2, fill=255)
    out = Image.new("RGBA", bar.size, (0, 0, 0, 0))
    out.paste(bar, (0, 0), mask)
    return out.resize((w, h), Image.LANCZOS)


UI_SCALE = 1.0


def z(v):
    """A size scaled to the settings window (1.0 = the normal size)."""
    return max(1, int(round(v * UI_SCALE)))


def set_ui_scale(s):
    global UI_SCALE, FONT, FONT_SMALL, FONT_BIG, FONT_BOLD, FONT_CHIP, FONT_TITLE
    UI_SCALE = s
    FONT = ("Segoe UI", z(14))
    FONT_SMALL = ("Segoe UI", z(13))
    FONT_BIG = ("Segoe UI", z(28), "bold")
    FONT_BOLD = ("Segoe UI", z(14), "bold")
    FONT_CHIP = ("Segoe UI", z(11), "bold")
    FONT_TITLE = ("Segoe UI", z(15), "bold")


class Pill(tk.Label):
    """Anti-aliased rounded button. primary/selected paint it in the accent colour."""

    def __init__(self, parent, text, command, w=110, h=32, bg=CARD, primary=False, font=None):
        super().__init__(parent, bd=0, highlightthickness=0, bg=bg, cursor="hand2",
                         font=font or FONT_BOLD, compound="center")
        self.w, self.h, self.text, self.command = w, h, text, command
        self.primary, self.selected = primary, False
        self.bind("<Button-1>", lambda e: self.command() if self.command else None)
        self._paint()

    def set_selected(self, v):
        self.selected = v
        self._paint()

    def set_text(self, text):
        self.text = text
        self._paint()

    def _paint(self):
        active = self.primary or self.selected
        fill = ACCENT if active else FIELD
        img = photo(("pill", self.w, self.h, fill), lambda: pill_image(self.w, self.h, fill))
        self.configure(image=img, text=self.text, fg=BG if active else TEXT)


class Switch(tk.Label):
    W, H = 70, 39

    def __init__(self, parent, value, command, bg=CARD):
        super().__init__(parent, bd=0, highlightthickness=0, bg=bg, cursor="hand2")
        self.W, self.H = z(70), z(39)
        self.value = bool(value)
        self.command = command
        self.bind("<Button-1>", self._click)
        self._paint()

    def _click(self, _=None):
        self.value = not self.value
        self._paint()
        if self.command:
            self.command(self.value)

    def set(self, v):
        self.value = bool(v)
        self._paint()

    def _paint(self):
        img = photo(("switch", self.value, ACCENT, FIELD, self.W, self.H),
                    lambda: switch_image(self.value, self.W, self.H))
        self.configure(image=img)


set_ui_scale(1.0)


# ───────────────────────────── colour picker, flags and language buttons ─────────────────────────────
def icon_disc(kind, color, bg_hex, size=44, glyph=28):
    base = pill_image(size, size, bg_hex).convert("RGBA")
    g = bulb_image(kind, color, glyph)
    off = (size - glyph) // 2
    base.paste(g, (off, off), g)
    return base


def flag_image(code):
    w, h, ss = 34, 24, 4
    W, H = w * ss, h * ss
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if code == "eg":                                   # Egypt
        d.rectangle((0, 0, W, H // 3), fill=(206, 17, 38, 255))
        d.rectangle((0, H // 3, W, 2 * H // 3), fill=(255, 255, 255, 255))
        d.rectangle((0, 2 * H // 3, W, H), fill=(0, 0, 0, 255))
        cx, cy, r = W // 2, H // 2, int(H * 0.13)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(192, 147, 0, 255))
    elif code == "ar":                                 # Saudi Arabia
        d.rectangle((0, 0, W, H), fill=(0, 108, 53, 255))
        d.rectangle((int(W * 0.25), int(H * 0.62), int(W * 0.75), int(H * 0.70)), fill=(255, 255, 255, 255))
    else:                                              # United States
        band = H / 13.0
        for i in range(13):
            d.rectangle((0, int(i * band), W, int((i + 1) * band)),
                        fill=(178, 34, 52, 255) if i % 2 == 0 else (255, 255, 255, 255))
        d.rectangle((0, 0, int(W * 0.42), int(H * 7 / 13.0)), fill=(60, 59, 110, 255))
        for row in range(3):
            for col in range(4):
                x = int(W * 0.07 + col * W * 0.1)
                y = int(H * 0.08 + row * H * 0.17)
                d.ellipse((x, y, x + ss * 2, y + ss * 2), fill=(255, 255, 255, 255))
    im = im.resize((w, h), Image.LANCZOS)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W - 1, H - 1), radius=4 * ss, fill=255)
    im.putalpha(mask.resize((w, h), Image.LANCZOS))
    return im


class LangButton(tk.Canvas):
    def __init__(self, parent, code, name, command):
        super().__init__(parent, width=z(170), height=z(46), bg=CARD, highlightthickness=0, bd=0,
                         cursor="hand2")
        self.code, self.name, self.command = code, name, command
        self.selected = False
        self.bind("<Button-1>", lambda e: self.command(self.code))
        self.draw()

    def set_selected(self, v):
        if v != self.selected:
            self.selected = v
            self.draw()

    def draw(self):
        self.delete("all")
        W, H = z(170), z(46)
        fill = ACCENT if self.selected else FIELD
        self.create_image(0, 0, anchor="nw", image=photo(("pill", W, H, fill), lambda: pill_image(W, H, fill)))
        self.create_image(z(14), H // 2, anchor="w",
                          image=photo(("flag", self.code, z(34)), lambda: flag_image(self.code)))
        self.create_text(z(48) + (W - z(56)) // 2, H // 2, text=self.name,
                         fill=BG if self.selected else TEXT, font=FONT_CHIP)


def pin_button_image(size, active):
    """A round button with a location pin. Active = filled with the accent colour."""
    base = pill_image(size, size, ACCENT if active else FIELD).convert("RGBA")
    ss = 4
    S = size * ss
    glyph = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(glyph)
    col = hex2rgb(BG if active else ACCENT) + (255,)
    cx, cy, r = S / 2.0, S * 0.40, S * 0.20
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
    d.polygon([(cx - 0.866 * r, cy + 0.5 * r), (cx, S * 0.80), (cx + 0.866 * r, cy + 0.5 * r)], fill=col)
    r2 = S * 0.085
    d.ellipse((cx - r2, cy - r2, cx + r2, cy + r2), fill=(0, 0, 0, 0))
    glyph = glyph.resize((size, size), Image.LANCZOS)
    base.paste(glyph, (0, 0), glyph)
    return base


class PinButton(tk.Label):
    """The "find my location" button. It pulses while the location is being found."""

    def __init__(self, parent, command, size=42, bg=CARD):
        super().__init__(parent, bd=0, highlightthickness=0, bg=bg, cursor="hand2")
        self.px, self.command = size, command
        self.busy, self.phase, self.job = False, False, None
        self.bind("<Button-1>", lambda e: self.command() if self.command else None)
        self._paint()

    def _paint(self):
        size, active = self.px, bool(self.busy and self.phase)
        self.configure(image=photo(("pin", size, active), lambda: pin_button_image(size, active)))

    def set_busy(self, v):
        v = bool(v)
        if v == self.busy:
            return
        self.busy, self.phase = v, v
        self._paint()
        if v:
            self.job = self.after(450, self._pulse)
        elif self.job is not None:
            try:
                self.after_cancel(self.job)
            except Exception:
                pass
            self.job = None

    def _pulse(self):
        if not self.busy:
            return
        try:
            self.phase = not self.phase
            self._paint()
            self.job = self.after(450, self._pulse)
        except tk.TclError:
            self.busy = False


class CityPicker:
    """A small window with a search box and the list of capitals. One click on a name picks it."""

    def __init__(self, parent, on_pick, current_key):
        self.on_pick = on_pick
        rtl = LANG in ("eg", "ar")
        top = tk.Toplevel(parent)
        self.top = top
        top.title(T("city_pick"))
        top.configure(bg=BG)
        top.transient(parent)
        w, h = z(420), z(560)
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        top.geometry("%dx%d+%d+%d" % (w, h, px + max(0, (pw - w) // 2), py + max(0, (ph - h) // 2)))
        top.bind("<MouseWheel>", lambda e: "break")        # the settings page must not scroll behind this window
        top.bind("<Escape>", lambda e: self.close())

        tk.Label(top, text=T("city_pick"), bg=BG, fg=TEXT, font=FONT_TITLE).pack(pady=(z(16), 0))
        self.var = tk.StringVar()
        self.entry = tk.Entry(top, textvariable=self.var, bg=FIELD, fg=TEXT, insertbackground=TEXT, relief="flat",
                              font=FONT, justify="right" if rtl else "left", highlightthickness=0)
        self.entry.pack(fill="x", padx=z(18), pady=(z(12), z(10)), ipady=z(8))
        body = tk.Frame(top, bg=CARD)
        body.pack(fill="both", expand=True, padx=z(18), pady=(0, z(18)))
        sb = tk.Scrollbar(body, orient="vertical")
        self.box = tk.Listbox(body, bg=CARD, fg=TEXT, selectbackground=ACCENT, selectforeground=BG,
                              activestyle="none", relief="flat", highlightthickness=0, bd=0, font=FONT,
                              exportselection=False, yscrollcommand=sb.set)
        sb.configure(command=self.box.yview)
        sb.pack(side="right", fill="y")
        self.box.pack(side="left", fill="both", expand=True, padx=(z(6), 0), pady=z(6))

        # every list entry sorted by the city name in the screen language
        self.order = sorted(range(len(CITIES)), key=lambda i: norm(place_names(CITIES[i])[0]))
        self.shown = []
        self.current = city_index(current_key)
        self.var.trace_add("write", lambda *a: self.fill())
        self.box.bind("<ButtonRelease-1>", self.pick_clicked)
        self.entry.bind("<Return>", self.pick_first)
        self.entry.bind("<Down>", self.to_list)
        self.box.bind("<Return>", self.pick_clicked)
        self.fill()
        self.entry.focus_set()
        top.after(100, self.entry.focus_force)

    def fill(self):
        q = norm(self.var.get().strip())
        self.box.delete(0, "end")
        self.shown = []
        for i in self.order:
            c = CITIES[i]
            if q and q not in norm(" ".join((c[0], c[1], c[2], c[3]))):
                continue
            name, country = place_names(c)
            self.shown.append(i)
            self.box.insert("end", "  %s  —  %s" % (name, country))
        if not self.shown:
            self.box.insert("end", "  " + T("city_none"))
        elif not q and self.current in self.shown:
            row = self.shown.index(self.current)
            self.box.selection_set(row)
            self.box.see(row)

    def pick_row(self, row):
        if 0 <= row < len(self.shown):
            key = CITIES[self.shown[row]][0]
            self.close()
            self.on_pick(key)

    def pick_clicked(self, e=None):
        sel = self.box.curselection()
        if sel:
            self.pick_row(sel[0])

    def pick_first(self, e=None):
        self.pick_row(0)

    def to_list(self, e=None):
        self.box.focus_set()
        if self.shown and not self.box.curselection():
            self.box.selection_set(0)
        return "break"

    def close(self):
        try:
            self.top.destroy()
        except Exception:
            pass


class ColourPicker(tk.Canvas):
    """Bulb icons in one row, a pointer under the current colour, and a smooth slider below.
    Moving right = more yellow (same as the mouse wheel)."""

    def __init__(self, parent, kelvin, command):
        self.W, self.H, self.PAD, self.ICON = z(480), z(130), z(34), z(44)
        super().__init__(parent, width=self.W, height=self.H, bg=CARD, highlightthickness=0, bd=0,
                         cursor="hand2")
        self.kelvin = kelvin
        self.command = command
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._press)
        self.draw()

    def _x(self, k):
        n = len(PRESETS)
        return self.PAD + (n - 1 - kelvin_to_index(k)) * (self.W - 2 * self.PAD) / float(n - 1)

    def _k(self, x):
        n = len(PRESETS)
        idx = (n - 1) - (x - self.PAD) / float(self.W - 2 * self.PAD) * (n - 1)
        return index_to_kelvin(idx)

    def _set(self, k):
        k = int(round(clamp(k, KMIN, KMAX) / 10.0) * 10)
        if k != self.kelvin:
            self.kelvin = k
            self.draw()
            self.command(k)

    def _press(self, e):
        if e.y <= z(52):                                # bulb row: jump to that bulb
            i = min(range(len(PRESETS)), key=lambda j: abs(self._x(PRESETS[j][1]) - e.x))
            if abs(self._x(PRESETS[i][1]) - e.x) <= self.ICON / 2.0:
                self._set(PRESETS[i][1])
            return
        self._set(self._k(clamp(e.x, self.PAD, self.W - self.PAD)))

    def step(self, d):
        self._set(self.kelvin + d * KWHEEL)

    def set(self, k):
        if k != self.kelvin:
            self.kelvin = k
            self.draw()

    def draw(self):
        self.delete("all")
        active = nearest_index(self.kelvin)
        icon = self.ICON
        for i in range(len(PRESETS)):
            x = self._x(PRESETS[i][1])
            on = i == active
            fill = ACCENT if on else FIELD
            color = hex2rgb(BG) if on else kelvin_rgb(PRESETS[i][1])
            self.create_image(x - icon / 2, z(6), anchor="nw",
                              image=photo(("disc", i, on, icon), lambda i=i, color=color, fill=fill:
                                          icon_disc(ICON_KINDS[i], color, fill, icon, z(28))))
        x = self._x(self.kelvin)
        tw, th = z(20), z(15)                           # the pointer: a triangle with rounded corners
        self.create_image(x, z(63), image=photo(("ptr", tw, th), lambda: round_tri_image(tw, th, ACCENT)))
        self.create_image(self.PAD, z(101), anchor="nw",
                          image=photo(("track", self.W), lambda: track_image(self.W - 2 * self.PAD)))
        ks = z(26)                                      # the knob: an anti-aliased circle
        self.create_image(x, z(108), image=photo(("knob", ks), lambda: knob_image(ks)))


def power_image(on, size=44):
    """The power symbol: yellow when EyeGuard runs, red when it is stopped."""
    ss = 4
    S = size * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    color = hex2rgb(ACCENT) + (255,) if on else (239, 68, 68, 255)
    pad = S * 0.14
    box = (pad, pad, S - pad, S - pad)
    w = int(S * 0.09)
    d.arc(box, start=-60, end=240, fill=color, width=w)            # ring with a gap at the top
    cx, cy, R = S / 2.0, S / 2.0, (S - 2 * pad) / 2.0
    d.line((cx, cy - R * 1.12, cx, cy - R * 0.1), fill=color, width=w)
    return im.resize((size, size), Image.LANCZOS)


def round_tri_image(w, h, color):
    """An upward triangle with rounded corners, smooth at the edges."""
    ss = 8
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).polygon([(w * ss / 2.0, 0), (0, h * ss), (w * ss, h * ss)], fill=255)
    im = im.filter(ImageFilter.GaussianBlur(ss * 1.2)).point(lambda v: 255 if v > 128 else 0)
    im = im.filter(ImageFilter.GaussianBlur(ss * 0.6))
    alpha = im.resize((w, h), Image.LANCZOS)
    out = Image.new("RGBA", (w, h), hex2rgb(color) + (255,))
    out.putalpha(alpha)
    return out


def knob_image(size=22):
    ss = 4
    S = size * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((ss, ss, S - ss - 1, S - ss - 1), fill=hex2rgb(TEXT) + (255,),
                               outline=hex2rgb(ACCENT) + (255,), width=3 * ss)
    return im.resize((size, size), Image.LANCZOS)


class PercentSlider(tk.Canvas):
    """Percent slider. Subclasses only set their own range (LO, HI, STEP)."""
    LO, HI, STEP = 20, 100, 5

    def __init__(self, parent, value, command):
        self.W, self.H, self.PAD = z(600), z(40), z(20)
        super().__init__(parent, width=self.W, height=self.H, bg=CARD, highlightthickness=0, bd=0,
                         cursor="hand2")
        self.value = value
        self.command = command
        self.bind("<Button-1>", self._drag)
        self.bind("<B1-Motion>", self._drag)
        self.draw()

    def _x(self, v):
        return self.PAD + (v - self.LO) / float(self.HI - self.LO) * (self.W - 2 * self.PAD)

    def _drag(self, e):
        frac = (clamp(e.x, self.PAD, self.W - self.PAD) - self.PAD) / float(self.W - 2 * self.PAD)
        v = int(round((self.LO + frac * (self.HI - self.LO)) / float(self.STEP)) * self.STEP)
        v = int(clamp(v, self.LO, self.HI))
        if v != self.value:
            self.value = v
            self.draw()
            self.command(v)

    def set(self, v):
        if v != self.value:
            self.value = v
            self.draw()

    def draw(self):
        self.delete("all")
        track_w = self.W - 2 * self.PAD
        th = z(8)
        y = (self.H - th) // 2
        self.create_image(self.PAD, y, anchor="nw", image=photo(("ptrack", track_w, th), lambda: pill_image(track_w, th, FIELD)))
        x = self._x(self.value)
        fw = max(th, int(x - self.PAD))
        self.create_image(self.PAD, y, anchor="nw", image=photo(("pfill", fw, th), lambda: pill_image(fw, th, ACCENT)))
        ks = z(22)
        self.create_image(x, self.H // 2, image=photo(("knob", ks), lambda: knob_image(ks)))


class SpeedSlider(PercentSlider):
    LO, HI, STEP = 25, 200, 5


class TimeField(tk.Frame):
    """Time entry in 12-hour form with an AM/PM button (ص / م in Arabic)."""

    def __init__(self, parent, value24, on_change):
        super().__init__(parent, bg=CARD)
        txt, self.pm = to12(value24)
        self.enabled = True
        self.on_change = on_change
        self.entry = tk.Entry(self, width=6, bg=FIELD, fg=TEXT, insertbackground=TEXT, relief="flat",
                              font=FONT, justify="center")
        self.entry.insert(0, txt)
        self.entry.pack(side="left", ipady=6)
        self.entry.bind("<KeyRelease>", lambda e: self.on_change(False))
        self.entry.bind("<FocusOut>", lambda e: self.on_change(True))
        self.toggle = Pill(self, self._pm_label(), self._flip, w=z(60), h=z(42), bg=CARD)
        self.toggle.pack(side="left", padx=(6, 0))

    def _pm_label(self):
        return T("pm") if self.pm else T("am")

    def _flip(self):
        if self.enabled:
            self.pm = not self.pm
            self.toggle.set_text(self._pm_label())
            self.on_change(True)

    def get24(self):
        return to24(self.entry.get(), self.pm)

    def set24(self, value24):
        txt, self.pm = to12(value24)
        self.entry.delete(0, "end")
        self.entry.insert(0, txt)
        self.toggle.set_text(self._pm_label())

    def set_enabled(self, on):
        self.enabled = on
        self.entry.configure(state="normal" if on else "disabled")


# ───────────────────────────── settings window ─────────────────────────────
class EyeLogo(tk.Label):
    """The program logo. When EyeGuard is switched on, its eye blinks three times. The eye always stays open."""
    STEPS = 20

    def __init__(self, parent, base, size):
        super().__init__(parent, bd=0, highlightthickness=0, bg=BG)
        self.size = size
        self.base = base.convert("RGBA").resize((512, 512), Image.LANCZOS)
        self.hand = self.base.getpixel((256, 430))             # the colour of the hand, under the eye
        self.frames = [ImageTk.PhotoImage(self._frame(i / float(self.STEPS)).resize((size, size), Image.LANCZOS))
                       for i in range(self.STEPS + 1)]
        self.state = None
        self.after_id = None
        self._show(self.STEPS)

    def _frame(self, openness):
        cx, cy, rx, ry = 256, 322, 116, 78                       # the eye on the 512 px logo
        eye = Image.new("L", (512, 512), 0)
        ImageDraw.Draw(eye).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
        opening = Image.new("L", (512, 512), 0)
        hy = max(0.0, openness * ry)
        ImageDraw.Draw(opening).ellipse((cx - rx, cy - hy, cx + rx, cy + hy), fill=255)
        covered = ImageChops.subtract(eye, opening)              # the eyelids
        frame = self.base.copy()
        frame.paste(Image.new("RGBA", (512, 512), self.hand), (0, 0), covered)
        return frame

    def _show(self, idx):
        self.configure(image=self.frames[idx])

    def set_state(self, on, animate=True):
        if on == self.state:
            return
        self.state = on
        if self.after_id is not None:
            self.after_cancel(self.after_id)
            self.after_id = None
        if on and animate:
            self._t0 = time.monotonic()
            self._blink()
        else:
            self._show(self.STEPS)

    def _blink(self):
        t = time.monotonic() - self._t0
        if t >= 1.4:
            self._show(self.STEPS)
            self.after_id = None
            return
        closed = max(blink_closed(t, start, 0.3) for start in (0.1, 0.5, 0.9))   # three blinks
        self._show(int(round((1 - closed) * self.STEPS)))
        self.after_id = self.after(33, self._blink)


class TrayHint:
    """A bar above the tray icon while the wheel turns: a line that shows where the colour is.
    It can be dragged, and it fades away two seconds after the last touch."""
    W, H, PAD = 210, 50, 16                        # 25% narrower than before
    HOLD_MS = 2000
    ALPHA = 0.95
    GLIDE_MS = 160

    def __init__(self, app):
        self.app = app
        self.alive = True
        self.fading = False
        self.token = 0
        self.gtok = 0
        self._hide_job = None
        self.shown_k = float(app.cfg["kelvin"])        # where the knob is drawn (it glides to the new colour)
        self.x, self.y = self._place()
        win = tk.Toplevel(app.root)
        self.win = win
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        try:
            win.attributes("-transparentcolor", BG)           # the rounded corners show the desktop
        except tk.TclError:
            pass
        win.configure(bg=BG)
        win.geometry("%dx%d+%d+%d" % (self.W, self.H, self.x, self.y + 12))
        win.attributes("-alpha", 0.0)
        c = tk.Canvas(win, width=self.W, height=self.H, bg=BG, highlightthickness=0, bd=0, cursor="hand2")
        c.pack()
        self.c = c
        c.bind("<Button-1>", self._drag)
        c.bind("<B1-Motion>", self._drag)
        self.touch()
        self._animate(180, self._in_step)

    def _place(self):
        sw = self.app.root.winfo_screenwidth()
        sh = self.app.root.winfo_screenheight()
        r = self.app.tray.icon_rect()
        if r:
            cx, top = (r[0] + r[2]) // 2, r[1]
        else:
            cx, top = sw - 60, sh - 60
        x = int(clamp(cx - self.W // 2, 0, sw - self.W))
        return x, max(0, top - self.H - 10)

    def _x_of(self, k):
        P, n = self.PAD, len(PRESETS)
        return P + (n - 1 - kelvin_to_index(k)) * (self.W - 2 * P) / float(n - 1)

    def _draw(self):
        if not self.alive:
            return
        c, W, H, P = self.c, self.W, self.H, self.PAD
        c.delete("all")
        c.create_image(0, 0, anchor="nw", image=photo(("hint_bg", W, H), lambda: pill_image(W, H, CARD)))
        # the line, and the knob where the colour is now
        tw = W - 2 * P
        c.create_image(P, (H - 10) // 2, anchor="nw", image=photo(("hint_track", tw), lambda: track_image(tw, 10)))
        c.create_image(self._x_of(self.shown_k), H // 2, image=photo(("hint_knob",), lambda: knob_image(18)))

    def _glide(self, target):
        """The knob slides to the new colour, instead of jumping."""
        start = self.shown_k
        if abs(target - start) < 1:
            self.shown_k = float(target)
            self._draw()
            return
        self.gtok += 1
        tok = self.gtok
        t0 = time.monotonic()

        def tick():
            if tok != self.gtok or not self.alive:
                return
            p = min(1.0, (time.monotonic() - t0) * 1000.0 / self.GLIDE_MS)
            e = p * p * (3 - 2 * p)
            self.shown_k = start + (target - start) * e
            self._draw()
            if p < 1.0:
                try:
                    self.win.after(16, tick)
                except tk.TclError:
                    pass
            else:
                self.shown_k = float(target)
        tick()

    def _drag(self, e):
        """The knob follows the mouse directly while dragging (no gliding, so it never lags behind)."""
        P, W, n = self.PAD, self.W, len(PRESETS)
        x = clamp(e.x, P, W - P)
        idx = (n - 1) - (x - P) / float(W - 2 * P) * (n - 1)
        k = int(round(index_to_kelvin(idx) / 10.0) * 10)
        self.gtok += 1                                    # stop any glide that is still running
        self.shown_k = float(k)
        self.app.set_kelvin(k)
        self._draw()
        self._keep_alive()

    def _set_alpha(self, a):
        try:
            self.win.attributes("-alpha", max(0.01, min(1.0, a)))
        except tk.TclError:
            pass

    def _animate(self, ms, step, done=None):
        self.token += 1
        tok = self.token
        t0 = time.monotonic()

        def tick():
            if tok != self.token or not self.alive:
                return
            p = min(1.0, (time.monotonic() - t0) * 1000.0 / ms)
            e = p * p * (3 - 2 * p)                           # smooth start and end
            step(e)
            if p < 1.0:
                try:
                    self.win.after(16, tick)
                except tk.TclError:
                    pass
            elif done:
                done()
        tick()

    def _in_step(self, e):
        self._set_alpha(self.ALPHA * e)
        self.win.geometry("%dx%d+%d+%d" % (self.W, self.H, self.x, self.y + int(12 * (1 - e))))

    def _out_step(self, e):
        self._set_alpha(self.ALPHA * (1 - e))

    def touch(self):
        """Called on every wheel notch: shows the bar, glides the knob and starts the two seconds again."""
        self._glide(self.app.cfg["kelvin"])
        self._keep_alive()

    def _keep_alive(self):
        if self._hide_job is not None:
            try:
                self.win.after_cancel(self._hide_job)
            except Exception:
                pass
        self._hide_job = self.win.after(self.HOLD_MS, self.fade_out)
        if self.fading:
            self.fading = False
            self._animate(160, lambda e: self._set_alpha(self.ALPHA * e))

    def fade_out(self):
        self._hide_job = None
        self.fading = True
        self._animate(450, self._out_step, self.destroy)

    def destroy(self):
        if not self.alive:
            return
        self.alive = False
        try:
            self.win.destroy()
        finally:
            self.app.hint = None


class SettingsWindow:
    """The settings window. It can be resized: when the size changes, everything is redrawn at that size."""
    BASE_W, BASE_H = 760, 880

    def __init__(self, app):
        self.app = app
        self.lang_btns = {}
        self.canvas = None
        self.city_msg = ""
        self.city_picker = None
        self.update_spinner = None
        self._spinner_job = None
        self._spinner_angle = 0
        self.scale = 1.0
        self._resize_job = None
        win = tk.Toplevel(app.root)
        self.win = win
        win.title(APP_NAME)
        win.configure(bg=BG)
        win.geometry("%dx%d" % (self.BASE_W, self.BASE_H))
        win.minsize(540, 560)
        win.protocol("WM_DELETE_WINDOW", self.close)
        win.bind("<Configure>", self._on_configure)
        self._build()
        win.lift()
        win.focus_force()

    def start_update_spinner(self):
        if not self.update_spinner or not self.win.winfo_exists():
            return
        self.update_spinner.pack(side="left", padx=(z(9), 0))
        self._spin_update()

    def _spin_update(self):
        if not self.update_spinner or not self.update_spinner.winfo_exists():
            return
        c = self.update_spinner
        c.delete("all")
        size = max(14, z(16))
        pad = z(3)
        self._spinner_angle = (self._spinner_angle + 32) % 360
        c.create_arc(pad, pad, size + pad, size + pad, start=self._spinner_angle,
                     extent=275, style="arc", outline=ACCENT, width=max(2, z(2)))
        self._spinner_job = self.win.after(55, self._spin_update)

    def stop_update_spinner(self):
        if self._spinner_job is not None:
            try:
                self.win.after_cancel(self._spinner_job)
            except Exception:
                pass
            self._spinner_job = None
        if self.update_spinner and self.update_spinner.winfo_exists():
            self.update_spinner.pack_forget()

    def _on_configure(self, e):
        if e.widget is not self.win:
            return
        if self._resize_job is not None:
            try:
                self.win.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.win.after(150, self._resized)

    def _resized(self):
        self._resize_job = None
        w, h = self.win.winfo_width(), self.win.winfo_height()
        if w < 2 or h < 2:
            return
        s = clamp(min(w / float(self.BASE_W), h / float(self.BASE_H)), 0.6, 1.8)
        if abs(s - self.scale) < 0.04:
            return
        self.scale = s
        self._build()

    def _build(self):
        if self.canvas is not None:
            try:
                self.canvas.unbind_all("<MouseWheel>")
            except Exception:
                pass
        for child in self.win.winfo_children():
            child.destroy()
        set_ui_scale(self.scale)
        self.rtl = LANG in ("eg", "ar")
        self.anchor_start = "e" if self.rtl else "w"
        self.side_start = "right" if self.rtl else "left"
        self.side_end = "left" if self.rtl else "right"
        self.lang_btns = {}
        win, app = self.win, self.app

        # footer first, so it always sits at the very end of the window
        foot = tk.Frame(win, bg=BG)
        foot.pack(side="bottom", pady=(0, z(14)))
        tk.Label(foot, text="Made by ", bg=BG, fg=MUTED, font=FONT_SMALL).pack(side="left")
        link = tk.Label(foot, text="a7yanan", bg=BG, fg=ACCENT, font=FONT_BOLD, cursor="hand2")
        link.pack(side="left")
        link.bind("<Button-1>", lambda e: webbrowser.open(AUTHOR_URL))

        # scrollable body, so everything fits on small screens too
        area = tk.Frame(win, bg=BG)
        area.pack(side="top", fill="both", expand=True)
        sb = tk.Scrollbar(area, orient="vertical")
        canvas = tk.Canvas(area, bg=BG, highlightthickness=0, bd=0, yscrollcommand=sb.set)
        sb.configure(command=canvas.yview)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(canvas, bg=BG)
        win_id = canvas.create_window(0, 0, anchor="nw", window=body)
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width))
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self.canvas = canvas
        canvas.bind_all("<MouseWheel>", self._on_wheel)

        head = tk.Frame(body, bg=BG)
        head.pack(fill="x", padx=z(30), pady=(z(22), z(8)))
        self.logo = EyeLogo(head, self._logo_base(), z(64))
        self.logo.pack(side=self.side_start)
        titles = tk.Frame(head, bg=BG)
        titles.pack(side=self.side_start, padx=z(14))
        tk.Label(titles, text=APP_NAME, bg=BG, fg=TEXT, font=FONT_BIG).pack(anchor=self.anchor_start)
        tk.Label(titles, text=T("tagline"), bg=BG, fg=MUTED, font=FONT_SMALL).pack(anchor=self.anchor_start)
        pwr = tk.Frame(head, bg=BG)
        pwr.pack(side=self.side_end)
        self.remote = tk.Label(pwr, bg=BG, bd=0)
        self.remote.pack(pady=(0, z(4)))
        self.power = Pill(pwr, "", app.toggle_power, w=z(130), h=z(50), bg=BG, font=FONT_BOLD)
        self.power.pack()

        # ── colour ──
        c1 = self._card(body)
        self._title(c1, T("colour"))
        cur = tk.Frame(c1, bg=CARD)
        cur.pack(pady=(z(10), 0))
        self.cur_icon = tk.Label(cur, bg=CARD, bd=0)
        self.cur_icon.pack(side="left")
        self.value_label = tk.Label(cur, text="", bg=CARD, fg=ACCENT, font=FONT_BOLD)
        self.value_label.pack(side="left", padx=z(10))
        self.picker = ColourPicker(c1, app.cfg["kelvin"], self.pick_kelvin)
        self.picker.pack(pady=(z(6), 0))
        tk.Label(c1, text=T("colour_tip"), bg=CARD, fg=MUTED, font=FONT_SMALL,
                 wraplength=z(580)).pack(pady=(z(8), 0))
        self.color_warn = tk.Label(c1, text="", bg=CARD, fg=ACCENT, font=FONT_SMALL, wraplength=z(580))
        self.color_warn.pack(pady=(z(4), 0))

        # ── eye reminders ──
        c2 = self._card(body)
        self._title(c2, T("reminders"))
        r = self._row(c2)
        self._label(r, T("remind_on"))
        Switch(r, app.cfg["remind_on"], lambda v: app.set_option("remind_on", v)).pack(side=self.side_end)
        r = self._row(c2)
        self._label(r, T("remind_every"))
        step = tk.Frame(r, bg=CARD)
        step.pack(side=self.side_end)
        Pill(step, "+", lambda: app.step_minutes(5), w=z(48), h=z(42), bg=CARD).pack(side="left")
        self.minutes_label = tk.Label(step, text="", bg=CARD, fg=TEXT, font=FONT_BOLD, width=9)
        self.minutes_label.pack(side="left")
        Pill(step, "−", lambda: app.step_minutes(-5), w=z(48), h=z(42), bg=CARD).pack(side="left")
        r = self._row(c2)
        self._label(r, T("skip_idle"))
        Switch(r, app.cfg["remind_skip_idle"], lambda v: app.set_option("remind_skip_idle", v)).pack(side=self.side_end)
        r = self._row(c2)
        self._label(r, T("try_now"))
        Pill(r, T("start"), app.show_break, w=z(126), h=z(42), bg=CARD, primary=True).pack(side=self.side_end)
        r = self._row(c2)
        self._label(r, T("opacity"))
        self.opacity_label = tk.Label(r, text="", bg=CARD, fg=ACCENT, font=FONT_BOLD)
        self.opacity_label.pack(side=self.side_end)
        self.opacity_slider = PercentSlider(c2, app.cfg["overlay_opacity"], self.on_opacity)
        self.opacity_slider.pack(anchor=self.anchor_start, pady=(z(4), 0))
        r = self._row(c2)
        self._label(r, T("speed"))
        self.speed_label = tk.Label(r, text="", bg=CARD, fg=ACCENT, font=FONT_BOLD)
        self.speed_label.pack(side=self.side_end)
        self.speed_slider = SpeedSlider(c2, app.cfg["eye_speed"], self.on_speed)
        self.speed_slider.pack(anchor=self.anchor_start, pady=(z(4), 0))

        # ── general ──
        c3 = self._card(body)
        self._title(c3, T("general"))
        r = self._row(c3)
        self._label(r, T("start_win"))
        self.autostart_switch = Switch(r, autostart_enabled(), self.on_autostart)
        self.autostart_switch.pack(side=self.side_end)
        r = self._row(c3)
        self._label(r, T("auto_sun"))
        self.auto_sun_switch = Switch(r, app.cfg.get("auto_sun", False), self.on_auto_sun)
        self.auto_sun_switch.pack(side=self.side_end)
        r = self._row(c3)
        self._label(r, T("city"))
        box = tk.Frame(r, bg=CARD)
        box.pack(side=self.side_end)
        self.city_pill = Pill(box, "", self.open_city_picker, w=z(220), h=z(42), bg=CARD)
        self.city_pill.pack(side="left")
        self.pin = PinButton(box, self.on_locate, size=z(42))
        self.pin.pack(side="left", padx=(z(8), 0))
        self.city_row = r
        self.city_status = tk.Label(c3, text="", bg=CARD, fg=ACCENT, font=FONT_SMALL, wraplength=z(560))
        r = self._row(c3)
        self._label(r, T("fullscreen"))
        Switch(r, app.cfg.get("pause_fullscreen", True), lambda v: app.set_option("pause_fullscreen", v)).pack(side=self.side_end)
        r = self._row(c3)
        self._label(r, T("schedule"))
        self.schedule_switch = Switch(r, app.cfg["schedule_on"], self.on_schedule_switch)
        self.schedule_switch.pack(side=self.side_end)
        r = self._row(c3)
        times = tk.Frame(r, bg=CARD)
        times.pack(side=self.side_end, padx=(0, z(12)))
        tk.Label(times, text=T("from"), bg=CARD, fg=MUTED, font=FONT).pack(side="left", padx=(z(8), z(8)))
        self.start_field = TimeField(times, app.cfg["start"], self.save_schedule)
        self.start_field.pack(side="left")
        tk.Label(times, text=T("to"), bg=CARD, fg=MUTED, font=FONT).pack(side="left", padx=(z(8), z(8)))
        self.end_field = TimeField(times, app.cfg["end"], self.save_schedule)
        self.end_field.pack(side="left")
        r = self._row(c3)
        self._label(r, T("language"))
        langs = tk.Frame(r, bg=CARD)
        langs.pack(side=self.side_end)
        for code, name in LANGS:
            b = LangButton(langs, code, name, app.set_lang)
            b.pack(side="left", padx=(z(6), 0))
            self.lang_btns[code] = b

        # ── updates (at the end of settings) ──
        r = self._row(c3)
        self._label(r, T("auto_update"))
        Switch(r, app.cfg.get("auto_update", True), lambda v: app.set_option("auto_update", v)).pack(side=self.side_end)
        r = self._row(c3)
        self._label(r, T("check_update") + "  V" + APP_VERSION)
        update_controls = tk.Frame(r, bg=CARD)
        update_controls.pack(side=self.side_end)
        Pill(update_controls, T("check_update"), app.check_update_interactive, w=z(160), h=z(42), bg=CARD).pack(side="left")
        self.update_spinner = tk.Canvas(update_controls, width=z(22), height=z(22), bg=CARD,
                                        highlightthickness=0, bd=0)
        self.update_spinner.pack(side="left", padx=(z(9), 0))
        self.update_spinner.pack_forget()

        self._power_state = None
        self.sync_all()

    def _logo_base(self):
        for name in ("logo.png", "app.ico"):
            path = resource(name)
            if os.path.exists(path):
                return Image.open(path).convert("RGBA")
        return Image.new("RGBA", (512, 512), (0, 0, 0, 0))

    def _card(self, parent):
        card = tk.Frame(parent, bg=CARD, padx=z(24), pady=z(18))
        card.pack(fill="x", padx=z(28), pady=(0, z(14)))
        return card

    def _title(self, card, text):
        tk.Label(card, text=text, bg=CARD, fg=TEXT, font=FONT_TITLE).pack(anchor=self.anchor_start)

    def _row(self, card):
        r = tk.Frame(card, bg=CARD)
        r.pack(fill="x", pady=(z(14), 0))
        return r

    def _label(self, row, text):
        tk.Label(row, text=text, bg=CARD, fg=TEXT, font=FONT).pack(side=self.side_start)

    # keep the controls in step with the saved settings
    def pick_kelvin(self, k):
        self.app.set_kelvin(k)

    def _on_wheel(self, e):
        """Wheel over the colour picker moves the colour; anywhere else it scrolls the page."""
        w = None
        try:
            w = self.win.winfo_containing(e.x_root, e.y_root)
        except Exception:
            pass
        node = w
        while node is not None:
            if node is self.picker:
                self.picker.step(-1 if e.delta > 0 else 1)
                return
            node = getattr(node, "master", None)
        self.canvas.yview_scroll(int(-e.delta / 120), "units")

    def sync_color(self):
        k = self.app.cfg["kelvin"]
        i = nearest_index(k)
        self.picker.set(k)
        self.color_warn.config(text="" if self.app.color_ok else T("color_fail"))
        self.cur_icon.configure(image=photo(("cur", i, z(40)), lambda: bulb_image(ICON_KINDS[i], kelvin_rgb(k), z(40))))
        self.value_label.config(text="%dK  ·  %s" % (k, preset_name(k)))

    def sync_power(self):
        on = self.app.is_on()
        if getattr(self, "_power_state", None) == on:
            return
        first = getattr(self, "_power_state", None) is None
        self._power_state = on
        self.logo.set_state(on, animate=not first)
        self.remote.configure(image=photo(("power", on, z(44)), lambda: power_image(on, z(44))))
        self.power.primary = on
        self.power.set_text(T("on") if on else T("off"))
        self.power.set_selected(False)

    def sync_reminders(self):
        self.minutes_label.config(text=T("minutes", self.app.cfg["remind_every"]))

    def sync_city(self):
        text = city_label(self.app.cfg)
        self.city_pill.set_text(text if len(text) <= 22 else text[:21] + "…")
        self.pin.set_busy(self.app.locating)
        msg = T("locating") if self.app.locating else self.city_msg
        if msg:
            self.city_status.config(text=msg, justify="right" if self.rtl else "left")
            self.city_status.pack(after=self.city_row, anchor=self.anchor_start, pady=(z(6), 0))
        else:
            self.city_status.pack_forget()

    def open_city_picker(self):
        if self.city_picker is not None:
            try:
                if self.city_picker.top.winfo_exists():
                    self.city_picker.top.lift()
                    self.city_picker.entry.focus_set()
                    return
            except Exception:
                pass
        self.city_picker = CityPicker(self.win, self.on_city_picked, self.app.cfg.get("city_key"))

    def on_city_picked(self, key):
        i = city_index(key)
        if i is None:
            return
        self.city_msg = ""
        self.app.set_city(key, CITIES[i][4], CITIES[i][5])
        self.sync_city()

    def on_locate(self):
        if self.app.locating:
            return
        self.city_msg = ""
        self.app.start_locate()
        self.sync_city()

    def geo_done(self, result):
        if result:
            self.city_msg = T("located" if result.get("exact") else "located_rough", result["label"])
        else:
            self.city_msg = T("locate_fail")
        self.sync_city()

    def sync_all(self):
        self.sync_power()
        self.sync_city()
        self.sync_color()
        self.sync_reminders()
        self.start_field.set_enabled(self.app.cfg["schedule_on"])
        self.end_field.set_enabled(self.app.cfg["schedule_on"])
        self.sync_opacity()
        for code, b in self.lang_btns.items():
            b.set_selected(code == LANG)

    # callbacks
    def on_autostart(self, value):
        try:
            set_autostart(value)
        except Exception as e:
            log("autostart failed: %r" % (e,))
            mb.showerror(APP_NAME, T("autostart_fail"), parent=self.win)
            self.autostart_switch.set(autostart_enabled())

    def on_auto_sun(self, value):
        self.app.cfg["auto_sun"] = value
        save_config(self.app.cfg)
        self.app.mode = "auto"
        self.app.last_window_ok = self.app.window_ok()
        self.sync_all()

    def on_schedule_switch(self, value):
        self.app.cfg["schedule_on"] = value
        save_config(self.app.cfg)
        self.app.mode = "auto"
        self.app.last_window_ok = self.app.window_ok()
        self.sync_all()

    def sync_opacity(self):
        v = self.app.cfg["overlay_opacity"]
        self.opacity_slider.set(v)
        self.opacity_label.config(text="%d%%" % v)
        sp = self.app.cfg["eye_speed"]
        self.speed_slider.set(sp)
        self.speed_label.config(text="%d%%" % sp)

    def on_speed(self, v):
        self.speed_label.config(text="%d%%" % v)
        self.app.set_option("eye_speed", v)

    def on_opacity(self, v):
        self.opacity_label.config(text="%d%%" % v)
        self.app.set_option("overlay_opacity", v)

    def save_schedule(self, report=True):
        s_ = self.start_field.get24()
        e_ = self.end_field.get24()
        if not s_ or not e_:
            if report:
                mb.showerror(APP_NAME, T("bad_time"), parent=self.win)
            return
        cfg = self.app.cfg
        if (cfg["start"], cfg["end"]) == (s_, e_):
            return
        cfg["start"], cfg["end"] = s_, e_
        save_config(cfg)
        self.app.mode = "auto"
        self.app.last_window_ok = self.app.window_ok()

    def close(self):
        self.stop_update_spinner()
        try:
            if self.canvas is not None:
                self.canvas.unbind_all("<MouseWheel>")
        except Exception:
            pass
        try:
            self.win.destroy()
        finally:
            self.app.settings = None


# ───────────────────────────── eye exercise (Eyeleo style) ─────────────────────────────
EYE_W, EYE_H = 1000, 340


EYE_BLINK_START = 3.2                          # the eye moves after the first two slow blinks
EYE_FIRST_BLINKS = [(0.2, 0.5), (1.0, 0.5)]    # (start, length) in seconds: the first two blinks


def blink_closed(t, start, length):
    """How closed the eye is during one blink: 0 = open, 1 = shut."""
    if not (start <= t < start + length):
        return 0.0
    x = (t - start) / float(length)
    if x < 0.35:                                   # close, starting and ending gently
        u = x / 0.35
        return u * u * (3 - 2 * u)
    if x < 0.5:                                    # short hold
        return 1.0
    u = (x - 0.5) / 0.5                            # open, fast at first and slow at the end
    return 1.0 - (1 - (1 - u) ** 3)


def blink_schedule():
    """The first blinks, then a blink about every 1.7 seconds while the eye moves."""
    out = list(EYE_FIRST_BLINKS)
    t = EYE_BLINK_START + 0.8
    while t < EYE_SECONDS - 0.9:
        out.append((t, 0.3))
        t += 1.7
    return out


def eye_pose(t, cycle=EYE_BASE_CYCLE):
    """Eye movement at time t: left-right and up-down swings, with blinks during the movement."""
    dx = dy = 0.0
    opn = 1.0
    for start, length in blink_schedule():
        opn = min(opn, 1.0 - blink_closed(t, start, length))
    w = 2 * math.pi / cycle
    h0 = EYE_BLINK_START
    L = (EYE_SECONDS - h0) / 2.0                   # both directions end exactly at EYE_SECONDS
    v0 = h0 + L
    if h0 <= t < v0:                               # left and right
        x = (t - h0) / L
        dx = math.sin(w * (t - h0)) * math.sin(math.pi * x) * 60
    elif v0 <= t < v0 + L:                         # up and down
        x = (t - v0) / L
        dy = math.sin(w * (t - v0)) * math.sin(math.pi * x) * 28
    return dx, dy, opn


def eye_image(dx, dy=0.0, opn=1.0, stretch=1.0):
    """Draws the two eyes, anti-aliased. opn < 1 closes the eyelids a little."""
    ss = 2
    im = Image.new("RGBA", (EYE_W * ss, EYE_H * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cy = EYE_H * ss // 2
    vy = max(0.04, opn * stretch)
    for ex in (EYE_W * ss // 2 - 170 * ss, EYE_W * ss // 2 + 170 * ss):
        d.ellipse((ex - 120 * ss, cy - 70 * ss * vy, ex + 120 * ss, cy + 70 * ss * vy),
                  fill=(255, 255, 255, 255), outline=(30, 41, 59, 255), width=5 * ss)
        if opn < 0.1:
            continue                              # eyes shut: no iris
        px_, py_ = ex + dx * ss, cy + dy * ss
        d.ellipse((px_ - 42 * ss, py_ - 42 * ss * vy, px_ + 42 * ss, py_ + 42 * ss * vy), fill=hex2rgb(ACCENT) + (255,))
        d.ellipse((px_ - 20 * ss, py_ - 20 * ss * vy, px_ + 20 * ss, py_ + 20 * ss * vy), fill=(17, 24, 39, 255))
        d.ellipse((px_ + 6 * ss, py_ - 30 * ss * vy, px_ + 18 * ss, py_ - 18 * ss * vy), fill=(255, 255, 255, 255))
    return im.resize((EYE_W, EYE_H), Image.LANCZOS)


EYE_MIN_H = 60                                # the strip at the top where the eyes first appear
EYE_START_Y = 0                               # the eye centre starts on the top edge of the screen


def ease_out_back(p, c1=1.25):
    """Moves past the target a little, then settles (motion-graphics style)."""
    c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def ease_out_cubic(p):
    return 1 - (1 - p) ** 3


def reveal_pose(t, sh):
    """Entrance at time t: (eye centre y, visible height, glow amount). Everything is settled after REVEAL."""
    p = clamp(t / EyeBreak.REVEAL, 0.0, 1.0)
    eye_y = EYE_START_Y + (sh / 2.0 - EYE_START_Y) * ease_out_back(p)
    h = max(EYE_MIN_H, sh * ease_out_cubic(p))
    return eye_y, min(float(sh), h), ease_out_cubic(p)


def blend_hex(a, b, f):
    """Mix two colours; f = 0 gives a, f = 1 gives b."""
    ca, cb = hex2rgb(a), hex2rgb(b)
    return "#%02x%02x%02x" % tuple(int(round(ca[i] + (cb[i] - ca[i]) * f)) for i in range(3))


class EyeBreak:
    """Full-screen movement screen. The eyes appear at the top, then the dark background is
    pulled down over REVEAL (3) seconds while the eyes come down to the centre. Then the eyes move."""
    REVEAL = 3.0

    def __init__(self, app):
        self.app = app
        self.alive = True
        self.t0 = time.monotonic()
        win = tk.Toplevel(app.root)
        self.win = win
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        try:
            win.attributes("-alpha", app.cfg["overlay_opacity"] / 100.0)
        except tk.TclError:
            pass
        self.sw = app.root.winfo_screenwidth()
        self.sh = app.root.winfo_screenheight()
        win.geometry("%dx%d+0+0" % (self.sw, EYE_MIN_H))
        # the canvas is the full screen; the window only shows its top part until the reveal ends
        c = tk.Canvas(win, width=self.sw, height=self.sh, bg="#07080B", highlightthickness=0, bd=0)
        c.place(x=0, y=0)
        self.c = c
        cx, cy = self.sw // 2, self.sh // 2
        c.create_text(cx, cy - 250, text=T("break_title"), fill=TEXT, font=("Segoe UI", 28, "bold"))
        c.create_text(cx, cy - 200, text=T("break_text"), fill=MUTED, font=("Segoe UI", 13))
        self.timer_text = c.create_text(cx, cy + 250, text="", fill=ACCENT, font=("Segoe UI", 14, "bold"))
        self.eye_item = c.create_image(cx - EYE_W // 2, EYE_START_Y - EYE_H // 2, anchor="nw")
        self.prev = reveal_pose(0.0, self.sh)[0]
        self.history = []                      # recent eye positions, for the motion trail
        self.cur = None
        self.skip = Pill(win, T("skip"), self.close, w=110, h=34, bg="#07080B")
        self.skip.place(x=self.sw - 150, y=self.sh - 70)
        self.snooze = Pill(win, T("snooze"), self.snooze_and_close, w=150, h=34, bg="#07080B")
        self.snooze.place(x=self.sw - 290, y=self.sh - 70)
        win.bind("<Escape>", lambda e: self.close())
        win.focus_force()
        self.animate()

    def animate(self):
        if not self.alive:
            return
        t = time.monotonic() - self.t0
        if t >= EYE_SECONDS:
            self.close()
            return
        eye_y, h, glow = reveal_pose(t, self.sh)
        self.win.geometry("%dx%d+0+0" % (self.sw, int(h)))
        # squash and stretch: the eyes stretch while they move fast, and settle when they stop
        speed = abs(eye_y - reveal_pose(max(0.0, t - 0.04), self.sh)[0]) / 0.04
        stretch = 1.0 + min(0.22, speed / 1600.0)
        dx, dy, opn = eye_pose(t, self.app.eye_cycle())
        # after the entrance the eyes float very gently, so they never look frozen
        float_y = 0.0 if t < self.REVEAL else 3.0 * math.sin(2 * math.pi * (t - self.REVEAL) / 2.6)
        self.c.coords(self.eye_item, self.sw // 2 - EYE_W // 2, eye_y + float_y - EYE_H / 2.0)
        moving = abs(dx - getattr(self, "_last_dx", dx)) + abs(dy - getattr(self, "_last_dy", dy)) > 1.5
        self._last_dx, self._last_dy = dx, dy
        if opn < 0.6 or not moving:
            self.history = []                      # no motion trail while closing or when still
        else:
            self.history.append((dx, dy, opn))
            self.history = self.history[-4:]
        frame = eye_image(dx, dy, opn, stretch)
        for k, (gx, gy, go) in enumerate(reversed(self.history[:-1])):
            # ghost copies of the recent positions: they fade out, like motion blur
            ghost = eye_image(gx, gy, go, stretch)
            alpha = max(0.0, 0.26 - 0.08 * k)
            ghost.putalpha(ghost.getchannel("A").point(lambda v, a=alpha: int(v * a)))
            frame = Image.alpha_composite(ghost, frame)
        self.cur = ImageTk.PhotoImage(frame)
        self.c.itemconfigure(self.eye_item, image=self.cur)
        self.c.itemconfigure(self.timer_text, text=T("break_left", max(0, math.ceil(EYE_SECONDS - t))))
        self.win.after(40, self.animate)

    def _finish(self):
        if not self.alive:
            return
        self.alive = False
        try:
            self.win.destroy()
        finally:
            self.app.eye_break = None

    def close(self):
        self.app.last_reminder = time.monotonic()
        self._finish()

    def snooze_and_close(self):
        self.app.last_reminder = time.monotonic() - self.app.cfg["remind_every"] * 60 + 5 * 60
        self._finish()


# ───────────────────────────── main app ─────────────────────────────
class App:
    def __init__(self):
        global LANG
        self.cfg = load_config()
        LANG = self.cfg["lang"]
        save_config(self.cfg)
        self.events = queue.Queue()
        self.mode = "auto"              # auto | on | off  (changed by the tray click / ON-OFF button)
        self.applied = None
        self.shown = 6500.0                 # the colour currently on the screen
        self.hint = None                    # the bar above the tray icon
        self.color_ok = True                # False when this screen refuses the colour change
        self.fullscreen = False             # True while a movie/game is full-screen OR a paused app is active
        self._pause_sticky = None           # exe key we are currently pausing for (survives taskbar clicks)
        self.tip_cache = None
        self.icon_state = None
        self.settings = None
        self.eye_break = None
        self.locating = False               # True while the location is being found
        self.last_reminder = time.monotonic()
        self.running = True
        set_warmth(6500)                # clear any leftover tint from an earlier crash
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(APP_NAME)
        self.tray = Tray(self.events)
        self.tray.pause_apps = list(self.cfg.get("pause_apps") or DEFAULT_PAUSE_APPS)
        self.tray.start()
        self.tray.ready.wait(5)
        threading.Thread(target=self._prepare_frames, daemon=True).start()
        threading.Thread(target=pin_tray_icon, daemon=True).start()
        self.last_window_ok = self.window_ok()
        self._update_busy = False
        self.refresh(force=True)
        self.root.after(250, self.poll)
        self.root.after(20, self.pump)
        self.root.after(50, self.color_tick)
        # announce a successful update from the previous run
        self.root.after(1500, self._show_pending_update_note)
        # auto-check at most once per day
        if self.cfg.get("auto_update", True) and self._due_for_update_check():
            self.root.after(10000, lambda: self.check_update(silent=True))

    # ── colour ──
    def window_ok(self):
        if self.cfg.get("auto_sun"):
            return is_night(datetime.datetime.now(), self.cfg["lat"], self.cfg["lon"])
        if not self.cfg["schedule_on"]:
            return True
        return in_window(datetime.datetime.now(), self.cfg["start"], self.cfg["end"])

    def is_on(self):
        if self.mode == "on":
            return True
        if self.mode == "off":
            return False
        return self.window_ok()

    def toggle_power(self):
        self.mode = "off" if self.is_on() else "on"
        self.refresh(force=True)
        self.tray.play(self.is_on())

    def _prepare_frames(self):
        try:
            out = os.path.join(os.environ.get("TEMP") or CONFIG_DIR, "EyeGuard_frames")
            os.makedirs(out, exist_ok=True)
            to_on = build_transition(False, True, out, "to_on")
            to_off = build_transition(True, False, out, "to_off")
            self.tray.frames = {True: to_on, False: to_off}
        except Exception:
            log("frames failed:\n%s" % traceback.format_exc())

    def target_kelvin(self):
        if self.fullscreen or not self.is_on():
            return 6500
        return self.cfg["kelvin"]

    def color_step(self):
        """Moves the screen colour smoothly towards its target. A full change takes about COLOR_FADE_MS;
        small changes (from the mouse wheel) are followed gently, so the bulbs blend smoothly."""
        target = self.target_kelvin()
        diff = target - self.shown
        if abs(diff) < 0.5:
            if self.shown != target:
                self.shown = float(target)
                self.color_ok = set_warmth(self.shown)
            return
        cap = (6500 - KMIN) * COLOR_TICK_MS / float(COLOR_FADE_MS)
        move = min(abs(diff), clamp(abs(diff) * 0.49, 28.0, cap))     # fast at first, slower near the end (40% faster)
        self.shown += move if diff > 0 else -move
        self.color_ok = set_warmth(self.shown)

    def color_tick(self):
        if not self.running:
            return
        try:
            self.color_step()
        except Exception:
            log("colour error:\n%s" % traceback.format_exc())
        self.root.after(50, self.color_tick)

    def refresh(self, force=False):
        # Pause colour filter when: full-screen movie/game, or a selected app is active.
        # Taskbar / desktop / Start are ignored so clicking them does not resume the filter.
        app_pause = False
        try:
            app_pause, self._pause_sticky = evaluate_app_pause(
                self.cfg.get("pause_apps") or [], self._pause_sticky)
        except Exception:
            log("app pause check failed:\n%s" % traceback.format_exc())
            app_pause = False
        fs = bool(self.cfg.get("pause_fullscreen")) and foreground_fullscreen()
        self.fullscreen = self.eye_break is None and (fs or app_pause)
        # Keep tray submenu in sync
        self.tray.pause_apps = list(self.cfg.get("pause_apps") or [])
        ok = self.window_ok()
        if ok != self.last_window_ok:           # the schedule window opened or closed
            self.last_window_ok = ok
            self.mode = "auto"
        on = self.is_on()
        if on:
            tip = T("tip_on", self.cfg["kelvin"], preset_name(self.cfg["kelvin"]))
        elif self.mode == "off":
            tip = T("tip_paused")
        else:
            tip = T("tip_sched")
        if force or tip != self.tip_cache or on != self.icon_state:
            self.tip_cache = tip
            self.icon_state = on
            self.tray.set_tip(APP_NAME + ": " + tip, T("pause") if on else T("resume"), on)
        if self.settings:
            self.settings.sync_power()
        self.check_reminder()

    # ── reminders ──
    def check_reminder(self):
        if not self.cfg["remind_on"] or self.eye_break is not None or self.settings is not None:
            return
        if self.fullscreen:
            return
        if time.monotonic() - self.last_reminder < self.cfg["remind_every"] * 60:
            return
        if self.cfg["remind_skip_idle"] and idle_seconds() >= IDLE_LIMIT:
            return                              # user is away: show it when they come back
        self.show_break()

    def eye_cycle(self):
        return EYE_BASE_CYCLE * 100.0 / self.cfg["eye_speed"]

    def show_break(self):
        if self.eye_break is None:
            self.eye_break = EyeBreak(self)

    def step_minutes(self, delta):
        self.set_option("remind_every", int(clamp(self.cfg["remind_every"] + delta, REMIND_MIN, REMIND_MAX)))
        if self.settings:
            self.settings.sync_reminders()

    # ── settings changes ──
    def set_option(self, key, value):
        self.cfg[key] = value
        save_config(self.cfg)
        if key == "remind_on" and value:
            self.last_reminder = time.monotonic()
        self.refresh()

    def set_kelvin(self, k):
        self.cfg["kelvin"] = int(clamp(k, KMIN, KMAX))
        save_config(self.cfg)
        self.refresh()
        if self.settings:
            self.settings.sync_color()

    def show_hint(self):
        if getattr(self, "hint", None) is None:
            try:
                self.hint = TrayHint(self)
            except Exception:
                log("tray hint failed:\n%s" % traceback.format_exc())
                self.hint = None
                return
        self.hint.touch()

    def step_kelvin(self, d):
        self.set_kelvin(self.cfg["kelvin"] + d * KWHEEL)

    def set_lang(self, code):
        global LANG
        LANG = code
        self.cfg["lang"] = code
        save_config(self.cfg)
        self.tip_cache = None
        self.refresh(force=True)
        if self.settings:
            self.settings.close()
            self.settings = SettingsWindow(self)

    # ── city and location ──
    def set_city(self, key, lat, lon, label=""):
        self.cfg["city_key"], self.cfg["city_label"] = key, label
        self.cfg["lat"], self.cfg["lon"] = float(lat), float(lon)
        save_config(self.cfg)
        self.refresh(force=True)

    def start_locate(self):
        if self.locating:
            return
        self.locating = True

        def work():
            try:
                self.events.put(("geo", detect_location()))
            except Exception:
                log("detect location failed:\n%s" % traceback.format_exc())
                self.events.put(("geo", None))

        threading.Thread(target=work, daemon=True).start()

    def geo_done(self, result):
        self.locating = False
        if result:
            self.set_city("auto", result["lat"], result["lon"], result["label"])
        if self.settings and self.settings.win.winfo_exists():
            self.settings.geo_done(result)

    # ── events from the tray / windows ──
    def handle(self, kind, value):
        if kind == "geo":
            self.geo_done(value)
        elif kind == "toggle":
            self.toggle_power()
        elif kind == "preset":
            self.step_kelvin(value)
            self.show_hint()
        elif kind == "break":
            self.show_break()
        elif kind == "settings":
            if self.settings and self.settings.win.winfo_exists():
                self.settings.win.lift()
                self.settings.win.focus_force()
            else:
                before = set(self.root.winfo_children())
                try:
                    self.settings = SettingsWindow(self)
                except Exception:
                    for w in self.root.winfo_children():
                        if w not in before and isinstance(w, tk.Toplevel):
                            w.destroy()          # remove the half-built window
                    self.settings = None
                    log("settings window failed:\n%s" % traceback.format_exc())
                    mb.showerror(APP_NAME, "Could not open the settings window. Send the log file to the developer.")
        elif kind == "pause_toggle":
            self.toggle_pause_app(value)
        elif kind == "pause_reset":
            self.reset_pause_apps()
        elif kind == "update_found":
            if self.settings:
                self.settings.stop_update_spinner()
            self._on_update_found(value)
        elif kind == "update_result":
            if self.settings:
                self.settings.stop_update_spinner()
            self._update_result(value)
        elif kind == "exit":
            self.quit()

    # ── auto-update (GitHub Releases, once per day, no questions) ──
    def _due_for_update_check(self):
        raw = str(self.cfg.get("last_update_check") or "").strip()
        if not raw:
            return True
        try:
            last = datetime.datetime.fromisoformat(raw)
            return (datetime.datetime.now() - last).total_seconds() >= UPDATE_CHECK_HOURS * 3600
        except Exception:
            return True

    def _mark_update_checked(self):
        self.cfg["last_update_check"] = datetime.datetime.now().isoformat(timespec="seconds")
        save_config(self.cfg)

    def _show_pending_update_note(self):
        note = str(self.cfg.get("pending_update_note") or "").strip()
        if not note:
            return
        self.cfg["pending_update_note"] = ""
        save_config(self.cfg)
        try:
            mb.showinfo(APP_NAME, T("update_done", note))
        except Exception:
            log("pending update note failed")

    def check_update_interactive(self):
        if self.settings and self.settings.win.winfo_exists():
            self.settings.start_update_spinner()
        self.check_update(silent=False)

    def check_update(self, silent=False):
        if self._update_busy:
            return
        self._update_busy = True

        def work():
            try:
                info = fetch_latest_release()
                self._mark_update_checked()
                remote = _parse_version(info["version"])
                local = _parse_version(APP_VERSION)
                if remote > local:
                    self.events.put(("update_found", {"info": info, "silent": silent}))
                else:
                    self.events.put(("update_result", {"ok": True, "latest": True, "silent": silent,
                                                       "version": info["version"]}))
            except Exception as e:
                log("update check failed: %r" % (e,))
                self.events.put(("update_result", {"ok": False, "silent": silent, "error": str(e)}))
            finally:
                self._update_busy = False

        threading.Thread(target=work, daemon=True).start()

    def _on_update_found(self, payload):
        """New version found → download and install automatically (no confirmation dialog)."""
        info = payload.get("info") or {}
        silent = bool(payload.get("silent"))
        if not is_frozen():
            # Source run cannot replace itself; only tell the user when they asked manually
            if not silent:
                mb.showinfo(APP_NAME, T("update_not_exe"))
                url = info.get("html_url") or ("https://github.com/%s/releases" % GITHUB_REPO)
                webbrowser.open(url)
            return
        if not silent:
            try:
                mb.showinfo(APP_NAME, T("update_started"))
            except Exception:
                pass
        self._download_and_apply(info, silent=silent)

    def _download_and_apply(self, info, silent=True):
        self._update_busy = True
        ver = str(info.get("version") or APP_VERSION)

        def work():
            try:
                # Remember to show "updated to X" on the next launch
                self.cfg["pending_update_note"] = ver
                save_config(self.cfg)
                dest = os.path.join(os.environ.get("TEMP") or CONFIG_DIR,
                                    "EyeGuard_%s.exe" % ver)
                download_update(info["url"], dest)
                if apply_update_and_restart(dest, ver):
                    self.events.put(("exit", None))
                else:
                    self.cfg["pending_update_note"] = ""
                    save_config(self.cfg)
                    self.events.put(("update_result", {"ok": False, "silent": silent, "error": "apply"}))
            except Exception as e:
                log("update download failed: %r" % (e,))
                self.cfg["pending_update_note"] = ""
                save_config(self.cfg)
                self.events.put(("update_result", {"ok": False, "silent": silent, "error": str(e)}))
            finally:
                self._update_busy = False

        threading.Thread(target=work, daemon=True).start()

    def _update_result(self, payload):
        if payload.get("silent"):
            return
        if payload.get("latest"):
            mb.showinfo(APP_NAME, T("update_latest", payload.get("version") or APP_VERSION))
        elif not payload.get("ok"):
            err = payload.get("error")
            if err == "apply":
                mb.showerror(APP_NAME, T("update_apply_fail"))
            else:
                mb.showerror(APP_NAME, T("update_fail"))

    def toggle_pause_app(self, exe):
        """Add or remove an exe from the pause-while-using list."""
        exe = str(exe).strip().lower()
        if not exe:
            return
        apps = list(self.cfg.get("pause_apps") or [])
        low = [a.lower() for a in apps]
        if exe in low:
            apps = [a for a in apps if a.lower() != exe]
            if self._pause_sticky == exe:
                self._pause_sticky = None
        else:
            apps.append(exe)
        self.cfg["pause_apps"] = apps
        save_config(self.cfg)
        self.tray.pause_apps = list(apps)
        self.refresh(force=True)

    def reset_pause_apps(self):
        self.cfg["pause_apps"] = list(DEFAULT_PAUSE_APPS)
        save_config(self.cfg)
        self.tray.pause_apps = list(DEFAULT_PAUSE_APPS)
        self._pause_sticky = None
        self.refresh(force=True)

    def pump(self):
        """Handles the tray and wheel events at once (every 20 ms), so the colour and the bar move smoothly."""
        try:
            while True:
                kind, value = self.events.get_nowait()
                try:
                    self.handle(kind, value)
                except Exception:
                    log("event %s failed:\n%s" % (kind, traceback.format_exc()))
        except queue.Empty:
            pass
        except Exception:
            log("event queue error:\n%s" % traceback.format_exc())
        if self.running:
            self.root.after(20, self.pump)

    def poll(self):
        try:
            if self.running:
                self.refresh()
        except Exception:
            log("refresh error:\n%s" % traceback.format_exc())
        finally:
            if self.running:
                self.root.after(250, self.poll)

    def quit(self):
        self.running = False
        set_warmth(6500)
        if self.eye_break is not None:
            self.eye_break._finish()
        self.tray.remove_icon()
        self.root.quit()


_mutex = None


def single_instance():
    global _mutex
    _mutex = _kernel32.CreateMutexW(None, 0, "EyeGuard_SingleInstance_Mutex")
    return ctypes.get_last_error() != 183       # 183 = already exists


def main():
    if not single_instance():
        return
    app = App()
    try:
        app.root.mainloop()
    finally:
        set_warmth(6500)
        app.tray.remove_icon()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("fatal: %r" % (e,))
        raise
