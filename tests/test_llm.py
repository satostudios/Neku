import importlib, json, os, unittest
from unittest import mock
from helpers import FakeServer, TempRootCase
from neko import llm
from neko.config import Config
from neko.llm import LocalLLM, estimate_tokens, is_local_endpoint

USER = [{"role":"user","content":"oi"}]

class EndpointTests(unittest.TestCase):
    def test_only_loopback_http_is_local(self):
        allowed = ["http://127.0.0.1:8080/v1/chat/completions", "http://127.0.0.1/", "http://[::1]:8080/"]
        refused = ["https://servidor.example/v1", "http://192.168.0.10:8080/", "http://localhost:8080/",
                   "https://127.0.0.1:8080/", "file:///C:/Windows/win.ini", "isto nao e url", "",
                   "http://127.0.0.1@servidor.example/", "http://127.0.0.1:8080@servidor.example/",
                   "http://usuario:senha@127.0.0.1/", "http://127.0.0.1:99999/"]
        for url in allowed:
            self.assertTrue(is_local_endpoint(url), url)
        for url in refused:
            self.assertFalse(is_local_endpoint(url), url)

class ReplyTests(TempRootCase):
    def setUp(self):
        super().setUp()
        self.config = Config(self.root)
        self.config.data["llm"]["enabled"] = True

    def serve(self, **kwargs):
        server = FakeServer(**kwargs)
        self.addCleanup(server.close)
        self.config.data["llm"]["endpoint"] = server.url
        return server

    def test_disabled_sends_nothing(self):
        self.config.data["llm"]["enabled"] = False
        server = self.serve()
        self.assertIsNone(LocalLLM(self.config).reply("s", USER))
        self.assertEqual(server.requests, [])

    def test_returns_clean_content(self):
        self.serve(body=b'{"choices":[{"message":{"content":"  ola  "}}]}')
        self.assertEqual(LocalLLM(self.config).reply("s", USER), "ola")

    def test_external_endpoint_is_never_called(self):
        self.config.data["llm"]["endpoint"] = "https://servidor.example/v1/chat/completions"
        with mock.patch.object(llm._opener, "open") as opened:
            self.assertIsNone(LocalLLM(self.config).reply("s", USER))
        opened.assert_not_called()

    def test_proxy_variables_are_ignored(self):
        server = self.serve()
        proxy = FakeServer()
        self.addCleanup(proxy.close)
        address = proxy.url.rsplit("/v1", 1)[0]
        self.addCleanup(importlib.reload, llm)
        with mock.patch.dict(os.environ, {"HTTP_PROXY":address, "http_proxy":address}):
            # O proxy do ambiente é lido ao montar o opener, então o módulo precisa carregar com ele.
            importlib.reload(llm)
            self.assertEqual(LocalLLM(self.config).reply("segredo", USER), "resposta do modelo")
        self.assertEqual(proxy.requests, [])
        self.assertEqual(len(server.requests), 1)

    def test_redirect_is_not_followed(self):
        target = FakeServer()
        self.addCleanup(target.close)
        self.serve(status=302, headers=[("Location", target.url)])
        self.assertIsNone(LocalLLM(self.config).reply("s", USER))
        self.assertEqual(target.requests, [])

    def test_unexpected_answers_become_none(self):
        bodies = [b'{"choices":[]}', b'{"choices":[{"message":{"content":null}}]}', b'[]', b'null',
                  b'{"choices":[{"message":{"content":""}}]}', b'{"choices":[{"message":{"content":42}}]}',
                  b'nao e json', b'{"erro":"x"}', b'\xff\xfe']
        for body in bodies:
            with self.subTest(body=body):
                self.serve(body=body)
                self.assertIsNone(LocalLLM(self.config).reply("s", USER))

    def test_cut_answer_ends_on_a_complete_sentence(self):
        body = json.dumps({"choices":[{"message":{"content":"Primeira frase. Segunda frase incompl"},"finish_reason":"length"}]}).encode()
        self.serve(body=body)
        self.assertEqual(LocalLLM(self.config).reply("s", USER), "Primeira frase.")

    def test_complete_answer_is_untouched(self):
        body = json.dumps({"choices":[{"message":{"content":"Primeira. Segunda sem ponto"},"finish_reason":"stop"}]}).encode()
        self.serve(body=body)
        self.assertEqual(LocalLLM(self.config).reply("s", USER), "Primeira. Segunda sem ponto")

    def test_examples_count_in_the_context_budget(self):
        server = self.serve()
        self.config.data["llm"]["context_tokens"] = 600
        examples = [{"role":"user","content":"x" * 600}, {"role":"assistant","content":"y" * 600}]
        history = [{"role":"user" if i % 2 == 0 else "assistant","content":"z" * 300} for i in range(5)]
        LocalLLM(self.config).reply("s", history, None, examples)
        sent = server.requests[-1]["messages"]
        self.assertLessEqual(sum(estimate_tokens(m["content"]) + 4 for m in sent), 600 - 160 + 20)
        self.assertEqual(sent[-1]["role"], "user")

    def test_http_error_becomes_none(self):
        self.serve(status=500)
        self.assertIsNone(LocalLLM(self.config).reply("s", USER))

    def test_server_offline_becomes_none(self):
        self.config.data["llm"]["endpoint"] = "http://127.0.0.1:9/v1/chat/completions"
        self.assertIsNone(LocalLLM(self.config).reply("s", USER))

    def test_history_always_starts_with_user(self):
        server = self.serve()
        history = []
        for turn in range(8):
            history.append({"role":"user","content":str(turn)})
            LocalLLM(self.config).reply("s", history)
            history.append({"role":"assistant","content":"r"})
            roles = [m["role"] for m in server.requests[-1]["messages"]]
            self.assertEqual(roles[:2], ["system", "user"])
            self.assertEqual(roles[-1], "user")
