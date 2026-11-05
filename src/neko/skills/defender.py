"""Verificação pelo Microsoft Defender, local e sem instalar nada. Não remove nem coloca em quarentena."""
import logging, os, subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

SCAN_TIMEOUT = 900
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

@dataclass
class ScanResult:
    status: str

    @property
    def clean(self):
        return self.status == "clean"

    @property
    def threat(self):
        return self.status == "threat"

def engine():
    return Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Windows Defender" / "MpCmdRun.exe"

def scan(path):
    tool = engine()
    if not tool.exists():
        return ScanResult("unavailable")
    try:
        result = subprocess.run([str(tool), "-Scan", "-ScanType", "3", "-File", str(path), "-DisableRemediation"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=SCAN_TIMEOUT, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        log.exception("Falha ao executar o Defender")
        return ScanResult("unavailable")
    if result.returncode == 0:
        return ScanResult("clean")
    if result.returncode == 2:
        return ScanResult("threat")
    log.warning("Defender terminou com o código %s", result.returncode)
    return ScanResult("unavailable")
