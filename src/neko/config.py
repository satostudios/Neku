import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULTS = {
    "mascot_name":"Neku", "onboarded":False, "agent_onboarded":False, "start_with_windows":False, "monitor_active_app":False,
    "save_chat_history":False, "observation_interval_seconds":30, "observation_paused":False,
    "observation_retention_days":30, "ignored_apps":[], "watch_downloads":False, "learn_language":True,
    "follow_mouse":True, "notebook_visible":False, "animation_level":"full", "scale":1.0, "window_pos":[140,140],
    "permissions":{"open_apps":"ask","open_web":"ask","read_files":"ask","write_files":"ask"},
    "automations":{"extract_zip":False,"extract_zip_declined":False},
    "vision":{"enabled":False,"interval_seconds":8,"retention_days":7,"ignored_titles":[]},
    "llm":{"enabled":False,"use_bundled":True,"endpoint":"http://127.0.0.1:8080/v1/chat/completions",
           "model":"local-model","timeout_seconds":25,"context_tokens":2048,"threads":0,"idle_unload_minutes":5}
}
LIMITS = {"observation_interval_seconds":(10,3600), "timeout_seconds":(1,300), "scale":(0.75,2.0),
          "observation_retention_days":(1,365), "context_tokens":(512,32768), "threads":(0,64),
          "idle_unload_minutes":(1,240), "interval_seconds":(3,300), "retention_days":(1,90)}
CHOICES = {"animation_level":("full","reduced"), "open_apps":("deny","ask","allow"), "open_web":("deny","ask","allow"),
           "read_files":("deny","ask","allow"), "write_files":("deny","ask")}

class Config:
    def __init__(self, root: Path):
        self.path = root / "config" / "settings.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = json.loads(json.dumps(DEFAULTS))
        self.backup_path = None
        self._load()

    def _load(self):
        if not self.path.exists():
            self._save_quietly()
            return
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8-sig"))
            if not isinstance(loaded, dict):
                raise ValueError("a raiz do JSON precisa ser um objeto")
        except OSError:
            # Sem conseguir ler, usa os padrões e nunca toca no arquivo.
            log.exception("Não foi possível ler settings.json")
            return
        except ValueError as e:
            log.warning("settings.json inválido: %s", e)
            if self._backup():
                self._save_quietly()
            return
        self._merge(self.data, loaded)
        problems = self._sanitize(self.data, DEFAULTS)
        if problems:
            log.warning("Valores inválidos trocados pelo padrão: %s", ", ".join(problems))
            if not self._backup():
                return
        if self.data != loaded:
            self._save_quietly()

    def _merge(self, dst, src):
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                self._merge(dst[k], v)
            else:
                dst[k] = v

    def _sanitize(self, data, defaults):
        problems = []
        for key, default in defaults.items():
            value = data.get(key)
            if isinstance(default, dict) and isinstance(value, dict):
                problems += self._sanitize(value, default)
            elif not self._is_valid(key, value, default):
                problems.append(key)
                data[key] = json.loads(json.dumps(default))
        return problems

    @staticmethod
    def _is_valid(key, value, default):
        if isinstance(default, float) and type(value) is int:
            value = float(value)
        if type(value) is not type(default):
            return False
        if key in LIMITS:
            low, high = LIMITS[key]
            return low <= value <= high
        if key in CHOICES:
            return value in CHOICES[key]
        return value != ""

    def _backup(self):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = self.path.with_name(f"{self.path.name}.bak-{stamp}")
        count = 1
        while target.exists():
            target = self.path.with_name(f"{self.path.name}.bak-{stamp}-{count}")
            count += 1
        try:
            shutil.copy2(self.path, target)
        except OSError:
            log.exception("Não foi possível criar o backup de settings.json")
            return False
        self.backup_path = target
        log.info("Backup da configuração criado: %s", target.name)
        return True

    def _save_quietly(self):
        try:
            self.save()
        except OSError:
            log.exception("Não foi possível salvar settings.json")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def save(self):
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
