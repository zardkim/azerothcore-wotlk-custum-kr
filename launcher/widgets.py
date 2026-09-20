# -*- coding: utf-8 -*-
"""목업의 그라디언트 버튼 / 상태 점 / 토글 스위치를 흉내내는 재사용 위젯들.
Tkinter 기본 위젯은 그라디언트/둥근모서리를 지원하지 않으므로 Canvas + PIL 로 그린다."""
import tkinter as tk

import theme
from tooltip import Tooltip


class GradientButton(tk.Canvas):
    def __init__(self, parent, text, command=None, width=120, height=32,
                 top="#2b3f55", bottom="#101d2a", border="#7d6733", text_color="#e2d3a4",
                 hover_top=None, hover_bottom=None, hover_border=None, hover_text_color=None,
                 disabled_top=None, disabled_bottom=None, disabled_border=None, disabled_text_color=None,
                 font=None, radius=3, border_width=1, container_bg="#071019", key=None, tooltip=None):
        super().__init__(parent, width=width, height=height, highlightthickness=0,
                          bg=container_bg, cursor="hand2")
        self.command = command
        self.enabled = True
        self.font = font or theme.korean(10, "bold")
        self.text = text
        self._bw, self._bh = width, height

        k = key or f"btn{id(self)}"
        self.normal_img = theme.gradient_photo(f"{k}-n", width, height, top, bottom, radius, border, border_width)
        self.hover_img = theme.gradient_photo(
            f"{k}-h", width, height,
            hover_top or top, hover_bottom or bottom, radius,
            hover_border or border, border_width,
        )
        d_top = disabled_top or (40, 40, 40)
        d_bottom = disabled_bottom or (20, 20, 20)
        self.disabled_img = theme.gradient_photo(
            f"{k}-d", width, height, d_top, d_bottom, radius,
            disabled_border or "#333333", border_width,
        )

        self.normal_text = text_color
        self.hover_text = hover_text_color or text_color
        self.disabled_text = disabled_text_color or "#666666"

        self.img_id = self.create_image(0, 0, anchor="nw", image=self.normal_img)
        self.text_id = self.create_text(width // 2, height // 2, text=text,
                                         fill=self.normal_text, font=self.font)

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.tooltip = Tooltip(self, tooltip) if tooltip else None

    def _on_enter(self, _e):
        if self.enabled:
            self.itemconfig(self.img_id, image=self.hover_img)
            self.itemconfig(self.text_id, fill=self.hover_text)

    def _on_leave(self, _e):
        if self.enabled:
            self.itemconfig(self.img_id, image=self.normal_img)
            self.itemconfig(self.text_id, fill=self.normal_text)

    def _on_click(self, _e):
        if self.enabled and self.command:
            self.command()

    def set_enabled(self, enabled):
        self.enabled = enabled
        if enabled:
            self.itemconfig(self.img_id, image=self.normal_img)
            self.itemconfig(self.text_id, fill=self.normal_text)
            self.config(cursor="hand2")
        else:
            self.itemconfig(self.img_id, image=self.disabled_img)
            self.itemconfig(self.text_id, fill=self.disabled_text)
            self.config(cursor="arrow")

    def set_text(self, text):
        self.itemconfig(self.text_id, text=text)


class StatusDot(tk.Canvas):
    def __init__(self, parent, size=12, container_bg="#0e1c28", tooltip=None):
        super().__init__(parent, width=size, height=size, highlightthickness=0, bg=container_bg)
        self.size = size
        pad = 1
        self.glow_id = self.create_oval(pad, pad, size - pad, size - pad, fill="#4a1c1c", outline="")
        inset = size * 0.22
        self.core_id = self.create_oval(inset, inset, size - inset, size - inset, fill="#7e2a2a", outline="")
        self.tooltip = Tooltip(self, tooltip) if tooltip else None

    def set_status(self, status_key):
        core, glow = theme.status_colors(status_key)
        self.itemconfig(self.glow_id, fill=glow)
        self.itemconfig(self.core_id, fill=core)


class ToggleSwitch(tk.Canvas):
    def __init__(self, parent, value=False, command=None, width=52, height=24, container_bg="#0d1a26",
                 tooltip=None):
        super().__init__(parent, width=width, height=height, highlightthickness=0,
                          bg=container_bg, cursor="hand2")
        self.value = value
        self.command = command
        self._bw, self._bh = width, height
        self.tooltip = Tooltip(self, tooltip) if tooltip else None
        r = height // 2
        self.on_img = theme.gradient_photo("toggle-on", width, height,
                                            theme.TOGGLE_ON_TOP, theme.TOGGLE_ON_BOTTOM,
                                            r, theme.TOGGLE_ON_BORDER, 1)
        self.off_img = theme.flat_photo("toggle-off", width, height,
                                         (13, 22, 32), r, theme.TOGGLE_OFF_BORDER, 1)
        self.img_id = self.create_image(0, 0, anchor="nw")
        knob_r = (height - 6) // 2
        self.knob_id = self.create_oval(0, 0, knob_r * 2, knob_r * 2, outline="")
        self._knob_r = knob_r
        self.bind("<Button-1>", self._on_click)
        self._redraw()

    def _redraw(self):
        pad = 3
        if self.value:
            self.itemconfig(self.img_id, image=self.on_img)
            self.itemconfig(self.knob_id, fill=theme.TOGGLE_KNOB_ON)
            x = self._bw - pad - self._knob_r * 2
        else:
            self.itemconfig(self.img_id, image=self.off_img)
            self.itemconfig(self.knob_id, fill=theme.TOGGLE_KNOB_OFF)
            x = pad
        y = (self._bh - self._knob_r * 2) // 2
        self.coords(self.knob_id, x, y, x + self._knob_r * 2, y + self._knob_r * 2)

    def _on_click(self, _e):
        self.set(not self.value)
        if self.command:
            self.command(self.value)

    def set(self, value):
        self.value = bool(value)
        self._redraw()

    def get(self):
        return self.value
