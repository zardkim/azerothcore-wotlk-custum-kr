# -*- coding: utf-8 -*-
"""클라이언트 설치 폴더를 나중에 다른 위치로 옮겼을 때, 런처가 그 새 위치를 다시
가리키도록 지정하는 설정 대화상자. 메인 창(overrideredirect)과 달리 표준 OS
타이틀바를 쓰는 단순한 Toplevel로 만든다 - 자주 여닫는 창이 아니라서 커스텀 크롬을
그대로 복제할 필요는 없다."""
import os
import tkinter as tk
from tkinter import filedialog

import theme
from widgets import GradientButton


def _hexcolor(c):
    if isinstance(c, str):
        return c
    return "#%02x%02x%02x" % c


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, current_dir, icon_path=None):
        super().__init__(parent)
        self.result = None
        self._dir = current_dir

        bg = _hexcolor(theme.CONTENT_BG_BOTTOM)
        self.title("설정")
        self.configure(bg=bg)
        self.resizable(False, False)
        self.transient(parent)
        if icon_path and os.path.isfile(icon_path):
            try:
                self.iconbitmap(icon_path)
            except tk.TclError:
                pass

        W, PAD = 460, 20

        tk.Label(self, text="클라이언트 설치 폴더", bg=bg, fg=theme.HEADER_TEXT,
                 font=theme.korean(12, "bold")).pack(anchor="w", padx=PAD, pady=(PAD, 4))
        tk.Label(self, text="게임 폴더를 다른 위치로 옮겼다면 여기서 새 위치를 지정하세요.",
                 bg=bg, fg=theme.LABEL_MUTED, font=theme.korean(10), wraplength=W - PAD * 2,
                 justify="left").pack(anchor="w", padx=PAD)

        row = tk.Frame(self, bg=bg)
        row.pack(fill="x", padx=PAD, pady=(10, 4))
        self.path_var = tk.StringVar(value=current_dir)
        entry = tk.Entry(row, textvariable=self.path_var, state="readonly",
                          readonlybackground=theme.INPUT_BG, fg=theme.INPUT_TEXT,
                          relief="flat", font=theme.korean(10))
        entry.pack(side="left", fill="x", expand=True, ipady=4)
        browse_btn = GradientButton(
            row, "찾아보기", command=self._browse, width=84, height=28,
            top=theme.BROWSE_TOP, bottom=theme.BROWSE_BOTTOM, border=theme.BROWSE_BORDER,
            text_color=theme.BROWSE_TEXT,
            hover_top=theme.BROWSE_TOP, hover_bottom=theme.BROWSE_BOTTOM,
            hover_border=theme.BROWSE_HOVER_BORDER, hover_text_color=theme.BROWSE_HOVER_TEXT,
            font=theme.korean(10, "bold"), radius=3, container_bg=bg,
        )
        browse_btn.pack(side="left", padx=(8, 0))

        self.hint_id = tk.Label(self, text="", bg=bg, fg="#e6b9a4", font=theme.korean(9))
        self.hint_id.pack(anchor="w", padx=PAD, pady=(0, 8))
        self._refresh_hint()

        btn_row = tk.Frame(self, bg=bg)
        btn_row.pack(fill="x", padx=PAD, pady=(0, PAD))
        ok_btn = GradientButton(
            btn_row, "확인", command=self._confirm, width=90, height=32,
            top=theme.PLAY_UP_TOP, bottom=theme.PLAY_UP_BOTTOM, border=theme.PLAY_UP_BORDER,
            text_color=theme.PLAY_UP_TEXT, font=theme.korean(10, "bold"), radius=3, container_bg=bg,
        )
        ok_btn.pack(side="right")
        cancel_btn = GradientButton(
            btn_row, "취소", command=self._cancel, width=90, height=32,
            top=theme.PLAY_DOWN_TOP, bottom=theme.PLAY_DOWN_BOTTOM, border=theme.PLAY_DOWN_BORDER,
            text_color=theme.PLAY_DOWN_TEXT, font=theme.korean(10, "bold"), radius=3, container_bg=bg,
        )
        cancel_btn.pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.update_idletasks()
        self._center_on(parent, W)
        self.grab_set()
        self.focus_set()

    def _center_on(self, parent, w):
        self.update_idletasks()
        h = self.winfo_reqheight()
        try:
            px, py = parent.winfo_x(), parent.winfo_y()
            pw, ph = parent.winfo_width(), parent.winfo_height()
        except tk.TclError:
            px, py, pw, ph = 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _refresh_hint(self):
        exists = bool(self._dir) and os.path.isdir(self._dir)
        self.hint_id.config(
            text="" if exists else "이 폴더는 아직 존재하지 않습니다.",
        )

    def _browse(self):
        chosen = filedialog.askdirectory(parent=self, title="클라이언트 폴더 선택",
                                          initialdir=self._dir or os.path.expanduser("~"),
                                          mustexist=True)
        if chosen:
            self._dir = chosen
            self.path_var.set(chosen)
            self._refresh_hint()

    def _confirm(self):
        self.result = self._dir
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()
