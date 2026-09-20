# -*- coding: utf-8 -*-
"""WOW Legends 플레이어용 런처 — 관리자용 런처(../launcher)의 디자인(테마/위젯/크롬
타이틀바)만 그대로 가져오고, 기능은 플레이어에게 필요한 것만 남겼다: 서버 상태 표시 /
클라이언트 다운로드(7-Zip SFX, 이어받기 지원) / PLAY / 설치 폴더 재지정(설정). 서버
시작·중지, GM 콘솔, 원격 SSH 관리 같은 운영자 전용 기능은 전혀 없다."""
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, font as tkfont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import admin_dialog
import config
import downloader
import protocol
import realmlist_sync
import server_status
import settings_dialog
import state
import theme
from paths import BASE_DIR
from status import RUNNING, STOPPED
from tooltip import attach_canvas_item
from widgets import GradientButton, StatusDot

APP_TITLE = "WOW Legends"

# 홈페이지에서 exe 하나만 받아서 실행해도, 그 위치(다운로드 폴더 등)에서 계속 도는
# 대신 이 고정 위치로 "설치"된 뒤 그 복사본이 다시 실행되도록 한다 — 매번 최신
# 다운로드 파일이 아니라 항상 같은 위치에 실제로 설치된 상태로 유지하기 위함.
INSTALL_DIR = r"C:\wow_launcher"
INSTALL_EXE_NAME = "WOW Legends.exe"


def ensure_installed():
    """스크립트로 실행 중이면(python app.py, 개발 중) 아무 것도 안 한다.
    exe로 빌드되어 실행 중인데 지금 실행 위치가 INSTALL_DIR가 아니면, 그 자리로
    복사(설치)하고 복사본을 다시 실행한 뒤 지금 프로세스는 종료한다. 이미
    INSTALL_DIR에서 실행 중이면(=이미 설치되어 있고 그 복사본이 실행된 경우)
    그대로 통과시킨다. 복사에 실패해도(권한 등) 지금 받은 exe로 그냥 계속
    실행되도록 조용히 넘어간다 — 설치 실패가 실행 자체를 막으면 안 되므로."""
    if not getattr(sys, "frozen", False):
        return
    current = os.path.abspath(sys.executable)
    target = os.path.join(INSTALL_DIR, INSTALL_EXE_NAME)
    if os.path.normcase(current) == os.path.normcase(os.path.abspath(target)):
        return
    try:
        os.makedirs(INSTALL_DIR, exist_ok=True)
        shutil.copy2(current, target)
    except OSError:
        return
    try:
        subprocess.Popen([target])
    except OSError:
        return
    sys.exit(0)

BORDER = 2
TITLEBAR_H = 30
CONTENT_PAD = 16
SPLASH_W = 360
COL_GAP = 16
RIGHT_W = 320
PANEL_H = 70
PLAY_W, PLAY_H = RIGHT_W, 68
PROGRESS_H = 20
RIGHT_TOTAL_H = PANEL_H + 24 + PLAY_H + 14 + PROGRESS_H
CONTENT_H = CONTENT_PAD * 2 + max(RIGHT_TOTAL_H, 360)
OUTER_W = BORDER * 2 + CONTENT_PAD * 2 + SPLASH_W + COL_GAP + RIGHT_W
OUTER_H = BORDER * 2 + TITLEBAR_H + CONTENT_H

STATUS_POLL_SECONDS = 5


def hexcolor(rgb):
    return "#%02x%02x%02x" % rgb


def center_on_screen(win, w, h):
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")


def make_draggable(item_id, canvas, win):
    state = {}

    def start(e):
        state["x"], state["y"] = e.x_root, e.y_root
        state["gx"], state["gy"] = win.winfo_x(), win.winfo_y()

    def move(e):
        dx, dy = e.x_root - state["x"], e.y_root - state["y"]
        win.geometry(f"+{state['gx'] + dx}+{state['gy'] + dy}")

    canvas.tag_bind(item_id, "<ButtonPress-1>", start)
    canvas.tag_bind(item_id, "<B1-Motion>", move)


class PlayerLauncher:
    def __init__(self):
        theme.set_app_user_model_id("WOWLegends.PlayerLauncher")
        theme.set_theme("wotlk")
        self.cfg = config.load_config()
        self.state = "checking"  # checking | download | downloading | play
        self._closing = False
        self._extract_anim_job = None
        self._extract_anim_x = 0

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(APP_TITLE)
        icon_path = os.path.join(theme.ASSETS_DIR, "icon.ico")
        if os.path.isfile(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except tk.TclError:
                pass

        theme.init_fonts(self.root)
        center_on_screen(self.root, OUTER_W, OUTER_H)
        self.root.resizable(False, False)
        self.root.configure(bg=theme.WINDOW_BG)
        self.root.overrideredirect(True)

        self.canvas = tk.Canvas(self.root, width=OUTER_W, height=OUTER_H,
                                 highlightthickness=0, bg=theme.WINDOW_BG)
        self.canvas.pack(fill="both", expand=True)

        chrome_bg = theme.gradient_photo("chrome", OUTER_W, OUTER_H,
                                          theme.CHROME_TOP, theme.CHROME_BOTTOM,
                                          radius=5, border=theme.CHROME_BORDER, border_width=1)
        self._chrome_bg = chrome_bg
        self.canvas.create_image(0, 0, image=chrome_bg, anchor="nw")

        self._build_titlebar()
        self._build_content()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        theme.force_taskbar_icon(self.root)
        self.root.deiconify()
        theme.apply_window_icon(self.root, icon_path)

        self._refresh_client_state()
        self._poll_status()

    # ==================== 타이틀바 ====================
    def _build_titlebar(self):
        c = self.canvas
        y0 = BORDER
        bar = theme.gradient_photo("titlebar", OUTER_W - BORDER * 2, TITLEBAR_H,
                                    theme.CHROME_TOP, theme.CHROME_BOTTOM)
        self._titlebar_img = bar
        bar_id = c.create_image(BORDER, y0, image=bar, anchor="nw")
        make_draggable(bar_id, c, self.root)

        badge = theme.gradient_photo("badge", 20, 20, theme.BADGE_TOP, theme.BADGE_BOTTOM,
                                      radius=4, border=theme.BADGE_BORDER)
        self._badge_img = badge
        c.create_image(BORDER + 6, y0 + 5, image=badge, anchor="nw")
        c.create_text(BORDER + 16, y0 + 15, text="W", font=theme.cinzel(13, "bold"), fill="#2b1c05")
        c.create_text(BORDER + 34, y0 + 15, text="월드 오브 워크래프트", anchor="w",
                       font=theme.korean(14, "bold"), fill="#ffffff")

        min_x = OUTER_W - BORDER - 6 - 28 - 4 - 28
        min_img = theme.gradient_photo("min-btn", 28, 22, theme.WINBTN_TOP, theme.WINBTN_BOTTOM,
                                        radius=3, border=theme.WINBTN_BORDER)
        self._min_img = min_img
        min_id = c.create_image(min_x, y0 + 4, image=min_img, anchor="nw")
        c.create_line(min_x + 9, y0 + 17, min_x + 19, y0 + 17, fill=theme.WINBTN_MARK, width=2)
        c.tag_bind(min_id, "<Button-1>", lambda e: theme.minimize_window(self.root))
        attach_canvas_item(c, min_id, "최소화")

        gear_x = min_x - 4 - 28
        gear_img = theme.gradient_photo("gear-btn", 28, 22, theme.WINBTN_TOP, theme.WINBTN_BOTTOM,
                                         radius=3, border=theme.WINBTN_BORDER)
        self._gear_img = gear_img
        gear_id = c.create_image(gear_x, y0 + 4, image=gear_img, anchor="nw")
        gear_txt_id = c.create_text(gear_x + 14, y0 + 15, text="⚙",
                                     font=("Segoe UI Symbol", 13), fill=theme.WINBTN_MARK)
        for iid in (gear_id, gear_txt_id):
            c.tag_bind(iid, "<Button-1>", self._on_gear_click)
            attach_canvas_item(c, iid, "설정")

        close_x = OUTER_W - BORDER - 6 - 28
        close_img = theme.gradient_photo("close-btn", 28, 22, theme.CLOSE_TOP, theme.CLOSE_BOTTOM,
                                          radius=3, border=theme.CLOSE_BORDER)
        self._close_img = close_img
        close_id = c.create_image(close_x, y0 + 4, image=close_img, anchor="nw")
        txt_id = c.create_text(close_x + 14, y0 + 15, text="×",
                                font=("Segoe UI", 14, "bold"), fill="#ffffff")
        for iid in (close_id, txt_id):
            c.tag_bind(iid, "<Button-1>", lambda e: self.on_close())
            attach_canvas_item(c, iid, "닫기")

    # ==================== 본문 ====================
    def _build_content(self):
        c = self.canvas
        x0 = BORDER + CONTENT_PAD
        y0 = BORDER + TITLEBAR_H + CONTENT_PAD
        # 콘텐츠 박스는 타이틀바 바로 아래부터 창 하단 테두리까지 꽉 채운다(타이틀바에
        # 딱 붙는 것처럼 하단도 딱 붙어야 함). 예전에는 CONTENT_PAD를 두 번 빼서
        # 박스가 실제보다 32px 짧게 그려졌고, 그 만큼 왼쪽 스플래시 아트와 박스
        # 배경 밑으로 빈 여백(배경색이 비치는 부분)이 남았었다.
        content_h = OUTER_H - (BORDER + TITLEBAR_H) - BORDER

        # 배경 아트 오버레이 (콘텐츠 박스와 같은 영역)
        overlay = theme.get_content_bg_overlay(OUTER_W - BORDER * 2, content_h)
        self._overlay_img = overlay
        c.create_image(BORDER, BORDER + TITLEBAR_H, image=overlay, anchor="nw")

        content_bg = theme.gradient_photo("content-bg", OUTER_W - BORDER * 2, content_h,
                                           theme.CONTENT_BG_TOP, theme.CONTENT_BG_BOTTOM,
                                           radius=4, border=theme.CONTENT_BORDER)
        self._content_bg_img = content_bg
        c.create_image(BORDER, y0 - CONTENT_PAD, image=content_bg, anchor="nw")

        # 로고
        logo_img = theme.get_logo_image(RIGHT_W, 70)
        if logo_img:
            self._logo_img = logo_img
            c.create_image(x0 + SPLASH_W + COL_GAP + RIGHT_W // 2, y0 + 35, image=logo_img)
        else:
            c.create_text(x0 + SPLASH_W + COL_GAP + RIGHT_W // 2, y0 + 20,
                           text="AZEROTHCORE", font=theme.cinzel(22, "bold"), fill=theme.HEADER_TEXT)

        # 좌측 스플래시 아트
        splash_h = content_h
        splash_img = theme.get_splash_image(SPLASH_W, splash_h)
        self._splash_img = splash_img
        c.create_image(x0, y0, image=splash_img, anchor="nw")
        c.create_rectangle(x0, y0, x0 + SPLASH_W, y0 + splash_h, outline=theme.SPLASH_BORDER, width=1)

        right_x = x0 + SPLASH_W + COL_GAP
        panel_y = y0 + 80

        # 서버 상태 패널
        panel_bg = theme.gradient_photo("status-panel", RIGHT_W, PANEL_H,
                                         theme.PANEL_BG, theme.PANEL_BG, radius=4,
                                         border=theme.PANEL_BORDER)
        self._panel_img = panel_bg
        c.create_image(right_x, panel_y, image=panel_bg, anchor="nw")

        self.status_dot = StatusDot(self.canvas, size=13, container_bg=theme.PANEL_BG,
                                     tooltip="서버 온라인 여부")
        c.create_window(right_x + 16, panel_y + PANEL_H // 2, window=self.status_dot, anchor="w")
        self.status_text_id = c.create_text(
            right_x + 40, panel_y + 18, anchor="w", text=self.cfg.get("realmlist") or "서버",
            font=theme.korean(13, "bold"), fill=theme.HEADER_TEXT,
        )
        self.status_sub_id = c.create_text(
            right_x + 40, panel_y + 40, anchor="w", text="확인 중...",
            font=theme.korean(11), fill=theme.LABEL_MUTED,
        )

        # PLAY / 다운로드 버튼 - 오른쪽 칼럼 맨 아래에 붙인다. 상태 패널 바로 밑에
        # 붙이면 왼쪽 스플래시 아트 높이(콘텐츠 전체 높이를 좌우간다)에 맞춰 버튼
        # 아래로 큰 빈 여백이 남아 어색해 보였다 - 진행률 표시줄까지 포함한 블록을
        # 콘텐츠 하단에 고정해서 그 여백을 없앤다.
        BOTTOM_MARGIN = 20
        PROGRESS_LABEL_H = 20  # 진행률 바 아래 텍스트 라벨의 대략적인 높이(줄간격 포함)
        progress_y = y0 + content_h - BOTTOM_MARGIN - PROGRESS_H - PROGRESS_LABEL_H
        play_y = progress_y - 14 - PLAY_H
        self.play_btn = GradientButton(
            self.canvas, "확인 중...", command=self._on_play_click,
            width=PLAY_W, height=PLAY_H,
            top=theme.PLAY_DOWN_TOP, bottom=theme.PLAY_DOWN_BOTTOM,
            border=theme.PLAY_DOWN_BORDER, text_color=theme.PLAY_DOWN_TEXT,
            hover_top=theme.PLAY_UP_TOP, hover_bottom=theme.PLAY_UP_BOTTOM,
            hover_border=theme.PLAY_UP_BORDER, hover_text_color=theme.PLAY_UP_TEXT,
            font=theme.cinzel(20, "bold"), radius=4, container_bg=hexcolor(theme.CONTENT_BG_BOTTOM),
        )
        c.create_window(right_x, play_y, window=self.play_btn, anchor="nw")
        self.play_btn.set_enabled(False)

        # 진행률 표시줄 (다운로드/설치 중에만 보임) - progress_y는 위에서 이미 계산됨
        content_bg_bottom = hexcolor(theme.CONTENT_BG_BOTTOM)
        self.progress_frame = tk.Frame(self.canvas, bg=content_bg_bottom)
        self.progress_bar_bg = tk.Canvas(self.progress_frame, width=RIGHT_W, height=PROGRESS_H,
                                          highlightthickness=0, bg=theme.INPUT_BG)
        self.progress_bar_bg.pack()
        self.progress_bar_fill = self.progress_bar_bg.create_rectangle(
            0, 0, 0, PROGRESS_H, fill=theme.DOT_UP, outline="")
        self.progress_label = tk.Label(self.progress_frame, text="", bg=content_bg_bottom,
                                        fg=theme.LABEL_MUTED, font=theme.korean(10))
        self.progress_label.pack(pady=(4, 0))
        self.progress_window_id = c.create_window(right_x, progress_y, window=self.progress_frame,
                                                    anchor="nw", state="hidden")

    # ==================== ⚙ 클릭 (일반: 설정 / Ctrl+Shift: 숨겨진 관리자 모드) =====
    def _on_gear_click(self, event):
        # Tk 모디파이어 비트마스크: Shift=0x0001, Control=0x0004 — 둘 다 눌려 있을
        # 때만 관리자 모드로 보낸다. 일반 플레이어는 그냥 ⚙를 눌러서 오는 거라
        # 이 조합을 우연히 만들 일이 없다.
        if (event.state & 0x0001) and (event.state & 0x0004):
            self._open_admin()
        else:
            self._open_settings()

    def _open_admin(self):
        if self.state == "downloading":
            return
        icon_path = os.path.join(theme.ASSETS_DIR, "icon.ico")
        admin_dialog.AdminDialog(self.root, icon_path=icon_path)

    # ==================== 설정(클라이언트 폴더 재지정) ====================
    def _open_settings(self):
        """게임 폴더를 나중에 다른 위치로 옮긴 경우를 대비해, 런처가 추적하는 설치
        위치를 사용자가 직접 다시 지정할 수 있게 한다. 다운로드 중에는 열지 않는다."""
        if self.state == "downloading":
            return
        current = self.install_dir or state.get_install_dir(self.cfg)
        icon_path = os.path.join(theme.ASSETS_DIR, "icon.ico")
        dlg = settings_dialog.SettingsDialog(self.root, current, icon_path=icon_path)
        self.root.wait_window(dlg)
        if dlg.result and os.path.normcase(os.path.abspath(dlg.result)) != os.path.normcase(os.path.abspath(current)):
            state.set_install_dir(dlg.result)
            self._refresh_client_state()
            if self.state != "downloading":
                self._show_progress_text(f"설치 폴더가 변경되었습니다: {dlg.result}")
                self.root.after(3500, self._hide_progress_if_idle)

    def _hide_progress_if_idle(self):
        if self.state not in ("downloading",):
            self._show_progress(False)

    # ==================== 클라이언트 상태 (다운로드 필요 / 실행 가능) ====================
    def _refresh_client_state(self):
        """설치 여부 확인: 마지막으로 사용자가 고른(또는 기본) 설치 폴더에 실행파일이
        실제로 있는지 본다(config.json에 지정된 이름뿐 아니라 Wow_hd.exe 같은 흔한
        대체 이름도 확인 - config.find_client_exe 참고). 있으면 PLAY, 없으면 다운로드
        버튼을 보여준다."""
        install_dir = state.get_install_dir(self.cfg)
        exe_path = config.find_client_exe(install_dir, self.cfg)
        if exe_path:
            self.install_dir = install_dir
            self.client_exe_path = exe_path
            self._set_state("play")
            threading.Thread(target=self._sync_realmlist, args=(install_dir,), daemon=True).start()
        else:
            self.install_dir = None
            self.client_exe_path = None
            self._set_state("download")

    def _set_state(self, new_state):
        self.state = new_state
        if new_state == "play":
            self.play_btn.set_text("PLAY")
            self.play_btn.set_enabled(True)
        elif new_state == "download":
            self.play_btn.set_text("다운로드")
            self.play_btn.set_enabled(bool(self.cfg.get("download_url")))
        elif new_state == "downloading":
            self.play_btn.set_text("설치 중...")
            self.play_btn.set_enabled(False)

    def _on_play_click(self):
        if self.state == "play":
            self._launch_client()
        elif self.state == "download":
            self._choose_folder_and_download()

    def _launch_client(self):
        exe_path = self.client_exe_path or config.find_client_exe(self.install_dir, self.cfg)
        if not exe_path:
            self._show_progress_text("클라이언트 실행 파일을 찾을 수 없습니다.", error=True)
            return
        try:
            subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path))
        except OSError as e:
            self._show_progress_text(f"클라이언트를 실행할 수 없습니다: {e}", error=True)

    # ==================== 다운로드 + 7z SFX 설치 ====================
    def _choose_folder_and_download(self):
        url = self.cfg.get("download_url")
        if not url:
            self._show_progress_text("다운로드 주소가 설정되어 있지 않습니다.", error=True)
            return

        initial_dir = state.get_install_dir(self.cfg)
        os.makedirs(initial_dir, exist_ok=True)
        chosen = filedialog.askdirectory(
            parent=self.root,
            title="클라이언트를 설치할 폴더를 선택하세요",
            initialdir=initial_dir,
            mustexist=False,
        )
        if not chosen:
            return  # 사용자가 취소함

        self._set_state("downloading")
        self._show_progress(True)
        threading.Thread(target=self._download_worker, args=(url, chosen), daemon=True).start()

    def _download_worker(self, url, install_dir):
        sfx_path = os.path.join(BASE_DIR, "_client_download.exe")

        def on_progress(downloaded, total):
            self.root.after(0, lambda: self._update_progress(downloaded, total, phase="download"))

        try:
            downloader.download_file(url, sfx_path, progress_cb=on_progress)
        except downloader.DownloadError as e:
            self.root.after(0, lambda: self._download_failed(str(e)))
            return

        self.root.after(0, lambda: self._update_progress(1, 1, phase="extract"))
        ok, err = downloader.extract_7z_sfx(sfx_path, install_dir)
        try:
            os.remove(sfx_path)
        except OSError:
            pass

        if not ok:
            self.root.after(0, lambda: self._download_failed(f"압축 풀기 실패: {err}"))
            return

        if not config.find_client_exe(install_dir, self.cfg):
            names = ", ".join(dict.fromkeys([self.cfg["client_exe"], *config.CLIENT_EXE_CANDIDATES]))
            self.root.after(0, lambda: self._download_failed(
                f"설치는 끝났지만 실행 파일({names})을 찾을 수 없습니다. "
                "압축 파일 구성을 확인해주세요."
            ))
            return

        self._write_realmlist(install_dir)
        state.set_install_dir(install_dir)
        self.root.after(0, lambda: self._download_complete(install_dir))

    def _resolve_realmlist_value(self):
        """realmlist_api_url이 설정돼 있으면 웹사이트의 공개 API에서 최신 접속 주소를
        가져와 우선 사용하고, 실패하거나 설정 안 돼 있으면 config.json의 고정값으로
        대체한다 (네트워크 호출이라 호출하는 쪽에서 백그라운드 스레드에서 불러야 함)."""
        synced = realmlist_sync.fetch_realmlist(self.cfg.get("realmlist_api_url"))
        return synced or config.realmlist_value(self.cfg)

    def _write_realmlist(self, client_dir):
        """클라이언트 폴더에 realmlist.wtf를 쓴다 — 이미 같은 내용이면 건드리지
        않는다(불필요한 디스크 쓰기 방지)."""
        value = self._resolve_realmlist_value()
        content = f"set realmlist {value}\n"
        path = os.path.join(client_dir, "realmlist.wtf")
        try:
            with open(path, "r", encoding="utf-8") as f:
                if f.read() == content:
                    return
        except OSError:
            pass
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError:
            pass

    def _sync_realmlist(self, install_dir):
        """런처 시작 시(클라이언트가 이미 설치되어 있을 때) 백그라운드에서 한 번 호출되어,
        운영자가 웹사이트에서 렐름 주소를 바꿨으면 클라이언트도 자동으로 맞춰준다."""
        self._write_realmlist(install_dir)

    def _download_failed(self, message):
        self._stop_extract_animation()
        self._show_progress_text(message, error=True)
        self._set_state("download")

    def _download_complete(self, install_dir):
        self._stop_extract_animation()
        self._show_progress(False)
        self.install_dir = install_dir
        self._refresh_client_state()

    def _update_progress(self, downloaded, total, phase):
        if phase == "extract":
            # 7-Zip SFX 모듈은 압축 해제 중 진행률을 알려주지 않으므로(콘솔 붙임 여부와
            # 무관하게 진행률 스위치를 무시함, 직접 확인함), 실제 %를 보여주는 대신
            # "설치하는 중..."이라는 문구와 함께 애니메이션으로 멈추지 않았음을 알린다.
            self._start_extract_animation()
            return
        self._stop_extract_animation()
        if total > 0:
            ratio = min(1.0, downloaded / total)
            mb_done = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            self._show_progress_text(f"다운로드 중... {mb_done:.0f} / {mb_total:.0f} MB")
        else:
            ratio = 0
            mb_done = downloaded / (1024 * 1024)
            self._show_progress_text(f"다운로드 중... {mb_done:.0f} MB")
        self.progress_bar_bg.coords(self.progress_bar_fill, 0, 0, int(RIGHT_W * ratio), PROGRESS_H)

    def _start_extract_animation(self):
        self._show_progress_text("설치하는 중...")
        if self._extract_anim_job is not None:
            return
        self._extract_anim_x = 0
        self._animate_extract()

    def _animate_extract(self):
        if self._closing:
            return
        seg_w = max(24, RIGHT_W // 6)
        x = self._extract_anim_x
        self.progress_bar_bg.coords(self.progress_bar_fill, x, 0, min(x + seg_w, RIGHT_W), PROGRESS_H)
        self._extract_anim_x = 0 if x + 6 > RIGHT_W else x + 6
        self._extract_anim_job = self.root.after(40, self._animate_extract)

    def _stop_extract_animation(self):
        if self._extract_anim_job is not None:
            self.root.after_cancel(self._extract_anim_job)
            self._extract_anim_job = None

    def _show_progress(self, visible):
        if not visible:
            self._stop_extract_animation()
        self.canvas.itemconfig(self.progress_window_id, state="normal" if visible else "hidden")
        if not visible:
            self.progress_bar_bg.coords(self.progress_bar_fill, 0, 0, 0, PROGRESS_H)

    def _show_progress_text(self, text, error=False):
        self._show_progress(True)
        self.progress_label.config(text=text, fg="#e6b9a4" if error else theme.LABEL_MUTED)

    # ==================== 서버 상태 폴링 ====================
    def _poll_status(self):
        if self._closing:
            return
        threading.Thread(target=self._status_worker, daemon=True).start()
        self.root.after(STATUS_POLL_SECONDS * 1000, self._poll_status)

    def _status_worker(self):
        online = server_status.check_server(
            self.cfg["auth_host"], self.cfg["auth_port"],
            self.cfg["world_host"], self.cfg["world_port"],
        )
        if not self._closing:
            self.root.after(0, lambda: self._apply_status(online))

    def _apply_status(self, online):
        self.status_dot.set_status(RUNNING if online else STOPPED)
        self.canvas.itemconfig(self.status_sub_id, text="온라인" if online else "오프라인",
                                fill=theme.DOT_UP if online else "#c98b7a")

    # ==================== 종료 ====================
    def on_close(self):
        self._closing = True
        self._stop_extract_animation()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    ensure_installed()
    if getattr(sys, "frozen", False):
        # 이미 떠 있는 인스턴스가 있으면(웹사이트 "지금 플레이하기"를 두 번
        # 눌렀을 때 등) 새 창을 또 띄우지 않고 기존 창만 앞으로 가져온다.
        _instance_lock = protocol.acquire_single_instance_lock(APP_TITLE)
        if _instance_lock is None:
            sys.exit(0)
        # wowlegends:// 프로토콜을 등록해서, 웹사이트가 이 프로토콜로 링크를
        # 열면 브라우저가 exe를 다시 받는 대신 OS가 이 설치본을 직접 실행한다.
        protocol.ensure_protocol_registered(os.path.join(INSTALL_DIR, INSTALL_EXE_NAME))
    PlayerLauncher().run()
