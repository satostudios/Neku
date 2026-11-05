import http.client, ipaddress, json, logging, re, urllib.request
from urllib.parse import urlsplit

log = logging.getLogger(__name__)

MAX_RESPONSE_BYTES = 1_000_000
MAX_MESSAGE_CHARS = 1000
REPLY_TOKENS = 220
MIN_ROOM = 40  # a sua mensagem sempre chega ao modelo, mesmo cortada, por maior que seja o prompt
CHARS_PER_TOKEN = 3.5
TEMPERATURE = 0.4

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

# Sem proxy e sem redirecionamento: a chamada nunca sai do endereço de loopback.
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)

def is_local_endpoint(url):
    try:
        parts = urlsplit(url)
        host = ipaddress.ip_address(parts.hostname or "")
        parts.port
    except ValueError:
        return False
    return parts.scheme == "http" and host.is_loopback and not parts.username and not parts.password

def estimate_tokens(text):
    return int(len(text) / CHARS_PER_TOKEN) + 1

def fit_messages(messages, system, context_tokens):
    """Mantém as mensagens mais novas que couberem junto do prompt e da resposta."""
    room = max(MIN_ROOM, context_tokens - REPLY_TOKENS - estimate_tokens(system))
    chosen = []
    for message in reversed(messages[-6:]):
        content = message["content"][:MAX_MESSAGE_CHARS]
        cost = estimate_tokens(content) + 4
        if cost > room:
            if not chosen and room > 8:
                content = content[:int((room - 4) * CHARS_PER_TOKEN)]
                chosen.append({"role":message["role"], "content":content})
            break
        room -= cost
        chosen.insert(0, {"role":message["role"], "content":content})
    while chosen and chosen[0]["role"] != "user":
        chosen.pop(0)
    return chosen

def trim_to_sentence(text):
    """Quando o limite de tokens corta a resposta, termina na última frase completa."""
    ends = list(re.finditer(r"[.!?…](?=\s|$)", text))
    return text[:ends[-1].end()].strip() if ends else text.strip()

def _finish(text, reason):
    if not text:
        return None
    return (trim_to_sentence(text) if reason == "length" else text.strip()) or None

def _parse(body):
    try:
        choice = json.loads(body)["choices"][0]
        content, reason = choice["message"]["content"], choice.get("finish_reason")
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        return None
    return _finish(content, reason) if isinstance(content, str) else None

def _read_stream(response, on_token):
    parts = []
    size = 0
    reason = None
    for raw in response:
        size += len(raw)
        if size > MAX_RESPONSE_BYTES:
            break
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            choice = json.loads(data)["choices"][0]
            token = choice["delta"].get("content")
            reason = choice.get("finish_reason") or reason
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            continue
        if isinstance(token, str) and token:
            parts.append(token)
            on_token(token)
    return _finish("".join(parts), reason)

class LocalLLM:
    def __init__(self, config, runtime=None):
        self.config, self.runtime = config, runtime

    def _bundled(self, cfg):
        return bool(self.runtime and cfg.get("use_bundled") and self.runtime.available())

    def enabled(self):
        cfg = self.config.get("llm", {})
        return bool(cfg.get("enabled") or self._bundled(cfg))

    def name(self):
        cfg = self.config.get("llm", {})
        return self.runtime.model_path().stem if self._bundled(cfg) else cfg.get("model", "configurado")

    def reply(self, system, messages, on_token=None, examples=()):
        cfg = self.config.get("llm", {})
        if not self.enabled():
            return None
        endpoint = self.runtime.ensure() if self._bundled(cfg) else cfg["endpoint"]
        if not endpoint:
            return None
        if not is_local_endpoint(endpoint):
            log.warning("Endpoint do LLM recusado: apenas endereços de loopback são permitidos")
            return None
        fixed = system + "".join(example["content"] for example in examples)
        recent = fit_messages(messages, fixed, cfg.get("context_tokens", 2048))
        payload = {"model":cfg.get("model","local-model"),
                   "messages":[{"role":"system","content":system}] + list(examples) + recent,
                   "temperature":TEMPERATURE,"max_tokens":REPLY_TOKENS,"stream":bool(on_token)}
        req = urllib.request.Request(endpoint, data=json.dumps(payload).encode(),
                                     headers={"Content-Type":"application/json"}, method="POST")
        try:
            with _opener.open(req, timeout=cfg["timeout_seconds"]) as r:
                if on_token:
                    return _read_stream(r, on_token)
                return _parse(r.read(MAX_RESPONSE_BYTES))
        except (OSError, http.client.HTTPException) as e:
            log.warning("LLM local indisponível: %s", type(e).__name__)
            return None
