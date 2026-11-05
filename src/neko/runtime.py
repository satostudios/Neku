"""Liga o llama-server só quando preciso e o desliga quando fica ocioso, para poupar memória."""
import ctypes, logging, socket, subprocess, sys, threading, time, urllib.error
from ctypes import wintypes
import psutil
from .llm import _opener

log = logging.getLogger(__name__)

START_TIMEOUT = 60
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
# Medido no i5-1235U: 4 threads rendem o mesmo que 8 com metade da CPU, e a prioridade baixa não reduz a velocidade.
DEFAULT_THREADS = 4
LOW_PRIORITY = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)

class _BasicLimits(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in ("reads", "writes", "others", "read_bytes", "write_bytes", "other_bytes")]

class _ExtendedLimits(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", _BasicLimits), ("IoInfo", _IoCounters), ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

def _bind_to_parent(process):
    """Se o Neku cair, o Windows encerra o servidor junto: nada fica rodando escondido."""
    if sys.platform != "win32":
        return None
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    job = kernel32.CreateJobObjectW(None, None)
    limits = _ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = 0x2000
    configured = kernel32.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits))
    if not job or not configured or not kernel32.AssignProcessToJobObject(job, int(process._handle)):
        log.warning("Não foi possível ligar o servidor do modelo ao processo do Neku")
    return job

def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]

class ModelRuntime:
    def __init__(self, root, config):
        self.exe = root / "runtime" / "llama" / "llama-server.exe"
        self.models = root / "models"
        self.config = config
        self.process = None
        self.url = None
        self.job = None
        self.last_used = 0.0
        self.stops = 0
        self.lock = threading.Lock()

    def model_path(self):
        found = sorted(self.models.glob("*.gguf")) if self.models.is_dir() else []
        return found[0] if found else None

    def available(self):
        return self.exe.exists() and self.model_path() is not None

    def command(self, port):
        cfg = self.config.get("llm", {})
        threads = cfg.get("threads") or min(DEFAULT_THREADS, max(2, psutil.cpu_count(logical=False) or DEFAULT_THREADS))
        return [str(self.exe), "-m", str(self.model_path()), "--host", "127.0.0.1", "--port", str(port),
                "-c", str(cfg.get("context_tokens", 2048)), "-t", str(threads), "-np", "1"]

    def running(self):
        return self.process is not None and self.process.poll() is None

    def ensure(self):
        """Devolve a URL do servidor, iniciando-o se preciso; nulo quando não dá para usar o modelo."""
        attempt = self.stops
        with self.lock:
            if attempt != self.stops:
                return None
            self.last_used = time.monotonic()
            if self.running():
                return self.url
            return self._start(attempt)

    def _start(self, attempt):
        port = free_port()
        try:
            self.process = subprocess.Popen(self.command(port), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL, creationflags=NO_WINDOW | LOW_PRIORITY)
        except OSError:
            log.exception("Não foi possível iniciar o servidor do modelo")
            return None
        self.job = _bind_to_parent(self.process)
        if self._wait_ready(port, attempt):
            self.url = f"http://127.0.0.1:{port}/v1/chat/completions"
            log.info("Servidor do modelo iniciado")
            return self.url
        if attempt == self.stops:
            log.warning("O servidor do modelo não ficou pronto")
        self._stop_process()
        return None

    def _wait_ready(self, port, attempt):
        limit = time.monotonic() + START_TIMEOUT
        while time.monotonic() < limit and self.running() and attempt == self.stops:
            try:
                with _opener.open(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                    if response.status == 200:
                        return True
            except urllib.error.HTTPError as error:
                if error.code != 503:
                    return False
            except OSError:
                pass
            time.sleep(0.25)
        return False

    def _stop_process(self):
        process, self.process, self.url = self.process, None, None
        if process is None:
            return
        process.terminate()
        try:
            process.wait(3)
        except subprocess.TimeoutExpired:
            process.kill()

    def stop(self):
        """Cancela também uma partida em andamento: carregar o modelo pode levar dezenas de segundos."""
        self.stops += 1
        with self.lock:
            self._stop_process()

    def stop_if_idle(self):
        """Roda na thread da interface: se o modelo está iniciando, não há o que descarregar nem por que esperar."""
        limit = self.config.get("llm", {}).get("idle_unload_minutes", 5) * 60
        if not self.lock.acquire(blocking=False):
            return
        try:
            if self.running() and time.monotonic() - self.last_used > limit:
                log.info("Servidor do modelo desligado por ociosidade")
                self._stop_process()
        finally:
            self.lock.release()
