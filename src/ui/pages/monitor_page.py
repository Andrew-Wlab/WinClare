"""
WinClare — Страница «Монитор системы»
Обновляется каждую секунду через self.after().
"""
import threading
import customtkinter as ctk
from modules.system.system_monitor import SystemMonitor, SystemSnapshot


def _cpu_color(pct: float) -> str:
    if pct >= 80:
        return "#e94560"
    if pct >= 50:
        return "#ed8936"
    return "#48bb78"


def _ram_color(pct: float) -> str:
    if pct >= 85:
        return "#e94560"
    if pct >= 60:
        return "#ed8936"
    return "#4a9eff"


class MonitorPage(ctk.CTkFrame):
    REFRESH_MS = 1000   # интервал обновления (мс)

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._monitor = SystemMonitor()
        self._running = True
        self._snap: SystemSnapshot | None = None
        self._lock = threading.Lock()
        self._build()
        self._schedule_update()

    # ── Построение интерфейса ────────────────────────────────────────────────

    def _build(self):
        # Заголовок
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(30, 10))
        ctk.CTkLabel(header, text="📊  Монитор системы",
                     font=ctk.CTkFont("Segoe UI", 22, weight="bold"),
                     text_color="#ffffff").pack(side="left")
        self.uptime_lbl = ctk.CTkLabel(header, text="",
                                        font=ctk.CTkFont("Segoe UI", 12),
                                        text_color="#718096")
        self.uptime_lbl.pack(side="right")

        # ── Верхний ряд: CPU + RAM ────────────────────────────────────────────
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=30, pady=(0, 10))
        top.columnconfigure((0, 1), weight=1, uniform="t")

        self._cpu_card = self._build_cpu_card(top)
        self._cpu_card.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        self._ram_card = self._build_ram_card(top)
        self._ram_card.grid(row=0, column=1, padx=(8, 0), sticky="nsew")

        # ── Средний ряд: Диски + Сеть ─────────────────────────────────────────
        mid = ctk.CTkFrame(self, fg_color="transparent")
        mid.pack(fill="x", padx=30, pady=(0, 10))
        mid.columnconfigure((0, 1), weight=1, uniform="m")

        self._disk_card = self._build_disk_card(mid)
        self._disk_card.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        self._net_card = self._build_net_card(mid)
        self._net_card.grid(row=0, column=1, padx=(8, 0), sticky="nsew")

        # ── Процессы ──────────────────────────────────────────────────────────
        ctk.CTkLabel(self, text="Активные процессы (топ по CPU)",
                     font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                     text_color="#ffffff").pack(anchor="w", padx=30, pady=(0, 6))

        # Заголовок таблицы
        thead = ctk.CTkFrame(self, fg_color="#0d1117", corner_radius=0)
        thead.pack(fill="x", padx=30)
        for col, (txt, w, anch) in enumerate([
            ("PID",      60,  "center"),
            ("Процесс",  0,   "w"),
            ("CPU %",    80,  "center"),
            ("RAM МБ",   90,  "center"),
            ("Статус",   90,  "center"),
            ("Польз.",   120, "center"),
        ]):
            ctk.CTkLabel(thead, text=txt,
                         font=ctk.CTkFont("Segoe UI", 11),
                         text_color="#718096",
                         width=w if w else 0,
                         anchor=anch,
                         ).grid(row=0, column=col,
                                padx=(8 if col == 0 else 4, 4),
                                pady=5,
                                sticky="ew" if col == 1 else "")
        thead.columnconfigure(1, weight=1)

        self.proc_frame = ctk.CTkScrollableFrame(
            self, fg_color="#16213e", corner_radius=14)
        self.proc_frame.pack(fill="both", expand=True, padx=30, pady=(4, 20))
        self.proc_frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(self.proc_frame, text="⏳  Загрузка...",
                     font=ctk.CTkFont("Segoe UI", 13),
                     text_color="#718096").grid(row=0, column=0, columnspan=6, pady=40)

    # ── Карточка CPU ─────────────────────────────────────────────────────────

    def _build_cpu_card(self, parent) -> ctk.CTkFrame:
        f = ctk.CTkFrame(parent, fg_color="#16213e", corner_radius=14)

        title_row = ctk.CTkFrame(f, fg_color="transparent")
        title_row.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(title_row, text="🖥️  Процессор",
                     font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                     text_color="#ffffff").pack(side="left")
        self.cpu_pct_lbl = ctk.CTkLabel(title_row, text="—%",
                                         font=ctk.CTkFont("Segoe UI", 20, weight="bold"),
                                         text_color="#48bb78")
        self.cpu_pct_lbl.pack(side="right")

        self.cpu_bar = ctk.CTkProgressBar(f, height=10, corner_radius=5,
                                           progress_color="#48bb78", fg_color="#2d3748")
        self.cpu_bar.set(0)
        self.cpu_bar.pack(fill="x", padx=16, pady=(0, 8))

        info_row = ctk.CTkFrame(f, fg_color="transparent")
        info_row.pack(fill="x", padx=16, pady=(0, 10))
        self.cpu_freq_lbl = ctk.CTkLabel(info_row, text="Частота: —",
                                          font=ctk.CTkFont("Segoe UI", 11),
                                          text_color="#a0aec0")
        self.cpu_freq_lbl.pack(side="left")
        self.cpu_cores_lbl = ctk.CTkLabel(info_row, text="Ядра: —",
                                           font=ctk.CTkFont("Segoe UI", 11),
                                           text_color="#a0aec0")
        self.cpu_cores_lbl.pack(side="right")

        self.cpu_temp_lbl = ctk.CTkLabel(f, text="",
                                          font=ctk.CTkFont("Segoe UI", 11),
                                          text_color="#ed8936")
        self.cpu_temp_lbl.pack(anchor="w", padx=16, pady=(0, 8))

        # Мини-бары по ядрам
        self.core_bars_frame = ctk.CTkFrame(f, fg_color="transparent")
        self.core_bars_frame.pack(fill="x", padx=16, pady=(0, 14))
        self._core_bars: list[ctk.CTkProgressBar] = []
        self._core_lbls: list[ctk.CTkLabel] = []

        return f

    # ── Карточка RAM ─────────────────────────────────────────────────────────

    def _build_ram_card(self, parent) -> ctk.CTkFrame:
        f = ctk.CTkFrame(parent, fg_color="#16213e", corner_radius=14)

        title_row = ctk.CTkFrame(f, fg_color="transparent")
        title_row.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(title_row, text="💾  Оперативная память",
                     font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                     text_color="#ffffff").pack(side="left")
        self.ram_pct_lbl = ctk.CTkLabel(title_row, text="—%",
                                         font=ctk.CTkFont("Segoe UI", 20, weight="bold"),
                                         text_color="#4a9eff")
        self.ram_pct_lbl.pack(side="right")

        self.ram_bar = ctk.CTkProgressBar(f, height=10, corner_radius=5,
                                           progress_color="#4a9eff", fg_color="#2d3748")
        self.ram_bar.set(0)
        self.ram_bar.pack(fill="x", padx=16, pady=(0, 8))

        info_row = ctk.CTkFrame(f, fg_color="transparent")
        info_row.pack(fill="x", padx=16, pady=(0, 10))
        self.ram_used_lbl = ctk.CTkLabel(info_row, text="Занято: —",
                                          font=ctk.CTkFont("Segoe UI", 11),
                                          text_color="#a0aec0")
        self.ram_used_lbl.pack(side="left")
        self.ram_total_lbl = ctk.CTkLabel(info_row, text="Всего: —",
                                           font=ctk.CTkFont("Segoe UI", 11),
                                           text_color="#a0aec0")
        self.ram_total_lbl.pack(side="right")

        # Swap
        swap_row = ctk.CTkFrame(f, fg_color="#0f1923", corner_radius=8)
        swap_row.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkLabel(swap_row, text="Swap",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color="#718096", width=50).pack(side="left", padx=8, pady=6)
        self.swap_bar = ctk.CTkProgressBar(swap_row, height=6, corner_radius=3,
                                            progress_color="#9f7aea", fg_color="#2d3748")
        self.swap_bar.set(0)
        self.swap_bar.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=6)
        self.swap_lbl = ctk.CTkLabel(swap_row, text="—",
                                      font=ctk.CTkFont("Segoe UI", 10),
                                      text_color="#a0aec0", width=70)
        self.swap_lbl.pack(side="right", padx=8)

        self.ram_avail_lbl = ctk.CTkLabel(f, text="",
                                           font=ctk.CTkFont("Segoe UI", 11),
                                           text_color="#48bb78")
        self.ram_avail_lbl.pack(anchor="w", padx=16, pady=(0, 14))

        return f

    # ── Карточка Диски ────────────────────────────────────────────────────────

    def _build_disk_card(self, parent) -> ctk.CTkFrame:
        f = ctk.CTkFrame(parent, fg_color="#16213e", corner_radius=14)
        ctk.CTkLabel(f, text="🗄️  Диски",
                     font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                     text_color="#ffffff").pack(anchor="w", padx=16, pady=(14, 8))
        self.disk_inner = ctk.CTkFrame(f, fg_color="transparent")
        self.disk_inner.pack(fill="both", expand=True, padx=16, pady=(0, 14))
        return f

    # ── Карточка Сеть ─────────────────────────────────────────────────────────

    def _build_net_card(self, parent) -> ctk.CTkFrame:
        f = ctk.CTkFrame(parent, fg_color="#16213e", corner_radius=14)
        ctk.CTkLabel(f, text="🌐  Сеть",
                     font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                     text_color="#ffffff").pack(anchor="w", padx=16, pady=(14, 8))

        def _net_row(label: str, color: str):
            r = ctk.CTkFrame(f, fg_color="#0f1923", corner_radius=8)
            r.pack(fill="x", padx=16, pady=(0, 8))
            ctk.CTkLabel(r, text=label, font=ctk.CTkFont("Segoe UI", 12),
                         text_color="#a0aec0", width=80, anchor="w"
                         ).pack(side="left", padx=12, pady=10)
            lbl = ctk.CTkLabel(r, text="—",
                               font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
                               text_color=color)
            lbl.pack(side="right", padx=12)
            return lbl

        self.net_recv_lbl  = _net_row("⬇  Приём:",    "#4a9eff")
        self.net_sent_lbl  = _net_row("⬆  Отправка:", "#48bb78")
        self.net_pkts_lbl  = _net_row("📦 Пакеты:",   "#a0aec0")

        return f

    # ── Обновление данных ────────────────────────────────────────────────────

    def _schedule_update(self):
        if not self._running:
            return
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        try:
            snap = self._monitor.get_snapshot()
        except Exception:
            snap = None
        self.after(0, lambda: self._apply(snap))

    def _apply(self, snap: SystemSnapshot | None):
        if snap is None or not self._running:
            self.after(self.REFRESH_MS, self._schedule_update)
            return

        self._snap = snap
        fmt = SystemMonitor.format_bytes

        # Uptime
        self.uptime_lbl.configure(
            text=f"⏱  Аптайм: {SystemMonitor.format_uptime(snap.uptime_seconds)}")

        # CPU
        cpu = snap.cpu
        c = _cpu_color(cpu.percent)
        self.cpu_pct_lbl.configure(text=f"{cpu.percent:.0f}%", text_color=c)
        self.cpu_bar.configure(progress_color=c)
        self.cpu_bar.set(cpu.percent / 100)
        self.cpu_freq_lbl.configure(text=f"Частота: {cpu.freq_mhz:.0f} МГц")
        self.cpu_cores_lbl.configure(
            text=f"Ядра: {cpu.cores_physical}ф / {cpu.cores_logical}л")
        if cpu.temperature is not None:
            tc = "#e94560" if cpu.temperature > 80 else "#ed8936" if cpu.temperature > 65 else "#48bb78"
            self.cpu_temp_lbl.configure(
                text=f"🌡  Температура: {cpu.temperature}°C", text_color=tc)
        else:
            self.cpu_temp_lbl.configure(text="")

        # Мини-бары ядер
        n_cores = len(cpu.per_core)
        existing = len(self._core_bars)
        if existing != n_cores:
            for w in self.core_bars_frame.winfo_children():
                w.destroy()
            self._core_bars.clear()
            self._core_lbls.clear()
            cols = min(n_cores, 8)
            for i in range(n_cores):
                self.core_bars_frame.columnconfigure(i % cols, weight=1)
                bar = ctk.CTkProgressBar(self.core_bars_frame, height=5,
                                         corner_radius=3, width=60,
                                         progress_color="#4a9eff",
                                         fg_color="#2d3748")
                bar.set(0)
                bar.grid(row=(i // cols) * 2, column=i % cols, padx=2, pady=(0, 1), sticky="ew")
                lbl = ctk.CTkLabel(self.core_bars_frame, text="C0",
                                   font=ctk.CTkFont("Segoe UI", 9),
                                   text_color="#718096")
                lbl.grid(row=(i // cols) * 2 + 1, column=i % cols, padx=2)
                self._core_bars.append(bar)
                self._core_lbls.append(lbl)

        for i, (bar, lbl, pct) in enumerate(
                zip(self._core_bars, self._core_lbls, cpu.per_core)):
            bar.set(pct / 100)
            bar.configure(progress_color=_cpu_color(pct))
            lbl.configure(text=f"C{i} {pct:.0f}%")

        # RAM
        ram = snap.ram
        rc = _ram_color(ram.percent)
        self.ram_pct_lbl.configure(text=f"{ram.percent:.0f}%", text_color=rc)
        self.ram_bar.configure(progress_color=rc)
        self.ram_bar.set(ram.percent / 100)
        self.ram_used_lbl.configure(text=f"Занято: {fmt(ram.used)}")
        self.ram_total_lbl.configure(text=f"Всего: {fmt(ram.total)}")
        self.ram_avail_lbl.configure(
            text=f"✅ Доступно: {fmt(ram.available)}")
        self.swap_bar.set(ram.swap_percent / 100 if ram.swap_total > 0 else 0)
        self.swap_lbl.configure(
            text=f"{fmt(ram.swap_used)} / {fmt(ram.swap_total)}"
            if ram.swap_total > 0 else "Нет")

        # Диски
        for w in self.disk_inner.winfo_children():
            w.destroy()
        for dk in snap.disks[:5]:
            dc = _cpu_color(dk.percent)
            dr = ctk.CTkFrame(self.disk_inner, fg_color="#0f1923", corner_radius=8)
            dr.pack(fill="x", pady=(0, 6))
            dr.columnconfigure(1, weight=1)
            ctk.CTkLabel(dr, text=dk.device.rstrip("\\"),
                         font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
                         text_color="#ffffff", width=46, anchor="w"
                         ).grid(row=0, column=0, padx=(10, 6), pady=(8, 2), sticky="w")
            bar2 = ctk.CTkProgressBar(dr, height=8, corner_radius=4,
                                      progress_color=dc, fg_color="#2d3748")
            bar2.set(dk.percent / 100)
            bar2.grid(row=0, column=1, padx=4, pady=(8, 2), sticky="ew")
            ctk.CTkLabel(dr, text=f"{dk.percent:.0f}%",
                         font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
                         text_color=dc, width=44
                         ).grid(row=0, column=2, padx=(4, 10), pady=(8, 2))
            ctk.CTkLabel(dr,
                         text=f"{fmt(dk.used)} / {fmt(dk.total)}  "
                              f"↓{fmt(dk.read_bytes, True)}  ↑{fmt(dk.write_bytes, True)}",
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color="#718096", anchor="w"
                         ).grid(row=1, column=0, columnspan=3, padx=10, pady=(0, 8), sticky="w")

        # Сеть
        net = snap.net
        self.net_recv_lbl.configure(text=fmt(net.bytes_recv, True))
        self.net_sent_lbl.configure(text=fmt(net.bytes_sent, True))
        self.net_pkts_lbl.configure(
            text=f"↓{net.packets_recv}  ↑{net.packets_sent}")

        # Процессы
        self._render_processes(snap)

        # Запускаем следующий цикл
        self.after(self.REFRESH_MS, self._schedule_update)

    def _render_processes(self, snap: SystemSnapshot):
        for w in self.proc_frame.winfo_children():
            w.destroy()
        if not snap.top_processes:
            ctk.CTkLabel(self.proc_frame, text="Нет данных",
                         font=ctk.CTkFont("Segoe UI", 12),
                         text_color="#718096").grid(row=0, column=0, columnspan=6, pady=20)
            return
        for i, p in enumerate(snap.top_processes):
            bg = "#1a1a2e" if i % 2 == 0 else "#16213e"
            row = ctk.CTkFrame(self.proc_frame, fg_color=bg, corner_radius=6, height=36)
            row.grid(row=i, column=0, padx=4, pady=1, sticky="ew")
            row.columnconfigure(1, weight=1)
            row.grid_propagate(False)

            cpu_c = _cpu_color(p.cpu_percent)
            for col, (txt, w, clr, anch) in enumerate([
                (str(p.pid),              60,  "#718096", "center"),
                (p.name[:30],             0,   "#ffffff", "w"),
                (f"{p.cpu_percent:.1f}%", 80,  cpu_c,     "center"),
                (f"{p.mem_mb:.0f}",       90,  "#a0aec0", "center"),
                (p.status,                90,  "#718096", "center"),
                (p.username[:14],         120, "#a0aec0", "center"),
            ]):
                ctk.CTkLabel(row, text=txt,
                             font=ctk.CTkFont("Segoe UI", 11),
                             text_color=clr,
                             width=w if w else 0,
                             anchor=anch,
                             ).grid(row=0, column=col,
                                    padx=(8 if col == 0 else 4, 4),
                                    sticky="ew" if col == 1 else "")

    def destroy(self):
        self._running = False
        super().destroy()
