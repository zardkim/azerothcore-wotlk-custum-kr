# -*- coding: utf-8 -*-
"""숨겨진 관리자 모드 창 (메인 창에서 Ctrl+Shift 를 누른 채 ⚙ 를 클릭해야 열림 -
app.py 참고). 일반 플레이어용 배포판에는 admin_config.json 이 없으므로 처음 열면
접속 정보 입력 폼부터 보여주고, 이미 설정돼 있으면 바로 백업 목록으로 들어간다.

SSH나 서버 쪽 스크립트를 거치지 않고, HeidiSQL 등과 똑같이 host/port/계정으로
DB에 직접 접속해서 백업/복원한다(db_backup.py, pymysql) - 서버에 아무것도 미리
올려둘 필요가 없다."""
import os
import threading
import tkinter as tk
from tkinter import messagebox

import admin_config
import db_backup
import paths
import theme
from widgets import GradientButton


def _hexcolor(c):
    if isinstance(c, str):
        return c
    return "#%02x%02x%02x" % c


class AdminDialog(tk.Toplevel):
    def __init__(self, parent, icon_path=None):
        super().__init__(parent)
        self.bg = _hexcolor(theme.CONTENT_BG_BOTTOM)
        self.title("관리자 모드")
        self.configure(bg=self.bg)
        self.resizable(False, False)
        self.transient(parent)
        if icon_path:
            try:
                self.iconbitmap(icon_path)
            except tk.TclError:
                pass

        self.body = tk.Frame(self, bg=self.bg)
        self.body.pack(fill="both", expand=True)

        # 백업 파일은 이 컴퓨터(런처가 실행되는 PC)에 저장한다 - 서버에는 남기지 않음.
        self.local_dir = os.path.join(paths.BASE_DIR, "backups")

        self.cfg = admin_config.load_admin_config()
        if admin_config.is_configured(self.cfg):
            self._build_backup_view()
        else:
            self._build_setup_view()

        self.update_idletasks()
        self._center_on(parent)
        self.grab_set()
        self.focus_set()

    def _center_on(self, parent):
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        try:
            px, py = parent.winfo_x(), parent.winfo_y()
            pw, ph = parent.winfo_width(), parent.winfo_height()
        except tk.TclError:
            px, py, pw, ph = 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _clear_body(self):
        for w in self.body.winfo_children():
            w.destroy()

    # ==================== 접속 정보 입력 ====================
    def _build_setup_view(self):
        self._clear_body()
        W, PAD = 440, 20
        tk.Label(self.body, text="관리자 DB 접속 정보", bg=self.bg, fg=theme.HEADER_TEXT,
                 font=theme.korean(13, "bold")).pack(anchor="w", padx=PAD, pady=(PAD, 4))
        tk.Label(self.body, text="HeidiSQL 등으로 접속할 때와 같은 정보입니다. 이 PC에만 "
                                  "저장되고(admin_config.json), 배포용 빌드에는 절대 포함되지 않습니다.",
                 bg=self.bg, fg=theme.LABEL_MUTED, font=theme.korean(10), wraplength=W - PAD * 2,
                 justify="left").pack(anchor="w", padx=PAD, pady=(0, 10))

        self._fields = {}

        def field(label, key, show=None):
            tk.Label(self.body, text=label, bg=self.bg, fg=theme.LABEL_MUTED,
                     font=theme.korean(11)).pack(anchor="w", padx=PAD, pady=(6, 0))
            var = tk.StringVar(value=str(self.cfg.get(key, "")))
            self._fields[key] = var
            tk.Entry(self.body, textvariable=var, bg=theme.INPUT_BG, fg=theme.INPUT_TEXT,
                     insertbackground=theme.INPUT_TEXT, relief="flat",
                     highlightthickness=1, highlightbackground=theme.INPUT_BORDER,
                     font=theme.mono(11), show=show).pack(fill="x", padx=PAD, ipady=4)

        field("호스트 (서버 주소)", "db_host")
        field("포트", "db_port")
        field("DB 사용자", "db_user")
        field("DB 비밀번호", "db_password", show="*")
        field("계정 DB 이름", "auth_db")
        field("캐릭터 DB 이름", "char_db")
        field("봇 계정 접두어 (기본 rndbot)", "bot_prefix")

        self._test_status = tk.StringVar(value="")
        tk.Label(self.body, textvariable=self._test_status, bg=self.bg, fg=theme.TEXT_MUTED3,
                 font=theme.korean(10, "bold"), wraplength=W - PAD * 2, justify="left",
                 anchor="w").pack(fill="x", padx=PAD, pady=(10, 0))

        btn_row = tk.Frame(self.body, bg=self.bg)
        btn_row.pack(fill="x", padx=PAD, pady=(10, PAD))
        GradientButton(
            btn_row, "저장", command=self._save_setup, width=90, height=32,
            top=theme.PLAY_UP_TOP, bottom=theme.PLAY_UP_BOTTOM, border=theme.PLAY_UP_BORDER,
            text_color=theme.PLAY_UP_TEXT, font=theme.korean(11, "bold"), radius=3, container_bg=self.bg,
        ).pack(side="right")
        GradientButton(
            btn_row, "닫기", command=self.destroy, width=90, height=32,
            top=theme.PLAY_DOWN_TOP, bottom=theme.PLAY_DOWN_BOTTOM, border=theme.PLAY_DOWN_BORDER,
            text_color=theme.PLAY_DOWN_TEXT, font=theme.korean(11, "bold"), radius=3, container_bg=self.bg,
        ).pack(side="right", padx=(0, 8))
        GradientButton(
            btn_row, "연결 테스트", command=self._test_connection, width=100, height=32,
            top=theme.BROWSE_TOP, bottom=theme.BROWSE_BOTTOM, border=theme.BROWSE_BORDER,
            text_color=theme.BROWSE_TEXT, font=theme.korean(11, "bold"), radius=3, container_bg=self.bg,
        ).pack(side="left")

    def _collect_setup_fields(self):
        for key, var in self._fields.items():
            self.cfg[key] = var.get().strip()
        try:
            self.cfg["db_port"] = int(self.cfg.get("db_port") or 3307)
        except ValueError:
            self.cfg["db_port"] = 3307
        if not self.cfg.get("bot_prefix"):
            self.cfg["bot_prefix"] = "rndbot"

    def _test_connection(self):
        self._collect_setup_fields()
        self._test_status.set("연결 확인 중...")

        def worker():
            ok, msg = db_backup.test_connection(
                self.cfg["db_host"], self.cfg["db_port"], self.cfg["db_user"], self.cfg["db_password"])
            self.after(0, lambda: self._test_status.set(("✅ " if ok else "❌ ") + msg))

        threading.Thread(target=worker, daemon=True).start()

    def _save_setup(self):
        self._collect_setup_fields()
        admin_config.save_admin_config(self.cfg)
        # 값이 일부만 채워져 있어도 저장은 항상 하고 넘어간다 - 백업 목록 화면
        # 쪽에서 필요한 값이 비어 있으면 그때 에러로 안내한다(저장 버튼이 아무
        # 반응 없는 것처럼 보이는 걸 방지 - 실제로 겪은 버그).
        self._build_backup_view()

    # ==================== 백업 목록 / 생성 / 복원 ====================
    def _conn(self):
        c = self.cfg
        return (c.get("db_host", ""), int(c.get("db_port") or 3307),
                c.get("db_user", ""), c.get("db_password", ""),
                c.get("auth_db", "acore_auth"), c.get("char_db", "acore_characters"),
                c.get("bot_prefix", "rndbot"))

    def _build_backup_view(self):
        self._clear_body()
        W, PAD = 600, 16

        top_row = tk.Frame(self.body, bg=self.bg)
        top_row.pack(fill="x", padx=PAD, pady=(PAD, 0))
        tk.Label(top_row, text="계정/캐릭터 백업", bg=self.bg, fg=theme.HEADER_TEXT,
                 font=theme.korean(14, "bold")).pack(side="left")
        GradientButton(
            top_row, "접속 정보 수정", command=self._build_setup_view, width=110, height=28,
            top=theme.BROWSE_TOP, bottom=theme.BROWSE_BOTTOM, border=theme.BROWSE_BORDER,
            text_color=theme.BROWSE_TEXT, font=theme.korean(11, "bold"), radius=3, container_bg=self.bg,
        ).pack(side="right")

        action_row = tk.Frame(self.body, bg=self.bg)
        action_row.pack(fill="x", padx=PAD, pady=(8, 0))
        self.btn_backup = GradientButton(
            action_row, "새 백업 만들기", command=self._run_backup, width=140, height=32,
            top=theme.PLAY_UP_TOP, bottom=theme.PLAY_UP_BOTTOM, border=theme.PLAY_UP_BORDER,
            text_color=theme.PLAY_UP_TEXT, font=theme.korean(12, "bold"), radius=3, container_bg=self.bg,
        )
        self.btn_backup.pack(side="left")
        self.btn_refresh = GradientButton(
            action_row, "새로고침", command=self._refresh_list, width=100, height=32,
            top=theme.BROWSE_TOP, bottom=theme.BROWSE_BOTTOM, border=theme.BROWSE_BORDER,
            text_color=theme.BROWSE_TEXT, font=theme.korean(12, "bold"), radius=3, container_bg=self.bg,
        )
        self.btn_refresh.pack(side="left", padx=(8, 0))

        tk.Label(self.body, text=f"저장 위치: {self.local_dir}", bg=self.bg, fg=theme.TEXT_MUTED3,
                 font=theme.mono(10), anchor="w", wraplength=W - PAD * 2).pack(fill="x", padx=PAD, pady=(6, 0))

        self.list_frame = tk.Frame(self.body, bg=self.bg, width=W - PAD * 2, height=180)
        self.list_frame.pack(fill="x", padx=PAD, pady=(10, 8))
        self.list_frame.pack_propagate(False)

        tk.Label(self.body, text="실행 로그", bg=self.bg, fg=theme.LABEL_MUTED,
                 font=theme.korean(11)).pack(anchor="w", padx=PAD)
        self.result_text = tk.Text(
            self.body, width=70, height=10, bg=theme.INPUT_BG, fg=theme.INPUT_TEXT,
            insertbackground=theme.INPUT_TEXT, relief="flat", highlightthickness=1,
            highlightbackground=theme.INPUT_BORDER, font=theme.mono(12), wrap="word", state="disabled",
        )
        self.result_text.pack(fill="both", expand=True, padx=PAD, pady=(4, PAD))

        self._refresh_list()

    def _append_result(self, text):
        self.result_text.config(state="normal")
        self.result_text.insert("end", text + "\n")
        self.result_text.see("end")
        self.result_text.config(state="disabled")

    def _set_busy(self, busy):
        self.btn_backup.set_enabled(not busy)
        self.btn_refresh.set_enabled(not busy)

    def _refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        tk.Label(self.list_frame, text="불러오는 중...", bg=self.bg,
                 fg=theme.TEXT_MUTED3, font=theme.korean(11)).pack(anchor="w", pady=6)

        def worker():
            backups, err = db_backup.list_local_backups(self.local_dir)
            self.after(0, lambda: self._apply_list(backups, err))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_list(self, backups, err):
        for w in self.list_frame.winfo_children():
            w.destroy()
        if err:
            tk.Label(self.list_frame, text=err, bg=self.bg, fg=theme.STOP_TEXT,
                     font=theme.korean(11), wraplength=560, justify="left",
                     anchor="w").pack(anchor="w", pady=6)
            return
        if not backups:
            tk.Label(self.list_frame, text="아직 백업이 없습니다.", bg=self.bg,
                     fg=theme.TEXT_MUTED3, font=theme.korean(11)).pack(anchor="w", pady=6)
            return
        canvas = tk.Canvas(self.list_frame, bg=self.bg, highlightthickness=0)
        scrollbar = tk.Scrollbar(self.list_frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=self.bg)
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
        row = tk.Frame(parent, bg=theme.INPUT_BG, highlightthickness=1, highlightbackground=theme.ROW_BORDER)
        row.pack(fill="x", pady=(0, 6))
        inner = tk.Frame(row, bg=theme.INPUT_BG)
        inner.pack(fill="x", padx=10, pady=8)
        tk.Label(inner, text=label, bg=theme.INPUT_BG, fg=theme.BODY_TEXT,
                 font=theme.korean(12, "bold")).pack(side="left")
        detail = (f"계정 {manifest.get('account_count', '?')}개 · "
                  f"캐릭터 {manifest.get('character_count', '?')}개")
        tk.Label(inner, text=detail, bg=theme.INPUT_BG, fg=theme.TEXT_MUTED3,
                 font=theme.korean(10)).pack(side="left", padx=(12, 0))
        GradientButton(
            inner, "복원", command=lambda b=backup_id: self._confirm_restore(b), width=64, height=28,
            top=theme.STOP_TOP, bottom=theme.STOP_BOTTOM, border=theme.STOP_BORDER,
            text_color=theme.STOP_TEXT, font=theme.korean(10, "bold"), radius=3, container_bg=theme.INPUT_BG,
        ).pack(side="right")

    def _run_backup(self):
        host, port, user, password, auth_db, char_db, bot_prefix = self._conn()
        if not host or not user:
            self._append_result("접속 정보 수정에서 호스트/DB 사용자를 먼저 입력하세요.")
            return
        self._append_result("> DB에 접속해서 백업 생성 중... (계정/캐릭터 수에 따라 몇 초~몇 분)")
        self._set_busy(True)

        def worker():
            backup_id, err = db_backup.run_backup(
                host, port, user, password, auth_db, char_db, self.local_dir, bot_prefix)

            def done():
                if backup_id:
                    self._append_result(f">> 백업 완료, 이 컴퓨터에 저장됨: {os.path.join(self.local_dir, backup_id)}")
                else:
                    self._append_result(err or "백업 실패")
                self._set_busy(False)
                if backup_id:
                    self._refresh_list()
            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _confirm_restore(self, backup_id):
        if not messagebox.askyesno(
            "백업 복원",
            f"'{backup_id}' 백업으로 복원합니다.\n\n"
            "지금 서버에 있는 실제 계정/캐릭터 데이터는 이 백업 시점 데이터로 완전히 "
            "덮어써지며 되돌릴 수 없습니다(봇 계정은 영향받지 않음). 계속하시겠습니까?",
            parent=self,
        ):
            return
        host, port, user, password, auth_db, char_db, bot_prefix = self._conn()
        self._append_result(f"> '{backup_id}' DB로 복원 중...")
        self._set_busy(True)

        def worker():
            ok, output = db_backup.run_restore(
                host, port, user, password, auth_db, char_db, self.local_dir, backup_id,
                bot_prefix=bot_prefix, force=True)

            def done():
                self._append_result(output or ("복원 완료" if ok else "복원 실패"))
                self._set_busy(False)
            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()
