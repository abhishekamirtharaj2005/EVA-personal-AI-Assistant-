"""
EVA System Monitor — CPU/RAM/GPU/temperature monitoring with threshold alerts.
"""

import logging
import platform
import subprocess
from typing import Optional

import psutil

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.system_monitor")


def _get_gpu_info() -> dict:
    """Try to get GPU info via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=gpu_name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(",")
            if len(parts) >= 5:
                return {
                    "name": parts[0].strip(),
                    "utilization": float(parts[1].strip()),
                    "memory_used_mb": float(parts[2].strip()),
                    "memory_total_mb": float(parts[3].strip()),
                    "temperature": float(parts[4].strip()),
                }
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass
    return {}


def _get_temperature() -> Optional[float]:
    """Get CPU temperature (platform-specific)."""
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                for entry in entries:
                    if entry.current > 0:
                        return entry.current
    except (AttributeError, Exception):
        pass

    # Windows fallback via WMI
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance MSAcpi_ThermalZoneTemperature -Namespace root/wmi "
                 "| Select-Object -First 1 -ExpandProperty CurrentTemperature"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                # WMI returns in tenths of Kelvin
                kelvin_tenths = float(result.stdout.strip())
                return (kelvin_tenths / 10.0) - 273.15
        except Exception:
            pass

    return None


@register_tool(
    name="get_system_stats",
    description="Get current system performance metrics: CPU usage, RAM usage, "
                "GPU usage (if NVIDIA), and CPU temperature.",
    parameters={
        "type": "OBJECT",
        "properties": {},
        "required": [],
    },
    category="system",
)
def get_system_stats() -> str:
    """Gather comprehensive system metrics."""
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_freq = psutil.cpu_freq()
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    # Format report
    lines = [
        f"**CPU**: {cpu_percent}% usage",
    ]
    if cpu_freq:
        lines[0] += f" @ {cpu_freq.current:.0f} MHz"

    lines.append(
        f"**RAM**: {mem.percent}% used "
        f"({mem.used / (1024**3):.1f} GB / {mem.total / (1024**3):.1f} GB)"
    )
    lines.append(
        f"**Disk**: {disk.percent}% used "
        f"({disk.used / (1024**3):.1f} GB / {disk.total / (1024**3):.1f} GB)"
    )

    # GPU
    gpu = _get_gpu_info()
    if gpu:
        lines.append(
            f"**GPU**: {gpu['name']} — {gpu['utilization']}% usage, "
            f"{gpu['memory_used_mb']:.0f}/{gpu['memory_total_mb']:.0f} MB, "
            f"{gpu['temperature']}°C"
        )

    # Temperature
    temp = _get_temperature()
    if temp:
        lines.append(f"**CPU Temp**: {temp:.1f}°C")

    # Battery
    battery = psutil.sensors_battery()
    if battery:
        status = "charging" if battery.power_plugged else "discharging"
        lines.append(f"**Battery**: {battery.percent}% ({status})")

    return "\n".join(lines)


def get_metrics_dict() -> dict:
    """Return metrics as a dict (for the UI metric bars)."""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    gpu = _get_gpu_info()
    temp = _get_temperature()

    return {
        "cpu": cpu_percent,
        "ram": mem.percent,
        "gpu": gpu.get("utilization", 0),
        "temp": temp or 0,
        "gpu_name": gpu.get("name", ""),
    }
