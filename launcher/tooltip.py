# -*- coding: utf-8 -*-
"""마우스를 올리면 잠깐 뒤에 뜨는 설명 풍선(툴팁). 런처의 어두운 남색 테마에 맞춘
작은 Toplevel 하나로 구현한다 - 버튼/아이콘처럼 실제 tkinter 위젯에는 Tooltip 을,
캔버스에 직접 그린 아이콘(점/텍스트)에는 attach_canvas_item 을 쓴다."""
import tkinter as tk

import theme

_DELAY_MS = 450


class Tooltip:
    """widget 에 <Enter>/<Leave> 를 붙여서, 일정 시간 마우스가 머무르면 그 아래에
    설명을 띄운다. 기존에 그 위젯에 바인딩된 <Enter>/<Leave> 핸들러(커서 모양 변경
    등)를 덮어쓰지 않도록 항상 add="+" 로 붙인다."""

    def __init__(self, widget, text, delay=_DELAY_MS, wraplength=260):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.wraplength = wraplength
        self.tip = None
        self._after_id = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._unschedule, add="+")
        widget.bind("<Button-1>", self._unschedule, add="+")

    def set_text(self, text):
        self.text = text

    def _schedule(self, _e=None):
        self._unschedule()
        if self.text:
            self._after_id = self.widget.after(self.delay, self._show)

    def _unschedule(self, _e=None):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        self._hide()

    def _show(self):
        if self.tip is not None or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except tk.TclError:
            return
        _show_at(self, x, y)

    def _hide(self):
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


def _show_at(owner, x, y):
    tip = tk.Toplevel(owner.widget)
    owner.tip = tip
    tip.wm_overrideredirect(True)
    try:
        tip.wm_attributes("-topmost", True)
    except tk.TclError:
        pass
    frame = tk.Frame(tip, bg=theme.ICON_HOVER_BORDER, padx=1, pady=1)
    frame.pack()
    tk.Label(frame, text=owner.text, justify="left", bg="#12212f", fg="#e8dfc8",
             font=theme.korean(10), wraplength=owner.wraplength, padx=8, pady=5).pack()
    tip.update_idletasks()
    tw, th = tip.winfo_width(), tip.winfo_height()
    sw, sh = tip.winfo_screenwidth(), tip.winfo_screenheight()
    x -= tw // 2
    x = max(2, min(x, sw - tw - 2))
    if y + th > sh:
        y = max(2, y - th - 34)
    tip.wm_geometry(f"+{x}+{y}")


class _CanvasItemTooltip:
    """캔버스 위에 직접 그린 아이템(create_oval/create_text 등, 별도 위젯이 아님)용.
    위젯이 없으니 캔버스 자체를 기준으로 after 를 걸고, 이벤트의 x_root/y_root 로
    위치를 잡는다."""

    def __init__(self, canvas, text, wraplength=260):
        self.widget = canvas
        self.text = text
        self.wraplength = wraplength
        self.tip = None
        self._after_id = None

    def set_text(self, text):
        self.text = text

    def _schedule(self, event):
        self._unschedule()
        rootx, rooty = event.x_root, event.y_root
        self._after_id = self.widget.after(_DELAY_MS, lambda: self._show(rootx, rooty))

    def _unschedule(self, _e=None):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        self._hide()

    def _show(self, rootx, rooty):
        if self.tip is not None or not self.text:
            return
        _show_at(self, rootx, rooty + 16)

    def _hide(self):
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


def attach_canvas_item(canvas, item_id, text, wraplength=260):
    """canvas.create_*() 가 반환한 item_id (또는 태그) 하나에 툴팁을 붙인다.
    같은 텍스트를 여러 item_id 에 붙이고 싶으면 그만큼 반복 호출하면 된다."""
    tt = _CanvasItemTooltip(canvas, text, wraplength=wraplength)
    canvas.tag_bind(item_id, "<Enter>", tt._schedule, add="+")
    canvas.tag_bind(item_id, "<Leave>", tt._unschedule, add="+")
    canvas.tag_bind(item_id, "<Button-1>", tt._unschedule, add="+")
    return tt
