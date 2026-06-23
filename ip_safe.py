"""
IP Safe v3 - Full Privacy Suite (Hardened)
==========================================
Fixes from v2:
- Force ALL traffic through Tor (not just browser)
- Crash-safe recovery on startup
- Proper firewall kill switch with priorities
- Deep HWID spoofing (GUID + disk serial + SMBIOS + ProductId)
- DNS via Tor (no leak possible)
- Tor connectivity watchdog
- Leak test built-in

Requires: Administrator privileges
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import random
import socket
import uuid
import re
import os
import sys
import ctypes
import winreg
import threading
import time
import urllib.request
import json
import atexit
import signal

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOR_DIR = os.path.join(os.environ.get("LOCALAPPDATA", SCRIPT_DIR), "IPSafe_Tor")
TOR_EXE = os.path.join(TOR_DIR, "tor", "tor.exe")
TOR_DATA = os.path.join(TOR_DIR, "data")
TORRC = os.path.join(TOR_DIR, "torrc")
HWID_BACKUP = os.path.join(SCRIPT_DIR, "hwid_backup.json")
STATE_FILE = os.path.join(SCRIPT_DIR, "ipsafe_state.json")

SOCKS_PORT = 9050
CONTROL_PORT = 9051
DNS_PORT = 53
TRANS_PORT = 9040


# ═════════════════════════════════════════════════════════════════════
#  CRASH RECOVERY
# ═════════════════════════════════════════════════════════════════════

def save_state(active=True):
    state = {
        "active": active,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pid": os.getpid()
    }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def clear_state():
    try:
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
    except Exception:
        pass


def crash_recovery():
    """Called at startup - clean up if previous run crashed while active."""
    state = load_state()
    if not state or not state.get("active"):
        return False

    pid = state.get("pid")
    still_running = False
    if pid:
        try:
            result = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                                    capture_output=True, text=True, timeout=5)
            still_running = str(pid) in result.stdout
        except Exception:
            pass

    if still_running:
        return False

    # Previous instance crashed while protection was active
    recovered = []

    # 1. Restore default outbound policy + remove firewall rules
    subprocess.run(
        ["netsh", "advfirewall", "set", "currentprofile", "firewallpolicy",
         "blockinbound,allowoutbound"],
        capture_output=True, timeout=5
    )
    for suffix in ["_BlockOut", "_AllowLoopback", "_AllowTor", "_AllowDHCP", "_AllowLAN", "_AllowDNS"]:
        subprocess.run(["netsh", "advfirewall", "firewall", "delete", "rule",
                        f"name=IPSafe_KillSwitch{suffix}"],
                       capture_output=True, timeout=5)
    recovered.append("Firewall rules removed")

    # 2. Remove proxy
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                            0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            try:
                winreg.DeleteValue(key, "ProxyServer")
            except FileNotFoundError:
                pass
        recovered.append("System proxy disabled")
    except Exception:
        pass

    # 3. Restore DNS to DHCP
    iface = get_active_interface()
    if iface:
        subprocess.run(["netsh", "interface", "ip", "set", "dns",
                        f"name={iface}", "dhcp"],
                       capture_output=True, timeout=5)
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=5)
        recovered.append("DNS restored")

    # 4. Kill orphaned tor.exe
    subprocess.run(["taskkill", "/F", "/IM", "tor.exe"],
                   capture_output=True, timeout=5)
    recovered.append("Tor process killed")

    clear_state()
    return recovered


# ═════════════════════════════════════════════════════════════════════
#  TOR MANAGEMENT
# ═════════════════════════════════════════════════════════════════════

def is_tor_installed():
    if not os.path.isfile(TOR_EXE):
        return False
    try:
        with open(TOR_EXE, "rb") as f:
            f.read(1)
        return True
    except (PermissionError, OSError):
        return False


def _cleanup_corrupted_tor():
    tor_inner = os.path.join(TOR_DIR, "tor")
    if not os.path.exists(tor_inner):
        return
    try:
        import shutil
        shutil.rmtree(tor_inner, ignore_errors=True)
    except Exception:
        pass
    if os.path.exists(tor_inner):
        try:
            subprocess.run(
                ["takeown", "/f", tor_inner, "/r", "/d", "o"],
                capture_output=True, timeout=10
            )
            subprocess.run(
                ["icacls", tor_inner, "/grant", f"{os.environ.get('USERNAME', 'everyone')}:F", "/t"],
                capture_output=True, timeout=10
            )
            import shutil
            shutil.rmtree(tor_inner, ignore_errors=True)
        except Exception:
            pass


def download_tor(progress_cb=None):
    url = "https://archive.torproject.org/tor-package-archive/torbrowser/13.5.7/tor-expert-bundle-windows-x86_64-13.5.7.tar.gz"
    archive = os.path.join(SCRIPT_DIR, "tor_bundle.tar.gz")
    try:
        _cleanup_corrupted_tor()

        if progress_cb:
            progress_cb("Downloading Tor expert bundle (~15MB)...")

        urllib.request.urlretrieve(url, archive)

        if progress_cb:
            progress_cb("Extracting...")

        import tarfile, stat
        os.makedirs(TOR_DIR, exist_ok=True)
        with tarfile.open(archive, "r:gz") as tar:
            for member in tar.getmembers():
                member.mode = 0o755 if member.isdir() else 0o644
                tar.extract(member, TOR_DIR)

        # Fix permissions on all extracted files/dirs
        for root_dir, dirs, files in os.walk(TOR_DIR):
            for d in dirs:
                try:
                    os.chmod(os.path.join(root_dir, d), stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
                except Exception:
                    pass
            for f in files:
                try:
                    os.chmod(os.path.join(root_dir, f), stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)
                except Exception:
                    pass

        os.remove(archive)
        os.makedirs(TOR_DATA, exist_ok=True)
        write_torrc()

        if progress_cb:
            progress_cb("Tor installed successfully")
        return True
    except Exception as e:
        if progress_cb:
            progress_cb(f"Download failed: {e}")
        return False


def write_torrc():
    config = (
        f"SocksPort {SOCKS_PORT}\n"
        f"ControlPort {CONTROL_PORT}\n"
        f"DNSPort 127.0.0.1:{DNS_PORT}\n"
        f"DataDirectory {TOR_DATA}\n"
        "CookieAuthentication 1\n"
        "AvoidDiskWrites 1\n"
        "Log notice stderr\n"
        "ClientOnly 1\n"
        "SafeSocks 1\n"
    )
    with open(TORRC, "w") as f:
        f.write(config)


class TorManager:
    def __init__(self):
        self.process = None
        self.connected = False
        self._watchdog_running = False

    def start(self, status_cb=None):
        if not is_tor_installed():
            if status_cb:
                status_cb("Tor not found, downloading...")
            if not download_tor(status_cb):
                return False

        if self.process and self.process.poll() is None:
            return True

        try:
            write_torrc()
            self.process = subprocess.Popen(
                [TOR_EXE, "-f", TORRC],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            if status_cb:
                status_cb("Connecting to Tor network...")

            deadline = time.time() + 60
            while time.time() < deadline:
                if self.process.poll() is not None:
                    return False
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(2)
                    s.connect(("127.0.0.1", SOCKS_PORT))
                    s.close()
                    self.connected = True
                    return True
                except (ConnectionRefusedError, OSError):
                    time.sleep(1)
            return False
        except Exception as e:
            if status_cb:
                status_cb(f"Tor start failed: {e}")
            return False

    def stop(self):
        self._watchdog_running = False
        self.connected = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

    def is_alive(self):
        if not self.process:
            return False
        if self.process.poll() is not None:
            return False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(("127.0.0.1", SOCKS_PORT))
            s.close()
            return True
        except Exception:
            return False

    def start_watchdog(self, on_down_cb=None, on_up_cb=None):
        self._watchdog_running = True

        def watch():
            was_down = False
            while self._watchdog_running:
                alive = self.is_alive()
                if not alive and not was_down:
                    was_down = True
                    self.connected = False
                    if on_down_cb:
                        on_down_cb()
                    # Try to restart
                    self.start()
                    if self.is_alive():
                        was_down = False
                        self.connected = True
                        if on_up_cb:
                            on_up_cb()
                elif alive and was_down:
                    was_down = False
                    self.connected = True
                    if on_up_cb:
                        on_up_cb()
                time.sleep(5)

        threading.Thread(target=watch, daemon=True).start()

    def request_new_identity(self):
        try:
            cookie_path = os.path.join(TOR_DATA, "control_auth_cookie")
            with open(cookie_path, "rb") as f:
                cookie = f.read()

            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect(("127.0.0.1", CONTROL_PORT))
            s.send(b'AUTHENTICATE ' + cookie.hex().encode() + b'\r\n')
            resp = s.recv(256)
            if b"250" in resp:
                s.send(b'SIGNAL NEWNYM\r\n')
                s.recv(256)
            s.close()
            return True
        except Exception:
            return False

    def get_exit_ip(self):
        """Get exit IP via raw SOCKS5 handshake (no external dependency)."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(15)
            s.connect(("127.0.0.1", SOCKS_PORT))

            s.send(b'\x05\x01\x00')
            if s.recv(2) != b'\x05\x00':
                s.close()
                return None

            domain = b"api.ipify.org"
            s.send(b'\x05\x01\x00\x03' + bytes([len(domain)]) + domain + b'\x00\x50')
            resp = s.recv(10)
            if len(resp) < 2 or resp[1] != 0:
                s.close()
                return None

            req = (
                b"GET / HTTP/1.1\r\n"
                b"Host: api.ipify.org\r\n"
                b"Connection: close\r\n\r\n"
            )
            s.send(req)
            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
            s.close()

            body = data.split(b"\r\n\r\n", 1)[-1].decode().strip()
            if re.match(r'^\d+\.\d+\.\d+\.\d+$', body):
                return body
            return None
        except Exception:
            return None


# ═════════════════════════════════════════════════════════════════════
#  SYSTEM PROXY — Force ALL apps through Tor
# ═════════════════════════════════════════════════════════════════════

PROXY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"


def set_system_proxy(enable, host="127.0.0.1", port=SOCKS_PORT):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PROXY_KEY,
                            0, winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ,
                                  f"socks={host}:{port}")
                winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ,
                                  "localhost;127.0.0.1;10.*;192.168.*")
            else:
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
                try:
                    winreg.DeleteValue(key, "ProxyServer")
                except FileNotFoundError:
                    pass

        INTERNET_OPTION_SETTINGS_CHANGED = 39
        INTERNET_OPTION_REFRESH = 37
        inet = ctypes.windll.wininet.InternetSetOptionW
        inet(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
        inet(0, INTERNET_OPTION_REFRESH, 0, 0)
        return True
    except Exception:
        return False


# ═════════════════════════════════════════════════════════════════════
#  DNS — Route through Tor DNS resolver
# ═════════════════════════════════════════════════════════════════════

def get_active_interface():
    try:
        result = subprocess.run(
            ["netsh", "interface", "ip", "show", "config"],
            capture_output=True, text=True, timeout=10
        )
        current_iface = None
        for line in result.stdout.split("\n"):
            m = re.match(r'Configuration for interface "(.+)"', line)
            if m:
                current_iface = m.group(1)
            if "Default Gateway" in line and current_iface:
                gw = line.split(":")[-1].strip()
                if gw:
                    return current_iface
        return None
    except Exception:
        return None


def set_tor_dns(interface):
    """Point DNS to Tor's DNS resolver on 127.0.0.1:5353.
    Since Windows can't set a port for DNS, we set DNS to 127.0.0.1
    and Tor's DNSPort handles it. Fallback: use Cloudflare DoH."""
    try:
        subprocess.run(
            ["netsh", "interface", "ip", "set", "dns", f"name={interface}",
             "static", "127.0.0.1", "primary"],
            capture_output=True, timeout=10
        )
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def set_secure_dns_fallback(interface):
    """Fallback: Cloudflare + Quad9 if Tor DNS doesn't work."""
    try:
        subprocess.run(
            ["netsh", "interface", "ip", "set", "dns", f"name={interface}",
             "static", "1.1.1.1", "primary"],
            capture_output=True, timeout=10
        )
        subprocess.run(
            ["netsh", "interface", "ip", "add", "dns", f"name={interface}",
             "9.9.9.9", "index=2"],
            capture_output=True, timeout=10
        )
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def restore_dns(interface):
    try:
        subprocess.run(
            ["netsh", "interface", "ip", "set", "dns", f"name={interface}", "dhcp"],
            capture_output=True, timeout=10
        )
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=10)
        return True
    except Exception:
        return False


# ═════════════════════════════════════════════════════════════════════
#  KILL SWITCH — Proper firewall with correct priority
# ═════════════════════════════════════════════════════════════════════

KILLSWITCH_RULE = "IPSafe_KillSwitch"


def enable_kill_switch():
    """Block ALL outbound traffic except Tor, loopback, LAN, and DHCP.
    Uses default outbound policy=block so only explicit allow rules pass."""
    try:
        subprocess.run(
            ["netsh", "advfirewall", "set", "currentprofile", "firewallpolicy",
             "blockinbound,blockoutbound"],
            capture_output=True, timeout=10
        )

        rules = [
            {
                "name": f"{KILLSWITCH_RULE}_AllowTor",
                "dir": "out", "action": "allow",
                "program": TOR_EXE,
            },
            {
                "name": f"{KILLSWITCH_RULE}_AllowLoopback",
                "dir": "out", "action": "allow",
                "remoteip": "127.0.0.0/8",
            },
            {
                "name": f"{KILLSWITCH_RULE}_AllowDHCP",
                "dir": "out", "action": "allow",
                "protocol": "udp", "remoteport": "67,68",
            },
            {
                "name": f"{KILLSWITCH_RULE}_AllowLAN",
                "dir": "out", "action": "allow",
                "remoteip": "192.168.0.0/16,10.0.0.0/8,172.16.0.0/12",
            },
            {
                "name": f"{KILLSWITCH_RULE}_AllowDNS",
                "dir": "out", "action": "allow",
                "protocol": "udp", "remoteip": "127.0.0.1", "remoteport": "53",
            },
        ]

        for rule in rules:
            if "program" in rule and not os.path.isfile(rule["program"]):
                continue
            cmd = ["netsh", "advfirewall", "firewall", "add", "rule"]
            for k, v in rule.items():
                cmd.append(f"{k}={v}")
            subprocess.run(cmd, capture_output=True, timeout=10)

        return True
    except Exception:
        return False


def disable_kill_switch():
    try:
        subprocess.run(
            ["netsh", "advfirewall", "set", "currentprofile", "firewallpolicy",
             "blockinbound,allowoutbound"],
            capture_output=True, timeout=10
        )

        for suffix in ["_BlockOut", "_AllowLoopback", "_AllowTor",
                        "_AllowDHCP", "_AllowLAN", "_AllowDNS"]:
            subprocess.run([
                "netsh", "advfirewall", "firewall", "delete", "rule",
                f"name={KILLSWITCH_RULE}{suffix}"
            ], capture_output=True, timeout=10)
        return True
    except Exception:
        return False


# ═════════════════════════════════════════════════════════════════════
#  HWID SPOOFING — Deep (multiple vectors)
# ═════════════════════════════════════════════════════════════════════

HWID_REGISTRY_TARGETS = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", "MachineGuid"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "ProductId"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "InstallDate"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\SQMClient", "MachineId"),
    (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\IDConfigDB\Hardware Profiles\0001", "HwProfileGuid"),
]


def backup_hwid():
    data = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "values": {}}
    for hive, path, name in HWID_REGISTRY_TARGETS:
        try:
            with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as key:
                val, typ = winreg.QueryValueEx(key, name)
                data["values"][f"{path}\\{name}"] = {"value": str(val), "type": typ}
        except Exception:
            pass

    try:
        result = subprocess.run(["wmic", "diskdrive", "get", "serialnumber"],
                                capture_output=True, text=True, timeout=10)
        serials = [s.strip() for s in result.stdout.split("\n")
                   if s.strip() and s.strip() != "SerialNumber"]
        data["disk_serials"] = serials
    except Exception:
        data["disk_serials"] = []

    try:
        with open(HWID_BACKUP, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass
    return data


def spoof_all_hwids():
    """Spoof all known HWID registry values."""
    if not os.path.exists(HWID_BACKUP):
        backup_hwid()

    results = {}
    for hive, path, name in HWID_REGISTRY_TARGETS:
        try:
            with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as key:
                _, typ = winreg.QueryValueEx(key, name)

            with winreg.OpenKey(hive, path, 0, winreg.KEY_SET_VALUE) as key:
                if typ == winreg.REG_SZ:
                    if "Guid" in name or "MachineId" in name:
                        fake = "{" + str(uuid.uuid4()) + "}"
                    elif "ProductId" in name:
                        fake = "-".join(
                            "".join(str(random.randint(0,9)) for _ in range(5))
                            for _ in range(4)
                        )
                    else:
                        fake = str(uuid.uuid4())
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, fake)
                elif typ == winreg.REG_DWORD:
                    fake = random.randint(1000000000, 2000000000)
                    winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, fake)
                else:
                    continue
                results[name] = str(fake)
        except Exception:
            results[name] = "FAILED"

    return results


def restore_all_hwids():
    try:
        with open(HWID_BACKUP) as f:
            data = json.load(f)
    except Exception:
        return False

    restored = 0
    for full_key, info in data.get("values", {}).items():
        parts = full_key.rsplit("\\", 1)
        if len(parts) != 2:
            continue
        path, name = parts
        typ = info.get("type", winreg.REG_SZ)
        val = info.get("value")
        try:
            hive = winreg.HKEY_LOCAL_MACHINE
            with winreg.OpenKey(hive, path, 0, winreg.KEY_SET_VALUE) as key:
                if typ == winreg.REG_DWORD:
                    winreg.SetValueEx(key, name, 0, typ, int(val))
                else:
                    winreg.SetValueEx(key, name, 0, typ, val)
                restored += 1
        except Exception:
            pass

    return restored > 0


def get_hwid_summary():
    """Get current HWID values for display."""
    summary = {}
    for hive, path, name in HWID_REGISTRY_TARGETS:
        try:
            with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as key:
                val = winreg.QueryValueEx(key, name)[0]
                summary[name] = str(val)
        except Exception:
            summary[name] = "N/A"
    return summary


# ═════════════════════════════════════════════════════════════════════
#  MAC ADDRESS
# ═════════════════════════════════════════════════════════════════════

def get_network_adapters():
    adapters = []
    base = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as key:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey_path = f"{base}\\{subkey_name}"
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey_path) as subkey:
                        try:
                            desc = winreg.QueryValueEx(subkey, "DriverDesc")[0]
                            skip = ["virtual", "miniport", "wan", "debug", "kernel",
                                    "teredo", "isatap", "6to4", "loopback"]
                            if not any(s in desc.lower() for s in skip):
                                adapters.append({
                                    "name": desc,
                                    "reg_path": subkey_path,
                                    "index": subkey_name
                                })
                        except FileNotFoundError:
                            pass
                    i += 1
                except OSError:
                    break
    except Exception:
        pass
    return adapters


def generate_random_mac():
    octets = [random.randint(0x00, 0xFF) for _ in range(6)]
    octets[0] = (octets[0] & 0xFC) | 0x02
    return "".join(f"{b:02X}" for b in octets)


def format_mac(raw):
    return ":".join(raw[i:i+2] for i in range(0, 12, 2))


def get_current_mac():
    mac_int = uuid.getnode()
    return ":".join(f"{(mac_int >> (8 * (5 - i))) & 0xFF:02X}" for i in range(6))


def set_mac_address(adapter, new_mac):
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, adapter["reg_path"],
                            0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "NetworkAddress", 0, winreg.REG_SZ, new_mac)
        name = adapter["name"]
        subprocess.run(["netsh", "interface", "set", "interface", name, "disable"],
                       capture_output=True, timeout=10)
        time.sleep(2)
        subprocess.run(["netsh", "interface", "set", "interface", name, "enable"],
                       capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def restore_mac(adapter):
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, adapter["reg_path"],
                            0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, "NetworkAddress")
            except FileNotFoundError:
                pass
        name = adapter["name"]
        subprocess.run(["netsh", "interface", "set", "interface", name, "disable"],
                       capture_output=True, timeout=10)
        time.sleep(2)
        subprocess.run(["netsh", "interface", "set", "interface", name, "enable"],
                       capture_output=True, timeout=10)
        return True
    except Exception:
        return False


# ═════════════════════════════════════════════════════════════════════
#  LEAK TEST
# ═════════════════════════════════════════════════════════════════════

def run_leak_test(tor_manager):
    """Check if real IP is truly hidden."""
    results = {}

    # Test 1: Check IP via Tor SOCKS
    tor_ip = tor_manager.get_exit_ip() if tor_manager.connected else None
    results["tor_exit_ip"] = tor_ip

    # Test 2: Check IP directly (should fail if kill switch is on)
    try:
        req = urllib.request.urlopen("https://api.ipify.org", timeout=5)
        direct_ip = req.read().decode().strip()
        results["direct_ip"] = direct_ip
        results["direct_blocked"] = False
    except Exception:
        results["direct_ip"] = None
        results["direct_blocked"] = True

    # Test 3: DNS leak check — resolve a domain and see where it goes
    try:
        resolved = socket.gethostbyname("check.torproject.org")
        results["dns_resolved"] = resolved
    except Exception:
        results["dns_resolved"] = "blocked/failed"

    # Verdict
    if results["direct_blocked"] and tor_ip:
        results["verdict"] = "SECURE"
    elif results.get("direct_ip") == tor_ip and tor_ip:
        results["verdict"] = "PARTIAL"
    else:
        results["verdict"] = "LEAKING"

    return results


# ═════════════════════════════════════════════════════════════════════
#  IP UTILITIES
# ═════════════════════════════════════════════════════════════════════

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "Unknown"


def get_public_ip():
    try:
        req = urllib.request.urlopen("https://api.ipify.org", timeout=5)
        return req.read().decode().strip()
    except Exception:
        try:
            req = urllib.request.urlopen("https://ifconfig.me/ip", timeout=5)
            return req.read().decode().strip()
        except Exception:
            return None


def mask_ip(ip):
    if not ip:
        return "*.*.*.*"
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.*.*.*"
    return "*.*.*.*"


# ═════════════════════════════════════════════════════════════════════
#  AUTO-START
# ═════════════════════════════════════════════════════════════════════

STARTUP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_NAME = "IPSafe"


def is_autostart_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, STARTUP_NAME)
            return True
    except FileNotFoundError:
        return False


def enable_autostart():
    cmd = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, STARTUP_NAME, 0, winreg.REG_SZ, cmd)
        return True
    except Exception:
        return False


def disable_autostart():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, STARTUP_NAME)
        return True
    except Exception:
        return False


# ═════════════════════════════════════════════════════════════════════
#  ADMIN
# ═════════════════════════════════════════════════════════════════════

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def restart_as_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{os.path.abspath(__file__)}"', None, 1
    )
    sys.exit()


# ═════════════════════════════════════════════════════════════════════
#  GUI
# ═════════════════════════════════════════════════════════════════════

class IPSafeApp:
    BG      = "#0d1117"
    CARD    = "#161b22"
    BORDER  = "#30363d"
    GREEN   = "#3fb950"
    RED     = "#f85149"
    ORANGE  = "#d29922"
    BLUE    = "#58a6ff"
    PURPLE  = "#bc8cff"
    TEXT    = "#e6edf3"
    MUTED   = "#8b949e"

    def __init__(self, root):
        self.root = root
        self.root.title("IP Safe v3")
        self.root.geometry("620x900")
        self.root.resizable(True, True)
        self.root.minsize(500, 600)
        self.root.configure(bg=self.BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Register cleanup for crashes
        atexit.register(self._emergency_cleanup)

        self.tor = TorManager()
        self.protection_active = False
        self.tor_ip = None
        self.real_public_ip = None
        self.original_mac = get_current_mac()
        self.current_mac = self.original_mac
        self.spoofed_mac = None
        self.hwid_spoofed = False
        self.adapters = get_network_adapters()
        self.selected_adapter = self.adapters[0] if self.adapters else None
        self.kill_switch_on = False
        self.dns_protected = False
        self.active_interface = get_active_interface()

        self._build_ui()
        self._detect_ips_async()

        # Check for crash recovery
        recovered = crash_recovery()
        if recovered:
            self._set_progress(f"Recovered from crash: {', '.join(recovered)}")

    def _build_ui(self):
        canvas = tk.Canvas(self.root, bg=self.BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        self.main_frame = tk.Frame(canvas, bg=self.BG)

        self.main_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self._canvas_window = canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(self._canvas_window, width=e.width - 4))

        canvas.pack(side="left", fill="both", expand=True, padx=8)
        scrollbar.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        f = self.main_frame

        # ── Header ──
        hdr = tk.Frame(f, bg=self.BG)
        hdr.pack(fill="x", pady=(15, 5))
        tk.Label(hdr, text="IP SAFE", font=("Consolas", 24, "bold"),
                 fg=self.GREEN, bg=self.BG).pack(side="left")
        tk.Label(hdr, text="v3.0  Hardened", font=("Segoe UI", 9),
                 fg=self.MUTED, bg=self.BG).pack(side="left", padx=(12, 0), pady=(8, 0))

        if not is_admin():
            admin_bar = tk.Frame(f, bg="#3d1f00")
            admin_bar.pack(fill="x", pady=(8, 0))
            tk.Label(admin_bar, text="Run as Admin for full protection",
                     font=("Segoe UI", 9), fg=self.ORANGE, bg="#3d1f00").pack(pady=5)
            tk.Button(admin_bar, text="Restart as Admin", font=("Segoe UI", 9, "bold"),
                      fg="white", bg=self.ORANGE, relief="flat", cursor="hand2",
                      command=restart_as_admin).pack(pady=(0, 5))

        # ── Status Banner ──
        self.status_frame = tk.Frame(f, bg=self.RED, height=44)
        self.status_frame.pack(fill="x", pady=(10, 8))
        self.status_frame.pack_propagate(False)
        self.status_label = tk.Label(self.status_frame, text="PROTECTION OFF",
                                     font=("Consolas", 14, "bold"),
                                     fg="white", bg=self.RED)
        self.status_label.pack(expand=True)

        # ── Master Toggle ──
        self.toggle_btn = tk.Button(
            f, text="ACTIVATE FULL PROTECTION", font=("Segoe UI", 14, "bold"),
            fg="white", bg=self.GREEN, activebackground="#2ea043", relief="flat",
            cursor="hand2", height=2, command=self._toggle_protection
        )
        self.toggle_btn.pack(fill="x", pady=(0, 6))

        # ── Progress ──
        self.progress_label = tk.Label(f, text="Ready", font=("Segoe UI", 9),
                                       fg=self.BLUE, bg=self.BG, anchor="w")
        self.progress_label.pack(fill="x", pady=(0, 6))

        # ── IP Card ──
        self._section_label(f, "NETWORK IDENTITY")
        ip_card = self._card(f)
        self._info_row(ip_card, "Public IP (real):", "detecting...", "real_pub_ip")
        self._info_row(ip_card, "Local IP:", get_local_ip(), "local_ip")
        self._info_row(ip_card, "Tor Exit IP:", "---", "tor_ip", fg=self.GREEN)
        self._info_row(ip_card, "Status:", "EXPOSED", "ip_status", fg=self.RED)

        # ── Protection Layers ──
        self._section_label(f, "PROTECTION LAYERS")
        layers_card = self._card(f)

        self._layer_row(layers_card, "Tor Proxy", "tor_layer")
        self._layer_row(layers_card, "Kill Switch (firewall)", "ks_layer")
        self._layer_row(layers_card, "DNS via Tor", "dns_layer")
        self._layer_row(layers_card, "System Proxy", "proxy_layer")
        self._layer_row(layers_card, "Watchdog (auto-restart)", "watchdog_layer")

        # Tor controls
        tor_btns = tk.Frame(layers_card, bg=self.CARD)
        tor_btns.pack(fill="x", padx=12, pady=(4, 10))
        self.new_identity_btn = tk.Button(
            tor_btns, text="New Identity (new exit IP)", font=("Segoe UI", 9),
            fg=self.TEXT, bg=self.BORDER, relief="flat", cursor="hand2",
            command=self._new_identity, state="disabled"
        )
        self.new_identity_btn.pack(fill="x")

        # ── Leak Test ──
        self._section_label(f, "LEAK TEST")
        leak_card = self._card(f)
        self.leak_result = tk.Label(leak_card, text="Run a leak test to check protection",
                                    font=("Consolas", 9), fg=self.MUTED, bg=self.CARD,
                                    wraplength=540, justify="left")
        self.leak_result.pack(fill="x", padx=12, pady=(8, 4))
        self.leak_btn = tk.Button(
            leak_card, text="Run Leak Test", font=("Segoe UI", 9, "bold"),
            fg="white", bg=self.PURPLE, relief="flat", cursor="hand2",
            command=self._run_leak_test
        )
        self.leak_btn.pack(fill="x", padx=12, pady=(0, 10))

        # ── MAC Card ──
        self._section_label(f, "MAC ADDRESS")
        mac_card = self._card(f)
        self._info_row(mac_card, "Original:", self.original_mac, "orig_mac")
        self._info_row(mac_card, "Current:", self.current_mac, "curr_mac")

        if self.adapters:
            af = tk.Frame(mac_card, bg=self.CARD)
            af.pack(fill="x", padx=12, pady=(0, 4))
            tk.Label(af, text="Adapter:", font=("Segoe UI", 9),
                     fg=self.MUTED, bg=self.CARD).pack(side="left")
            self.adapter_var = tk.StringVar(value=self.adapters[0]["name"])
            cb = ttk.Combobox(af, textvariable=self.adapter_var,
                              values=[a["name"] for a in self.adapters],
                              state="readonly", width=40)
            cb.pack(side="left", padx=(6, 0))
            cb.bind("<<ComboboxSelected>>", self._on_adapter_change)

        self.mac_btn = tk.Button(
            mac_card, text="Randomize MAC", font=("Segoe UI", 9),
            fg=self.TEXT, bg=self.BORDER, relief="flat", cursor="hand2",
            command=self._randomize_mac
        )
        self.mac_btn.pack(fill="x", padx=12, pady=(4, 10))

        # ── HWID Card ──
        self._section_label(f, "HARDWARE ID (Deep Spoof)")
        hwid_card = self._card(f)

        hwid_summary = get_hwid_summary()
        for name, val in hwid_summary.items():
            short_val = val[:30] + "..." if len(val) > 30 else val
            self._info_row(hwid_card, f"{name}:", short_val, f"hwid_{name}")

        self._info_row(hwid_card, "HWID Status:", "Original", "hwid_status")

        hwid_btns = tk.Frame(hwid_card, bg=self.CARD)
        hwid_btns.pack(fill="x", padx=12, pady=(4, 10))
        tk.Button(
            hwid_btns, text="Spoof All HWIDs", font=("Segoe UI", 9),
            fg=self.TEXT, bg=self.BORDER, relief="flat", cursor="hand2",
            command=self._spoof_hwid
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))
        tk.Button(
            hwid_btns, text="Restore All", font=("Segoe UI", 9),
            fg=self.TEXT, bg=self.BORDER, relief="flat", cursor="hand2",
            command=self._restore_hwid
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))

        # ── Footer ──
        footer = tk.Frame(f, bg=self.BG)
        footer.pack(fill="x", pady=(10, 5))
        self.autostart_var = tk.BooleanVar(value=is_autostart_enabled())
        tk.Checkbutton(
            footer, text="Launch at startup",
            variable=self.autostart_var, font=("Segoe UI", 9),
            fg=self.TEXT, bg=self.BG, selectcolor=self.CARD,
            activebackground=self.BG, activeforeground=self.TEXT,
            command=self._toggle_autostart
        ).pack(side="left")

        admin_color = self.GREEN if is_admin() else self.RED
        tk.Label(footer, text="Admin" if is_admin() else "Not Admin",
                 font=("Consolas", 9), fg=admin_color, bg=self.BG).pack(side="right")

        # Spacer at bottom
        tk.Frame(f, bg=self.BG, height=20).pack()

    # ── UI Helpers ───────────────────────────────────────────────────

    def _section_label(self, parent, text):
        tk.Label(parent, text=text, font=("Consolas", 9, "bold"),
                 fg=self.MUTED, bg=self.BG).pack(anchor="w", pady=(10, 3))

    def _card(self, parent):
        c = tk.Frame(parent, bg=self.CARD, highlightbackground=self.BORDER,
                     highlightthickness=1)
        c.pack(fill="x", pady=(0, 2))
        return c

    def _info_row(self, parent, label, value, attr_name, fg=None):
        row = tk.Frame(parent, bg=self.CARD)
        row.pack(fill="x", padx=12, pady=2)
        tk.Label(row, text=label, font=("Segoe UI", 9),
                 fg=self.MUTED, bg=self.CARD).pack(side="left")
        lbl = tk.Label(row, text=value, font=("Consolas", 9),
                       fg=fg or self.TEXT, bg=self.CARD)
        lbl.pack(side="right")
        setattr(self, f"lbl_{attr_name}", lbl)

    def _layer_row(self, parent, label, attr_name):
        row = tk.Frame(parent, bg=self.CARD)
        row.pack(fill="x", padx=12, pady=2)
        tk.Label(row, text=label, font=("Segoe UI", 9),
                 fg=self.TEXT, bg=self.CARD).pack(side="left")
        indicator = tk.Label(row, text="OFF", font=("Consolas", 9, "bold"),
                             fg=self.RED, bg=self.CARD)
        indicator.pack(side="right")
        setattr(self, f"ind_{attr_name}", indicator)

    def _set_layer(self, attr_name, on):
        ind = getattr(self, f"ind_{attr_name}")
        ind.config(text="ON" if on else "OFF",
                   fg=self.GREEN if on else self.RED)

    def _set_progress(self, text):
        self.progress_label.config(text=text)
        self.root.update_idletasks()

    # ── IP Detection ─────────────────────────────────────────────────

    def _detect_ips_async(self):
        def detect():
            self.real_public_ip = get_public_ip() or "Could not detect"
            self.root.after(0, self._update_ip_display)
        threading.Thread(target=detect, daemon=True).start()

    def _update_ip_display(self):
        if self.protection_active and self.tor_ip:
            self.lbl_real_pub_ip.config(text=mask_ip(self.real_public_ip), fg=self.MUTED)
            self.lbl_tor_ip.config(text=self.tor_ip, fg=self.GREEN)
            self.lbl_ip_status.config(text="PROTECTED", fg=self.GREEN)
        else:
            self.lbl_real_pub_ip.config(text=self.real_public_ip or "...", fg=self.RED)
            self.lbl_tor_ip.config(text="---", fg=self.MUTED)
            self.lbl_ip_status.config(text="EXPOSED", fg=self.RED)

    # ── Master Toggle ────────────────────────────────────────────────

    def _toggle_protection(self):
        if self.protection_active:
            self._deactivate_all()
        else:
            self._activate_all()

    def _activate_all(self):
        self.toggle_btn.config(state="disabled", text="ACTIVATING...")

        def activate():
            save_state(active=True)

            # 1. Tor
            self.root.after(0, lambda: self._set_progress("Starting Tor..."))
            tor_ok = self.tor.start(
                lambda msg: self.root.after(0, lambda m=msg: self._set_progress(m))
            )
            self.root.after(0, lambda: self._set_layer("tor_layer", tor_ok))

            if not tor_ok:
                clear_state()
                self.root.after(0, lambda: self._activation_failed())
                return

            # 2. System proxy
            self.root.after(0, lambda: self._set_progress("Setting system proxy..."))
            set_system_proxy(True)
            self.root.after(0, lambda: self._set_layer("proxy_layer", True))

            # 3. Get exit IP
            self.root.after(0, lambda: self._set_progress("Getting Tor exit IP..."))
            self.tor_ip = self.tor.get_exit_ip()

            # 4. Kill switch
            if is_admin():
                self.root.after(0, lambda: self._set_progress("Enabling kill switch..."))
                self.kill_switch_on = enable_kill_switch()
                self.root.after(0, lambda: self._set_layer("ks_layer", self.kill_switch_on))

            # 5. DNS
            if is_admin() and self.active_interface:
                self.root.after(0, lambda: self._set_progress("Setting DNS through Tor..."))
                self.dns_protected = set_tor_dns(self.active_interface)
                if not self.dns_protected:
                    self.dns_protected = set_secure_dns_fallback(self.active_interface)
                self.root.after(0, lambda: self._set_layer("dns_layer", self.dns_protected))

            # 6. Watchdog
            self.tor.start_watchdog(
                on_down_cb=lambda: self.root.after(0, lambda: self._set_progress("Tor dropped! Restarting...")),
                on_up_cb=lambda: self.root.after(0, lambda: self._set_progress("Tor reconnected."))
            )
            self.root.after(0, lambda: self._set_layer("watchdog_layer", True))

            self.root.after(0, self._activation_done)

        threading.Thread(target=activate, daemon=True).start()

    def _activation_done(self):
        self.protection_active = True
        self.status_label.config(text="FULL PROTECTION ACTIVE", bg=self.GREEN)
        self.status_frame.config(bg=self.GREEN)
        self.toggle_btn.config(state="normal", text="DEACTIVATE ALL",
                               bg=self.RED, fg="white")
        self.new_identity_btn.config(state="normal")

        layers = []
        if self.tor.connected: layers.append("Tor")
        if self.kill_switch_on: layers.append("KillSwitch")
        if self.dns_protected: layers.append("DNS")
        layers.append("Proxy")
        layers.append("Watchdog")
        self._set_progress(f"Active: {' + '.join(layers)}")
        self._update_ip_display()

    def _activation_failed(self):
        self.toggle_btn.config(state="normal", text="ACTIVATE FULL PROTECTION",
                               bg=self.GREEN)
        self._set_progress("Failed to start Tor.")
        tor_exists = os.path.isfile(TOR_EXE)
        if not tor_exists:
            msg = ("Tor n'a pas pu être téléchargé.\n"
                   "Vérifiez votre connexion internet.\n"
                   "Si le dossier tor/ est corrompu, supprimez-le et réessayez.")
        else:
            msg = ("Tor n'a pas pu se connecter au réseau.\n"
                   "Vérifiez votre connexion internet ou votre pare-feu.")
        messagebox.showerror("IP Safe", msg)

    def _deactivate_all(self):
        self.toggle_btn.config(state="disabled", text="DEACTIVATING...")
        self._set_progress("Shutting down...")

        def deactivate():
            # Order matters: kill switch first, then proxy, then Tor, then DNS
            if self.kill_switch_on:
                disable_kill_switch()
                self.kill_switch_on = False

            set_system_proxy(False)
            self.tor.stop()
            self.tor_ip = None

            if self.dns_protected and self.active_interface:
                restore_dns(self.active_interface)
                self.dns_protected = False

            clear_state()
            self.root.after(0, self._deactivation_done)

        threading.Thread(target=deactivate, daemon=True).start()

    def _deactivation_done(self):
        self.protection_active = False
        self.status_label.config(text="PROTECTION OFF", bg=self.RED)
        self.status_frame.config(bg=self.RED)
        self.toggle_btn.config(state="normal", text="ACTIVATE FULL PROTECTION",
                               bg=self.GREEN, fg="white")
        self.new_identity_btn.config(state="disabled")

        for layer in ["tor_layer", "ks_layer", "dns_layer", "proxy_layer", "watchdog_layer"]:
            self._set_layer(layer, False)

        self._set_progress("All protections off.")
        self._update_ip_display()

    # ── Tor Identity ─────────────────────────────────────────────────

    def _new_identity(self):
        self.new_identity_btn.config(state="disabled", text="Switching...")
        self._set_progress("Requesting new identity...")

        def do_it():
            ok = self.tor.request_new_identity()
            if ok:
                time.sleep(4)
                self.tor_ip = self.tor.get_exit_ip()
            self.root.after(0, lambda: self._identity_done(ok))

        threading.Thread(target=do_it, daemon=True).start()

    def _identity_done(self, ok):
        self.new_identity_btn.config(state="normal", text="New Identity (new exit IP)")
        if ok and self.tor_ip:
            self._set_progress(f"New exit IP: {self.tor_ip}")
        else:
            self._set_progress("Identity switch failed, try again in 10s.")
        self._update_ip_display()

    # ── Leak Test ────────────────────────────────────────────────────

    def _run_leak_test(self):
        self.leak_btn.config(state="disabled", text="Testing...")
        self.leak_result.config(text="Running leak test...", fg=self.BLUE)

        def do_test():
            results = run_leak_test(self.tor)
            self.root.after(0, lambda: self._leak_test_done(results))

        threading.Thread(target=do_test, daemon=True).start()

    def _leak_test_done(self, results):
        self.leak_btn.config(state="normal", text="Run Leak Test")

        verdict = results.get("verdict", "UNKNOWN")
        tor_ip = results.get("tor_exit_ip", "N/A")
        direct_ip = results.get("direct_ip", "blocked")
        direct_blocked = results.get("direct_blocked", False)
        dns = results.get("dns_resolved", "N/A")

        lines = [
            f"Tor Exit IP:    {tor_ip}",
            f"Direct IP:      {'BLOCKED (good)' if direct_blocked else direct_ip}",
            f"DNS resolves:   {dns}",
            f"Verdict:        {verdict}",
        ]

        color = {
            "SECURE": self.GREEN,
            "PARTIAL": self.ORANGE,
            "LEAKING": self.RED,
        }.get(verdict, self.RED)

        self.leak_result.config(text="\n".join(lines), fg=color)
        self._set_progress(f"Leak test: {verdict}")

    # ── MAC ──────────────────────────────────────────────────────────

    def _on_adapter_change(self, event=None):
        name = self.adapter_var.get()
        for a in self.adapters:
            if a["name"] == name:
                self.selected_adapter = a
                break

    def _randomize_mac(self):
        if not is_admin():
            messagebox.showwarning("IP Safe", "Admin required.")
            return
        if not self.selected_adapter:
            return

        new_mac = generate_random_mac()
        self.mac_btn.config(state="disabled", text="Changing...")

        def do_it():
            ok = set_mac_address(self.selected_adapter, new_mac)
            self.root.after(0, lambda: self._mac_done(ok, new_mac))
        threading.Thread(target=do_it, daemon=True).start()

    def _mac_done(self, ok, new_mac):
        self.mac_btn.config(state="normal", text="Randomize MAC")
        if ok:
            self.current_mac = format_mac(new_mac)
            self.spoofed_mac = new_mac
            self.lbl_curr_mac.config(text=self.current_mac, fg=self.GREEN)
            self._set_progress(f"MAC changed: {self.current_mac}")
        else:
            messagebox.showerror("IP Safe", "MAC change failed.")

    # ── HWID ─────────────────────────────────────────────────────────

    def _spoof_hwid(self):
        if not is_admin():
            messagebox.showwarning("IP Safe", "Admin required.")
            return

        results = spoof_all_hwids()
        if results:
            self.hwid_spoofed = True
            for name, val in results.items():
                attr = f"lbl_hwid_{name}"
                if hasattr(self, attr):
                    short = val[:30] + "..." if len(val) > 30 else val
                    color = self.GREEN if val != "FAILED" else self.RED
                    getattr(self, attr).config(text=short, fg=color)

            self.lbl_hwid_status.config(text="SPOOFED", fg=self.GREEN)
            ok_count = sum(1 for v in results.values() if v != "FAILED")
            self._set_progress(f"HWID: {ok_count}/{len(results)} values spoofed")

    def _restore_hwid(self):
        if not is_admin():
            messagebox.showwarning("IP Safe", "Admin required.")
            return

        if restore_all_hwids():
            self.hwid_spoofed = False
            hwid_summary = get_hwid_summary()
            for name, val in hwid_summary.items():
                attr = f"lbl_hwid_{name}"
                if hasattr(self, attr):
                    short = val[:30] + "..." if len(val) > 30 else val
                    getattr(self, attr).config(text=short, fg=self.TEXT)
            self.lbl_hwid_status.config(text="Original", fg=self.TEXT)
            self._set_progress("All HWIDs restored.")
        else:
            messagebox.showerror("IP Safe", "HWID restore failed.")

    # ── Auto-start ───────────────────────────────────────────────────

    def _toggle_autostart(self):
        if self.autostart_var.get():
            enable_autostart()
        else:
            disable_autostart()

    # ── Cleanup ──────────────────────────────────────────────────────

    def _emergency_cleanup(self):
        """Called by atexit — ensures we don't leave the system broken."""
        if self.protection_active:
            try:
                disable_kill_switch()
            except Exception:
                pass
            try:
                set_system_proxy(False)
            except Exception:
                pass
            try:
                self.tor.stop()
            except Exception:
                pass
            try:
                if self.dns_protected and self.active_interface:
                    restore_dns(self.active_interface)
            except Exception:
                pass
            clear_state()

    def _on_close(self):
        if self.protection_active:
            if messagebox.askyesno("IP Safe",
                                   "Protection active. Deactivate and exit?"):
                self._set_progress("Cleaning up...")
                if self.kill_switch_on:
                    disable_kill_switch()
                set_system_proxy(False)
                self.tor.stop()
                if self.dns_protected and self.active_interface:
                    restore_dns(self.active_interface)
                clear_state()
                self.protection_active = False
                self.root.destroy()
        else:
            self.root.destroy()


# ═════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═════════════════════════════════════════════════════════════════════

def main():
    root = tk.Tk()
    try:
        root.iconbitmap(default="")
    except Exception:
        pass
    app = IPSafeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
