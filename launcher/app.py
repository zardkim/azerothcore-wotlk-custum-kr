# -*- coding: utf-8 -*-
"""WOW Legends Launcher
claude.ai/design 의 'WoW Launcher' 목업(블리자드 런처 스타일) 을 그대로 옮긴 버전.
mysql / authserver / worldserver 를 콘솔창 없이 실행/중지/재시작하고 상태를 보여주며,
WoW 클라이언트 실행(Play) 기능을 제공한다."""
import glob
import os
import socket
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psutil

import backup_remote
import conf_reader
import config_store
import paths
import remote_conf
import remote_process
import soap_client
import theme
from tooltip import Tooltip, attach_canvas_item
from version import __version__ as APP_VERSION
from widgets import GradientButton, StatusDot, ToggleSwitch
from process_manager import (
    ServiceProcess, MysqlProcess, launch_client,
    RUNNING, STARTING, STOPPING, STOPPED, ERROR, STATUS_LABEL,
)

# ---------------- 레이아웃 상수 (목업 CSS 값을 그대로 옮김) ----------------
BORDER = 2
TITLEBAR_H = 30
CONTENT_PAD = 12
SPLASH_W = 410
COL_GAP = 12
ICON_BTN = 36
ROW_H = 50
ROW_GAP = 9
PLAY_W, PLAY_H = 164, 86
STATUS_HEADER_H = 48
STATUS_BODY_PAD = 14

OUTER_W = 1120
RIGHT_W = OUTER_W - BORDER * 2 - CONTENT_PAD * 2 - SPLASH_W - COL_GAP
ROW1_H = 150
ROW1_GAP = 10
PLAY_GAP = 16
STATUS_PANEL_H = STATUS_HEADER_H + STATUS_BODY_PAD * 2 + ROW_H * 3 + ROW_GAP * 2
RIGHT_TOTAL_H = ROW1_H + ROW1_GAP + STATUS_PANEL_H + PLAY_GAP + PLAY_H
CONTENT_H = CONTENT_PAD * 2 + RIGHT_TOTAL_H
OUTER_H = BORDER * 2 + TITLEBAR_H + CONTENT_H


def hexcolor(rgb):
    return "#%02x%02x%02x" % rgb


def center_on_screen(win, w, h):
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    x, y = (sw - w) // 2, (sh - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")


def make_draggable(item_or_widget, canvas, win):
    state = {}

    def start(e):
        state["x"], state["y"] = e.x_root, e.y_root
        state["gx"], state["gy"] = win.winfo_x(), win.winfo_y()

    def move(e):
        dx, dy = e.x_root - state["x"], e.y_root - state["y"]
        win.geometry(f"+{state['gx'] + dx}+{state['gy'] + dy}")

    if isinstance(item_or_widget, int):
        canvas.tag_bind(item_or_widget, "<ButtonPress-1>", start)
        canvas.tag_bind(item_or_widget, "<B1-Motion>", move)
    else:
        item_or_widget.bind("<ButtonPress-1>", start)
        item_or_widget.bind("<B1-Motion>", move)


class ConfirmDialog(tk.Toplevel):
    """윈도우 기본 messagebox 대신 런처 디자인(어두운 남색 + GradientButton)에 맞춘
    예/아니오 확인창. tkinter 의 기본 messagebox 는 흰 배경/시스템 글꼴이라 이 런처의
    커스텀 크롬 디자인과 확 어긋나 보인다."""

    def __init__(self, parent, title, message, yes_text="예", no_text="아니오"):
        super().__init__(parent)
        self.result = False
        self.title(title)
        self.configure(bg="#0d1a26")
        dlg_w, dlg_h = 440, 200
        center_on_screen(self, dlg_w, dlg_h)
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._on_no)

        tk.Label(self, text=message, bg="#0d1a26", fg=theme.BODY_TEXT,
                  font=theme.korean(12), justify="left", anchor="nw",
                  wraplength=dlg_w - 40).pack(fill="both", expand=True, padx=20, pady=(20, 10))

        btn_row = tk.Frame(self, bg="#0d1a26")
        btn_row.pack(fill="x", padx=20, pady=(0, 20))
        GradientButton(
            btn_row, no_text, self._on_no, 100, 32,
            theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
            hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="confirm-no",
        ).pack(side="right")
        GradientButton(
            btn_row, yes_text, self._on_yes, 100, 32,
            theme.START_TOP, theme.START_BOTTOM, theme.START_BORDER, theme.START_TEXT,
            hover_border=theme.START_HOVER_BORDER, hover_text_color=theme.START_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="confirm-yes",
        ).pack(side="right", padx=(0, 8))

        self.grab_set()
        self.focus_set()

    def _on_yes(self):
        self.result = True
        self.destroy()

    def _on_no(self):
        self.result = False
        self.destroy()


def ask_confirm(parent, title, message, yes_text="예", no_text="아니오"):
    """ConfirmDialog 를 띄우고 닫힐 때까지 기다린 뒤 예/아니오 결과(bool)를 돌려준다."""
    try:
        parent.attributes("-topmost", True)
        parent.lift()
        parent.update()
    except Exception:
        pass
    dlg = ConfirmDialog(parent, title, message, yes_text, no_text)
    parent.wait_window(dlg)
    try:
        parent.attributes("-topmost", False)
    except Exception:
        pass
    return dlg.result


class AlertDialog(tk.Toplevel):
    """확인 버튼 하나만 있는 안내창(ConfirmDialog 의 예/아니오 중 하나만 남긴 경량
    버전). 값 검증 실패, 저장 완료 안내처럼 그냥 읽고 닫으면 되는 메시지에 쓴다."""

    def __init__(self, parent, title, message, ok_text="확인"):
        super().__init__(parent)
        self.title(title)
        self.configure(bg="#0d1a26")
        dlg_w, dlg_h = 440, 200
        center_on_screen(self, dlg_w, dlg_h)
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._on_ok)

        tk.Label(self, text=message, bg="#0d1a26", fg=theme.BODY_TEXT,
                  font=theme.korean(12), justify="left", anchor="nw",
                  wraplength=dlg_w - 40).pack(fill="both", expand=True, padx=20, pady=(20, 10))

        btn_row = tk.Frame(self, bg="#0d1a26")
        btn_row.pack(fill="x", padx=20, pady=(0, 20))
        GradientButton(
            btn_row, ok_text, self._on_ok, 100, 32,
            theme.START_TOP, theme.START_BOTTOM, theme.START_BORDER, theme.START_TEXT,
            hover_border=theme.START_HOVER_BORDER, hover_text_color=theme.START_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="alert-ok",
        ).pack(side="right")

        self.grab_set()
        self.focus_set()

    def _on_ok(self):
        self.destroy()


def alert(parent, title, message, ok_text="확인"):
    """AlertDialog 를 띄우고 닫힐 때까지 기다린다(반환값 없음)."""
    try:
        parent.attributes("-topmost", True)
        parent.lift()
        parent.update()
    except Exception:
        pass
    dlg = AlertDialog(parent, title, message, ok_text)
    parent.wait_window(dlg)
    try:
        parent.attributes("-topmost", False)
    except Exception:
        pass


class RemoteCheckResultDialog(tk.Toplevel):
    """메인 화면 "서버 체크" 아이콘 결과 - conf 파일에서 찾은 포트, 그리고 그
    포트로 실제 접속해본 결과를 여러 줄로 보여준다. AlertDialog 는 200px 고정
    높이라 이 정도 분량엔 비좁아서 따로 만든다."""

    def __init__(self, app, lines):
        super().__init__(app.root)
        self.title("원격 서버 체크 결과")
        self.configure(bg="#0d1a26")
        dlg_w, dlg_h = 500, 380
        center_on_screen(self, dlg_w, dlg_h)
        self.resizable(False, False)
        self.transient(app.root)

        body = tk.Frame(self, bg="#0d1a26")
        body.pack(fill="both", expand=True, padx=20, pady=(20, 10))
        tk.Label(body, text="\n".join(lines), bg="#0d1a26", fg=theme.BODY_TEXT,
                  font=theme.mono(11), justify="left", anchor="nw",
                  wraplength=dlg_w - 40).pack(fill="both", expand=True)

        btn_row = tk.Frame(self, bg="#0d1a26")
        btn_row.pack(fill="x", padx=20, pady=(0, 20))
        GradientButton(
            btn_row, "확인", self.destroy, 100, 32,
            theme.START_TOP, theme.START_BOTTOM, theme.START_BORDER, theme.START_TEXT,
            hover_border=theme.START_HOVER_BORDER, hover_text_color=theme.START_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="remote-check-close",
        ).pack(side="right")

        self.grab_set()
        self.focus_set()


class PromptDialog(tk.Toplevel):
    """윈도우 기본 simpledialog.askstring 대신 런처 디자인에 맞춘 한 줄 텍스트 입력창."""

    def __init__(self, parent, title, message, initial=""):
        super().__init__(parent)
        self.result = None
        self.title(title)
        self.configure(bg="#0d1a26")
        dlg_w, dlg_h = 400, 168
        center_on_screen(self, dlg_w, dlg_h)
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        tk.Label(self, text=message, bg="#0d1a26", fg=theme.BODY_TEXT,
                  font=theme.korean(12), justify="left", anchor="w",
                  wraplength=dlg_w - 40).pack(fill="x", padx=20, pady=(20, 8))

        self.var = tk.StringVar(value=initial)
        entry = tk.Entry(self, textvariable=self.var, bg=theme.INPUT_BG, fg=theme.INPUT_TEXT,
                          insertbackground=theme.INPUT_TEXT, relief="flat",
                          highlightthickness=1, highlightbackground=theme.INPUT_BORDER,
                          font=theme.mono(12))
        entry.pack(fill="x", padx=20, ipady=5)
        entry.bind("<Return>", lambda e: self._on_ok())
        entry.bind("<Escape>", lambda e: self._on_cancel())

        btn_row = tk.Frame(self, bg="#0d1a26")
        btn_row.pack(fill="x", padx=20, pady=20)
        GradientButton(
            btn_row, "취소", self._on_cancel, 90, 32,
            theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
            hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="prompt-cancel",
        ).pack(side="right")
        GradientButton(
            btn_row, "확인", self._on_ok, 90, 32,
            theme.START_TOP, theme.START_BOTTOM, theme.START_BORDER, theme.START_TEXT,
            hover_border=theme.START_HOVER_BORDER, hover_text_color=theme.START_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="prompt-ok",
        ).pack(side="right", padx=(0, 8))

        self.grab_set()
        entry.focus_set()

    def _on_ok(self):
        self.result = self.var.get()
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()


def ask_string(parent, title, message, initial=""):
    """PromptDialog 를 띄우고 닫힐 때까지 기다린 뒤 입력 문자열(취소하면 None)을 돌려준다."""
    try:
        parent.attributes("-topmost", True)
        parent.lift()
        parent.update()
    except Exception:
        pass
    dlg = PromptDialog(parent, title, message, initial)
    parent.wait_window(dlg)
    try:
        parent.attributes("-topmost", False)
    except Exception:
        pass
    return dlg.result


class LauncherApp:
    def __init__(self):
        theme.set_app_user_model_id()

        self.cfg = config_store.load_config()
        self.busy = {}
        self._client_pid = None
        self._last_status = {}
        self._intentional_stop = {}
        self._closing = False
        self._refresh_thread_started = False
        self.theme = self.cfg.get("theme", "wotlk")
        theme.set_theme(self.theme)
        self.mode = self.cfg.get("mode", "local")

        self.root = tk.Tk()
        self.root.report_callback_exception = self._log_callback_exception
        self.root.withdraw()
        self.root.title(f"WOW Legends Launcher v{APP_VERSION}")

        icon_path = os.path.join(theme.ASSETS_DIR, "icon.ico")
        if os.path.isfile(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except tk.TclError:
                pass

        theme.init_fonts(self.root)
        if self.cfg.get("ui_font"):
            theme.set_ui_font(self.cfg["ui_font"])

        center_on_screen(self.root, OUTER_W, OUTER_H)
        self.root.resizable(False, False)
        self.root.configure(bg=theme.WINDOW_BG)
        self.root.overrideredirect(True)

        self.canvas = tk.Canvas(self.root, width=OUTER_W, height=OUTER_H,
                                 highlightthickness=0, bg=theme.WINDOW_BG)
        self.canvas.pack(fill="both", expand=True)

        # 파란 크롬 테두리
        chrome_bg = theme.gradient_photo("chrome", OUTER_W, OUTER_H,
                                          theme.CHROME_TOP, theme.CHROME_BOTTOM,
                                          radius=5, border=theme.CHROME_BORDER, border_width=1)
        self.canvas.create_image(0, 0, image=chrome_bg, anchor="nw")
        self._chrome_bg = chrome_bg

        self._build_titlebar()
        self._build_content()

        self.services = self._build_services()
        for key in self.services:
            self.busy[key] = None

        self.apply_config()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        theme.force_taskbar_icon(self.root)
        self.root.deiconify()
        theme.apply_window_icon(self.root, icon_path)

        if self.cfg.get("opt_autostart") and self.mode != "remote":
            self.root.after(400, self._run_autostart)

        self.refresh()
        self._refresh_server_info()

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
        c.tag_bind(min_id, "<Button-1>", lambda e: self.on_minimize())
        attach_canvas_item(c, min_id, "최소화")

        # WotLK/Classic 테마 탭 — claude.ai/design 목업에 새로 생긴 테마 전환 UI를
        # 그대로 옮겼다. 타이틀 텍스트와 최소화 버튼 사이, 다른 창 조작 버튼들과
        # 같은 방식(캔버스에 직접 그리고 tag_bind)으로 만든다.
        tab_w, tab_h, tab_gap = 54, 20, 4
        tab_right = min_x - 10
        self._theme_tab_ids = {}
        for name, label in (("classic", "Classic"), ("wotlk", "WotLK")):
            tab_x = tab_right - tab_w
            tab_right = tab_x - tab_gap
            active = self.theme == name
            top, bottom = (theme.START_TOP, theme.START_BOTTOM) if active \
                else (theme.BROWSE_TOP, theme.BROWSE_BOTTOM)
            border = theme.START_BORDER if active else theme.BROWSE_BORDER
            text_color = theme.START_TEXT if active else theme.BROWSE_TEXT
            tab_img = theme.gradient_photo(f"theme-tab-{name}-{active}", tab_w, tab_h,
                                            top, bottom, radius=3, border=border)
            setattr(self, f"_theme_tab_img_{name}", tab_img)
            img_id = c.create_image(tab_x, y0 + 5, image=tab_img, anchor="nw")
            txt_id = c.create_text(tab_x + tab_w // 2, y0 + 5 + tab_h // 2, text=label,
                                    font=theme.korean(10, "bold"), fill=text_color)
            for iid in (img_id, txt_id):
                c.tag_bind(iid, "<Button-1>", lambda e, n=name: self._set_theme(n))
            attach_canvas_item(c, img_id, f"{label} 테마로 전환")
            attach_canvas_item(c, txt_id, f"{label} 테마로 전환")

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

    def on_minimize(self):
        theme.minimize_window(self.root)

    # ==================== 테마 전환 (WotLK / Classic) ====================
    def _set_theme(self, name):
        if name == self.theme:
            return
        self.theme = name
        self.cfg["theme"] = name
        config_store.save_config(self.cfg)
        theme.set_theme(name)
        self._rebuild_ui()

    def _rebuild_ui(self):
        """캔버스를 통째로 지우고 __init__ 과 같은 순서로 다시 그린다. Tkinter 는
        웹처럼 상태가 바뀐다고 알아서 다시 그려주지 않으니, 목업의 setState 재렌더를
        '캔버스 비우고 다시 그리기'로 대신한다. 다시 그리면 카드/버튼이 전부 새
        위젯이 되니, 지금 알고 있는 서버 상태를 그 자리에서 바로 반영해서(다음
        1.5초 새로고침을 기다리지 않고) 잠깐 "전부 정지됨"으로 보이는 깜빡임을
        없앤다."""
        self.canvas.delete("all")
        chrome_bg = theme.gradient_photo("chrome", OUTER_W, OUTER_H,
                                          theme.CHROME_TOP, theme.CHROME_BOTTOM,
                                          radius=5, border=theme.CHROME_BORDER, border_width=1)
        self.canvas.create_image(0, 0, image=chrome_bg, anchor="nw")
        self._chrome_bg = chrome_bg

        self._build_titlebar()
        self._build_content()

        results = {}
        for key, svc in self.services.items():
            pending = self.busy.get(key) or self.busy.get("all")
            status = self._last_status.get(key, STOPPED)
            console_on = svc.console_visible() if status in (RUNNING, STARTING) else False
            results[key] = {"status": status, "busy": bool(pending), "console_on": console_on}
        self._apply_refresh(results)
        self._refresh_server_info()

    # ==================== 본문 ====================
    def _build_content(self):
        c = self.canvas
        cx0, cy0 = BORDER, BORDER + TITLEBAR_H
        cw, ch = OUTER_W - BORDER * 2, CONTENT_H

        content_bg = theme.get_content_bg_overlay(cw, ch, opacity=0.25)
        self._content_bg = content_bg
        c.create_rectangle(cx0, cy0, cx0 + cw, cy0 + ch, fill=theme.CONTENT_BORDER, outline="")
        c.create_image(cx0, cy0, image=content_bg, anchor="nw")

        left = cx0 + CONTENT_PAD
        top = cy0 + CONTENT_PAD
        self._build_splash(left, top, SPLASH_W, RIGHT_TOTAL_H)

        right_x = left + SPLASH_W + COL_GAP
        self._build_logo_row(right_x, top, RIGHT_W, ROW1_H)
        self._build_status_panel(right_x, top + ROW1_H + ROW1_GAP, RIGHT_W, STATUS_PANEL_H)
        self._build_play_row(right_x, top + ROW1_H + ROW1_GAP + STATUS_PANEL_H + PLAY_GAP, RIGHT_W, PLAY_H)

    def _build_splash(self, x, y, w, h):
        c = self.canvas
        self._splash_rect = (x, y, w, h)
        img = theme.get_splash_image(w, h)
        self._splash_img = img
        rect_id = c.create_rectangle(x, y, x + w, y + h, fill=theme.SPLASH_BG, outline=theme.SPLASH_BORDER)
        img_id = c.create_image(x, y, image=img, anchor="nw")
        text1_id = c.create_text(x + 12, y + h - 34, text="BLIZZARD", anchor="sw",
                                  font=theme.cinzel(18, "bold"), fill="#e8e8e8")
        text2_id = c.create_text(x + 12, y + h - 14, text="© 2009 BLIZZARD ENTERTAINMENT, INC. ALL RIGHTS RESERVED.",
                                  anchor="sw", font=theme.korean(9), fill="#9fb0c4")
        self._splash_items = (rect_id, img_id, text1_id, text2_id)

        # 스플래시 이미지를 클릭하면 온라인 계정 목록으로, 다시 클릭하면 원래 이미지로
        # 돌아온다(온라인 목록을 항상 켜두면 새로고침 부담이 생기므로 클릭할 때만 조회).
        self._online_list_mode = False
        self._online_list_window_id = None
        self._online_list_frame = None
        self._online_list_body = None
        self._online_list_title = None
        for item_id in self._splash_items:
            c.tag_bind(item_id, "<Button-1>", self._on_splash_click)
            c.tag_bind(item_id, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
            c.tag_bind(item_id, "<Leave>", lambda e: self.canvas.config(cursor=""))
            attach_canvas_item(c, item_id, "클릭하면 지금 접속 중인 온라인 계정 목록을 볼 수 있습니다")

    # ==================== 온라인 계정 목록(스플래시 이미지 클릭 토글) ====================
    def _on_splash_click(self, event=None):
        if self._online_list_mode:
            self._show_splash_art()
        else:
            self._show_online_list()

    def _show_splash_art(self):
        self._online_list_mode = False
        if self._online_list_window_id is not None:
            self.canvas.delete(self._online_list_window_id)
            self._online_list_window_id = None
        if self._online_list_frame is not None:
            self._online_list_frame.destroy()
            self._online_list_frame = None
        self._online_list_body = None
        self._online_list_title = None
        for item_id in self._splash_items:
            self.canvas.itemconfig(item_id, state="normal")

    def _show_online_list(self):
        """스플래시 이미지 자리에 지금 접속 중인 계정을 얼라이언스/호드로 나눠서 보여준다.
        머리글(제목 + 새로고침/닫기 아이콘)은 계속 떠 있고, 그 아래 본문만 매번
        다시 그린다(로딩 중/오류/결과 상태를 바꿀 때 새로고침·닫기 버튼이 사라지지
        않도록)."""
        self._online_list_mode = True
        for item_id in self._splash_items:
            self.canvas.itemconfig(item_id, state="hidden")

        x, y, w, h = self._splash_rect
        frame = tk.Frame(self.canvas, bg="#05080d", highlightthickness=1,
                          highlightbackground=theme.SPLASH_BORDER)
        self._online_list_window_id = self.canvas.create_window(
            x, y, window=frame, anchor="nw", width=w, height=h)
        self._online_list_frame = frame

        header = tk.Frame(frame, bg="#05080d")
        header.pack(fill="x", padx=10, pady=(8, 0))
        GradientButton(
            header, "✕", self._show_splash_art, 26, 26,
            theme.ICON_TOP, theme.ICON_BOTTOM, theme.ICON_BORDER, theme.ICON_TEXT,
            hover_border=theme.ICON_HOVER_BORDER, font=("Segoe UI Symbol", 12),
            radius=4, container_bg="#05080d", key="online-close", tooltip="닫고 원래 이미지로 돌아가기",
        ).pack(side="right")
        GradientButton(
            header, "⟳", self._refresh_online_list, 26, 26,
            theme.ICON_TOP, theme.ICON_BOTTOM, theme.ICON_BORDER, theme.ICON_TEXT,
            hover_border=theme.ICON_HOVER_BORDER, font=("Segoe UI Symbol", 13, "bold"),
            radius=4, container_bg="#05080d", key="online-refresh", tooltip="목록 새로고침",
        ).pack(side="right", padx=(0, 6))
        self._online_list_title = tk.Label(header, text="온라인 계정", bg="#05080d",
                                            fg=theme.HEADER_TEXT, font=theme.korean(13, "bold"),
                                            anchor="w")
        self._online_list_title.pack(side="left", fill="x", expand=True)

        tk.Frame(frame, bg=theme.HEADER_BORDER, height=1).pack(fill="x", padx=10, pady=(8, 0))

        self._online_list_body = tk.Frame(frame, bg="#05080d")
        self._online_list_body.pack(fill="both", expand=True)

        self._refresh_online_list()

    def _refresh_online_list(self):
        """지금 상태로 다시 조회한다 — 처음 열 때도, 새로고침(⟳) 버튼을 눌렀을 때도
        이 메서드 하나로 처리한다(패널 자체는 그대로 두고 본문만 다시 그림)."""
        if not self._online_list_mode or self._online_list_body is None:
            return
        for w in self._online_list_body.winfo_children():
            w.destroy()
        self._online_list_title.config(text="온라인 계정")

        w = self._splash_rect[2]
        status_label = tk.Label(self._online_list_body, text="온라인 계정을 불러오는 중...",
                                 bg="#05080d", fg=theme.LABEL_MUTED, font=theme.korean(12),
                                 wraplength=w - 24, justify="center")
        status_label.pack(pady=(24, 0), padx=12)

        if self._last_status.get("worldserver") != RUNNING:
            status_label.config(text="월드 서버가 실행 중이 아닙니다.\n서버 구동에서 먼저 켜주세요.")
            return
        gm_account = self.cfg.get("gm_account", "")
        gm_password = self.cfg.get("gm_password", "")
        if not gm_account or not gm_password:
            status_label.config(text="설정(⚙) > GM 계정 에서 GM 계정을 먼저 지정하세요.")
            return

        def progress(done, total):
            self.root.after(0, lambda: self._update_online_list_progress(done, total))

        try:
            list_limit = max(1, int(self.cfg.get("online_list_limit", 100)))
        except (TypeError, ValueError):
            list_limit = 100

        def worker():
            ok, entries, err = soap_client.list_online_accounts(
                self.soap_host(), int(self.cfg.get("soap_port", 7878)),
                gm_account, gm_password, limit=list_limit, progress_cb=progress,
            )
            self.root.after(0, lambda: self._on_online_list_fetched(ok, entries, err))

        threading.Thread(target=worker, daemon=True).start()

    def _update_online_list_progress(self, done, total):
        if not self._online_list_mode or self._online_list_body is None:
            return
        for w in self._online_list_body.winfo_children():
            if isinstance(w, tk.Label):
                w.config(text=f"온라인 계정을 불러오는 중... ({done}/{total})")
                return

    def _on_online_list_fetched(self, ok, entries, err):
        # 조회하는 동안 사용자가 이미 닫기를 눌러서 스플래시 이미지로 돌아갔을 수 있다
        # — 그럴 땐 이미 없어진 프레임에 그리지 않고 조용히 무시한다.
        if not self._online_list_mode or self._online_list_body is None:
            return
        for w in self._online_list_body.winfo_children():
            w.destroy()
        if not ok:
            tk.Label(self._online_list_body, text=err or "목록을 불러오지 못했습니다.",
                     bg="#05080d", fg=theme.TEXT_MUTED3, font=theme.korean(11),
                     wraplength=self._splash_rect[2] - 24, justify="center").pack(pady=24, padx=12)
            return
        if not entries:
            tk.Label(self._online_list_body, text="지금 접속 중인 계정이 없습니다.",
                     bg="#05080d", fg=theme.TEXT_MUTED3, font=theme.korean(11),
                     wraplength=self._splash_rect[2] - 24, justify="center").pack(pady=24, padx=12)
            return
        self._render_online_list(entries)

    def _render_online_list(self, entries):
        body = self._online_list_body
        alliance = [e for e in entries if e.get("faction") == "alliance"]
        horde = [e for e in entries if e.get("faction") == "horde"]
        unknown_n = len(entries) - len(alliance) - len(horde)

        title_text = f"온라인 계정 — 얼라이언스 {len(alliance)} / 호드 {len(horde)}"
        if unknown_n:
            title_text += f" / 미확인 {unknown_n}"
        self._online_list_title.config(text=title_text)

        cols = tk.Frame(body, bg="#05080d")
        cols.pack(fill="both", expand=True, padx=10, pady=(6, 10))

        def build_column(label, faction_list, color, head_bg, list_bg, list_border, logo_name):
            col = tk.Frame(cols, bg="#05080d")
            col.pack(side="left", fill="both", expand=True, padx=(0, 6))
            # 얼라이언스/호드를 한눈에 구분할 수 있도록 진영별로 배경색이 다른 이름표
            # 바(head)와 목록 칸(list_bg) 둘 다 색을 다르게 준다.
            head = tk.Frame(col, bg=head_bg)
            head.pack(fill="x")
            logo = theme.get_icon_image(logo_name, max_size=26)
            if logo:
                logo_lbl = tk.Label(head, image=logo, bg=head_bg)
                logo_lbl.image = logo  # GC 방지
                logo_lbl.pack(side="left", padx=(8, 6), pady=6)
            tk.Label(head, text=f"{label} ({len(faction_list)})", bg=head_bg, fg=color,
                     font=theme.korean(13, "bold"), anchor="w").pack(side="left")
            # width=1 로 최소화 — tk.Text 기본 너비(80글자)를 그대로 두면 요청 크기가
            # 이 칸 실제 폭보다 훨씬 커져서, 첫 번째(얼라이언스) 칸이 공간을 다 차지하고
            # 두 번째(호드) 칸이 화면 밖으로 밀려나는 문제가 있었다(라이브 캡처로 확인함).
            # 실제 크기는 옆의 fill="both"/expand=True 가 알아서 나눠 채운다.
            text = tk.Text(col, bg=list_bg, fg=theme.INPUT_TEXT, relief="flat",
                            highlightthickness=1, highlightbackground=list_border,
                            font=theme.korean(12), wrap="none", cursor="arrow", width=1)
            for e in faction_list:
                text.insert("end", f"{e['character']}\n")
            text.config(state="disabled")
            text.pack(fill="both", expand=True, pady=(4, 0))

        build_column("얼라이언스", alliance, "#bcdcff", "#152944", "#0c1826", "#274866", "alliance-logo.png")
        build_column("호드", horde, "#ffcab8", "#3a1710", "#20100c", "#5c2c1f", "horde-logo.png")

    def _build_logo_row(self, x, y, w, h):
        c = self.canvas
        # 서버 목록/설정/도움말 세 아이콘을 한 줄에 나란히 두므로, 로고 폭은
        # 아이콘 3개 + 그 사이 간격 2개만큼을 빼서 계산한다.
        logo_w = w - COL_GAP - ICON_BTN * 3 - 8 * 2
        logo = theme.get_logo_image(logo_w, h)
        if logo:
            self._logo_img = logo
            c.create_image(x + logo_w // 2, y + h // 2, image=logo, anchor="center")
        else:
            c.create_text(x + logo_w // 2, y + h // 2 - 16, text="WORLD OF WARCRAFT", anchor="center",
                           font=theme.cinzel(30, "bold"), fill="#e8dfc8")
            c.create_text(x + logo_w // 2, y + h // 2 + 18, text="WRATH OF THE LICH KING", anchor="center",
                           font=theme.cinzel(14), fill="#8fa4bb")

        # 오른쪽 끝부터 도움말 · 설정 · 서버 목록 순서로 한 줄에 배치한다
        # (요청한 "서버 목록, 설정, 도움말" 순서를 왼쪽→오른쪽으로 그대로 따름).
        icon_x = x + w - ICON_BTN
        self.btn_help = GradientButton(
            self.canvas, "?", self.open_help, ICON_BTN, ICON_BTN,
            theme.ICON_TOP, theme.ICON_BOTTOM, theme.ICON_BORDER, theme.ICON_TEXT,
            hover_border=theme.ICON_HOVER_BORDER, font=theme.cinzel(15, "bold"),
            radius=6, container_bg="#0d1a26", key="help-icon", tooltip="도움말",
        )
        self.canvas.create_window(icon_x, y, window=self.btn_help, anchor="nw")

        settings_icon_x = icon_x - ICON_BTN - 8
        self.btn_settings = GradientButton(
            self.canvas, "⚙", self.open_settings, ICON_BTN, ICON_BTN,
            theme.ICON_TOP, theme.ICON_BOTTOM, theme.ICON_BORDER, theme.ICON_TEXT,
            hover_border=theme.ICON_HOVER_BORDER, font=("Segoe UI Symbol", 15),
            radius=6, container_bg="#0d1a26", key="settings-icon", tooltip="설정",
        )
        self.canvas.create_window(settings_icon_x, y, window=self.btn_settings, anchor="nw")

        # 설정 창 안에 있던 "서버 관리" 진입점을 메인 화면에서도 바로 쓸 수
        # 있도록, 설정 아이콘 왼쪽에 서버 목록 드롭다운 아이콘을 둔다. 서버
        # 관리 창을 여는 것보다 가벼운 동작(그냥 목록에서 골라 바로 전환)이라
        # 별도 아이콘으로 뺐다 - 추가/삭제처럼 목록 자체를 바꾸는 작업은 여전히
        # 드롭다운 맨 아래 "서버 관리..." 항목에서 기존 창으로 들어가서 한다.
        server_icon_x = settings_icon_x - ICON_BTN - 8
        self.btn_server_switch = GradientButton(
            self.canvas, "☰", self._open_server_switch_menu, ICON_BTN, ICON_BTN,
            theme.ICON_TOP, theme.ICON_BOTTOM, theme.ICON_BORDER, theme.ICON_TEXT,
            hover_border=theme.ICON_HOVER_BORDER, font=("Segoe UI Symbol", 15),
            radius=6, container_bg="#0d1a26", key="server-switch-icon", tooltip="서버 전환",
        )
        self.canvas.create_window(server_icon_x, y, window=self.btn_server_switch, anchor="nw")

    def _build_status_panel(self, x, y, w, h):
        c = self.canvas
        panel_bg_avg = hexcolor(((theme.CONTENT_BG_TOP[0] + theme.CONTENT_BG_BOTTOM[0]) // 2,
                                  (theme.CONTENT_BG_TOP[1] + theme.CONTENT_BG_BOTTOM[1]) // 2,
                                  (theme.CONTENT_BG_TOP[2] + theme.CONTENT_BG_BOTTOM[2]) // 2))
        panel_img = theme.get_content_bg_overlay(w, h, opacity=0.18)
        self._status_panel_img = panel_img
        c.create_rectangle(x, y, x + w, y + h, fill=theme.PANEL_BG, outline=theme.PANEL_BORDER)
        c.create_image(x, y, image=panel_img, anchor="nw")

        self._panel_title_id = c.create_text(
            x + 18, y + STATUS_HEADER_H // 2, text="서버 상태", anchor="w",
            font=theme.cinzel(19, "bold"), fill=theme.HEADER_TEXT)
        # 활성 서버 배지 - "서버 상태" 글자 폭이 자동시작 중엔 잠깐 늘어나서
        # (예: "서버 상태 — 자동시작중...") 딱 붙여두면 겹칠 수 있지만, 그 상태는
        # 몇 초짜리라 고정 위치로 충분하다. 눌러서 서버 관리 창으로 바로 갈 수 있음.
        self._mode_badge_id = c.create_text(
            x + 140, y + STATUS_HEADER_H // 2, text="", anchor="w",
            font=theme.korean(11, "bold"), fill=theme.TEXT_MUTED3)
        c.tag_bind(self._mode_badge_id, "<Button-1>",
                   lambda e: ServerManageDialog(self, on_change=self._on_server_manage_changed))
        c.tag_bind(self._mode_badge_id, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        c.tag_bind(self._mode_badge_id, "<Leave>", lambda e: self.canvas.config(cursor=""))
        self._mode_badge_x = x + 140
        self._mode_badge_tooltip = attach_canvas_item(c, self._mode_badge_id, "")
        c.create_line(x, y + STATUS_HEADER_H, x + w, y + STATUS_HEADER_H, fill=theme.HEADER_BORDER)

        btn_w, btn_h = 84, 28
        icon_w = 28
        self.btn_account = GradientButton(
            self.canvas, "계정 관리", self.open_account_manage,
            btn_w, btn_h, theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
            hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=3, container_bg=panel_bg_avg, key="account-manage",
            tooltip="계정 생성 / 비밀번호 변경 / GM 권한 설정 / 전체 저장",
        )
        self.btn_game_settings = GradientButton(
            self.canvas, "게임 설정", self.open_game_settings,
            btn_w, btn_h, theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
            hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=3, container_bg=panel_bg_avg, key="game-settings",
            tooltip="비행경로/시작 자금/경험치/드랍률/퀘스트 보상 (worldserver.conf)",
        )
        # "서버 구동" 다이얼로그를 없애고, 그 안에 있던 모두 시작/모두 중지를 아이콘
        # 버튼으로 여기(그 버튼이 있던 자리)에 바로 둔다.
        self.btn_start_all = GradientButton(
            self.canvas, "▶", lambda: self.run_action("all", "start"),
            icon_w, btn_h, theme.START_TOP, theme.START_BOTTOM, theme.START_BORDER, theme.START_TEXT,
            hover_border=theme.START_HOVER_BORDER, hover_text_color=theme.START_HOVER_TEXT,
            font=("Segoe UI Symbol", 13, "bold"), radius=3, container_bg=panel_bg_avg, key="start-all",
            tooltip="모두 시작 (MySQL → 인증 서버 → 월드 서버 순서로)",
        )
        self.btn_stop_all = GradientButton(
            self.canvas, "■", lambda: self.run_action("all", "stop"),
            icon_w, btn_h, theme.STOP_TOP, theme.STOP_BOTTOM, theme.STOP_BORDER, theme.STOP_TEXT,
            hover_border=theme.STOP_HOVER_BORDER, hover_text_color=theme.STOP_HOVER_TEXT,
            font=("Segoe UI Symbol", 11, "bold"), radius=3, container_bg=panel_bg_avg, key="stop-all",
            tooltip="모두 중지",
        )
        # 원격 서버 전용 - conf 파일에서 실제 포트를 다시 읽어와 접속을 확인한다.
        # 로컬 모드에서는 의미가 없으므로 비활성화만 해두고(_apply_refresh 에서),
        # 버튼 자체는 항상 만들어서 ▶/■ 와 같은 자리 계산 방식을 그대로 따른다.
        self.btn_remote_check = GradientButton(
            self.canvas, "⟲", self._check_remote_server,
            icon_w, btn_h, theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
            hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
            font=("Segoe UI Symbol", 15, "bold"), radius=3, container_bg=panel_bg_avg, key="remote-check",
            tooltip="원격 서버 체크 (conf 파일에서 포트를 다시 읽어 접속 확인, 원격 모드 전용)",
        )
        ip_label = tk.Label(self.canvas, text="127.0.0.1", bg=panel_bg_avg, fg=theme.TEXT_MUTED2,
                             font=theme.korean(12))
        Tooltip(ip_label, "서버 접속 IP (렐름리스트에 사용)")
        self.ip_label = ip_label
        gap = 6
        right_edge = x + w - 14
        c.create_window(right_edge, y + STATUS_HEADER_H // 2, window=ip_label, anchor="e")
        c.create_window(right_edge - 90, y + STATUS_HEADER_H // 2, window=self.btn_stop_all, anchor="e")
        c.create_window(right_edge - 90 - icon_w - gap, y + STATUS_HEADER_H // 2,
                         window=self.btn_start_all, anchor="e")
        account_right = right_edge - 90 - (icon_w + gap) * 2 - 2
        c.create_window(account_right, y + STATUS_HEADER_H // 2,
                         window=self.btn_account, anchor="e")
        game_settings_right = account_right - btn_w - gap
        c.create_window(game_settings_right, y + STATUS_HEADER_H // 2,
                         window=self.btn_game_settings, anchor="e")
        remote_check_right = game_settings_right - btn_w - icon_w - gap
        c.create_window(remote_check_right, y + STATUS_HEADER_H // 2,
                         window=self.btn_remote_check, anchor="e")

        # 배지(서버 이름)가 이 버튼들과 안 겹치도록, 배지가 쓸 수 있는 최대 폭을
        # "버튼 줄 중 제일 왼쪽(서버 체크 아이콘)의 왼쪽 끝 - 여백" 으로 잡아둔다.
        # _update_mode_badge() 는 이 값 기준으로 이름이 길면 말줄임(...)한다.
        self._badge_max_w = (remote_check_right - icon_w) - self._mode_badge_x - 10
        self._update_mode_badge()

        self.main_rows = {}
        row_bg_avg = hexcolor(((theme.ROW_BG_TOP[0] + theme.ROW_BG_BOTTOM[0]) // 2,
                               (theme.ROW_BG_TOP[1] + theme.ROW_BG_BOTTOM[1]) // 2,
                               (theme.ROW_BG_TOP[2] + theme.ROW_BG_BOTTOM[2]) // 2))
        icon_size = 40
        # mysql.webp 는 정사각형 아이콘이 아니라 가로로 긴 워드마크(512x256)라 exe
        # 아이콘과 같은 max_size 로 맞추면 세로 폭이 절반으로 줄어서 유독 작아 보인다.
        # 다른 두 아이콘과 세로 높이가 비슷해 보이도록 가로 폭 기준을 넉넉히 준다.
        # 인증서버/월드서버는 아이콘을 여기서 바로 확정하지 않고 일단 빈 채로 카드를
        # 만든 다음 _update_card_icons() 에서 채운다 - 원격 모드일 땐 로컬 exe 파일이
        # 있을 이유가 없어서(있어도 지금 실행 중인 것과 무관해 의미가 없음)
        # authserver.ico/worldserver.ico 번들 아이콘을 대신 쓰는데, 서버를 전환하면
        # 로컬<->원격이 바뀔 수 있으니 그때마다 다시 계산해서 갈아 끼워야 한다.
        specs = [
            ("mysql", "MySQL", theme.get_icon_image("mysql.webp", max_size=icon_size * 2)),
            ("authserver", "인증 서버", None),
            ("worldserver", "월드 서버", None),
        ]
        card_gap = 12
        avail_w = w - 36
        card_w = (avail_w - card_gap * 2) // 3
        card_h = h - STATUS_HEADER_H - STATUS_BODY_PAD * 2
        card_y = y + STATUS_HEADER_H + STATUS_BODY_PAD
        card_x0 = x + 18
        for i, (key, name, icon_photo) in enumerate(specs):
            cx = card_x0 + i * (card_w + card_gap)
            self._build_status_card(c, cx, card_y, card_w, card_h, key, name, row_bg_avg, icon_photo)
        self._update_card_icons()

    def _build_status_card(self, canvas, x, y, w, h, key, name, row_bg_avg, icon_photo):
        """아이콘 이미지 + 상태 점 + 텍스트에 더해, 시작/중지/콘솔 보기 버튼까지 카드
        안에 바로 둔다(예전엔 '서버 구동' 다이얼로그를 따로 열어야 했는데, 그 기능을
        여기로 옮겼다). 메인 화면에서 바로 mysql/인증 서버/월드 서버를 조작할 수
        있도록 mysql.webp/exe 아이콘과 함께 가로로 나란히 띄워둔다."""
        c = canvas
        card_img = theme.gradient_photo(f"maincard-{key}", w, h, theme.ROW_BG_TOP, theme.ROW_BG_BOTTOM,
                                         radius=5, border=theme.ROW_BORDER)
        c.create_image(x, y, image=card_img, anchor="nw")
        setattr(self, f"_maincard_img_{key}", card_img)

        cx = x + w // 2
        icon_y = y + int(h * 0.26)
        # 아이콘이 없어도(icon_photo=None) item 자체는 만들어 id 를 남겨둔다 -
        # _update_card_icons() 가 나중에 itemconfig(image=...) 로 채워 넣을 수 있게.
        icon_item_id = c.create_image(cx, icon_y, anchor="center")
        setattr(self, f"_maincard_icon_item_{key}", icon_item_id)
        if icon_photo is not None:
            c.itemconfig(icon_item_id, image=icon_photo)
            setattr(self, f"_maincard_icon_{key}", icon_photo)

        c.create_text(cx, y + int(h * 0.50), text=name, anchor="center",
                       font=theme.korean(13, "bold"), fill="#dbe6f3")

        status_y = y + int(h * 0.66)
        dot = StatusDot(c, size=10, container_bg=row_bg_avg,
                         tooltip="초록 = 실행 중 · 노랑 = 진행 중 · 빨강 = 정지됨")
        c.create_window(cx - 26, status_y, window=dot, anchor="center")
        status_text_id = c.create_text(cx - 12, status_y, text=STATUS_LABEL[STOPPED], anchor="w",
                                        font=theme.korean(12), fill=theme.TEXT_MUTED3)
        attach_canvas_item(c, status_text_id, "초록 = 실행 중 · 노랑 = 진행 중 · 빨강 = 정지됨")

        start_w, stop_w, console_w, gm_w, btn_h, gap = 34, 34, 26, 30, 22, 6
        # GM 명령 콘솔은 월드 서버에 대한 조작이라 이 카드에만 4번째 버튼으로
        # 붙인다(메인 화면 헤더는 이미 계정관리/게임설정/서버체크/시작/중지로
        # 꽉 차 있어서 거기에 또 추가하면 좁아짐).
        show_gm_btn = key == "worldserver"
        total_btn_w = start_w + stop_w + console_w + gap * 2
        if show_gm_btn:
            total_btn_w += gm_w + gap
        bx = cx - total_btn_w // 2
        btn_row_y = y + h - 18

        btn_start = GradientButton(
            c, "▶", lambda k=key: self.run_action(k, "start"),
            start_w, btn_h, theme.START_TOP, theme.START_BOTTOM, theme.START_BORDER, theme.START_TEXT,
            hover_border=theme.START_HOVER_BORDER, hover_text_color=theme.START_HOVER_TEXT,
            font=("Segoe UI Symbol", 11, "bold"), radius=3, container_bg=row_bg_avg, key=f"card-start-{key}",
            tooltip=f"{name} 시작",
        )
        c.create_window(bx, btn_row_y, window=btn_start, anchor="w")
        bx += start_w + gap

        btn_stop = GradientButton(
            c, "■", lambda k=key: self.run_action(k, "stop"),
            stop_w, btn_h, theme.STOP_TOP, theme.STOP_BOTTOM, theme.STOP_BORDER, theme.STOP_TEXT,
            hover_border=theme.STOP_HOVER_BORDER, hover_text_color=theme.STOP_HOVER_TEXT,
            font=("Segoe UI Symbol", 9, "bold"), radius=3, container_bg=row_bg_avg, key=f"card-stop-{key}",
            tooltip=f"{name} 중지",
        )
        c.create_window(bx, btn_row_y, window=btn_stop, anchor="w")
        bx += stop_w + gap

        btn_console = GradientButton(
            c, ">_", lambda k=key: self.on_view_console(k),
            console_w, btn_h, theme.ICON_TOP, theme.ICON_BOTTOM, theme.ICON_BORDER, theme.ICON_TEXT,
            hover_border=theme.ICON_HOVER_BORDER, font=theme.mono(10, "bold"),
            radius=3, container_bg=row_bg_avg, key=f"card-console-{key}",
            tooltip=f"{name} 콘솔 창 보기/숨기기 (실행 중일 때만)",
        )
        c.create_window(bx, btn_row_y, window=btn_console, anchor="w")

        if show_gm_btn:
            bx += console_w + gap
            btn_gm = GradientButton(
                c, "GM", lambda: self.open_gm_console(), gm_w, btn_h,
                theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
                hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
                font=theme.korean(9, "bold"), radius=3, container_bg=row_bg_avg, key="card-gm-console",
                tooltip="GM 명령 직접 입력해서 실행 (SOAP)",
            )
            c.create_window(bx, btn_row_y, window=btn_gm, anchor="w")

        self.main_rows[key] = {
            "canvas": c, "dot": dot, "status_text_id": status_text_id,
            "btn_start": btn_start, "btn_stop": btn_stop, "btn_console": btn_console,
        }

    def _build_play_row(self, x, y, w, h):
        self.play_btn = GradientButton(
            self.canvas, "▶  PLAY", self.on_play, PLAY_W, PLAY_H,
            theme.PLAY_DOWN_TOP, theme.PLAY_DOWN_BOTTOM, theme.PLAY_DOWN_BORDER, theme.PLAY_DOWN_TEXT,
            font=theme.cinzel(30, "bold"), radius=6, border_width=2, container_bg="#0d1a26", key="play",
            tooltip="WoW 클라이언트 실행 (MySQL/인증 서버/월드 서버가 모두 실행 중이어야 함)",
        )
        self.play_btn.set_enabled(False)
        self.canvas.create_window(x + w - PLAY_W, y, window=self.play_btn, anchor="nw")
        self._play_up = False

        # PLAY 버튼 왼쪽의 남는 공간에 'server info' GM 명령 결과(접속 인원/최고 접속/
        # 가동 시간/응답 지연)를 보여준다. 스플래시 이미지 바로 오른쪽이라 "왼쪽 이미지와
        # PLAY 버튼 사이"에 해당하는 자리.
        info_w = w - PLAY_W - PLAY_GAP
        self._build_server_info_panel(x, y, info_w, h)

    SERVER_INFO_INTERVAL_MS = 10 * 60 * 1000  # 10분

    # 통계별 아이콘 점 색(글꼴에 있는지 없는지 알 수 없는 그림문자 대신, 항상 그려지는
    # 캔버스 원을 작은 "아이콘"으로 써서 폰트 미지원 문제 없이 구분되게 했다).
    SERVER_INFO_SPECS = [
        ("characters", "접속", "#5fe08a"),
        ("peak", "최고 접속", "#e0b93f"),
        ("uptime", "가동", "#6fa8dc"),
        ("update_diff_ms", "지연", "#5fe08a"),
    ]

    SERVER_INFO_TOOLTIPS = {
        "characters": "지금 월드에 접속해 있는 캐릭터 수 (봇 포함, 온라인 계정 목록과 동일 기준)",
        "peak": "서버가 시작된 뒤 실제 접속 세션 기준 최고 동시 접속자 수",
        "uptime": "월드 서버가 켜진 뒤 지난 시간",
        "update_diff_ms": "서버 틱 처리 지연 (200ms 미만 초록 · 500ms 미만 노랑 · 그 이상 빨강)",
    }

    def _build_server_info_panel(self, x, y, w, h):
        c = self.canvas
        row_bg_avg = hexcolor(((theme.ROW_BG_TOP[0] + theme.ROW_BG_BOTTOM[0]) // 2,
                               (theme.ROW_BG_TOP[1] + theme.ROW_BG_BOTTOM[1]) // 2,
                               (theme.ROW_BG_TOP[2] + theme.ROW_BG_BOTTOM[2]) // 2))
        panel_img = theme.gradient_photo("server-info-panel", w, h, theme.ROW_BG_TOP, theme.ROW_BG_BOTTOM,
                                          radius=5, border=theme.ROW_BORDER)
        self._server_info_panel_img = panel_img
        c.create_image(x, y, image=panel_img, anchor="nw")

        btn_size = 30
        refresh_btn = GradientButton(
            c, "⟳", self._refresh_server_info, btn_size, btn_size,
            theme.ICON_TOP, theme.ICON_BOTTOM, theme.ICON_BORDER, theme.ICON_TEXT,
            hover_border=theme.ICON_HOVER_BORDER, font=("Segoe UI Symbol", 14, "bold"),
            radius=4, container_bg=row_bg_avg, key="server-info-refresh",
            tooltip="서버 정보 새로고침 (10분마다 자동으로도 갱신됨)",
        )
        c.create_window(x + w - 10, y + h // 2, window=refresh_btn, anchor="e")

        seg_w = (w - btn_size - 24) // len(self.SERVER_INFO_SPECS)
        cy = y + h // 2
        self._server_info_dot_ids = {}
        self._server_info_text_ids = {}
        for i, (key, label, color) in enumerate(self.SERVER_INFO_SPECS):
            seg_x = x + 16 + i * seg_w
            dot_id = c.create_oval(seg_x, cy - 5, seg_x + 10, cy + 5, fill=color, outline="")
            text_id = c.create_text(seg_x + 16, cy, text=f"{label} —", anchor="w",
                                     font=theme.korean(12, "bold"), fill=theme.HEADER_TEXT)
            self._server_info_dot_ids[key] = dot_id
            self._server_info_text_ids[key] = text_id
            tip = self.SERVER_INFO_TOOLTIPS[key]
            attach_canvas_item(c, dot_id, tip)
            attach_canvas_item(c, text_id, tip)
        self._server_info_after_id = None

    def _refresh_server_info(self):
        """'server info' 는 SOAP 호출 1번짜리라(온라인 계정 목록과 달리 캐릭터마다
        추가 호출이 없음) 가볍다 — 10분마다 자동으로, 그리고 ⟳ 버튼을 눌러도 즉시
        새로고침한다. 자동/수동 두 경로가 겹쳐서 예약된 새로고침이 계속 쌓이는 걸
        막기 위해, 시작할 때 대기 중인 예약을 먼저 취소한다."""
        if self._server_info_after_id is not None:
            try:
                self.root.after_cancel(self._server_info_after_id)
            except Exception:
                pass
            self._server_info_after_id = None

        gm_account = self.cfg.get("gm_account", "")
        gm_password = self.cfg.get("gm_password", "")
        if self._last_status.get("worldserver") != RUNNING or not gm_account or not gm_password:
            for key, label, _color in self.SERVER_INFO_SPECS:
                self.canvas.itemconfig(self._server_info_text_ids[key], text=f"{label} —")
            self._server_info_after_id = self.root.after(
                self.SERVER_INFO_INTERVAL_MS, self._refresh_server_info)
            return

        for key, label, _color in self.SERVER_INFO_SPECS:
            self.canvas.itemconfig(self._server_info_text_ids[key], text=f"{label} …")

        def worker():
            ok, msg = soap_client.execute_command(
                self.soap_host(), int(self.cfg.get("soap_port", 7878)),
                gm_account, gm_password, "server info", timeout=8,
            )
            info = soap_client.parse_server_info(msg) if ok else {}
            self.root.after(0, lambda: self._apply_server_info(info))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_server_info(self, info):
        # "Connected players"(실제 접속) 대신 "Characters in world"(월드 내 캐릭터 수)를
        # 쓴다 — 온라인 계정 목록(account onlinelist)이 세는 것도 바로 이 값이라,
        # 봇이 많은 서버에서 두 화면의 인원수가 서로 다르게 보이던 문제를 해결한다.
        characters = info.get("characters")
        peak = info.get("peak")
        uptime = info.get("uptime")
        diff = info.get("update_diff_ms")

        if characters is None and peak is None and uptime is None and diff is None:
            for key, label, _color in self.SERVER_INFO_SPECS:
                self.canvas.itemconfig(self._server_info_text_ids[key], text=f"{label} 오류")
            self._server_info_after_id = self.root.after(
                self.SERVER_INFO_INTERVAL_MS, self._refresh_server_info)
            return

        self.canvas.itemconfig(self._server_info_text_ids["characters"],
                                text=f"접속 {characters}명" if characters is not None else "접속 —")
        self.canvas.itemconfig(self._server_info_text_ids["peak"],
                                text=f"최고 접속 {peak}명" if peak is not None else "최고 접속 —")
        self.canvas.itemconfig(self._server_info_text_ids["uptime"],
                                text=f"가동 {uptime}" if uptime else "가동 —")
        if diff is not None:
            self.canvas.itemconfig(self._server_info_text_ids["update_diff_ms"], text=f"지연 {diff}ms")
            # 지연이 크면 초록 대신 주황/빨강 점으로 바로 알아볼 수 있게 한다.
            diff_color = "#5fe08a" if diff < 200 else ("#e0b93f" if diff < 500 else "#c0392b")
            self.canvas.itemconfig(self._server_info_dot_ids["update_diff_ms"], fill=diff_color)
        else:
            self.canvas.itemconfig(self._server_info_text_ids["update_diff_ms"], text="지연 —")

        self._server_info_after_id = self.root.after(
            self.SERVER_INFO_INTERVAL_MS, self._refresh_server_info)

    def _set_play_state(self, all_up):
        if all_up == self._play_up:
            return
        self._play_up = all_up
        b = self.play_btn
        k = "play"
        if all_up:
            b.normal_img = theme.gradient_photo(f"{k}-up-n", PLAY_W, PLAY_H, theme.PLAY_UP_TOP,
                                                 theme.PLAY_UP_BOTTOM, 6, theme.PLAY_UP_BORDER, 2)
            b.hover_img = theme.gradient_photo(f"{k}-up-h", PLAY_W, PLAY_H, theme.PLAY_UP_TOP,
                                                theme.PLAY_UP_BOTTOM, 6, "#fff0bd", 2)
            b.normal_text = theme.PLAY_UP_TEXT
            b.hover_text = theme.PLAY_UP_TEXT
        else:
            b.normal_img = theme.gradient_photo(f"{k}-dn-n", PLAY_W, PLAY_H, theme.PLAY_DOWN_TOP,
                                                 theme.PLAY_DOWN_BOTTOM, 6, theme.PLAY_DOWN_BORDER, 2)
            b.hover_img = b.normal_img
            b.normal_text = theme.PLAY_DOWN_TEXT
            b.hover_text = theme.PLAY_DOWN_TEXT
        b.itemconfig(b.img_id, image=b.normal_img)
        b.itemconfig(b.text_id, fill=b.normal_text)
        has_client = bool(self.cfg.get("wow_client_exe"))
        b.set_enabled(all_up and has_client)

    def _update_mode_badge(self):
        if not hasattr(self, "_mode_badge_id"):
            return
        servers = self.cfg.get("servers") or []
        active_id = self.cfg.get("active_server_id")
        server = next((s for s in servers if s.get("id") == active_id), None)
        name = server.get("name", "서버") if server else "서버"
        tag = "원격" if self.mode == "remote" else "로컬"
        full_text = f"[{name} · {tag}]"

        max_w = getattr(self, "_badge_max_w", None)
        display_text = full_text
        if max_w and max_w > 0:
            f = tkfont.Font(font=theme.korean(11, "bold"))
            if f.measure(full_text) > max_w:
                suffix = f" · {tag}]"
                budget = max_w - f.measure("[" + suffix)
                truncated = ""
                for i in range(len(name), 0, -1):
                    candidate = name[:i] + "…"
                    if f.measure(candidate) <= budget:
                        truncated = candidate
                        break
                display_text = f"[{truncated or '…'}{suffix}"
        self.canvas.itemconfig(self._mode_badge_id, text=display_text)
        if hasattr(self, "_mode_badge_tooltip"):
            self._mode_badge_tooltip.set_text(f"지금 활성 서버: {name} ({tag}) — 클릭하면 서버 관리")

    def _on_server_manage_changed(self):
        """메인 화면에서 연 서버 관리 창에서 서버를 바꾸면(전환/추가/삭제로 활성
        서버가 달라지면), 지금 알고 있는 상태를 새로 반영한다 - 다음 1.5초
        새로고침을 기다리지 않고 바로."""
        self._refresh_server_info()
        results = {}
        for key, svc in self.services.items():
            status = self._last_status.get(key, STOPPED)
            console_on = svc.console_visible() if status in (RUNNING, STARTING) else False
            results[key] = {"status": status, "busy": False, "console_on": console_on}
        self._apply_refresh(results)

    def switch_to_server(self, server):
        """활성 서버를 server 로 바꾸고 연쇄적으로 필요한 걸 전부 그 자리에서
        반영한다(서비스 재설정, realmlist.wtf, 배지, 상태 카드/Play 버튼) - 서버
        관리 창의 "전환" 버튼과 메인 화면 헤더의 서버 전환 드롭다운이 이 메서드
        하나를 같이 쓴다. 두 경로가 각자 따로 flatten/apply_config 를 부르게
        놔두면 나중에 한쪽만 고치고 다른 쪽을 깜빡하는 식으로 갈라지기 쉬워서
        하나로 합쳤다."""
        if server.get("id") == self.cfg.get("active_server_id"):
            return
        self.cfg["active_server_id"] = server["id"]
        config_store.flatten_active_server(self.cfg)
        config_store.save_config(self.cfg)
        self.apply_config()
        self._update_realmlist_file()
        self._update_mode_badge()
        self._on_server_manage_changed()

    def _open_server_switch_menu(self):
        """헤더의 ☰ 아이콘 - 서버 목록을 드롭다운(tk.Menu)으로 보여주고, 고르면
        바로 그 서버로 전환한다. 서버 추가/삭제 같은 목록 자체를 바꾸는 작업은
        메뉴 맨 아래 "서버 관리..." 로 기존 ServerManageDialog 를 그대로 연다."""
        servers = self.cfg.get("servers") or []
        active_id = self.cfg.get("active_server_id")
        menu = tk.Menu(self.root, tearoff=0, bg="#132235", fg=theme.BODY_TEXT,
                        activebackground=theme.PANEL_BORDER, activeforeground=theme.HEADER_TEXT,
                        font=theme.korean(11), bd=0)
        for server in servers:
            tag = "원격" if server.get("mode") == "remote" else "로컬"
            mark = "● " if server.get("id") == active_id else "    "
            label = f"{mark}{server.get('name', '서버')}  [{tag}]"
            menu.add_command(label=label, command=lambda s=server: self.switch_to_server(s))
        menu.add_separator()
        menu.add_command(
            label="서버 관리...",
            command=lambda: ServerManageDialog(self, on_change=self._on_server_manage_changed),
        )
        btn = self.btn_server_switch
        mx = btn.winfo_rootx()
        my = btn.winfo_rooty() + btn.winfo_height()
        try:
            menu.tk_popup(mx, my)
        finally:
            menu.grab_release()

    def soap_host(self):
        """GM SOAP 호출(계정 관리/서버 정보/전체 저장 등)에 쓸 호스트. 원격
        모드면 원격 서버 주소, 로컬이면 지금처럼 항상 127.0.0.1(SOAP 는 로컬
        worldserver 에만 붙게 돼 있음)."""
        if self.mode == "remote":
            return self.cfg.get("remote_host", "") or "127.0.0.1"
        return "127.0.0.1"

    def _build_services(self):
        """self.mode 에 맞는 서비스 객체 3개를 새로 만든다. 로컬/원격은 클래스
        자체가 달라서(ServiceProcess vs RemoteServiceProcess), 설정에서 모드를
        바꾼 경우 기존 객체의 속성만 고쳐 쓸 수 없고 통째로 다시 만들어야 한다."""
        if self.mode == "remote":
            return {
                "mysql": remote_process.RemoteServiceProcess(
                    "mysql", "MySQL", "port", port=self.cfg.get("mysql_port", 3306)),
                "authserver": remote_process.RemoteServiceProcess(
                    "authserver", "인증 서버", "port", port=self.cfg.get("auth_port", 3724)),
                "worldserver": remote_process.RemoteServiceProcess("worldserver", "월드 서버", "soap"),
            }
        return {
            "mysql": MysqlProcess(),
            "authserver": ServiceProcess("authserver", "인증 서버", self.cfg.get("auth_port", 3724)),
            "worldserver": ServiceProcess("worldserver", "월드 서버", self.cfg.get("world_port", 8085)),
        }

    # ==================== 설정 반영 ====================
    def apply_config(self):
        """서버 파일이 있는 위치(root_dir)와, 이 런처 exe 가 실제로 놓인 위치가
        다를 수 있다(예: 런처를 WoW 클라이언트 폴더에 복사해서 실행하는 경우, 서버는
        전혀 다른 드라이브에 있음). 그래서 각 서비스의 작업 폴더(cwd)는 root_dir 같은
        간접값이 아니라, 그 서비스에 실제로 지정된 실행파일 경로에서 직접 뽑아낸다 —
        안 그러면 authserver.exe 경로는 맞는데 cwd 만 틀려서, authserver 가 자기
        configs\\authserver.conf 를 못 찾고 시작하자마자 조용히 종료해버리는 버그가 생긴다
        (root_dir 자동 감지값이 실제 서버 위치와 다를 때 실제로 이렇게 재현됨)."""
        cfg = self.cfg
        new_mode = cfg.get("mode", "local")
        if new_mode != self.mode:
            # 설정에서 로컬/원격을 바꾼 경우 - 서비스 객체 자체를 다시 만든다
            # (아래에서 바로 새 객체에 host/port 등을 채움).
            self.mode = new_mode
            self.services = self._build_services()

        if self.mode == "remote":
            host = cfg.get("remote_host", "")
            self.services["mysql"].host = host
            self.services["mysql"].port = int(cfg.get("mysql_port", 3306))
            self.services["authserver"].host = host
            self.services["authserver"].port = int(cfg.get("auth_port", 3724))
            self.services["worldserver"].host = host
            self.services["worldserver"].soap_port = int(cfg.get("soap_port", 7878))
            self.services["worldserver"].gm_account = cfg.get("gm_account", "")
            self.services["worldserver"].gm_password = cfg.get("gm_password", "")
            self.ip_label.config(text=host or "(미설정)")
            self._update_card_icons()
            return

        root_dir = cfg.get("root_dir") or config_store.DEFAULT_ROOT

        mysqld = cfg.get("mysqld_exe", "")
        is_bat = mysqld.lower().endswith((".bat", ".cmd"))
        # mysqladmin/my.ini 는 mysqld_exe 가 실제로 있는 위치 기준으로 찾는다(.bat 는
        # 보통 repack 루트에 바로 있고, mysqld.exe 는 그 밑 mysql\bin\ 에 있음) —
        # root_dir 을 안 쓰는 이유는 위와 같다.
        mysql_root = os.path.dirname(mysqld) if is_bat else os.path.dirname(os.path.dirname(mysqld))
        mysql_root = mysql_root or root_dir
        mysqladmin = os.path.join(mysql_root, "mysql", "bin", "mysqladmin.exe")
        mysql_ini = os.path.join(mysql_root, "mysql", "my.ini")
        # .bat 로 실행하는 경우 그 안에 이미 필요한 옵션이 들어있다고 보고 별도 인자를 안 붙인다
        # (배치파일이 인자를 받아 쓰지 않기도 하고, 뜻하지 않게 두 번 지정되는 걸 피하기 위함).
        mysql_args = [] if is_bat else (
            [f"--defaults-file={mysql_ini}"] if os.path.isfile(mysql_ini) else []
        )

        self.services["mysql"].port = int(cfg.get("mysql_port", 3306))
        self.services["mysql"].host = cfg.get("mysql_host", "127.0.0.1")
        self.services["mysql"].configure(
            exe_path=mysqld, cwd=os.path.dirname(mysqld) or root_dir,
            args=mysql_args, mysqladmin_exe=mysqladmin,
        )
        auth_exe = cfg.get("authserver_exe", "")
        self.services["authserver"].port = int(cfg.get("auth_port", 3724))
        self.services["authserver"].configure(exe_path=auth_exe, cwd=os.path.dirname(auth_exe) or root_dir)
        world_exe = cfg.get("worldserver_exe", "")
        self.services["worldserver"].port = int(cfg.get("world_port", 8085))
        self.services["worldserver"].configure(exe_path=world_exe, cwd=os.path.dirname(world_exe) or root_dir)

        self.ip_label.config(text=cfg.get("mysql_host", "127.0.0.1"))
        self._update_card_icons()

    def _update_card_icons(self):
        """인증 서버/월드 서버 카드의 아이콘을 지금 모드에 맞게 (다시) 채운다.
        로컬 모드면 지금까지처럼 실제 exe 파일에 박힌 아이콘을 뽑아 쓰고, 원격
        모드면(로컬 exe 경로가 있어도 지금 실행 중인 것과 무관하므로 의미가 없다)
        assets\\authserver.ico / worldserver.ico 번들 아이콘을 대신 쓴다. exe
        추출이 실패해도(경로가 비었거나 파일이 없음) 같은 번들 아이콘으로 대체돼서
        카드가 아이콘 없이 비어 보이는 일이 없다. apply_config() 가 호출될 때마다
        (시작 시, 설정 저장 시, 서버 전환/삭제 시) 같이 호출돼서 항상 지금 활성
        서버의 모드를 반영한다."""
        if not hasattr(self, "_maincard_icon_item_authserver"):
            return  # 아직 상태 카드가 만들어지기 전(최초 apply_config 호출 이전)
        icon_size = 40
        for key, exe_key, ico_name in (
            ("authserver", "authserver_exe", "authserver.ico"),
            ("worldserver", "worldserver_exe", "worldserver.ico"),
        ):
            icon = None
            if self.mode != "remote":
                icon = theme.get_exe_icon_image(self.cfg.get(exe_key, ""), size=icon_size)
            if icon is None:
                icon = theme.get_icon_image(ico_name, max_size=icon_size)
            if icon is None:
                continue
            item_id = getattr(self, f"_maincard_icon_item_{key}")
            self.canvas.itemconfig(item_id, image=icon)
            setattr(self, f"_maincard_icon_{key}", icon)  # GC 방지용 참조 유지

    def _update_realmlist_file(self):
        """클라이언트 폴더 밑의 realmlist.wtf 를 "지금 활성 서버"의 렐름리스트
        주소로 다시 쓴다. 설정 저장(SettingsDialog._save) 뿐 아니라 서버 관리
        창에서 서버를 전환/삭제해서 활성 서버가 바뀔 때도 호출해야 한다 - 안
        그러면 다른 서버로 전환했는데 클라이언트는 예전 서버 주소로 계속
        접속을 시도하는 상태가 된다."""
        client_dir = os.path.dirname(self.cfg.get("wow_client_exe", ""))
        active = self.cfg.get("realmlist_active", "")
        if not client_dir or not active or not os.path.isdir(client_dir):
            return
        try:
            found = glob.glob(os.path.join(client_dir, "**", "realmlist.wtf"), recursive=True)
            for f in found:
                with open(f, "w", encoding="utf-8") as fh:
                    fh.write(f"set realmlist {active}\n")
        except OSError:
            pass

    def _check_remote_server(self):
        """메인 화면 "⟲ 서버 체크" 아이콘(원격 모드 전용) - authserver.conf 의
        RealmServerPort, worldserver.conf 의 SOAP.Port 를 SSH 로 직접 읽어와서,
        수동으로 입력해둔 auth_port/soap_port 설정값이 실제 conf 파일과 다르면
        자동으로 바로잡은 뒤 그 값으로 접속까지 확인한다. 인증 서버는 raw TCP
        포트 검사라 conf 에 적힌 실제 리슨 포트와 설정값이 어긋나면 서버가 켜져
        있어도 "정지"로 잘못 표시되는데, 이 버튼이 그 어긋남을 바로잡는 용도다.
        매 1.5초 새로고침마다 SSH 를 새로 열면 느려지니, 자동 폴링에는 안 쓰고
        이 버튼을 눌렀을 때만 한 번 확인한다."""
        if self.mode != "remote":
            return
        cfg = self.cfg
        host = cfg.get("remote_host", "")
        ssh_port = cfg.get("remote_ssh_port", 22)
        ssh_user = cfg.get("remote_ssh_user", "")
        ssh_key = cfg.get("remote_ssh_key_path", "")
        auth_conf_path = cfg.get("remote_authserver_conf_path", "")
        world_conf_path = cfg.get("remote_worldserver_conf_path", "")
        gm_account = cfg.get("gm_account", "")
        gm_password = cfg.get("gm_password", "")
        mysql_port = int(cfg.get("mysql_port", 3306) or 3306)
        prev_auth_port = int(cfg.get("auth_port", 3724) or 3724)
        prev_soap_port = int(cfg.get("soap_port", 7878) or 7878)

        if not host:
            alert(self.root, "서버 체크", "호스트가 설정되어 있지 않습니다. 설정에서 원격 접속 정보를 먼저 입력해 주세요.")
            return

        self.btn_remote_check.set_enabled(False)

        def worker():
            lines = []
            detected_auth_port = None
            detected_soap_port = None

            if auth_conf_path:
                content, err = remote_conf.read_text_detailed(host, ssh_port, ssh_user, ssh_key, auth_conf_path)
                if content is not None:
                    v = conf_reader.parse_conf_value_from_text(content, "RealmServerPort")
                    if v and v.strip().isdigit():
                        detected_auth_port = int(v.strip())
                        lines.append(f"인증 서버 conf에서 포트 확인: {detected_auth_port}")
                    else:
                        lines.append("인증 서버 conf에 RealmServerPort 값이 없어 기존 설정값을 그대로 씀")
                else:
                    lines.append(f"인증 서버 conf 읽기 실패: {err}")
            else:
                lines.append("원격 authserver.conf 경로가 비어 있어 conf 확인은 건너뜀")

            if world_conf_path:
                content, err = remote_conf.read_text_detailed(host, ssh_port, ssh_user, ssh_key, world_conf_path)
                if content is not None:
                    v = conf_reader.parse_conf_value_from_text(content, "SOAP.Port")
                    if v and v.strip().isdigit():
                        detected_soap_port = int(v.strip())
                        lines.append(f"월드 서버 conf에서 SOAP 포트 확인: {detected_soap_port}")
                    else:
                        lines.append("월드 서버 conf에 SOAP.Port 값이 없어 기존 설정값을 그대로 씀")
                    enabled_v = conf_reader.parse_conf_value_from_text(content, "SOAP.Enabled")
                    if enabled_v is not None and enabled_v.strip() not in ("1", "true", "True"):
                        lines.append("⚠ worldserver.conf 에 SOAP.Enabled = 0 으로 되어 있습니다 - "
                                      "이러면 월드 서버가 켜져 있어도 상태 확인/계정 관리가 항상 실패합니다.")
                    soap_ip_v = conf_reader.parse_conf_value_from_text(content, "SOAP.IP")
                    if soap_ip_v and soap_ip_v.strip() in ("127.0.0.1", "localhost"):
                        lines.append(
                            f"⚠ worldserver.conf 에 SOAP.IP = {soap_ip_v.strip()} 로 되어 있습니다 - "
                            "SOAP이 원격 서버(또는 도커 컨테이너) 자기 자신에게만 열려 있어서 "
                            "게임 접속 포트(WorldServerPort)와 달리 외부에서는 접속할 수 없습니다. "
                            "이게 SOAP만 실패하고 게임 플레이는 되는 가장 흔한 원인입니다 - "
                            "worldserver.conf 에서 SOAP.IP 를 \"0.0.0.0\" 으로 바꾸고(도커라면 컨테이너의 "
                            "0.0.0.0이어야 포트 매핑을 통해 바깥에서 닿습니다) 월드 서버를 재시작해야 "
                            "합니다.")
                else:
                    lines.append(f"월드 서버 conf 읽기 실패: {err}")
            else:
                lines.append("원격 worldserver.conf 경로가 비어 있어 conf 확인은 건너뜀")

            final_auth_port = detected_auth_port or prev_auth_port
            final_soap_port = detected_soap_port or prev_soap_port

            def tcp_check(port):
                try:
                    with socket.create_connection((host, port), timeout=3):
                        return True
                except OSError:
                    return False

            mysql_ok = tcp_check(mysql_port)
            auth_ok = tcp_check(final_auth_port)
            if gm_account and gm_password:
                world_ok, world_msg = soap_client.execute_command(
                    host, final_soap_port, gm_account, gm_password, "server info", timeout=8)
            else:
                world_ok, world_msg = False, "GM 계정/비밀번호가 설정되어 있지 않습니다."

            lines.append("")
            lines.append(f"MySQL ({mysql_port}): {'✅ 온라인' if mysql_ok else '❌ 오프라인'}")
            lines.append(f"인증 서버 ({final_auth_port}): {'✅ 온라인' if auth_ok else '❌ 오프라인'}")
            world_line = f"월드 서버 (SOAP {final_soap_port}): {'✅ 온라인' if world_ok else '❌ 오프라인'}"
            if not world_ok:
                world_line += f" - {world_msg}"
            lines.append(world_line)

            def apply():
                changed = False
                if detected_auth_port and detected_auth_port != prev_auth_port:
                    self.cfg["auth_port"] = detected_auth_port
                    self.services["authserver"].port = detected_auth_port
                    changed = True
                if detected_soap_port and detected_soap_port != prev_soap_port:
                    self.cfg["soap_port"] = detected_soap_port
                    self.services["worldserver"].soap_port = detected_soap_port
                    changed = True
                if changed:
                    config_store.sync_active_server(self.cfg)
                    config_store.save_config(self.cfg)

                self.btn_remote_check.set_enabled(True)
                self._last_status["mysql"] = RUNNING if mysql_ok else STOPPED
                self._last_status["authserver"] = RUNNING if auth_ok else STOPPED
                self._last_status["worldserver"] = RUNNING if world_ok else STOPPED
                results = {k: {"status": v, "busy": False, "console_on": False}
                           for k, v in self._last_status.items()}
                self._apply_refresh(results)
                RemoteCheckResultDialog(self, lines)

            self.root.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def _log_perf(self, message):
        """설정 창 열기/찾아보기 같은 조작이 유난히 느렸을 때(0.15초 이상) 그 순간의
        상황(무슨 동작이 busy 인지, 각 서비스 마지막 확인 상태)까지 같이 launcher\\perf.log
        에 남긴다. 사용자 PC 에서만 재현되는 느려짐은 여기서 직접 원인을 추측하는 것보다
        실제 기록을 보고 판단하는 게 정확하다."""
        try:
            log_path = os.path.join(paths.BASE_DIR, "perf.log")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message} "
                        f"(busy={dict(self.busy)}, last_status={dict(self._last_status)})\n")
        except OSError:
            pass

    # ==================== 설정 / 도움말 창 ====================
    def open_settings(self):
        t0 = time.perf_counter()
        SettingsDialog(self)
        elapsed = time.perf_counter() - t0
        if elapsed > 0.15:
            self._log_perf(f"설정 창 생성 {elapsed:.3f}초 걸림 (평소보다 느림)")

    def open_help(self):
        HelpDialog(self)

    def open_account_manage(self):
        AccountManageDialog(self)

    def open_gm_console(self):
        GmConsoleDialog(self)

    def open_game_settings(self):
        GameSettingsDialog(self)

    def _run_autostart(self):
        """설정의 '런처 실행 시 자동 시작'이 켜져 있으면 실행되는 경로. 진행 중임을
        알 수 있도록 패널 제목("서버 상태")을 잠깐 "서버 상태 — 자동시작중..." 으로
        바꿔뒀다가, 모두 시작이 끝나면(성공/실패 무관) 원래대로 되돌린다(모두 시작/
        모두 중지가 아이콘 버튼으로 바뀌면서 글자를 표시할 자리가 따로 없어졌다)."""
        self.canvas.itemconfig(self._panel_title_id, text="서버 상태 — 자동시작중...")
        self.run_action("all", "start")
        self._watch_autostart_completion()

    def _watch_autostart_completion(self):
        if self.busy.get("all") is not None:
            self.root.after(500, self._watch_autostart_completion)
            return
        self.canvas.itemconfig(self._panel_title_id, text="서버 상태")

    # ==================== 동작 ====================
    def run_action(self, key, action):
        """key 는 서비스 키 또는 'all'. action 은 'start'/'stop'/'restart'.
        self.busy[key] 에는 진행 중인 동작 이름을 넣어둔다 (없으면 None) —
        refresh() 가 pid 유무를 추측하지 않고 실제로 어떤 동작이 진행 중인지 그대로 표시하게 함."""
        if key == "all":
            if self.busy.get("all"):
                return
            if action != "start":
                for k in self.services:
                    self._intentional_stop[k] = True
            self.busy["all"] = action

            def worker_all():
                try:
                    if action == "start":
                        self._start_all_sequenced()
                    else:
                        self._stop_all_sequenced()
                finally:
                    self.busy["all"] = None

            threading.Thread(target=worker_all, daemon=True).start()
            return

        if self.busy.get(key):
            return

        if action in ("stop", "restart"):
            # 사용자가 직접 중지/재시작을 눌렀다는 표시 — refresh() 폴링 주기(1.5초)보다
            # 먼저 서비스가 죽어버리면(WM_CLOSE 로 바로 꺼지는 경우가 흔함) 상태 변화를
            # 놓쳐서 방금 누른 중지를 "예상치 않은 종료"로 착각해 오류창을 띄우는 버그가
            # 있었다. 이 플래그로 그 다음 STOPPED 전환 한 번은 경고 없이 넘어간다.
            self._intentional_stop[key] = True
        else:
            self._intentional_stop[key] = False

        self.busy[key] = action

        def worker():
            svc = self.services[key]
            ok, err = True, None
            try:
                show_console = bool(self.cfg.get("opt_show_console"))
                if action == "start":
                    ok, err = svc.start(show_console=show_console)
                elif action == "stop":
                    if key == "worldserver":
                        self._saveall_before_stop()
                    ok, err = svc.stop()
                elif action == "restart":
                    if key == "worldserver":
                        self._saveall_before_stop()
                    svc.stop()
                    time.sleep(1.0)
                    ok, err = svc.start(show_console=show_console)
            finally:
                self.busy[key] = None
                if not ok and err:
                    # 경로가 잘못됐거나 실행 자체가 실패한 경우 — 예전엔 여기서 그냥
                    # 조용히 실패해서 "눌러도 반응이 없다"처럼 보였다. 즉시 알려준다.
                    self._notify_error("실행 실패", f"{svc.display_name}: {err}")

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _wait_for_port(svc, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if svc.is_port_open():
                return True
            time.sleep(0.5)
        return False

    def _saveall_before_stop(self):
        """월드서버를 멈추기 직전에 saveall 을 한 번 시도한다(데이터 유실 방지).
        SOAP 이 설정 안 됐거나 실패해도 팝업 없이 조용히 넘어가고 중지는 그대로 진행한다
        — 저장 시도가 실제 종료를 막는 요인이 되면 안 된다."""
        if self.services["worldserver"].status() != RUNNING:
            return
        try:
            soap_client.execute_command(
                self.soap_host(), int(self.cfg.get("soap_port", 7878)),
                self.cfg.get("gm_account", ""), self.cfg.get("gm_password", ""),
                "saveall", timeout=5,
            )
        except Exception:
            pass

    def _force_foreground(self):
        """커스텀 테두리 없는 창(overrideredirect) 뒤에 안내창이 숨어서, 응답을 기다리며
        앱 전체가 멈춘 것처럼 보이는 걸 막기 위해 안내창을 띄우기 직전에 메인 창을
        강제로 앞으로/포커스로 가져온다."""
        try:
            self.root.attributes("-topmost", True)
            self.root.lift()
            self.root.focus_force()
            self.root.update()
        except Exception:
            pass

    def _show_message(self, kind, title, message):
        def show():
            self._force_foreground()
            fn = {"error": messagebox.showerror, "warning": messagebox.showwarning,
                  "info": messagebox.showinfo}[kind]
            fn(title, message, parent=self.root)
            try:
                self.root.attributes("-topmost", False)
            except Exception:
                pass
        self.root.after(0, show)

    def _notify_error(self, title, message):
        self._show_message("error", title, message)

    def _start_all_sequenced(self):
        """MySQL 이 실제로 응답하는 걸 확인한 뒤 AuthServer, AuthServer 가 실제로
        응답하는 걸 확인한 뒤에야 WorldServer 를 시작한다. 앞 단계가 시간 내에
        올라오지 못해도(느린 PC 에서 MySQL 초기 구동이 오래 걸릴 수 있음) 팝업 없이
        조용히 다음 단계로 넘어간다 — 상태 점이 이미 그 상황을 그대로 보여준다."""
        show_console = bool(self.cfg.get("opt_show_console"))
        mysql = self.services["mysql"]
        mysql.start(show_console=show_console)
        self._wait_for_port(mysql, 45)

        auth = self.services["authserver"]
        auth.start(show_console=show_console)
        self._wait_for_port(auth, 30)

        self.services["worldserver"].start(show_console=show_console)

    def _stop_all_sequenced(self):
        self._saveall_before_stop()
        self.services["worldserver"].stop()
        self.services["authserver"].stop()
        self.services["mysql"].stop()

    def on_play(self):
        exe = self.cfg.get("wow_client_exe", "")
        ok, err = launch_client(exe)
        if not ok:
            self._notify_error("실행 실패", err)
            return
        try:
            for p in psutil.process_iter(["pid", "exe"]):
                if p.info.get("exe") and os.path.normcase(p.info["exe"]) == os.path.normcase(exe):
                    self._client_pid = p.info["pid"]
        except Exception:
            self._client_pid = None

    def on_view_console(self, key):
        """다시 누르면 숨기고, 숨겨져 있으면 보여준다 (토글)."""
        svc = self.services[key]
        if self._last_status.get(key) == STOPPED:
            self._show_message("info", "콘솔 보기", f"{svc.display_name} 이(가) 실행 중이 아닙니다.")
            return
        if not svc.toggle_console():
            self._show_message("info", "콘솔 보기", f"{svc.display_name} 콘솔창을 찾을 수 없습니다.")

    # ==================== 주기적 상태 갱신 ====================
    LOG_FILE_BY_KEY = {"authserver": "Auth.log", "worldserver": "Server.log"}

    @staticmethod
    def _tail_log(path, n_lines=12, max_bytes=8000):
        """로그 파일(수 MB) 전체를 읽지 않고 끝부분만 효율적으로 읽어온다."""
        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - max_bytes))
                data = f.read().decode("utf-8", errors="replace")
            lines = data.splitlines()
            return "\n".join(lines[-n_lines:])
        except OSError:
            return None

    def _check_unexpected_stop(self, key, svc, status):
        """방금 전까지 실행/시작 중이던 서비스가 (내가 중지 버튼을 누른 게 아닌데) 갑자기
        정지됨으로 바뀌면 — 대부분 MySQL 연결 실패 등으로 곧바로 종료된 경우다. 팝업으로
        방해하지 않고, 진단할 수 있게 로그 마지막 부분만 파일로 조용히 남겨둔다
        (launcher\\last_crash.log — 상태 점(빨강)이 이미 화면에 정지됨을 보여주므로
        그걸로 충분하고, 창을 따로 띄우면 아래 두 문제가 있었다: ① overrideredirect 창
        뒤에 숨어서 응답 대기 상태로 멈춘 것처럼 보임 ② 사용자가 직접 중지를 눌렀을 때와
        구분하기가 타이밍에 의존해 취약함)."""
        prev = self._last_status.get(key)
        if prev in (RUNNING, STARTING) and status == STOPPED:
            if self._intentional_stop.get(key):
                self._intentional_stop[key] = False
                return
            log_name = self.LOG_FILE_BY_KEY.get(key)
            if log_name:
                tail = self._tail_log(os.path.join(self.cfg.get("root_dir", ""), log_name))
                if tail:
                    try:
                        crash_log = os.path.join(paths.BASE_DIR, "last_crash.log")
                        with open(crash_log, "a", encoding="utf-8") as f:
                            f.write(f"\n=== {svc.display_name} 예상치 않은 종료 "
                                    f"({time.strftime('%Y-%m-%d %H:%M:%S')}) ===\n{tail}\n")
                    except OSError:
                        pass
        elif status in (RUNNING, STARTING):
            pass

    @staticmethod
    def _style_console_button(btn, key, active):
        """콘솔 보기(>_) 버튼을 지금 콘솔창이 실제로 열려있는지(active)에 따라 다른
        색으로 칠한다 — 클릭해도 버튼 모양이 그대로라 열었는지 닫았는지 헷갈리던 문제.
        버튼 위젯 자체(GradientButton)는 normal/hover 이미지를 갈아끼우는 방식만
        지원하므로, Play 버튼 상태 전환(_set_play_state)과 같은 방식으로 매 틱마다
        normal_img/hover_img 를 상태에 맞는 색으로 교체해둔다(gradient_photo 가 캐싱하므로
        매번 새로 그리는 비용은 없음)."""
        if active:
            top, bottom = theme.CONSOLE_ACTIVE_TOP, theme.CONSOLE_ACTIVE_BOTTOM
            border, hover_border = theme.CONSOLE_ACTIVE_BORDER, theme.CONSOLE_ACTIVE_HOVER_BORDER
            text, hover_text = theme.CONSOLE_ACTIVE_TEXT, theme.CONSOLE_ACTIVE_TEXT
        else:
            top, bottom = theme.ICON_TOP, theme.ICON_BOTTOM
            border, hover_border = theme.ICON_BORDER, theme.ICON_HOVER_BORDER
            text, hover_text = theme.ICON_TEXT, theme.ICON_TEXT
        suffix = "on" if active else "off"
        btn.normal_img = theme.gradient_photo(f"console-{key}-{suffix}-n", btn._bw, btn._bh,
                                               top, bottom, 3, border, 1)
        btn.hover_img = theme.gradient_photo(f"console-{key}-{suffix}-h", btn._bw, btn._bh,
                                              top, bottom, 3, hover_border, 1)
        btn.normal_text = text
        btn.hover_text = hover_text

    def refresh(self):
        # 실제 상태 확인(svc.status() 안의 포트 체크)은 백그라운드 스레드에서 한다.
        # 이 PC 에서는 닫힌 포트로 연결을 시도하면 즉시 거절되지 않고 소켓 타임아웃인
        # 최대 0.4초를 그대로 기다린다 — 그 확인을 메인 스레드에서 그대로 부르면
        # 서비스 3개 중 꺼져있는 게 많을수록 그만큼(최대 1.2초) 창 전체가 얼어붙어서,
        # 그 타이밍에 설정 창을 열거나 찾아보기 버튼을 누르면 반응이 늦거나 멈춘
        # 것처럼 느껴지는 원인이었다. 위젯 갱신만 root.after(0, ...) 로 메인 스레드에 넘긴다.
        #
        # 스레드는 1.5초마다 새로 만들지 않고, 앱이 켜져있는 동안 계속 도는 스레드
        # 하나만 써서(_refresh_loop) 반복적인 스레드 생성/정리 비용 자체를 없앤다 —
        # 매번 새 Thread 객체를 만드는 게 그 자체로 느려서라기보다, 백신 실시간 감시가
        # 새 스레드/네트워크 연결이 생길 때마다 검사에 끼어드는 경우가 있어 그 누적 비용을
        # 줄이기 위함이다.
        if not self._refresh_thread_started:
            self._refresh_thread_started = True
            threading.Thread(target=self._refresh_loop, daemon=True).start()

    def _refresh_loop(self):
        while True:
            self._refresh_worker()
            time.sleep(1.5)

    def _refresh_worker(self):
        results = {}
        for key, svc in self.services.items():
            pending = self.busy.get(key) or self.busy.get("all")
            busy = bool(pending)
            prev = self._last_status.get(key)
            if pending == "stop":
                status = STOPPING
            elif pending == "start":
                status = STARTING
            elif pending == "restart":
                status = STOPPING if svc.pid() else STARTING
            elif not busy and prev in (STOPPED, ERROR):
                # 이미 정지된 걸로 확인된 서비스는 사용자가 시작을 누르기 전까지
                # 저절로 켜질 리 없다 — 시작 버튼을 누르면 위의 pending=="start" 분기로
                # 바로 넘어가서 실제 확인이 다시 시작되므로, 그 전까지는 매 1.5초마다
                # 불필요하게 포트 접속을 시도하지 않는다(정지 상태에서는 확인 자체를
                # 안 함). 실행 중/시작 중이었던 서비스는 계속 실제로 확인해서 예상치
                # 않은 종료를 놓치지 않는다.
                status = STOPPED
            else:
                status = svc.status()
                self._check_unexpected_stop(key, svc, status)
            # busy(시작/중지/재시작 진행 중)일 때도 임시 상태(STARTING/STOPPING)를 계속
            # 기록해둬야, 중지가 끝난 다음 틱에 "직전 상태가 RUNNING이었다가 STOPPED로
            # 바뀜"으로 오인해서 방금 사용자가 직접 누른 중지를 "예상치 않은 종료"로
            # 잘못 알리는 버그가 안 생긴다.
            self._last_status[key] = status
            console_on = svc.console_visible() if status in (RUNNING, STARTING) else False
            results[key] = {"status": status, "busy": busy, "console_on": console_on}
        self.root.after(0, lambda: self._apply_refresh(results))

    def _apply_refresh(self, results):
        all_up = True
        # 원격 모드는 시작/중지/콘솔을 지원하지 않는다(RemoteServiceProcess.start/stop
        # 참고) - 버튼을 항상 비활성으로 둬서 눌러도 아무 일도 안 하게 한다.
        can_control = self.mode != "remote"
        for key, r in results.items():
            status, busy, console_on = r["status"], r["busy"], r["console_on"]
            if status != RUNNING:
                all_up = False

            # 메인 화면 상태 카드 — 시작/중지/콘솔 버튼이 카드에 바로 붙어있다.
            main_row = self.main_rows.get(key)
            if main_row is not None:
                main_row["dot"].set_status(status)
                main_row["canvas"].itemconfig(main_row["status_text_id"], text=STATUS_LABEL.get(status, status))
                main_row["btn_start"].set_enabled(can_control and not busy and status in (STOPPED, ERROR))
                main_row["btn_stop"].set_enabled(can_control and not busy and status in (RUNNING, STARTING))
                self._style_console_button(main_row["btn_console"], key, console_on)
                main_row["btn_console"].set_enabled(can_control and status in (RUNNING, STARTING))

        if hasattr(self, "btn_start_all"):
            self.btn_start_all.set_enabled(can_control)
            self.btn_stop_all.set_enabled(can_control)
        if hasattr(self, "btn_remote_check"):
            self.btn_remote_check.set_enabled(self.mode == "remote")
        self._update_mode_badge()

        self._set_play_state(all_up)

        if self.cfg.get("opt_stop_on_exit") and self._client_pid:
            if not psutil.pid_exists(self._client_pid):
                self._client_pid = None
                if not self.busy.get("all"):
                    self.run_action("all", "stop")

        self.root.after(1500, self.refresh)

    def _log_callback_exception(self, exc, val, tb):
        """Tkinter 콜백(버튼 클릭, after() 등) 안에서 예외가 나면 기본적으로 자체 오류창을
        띄우는데, 그게 오히려 원인을 알 수 없는 팝업으로 보여서 조용히 파일로만 남긴다."""
        try:
            import traceback
            log_path = os.path.join(paths.BASE_DIR, "error.log")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                traceback.print_exception(exc, val, tb, file=f)
        except Exception:
            pass

    def on_close(self):
        """X 버튼(또는 Alt+F4)을 누르면 바로 닫지 않고 먼저 물어본다 — 서버가 하나라도
        떠 있으면 실수로 창을 닫아서 저장 안 된 채로 서버까지 같이 죽는 걸 막기 위함.
        떠 있는 서버가 하나도 없으면 물어볼 필요가 없어 바로 닫는다."""
        if self._closing:
            return
        # 원격 모드는 런처를 닫아도 원격 서버에 아무 영향이 없으므로(로컬
        # 프로세스가 아님) "서버가 같이 죽는 걸 막는" 이 확인 자체가 의미 없다 -
        # 바로 닫는다.
        running = self.mode != "remote" and any(
            self._last_status.get(key) == RUNNING for key in self.services)
        if not running:
            self.root.destroy()
            return

        answer = ask_confirm(
            self.root, "종료 확인",
            "서버를 저장한 뒤 종료하시겠습니까?\n\n"
            "예 — 서버를 저장하고 모두 중지한 뒤 런처를 종료합니다.\n"
            "아니오 — 서버는 계속 실행한 채 작업표시줄로 최소화합니다.",
        )

        if answer:
            self._shutdown_and_exit()
        else:
            theme.minimize_window(self.root)

    def _shutdown_and_exit(self):
        """모두 중지(저장 포함)를 끝까지 기다렸다가 창을 닫는다 — 중지 스레드를
        daemon 으로 던져놓고 바로 destroy() 해버리면 mysql 등이 채 안 꺼진 채로
        프로세스가 죽어서 정상 종료 순서가 보장 안 될 수 있다."""
        self._closing = True
        for k in self.services:
            self._intentional_stop[k] = True
        self.busy["all"] = "stop"

        def worker():
            try:
                self._stop_all_sequenced()
            finally:
                self.busy["all"] = None
                self.root.after(0, self.root.destroy)

        threading.Thread(target=worker, daemon=True).start()

    def run(self):
        self.root.mainloop()


# ==================== SSH 키 도움말 창 ====================
class SshKeyHelpDialog(tk.Toplevel):
    """"원격 SSH 개인키 파일" 항목의 '?' 아이콘에서 여는 도움말 - 키를 어떻게
    만들고 원격 서버에 등록해야 런처가 비밀번호 없이 접속할 수 있는지 안내한다.
    런처는 비밀번호 입력을 지원하지 않으므로(설정 파일에 평문 저장하지 않기
    위해) SSH 키 등록이 원격 모드를 쓰기 위한 필수 절차다."""

    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        user = app.cfg.get("remote_ssh_user", "") or "사용자"
        host = app.cfg.get("remote_host", "") or "원격주소"
        port = str(app.cfg.get("remote_ssh_port", 22) or 22)
        target = f"{user}@{host}"
        port_flag = f"-p {port} " if port != "22" else ""
        self.STEPS = [
            ("1", "키 쌍 만들기",
             "명령 프롬프트나 PowerShell에서 아래 명령을 실행합니다. 'Enter passphrase' 라고"
             " 물어보면 암호 구문(패스프레이즈)을 입력하지 말고 그냥 Enter 를 두 번 누르세요 -"
             " 런처가 접속할 때마다 암호를 입력해줄 수는 없으니 이 키는 비워두는 걸 권장합니다"
             "(cmd 에서 -N \"\" 옵션으로 한 번에 비우려고 하면 빈 따옴표가 명령줄 끝에서"
             " 사라져 버려 'option requires an argument' 오류가 나니, 그냥 Enter로 넘기세요)."
             " 완료되면 개인키(wow_remote)와 공개키(wow_remote.pub) 두 파일이"
             " %USERPROFILE%\\.ssh\\ 안에 생깁니다.",
             'ssh-keygen -t ed25519 -f "%USERPROFILE%\\.ssh\\wow_remote"'),
            ("2", "공개키를 원격 서버에 등록",
             "아래 명령으로 방금 만든 공개키를 원격 서버의 ~/.ssh/authorized_keys 에 추가합니다."
             " 이번 한 번은 원격 서버 비밀번호를 직접 입력해서 접속해야 합니다. SSH 포트가"
             " 22번이 아니면 -p 옵션으로 따로 넘겨야 합니다 - host:port 처럼 주소에 콜론으로"
             " 붙이면 안 됩니다(그건 브라우저 주소 표기법이지 ssh 명령 문법이 아닙니다).",
             f'type "%USERPROFILE%\\.ssh\\wow_remote.pub" | ssh {port_flag}{target} "mkdir -p ~/.ssh '
             '&& cat >> ~/.ssh/authorized_keys"'),
            ("3", "접속 테스트",
             "아래 명령을 실행했을 때 비밀번호 입력 없이 바로 접속되면 성공입니다. 여기서"
             " 안 되면 런처에서도 안 됩니다 - 4번으로 넘어가기 전에 먼저 여기서 확인하세요.",
             f'ssh -i "%USERPROFILE%\\.ssh\\wow_remote" {port_flag}{target}'),
            ("4", "런처에 등록",
             "이 항목(SSH 개인키 파일)에 방금 만든 개인키 경로를 지정합니다 - 확장자가 .pub"
             "인 공개키가 아니라 그 반대쪽(예: C:\\Users\\사용자이름\\.ssh\\wow_remote)입니다."
             " 호스트/SSH 포트/SSH 사용자도 같이 채워야 접속됩니다.", None),
        ]
        self.TIPS = [
            ("Could not resolve hostname ...:포트번호",
             "ssh 명령에는 host:port 표기법이 없습니다 - 포트는 반드시 -p 250 처럼 따로"
             " 넘겨야 하고, 주소 뒤에 :250 을 붙이면 그 전체를(콜론까지) 호스트 이름으로"
             " 착각해서 이런 오류가 납니다. 위 명령들은 SSH 포트를 22가 아닌 값으로 설정"
             " 해두면 자동으로 -p 옵션을 붙여서 만들어집니다."),
            ("Permission denied (publickey)",
             "~/.ssh(700)와 authorized_keys(600)만 맞으면 된다고 생각하기 쉽지만, sshd는"
             " authorized_keys → .ssh → 홈 디렉터리까지 전부 훑어서 그룹/전체 쓰기 권한이"
             " 하나라도 있으면 키를 통째로 거부하고 조용히 비밀번호 인증으로 넘어갑니다."
             " chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys 로도 안 되면 홈"
             " 디렉터리 자체도 확인하세요: chmod 755 ~"),
            ("시놀로지(Synology) NAS인데 권한을 다 맞췄는데도 비밀번호를 물어봄",
             "시놀로지는 다중 프로토콜(SMB 등) 호환 때문에 사용자 홈 디렉터리 자체를 기본"
             " 777(전체 쓰기 가능)로 만들어두는 경우가 많습니다 - ls -la ~/.ssh 했을 때 .. 줄"
             "(홈 디렉터리)이 drwxrwxrwx 로 보이면 이게 원인입니다. ssh 로 접속해서"
             " chmod 755 ~ (또는 실제 홈 경로, 예: /var/services/homes/xbox) 를 실행하면"
             " 보통 바로 해결됩니다. 그래도 안 되면 ACL이 덮어쓰고 있는 것이니"
             " synoacltool -del ~ 로 ACL을 지운 뒤 다시 chmod 755 ~ 를 실행해 보세요."),
            ("비밀번호를 계속 물어봄",
             "키를 만들 때 암호 구문(패스프레이즈)을 입력했다면 접속할 때마다 물어봅니다."
             " 런처 전용 키는 1번 단계처럼 물어볼 때 그냥 Enter 를 눌러 패스프레이즈 없이"
             " 새로 만드세요."),
            ("'ssh'은(는) 내부 또는 외부 명령이 아닙니다",
             "Windows 10 1809 이상엔 OpenSSH 클라이언트가 기본 포함돼 있습니다. 없다면"
             " 설정 > 앱 > 선택적 기능에서 \"OpenSSH 클라이언트\"를 추가하세요."),
        ]

        self.title("SSH 키 도움말")
        self.configure(bg="#0d1a26")
        center_on_screen(self, 600, 660)
        self.resizable(False, True)
        self.transient(app.root)
        self.grab_set()

        outer = tk.Frame(self, bg="#0d1a26")
        outer.pack(fill="both", expand=True, padx=20, pady=18)

        tk.Label(outer, text="SSH 키 생성 및 설정 방법", bg="#0d1a26", fg=theme.HEADER_TEXT,
                  font=theme.korean(15, "bold"), anchor="w").pack(fill="x", pady=(0, 4))
        tk.Label(outer,
                  text="런처는 비밀번호 저장 없이 SSH 키로만 원격 서버에 접속합니다. 아래"
                       " 순서대로 한 번만 준비해두면 됩니다.",
                  bg="#0d1a26", fg=theme.TEXT_MUTED3, font=theme.korean(10),
                  anchor="w", justify="left", wraplength=560).pack(fill="x", pady=(0, 10))
        tk.Frame(outer, bg=theme.HEADER_BORDER, height=1).pack(fill="x", pady=(0, 10))

        canvas = tk.Canvas(outer, bg="#0d1a26", highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        body = tk.Frame(canvas, bg="#0d1a26")
        body_win = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(body_win, width=e.width))

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        self.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        for num, title, desc, cmd in self.STEPS:
            row = tk.Frame(body, bg="#0d1a26")
            row.pack(fill="x", pady=8)
            badge = tk.Canvas(row, width=26, height=26, bg="#0d1a26", highlightthickness=0)
            badge.pack(side="left", anchor="n")
            img = theme.gradient_photo(f"sshhelp-badge-{num}", 26, 26, theme.START_TOP, theme.START_BOTTOM,
                                        13, theme.START_BORDER)
            badge.create_image(0, 0, image=img, anchor="nw")
            badge.image = img
            badge.create_text(13, 13, text=num, font=theme.korean(12, "bold"), fill=theme.START_TEXT)
            txt = tk.Frame(row, bg="#0d1a26")
            txt.pack(side="left", fill="x", expand=True, padx=(12, 0))
            tk.Label(txt, text=title, bg="#0d1a26", fg="#dbe6f3", font=theme.korean(13, "bold"),
                      anchor="w").pack(fill="x")
            tk.Label(txt, text=desc, bg="#0d1a26", fg=theme.TEXT_MUTED3, font=theme.korean(11),
                      anchor="w", justify="left", wraplength=480).pack(fill="x", pady=(2, 0))
            if cmd:
                cmd_row = tk.Frame(txt, bg="#0e1c28", highlightthickness=1,
                                    highlightbackground=theme.ROW_BORDER)
                cmd_row.pack(fill="x", pady=(6, 0))
                tk.Label(cmd_row, text=cmd, bg="#0e1c28", fg=theme.START_TEXT,
                          font=theme.mono(10), anchor="w", justify="left",
                          wraplength=390).pack(side="left", fill="x", expand=True, padx=8, pady=6)
                GradientButton(
                    cmd_row, "복사", lambda c=cmd: self._copy(c), 50, 24,
                    theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
                    hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
                    font=theme.korean(10, "bold"), radius=3, container_bg="#0e1c28",
                    key=f"sshhelp-copy-{num}", tooltip="명령 복사",
                ).pack(side="right", padx=6, pady=6)

        tk.Label(body, text="문제 해결", bg="#0d1a26", fg=theme.HEADER_TEXT,
                  font=theme.korean(13, "bold"), anchor="w").pack(fill="x", pady=(14, 8))
        tk.Frame(body, bg=theme.HEADER_BORDER, height=1).pack(fill="x", pady=(0, 10))
        for title, desc in self.TIPS:
            card = tk.Frame(body, bg="#0e1c28", highlightthickness=1, highlightbackground=theme.ROW_BORDER)
            card.pack(fill="x", pady=4)
            inner = tk.Frame(card, bg="#0e1c28")
            inner.pack(fill="x", padx=12, pady=9)
            tk.Label(inner, text=title, bg="#0e1c28", fg=theme.START_TEXT, font=theme.korean(11, "bold"),
                      anchor="w", justify="left", wraplength=540).pack(fill="x")
            tk.Label(inner, text=desc, bg="#0e1c28", fg=theme.TEXT_MUTED3, font=theme.korean(10),
                      anchor="w", justify="left", wraplength=540).pack(fill="x", pady=(3, 0))

        footer = tk.Frame(self, bg="#0d1a26")
        footer.pack(fill="x", padx=20, pady=(0, 18))
        close_btn = GradientButton(
            footer, "닫기", self.destroy, 90, 32,
            theme.START_TOP, theme.START_BOTTOM, theme.START_BORDER, theme.START_TEXT,
            hover_border=theme.START_HOVER_BORDER, hover_text_color=theme.START_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="sshhelp-close",
        )
        close_btn.pack(side="right")

    def _copy(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()


# ==================== 설정 창 ====================
SETTINGS_FILETYPES = [("실행/배치 파일", "*.exe;*.bat"), ("모든 파일", "*.*")]


class SettingsDialog(tk.Toplevel):
    UI_FONT_DEFAULT_LABEL = "시스템 기본 (맑은 고딕)"

    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("설정")
        self.configure(bg="#0d1a26")
        self._dlg_w = 1180
        center_on_screen(self, self._dlg_w, 600)
        self.resizable(False, False)
        self.transient(app.root)
        self.grab_set()

        body = tk.Frame(self, bg="#0d1a26", width=self._dlg_w, height=600)
        body.pack(fill="both", expand=True)

        self.vars = {}
        # 렐름리스트 주소 목록(최대 5개) - "저장"을 눌러야 self.app.cfg 에 반영되는
        # 작업용 사본. 개별 주소를 콤보박스로 고르는 값(활성 주소)은 다른 필드들과
        # 똑같이 self.vars 에 담아 범용 저장 루프를 그대로 타게 하지만, 목록
        # 자체는 위젯 하나로 표현이 안 되니 따로 들고 있는다.
        self.realmlist_addrs = list(self.app.cfg.get("realmlist_list") or ["127.0.0.1"])
        self._setup_dark_combobox_style()

        # 버튼 줄(기본값으로/취소/저장)을 먼저 만들어서 맨 아래에 자리를 고정해
        # 둔다 - Tk pack 은 "먼저 자리를 차지한 쪽이 우선"이라, expand=True 인
        # 사이드바+콘텐츠 영역보다 먼저 pack 해둬야 맨 아래 줄이 안 밀려난다.
        # 실제 버튼들은 지금까지와 같은 위치(파일 맨 끝, 모든 필드를 만든 뒤)에서
        # 이 btns 프레임에 채워 넣는다.
        btns = tk.Frame(body, bg="#0d1a26")
        btns.pack(side="bottom", fill="x", padx=16, pady=20)

        top_row = tk.Frame(body, bg="#0d1a26")
        top_row.pack(side="top", fill="both", expand=True)

        # 왼쪽 고정폭 사이드바(서버 목록, on/off 토글로 선택) 먼저 pack 해서
        # 자리를 잡아두고, 오른쪽 콘텐츠(지금까지의 모드탭+3열 설정 항목)가
        # 남은 공간을 fill+expand 로 채우게 한다.
        sidebar = tk.Frame(top_row, bg="#0e1c28", width=220,
                            highlightthickness=1, highlightbackground=theme.HEADER_BORDER)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self._build_settings_sidebar(sidebar)

        content = tk.Frame(top_row, bg="#0d1a26")
        content.pack(side="left", fill="both", expand=True)

        def section(parent, title):
            tk.Label(parent, text=title, bg="#0d1a26", fg=theme.HEADER_TEXT,
                      font=theme.korean(14, "bold"), anchor="w").pack(fill="x", pady=(0, 6))
            tk.Frame(parent, bg=theme.HEADER_BORDER, height=1).pack(fill="x")

        def entry_row(parent, label, key, show=None):
            wrap = tk.Frame(parent, bg="#0d1a26")
            wrap.pack(fill="x", pady=(10, 0))
            tk.Label(wrap, text=label, bg="#0d1a26", fg=theme.LABEL_MUTED,
                      font=theme.korean(11), anchor="w").pack(fill="x")
            var = tk.StringVar(value=str(self.app.cfg.get(key, "")))
            self.vars[key] = var
            tk.Entry(wrap, textvariable=var, bg=theme.INPUT_BG, fg=theme.INPUT_TEXT,
                      insertbackground=theme.INPUT_TEXT, relief="flat",
                      highlightthickness=1, highlightbackground=theme.INPUT_BORDER,
                      font=theme.mono(11), show=show).pack(fill="x", ipady=4, pady=(3, 0))
            return wrap

        def path_row(parent, label, key, help_cb=None):
            wrap = tk.Frame(parent, bg="#0d1a26")
            wrap.pack(fill="x", pady=(10, 0))
            label_row = tk.Frame(wrap, bg="#0d1a26")
            label_row.pack(fill="x")
            tk.Label(label_row, text=label, bg="#0d1a26", fg=theme.LABEL_MUTED,
                      font=theme.korean(11), anchor="w").pack(side="left")
            if help_cb:
                help_badge = tk.Canvas(label_row, width=16, height=16, bg="#0d1a26",
                                        highlightthickness=0, cursor="hand2")
                help_badge.pack(side="left", padx=(5, 0))
                help_img = theme.gradient_photo(f"help-badge-{key}", 16, 16, theme.START_TOP,
                                                 theme.START_BOTTOM, 8, theme.START_BORDER)
                help_badge.image = help_img
                help_badge.create_image(0, 0, image=help_img, anchor="nw")
                help_badge.create_text(8, 8, text="?", font=theme.korean(9, "bold"), fill=theme.START_TEXT)
                help_badge.bind("<Button-1>", lambda e: help_cb())
                Tooltip(help_badge, "SSH 키 생성 및 설정 방법 보기")
            row = tk.Frame(wrap, bg="#0d1a26")
            row.pack(fill="x", pady=(3, 0))
            var = tk.StringVar(value=str(self.app.cfg.get(key, "")))
            self.vars[key] = var
            tk.Entry(row, textvariable=var, bg=theme.INPUT_BG, fg=theme.INPUT_TEXT,
                      insertbackground=theme.INPUT_TEXT, relief="flat",
                      highlightthickness=1, highlightbackground=theme.INPUT_BORDER,
                      font=theme.mono(10)).pack(side="left", fill="x", expand=True, ipady=4)
            browse = GradientButton(
                row, "...", lambda k=key: self._browse(k), 30, 26,
                theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
                hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
                font=theme.korean(11, "bold"), radius=3, container_bg="#0d1a26", key=f"browse-{key}",
                tooltip="파일 찾아보기",
            )
            browse.pack(side="left", padx=(6, 0))
            return wrap

        TOGGLE_TOOLTIPS = {
            "opt_autostart": "런처를 열면 MySQL → 인증 서버 → 월드 서버를 자동으로 순서대로 켭니다.",
            "opt_show_console": "서버들을 켤 때 콘솔 창을 처음부터 보이게 시작합니다 (평소엔 숨김).",
            "opt_stop_on_exit": "Play 로 실행한 WoW 클라이언트가 종료되면 서버 3개를 자동으로 내립니다.",
        }

        def toggle_row(parent, label, key):
            row = tk.Frame(parent, bg="#0d1a26")
            row.pack(fill="x", pady=(10, 0))
            tk.Label(row, text=label, bg="#0d1a26", fg=theme.LABEL_MUTED,
                      font=theme.korean(11), anchor="w", wraplength=160, justify="left").pack(side="left")
            sw = ToggleSwitch(row, value=bool(self.app.cfg.get(key)), container_bg="#0d1a26",
                               tooltip=TOGGLE_TOOLTIPS.get(key))
            sw.pack(side="right")
            self.vars[key] = sw

        def font_row(parent, label, key):
            wrap = tk.Frame(parent, bg="#0d1a26")
            wrap.pack(fill="x", pady=(10, 0))
            tk.Label(wrap, text=label, bg="#0d1a26", fg=theme.LABEL_MUTED,
                      font=theme.korean(11), anchor="w").pack(fill="x")
            values = [self.UI_FONT_DEFAULT_LABEL] + theme.list_local_fonts()
            var = tk.StringVar()
            current = self.app.cfg.get(key, "")
            var.set(current if current in values else self.UI_FONT_DEFAULT_LABEL)
            self.vars[key] = var
            combo = ttk.Combobox(wrap, textvariable=var, values=values, state="readonly",
                                  style="Dark.TCombobox", font=theme.korean(11))
            combo.pack(fill="x", ipady=2, pady=(3, 0))
            tk.Label(wrap, text="한글이 없는 폰트를 고르면 한글 글자는 시스템 기본 폰트로 대신 표시됩니다.",
                      bg="#0d1a26", fg=theme.TEXT_MUTED3, font=theme.korean(9),
                      anchor="w", justify="left", wraplength=260).pack(fill="x", pady=(3, 0))
            return wrap

        def realmlist_row(parent, label, key):
            wrap = tk.Frame(parent, bg="#0d1a26")
            wrap.pack(fill="x", pady=(14, 0))
            tk.Label(wrap, text=label, bg="#0d1a26", fg=theme.LABEL_MUTED,
                      font=theme.korean(11), anchor="w").pack(fill="x")

            row = tk.Frame(wrap, bg="#0d1a26")
            row.pack(fill="x", pady=(3, 0))

            var = tk.StringVar()
            active = self.app.cfg.get(key, "127.0.0.1")
            var.set(active if active in self.realmlist_addrs else self.realmlist_addrs[0])
            self.vars[key] = var
            combo = ttk.Combobox(row, textvariable=var, values=self.realmlist_addrs,
                                  state="readonly", style="Dark.TCombobox", font=theme.mono(11))
            combo.pack(side="left", fill="x", expand=True, ipady=2)

            def add_addr():
                if len(self.realmlist_addrs) >= 5:
                    alert(self, "렐름리스트", "최대 5개까지 등록할 수 있습니다.")
                    return
                new_addr = ask_string(self, "렐름리스트 추가",
                                       "새 서버 주소를 입력하세요 (예: 127.0.0.1 또는 mydomain.com):")
                if not new_addr or not new_addr.strip():
                    return
                new_addr = new_addr.strip()
                if new_addr not in self.realmlist_addrs:
                    self.realmlist_addrs.append(new_addr)
                    combo.config(values=self.realmlist_addrs)
                var.set(new_addr)

            def remove_addr():
                current = var.get()
                if current not in self.realmlist_addrs:
                    return
                if len(self.realmlist_addrs) <= 1:
                    alert(self, "렐름리스트", "최소 1개는 남아있어야 합니다.")
                    return
                self.realmlist_addrs.remove(current)
                combo.config(values=self.realmlist_addrs)
                var.set(self.realmlist_addrs[0])

            GradientButton(
                row, "+", add_addr, 30, 26,
                theme.START_TOP, theme.START_BOTTOM, theme.START_BORDER, theme.START_TEXT,
                hover_border=theme.START_HOVER_BORDER, hover_text_color=theme.START_HOVER_TEXT,
                font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="realmlist-add",
                tooltip="주소 추가 (최대 5개)",
            ).pack(side="left", padx=(6, 0))
            GradientButton(
                row, "-", remove_addr, 30, 26,
                theme.STOP_TOP, theme.STOP_BOTTOM, theme.STOP_BORDER, theme.STOP_TEXT,
                hover_border=theme.STOP_HOVER_BORDER, hover_text_color=theme.STOP_HOVER_TEXT,
                font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="realmlist-remove",
                tooltip="선택한 주소 삭제",
            ).pack(side="left", padx=(6, 0))
            return wrap

        def two_columns(parent):
            row = tk.Frame(parent, bg="#0d1a26")
            row.pack(fill="x", pady=(18, 0))
            left = tk.Frame(row, bg="#0d1a26")
            left.pack(side="left", fill="both", expand=True, padx=(16, 8))
            right = tk.Frame(row, bg="#0d1a26")
            right.pack(side="left", fill="both", expand=True, padx=(8, 16))
            return left, right

        def three_columns(parent):
            row = tk.Frame(parent, bg="#0d1a26")
            row.pack(fill="x", pady=(18, 0))
            left = tk.Frame(row, bg="#0d1a26")
            left.pack(side="left", fill="both", expand=True, padx=(16, 8))
            mid = tk.Frame(row, bg="#0d1a26")
            mid.pack(side="left", fill="both", expand=True, padx=8)
            right = tk.Frame(row, bg="#0d1a26")
            right.pack(side="left", fill="both", expand=True, padx=(8, 16))
            return left, mid, right

        # "모드" 를 진짜 탭처럼 만든다(게임 설정 창의 탭과 같은 방식) - 로컬/원격
        # 전용 필드만 탭 콘텐츠 안에서 바뀌고, 나머지(클라이언트/렐름리스트/GM계정/
        # 화면/실행옵션)는 항상 그대로 보여서 탭을 바꿔도 창 높이가 크게 안 흔들린다.
        # (예전엔 로컬 항목 위에 원격 항목을 통째로 더 쌓는 식이라 원격을 고르면
        # 창이 세로로 아주 길어지는 문제가 있었음.)
        mode_tab_row = tk.Frame(content, bg="#0d1a26")
        mode_tab_row.pack(fill="x", padx=16, pady=(16, 0))
        self.mode = self.app.cfg.get("mode", "local")
        self.mode_radios = {}

        def radio_option(parent, label, value):
            row = tk.Frame(parent, bg="#0d1a26", cursor="hand2")
            row.pack(side="left", padx=(0, 24))
            dot = tk.Canvas(row, width=18, height=18, bg="#0d1a26", highlightthickness=0)
            dot.pack(side="left")
            ring_id = dot.create_oval(2, 2, 16, 16, outline=theme.BROWSE_BORDER, width=2)
            fill_id = dot.create_oval(5, 5, 13, 13, fill="", outline="")
            lbl = tk.Label(row, text=label, bg="#0d1a26", fg=theme.BROWSE_TEXT, font=theme.korean(12, "bold"))
            lbl.pack(side="left", padx=(6, 0))
            for w in (row, dot, lbl):
                w.bind("<Button-1>", lambda e, v=value: self._select_mode(v))
            self.mode_radios[value] = (dot, ring_id, fill_id, lbl)

        radio_option(mode_tab_row, "로컬 모드", "local")
        radio_option(mode_tab_row, "원격 모드", "remote")
        tk.Frame(content, bg=theme.HEADER_BORDER, height=1).pack(fill="x", padx=16, pady=(10, 0))

        # 3열 배치: 1열(모드별 정보) · 2열(클라이언트/렐름리스트/GM계정) ·
        # 3열(화면/실행옵션). 예전엔 모드별 정보 한 줄, 클라이언트/화면 한 줄
        # 이렇게 2단짜리 줄이 두 번 세로로 쌓여서 창이 세로로 아주 길었는데,
        # 가로로 넓혀서 한 줄에 나란히 배치했다.
        col_mode, col_client, col_options = three_columns(content)

        self.mode_tab_content = tk.Frame(col_mode, bg="#0d1a26")
        self.mode_tab_content.pack(fill="both", expand=True)

        # 로컬/원격 프레임은 이제 내부에서 two_columns() 로 또 나누지 않고
        # (한 열 폭 안에서 2단으로 쪼개면 너무 좁아짐), 섹션들을 위아래로
        # 그냥 순서대로 쌓는다 - 필드 자체는 예전 2단 배치의 한쪽 칸과
        # 폭이 거의 같아서(예전: 640폭의 절반 절반, 지금: 960폭의 1/3 한 칸)
        # entry_row/path_row 안쪽 위젯은 그대로 재사용해도 크기가 맞는다.
        self.local_path_frame = tk.Frame(self.mode_tab_content, bg="#0d1a26")
        section(self.local_path_frame, "데이터베이스")
        entry_row(self.local_path_frame, "MySQL 호스트", "mysql_host")
        entry_row(self.local_path_frame, "포트", "mysql_port")
        entry_row(self.local_path_frame, "사용자", "db_user")
        entry_row(self.local_path_frame, "비밀번호", "db_password", show="*")
        tk.Frame(self.local_path_frame, bg="#0d1a26", height=14).pack(fill="x")
        section(self.local_path_frame, "서버 경로")
        path_row(self.local_path_frame, "MySQL 실행파일", "mysqld_exe")
        path_row(self.local_path_frame, "인증 서버", "authserver_exe")
        path_row(self.local_path_frame, "월드 서버", "worldserver_exe")

        self.remote_frame = tk.Frame(self.mode_tab_content, bg="#0d1a26")
        section(self.remote_frame, "원격 접속 정보 (SSH)")
        entry_row(self.remote_frame, "호스트", "remote_host")
        entry_row(self.remote_frame, "SSH 포트", "remote_ssh_port")
        entry_row(self.remote_frame, "SSH 사용자", "remote_ssh_user")
        path_row(self.remote_frame, "SSH 개인키 파일", "remote_ssh_key_path",
                 help_cb=lambda: SshKeyHelpDialog(self.app))
        tk.Frame(self.remote_frame, bg="#0d1a26", height=14).pack(fill="x")
        section(self.remote_frame, "원격 conf 경로")
        entry_row(self.remote_frame, "원격 worldserver.conf 경로", "remote_worldserver_conf_path")
        entry_row(self.remote_frame, "원격 authserver.conf 경로 (선택)", "remote_authserver_conf_path")
        tk.Frame(self.remote_frame, bg="#0d1a26", height=14).pack(fill="x")
        section(self.remote_frame, "백업 / 복원")
        entry_row(self.remote_frame, "원격 배포 폴더 (docker-compose.yml 위치)", "remote_deploy_dir")
        tk.Label(self.remote_frame, text="계정/캐릭터 백업·복원(scripts/backup.sh, restore.sh)이 있는 "
                                          "폴더 경로입니다. \"서버 관리\"에서 이 서버의 \"백업/복원\" "
                                          "버튼으로 실행할 수 있습니다.",
                  bg="#0d1a26", fg=theme.TEXT_MUTED3, font=theme.korean(9),
                  anchor="w", justify="left", wraplength=280).pack(fill="x", pady=(6, 0))
        tk.Label(self.remote_frame, text="비밀번호 대신 SSH 키 인증만 지원합니다. 시작/중지는 "
                                          "지원하지 않고 상태 확인·게임 설정·계정 관리만 가능합니다. "
                                          "클라이언트가 이 서버로 접속하려면 옆의 렐름리스트에도 이 "
                                          "호스트 주소를 등록하세요.",
                  bg="#0d1a26", fg=theme.TEXT_MUTED3, font=theme.korean(9),
                  anchor="w", justify="left", wraplength=280).pack(fill="x", pady=(10, 0))

        # 이 열 자체가 이제 폭 ~300px 짜리 한 칸이라(예전엔 remote_frame 전체
        # 폭 ~600px 안에서 상태문구+버튼을 가로로 나란히 뒀음), 버튼을 문구
        # 오른쪽이 아니라 아래로 내려서 좁은 폭에서도 안 눌리게 했다.
        test_wrap = tk.Frame(self.remote_frame, bg="#0d1a26")
        test_wrap.pack(fill="x", pady=(14, 0))
        self._remote_test_status = tk.StringVar(value="")
        self._remote_test_status_label = tk.Label(
            test_wrap, textvariable=self._remote_test_status, bg="#0d1a26",
            fg=theme.TEXT_MUTED3, font=theme.korean(10, "bold"), anchor="w", justify="left",
            wraplength=280)
        self._remote_test_status_label.pack(fill="x")
        self._remote_test_btn = GradientButton(
            test_wrap, "연결 테스트", self._run_remote_test, 120, 30,
            theme.START_TOP, theme.START_BOTTOM, theme.START_BORDER, theme.START_TEXT,
            hover_border=theme.START_HOVER_BORDER, hover_text_color=theme.START_HOVER_TEXT,
            font=theme.korean(11, "bold"), radius=3, container_bg="#0d1a26", key="remote-test",
            tooltip="SSH 접속과 worldserver.conf 읽기를 지금 입력한 값으로 확인합니다",
        )
        self._remote_test_btn.pack(anchor="w", pady=(6, 0))

        section(col_client, "클라이언트")
        path_row(col_client, "실행 파일", "wow_client_exe")

        tk.Frame(col_client, bg="#0d1a26", height=18).pack(fill="x")
        realmlist_row(col_client, "렐름리스트 (클라이언트 접속 주소, 최대 5개)", "realmlist_active")

        tk.Frame(col_client, bg="#0d1a26", height=18).pack(fill="x")
        section(col_client, "GM 계정")
        entry_row(col_client, "GM 계정", "gm_account")
        entry_row(col_client, "GM 비밀번호", "gm_password", show="*")
        entry_row(col_client, "온라인 계정 표시수", "online_list_limit")

        section(col_options, "화면")
        font_row(col_options, "폰트 (assets/fonts 폴더에서 찾은 폰트)", "ui_font")

        tk.Frame(col_options, bg="#0d1a26", height=18).pack(fill="x")
        section(col_options, "실행 옵션")
        toggle_row(col_options, "런처 실행 시 자동 시작", "opt_autostart")
        toggle_row(col_options, "서버 콘솔 창 표시", "opt_show_console")
        toggle_row(col_options, "게임 종료 시 서버 중지", "opt_stop_on_exit")

        reset_btn = GradientButton(
            btns, "기본값으로", self._reset_defaults, 100, 32,
            theme.STOP_TOP, theme.STOP_BOTTOM, theme.STOP_BORDER, theme.STOP_TEXT,
            hover_border=theme.STOP_HOVER_BORDER, hover_text_color=theme.STOP_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="reset",
        )
        reset_btn.pack(side="left")
        save_btn = GradientButton(
            btns, "저장", self._save, 90, 32,
            theme.START_TOP, theme.START_BOTTOM, theme.START_BORDER, theme.START_TEXT,
            hover_border=theme.START_HOVER_BORDER, hover_text_color=theme.START_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="save",
        )
        save_btn.pack(side="right")
        cancel_btn = GradientButton(
            btns, "취소", self.destroy, 90, 32,
            theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
            hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="cancel",
        )
        cancel_btn.pack(side="right", padx=(0, 8))

        # 모든 섹션(모드별 필드 + 클라이언트/GM계정/화면/실행옵션 + 버튼줄)이 다
        # 만들어진 뒤에 초기 모드를 적용해야, 그 시점에 필요한 창 높이를 정확히
        # 잴 수 있다(이보다 일찍 하면 아직 안 만들어진 아래쪽 섹션들 높이가
        # 반영이 안 돼서 창이 잘려 보임).
        self._select_mode(self.mode)

    DEFAULTS = {
        "db_user": "root",
        "db_password": "",
        "mysqld_exe": "",
        "authserver_exe": "",
        "worldserver_exe": "",
        "wow_client_exe": "",
    }

    def _reset_defaults(self):
        for key, value in self.DEFAULTS.items():
            self.vars[key].set(value)

    # ---------------- 모드(로컬/원격) ----------------
    def _select_mode(self, m):
        self.mode = m
        for mval, (dot, ring_id, fill_id, lbl) in self.mode_radios.items():
            active = mval == m
            dot.itemconfig(ring_id, outline=theme.START_BORDER if active else theme.BROWSE_BORDER)
            dot.itemconfig(fill_id, fill=theme.START_BORDER if active else "")
            lbl.config(fg=theme.START_TEXT if active else theme.BROWSE_TEXT)
        if m == "remote":
            self.local_path_frame.pack_forget()
            self.remote_frame.pack(fill="x")
        else:
            self.remote_frame.pack_forget()
            self.local_path_frame.pack(fill="x")
        # 로컬/원격 필드 수가 달라서 필요한 창 높이도 다르다 - 매번 실제 필요한
        # 높이를 재서 다시 가운데 정렬(창 크기를 고정폭으로 미리 크게 잡아두면
        # 로컬 모드일 때 아래쪽이 휑하게 비어 보여서, 모드에 맞게 딱 맞춘다).
        self.update_idletasks()
        needed_h = self.winfo_reqheight() + 20
        center_on_screen(self, self._dlg_w, needed_h)

    # ---------------- 프리셋(설정값 여러 개 저장/불러오기) ----------------
    def _setup_dark_combobox_style(self):
        """콤보박스(서버 목록/폰트/렐름리스트/원격 모드에 쓰는 InstantFlightPaths
        등)를 어두운 테마에 맞게 칠하는 ttk 스타일 - 여러 콤보박스가 공유하므로
        한 번만 설정해둔다."""
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Dark.TCombobox",
                         fieldbackground=theme.INPUT_BG, background=theme.INPUT_BG,
                         foreground=theme.INPUT_TEXT, arrowcolor=theme.LABEL_MUTED,
                         bordercolor=theme.INPUT_BORDER, selectbackground=theme.INPUT_BG,
                         selectforeground=theme.INPUT_TEXT)
        style.map("Dark.TCombobox",
                  fieldbackground=[("readonly", theme.INPUT_BG)],
                  foreground=[("readonly", theme.INPUT_TEXT)])
        self.option_add("*TCombobox*Listbox.background", theme.INPUT_BG)
        self.option_add("*TCombobox*Listbox.foreground", theme.INPUT_TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", theme.START_BORDER)
        self.option_add("*TCombobox*Listbox.selectForeground", theme.START_HOVER_TEXT)

    def _build_settings_sidebar(self, parent):
        """왼쪽 사이드바 - 서버 목록을 보여주고, 각 행의 on/off 토글로 "지금
        편집할 서버"를 고른다(정확히 하나만 켜져 있어야 하므로, 이미 켜진
        행을 끄려고 하면 바로 되돌리고, 다른 행을 켜면 그 서버로 전환한 뒤
        창을 다시 연다 - 필드를 하나씩 다시 채우는 것보다 통째로 다시 만드는
        `_on_server_changed()` 와 같은 방식이 실수 없이 확실하다). 추가(+)는
        헤더에, 수정(✎)/삭제(✕)는 각 행에 아이콘으로 바로 붙어있다 - 이 목록만
        보려고 별도로 `ServerManageDialog` 를 여는 과정을 없애기 위함(그
        다이얼로그 자체는 메인 화면 ☰ 드롭다운/배지 클릭에서는 계속 쓰인다)."""
        header = tk.Frame(parent, bg="#0e1c28")
        header.pack(fill="x", padx=14, pady=(14, 8))
        tk.Label(header, text="서버 목록", bg="#0e1c28", fg=theme.HEADER_TEXT,
                  font=theme.korean(13, "bold"), anchor="w").pack(side="left")
        GradientButton(
            header, "+", self._sidebar_add_server, 24, 24,
            theme.START_TOP, theme.START_BOTTOM, theme.START_BORDER, theme.START_TEXT,
            hover_border=theme.START_HOVER_BORDER, hover_text_color=theme.START_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=4, container_bg="#0e1c28", key="sidebar-server-add",
            tooltip="서버 추가",
        ).pack(side="right")

        self.sidebar_rows_frame = tk.Frame(parent, bg="#0e1c28")
        self.sidebar_rows_frame.pack(fill="both", expand=True, padx=10)
        self._refresh_sidebar_rows()

        tk.Label(parent, text="전환하면 저장하지 않은 변경사항은 사라집니다.",
                  bg="#0e1c28", fg=theme.TEXT_MUTED3, font=theme.korean(8),
                  anchor="w", justify="left", wraplength=190).pack(fill="x", padx=14, pady=(4, 14))

    def _refresh_sidebar_rows(self):
        for w in self.sidebar_rows_frame.winfo_children():
            w.destroy()
        self._sidebar_switches = []
        servers = self.app.cfg.get("servers") or []
        active_id = self.app.cfg.get("active_server_id")
        for server in servers:
            is_active = server.get("id") == active_id
            row_bg = "#17293b" if is_active else "#0e1c28"
            row = tk.Frame(self.sidebar_rows_frame, bg=row_bg, highlightthickness=1,
                            highlightbackground=theme.START_BORDER if is_active else "#0e1c28")
            row.pack(fill="x", pady=(0, 6))
            inner = tk.Frame(row, bg=row_bg)
            inner.pack(fill="x", padx=10, pady=8)

            switch = ToggleSwitch(inner, value=is_active, container_bg=row_bg,
                                   tooltip="이 서버로 전환" if not is_active else "지금 편집 중")
            switch.pack(side="right")
            switch.command = lambda v, s=server, sw=switch: self._on_sidebar_toggle(s, v, sw)
            switch.server_id = server.get("id")
            self._sidebar_switches.append(switch)

            icon_col = tk.Frame(inner, bg=row_bg)
            icon_col.pack(side="right", padx=(0, 6))
            GradientButton(
                icon_col, "✕", lambda s=server: self._sidebar_delete_server(s), 22, 22,
                theme.STOP_TOP, theme.STOP_BOTTOM, theme.STOP_BORDER, theme.STOP_TEXT,
                hover_border=theme.STOP_HOVER_BORDER, hover_text_color=theme.STOP_HOVER_TEXT,
                font=theme.korean(10, "bold"), radius=4, container_bg=row_bg, key=f"sidebar-delete-{server['id']}",
                tooltip="서버 삭제",
            ).pack(side="right", padx=(3, 0))
            GradientButton(
                icon_col, "✎", lambda s=server: self._sidebar_edit_server(s), 22, 22,
                theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
                hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
                font=theme.korean(10, "bold"), radius=4, container_bg=row_bg, key=f"sidebar-edit-{server['id']}",
                tooltip="이름/환경 수정",
            ).pack(side="right")

            text_col = tk.Frame(inner, bg=row_bg)
            text_col.pack(side="left", fill="x", expand=True)
            tk.Label(text_col, text=server.get("name", "서버"), bg=row_bg, fg=theme.BODY_TEXT,
                      font=theme.korean(11, "bold"), anchor="w").pack(fill="x")
            pack_name = server.get("pack_name", "").strip()
            if pack_name:
                tk.Label(text_col, text=pack_name, bg=row_bg, fg=theme.TEXT_MUTED3,
                          font=theme.korean(9), anchor="w").pack(fill="x")
            tag = "원격" if server.get("mode") == "remote" else "로컬"
            tk.Label(text_col, text=f"[{tag}]", bg=row_bg, fg=theme.TEXT_MUTED3,
                      font=theme.korean(9), anchor="w").pack(fill="x")

    def _sidebar_add_server(self):
        name = ask_string(self, "서버 추가", "새 서버 이름을 입력하세요:")
        if not name or not name.strip():
            return
        new_entry = config_store.new_server(name.strip())
        servers = list(self.app.cfg.get("servers") or [])
        servers.append(new_entry)
        self.app.cfg["servers"] = servers
        self.app.switch_to_server(new_entry)
        self.destroy()
        SettingsDialog(self.app)

    def _sidebar_edit_server(self, server):
        def on_saved(_s):
            self.destroy()
            SettingsDialog(self.app)
        ServerEditDialog(self.app, server, on_saved=on_saved)

    def _sidebar_delete_server(self, server):
        servers = list(self.app.cfg.get("servers") or [])
        if len(servers) <= 1:
            alert(self, "서버 삭제", "서버는 최소 1개는 남아있어야 합니다.")
            return
        if not ask_confirm(self, "서버 삭제", f"'{server.get('name', '서버')}' 서버를 삭제하시겠습니까?"):
            return
        servers = [s for s in servers if s.get("id") != server.get("id")]
        self.app.cfg["servers"] = servers
        was_active = self.app.cfg.get("active_server_id") == server.get("id")
        if was_active:
            self.app.switch_to_server(servers[0])
            self.destroy()
            SettingsDialog(self.app)
        else:
            config_store.save_config(self.app.cfg)
            self._refresh_sidebar_rows()

    def _on_sidebar_toggle(self, server, is_on, switch):
        if not is_on:
            # 정확히 하나의 서버만 켜져 있어야 하므로, 활성 서버를 끄려는
            # 시도는 그냥 다시 켜서 되돌린다.
            switch.set(True)
            return
        if server.get("id") == self.app.cfg.get("active_server_id"):
            return
        self.app.switch_to_server(server)
        self.destroy()
        SettingsDialog(self.app)

    def _on_server_changed(self):
        """서버 관리 창에서 다른 서버로 전환하면, 지금 열려있는 설정 창을 닫고
        새로 연다 - 활성 서버가 바뀌면 이 폼에 채워야 할 값(모드/DB/경로/렐름리스트
        등) 전체가 달라지는데, 이미 만들어진 위젯들을 하나씩 다시 채우는 것보다
        통째로 다시 만드는 쪽이 실수 없이 확실하다."""
        self.destroy()
        SettingsDialog(self.app)

    def _run_remote_test(self):
        """"연결 테스트" 버튼 - 저장을 누르기 전, 지금 폼에 입력한 값 그대로 SSH
        접속과 원격 worldserver.conf 읽기를 확인한다. 저장된 self.app.cfg 가 아니라
        self.vars 에서 직접 읽는 이유: 값을 막 입력한 상태에서 저장 없이 바로
        확인해보고 싶을 때가 많기 때문."""
        host = self.vars["remote_host"].get().strip()
        user = self.vars["remote_ssh_user"].get().strip()
        key_path = self.vars["remote_ssh_key_path"].get().strip()
        conf_path = self.vars["remote_worldserver_conf_path"].get().strip()
        port_raw = self.vars["remote_ssh_port"].get().strip()
        try:
            port = int(port_raw) if port_raw else 22
        except ValueError:
            self._remote_test_status_label.config(fg="#e0b93f")
            self._remote_test_status.set("SSH 포트는 숫자로 입력해 주세요.")
            return
        if not host:
            self._remote_test_status_label.config(fg="#e0b93f")
            self._remote_test_status.set("호스트를 먼저 입력해 주세요.")
            return

        self._remote_test_btn.set_enabled(False)
        self._remote_test_btn.set_text("확인 중...")
        self._remote_test_status_label.config(fg=theme.TEXT_MUTED3)
        self._remote_test_status.set("SSH 접속을 확인하는 중...")

        def worker():
            ok, msg = remote_conf.check_connection(host, port, user, key_path)
            conf_msg = ""
            conf_ok = True
            if ok:
                if conf_path:
                    content, err = remote_conf.read_text_detailed(host, port, user, key_path, conf_path)
                    if content is not None:
                        lines = content.count("\n") + 1
                        conf_msg = f" / conf 파일 읽기 성공 ({lines}줄)"
                    elif err and ("denied" in err.lower() or "permission" in err.lower()):
                        # 접속은 되는데 conf 파일만 권한 때문에 못 읽는 흔한 경우 - 다른
                        # 권한은 안 건드리고 읽기 권한만(o+r) 자동으로 한 번 추가해보고
                        # 바로 재시도한다. 파일 소유자가 SSH 계정과 다르면(도커 컨테이너
                        # 안쪽 UID로 마운트된 경우 등) chmod 자체가 거부될 수 있는데, 그
                        # 경우 이유를 그대로 사용자에게 보여준다.
                        chmod_ok, chmod_msg = remote_conf.chmod_add_read(
                            host, port, user, key_path, conf_path)
                        if chmod_ok:
                            content2, err2 = remote_conf.read_text_detailed(
                                host, port, user, key_path, conf_path)
                            if content2 is not None:
                                lines = content2.count("\n") + 1
                                conf_msg = (f" / conf 파일 권한 문제를 자동으로 고치고"
                                            f" 읽기 성공 ({lines}줄)")
                            else:
                                conf_msg = f" / 권한은 고쳤지만 여전히 읽기 실패: {err2}"
                                conf_ok = False
                        else:
                            conf_msg = (f" / conf 파일 읽기 실패({err}) - 권한 자동 수정도"
                                        f" 실패: {chmod_msg}")
                            conf_ok = False
                    else:
                        conf_msg = f" / conf 파일 읽기 실패: {err}"
                        conf_ok = False
                else:
                    conf_msg = (" / \"원격 worldserver.conf 경로\" 가 비어 있습니다 - 게임"
                                " 설정을 쓰려면 이 값을 입력해야 합니다.")
                    conf_ok = False
            elif "denied" in msg.lower() or "publickey" in msg.lower():
                # BatchMode=yes 라 비밀번호 프롬프트로 넘어가지 못하고 여기서 바로
                # 실패한다 - 그래서 수동으로 ssh 실행하면 비밀번호를 입력해서 접속은
                # 되는데, 이 테스트는 실패로 뜨는 게 정상이다(런처는 비밀번호를 입력해줄
                # 수 없으므로 키 인증이 그냥 되어야 함). 공개키 등록이 아직 안 됐거나
                # 잘못됐다는 뜻이라 SSH 키 도움말 2번 단계를 다시 안내한다.
                msg += (" (직접 ssh로 접속했을 때 비밀번호를 입력해야 했다면 이게 원인입니다"
                        " - 공개키가 원격 서버에 아직 제대로 등록되지 않았습니다. 'SSH 개인키"
                        " 파일' 옆의 ? 도움말 2번 단계를 다시 확인해 보세요.)")

            def apply():
                self._remote_test_btn.set_enabled(True)
                self._remote_test_btn.set_text("연결 테스트")
                if ok and conf_ok:
                    self._remote_test_status_label.config(fg="#5fe08a")
                    self._remote_test_status.set(f"✅ SSH 접속 성공{conf_msg}")
                elif ok:
                    self._remote_test_status_label.config(fg="#e0b93f")
                    self._remote_test_status.set(f"⚠ SSH 접속 성공{conf_msg}")
                else:
                    self._remote_test_status_label.config(fg="#ff6b6b")
                    self._remote_test_status.set(f"❌ SSH 접속 실패: {msg}")
            self.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def _browse(self, key):
        t0 = time.perf_counter()
        var = self.vars[key]
        current = var.get()
        initdir = os.path.dirname(current) if current else self.app.cfg.get("root_dir", "")
        setup_elapsed = time.perf_counter() - t0
        if setup_elapsed > 0.05:
            self.app._log_perf(f"찾아보기({key}) 대화상자 열기 전 준비 {setup_elapsed:.3f}초")

        path = filedialog.askopenfilename(
            initialdir=initdir or None, parent=self, filetypes=SETTINGS_FILETYPES,
        )
        if path:
            path = os.path.normpath(path)
            var.set(path)
            if key in ("authserver_exe", "worldserver_exe"):
                t1 = time.perf_counter()
                self._autofill_db_from_authserver_conf(path)
                autofill_elapsed = time.perf_counter() - t1
                if autofill_elapsed > 0.05:
                    self.app._log_perf(f"DB 자동 채움({key}) {autofill_elapsed:.3f}초")

    def _autofill_db_from_authserver_conf(self, exe_path):
        """인증 서버/월드 서버 경로를 지정하면, 그 근처(같은 폴더 또는 configs\\ 등
        하위 폴더)의 authserver.conf 에서 LoginDatabaseInfo 를 읽어 DB 접속 정보를
        자동으로 채워준다. 못 찾아도 조용히 넘어간다(팝업 없음) — 서버팩마다 conf
        위치가 다를 수 있어서 못 찾는 게 정상적인 경우도 많다."""
        info = conf_reader.read_database_info(exe_path, "authserver.conf", "LoginDatabaseInfo")
        if not info:
            return
        self.vars["mysql_host"].set(info["host"])
        self.vars["mysql_port"].set(info["port"])
        self.vars["db_user"].set(info["user"])
        self.vars["db_password"].set(info["password"])

    def _save(self):
        prev_font = self.app.cfg.get("ui_font", "")
        for key, v in self.vars.items():
            if isinstance(v, ToggleSwitch):
                self.app.cfg[key] = v.get()
            else:
                self.app.cfg[key] = v.get().strip()
        try:
            self.app.cfg["mysql_port"] = int(self.app.cfg.get("mysql_port") or 3306)
        except ValueError:
            self.app.cfg["mysql_port"] = 3306
        try:
            self.app.cfg["online_list_limit"] = max(1, int(self.app.cfg.get("online_list_limit") or 100))
        except ValueError:
            self.app.cfg["online_list_limit"] = 100
        try:
            self.app.cfg["remote_ssh_port"] = int(self.app.cfg.get("remote_ssh_port") or 22)
        except ValueError:
            self.app.cfg["remote_ssh_port"] = 22
        if self.app.cfg.get("ui_font") == self.UI_FONT_DEFAULT_LABEL:
            self.app.cfg["ui_font"] = ""
        self.app.cfg["realmlist_list"] = list(self.realmlist_addrs)
        self.app.cfg["mode"] = self.mode

        # 방금 고친 값들을 "지금 활성 서버" 항목에도 그대로 되돌려 쓴다 - 안 하면
        # cfg 최상위(화면에 반영된 값)만 바뀌고 servers 목록 안의 항목은 예전
        # 값 그대로 남아서, 다른 서버로 갔다가 돌아오면 방금 고친 게 사라진 것처럼
        # 보인다.
        config_store.sync_active_server(self.app.cfg)
        config_store.save_config(self.app.cfg)

        self.app.apply_config()
        self.app._update_realmlist_file()
        # 폰트가 바뀌었으면 메인 창을 다시 그려서 바로 반영한다(테마 전환과 같은
        # 방식 — Tkinter 는 이미 만든 위젯의 글꼴을 값 하나 바꾼다고 저절로 다시
        # 그려주지 않는다).
        new_font = self.app.cfg.get("ui_font", "")
        if new_font != prev_font:
            theme.set_ui_font(new_font)
            self.app._rebuild_ui()
        self.destroy()


# ==================== 서버 관리 창 ====================
class ServerManageDialog(tk.Toplevel):
    """서버 목록(로컬/원격 여러 개)을 추가/삭제/전환한다. 각 서버의 상세 필드
    편집(DB/경로/SSH/GM 계정/렐름리스트)은 여기서 하지 않고, 그 서버를 활성화한
    뒤 설정(SettingsDialog)에서 한다 - 화면 두 개에 같은 편집 UI를 중복해서
    만들지 않기 위함."""

    def __init__(self, app, on_change=None):
        super().__init__(app.root)
        self.app = app
        self.on_change = on_change
        self.title("서버 관리")
        self.configure(bg="#0d1a26")
        dlg_w, dlg_h = 480, 460
        center_on_screen(self, dlg_w, dlg_h)
        self.resizable(False, False)
        self.transient(app.root)
        self.grab_set()
        self.focus_set()

        body = tk.Frame(self, bg="#0d1a26", width=dlg_w, height=dlg_h)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="서버 목록", bg="#0d1a26", fg=theme.HEADER_TEXT,
                  font=theme.korean(14, "bold"), anchor="w").pack(fill="x", padx=16, pady=(16, 6))
        tk.Frame(body, bg=theme.HEADER_BORDER, height=1).pack(fill="x", padx=16)

        self.list_frame = tk.Frame(body, bg="#0d1a26")
        self.list_frame.pack(fill="both", expand=True, padx=16, pady=(8, 8))

        btns = tk.Frame(body, bg="#0d1a26")
        btns.pack(fill="x", padx=16, pady=(0, 16))
        GradientButton(
            btns, "추가", self._add_server, 74, 30,
            theme.START_TOP, theme.START_BOTTOM, theme.START_BORDER, theme.START_TEXT,
            hover_border=theme.START_HOVER_BORDER, hover_text_color=theme.START_HOVER_TEXT,
            font=theme.korean(11, "bold"), radius=3, container_bg="#0d1a26", key="server-add",
            tooltip="새 서버 추가 (로컬 기본값으로 시작, 활성화 후 설정에서 편집)",
        ).pack(side="left")
        GradientButton(
            btns, "닫기", self.destroy, 90, 30,
            theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
            hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
            font=theme.korean(11, "bold"), radius=3, container_bg="#0d1a26", key="server-close",
        ).pack(side="right")

        self._refresh_list()

    def _refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        servers = self.app.cfg.get("servers") or []
        active_id = self.app.cfg.get("active_server_id")
        for server in servers:
            self._build_row(server, server.get("id") == active_id)

    def _build_row(self, server, is_active):
        row_bg = "#132235" if is_active else "#0e1c28"
        row = tk.Frame(self.list_frame, bg=row_bg, highlightthickness=1,
                        highlightbackground=theme.START_BORDER if is_active else theme.ROW_BORDER)
        row.pack(fill="x", pady=(0, 8))
        inner = tk.Frame(row, bg=row_bg)
        inner.pack(fill="x", padx=12, pady=10)

        name_row = tk.Frame(inner, bg=row_bg)
        name_row.pack(fill="x")
        tk.Label(name_row, text=server.get("name", "서버"), bg=row_bg, fg=theme.BODY_TEXT,
                  font=theme.korean(13, "bold"), anchor="w").pack(side="left")
        mode_label = "원격" if server.get("mode") == "remote" else "로컬"
        tk.Label(name_row, text=f"[{mode_label}]", bg=row_bg,
                  fg=theme.TEXT_MUTED3, font=theme.korean(10), anchor="w").pack(side="left", padx=(6, 0))
        if is_active:
            tk.Label(name_row, text="● 활성", bg=row_bg, fg=theme.DOT_UP,
                      font=theme.korean(10, "bold")).pack(side="left", padx=(8, 0))

        pack_name = server.get("pack_name", "").strip()
        if pack_name:
            tk.Label(inner, text=pack_name, bg=row_bg, fg=theme.LABEL_MUTED,
                      font=theme.korean(10), anchor="w").pack(fill="x", pady=(2, 0))

        detail = server.get("remote_host") if server.get("mode") == "remote" else server.get("worldserver_exe", "")
        tk.Label(inner, text=detail or "(설정 없음)", bg=row_bg, fg=theme.TEXT_MUTED3,
                  font=theme.mono(9), anchor="w", wraplength=340, justify="left").pack(fill="x", pady=(3, 8))

        btn_row = tk.Frame(inner, bg=row_bg)
        btn_row.pack(fill="x")
        if not is_active:
            GradientButton(
                btn_row, "전환", lambda s=server: self._activate(s), 70, 26,
                theme.START_TOP, theme.START_BOTTOM, theme.START_BORDER, theme.START_TEXT,
                hover_border=theme.START_HOVER_BORDER, hover_text_color=theme.START_HOVER_TEXT,
                font=theme.korean(10, "bold"), radius=3, container_bg=row_bg, key=f"server-activate-{server['id']}",
            ).pack(side="left", padx=(0, 6))
        GradientButton(
            btn_row, "수정", lambda s=server: self._edit(s), 70, 26,
            theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
            hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
            font=theme.korean(10, "bold"), radius=3, container_bg=row_bg, key=f"server-edit-{server['id']}",
            tooltip="이름과 로컬/원격 환경 수정",
        ).pack(side="left", padx=(0, 6))
        if server.get("mode") == "remote":
            GradientButton(
                btn_row, "백업/복원", lambda s=server: self._open_backup(s), 84, 26,
                theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
                hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
                font=theme.korean(10, "bold"), radius=3, container_bg=row_bg,
                key=f"server-backup-{server['id']}",
                tooltip="이 서버의 계정/캐릭터 백업 생성 및 복원 (SSH로 backup.sh/restore.sh 실행)",
            ).pack(side="left", padx=(0, 6))
        GradientButton(
            btn_row, "삭제", lambda s=server: self._delete(s), 70, 26,
            theme.STOP_TOP, theme.STOP_BOTTOM, theme.STOP_BORDER, theme.STOP_TEXT,
            hover_border=theme.STOP_HOVER_BORDER, hover_text_color=theme.STOP_HOVER_TEXT,
            font=theme.korean(10, "bold"), radius=3, container_bg=row_bg, key=f"server-delete-{server['id']}",
        ).pack(side="left")

    def _activate(self, server):
        self.app.switch_to_server(server)
        self._refresh_list()
        if self.on_change:
            self.on_change()

    def _edit(self, server):
        ServerEditDialog(self.app, server, on_saved=self._on_server_edited)

    def _open_backup(self, server):
        BackupManageDialog(self.app, server)

    def _on_server_edited(self, server):
        self._refresh_list()
        if server.get("id") == self.app.cfg.get("active_server_id") and self.on_change:
            self.on_change()

    def _add_server(self):
        name = ask_string(self, "서버 추가", "새 서버 이름을 입력하세요:")
        if not name or not name.strip():
            return
        new_entry = config_store.new_server(name.strip())
        servers = list(self.app.cfg.get("servers") or [])
        servers.append(new_entry)
        self.app.cfg["servers"] = servers
        self._activate(new_entry)
        alert(self, "서버 추가됨",
              f"'{new_entry['name']}' 서버를 추가하고 활성화했습니다.\n"
              "설정 창에서 이 서버의 정보를 입력해 주세요.")

    def _delete(self, server):
        servers = list(self.app.cfg.get("servers") or [])
        if len(servers) <= 1:
            alert(self, "서버 삭제", "서버는 최소 1개는 남아있어야 합니다.")
            return
        if not ask_confirm(self, "서버 삭제", f"'{server.get('name', '서버')}' 서버를 삭제하시겠습니까?"):
            return
        servers = [s for s in servers if s.get("id") != server.get("id")]
        self.app.cfg["servers"] = servers
        was_active = self.app.cfg.get("active_server_id") == server.get("id")
        if was_active:
            self.app.switch_to_server(servers[0])
        else:
            config_store.save_config(self.app.cfg)
        self._refresh_list()
        if was_active and self.on_change:
            self.on_change()


class ServerEditDialog(tk.Toplevel):
    """"서버 관리" 목록의 "수정" 버튼 - 이름과 로컬/원격 환경(모드)만 여기서
    바로 바꾼다. DB/SSH/GM 계정 같은 상세 필드는 여전히 그 서버를 활성화한 뒤
    설정(SettingsDialog)에서 편집한다 - 두 화면에 같은 편집 UI를 중복해서
    만들지 않기 위함(ServerManageDialog 의 설계와 동일한 원칙)."""

    def __init__(self, app, server, on_saved=None):
        super().__init__(app.root)
        self.app = app
        self.server = server
        self.on_saved = on_saved
        self.title("서버 수정")
        self.configure(bg="#0d1a26")
        dlg_w, dlg_h = 360, 320
        center_on_screen(self, dlg_w, dlg_h)
        self.resizable(False, False)
        self.transient(app.root)

        body = tk.Frame(self, bg="#0d1a26")
        body.pack(fill="both", expand=True, padx=20, pady=(20, 0))

        tk.Label(body, text="서버 이름", bg="#0d1a26", fg=theme.LABEL_MUTED,
                  font=theme.korean(11), anchor="w").pack(fill="x")
        self.name_var = tk.StringVar(value=server.get("name", ""))
        entry = tk.Entry(body, textvariable=self.name_var, bg=theme.INPUT_BG, fg=theme.INPUT_TEXT,
                          insertbackground=theme.INPUT_TEXT, relief="flat",
                          highlightthickness=1, highlightbackground=theme.INPUT_BORDER,
                          font=theme.korean(11))
        entry.pack(fill="x", ipady=4, pady=(3, 14))

        tk.Label(body, text="서버팩 이름 (부제목)", bg="#0d1a26", fg=theme.LABEL_MUTED,
                  font=theme.korean(11), anchor="w").pack(fill="x")
        self.pack_name_var = tk.StringVar(value=server.get("pack_name", ""))
        tk.Entry(body, textvariable=self.pack_name_var, bg=theme.INPUT_BG, fg=theme.INPUT_TEXT,
                  insertbackground=theme.INPUT_TEXT, relief="flat",
                  highlightthickness=1, highlightbackground=theme.INPUT_BORDER,
                  font=theme.korean(11)).pack(fill="x", ipady=4, pady=(3, 14))

        tk.Label(body, text="서버 환경", bg="#0d1a26", fg=theme.LABEL_MUTED,
                  font=theme.korean(11), anchor="w").pack(fill="x")
        mode_row = tk.Frame(body, bg="#0d1a26")
        mode_row.pack(fill="x", pady=(6, 0))
        self._mode = server.get("mode", "local")
        self.mode_buttons = {}
        for mval, mlabel in (("local", "로컬"), ("remote", "원격")):
            btn = GradientButton(
                mode_row, mlabel, lambda m=mval: self._select_mode(m), 100, 30,
                theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
                hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
                font=theme.korean(11, "bold"), radius=3, container_bg="#0d1a26", key=f"server-edit-mode-{mval}",
            )
            btn.pack(side="left", padx=(0, 6))
            self.mode_buttons[mval] = btn
        self._select_mode(self._mode)
        tk.Label(body, text="DB/경로 또는 SSH 접속 정보 같은 상세 항목은 이 서버를 "
                             "활성화한 뒤 설정 창에서 편집합니다.",
                  bg="#0d1a26", fg=theme.TEXT_MUTED3, font=theme.korean(9),
                  anchor="w", justify="left", wraplength=320).pack(fill="x", pady=(14, 0))

        btn_row = tk.Frame(self, bg="#0d1a26")
        btn_row.pack(fill="x", padx=20, pady=20)
        GradientButton(
            btn_row, "저장", self._save, 90, 32,
            theme.START_TOP, theme.START_BOTTOM, theme.START_BORDER, theme.START_TEXT,
            hover_border=theme.START_HOVER_BORDER, hover_text_color=theme.START_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="server-edit-save",
        ).pack(side="right")
        GradientButton(
            btn_row, "취소", self.destroy, 90, 32,
            theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
            hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="server-edit-cancel",
        ).pack(side="right", padx=(0, 8))

        self.grab_set()
        entry.focus_set()
        entry.icursor("end")

    def _select_mode(self, m):
        self._mode = m
        for mval, btn in self.mode_buttons.items():
            active = mval == m
            btn.itemconfig(btn.text_id, fill=theme.START_TEXT if active else theme.BROWSE_TEXT)
            btn.itemconfig(btn.img_id, image=btn.hover_img if active else btn.normal_img)

    def _save(self):
        name = self.name_var.get().strip()
        if not name:
            alert(self, "서버 수정", "이름을 입력해 주세요.")
            return
        self.server["name"] = name
        self.server["pack_name"] = self.pack_name_var.get().strip()
        self.server["mode"] = self._mode
        config_store.save_config(self.app.cfg)
        # 지금 수정한 게 활성 서버면(예: 모드를 바꿈) 메인 화면에 바로 반영한다.
        if self.server.get("id") == self.app.cfg.get("active_server_id"):
            config_store.flatten_active_server(self.app.cfg)
            self.app.apply_config()
            self.app._update_realmlist_file()
            self.app._update_mode_badge()
            self.app._on_server_manage_changed()
        if self.on_saved:
            self.on_saved(self.server)
        self.destroy()


# ==================== 게임 설정 창 (worldserver.conf 직접 수정) ====================
# 탭 목록 (탭id, 탭 이름) - 이 순서 그대로 탭바에 표시된다.
GAME_SETTINGS_TABS = [
    ("flight", "비행"),
    ("start", "시작옵션"),
    ("xp", "경험치"),
    ("drop", "드랍률"),
    ("quest", "퀘스트"),
]

# 필드 종류: toggle(0/1) · choice(정해진 값 중 선택) · rate(소수 배율) · int(정수) ·
# money(정수, 골드 환산 안내를 옆에 보여줌). "default" 는 AzerothCore worldserver.conf
# 원본 주석에 적힌 기본값 - "기본값" 버튼을 누르면 이 값으로 되돌아간다.
GAME_SETTINGS_FIELDS = {
    "flight": [
        {"key": "AllFlightPaths", "kind": "toggle", "default": "0",
         "label": "생성 시 비행경로 모두 알고 시작",
         "desc": "켜면 캐릭터를 만들자마자 양 진영 비행경로를 전부 아는 상태로 시작합니다."},
        {"key": "InstantFlightPaths", "kind": "choice", "default": "0",
         "label": "비행 즉시 도착",
         "desc": "비행 이동을 순간이동처럼 즉시 끝낼지 정합니다.",
         "choices": [("0", "끔"), ("1", "켬"), ("2", "켬 (비행사에서 토글 가능)")]},
    ],
    "start": [
        {"key": "StartPlayerMoney", "kind": "money", "default": "0",
         "label": "캐릭터 생성 시 소지금 (구리)",
         "desc": "새 캐릭터를 만들 때 처음 갖고 시작하는 돈입니다 (1 골드 = 10000 구리)."},
    ],
    "xp": [
        {"key": "Rate.XP.Kill", "kind": "rate", "default": "1",
         "label": "사냥 경험치 배율", "desc": "몬스터를 처치했을 때 얻는 경험치 배율입니다."},
        {"key": "Rate.XP.Quest", "kind": "rate", "default": "1",
         "label": "퀘스트 경험치 배율", "desc": "퀘스트를 완료했을 때 얻는 경험치 배율입니다."},
        {"key": "Rate.XP.Quest.DF", "kind": "rate", "default": "1",
         "label": "던전파인더 퀘스트 경험치 배율",
         "desc": "던전파인더(자동 그룹찾기)로 받은 퀘스트에만 적용되는 경험치 배율입니다."},
        {"key": "Rate.XP.Explore", "kind": "rate", "default": "1",
         "label": "탐사 경험치 배율", "desc": "새 지역을 처음 발견했을 때 얻는 경험치 배율입니다."},
        {"key": "Rate.XP.Pet", "kind": "rate", "default": "1",
         "label": "펫 경험치 배율", "desc": "사냥꾼 펫이 얻는 경험치 배율입니다."},
    ],
    "drop": [
        {"key": "Rate.Drop.Item.Poor", "kind": "rate", "default": "1",
         "label": "허접 (회색) 아이템 드랍률", "desc": "품질 등급이 '허접'인 아이템의 드랍률입니다."},
        {"key": "Rate.Drop.Item.Normal", "kind": "rate", "default": "1",
         "label": "일반 (흰색) 아이템 드랍률", "desc": "품질 등급이 '일반'인 아이템의 드랍률입니다."},
        {"key": "Rate.Drop.Item.Uncommon", "kind": "rate", "default": "1",
         "label": "고급 (초록) 아이템 드랍률", "desc": "품질 등급이 '고급'인 아이템의 드랍률입니다."},
        {"key": "Rate.Drop.Item.Rare", "kind": "rate", "default": "1",
         "label": "희귀 (파랑) 아이템 드랍률", "desc": "품질 등급이 '희귀'인 아이템의 드랍률입니다."},
        {"key": "Rate.Drop.Item.Epic", "kind": "rate", "default": "1",
         "label": "영웅 (보라) 아이템 드랍률", "desc": "품질 등급이 '영웅'인 아이템의 드랍률입니다."},
        {"key": "Rate.Drop.Item.Legendary", "kind": "rate", "default": "1",
         "label": "전설 (주황) 아이템 드랍률", "desc": "품질 등급이 '전설'인 아이템의 드랍률입니다."},
        {"key": "Rate.Drop.Item.Artifact", "kind": "rate", "default": "1",
         "label": "유물 아이템 드랍률", "desc": "유물 등급 아이템의 드랍률입니다."},
        {"key": "Rate.Drop.Item.Referenced", "kind": "rate", "default": "1",
         "label": "참조 아이템 드랍률",
         "desc": "다른 전리품 그룹을 참조하는 형태로 등록된 아이템의 드랍률입니다."},
        {"key": "Rate.Drop.Money", "kind": "rate", "default": "1",
         "label": "골드 드랍률", "desc": "몬스터가 떨어뜨리는 돈의 배율입니다."},
    ],
    "quest": [
        {"key": "Quests.LowLevelHideDiff", "kind": "int", "default": "4",
         "label": "저레벨 퀘스트 숨김 레벨차",
         "desc": "캐릭터 레벨보다 이 값 이상 낮은 퀘스트는 지도/NPC 위 느낌표(!)가 안 보입니다."},
        {"key": "Quests.HighLevelHideDiff", "kind": "int", "default": "7",
         "label": "고레벨 퀘스트 숨김 레벨차",
         "desc": "캐릭터 레벨보다 이 값 이상 높은 퀘스트는 지도/NPC 위 느낌표(!)가 안 보입니다."},
        {"key": "Quests.IgnoreRaid", "kind": "toggle", "default": "0",
         "label": "공격대 중 비공격대 퀘스트 완료 허용",
         "desc": "켜면 공격대에 속해 있어도 공격대 전용이 아닌 퀘스트를 완료할 수 있습니다."},
        {"key": "Rate.RewardQuestMoney", "kind": "rate", "default": "1",
         "label": "퀘스트 보상 골드 배율",
         "desc": "퀘스트 완료 보상으로 받는 돈의 배율입니다 (만렙 보너스 골드는 별도)."},
        {"key": "Rate.RewardBonusMoney", "kind": "rate", "default": "1",
         "label": "만렙 보너스 골드 배율",
         "desc": "만렙 캐릭터가 경험치 대신 받는 보너스 골드의 배율입니다."},
    ],
}


# ==================== 백업 / 복원 창 ====================
class BackupManageDialog(tk.Toplevel):
    """원격 서버의 계정/캐릭터 백업(scripts/backup.sh)을 만들고, 목록에서 골라
    복원(scripts/restore.sh)한다 - 전부 SSH로 원격 셸 명령을 실행한다
    (backup_remote.py). 월드/봇 데이터는 백업 대상이 아니다(스크립트 쪽 정책)."""

    def __init__(self, app, server):
        super().__init__(app.root)
        self.app = app
        self.server = server
        self.title(f"백업 / 복원 - {server.get('name', '서버')}")
        self.configure(bg="#0d1a26")
        dlg_w, dlg_h = 620, 560
        center_on_screen(self, dlg_w, dlg_h)
        self.resizable(False, False)
        self.transient(app.root)
        self.grab_set()

        body = tk.Frame(self, bg="#0d1a26", width=dlg_w, height=dlg_h)
        body.pack(fill="both", expand=True)

        top_row = tk.Frame(body, bg="#0d1a26")
        top_row.pack(fill="x", padx=16, pady=(16, 0))
        tk.Label(top_row, text="계정/캐릭터 백업 목록", bg="#0d1a26", fg=theme.HEADER_TEXT,
                  font=theme.korean(14, "bold"), anchor="w").pack(side="left")
        self.btn_backup = GradientButton(
            top_row, "새 백업 만들기", self._run_backup, 130, 30,
            theme.START_TOP, theme.START_BOTTOM, theme.START_BORDER, theme.START_TEXT,
            hover_border=theme.START_HOVER_BORDER, hover_text_color=theme.START_HOVER_TEXT,
            font=theme.korean(11, "bold"), radius=3, container_bg="#0d1a26", key="backup-create",
            tooltip="지금 상태로 acore_auth/acore_characters 백업 (월드/봇 데이터는 대상 아님)",
        )
        self.btn_backup.pack(side="right")
        self.btn_refresh = GradientButton(
            top_row, "새로고침", self._refresh_list, 90, 30,
            theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
            hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
            font=theme.korean(11, "bold"), radius=3, container_bg="#0d1a26", key="backup-refresh",
        )
        self.btn_refresh.pack(side="right", padx=(0, 8))

        tk.Frame(body, bg=theme.HEADER_BORDER, height=1).pack(fill="x", padx=16, pady=(10, 0))

        list_wrap = tk.Frame(body, bg="#0d1a26")
        list_wrap.pack(fill="both", expand=False, padx=16, pady=(8, 8))
        self.list_frame = tk.Frame(list_wrap, bg="#0d1a26")
        self.list_frame.pack(fill="both", expand=True)
        self.list_frame.config(height=220)
        self.list_frame.pack_propagate(False)
        self._empty_label = tk.Label(self.list_frame, text="불러오는 중...", bg="#0d1a26",
                                      fg=theme.TEXT_MUTED3, font=theme.korean(11))
        self._empty_label.pack(anchor="w", pady=8)

        tk.Label(body, text="실행 로그", bg="#0d1a26", fg=theme.LABEL_MUTED,
                  font=theme.korean(11), anchor="w").pack(fill="x", padx=16)
        result_wrap = tk.Frame(body, bg="#0d1a26")
        result_wrap.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        self.result_text = tk.Text(
            result_wrap, bg=theme.INPUT_BG, fg=theme.INPUT_TEXT, insertbackground=theme.INPUT_TEXT,
            relief="flat", highlightthickness=1, highlightbackground=theme.INPUT_BORDER,
            font=theme.mono(10), wrap="word", state="disabled",
        )
        self.result_text.pack(side="left", fill="both", expand=True)

        self._refresh_list()

    # ---------------- 원격 접속 정보 ----------------
    def _conn(self):
        s = self.server
        return (s.get("remote_host", ""), int(s.get("remote_ssh_port") or 22),
                s.get("remote_ssh_user", ""), s.get("remote_ssh_key_path", ""),
                s.get("remote_deploy_dir", ""))

    def _append_result(self, text):
        self.result_text.config(state="normal")
        self.result_text.insert("end", text + "\n")
        self.result_text.see("end")
        self.result_text.config(state="disabled")

    def _set_busy(self, busy):
        self.btn_backup.set_enabled(not busy)
        self.btn_refresh.set_enabled(not busy)

    # ---------------- 목록 ----------------
    def _refresh_list(self):
        host, port, user, key_path, deploy_dir = self._conn()
        for w in self.list_frame.winfo_children():
            w.destroy()
        tk.Label(self.list_frame, text="불러오는 중...", bg="#0d1a26",
                  fg=theme.TEXT_MUTED3, font=theme.korean(11)).pack(anchor="w", pady=8)

        def worker():
            backups, err = backup_remote.list_backups(host, port, user, key_path, deploy_dir)
            self.after(0, lambda: self._apply_list(backups, err))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_list(self, backups, err):
        for w in self.list_frame.winfo_children():
            w.destroy()
        if err:
            tk.Label(self.list_frame, text=err, bg="#0d1a26", fg=theme.STOP_TEXT,
                      font=theme.korean(11), wraplength=560, justify="left",
                      anchor="w").pack(anchor="w", pady=8)
            return
        if not backups:
            tk.Label(self.list_frame, text="아직 백업이 없습니다. \"새 백업 만들기\"로 하나 만드세요.",
                      bg="#0d1a26", fg=theme.TEXT_MUTED3, font=theme.korean(11)).pack(anchor="w", pady=8)
            return
        canvas = tk.Canvas(self.list_frame, bg="#0d1a26", highlightthickness=0)
        scrollbar = tk.Scrollbar(self.list_frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#0d1a26")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        for manifest in backups:
            self._build_row(inner, manifest)

    def _build_row(self, parent, manifest):
        backup_id = manifest.get("backup_id", "")
        label = backup_id
        if len(backup_id) == 15 and backup_id[8] == "-":
            label = (f"{backup_id[0:4]}-{backup_id[4:6]}-{backup_id[6:8]} "
                      f"{backup_id[9:11]}:{backup_id[11:13]}:{backup_id[13:15]}")
        row = tk.Frame(parent, bg="#0e1c28", highlightthickness=1, highlightbackground=theme.ROW_BORDER)
        row.pack(fill="x", pady=(0, 6))
        inner = tk.Frame(row, bg="#0e1c28")
        inner.pack(fill="x", padx=12, pady=8)
        tk.Label(inner, text=label, bg="#0e1c28", fg=theme.BODY_TEXT,
                  font=theme.korean(12, "bold"), anchor="w").pack(side="left")
        detail = (f"계정 {manifest.get('account_count', '?')}개 · "
                  f"캐릭터 {manifest.get('character_count', '?')}개")
        tk.Label(inner, text=detail, bg="#0e1c28", fg=theme.TEXT_MUTED3,
                  font=theme.korean(10), anchor="w").pack(side="left", padx=(12, 0))
        GradientButton(
            inner, "복원", lambda b=backup_id: self._confirm_restore(b), 70, 26,
            theme.STOP_TOP, theme.STOP_BOTTOM, theme.STOP_BORDER, theme.STOP_TEXT,
            hover_border=theme.STOP_HOVER_BORDER, hover_text_color=theme.STOP_HOVER_TEXT,
            font=theme.korean(10, "bold"), radius=3, container_bg="#0e1c28",
            key=f"backup-restore-{backup_id}",
        ).pack(side="right")

    # ---------------- 새 백업 ----------------
    def _run_backup(self):
        host, port, user, key_path, deploy_dir = self._conn()
        if not deploy_dir:
            self._append_result("설정(⚙) > 원격 접속 정보 에서 \"원격 배포 폴더\"를 먼저 지정하세요.")
            return
        self._append_result("> 백업 생성 중... (mysqldump 크기에 따라 몇 분 걸릴 수 있습니다)")
        self._set_busy(True)

        def worker():
            ok, output = backup_remote.run_backup(host, port, user, key_path, deploy_dir)
            def done():
                self._append_result(output or ("백업 완료" if ok else "백업 실패"))
                self._set_busy(False)
                if ok:
                    self._refresh_list()
            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    # ---------------- 복원 ----------------
    def _confirm_restore(self, backup_id):
        if not ask_confirm(
            self, "백업 복원",
            f"'{backup_id}' 백업으로 복원합니다.\n\n"
            "지금 서버에 있는 계정/캐릭터 데이터는 이 백업 시점 데이터로 완전히 "
            "덮어써지며 되돌릴 수 없습니다. worldserver/authserver가 잠시 중지됩니다.\n\n"
            "계속하시겠습니까?",
        ):
            return
        host, port, user, key_path, deploy_dir = self._conn()
        self._append_result(f"> '{backup_id}' 복원 중...")
        self._set_busy(True)

        def worker():
            ok, output = backup_remote.run_restore(host, port, user, key_path, deploy_dir, backup_id)
            def done():
                self._append_result(output or ("복원 완료" if ok else "복원 실패"))
                self._set_busy(False)
            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()


class GameSettingsDialog(tk.Toplevel):
    """worldserver.conf 에 있는 게임플레이 수치(비행경로/시작 자금/경험치·드랍률
    배율/퀘스트 보상)를 직접 읽고 쓴다. 런처 자체 config.json 이 아니라 conf 파일
    자체가 항상 진실의 원천이라, 열 때마다 그 자리에서 다시 읽는다 - 다른 곳(서버
    콘솔 등)에서 직접 고쳤어도 최신값을 보여준다."""

    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("게임 설정")
        self.configure(bg="#0d1a26")
        dlg_w, dlg_h = 720, 700
        center_on_screen(self, dlg_w, dlg_h)
        self.resizable(False, False)
        self.transient(app.root)
        self.grab_set()
        self.focus_set()

        self.vars = {}
        self.current_values = {}
        self.active_tab = GAME_SETTINGS_TABS[0][0]
        self.tab_buttons = {}
        self.mode = app.mode
        self.conf_path = None
        self.conf_text = None
        not_found_msg = "worldserver.conf 를 찾지 못했습니다.\n설정 > 서버 경로에서 월드 서버 실행파일을 먼저 지정해 주세요."
        if self.mode == "remote":
            remote_path = app.cfg.get("remote_worldserver_conf_path", "")
            if not remote_path:
                not_found_msg = ("\"원격 worldserver.conf 경로\" 가 비어 있습니다.\n"
                                  "설정 > 원격 모드 탭 > 원격 conf 경로에서 이 값을 먼저"
                                  " 입력해 주세요(예: /var/packages/WoWServer/target/etc/"
                                  "worldserver.conf).")
            else:
                not_found_msg = ("원격 worldserver.conf 를 가져오지 못했습니다.\n"
                                  "설정 > 원격 모드 탭의 \"연결 테스트\" 버튼으로 SSH 접속과"
                                  " conf 파일 읽기가 되는지 먼저 확인해 주세요 - 실패 이유를"
                                  " 거기서 자세히 보여줍니다.")
                self.conf_text = remote_conf.read_text(
                    app.cfg.get("remote_host", ""), app.cfg.get("remote_ssh_port", 22),
                    app.cfg.get("remote_ssh_user", ""), app.cfg.get("remote_ssh_key_path", ""),
                    remote_path,
                )
        else:
            self.conf_path = conf_reader.find_conf_file(
                app.cfg.get("worldserver_exe", ""), "worldserver.conf")
            if self.conf_path:
                try:
                    with open(self.conf_path, "r", encoding="utf-8-sig", errors="replace") as f:
                        self.conf_text = f.read()
                except OSError:
                    self.conf_text = None

        body = tk.Frame(self, bg="#0d1a26", width=dlg_w, height=dlg_h)
        body.pack(fill="both", expand=True)

        if not self.conf_text:
            tk.Label(body, text=not_found_msg,
                      bg="#0d1a26", fg=theme.LABEL_MUTED, font=theme.korean(12),
                      wraplength=650, justify="left").pack(padx=20, pady=40)
            close_row = tk.Frame(body, bg="#0d1a26")
            close_row.pack(fill="x", padx=20, pady=(0, 20), side="bottom")
            GradientButton(
                close_row, "닫기", self.destroy, 90, 32,
                theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
                hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
                font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="game-settings-close",
            ).pack(side="right")
            return

        all_keys = [f["key"] for fields in GAME_SETTINGS_FIELDS.values() for f in fields]
        self.current_values = conf_reader.read_values_from_text(self.conf_text, all_keys)

        tab_row = tk.Frame(body, bg="#0d1a26")
        tab_row.pack(fill="x", padx=16, pady=(16, 0))
        for tab_id, tab_label in GAME_SETTINGS_TABS:
            btn = GradientButton(
                tab_row, tab_label, lambda t=tab_id: self._select_tab(t), 108, 30,
                theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
                hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
                font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key=f"gs-tab-{tab_id}",
            )
            btn.pack(side="left", padx=(0, 6))
            self.tab_buttons[tab_id] = btn
        tk.Frame(body, bg=theme.HEADER_BORDER, height=1).pack(fill="x", padx=16, pady=(10, 0))

        # 탭마다 필드 수가 다르고(드랍률 9개 vs 시작옵션 1개) 다이얼로그를 가장 많은
        # 탭 기준으로 늘리면 다른 탭이 휑해 보이므로, 탭 전환은 미리 다 만들어둔
        # 프레임을 pack/pack_forget 으로 보이기/숨기기만 한다(내용을 지우고 다시
        # 만들지 않음) - _save() 가 지금 보이는 탭이 아닌 다른 탭의 값도 읽어야
        # 하는데, 위젯을 destroy() 해버리면 그 참조가 죽어서 저장이 깨진다.
        # 필드를 2열로 배치해서(값 입력칸을 좁게 만든 김에) 세로 길이를 줄이고,
        # 스크롤이 필요 없게 한다.
        self.tab_content = tk.Frame(body, bg="#0d1a26")
        self.tab_content.pack(fill="both", expand=True, padx=16, pady=(12, 0))

        self.tab_frames = {}
        for tab_id, _tab_label in GAME_SETTINGS_TABS:
            frame = tk.Frame(self.tab_content, bg="#0d1a26")
            frame.grid_columnconfigure(0, weight=1, uniform="gscol")
            frame.grid_columnconfigure(1, weight=1, uniform="gscol")
            for i, field in enumerate(GAME_SETTINGS_FIELDS[tab_id]):
                col = i % 2
                cell = tk.Frame(frame, bg="#0d1a26")
                cell.grid(row=i // 2, column=col, sticky="new",
                          padx=(0, 10) if col == 0 else (10, 0), pady=(0, 14))
                self._build_field(cell, field)
            self.tab_frames[tab_id] = frame

        btns = tk.Frame(body, bg="#0d1a26")
        btns.pack(fill="x", padx=16, pady=16)
        GradientButton(
            btns, "닫기", self.destroy, 90, 32,
            theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
            hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="game-settings-cancel",
        ).pack(side="right")
        GradientButton(
            btns, "저장", self._save, 90, 32,
            theme.START_TOP, theme.START_BOTTOM, theme.START_BORDER, theme.START_TEXT,
            hover_border=theme.START_HOVER_BORDER, hover_text_color=theme.START_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="game-settings-save",
        ).pack(side="right", padx=(0, 8))

        self._select_tab(self.active_tab)

    # ---------------- 탭 ----------------
    def _select_tab(self, tab_id):
        self.active_tab = tab_id
        for t_id, btn in self.tab_buttons.items():
            is_active = t_id == tab_id
            btn.itemconfig(btn.text_id, fill=theme.START_TEXT if is_active else theme.BROWSE_TEXT)
            btn.itemconfig(btn.img_id, image=btn.hover_img if is_active else btn.normal_img)
            if is_active:
                self.tab_frames[t_id].pack(fill="both", expand=True)
            else:
                self.tab_frames[t_id].pack_forget()

    # ---------------- 필드 위젯 ----------------
    def _build_field(self, parent, field):
        key = field["key"]
        kind = field["kind"]
        raw_value = self.current_values.get(key)

        row = tk.Frame(parent, bg="#0d1a26")
        row.pack(fill="x", pady=(0, 14))

        head = tk.Frame(row, bg="#0d1a26")
        head.pack(fill="x")
        tk.Label(head, text=field["label"], bg="#0d1a26", fg=theme.LABEL_MUTED,
                  font=theme.korean(11, "bold"), anchor="w").pack(side="left")
        GradientButton(
            head, "기본값", lambda k=key: self._apply_default(k), 58, 22,
            theme.ICON_TOP, theme.ICON_BOTTOM, theme.ICON_BORDER, theme.ICON_TEXT,
            hover_border=theme.ICON_HOVER_BORDER, font=theme.korean(10, "bold"),
            radius=3, container_bg="#0d1a26", key=f"gs-default-{key}",
            tooltip=f"기본값({field['default']})으로 되돌립니다",
        ).pack(side="right")

        tk.Label(row, text=field["desc"], bg="#0d1a26", fg=theme.TEXT_MUTED3,
                  font=theme.korean(10), anchor="w", justify="left",
                  wraplength=310).pack(fill="x", pady=(2, 6))

        if kind == "toggle":
            sw = ToggleSwitch(row, value=(raw_value == "1"), container_bg="#0d1a26")
            sw.pack(anchor="w")
            self.vars[key] = ("toggle", sw, None)
            return

        if kind == "choice":
            choices = field["choices"]
            text_by_code = {code: text for code, text in choices}
            code_by_text = {text: code for code, text in choices}
            combo = ttk.Combobox(row, values=[text for _, text in choices],
                                  state="readonly", style="Dark.TCombobox", font=theme.korean(11))
            combo.set(text_by_code.get(raw_value, choices[0][1]))
            combo.pack(fill="x")
            self.vars[key] = ("choice", combo, code_by_text)
            return

        value_row = tk.Frame(row, bg="#0d1a26")
        value_row.pack(fill="x")
        var = tk.StringVar(value=raw_value if raw_value is not None else "")
        # 대부분 값(배율/레벨차)은 숫자 4자리를 넘지 않으니 입력칸을 짧게 두고,
        # 소지금(구리)만 자릿수가 커서(예: 5000000) 따로 넉넉하게 잡는다.
        entry_width = 30 if kind == "money" else 8
        entry = tk.Entry(value_row, textvariable=var, width=entry_width,
                          bg=theme.INPUT_BG, fg=theme.INPUT_TEXT,
                          insertbackground=theme.INPUT_TEXT, relief="flat",
                          highlightthickness=1, highlightbackground=theme.INPUT_BORDER,
                          font=theme.mono(11))
        entry.pack(side="left", ipady=4)

        if kind == "money":
            hint = tk.Label(value_row, text="", bg="#0d1a26", fg=theme.TEXT_MUTED3,
                              font=theme.korean(10), width=14, anchor="w")
            hint.pack(side="left", padx=(8, 0))

            def update_hint(*_args, var=var, hint=hint):
                try:
                    hint.config(text=f"≈ {int(var.get()) / 10000:g} 골드")
                except ValueError:
                    hint.config(text="")

            # <KeyRelease> 만 걸어두면 "기본값" 버튼처럼 타이핑 없이 var.set() 으로
            # 값을 바꿀 때는 안내가 안 바뀐다 - trace 를 걸어서 값이 바뀌는 모든
            # 경우(타이핑/기본값 적용 둘 다)에 반응하게 한다.
            var.trace_add("write", update_hint)
            update_hint()

        self.vars[key] = (kind, var, None)

    def _apply_default(self, key):
        field = next(f for fields in GAME_SETTINGS_FIELDS.values() for f in fields if f["key"] == key)
        default = field["default"]
        widget_kind, widget, extra = self.vars[key]
        if widget_kind == "toggle":
            widget.set(default == "1")
        elif widget_kind == "choice":
            text_by_code = {code: text for code, text in field["choices"]}
            combo_text = text_by_code.get(default, field["choices"][0][1])
            widget.set(combo_text)
        else:
            widget.set(default)

    # ---------------- 저장 ----------------
    def _save(self):
        updates = {}
        errors = []
        for fields in GAME_SETTINGS_FIELDS.values():
            for field in fields:
                key, label = field["key"], field["label"]
                widget_kind, widget, extra = self.vars[key]
                if widget_kind == "toggle":
                    updates[key] = "1" if widget.get() else "0"
                elif widget_kind == "choice":
                    updates[key] = extra.get(widget.get(), "0")
                elif widget_kind == "rate":
                    try:
                        updates[key] = f"{float(widget.get().strip()):g}"
                    except ValueError:
                        errors.append(label)
                else:  # int / money
                    try:
                        updates[key] = str(int(widget.get().strip()))
                    except ValueError:
                        errors.append(label)

        if errors:
            alert(self, "입력 오류",
                  "다음 항목의 값이 올바르지 않습니다(숫자만 입력해 주세요):\n\n" + "\n".join(errors))
            return

        if self.mode == "remote":
            new_text, changed, missing = conf_reader.apply_updates_to_text(self.conf_text, updates)
            if changed:
                ok, err = remote_conf.write_text_detailed(
                    self.app.cfg.get("remote_host", ""), self.app.cfg.get("remote_ssh_port", 22),
                    self.app.cfg.get("remote_ssh_user", ""), self.app.cfg.get("remote_ssh_key_path", ""),
                    self.app.cfg.get("remote_worldserver_conf_path", ""), new_text,
                )
                if not ok:
                    msg = f"원격 서버에 저장하지 못했습니다.\n\n{err}"
                    if err and ("denied" in err.lower() or "permission" in err.lower()):
                        msg += ("\n\n연결과 conf 읽기는 이미 되고 있으니 SSH 자체 문제는 아닙니다 -"
                                " 이 conf 파일(또는 그 폴더)에 SSH 로그인 계정의 쓰기 권한이 없다는"
                                " 뜻입니다. 읽기 권한만 열어뒀다면(o+r) 쓰기 권한은 별도로 필요합니다."
                                " 원격 서버에서 파일 소유자를 SSH 계정으로 바꾸거나(chown), SSH 계정을"
                                " 파일 소유 그룹에 추가한 뒤 그 그룹에 쓰기 권한을 주는 방법을 권장합니다"
                                "(모든 사용자에게 쓰기 권한을 여는 것보다 안전합니다 - 이 파일엔 DB"
                                " 비밀번호도 들어있습니다).")
                    alert(self, "저장 실패", msg)
                    return
                self.conf_text = new_text
        else:
            changed, missing = conf_reader.set_values(self.conf_path, updates)

        if missing:
            alert(self, "일부 항목 저장 실패",
                  "worldserver.conf 에서 다음 항목을 찾지 못해 저장하지 못했습니다:\n\n"
                  + "\n".join(missing))
        if not changed:
            return

        self.current_values.update(updates)
        if self.mode == "remote":
            # 원격 모드는 재시작을 지원하지 않는다(설정에서 "시작/중지 미지원"으로
            # 안내한 것과 동일한 이유) - 안내만 하고 실제 재시작은 사용자가 원격
            # 서버에서 직접 한다.
            alert(self, "저장됨",
                  "저장되었습니다. 적용하려면 원격 서버에서 월드 서버를 재시작해야 합니다.")
            return

        if self.app._last_status.get("worldserver") != RUNNING:
            alert(self, "저장됨", "저장되었습니다. 다음에 월드 서버를 시작하면 적용됩니다.")
            return

        if ask_confirm(self, "월드 서버 재시작",
                        "저장되었습니다. 적용하려면 월드 서버를 재시작해야 합니다.\n"
                        "지금 저장 후 재시작하시겠습니까?"):
            self.app.run_action("worldserver", "restart")


# ==================== 도움말 창 ====================
class HelpDialog(tk.Toplevel):
    STEPS = [
        ("1", "MySQL 시작", "데이터베이스가 먼저 올라와야 인증 서버가 계정 정보를 읽을 수 있습니다."),
        ("2", "인증 서버 시작", "로그인과 렐름 목록을 담당합니다. 상태 표시가 실행 중으로 바뀔 때까지 기다립니다."),
        ("3", "월드 서버 시작", "맵과 캐릭터 데이터를 불러오므로 첫 실행은 시간이 걸릴 수 있습니다."),
        ("4", "게임 시작", "세 서버가 모두 실행 중이면 Play 버튼이 활성화됩니다."),
    ]
    TIPS = [
        ("로그인 실패", "설정에서 렐름리스트 주소와 인증 서버 포트를 확인하세요."),
        ("서버가 즉시 종료", "MySQL 계정 정보가 틀렸을 가능성이 큽니다. 설정의 데이터베이스 항목을 확인하세요."),
        ("경로 오류", "실행 파일 경로가 실제 위치와 일치하는지 설정에서 확인하세요."),
    ]

    def __init__(self, app):
        super().__init__(app.root)
        self.title("도움말")
        self.configure(bg="#0d1a26")
        center_on_screen(self, 560, 620)
        self.resizable(False, True)
        self.transient(app.root)
        self.grab_set()

        body = tk.Frame(self, bg="#0d1a26")
        body.pack(fill="both", expand=True, padx=20, pady=18)

        tk.Label(body, text="접속 순서", bg="#0d1a26", fg=theme.HEADER_TEXT,
                  font=theme.korean(15, "bold"), anchor="w").pack(fill="x", pady=(0, 8))
        tk.Frame(body, bg=theme.HEADER_BORDER, height=1).pack(fill="x", pady=(0, 10))
        for num, title, desc in self.STEPS:
            row = tk.Frame(body, bg="#0d1a26")
            row.pack(fill="x", pady=6)
            badge = tk.Canvas(row, width=26, height=26, bg="#0d1a26", highlightthickness=0)
            badge.pack(side="left", anchor="n")
            img = theme.gradient_photo(f"help-badge-{num}", 26, 26, theme.START_TOP, theme.START_BOTTOM,
                                        13, theme.START_BORDER)
            badge.create_image(0, 0, image=img, anchor="nw")
            badge.image = img
            badge.create_text(13, 13, text=num, font=theme.korean(12, "bold"), fill=theme.START_TEXT)
            txt = tk.Frame(row, bg="#0d1a26")
            txt.pack(side="left", fill="x", expand=True, padx=(12, 0))
            tk.Label(txt, text=title, bg="#0d1a26", fg="#dbe6f3", font=theme.korean(13, "bold"),
                      anchor="w").pack(fill="x")
            tk.Label(txt, text=desc, bg="#0d1a26", fg=theme.TEXT_MUTED3, font=theme.korean(11),
                      anchor="w", justify="left", wraplength=440).pack(fill="x", pady=(2, 0))

        tk.Label(body, text="문제 해결", bg="#0d1a26", fg=theme.HEADER_TEXT,
                  font=theme.korean(15, "bold"), anchor="w").pack(fill="x", pady=(18, 8))
        tk.Frame(body, bg=theme.HEADER_BORDER, height=1).pack(fill="x", pady=(0, 10))
        for title, desc in self.TIPS:
            card = tk.Frame(body, bg="#0e1c28", highlightthickness=1, highlightbackground=theme.ROW_BORDER)
            card.pack(fill="x", pady=4)
            inner = tk.Frame(card, bg="#0e1c28")
            inner.pack(fill="x", padx=12, pady=9)
            tk.Label(inner, text=title, bg="#0e1c28", fg=theme.START_TEXT, font=theme.korean(12, "bold"),
                      width=14, anchor="w", justify="left").pack(side="left", anchor="n")
            tk.Label(inner, text=desc, bg="#0e1c28", fg=theme.TEXT_MUTED3, font=theme.korean(11),
                      anchor="w", justify="left", wraplength=340).pack(side="left", fill="x", expand=True)

        footer = tk.Frame(body, bg="#0d1a26")
        footer.pack(fill="x", pady=(16, 0))
        tk.Label(footer, text=f"WOW Launcher v{APP_VERSION}  ·  제작: zardkim", bg="#0d1a26",
                  fg=theme.TEXT_MUTED3, font=theme.korean(10)).pack(side="left")

        close_btn = GradientButton(
            footer, "닫기", self.destroy, 90, 32,
            theme.START_TOP, theme.START_BOTTOM, theme.START_BORDER, theme.START_TEXT,
            hover_border=theme.START_HOVER_BORDER, hover_text_color=theme.START_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="help-close",
        )
        close_btn.pack(side="right")


# ==================== 계정 관리 창 ====================
class AccountManageDialog(tk.Toplevel):
    """AzerothCore GM 명령(계정 생성/비밀번호 변경/GM 권한/전체저장)을 SOAP 로 실행.
    https://www.azerothcore.org/wiki/gm-commands 참고. 명령을 직접 입력하지 않고
    버튼 → 입력 폼 → 명령 자동 조립 방식으로 만든다."""

    MODES = [
        ("create", "계정 생성"),
        ("password", "비밀번호 변경"),
        ("gmlevel", "GM 권한 설정"),
        ("saveall", "전체 저장"),
    ]

    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("계정 관리")
        self.configure(bg="#0d1a26")
        center_on_screen(self, 560, 540)
        self.resizable(False, False)
        self.transient(app.root)
        self.grab_set()

        body = tk.Frame(self, bg="#0d1a26", width=560, height=540)
        body.pack(fill="both", expand=True)

        btn_row = tk.Frame(body, bg="#0d1a26")
        btn_row.pack(fill="x", padx=16, pady=(16, 0))
        for mode, label in self.MODES:
            GradientButton(
                btn_row, label, lambda m=mode: self._select_mode(m), 122, 30,
                theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
                hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
                font=theme.korean(11, "bold"), radius=3, container_bg="#0d1a26", key=f"mode-{mode}",
            ).pack(side="left", padx=(0, 6))

        tk.Frame(body, bg=theme.HEADER_BORDER, height=1).pack(fill="x", padx=16, pady=(12, 0))

        self.form_frame = tk.Frame(body, bg="#0d1a26")
        self.form_frame.pack(fill="x", padx=16, pady=(12, 8))

        tk.Label(body, text="결과", bg="#0d1a26", fg=theme.LABEL_MUTED,
                  font=theme.korean(11), anchor="w").pack(fill="x", padx=16)

        result_wrap = tk.Frame(body, bg="#0d1a26")
        result_wrap.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        # 화면에 늘 보이는 스크롤바(윈도우 기본 회색 스타일이라 어두운 테마와 안 어울림)
        # 대신, 마우스 휠로는 그대로 스크롤할 수 있게 Text 위젯만 둔다.
        self.result_text = tk.Text(
            result_wrap, bg=theme.INPUT_BG, fg=theme.INPUT_TEXT, insertbackground=theme.INPUT_TEXT,
            relief="flat", highlightthickness=1, highlightbackground=theme.INPUT_BORDER,
            font=theme.mono(10), wrap="word", state="disabled",
        )
        self.result_text.pack(side="left", fill="both", expand=True)

        self._select_mode("create")

    # ---------------- 입력 폼 ----------------
    def _entry(self, parent, label, show=None):
        wrap = tk.Frame(parent, bg="#0d1a26")
        wrap.pack(fill="x", pady=(0, 8))
        tk.Label(wrap, text=label, bg="#0d1a26", fg=theme.LABEL_MUTED,
                  font=theme.korean(11), width=10, anchor="w").pack(side="left")
        var = tk.StringVar()
        tk.Entry(wrap, textvariable=var, bg=theme.INPUT_BG, fg=theme.INPUT_TEXT,
                  insertbackground=theme.INPUT_TEXT, relief="flat",
                  highlightthickness=1, highlightbackground=theme.INPUT_BORDER,
                  font=theme.mono(11), show=show).pack(side="left", fill="x", expand=True, ipady=4)
        return var

    def _run_button(self, parent, on_click):
        GradientButton(
            parent, "실행", on_click, 90, 30,
            theme.START_TOP, theme.START_BOTTOM, theme.START_BORDER, theme.START_TEXT,
            hover_border=theme.START_HOVER_BORDER, hover_text_color=theme.START_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="account-run",
        ).pack(anchor="e", pady=(4, 0))

    def _select_mode(self, mode):
        for w in self.form_frame.winfo_children():
            w.destroy()

        if mode == "create":
            name_var = self._entry(self.form_frame, "계정명")
            pw_var = self._entry(self.form_frame, "비밀번호", show="*")
            self._run_button(self.form_frame, lambda: self._run(
                f"account create {name_var.get().strip()} {pw_var.get()}",
                require=(name_var.get().strip(), pw_var.get())))
        elif mode == "password":
            name_var = self._entry(self.form_frame, "계정명")
            pw_var = self._entry(self.form_frame, "새 비밀번호", show="*")
            self._run_button(self.form_frame, lambda: self._run(
                f"account set password {name_var.get().strip()} {pw_var.get()} {pw_var.get()}",
                require=(name_var.get().strip(), pw_var.get())))
        elif mode == "gmlevel":
            name_var = self._entry(self.form_frame, "계정명")
            self._run_button(self.form_frame, lambda: self._run(
                f"account set gmlevel {name_var.get().strip()} 3 -1",
                require=(name_var.get().strip(),)))
        elif mode == "saveall":
            tk.Label(self.form_frame, text="현재 서버 상태를 즉시 저장합니다.",
                      bg="#0d1a26", fg=theme.TEXT_MUTED3, font=theme.korean(11)).pack(anchor="w")
            self._run_button(self.form_frame, lambda: self._run("saveall", require=()))

    # ---------------- 명령 실행 ----------------
    def _append_result(self, text):
        self.result_text.config(state="normal")
        self.result_text.insert("end", text + "\n")
        self.result_text.see("end")
        self.result_text.config(state="disabled")

    def _run(self, command, require):
        if any(not v for v in require):
            self._append_result("계정명/비밀번호를 입력하세요.")
            return
        if self.app._last_status.get("worldserver") != RUNNING:
            self._append_result("월드 서버가 실행 중이 아닙니다. 먼저 서버를 켜세요.")
            return
        gm_account = self.app.cfg.get("gm_account", "")
        gm_password = self.app.cfg.get("gm_password", "")
        if not gm_account or not gm_password:
            self._append_result("설정(⚙) > GM 계정 에서 GM 계정을 먼저 지정하세요.")
            return

        self._append_result(f"> {command}")
        host = self.app.soap_host()
        port = int(self.app.cfg.get("soap_port", 7878))

        def worker():
            ok, msg = soap_client.execute_command(host, port, gm_account, gm_password, command, timeout=10)
            self.after(0, lambda: self._append_result(msg))

        threading.Thread(target=worker, daemon=True).start()


# ==================== GM 명령 콘솔 창 ====================
class GmConsoleDialog(tk.Toplevel):
    """"월드 서버" 카드의 GM 버튼 - 미리 만들어둔 폼(AccountManageDialog) 대신
    아무 GM 명령이나 직접 입력해서 실행한다. 검증/실행/결과 표시 흐름은
    AccountManageDialog._run 과 동일(soap_client.execute_command 는 원래
    범용이라 새 실행 로직이 필요 없음) - 다만 프리셋 폼 없이 입력창 하나로
    구성된 순수 콘솔이다."""

    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("GM 명령 콘솔")
        self.configure(bg="#0d1a26")
        center_on_screen(self, 560, 460)
        self.resizable(False, False)
        self.transient(app.root)
        self.grab_set()

        body = tk.Frame(self, bg="#0d1a26", width=560, height=460)
        body.pack(fill="both", expand=True)

        input_row = tk.Frame(body, bg="#0d1a26")
        input_row.pack(fill="x", padx=16, pady=(16, 0))
        self.command_var = tk.StringVar()
        entry = tk.Entry(input_row, textvariable=self.command_var, bg=theme.INPUT_BG, fg=theme.INPUT_TEXT,
                          insertbackground=theme.INPUT_TEXT, relief="flat",
                          highlightthickness=1, highlightbackground=theme.INPUT_BORDER,
                          font=theme.mono(11))
        entry.pack(side="left", fill="x", expand=True, ipady=5)
        entry.bind("<Return>", lambda e: self._run())
        entry.focus_set()
        GradientButton(
            input_row, "실행", self._run, 70, 30,
            theme.START_TOP, theme.START_BOTTOM, theme.START_BORDER, theme.START_TEXT,
            hover_border=theme.START_HOVER_BORDER, hover_text_color=theme.START_HOVER_TEXT,
            font=theme.korean(12, "bold"), radius=3, container_bg="#0d1a26", key="gm-console-run",
        ).pack(side="left", padx=(6, 0))

        tk.Label(body, text="예: server info, account onlinelist, pinfo 캐릭터명 (점 없이 입력)",
                  bg="#0d1a26", fg=theme.TEXT_MUTED3, font=theme.korean(9),
                  anchor="w").pack(fill="x", padx=16, pady=(4, 0))

        result_head = tk.Frame(body, bg="#0d1a26")
        result_head.pack(fill="x", padx=16, pady=(12, 0))
        tk.Label(result_head, text="결과", bg="#0d1a26", fg=theme.LABEL_MUTED,
                  font=theme.korean(11), anchor="w").pack(side="left")
        GradientButton(
            result_head, "지우기", self._clear, 70, 24,
            theme.BROWSE_TOP, theme.BROWSE_BOTTOM, theme.BROWSE_BORDER, theme.BROWSE_TEXT,
            hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
            font=theme.korean(10, "bold"), radius=3, container_bg="#0d1a26", key="gm-console-clear",
        ).pack(side="right")

        result_wrap = tk.Frame(body, bg="#0d1a26")
        result_wrap.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        self.result_text = tk.Text(
            result_wrap, bg=theme.INPUT_BG, fg=theme.INPUT_TEXT, insertbackground=theme.INPUT_TEXT,
            relief="flat", highlightthickness=1, highlightbackground=theme.INPUT_BORDER,
            font=theme.mono(10), wrap="word", state="disabled",
        )
        self.result_text.pack(side="left", fill="both", expand=True)

    def _append_result(self, text):
        self.result_text.config(state="normal")
        self.result_text.insert("end", text + "\n")
        self.result_text.see("end")
        self.result_text.config(state="disabled")

    def _clear(self):
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.config(state="disabled")

    def _run(self, _event=None):
        command = self.command_var.get().strip()
        if not command:
            return
        if self.app._last_status.get("worldserver") != RUNNING:
            self._append_result("월드 서버가 실행 중이 아닙니다. 먼저 서버를 켜세요.")
            return
        gm_account = self.app.cfg.get("gm_account", "")
        gm_password = self.app.cfg.get("gm_password", "")
        if not gm_account or not gm_password:
            self._append_result("설정(⚙) > GM 계정 에서 GM 계정을 먼저 지정하세요.")
            return

        self._append_result(f"> {command}")
        self.command_var.set("")
        host = self.app.soap_host()
        port = int(self.app.cfg.get("soap_port", 7878))

        def worker():
            ok, msg = soap_client.execute_command(host, port, gm_account, gm_password, command, timeout=10)
            self.after(0, lambda: self._append_result(msg))

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    LauncherApp().run()
