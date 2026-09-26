"""
EVA Smart Home Control — Control IoT devices (lights, plugs, thermostats).
Supports: TP-Link Kasa, Philips Hue, and Home Assistant REST API.
Falls back to generic HTTP commands for custom setups.
"""

import json
import logging
import subprocess
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.smart_home")


def _kasa_discover() -> list[dict]:
    """Discover TP-Link Kasa devices on the network."""
    try:
        result = subprocess.run(
            ["python", "-m", "kasa", "discover", "--json"],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
        )
        if result.returncode == 0 and result.stdout.strip():
            devices = json.loads(result.stdout)
            return [
                {"name": d.get("alias", "Unknown"), "ip": d.get("host", ""),
                 "type": d.get("device_type", ""), "on": d.get("is_on", False)}
                for d in (devices if isinstance(devices, list) else [devices])
            ]
    except Exception as e:
        logger.debug(f"Kasa discover: {e}")
    return []


def _kasa_command(ip: str, command: str) -> str:
    """Send a command to a Kasa device."""
    try:
        result = subprocess.run(
            ["python", "-m", "kasa", "--host", ip, command],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
        )
        return result.stdout.strip() or "Command sent."
    except Exception as e:
        return f"Kasa command failed: {e}"


def _home_assistant_call(endpoint: str, method: str = "GET",
                         data: dict = None) -> Optional[dict]:
    """Call Home Assistant REST API."""
    from memory.config_manager import config
    ha_url = config.get("home_assistant_url", "")
    ha_token = config.get("home_assistant_token", "")

    if not ha_url or not ha_token:
        return None

    try:
        import requests
        headers = {
            "Authorization": f"Bearer {ha_token}",
            "Content-Type": "application/json",
        }
        url = f"{ha_url.rstrip('/')}/api/{endpoint}"

        if method == "POST":
            resp = requests.post(url, json=data or {}, headers=headers, timeout=10)
        else:
            resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code in (200, 201):
            return resp.json()
        return {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


@register_tool(
    name="smart_home",
    description="Control smart home devices — lights, plugs, switches, thermostats. "
                "Supports TP-Link Kasa devices and Home Assistant integration. "
                "Actions: list (discover devices), on/off (toggle device), "
                "set (brightness/temperature), status.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: list | on | off | toggle | brightness | temperature | status",
            },
            "device": {
                "type": "STRING",
                "description": "Device name or location. E.g., 'bedroom light', 'living room plug'",
            },
            "value": {
                "type": "INTEGER",
                "description": "Value for brightness (0-100) or temperature (16-30°C)",
            },
        },
        "required": ["action"],
    },
    category="iot",
)
def smart_home(action: str, device: str = "", value: int = 0) -> str:
    """Control smart home devices."""
    action = action.lower().strip()
    device_lower = device.lower().strip()

    # ── Discover devices ─────────────────────────────────────
    if action == "list":
        devices = _kasa_discover()

        # Also try Home Assistant
        ha_result = _home_assistant_call("states")
        ha_devices = []
        if isinstance(ha_result, list):
            for entity in ha_result:
                eid = entity.get("entity_id", "")
                if eid.startswith(("light.", "switch.", "climate.")):
                    ha_devices.append({
                        "name": entity.get("attributes", {}).get("friendly_name", eid),
                        "entity_id": eid,
                        "state": entity.get("state", "unknown"),
                    })

        if not devices and not ha_devices:
            return (
                "🏠 No smart home devices found.\n\n"
                "To set up:\n"
                "• TP-Link Kasa: pip install python-kasa\n"
                "• Home Assistant: Add home_assistant_url and home_assistant_token in Settings"
            )

        lines = []
        for d in devices:
            status = "🟢 ON" if d["on"] else "🔴 OFF"
            lines.append(f"  • {d['name']} ({d['type']}) — {status} [{d['ip']}]")
        for d in ha_devices:
            lines.append(f"  • {d['name']} — {d['state']} [{d['entity_id']}]")

        return f"🏠 Smart Home Devices ({len(devices) + len(ha_devices)}):\n" + "\n".join(lines)

    # ── Turn on/off ──────────────────────────────────────────
    elif action in ("on", "off", "toggle"):
        if not device:
            return "Which device? Give me a name like 'bedroom light'."

        # Try Kasa
        devices = _kasa_discover()
        for d in devices:
            if device_lower in d["name"].lower():
                result = _kasa_command(d["ip"], action)
                return f"🏠 {d['name']}: {action.upper()} — {result}"

        # Try Home Assistant
        ha_result = _home_assistant_call("states")
        if isinstance(ha_result, list):
            for entity in ha_result:
                name = entity.get("attributes", {}).get("friendly_name", "").lower()
                eid = entity.get("entity_id", "")
                if device_lower in name or device_lower in eid:
                    domain = eid.split(".")[0]
                    service = f"turn_{action}" if action != "toggle" else "toggle"
                    _home_assistant_call(
                        f"services/{domain}/{service}",
                        method="POST",
                        data={"entity_id": eid}
                    )
                    return f"🏠 {entity.get('attributes', {}).get('friendly_name', eid)}: {action.upper()}"

        return f"Device '{device}' not found. Say 'list smart home devices' to see available ones."

    # ── Brightness ───────────────────────────────────────────
    elif action == "brightness":
        if not device:
            return "Which light?"
        if not (0 <= value <= 100):
            return "Brightness should be 0-100."

        ha_result = _home_assistant_call("states")
        if isinstance(ha_result, list):
            for entity in ha_result:
                name = entity.get("attributes", {}).get("friendly_name", "").lower()
                eid = entity.get("entity_id", "")
                if device_lower in name and eid.startswith("light."):
                    _home_assistant_call(
                        "services/light/turn_on",
                        method="POST",
                        data={"entity_id": eid, "brightness_pct": value}
                    )
                    return f"💡 {name}: brightness set to {value}%"

        return f"Light '{device}' not found."

    # ── Temperature ──────────────────────────────────────────
    elif action == "temperature":
        if not device:
            return "Which thermostat/AC?"
        if not (16 <= value <= 30):
            return "Temperature should be 16-30°C."

        ha_result = _home_assistant_call("states")
        if isinstance(ha_result, list):
            for entity in ha_result:
                name = entity.get("attributes", {}).get("friendly_name", "").lower()
                eid = entity.get("entity_id", "")
                if device_lower in name and eid.startswith("climate."):
                    _home_assistant_call(
                        "services/climate/set_temperature",
                        method="POST",
                        data={"entity_id": eid, "temperature": value}
                    )
                    return f"🌡️ {name}: temperature set to {value}°C"

        return f"Thermostat '{device}' not found."

    # ── Status ───────────────────────────────────────────────
    elif action == "status":
        if not device:
            return smart_home(action="list")

        ha_result = _home_assistant_call("states")
        if isinstance(ha_result, list):
            for entity in ha_result:
                name = entity.get("attributes", {}).get("friendly_name", "").lower()
                if device_lower in name:
                    attrs = entity.get("attributes", {})
                    return (
                        f"🏠 {attrs.get('friendly_name', device)}:\n"
                        f"  State: {entity.get('state')}\n"
                        f"  Attributes: {json.dumps(attrs, indent=2)[:300]}"
                    )

        return f"Device '{device}' not found."

    return f"Unknown smart home action '{action}'. Use: list, on, off, toggle, brightness, temperature, status."
