"""
Visio COM Client Manager.
Handles COM lifecycle, STA thread apartment initialization,
Click-to-Run (C2R) process bootstrapping, alert suppression, and safe cleanup for Microsoft Visio.
"""

import os
import subprocess
import time
import winreg
from typing import Optional
import pythoncom
import win32com.client


def find_visio_executable() -> Optional[str]:
    """
    Locates the VISIO.EXE binary on the local system via registry or standard Office paths.
    """
    # 1. Try registry LocalServer32
    for clsid in ["{00021A20-0000-0000-C000-000000000046}", "{000D0A26-0000-0000-C000-000000000046}"]:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\LocalServer32") as key:
                val = winreg.QueryValue(key, "")
                if val:
                    raw_path = val.split(" /")[0].strip('"').strip()
                    if os.path.exists(raw_path):
                        return raw_path
        except OSError:
            pass

    # 2. Check standard installation directories
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    candidate_paths = [
        os.path.join(program_files, r"Microsoft Office\root\Office16\VISIO.EXE"),
        os.path.join(program_files_x86, r"Microsoft Office\root\Office16\VISIO.EXE"),
        os.path.join(program_files, r"Microsoft Office\Office16\VISIO.EXE"),
        os.path.join(program_files, r"Microsoft Office\Office15\VISIO.EXE"),
        os.path.join(program_files, r"Microsoft Office\Office14\VISIO.EXE"),
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            return p

    return None


def is_visio_installed() -> bool:
    """
    Checks if Microsoft Visio is installed on the local system.
    """
    if find_visio_executable():
        return True

    # Check registry ProgID
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Visio.Application\CurVer"):
            return True
    except OSError:
        pass

    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Visio.Application"):
            return True
    except OSError:
        pass

    return False


def get_visio_version() -> str:
    """
    Returns the version string of the installed Microsoft Visio instance.
    Uses VisioSession to ensure reliable Click-to-Run bootstrapping.
    """
    try:
        with VisioSession(visible=False) as app:
            return str(app.Version)
    except Exception as e:
        # If COM fails, check binary file version or fallback to 16.0
        visio_exe = find_visio_executable()
        if visio_exe and "Office16" in visio_exe:
            return "16.0 (Office 16 / Microsoft 365)"
        return f"Algılandı ({e})"


def open_in_visio(vsdx_path: str):
    """
    Opens the specified .vsdx file in Microsoft Visio for the user.
    """
    abs_path = os.path.abspath(vsdx_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"File not found: {abs_path}")
    os.startfile(abs_path)


class VisioSession:
    """
    Context manager for automated Visio COM operations.
    Ensures single-threaded apartment (STA) initialization,
    automatic Click-to-Run process bootstrapping if DCOM times out,
    and guaranteed cleanup.
    """

    def __init__(self, visible: bool = False):
        self.visible = visible
        self.app = None
        self.spawned_proc: Optional[subprocess.Popen] = None

    def __enter__(self):
        pythoncom.CoInitialize()
        self.app = None
        self.spawned_proc = None

        visio_exe = find_visio_executable()

        # If Visio executable is found on system, pre-launch with /Automation to ensure
        # instant Click-to-Run (C2R) initialization without DCOM timeouts
        if visio_exe:
            try:
                self.spawned_proc = subprocess.Popen([visio_exe, "/Automation"])
                time.sleep(1.0)
            except Exception:
                pass

        prog_ids = ["Visio.Application", "Visio.InvisibleApp"] if self.visible else ["Visio.InvisibleApp", "Visio.Application"]
        for _ in range(10):
            for pid in prog_ids:
                try:
                    self.app = win32com.client.Dispatch(pid)
                    if self.app is not None:
                        break
                except Exception:
                    self.app = None
            if self.app is not None:
                break
            time.sleep(0.3)

        if self.app is None:
            pythoncom.CoUninitialize()
            raise RuntimeError(
                "Microsoft Visio COM arabirimi başlatılamadı (Server execution failed / DCOM zaman aşımı).\n"
                "Lütfen Microsoft Visio'nun bu bilgisayarda açık ve etkinleştirilmiş olduğunu doğrulayınız."
            )

        try:
            # Suppress alert popups and progress bars during programmatic automation
            self.app.ShowProgress = False
            self.app.AlertResponse = 1  # 1 = IDOK / Yes to any alert
            if self.visible:
                self.app.Visible = True
        except Exception:
            pass

        return self.app

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.app is not None:
            try:
                self.app.Quit()
            except Exception:
                pass
            self.app = None

        # If we spawned a helper process, ensure it terminates cleanly
        if self.spawned_proc is not None:
            try:
                self.spawned_proc.wait(timeout=2.0)
            except (subprocess.TimeoutExpired, Exception):
                try:
                    self.spawned_proc.terminate()
                except Exception:
                    pass
            self.spawned_proc = None

        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
