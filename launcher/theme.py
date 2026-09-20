# -*- coding: utf-8 -*-
"""claude.ai/design 의 'WoW Launcher' 목업을 기준으로 한 팔레트/폰트/이미지 유틸.
색상 값은 목업의 CSS 값을 그대로 옮겼다."""
import ctypes
import os
import struct
import tkinter.font as tkfont
from ctypes import wintypes

from PIL import Image, ImageDraw, ImageTk, ImageFilter

from paths import BASE_DIR

ASSETS_DIR = os.path.join(BASE_DIR, "assets")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")

# ---------------- 색상 팔레트 (목업 CSS 값 그대로) ----------------
# claude.ai/design 의 목업이 WotLK/Classic 두 테마로 전환되는 기능이 생겨서, 여기서도
# 색상 상수들을 THEMES 딕셔너리 두 벌(테마별)로 나누고 set_theme() 으로 전환한다.
# 상태 점(DOT_UP/DOT_DOWN 등)과 "콘솔 열림" 표시(CONSOLE_ACTIVE_*)는 목업에서도
# 테마와 무관하게 고정값이라(실행중=초록, 정지=빨강은 테마를 바꿔도 그대로여야 바로
# 알아볼 수 있음) THEMES 밖에 그대로 둔다. WINDOW_BG(창 바깥 여백)도 목업 <style>의
# body 배경이라 테마 불문 고정.
DOT_UP, DOT_UP_GLOW, DOT_DOWN = "#5fe08a", "#35c26a", "#7e2a2a"
CONSOLE_ACTIVE_BORDER, CONSOLE_ACTIVE_HOVER_BORDER = "#3fae6e", "#5fe08a"
CONSOLE_ACTIVE_TOP, CONSOLE_ACTIVE_BOTTOM = (32, 84, 55), (13, 38, 25)
CONSOLE_ACTIVE_TEXT = "#baf6cf"
WINDOW_BG = "#1b1b1b"  # 목업 body 배경(창 바깥 영역)

THEMES = {
    "wotlk": {
        "CHROME_TOP": "#4a80c8", "CHROME_BOTTOM": "#2f5da3", "CHROME_BORDER": "#0e2545",
        "BADGE_TOP": (246, 214, 138), "BADGE_BOTTOM": (138, 90, 21), "BADGE_BORDER": "#2b1c05",

        "CONTENT_BORDER": "#0a1626",
        "CONTENT_BG_TOP": (13, 26, 38), "CONTENT_BG_BOTTOM": (6, 10, 16),

        "SPLASH_BORDER": "#1d2c3d", "SPLASH_BG": "#05080d",

        "PANEL_BORDER": "#3b4c60", "PANEL_BG": "#071019",

        "ROW_BORDER": "#22364a",
        "ROW_BG_TOP": (14, 28, 40), "ROW_BG_BOTTOM": (9, 19, 32),

        "START_BORDER": "#7d6733", "START_HOVER_BORDER": "#c8ab5e",
        "START_TOP": (43, 63, 85), "START_BOTTOM": (16, 29, 42),
        "START_TEXT": "#e2d3a4", "START_HOVER_TEXT": "#fff3cf",

        "STOP_BORDER": "#6b4630", "STOP_HOVER_BORDER": "#b3735a",
        "STOP_TOP": (58, 42, 40), "STOP_BOTTOM": (26, 17, 19),
        "STOP_TEXT": "#e6b9a4", "STOP_HOVER_TEXT": "#ffd9c8",

        "BROWSE_BORDER": "#4d5a68", "BROWSE_HOVER_BORDER": "#7c8b99",
        "BROWSE_TOP": (34, 48, 61), "BROWSE_BOTTOM": (13, 22, 32),
        "BROWSE_TEXT": "#b9c6d3", "BROWSE_HOVER_TEXT": "#e6eef6",

        "CLOSE_BORDER": "#6b1414",
        "CLOSE_TOP": (229, 123, 106), "CLOSE_BOTTOM": (195, 58, 38),

        "ICON_BORDER": "#6d5a2c", "ICON_HOVER_BORDER": "#c8ab5e",
        "ICON_TOP": (34, 53, 74), "ICON_BOTTOM": (15, 27, 40),
        "ICON_TEXT": "#e2d3a4",

        "PLAY_UP_BORDER": "#e0c274",
        "PLAY_UP_TOP": (74, 125, 85), "PLAY_UP_BOTTOM": (18, 52, 31),
        "PLAY_UP_TEXT": "#fff3c9",
        "PLAY_DOWN_BORDER": "#4d5a68",
        "PLAY_DOWN_TOP": (30, 42, 54), "PLAY_DOWN_BOTTOM": (11, 18, 25),
        "PLAY_DOWN_TEXT": "#77848f",

        "INPUT_BORDER": "#2c3f54", "INPUT_BG": "#060d15", "INPUT_TEXT": "#dbe6f3",

        "LABEL_MUTED": "#a9bccf", "TEXT_MUTED2": "#8fa4bb", "TEXT_MUTED3": "#93a7bb",
        "HEADER_TEXT": "#e8dfc8", "HEADER_BORDER": "#2a3d52",
        "BODY_TEXT": "#dbe6f3",

        "TOGGLE_ON_BORDER": "#6d5a2c",
        "TOGGLE_ON_TOP": (61, 107, 77), "TOGGLE_ON_BOTTOM": (22, 48, 31),
        "TOGGLE_KNOB_ON": "#f0dfae",
        "TOGGLE_OFF_BORDER": "#33414f", "TOGGLE_OFF_BG": "#0d1620", "TOGGLE_KNOB_OFF": "#4d5a68",

        "WINBTN_TOP": (143, 182, 228), "WINBTN_BOTTOM": (93, 140, 196),
        "WINBTN_BORDER": "#12365f", "WINBTN_MARK": "#0d2a4b",
    },
    "classic": {
        "CHROME_TOP": "#3d3733", "CHROME_BOTTOM": "#221c19", "CHROME_BORDER": "#0b0807",
        "BADGE_TOP": (242, 199, 119), "BADGE_BOTTOM": (122, 61, 16), "BADGE_BORDER": "#2a1706",

        "CONTENT_BORDER": "#150c08",
        "CONTENT_BG_TOP": (28, 16, 10), "CONTENT_BG_BOTTOM": (10, 5, 4),

        "SPLASH_BORDER": "#341d14", "SPLASH_BG": "#0a0503",

        "PANEL_BORDER": "#603724", "PANEL_BG": "#0c0707",

        "ROW_BORDER": "#3f2418",
        "ROW_BG_TOP": (37, 19, 12), "ROW_BG_BOTTOM": (21, 10, 6),

        "START_BORDER": "#8a5f2c", "START_HOVER_BORDER": "#e0a458",
        "START_TOP": (74, 42, 26), "START_BOTTOM": (29, 14, 8),
        "START_TEXT": "#efc98d", "START_HOVER_TEXT": "#fff0cc",

        "STOP_BORDER": "#7a3520", "STOP_HOVER_BORDER": "#c96a44",
        "STOP_TOP": (74, 26, 20), "STOP_BOTTOM": (29, 8, 6),
        "STOP_TEXT": "#f0b294", "STOP_HOVER_TEXT": "#ffdcc6",

        "BROWSE_BORDER": "#5c463a", "BROWSE_HOVER_BORDER": "#9a7c66",
        "BROWSE_TOP": (51, 39, 35), "BROWSE_BOTTOM": (21, 14, 11),
        "BROWSE_TEXT": "#cbb6a4", "BROWSE_HOVER_TEXT": "#f6e9dc",

        "CLOSE_BORDER": "#5c1a0d",
        "CLOSE_TOP": (212, 96, 60), "CLOSE_BOTTOM": (143, 36, 17),

        "ICON_BORDER": "#755126", "ICON_HOVER_BORDER": "#e0a458",
        "ICON_TOP": (65, 32, 15), "ICON_BOTTOM": (28, 12, 6),
        "ICON_TEXT": "#efc98d",

        "PLAY_UP_BORDER": "#f0b56a",
        "PLAY_UP_TOP": (207, 79, 28), "PLAY_UP_BOTTOM": (107, 23, 7),
        "PLAY_UP_TEXT": "#fff1d6",
        "PLAY_DOWN_BORDER": "#5c463a",
        "PLAY_DOWN_TOP": (42, 35, 32), "PLAY_DOWN_BOTTOM": (16, 11, 9),
        "PLAY_DOWN_TEXT": "#8c7a6e",

        "INPUT_BORDER": "#4c2c1e", "INPUT_BG": "#0d0604", "INPUT_TEXT": "#ecdcc8",

        "LABEL_MUTED": "#caac94", "TEXT_MUTED2": "#b09480", "TEXT_MUTED3": "#b49780",
        "HEADER_TEXT": "#f2d9a8", "HEADER_BORDER": "#4a2a1c",
        "BODY_TEXT": "#ecdcc8",

        "TOGGLE_ON_BORDER": "#6d5226",
        "TOGGLE_ON_TOP": (168, 84, 36), "TOGGLE_ON_BOTTOM": (74, 28, 12),
        "TOGGLE_KNOB_ON": "#f6d59c",
        "TOGGLE_OFF_BORDER": "#3a2418", "TOGGLE_OFF_BG": "#150e0b", "TOGGLE_KNOB_OFF": "#5c463a",

        "WINBTN_TOP": (138, 124, 114), "WINBTN_BOTTOM": (88, 77, 70),
        "WINBTN_BORDER": "#3a2f28", "WINBTN_MARK": "#1a1310",
    },
}

CURRENT_THEME = "wotlk"


def set_theme(name):
    """THEMES[name] 의 색상들을 지금과 같은 모듈 전역 이름으로 다시 대입하고,
    색상별로 캐싱된 그라디언트 이미지들을 비운다(안 비우면 테마를 바꿔도 예전 색이
    그대로 나옴). exe 아이콘 캐시도 같이 비워지지만 테마와 무관한 데이터라 다시
    추출하는 정도의 비용만 든다."""
    global CURRENT_THEME
    if name not in THEMES:
        return
    CURRENT_THEME = name
    globals().update(THEMES[name])
    _image_cache.clear()


# 모듈을 처음 불러올 때 wotlk 기본값을 바로 채워둔다(set_theme() 을 안 불러도 지금까지
# 처럼 동작).
globals().update(THEMES[CURRENT_THEME])

# ---------------- 폰트 ----------------
CINZEL_FAMILY = "Cinzel"
DEFAULT_KOREAN_FAMILY = "맑은 고딕"
KOREAN_FAMILY = DEFAULT_KOREAN_FAMILY
MONO_FAMILY = "Consolas"

# assets/fonts/ 에서 찾은 폰트 파일들 - {실제 패밀리명: 파일 경로}. init_fonts() 가
# 채운다. list_local_fonts() 가 이 목록을 그대로 "폰트" 드롭다운에 보여준다 -
# 폴더에 있는 폰트는 (한글 지원 여부와 무관하게) 전부 선택할 수 있어야 한다.
LOCAL_FONTS = {}

_FR_PRIVATE = 0x10
_FONT_EXTS = (".ttf", ".otf", ".ttc")
_fonts_ready = False


def _read_font_family_name(path):
    """폰트 파일(.ttf/.otf/.ttc)의 name 테이블에서 실제 패밀리 이름(name id 1)을
    직접 읽는다. AddFontResourceExW 로 전/후 tkfont.families() 를 비교하는 방법도
    가능하지만, 그 폰트가 이미 시스템에 설치돼 있는 경우(예: 사용자가 이미 설치된
    폰트를 그대로 assets/fonts 에 복사해 넣은 경우) '새로 생긴 이름이 없다'고
    오판해서 목록에서 통째로 빠지는 문제가 있어 — 등록 성패/설치 여부와 무관하게
    항상 정확한 이름을 얻도록 파일을 직접 파싱한다."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    try:
        offset = struct.unpack(">I", data[12:16])[0] if data[:4] == b"ttcf" else 0
        num_tables = struct.unpack(">H", data[offset + 4:offset + 6])[0]
        name_table_offset = None
        for i in range(num_tables):
            rec = data[offset + 12 + i * 16: offset + 12 + i * 16 + 16]
            if rec[0:4] == b"name":
                name_table_offset = struct.unpack(">I", rec[8:12])[0]
                break
        if name_table_offset is None:
            return None
        count, string_offset = struct.unpack(">HH", data[name_table_offset + 2:name_table_offset + 6])
        base = name_table_offset + 6
        best = None
        for i in range(count):
            rec = data[base + i * 12: base + i * 12 + 12]
            platform_id, encoding_id, lang_id, name_id, length, rec_offset = struct.unpack(">HHHHHH", rec)
            if name_id != 1:  # Family name
                continue
            raw = data[name_table_offset + string_offset + rec_offset:
                       name_table_offset + string_offset + rec_offset + length]
            try:
                text = raw.decode("utf-16-be") if platform_id in (0, 3) else raw.decode("mac_roman")
            except (UnicodeDecodeError, LookupError):
                continue
            if platform_id == 3 and encoding_id == 1 and lang_id == 0x409:
                return text  # Windows/유니코드/영어(en-US) - 최우선
            if best is None:
                best = text
        return best
    except (struct.error, IndexError):
        return None


def init_fonts(root):
    """assets/fonts/ 안의 폰트 파일을 전부 이 프로세스 전용으로 등록하고(시스템에
    설치하지 않고, 이 런처를 실행하는 동안만 사용됨), 각 파일의 실제 패밀리 이름을
    LOCAL_FONTS 에 담아둔다."""
    global CINZEL_FAMILY, _fonts_ready
    if _fonts_ready:
        return
    if os.path.isdir(FONTS_DIR):
        for fname in sorted(os.listdir(FONTS_DIR)):
            if not fname.lower().endswith(_FONT_EXTS):
                continue
            path = os.path.join(FONTS_DIR, fname)
            try:
                ctypes.windll.gdi32.AddFontResourceExW(path, _FR_PRIVATE, 0)
            except Exception:
                pass
            family = _read_font_family_name(path)
            if family:
                LOCAL_FONTS[family] = path

    if "Cinzel" in LOCAL_FONTS:
        CINZEL_FAMILY = "Cinzel"
    else:
        candidates = [f for f in LOCAL_FONTS if "cinzel" in f.lower()]
        if not candidates:
            candidates = [f for f in tkfont.families(root) if "cinzel" in f.lower()]
        CINZEL_FAMILY = candidates[0] if candidates else "Georgia"
    _fonts_ready = True


def list_local_fonts():
    """assets/fonts/ 에서 찾은 폰트 패밀리 이름 목록(가나다/알파벳 순) - 폴더에 있는
    폰트는 전부 "폰트" 드롭다운 후보가 된다."""
    return sorted(LOCAL_FONTS.keys())


def set_ui_font(name):
    """일반 UI 글꼴(라벨/버튼 등 대부분의 한글 텍스트)을 바꾼다. name 이 비어있거나
    LOCAL_FONTS 에 없으면 기본값(맑은 고딕)으로 되돌린다. 로고/타이틀 같은 Cinzel
    브랜딩 글꼴과 입력창의 고정폭(Consolas) 글꼴은 이 설정과 무관하게 그대로 둔다.
    한글 글리프가 없는 폰트를 고르면 한글 텍스트는 시스템이 자동으로 다른 폰트로
    대체해서 보여준다(설정 화면에 안내 문구로 표시)."""
    global KOREAN_FAMILY
    KOREAN_FAMILY = name if name in LOCAL_FONTS else DEFAULT_KOREAN_FAMILY


def cinzel(px, weight="normal"):
    # 음수 크기 = px 단위 (tkinter 규칙) : CSS px 값과 그대로 맞추기 위함
    return (CINZEL_FAMILY, -abs(px), weight)


def korean(px, weight="normal"):
    return (KOREAN_FAMILY, -abs(px), weight)


def mono(px, weight="normal"):
    return (MONO_FAMILY, -abs(px), weight)


# ---------------- 작업표시줄 아이콘 관련 트릭 ----------------
def set_app_user_model_id(app_id="WOWLegends.Launcher"):
    """pythonw.exe 로 실행하면 Windows 작업표시줄이 우리 창을 'python' 으로 묶어서
    파이썬 기본 아이콘을 보여준다 (WM_SETICON 으로 아이콘을 붙여도 소용없음).
    이 프로세스만의 고유 AppUserModelID 를 지정해줘야 작업표시줄이 pythonw.exe 대신
    우리가 설정한 아이콘을 쓴다. 창을 만들기 전에, 최대한 일찍 호출해야 한다."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


def force_taskbar_icon(root):
    """overrideredirect(True) 창은 기본적으로 작업표시줄에 안 나타나므로
    WS_EX_APPWINDOW 스타일을 강제로 붙여준다."""
    try:
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        root.withdraw()
        root.after(10, root.deiconify)
    except Exception:
        pass


def minimize_window(root):
    """overrideredirect(True) 창을 작업표시줄로 최소화한다.

    Tk 의 iconify() 는 overrideredirect(False) 로 먼저 되돌린 뒤에만 동작하는데,
    이 전환 과정에서 Tk 가 내부적으로 HWND 를 다시 만드는 경우가 있어 — 그러면 우리가
    force_taskbar_icon() 으로 붙여둔 WS_EX_APPWINDOW 스타일이 새 HWND 에는 없어서
    작업표시줄에서 그냥 사라져버린다(최소화가 아니라 안 보이게 닫힌 것처럼 보임).
    그래서 Tk 상태는 건드리지 않고 Win32 ShowWindow(SW_MINIMIZE) 로 직접 최소화한다."""
    try:
        SW_MINIMIZE = 6
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        ctypes.windll.user32.ShowWindow(hwnd, SW_MINIMIZE)
    except Exception:
        root.iconify()


_icon_handles = []  # GC 방지용으로 로드한 HICON 을 계속 들고 있어야 함


def apply_window_icon(root, ico_path):
    """taskbar 강제 표시 트릭(withdraw/deiconify + 스타일 변경) 이후에 다시 호출해야
    아이콘이 실제로 붙는다 — Tk 의 iconbitmap() 만으로는 그 트릭 때문에 씻겨나감."""
    if not os.path.isfile(ico_path):
        return
    try:
        LR_LOADFROMFILE = 0x00000010
        IMAGE_ICON = 1
        WM_SETICON = 0x0080
        ICON_SMALL, ICON_BIG = 0, 1

        user32 = ctypes.windll.user32
        root.update_idletasks()
        hwnd = user32.GetParent(root.winfo_id())

        h_big = user32.LoadImageW(0, ico_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
        h_small = user32.LoadImageW(0, ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
        if h_big:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_big)
            _icon_handles.append(h_big)
        if h_small:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_small)
            _icon_handles.append(h_small)
    except Exception:
        pass


# ---------------- 이미지(그라디언트/배경) 생성 ----------------
_image_cache = {}


ASSET_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def _asset(name):
    p = os.path.join(ASSETS_DIR, name)
    return p if os.path.isfile(p) else None


def _asset_multi(basename):
    """basename.jpg / .jpeg / .png / .webp 순으로 찾아 첫 번째로 존재하는 파일을 반환."""
    for ext in ASSET_EXTS:
        p = os.path.join(ASSETS_DIR, basename + ext)
        if os.path.isfile(p):
            return p
    return None


def _load_cover(path, width, height):
    """이미지를 (width, height) 영역에 꽉 차도록 비율 유지하며 자름(CSS의 cover 방식)."""
    img = Image.open(path).convert("RGB")
    src_ratio = img.width / img.height
    dst_ratio = width / height
    if src_ratio > dst_ratio:
        new_h = height
        new_w = int(height * src_ratio)
    else:
        new_w = width
        new_h = int(width / src_ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left, top = (new_w - width) // 2, (new_h - height) // 2
    return img.crop((left, top, left + width, top + height))


def _load_cover_zoomed(path, width, height, zoom, focal_x, focal_y):
    """_load_cover() 에 확대율(zoom)과 초점 위치(focal_x/y, 0~1)를 더한 버전 —
    CSS의 background-size:NNN% / background-position:X% Y% 를 흉내낸다. classic
    테마 배경 아트가 원본 스크린샷을 크게 확대해서 특정 지점만 보여주는 식이라
    필요해졌다."""
    img = Image.open(path).convert("RGB")
    # 먼저 cover 로 (width,height) 를 꽉 채운 뒤, 그 결과를 다시 zoom 배로 확대하고
    # focal 지점이 중심에 오도록 크롭한다 - CSS 의 두 단계(cover 후 확대) 효과와 같음.
    covered = _load_cover(path, width, height)
    zw, zh = max(1, int(width * zoom)), max(1, int(height * zoom))
    covered = covered.resize((zw, zh), Image.LANCZOS)
    cx, cy = int(zw * focal_x), int(zh * focal_y)
    left = min(max(0, cx - width // 2), zw - width)
    top = min(max(0, cy - height // 2), zh - height)
    return covered.crop((left, top, left + width, top + height))


def _to_rgb(c):
    if isinstance(c, str):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return c


def gradient_image(w, h, top, bottom, radius=0, border=None, border_width=1):
    """수직 그라디언트 사각형(둥근 모서리+테두리 옵션) PIL Image 생성."""
    top, bottom = _to_rgb(top), _to_rgb(bottom)
    w, h = max(1, int(w)), max(1, int(h))
    base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    grad = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        grad.putpixel((0, y), (r, g, b))
    grad = grad.resize((w, h))

    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    if radius > 0:
        md.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    else:
        md.rectangle([0, 0, w - 1, h - 1], fill=255)
    base.paste(grad, (0, 0), mask)

    if border:
        bd = ImageDraw.Draw(base)
        if radius > 0:
            bd.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius,
                                  outline=border, width=border_width)
        else:
            bd.rectangle([0, 0, w - 1, h - 1], outline=border, width=border_width)
    return base


def gradient_photo(key, w, h, top, bottom, radius=0, border=None, border_width=1):
    cache_key = (key, w, h, top, bottom, radius, border, border_width)
    if cache_key in _image_cache:
        return _image_cache[cache_key]
    img = gradient_image(w, h, top, bottom, radius, border, border_width)
    photo = ImageTk.PhotoImage(img)
    _image_cache[cache_key] = photo
    return photo


def flat_photo(key, w, h, color, radius=0, border=None, border_width=1):
    return gradient_photo(key, w, h, color, color, radius, border, border_width)


def get_splash_image(width, height):
    """왼쪽 사이드바(리치왕 아트) 패널 이미지. assets/left_side.(jpg|png|webp) 사용, 없으면 생성."""
    key = ("splash", width, height)
    if key in _image_cache:
        return _image_cache[key]
    path = _asset_multi("left_side")
    if path:
        try:
            img = _load_cover(path, width, height)
        except Exception:
            img = _generate_splash(width, height)
    else:
        img = _generate_splash(width, height)
    img = _darken_bottom(img)
    photo = ImageTk.PhotoImage(img)
    _image_cache[key] = photo
    return photo


def _darken_bottom(img):
    """하단부에 어두운 그라디언트를 깔아 그 위의 글자가 잘 보이도록 함."""
    w, h = img.size
    band_h = int(h * 0.4)
    shade = Image.new("L", (1, band_h), 0)
    for y in range(band_h):
        t = y / max(1, band_h - 1)
        shade.putpixel((0, y), int(200 * t))
    shade = shade.resize((w, band_h))
    black = Image.new("RGB", (w, band_h), (0, 0, 0))
    region = img.crop((0, h - band_h, w, h))
    region = Image.composite(black, region, shade)
    img = img.copy()
    img.paste(region, (0, h - band_h))
    return img


def _generate_splash(w, h):
    img = Image.new("RGB", (w, h), (5, 8, 13))
    top, bottom = (26, 38, 56), (5, 8, 13)
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        ImageDraw.Draw(img).line([(0, y), (w, y)], fill=(r, g, b))
    vignette = Image.new("L", (w, h), 0)
    vd = ImageDraw.Draw(vignette)
    margin = int(min(w, h) * 0.2)
    vd.ellipse([-margin, -margin, w + margin, h + margin], fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(70))
    img = Image.composite(img, Image.new("RGB", (w, h), (0, 0, 0)), vignette)
    return img


# classic 테마의 배경 아트(assets/background_classic.webp - 클래식 런처 스크린샷)는
# 원본을 420% 확대해서 24%/62% 지점만 보여주는 클로즈업 효과로 쓴다(디자인의
# tArtSize:"420% auto"/tArtPos:"24% 62%" 를 그대로 옮김). wotlk 쪽은 지금까지처럼
# 그냥 cover.
_THEME_ART_ZOOM = {
    "classic": (0.24, 0.62, 4.2),
}


def get_content_bg_overlay(width, height, opacity=0.28):
    """콘텐츠 영역 전체에 옅게 깔리는 배경 아트. 테마별 전용 이미지
    (assets/background_<테마>.*) 가 있으면 그걸 쓰고, 없으면 공용
    assets/background.(jpg|png|webp) 로 되돌아간다(사용자가 커스텀한 이미지를 계속
    wotlk/기본으로 쓸 수 있게)."""
    key = ("overlay", CURRENT_THEME, width, height, opacity)
    if key in _image_cache:
        return _image_cache[key]
    path = _asset_multi(f"background_{CURRENT_THEME}") or _asset_multi("background")
    zoom = _THEME_ART_ZOOM.get(CURRENT_THEME)
    if path:
        try:
            if zoom:
                fx, fy, z = zoom
                img = _load_cover_zoomed(path, width, height, z, fx, fy)
            else:
                img = _load_cover(path, width, height)
        except Exception:
            img = _generate_splash(width, height)
    else:
        img = _generate_splash(width, height)
    dark = Image.new("RGB", (width, height), (5, 10, 16))
    img = Image.blend(dark, img, opacity)
    photo = ImageTk.PhotoImage(img)
    _image_cache[key] = photo
    return photo


def get_logo_image(max_width, max_height):
    path = _asset_multi("logo")
    if not path:
        return None
    key = ("logo", max_width, max_height)
    if key in _image_cache:
        return _image_cache[key]
    try:
        img = Image.open(path).convert("RGBA")
        ratio = min(max_width / img.width, max_height / img.height, 1.0)
        img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        _image_cache[key] = photo
        return photo
    except Exception:
        return None


def get_icon_image(name, max_size=20):
    path = _asset(name)
    if not path:
        return None
    key = ("icon", name, max_size)
    if key in _image_cache:
        return _image_cache[key]
    try:
        img = Image.open(path).convert("RGBA")
        ratio = min(max_size / img.width, max_size / img.height, 1.0)
        img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        _image_cache[key] = photo
        return photo
    except Exception:
        return None


def _extract_exe_icon(exe_path, size):
    """exe 파일에 박혀 있는 아이콘을 PIL Image(RGBA)로 추출한다. 실패하면 None.
    CreateDIBSection 으로 32bpp 알파 채널이 있는 메모리 비트맵을 만들고 그 위에
    DrawIconEx 로 아이콘을 직접 그려서 픽셀을 읽어온다 — 구버전(마스크 방식)/
    신버전(진짜 알파 채널) 아이콘 모두 DrawIconEx 가 알아서 합성해주므로,
    아이콘 형식을 직접 구분해서 마스크를 조합하는 것보다 간단하고 안정적이다."""
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    shell32 = ctypes.windll.shell32

    large = (wintypes.HICON * 1)()
    small = (wintypes.HICON * 1)()
    try:
        shell32.ExtractIconExW(exe_path, 0, large, small, 1)
    except Exception:
        return None
    hicon = large[0] or small[0]
    if not hicon:
        return None

    hbm = None
    mem_dc = None
    screen_dc = None
    try:
        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long),
                ("biHeight", ctypes.c_long), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD),
            ]

        class BITMAPINFO(ctypes.Structure):
            _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = size
        bmi.bmiHeader.biHeight = -size  # top-down
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0  # BI_RGB

        screen_dc = user32.GetDC(0)
        mem_dc = gdi32.CreateCompatibleDC(screen_dc)
        bits_ptr = ctypes.c_void_p()
        hbm = gdi32.CreateDIBSection(mem_dc, ctypes.byref(bmi), 0,
                                      ctypes.byref(bits_ptr), None, 0)
        if not hbm or not bits_ptr:
            return None
        old = gdi32.SelectObject(mem_dc, hbm)
        ctypes.memset(bits_ptr, 0, size * size * 4)
        DI_NORMAL = 0x0003
        user32.DrawIconEx(mem_dc, 0, 0, hicon, size, size, 0, None, DI_NORMAL)
        gdi32.SelectObject(mem_dc, old)

        buf = ctypes.string_at(bits_ptr, size * size * 4)
        img = Image.frombuffer("RGBA", (size, size), buf, "raw", "BGRA", 0, 1)
        return img.copy()
    except Exception:
        return None
    finally:
        try:
            user32.DestroyIcon(hicon)
        except Exception:
            pass
        if hbm:
            try:
                gdi32.DeleteObject(hbm)
            except Exception:
                pass
        if mem_dc:
            try:
                gdi32.DeleteDC(mem_dc)
            except Exception:
                pass
        if screen_dc:
            try:
                user32.ReleaseDC(0, screen_dc)
            except Exception:
                pass


def get_exe_icon_image(exe_path, size=40):
    """exe 아이콘을 캐싱해서 PhotoImage 로 반환. 경로가 비어있거나 파일이 없거나
    추출에 실패하면 None(호출 쪽에서 대체 표시를 하도록 둠)."""
    if not exe_path or not os.path.isfile(exe_path):
        return None
    key = ("exeicon", os.path.abspath(exe_path), size)
    if key in _image_cache:
        return _image_cache[key]
    img = _extract_exe_icon(exe_path, size)
    if img is None:
        return None
    photo = ImageTk.PhotoImage(img)
    _image_cache[key] = photo
    return photo


def status_colors(status_key):
    from process_manager import RUNNING, STARTING, STOPPING, STOPPED, ERROR
    if status_key == RUNNING:
        return DOT_UP, DOT_UP_GLOW
    if status_key in (STARTING, STOPPING):
        return "#e0b93f", "#b3902a"
    if status_key == ERROR:
        return "#c0392b", "#7e2a2a"
    return DOT_DOWN, "#4a1c1c"
