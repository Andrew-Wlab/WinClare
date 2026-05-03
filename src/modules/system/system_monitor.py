"""
WinClare — Монитор системы
Собирает данные CPU, RAM, диск, сеть, процессы через psutil.
"""
import os
import time
import psutil
from dataclasses import dataclass, field
from typing import Optional
from utils.logger import logger

try:
    import wmi as _wmi
    _WMI_AVAILABLE = True
except Exception:
    _WMI_AVAILABLE = False


@dataclass
class CpuInfo:
    percent: float          # загрузка % (усреднение по всем ядрам)
    per_core: list[float]   # загрузка по ядрам
    freq_mhz: float         # текущая частота
    freq_max_mhz: float     # максимальная частота
    cores_physical: int
    cores_logical: int
    temperature: Optional[float]  # °C или None


@dataclass
class RamInfo:
    total: int      # байты
    used: int
    available: int
    percent: float
    swap_total: int
    swap_used: int
    swap_percent: float


@dataclass
class DiskInfo:
    device: str
    mountpoint: str
    fstype: str
    total: int
    used: int
    free: int
    percent: float
    read_bytes: int   # за последний интервал
    write_bytes: int


@dataclass
class NetInfo:
    bytes_sent: int     # за последний интервал
    bytes_recv: int
    packets_sent: int
    packets_recv: int


@dataclass
class ProcessInfo:
    pid: int
    name: str
    cpu_percent: float
    mem_mb: float
    status: str
    username: str


@dataclass
class SystemSnapshot:
    cpu: CpuInfo
    ram: RamInfo
    disks: list[DiskInfo] = field(default_factory=list)
    net: NetInfo = field(default_factory=lambda: NetInfo(0, 0, 0, 0))
    top_processes: list[ProcessInfo] = field(default_factory=list)
    uptime_seconds: int = 0


# ── Кэш предыдущих показателей ввода-вывода ──────────────────────────────────

_prev_disk_io: dict[str, tuple[int, int]] = {}  # device -> (read_bytes, write_bytes)
_prev_net_io: tuple[int, int, int, int] = (0, 0, 0, 0)  # sent, recv, psent, precv
_prev_snapshot_time: float = 0.0


def _get_cpu_temp() -> Optional[float]:
    """Попытка получить температуру CPU (только Windows через WMI)."""
    if not _WMI_AVAILABLE:
        return None
    try:
        w = _wmi.WMI(namespace="root\\wmi")
        sensors = w.MSAcpi_ThermalZoneTemperature()
        if sensors:
            # Конвертируем из десятых долей Кельвина в °C
            temp_k = sensors[0].CurrentTemperature / 10.0
            return round(temp_k - 273.15, 1)
    except Exception:
        pass
    # Второй способ: psutil (Linux/macOS)
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                if entries:
                    return round(entries[0].current, 1)
    except AttributeError:
        pass
    return None


class SystemMonitor:
    def __init__(self):
        self._last_cpu_call = 0.0
        # Инициализируем базовую точку для дифференциальных замеров
        try:
            psutil.cpu_percent(interval=None)
            psutil.cpu_percent(percpu=True, interval=None)
        except Exception:
            pass

    def get_snapshot(self) -> SystemSnapshot:
        global _prev_disk_io, _prev_net_io, _prev_snapshot_time

        now = time.time()
        elapsed = now - _prev_snapshot_time if _prev_snapshot_time else 1.0
        if elapsed < 0.01:
            elapsed = 1.0
        _prev_snapshot_time = now

        # ── CPU ──────────────────────────────────────────────────────────────
        try:
            cpu_pct = psutil.cpu_percent(interval=None)
            per_core = psutil.cpu_percent(percpu=True, interval=None)
        except Exception:
            cpu_pct, per_core = 0.0, []

        try:
            freq = psutil.cpu_freq()
            freq_cur = round(freq.current, 1) if freq else 0.0
            freq_max = round(freq.max, 1) if freq else 0.0
        except Exception:
            freq_cur = freq_max = 0.0

        cpu_info = CpuInfo(
            percent=round(cpu_pct, 1),
            per_core=[round(p, 1) for p in per_core],
            freq_mhz=freq_cur,
            freq_max_mhz=freq_max,
            cores_physical=psutil.cpu_count(logical=False) or 1,
            cores_logical=psutil.cpu_count(logical=True) or 1,
            temperature=_get_cpu_temp(),
        )

        # ── RAM ──────────────────────────────────────────────────────────────
        try:
            vm = psutil.virtual_memory()
            sw = psutil.swap_memory()
            ram_info = RamInfo(
                total=vm.total, used=vm.used, available=vm.available,
                percent=round(vm.percent, 1),
                swap_total=sw.total, swap_used=sw.used,
                swap_percent=round(sw.percent, 1),
            )
        except Exception:
            ram_info = RamInfo(0, 0, 0, 0, 0, 0, 0)

        # ── Диски ────────────────────────────────────────────────────────────
        disks: list[DiskInfo] = []
        try:
            disk_io_now = psutil.disk_io_counters(perdisk=True) or {}
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                except (OSError, PermissionError):
                    continue
                dev = part.device.replace("\\", "").replace("/", "").upper()
                prev_r, prev_w = _prev_disk_io.get(dev, (0, 0))
                cur_io = disk_io_now.get(dev)
                if cur_io:
                    dr = max(0, cur_io.read_bytes - prev_r)
                    dw = max(0, cur_io.write_bytes - prev_w)
                    _prev_disk_io[dev] = (cur_io.read_bytes, cur_io.write_bytes)
                else:
                    dr = dw = 0
                disks.append(DiskInfo(
                    device=part.device,
                    mountpoint=part.mountpoint,
                    fstype=part.fstype,
                    total=usage.total, used=usage.used, free=usage.free,
                    percent=round(usage.percent, 1),
                    read_bytes=dr, write_bytes=dw,
                ))
        except Exception as e:
            logger.warning(f"Disk info error: {e}")

        # ── Сеть ─────────────────────────────────────────────────────────────
        try:
            nio = psutil.net_io_counters()
            ps, pr, pps, ppr = _prev_net_io
            net_info = NetInfo(
                bytes_sent=max(0, nio.bytes_sent - ps),
                bytes_recv=max(0, nio.bytes_recv - pr),
                packets_sent=max(0, nio.packets_sent - pps),
                packets_recv=max(0, nio.packets_recv - ppr),
            )
            _prev_net_io = (nio.bytes_sent, nio.bytes_recv,
                            nio.packets_sent, nio.packets_recv)
        except Exception:
            net_info = NetInfo(0, 0, 0, 0)

        # ── Процессы (топ 20 по CPU) ─────────────────────────────────────────
        top_procs: list[ProcessInfo] = []
        try:
            procs = []
            for p in psutil.process_iter(
                    ["pid", "name", "cpu_percent", "memory_info", "status", "username"]):
                try:
                    info = p.info
                    mem = info["memory_info"]
                    procs.append(ProcessInfo(
                        pid=info["pid"],
                        name=info["name"] or "—",
                        cpu_percent=round(info["cpu_percent"] or 0.0, 1),
                        mem_mb=round((mem.rss if mem else 0) / 1024 / 1024, 1),
                        status=info["status"] or "—",
                        username=(info["username"] or "").split("\\")[-1],
                    ))
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            procs.sort(key=lambda p: p.cpu_percent, reverse=True)
            top_procs = procs[:20]
        except Exception as e:
            logger.warning(f"Process list error: {e}")

        # ── Аптайм ───────────────────────────────────────────────────────────
        try:
            uptime = int(time.time() - psutil.boot_time())
        except Exception:
            uptime = 0

        return SystemSnapshot(
            cpu=cpu_info,
            ram=ram_info,
            disks=disks,
            net=net_info,
            top_processes=top_procs,
            uptime_seconds=uptime,
        )

    @staticmethod
    def format_bytes(b: int, per_sec: bool = False) -> str:
        suffix = "/с" if per_sec else ""
        for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
            if b < 1024:
                return f"{b:.1f} {unit}{suffix}"
            b /= 1024
        return f"{b:.1f} ТБ{suffix}"

    @staticmethod
    def format_uptime(seconds: int) -> str:
        d, r = divmod(seconds, 86400)
        h, r = divmod(r, 3600)
        m, s = divmod(r, 60)
        if d > 0:
            return f"{d}д {h:02}:{m:02}:{s:02}"
        return f"{h:02}:{m:02}:{s:02}"
