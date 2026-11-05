import unittest
import helpers
from neko.memory import commands
from neko.memory.commands import categorize, is_secret, parse
from neko.skills.parser import parse as parse_skill

REMEMBER = ["Lembre que eu gosto de café sem açúcar", "Neku, lembra que meu nome é Silva", "lembre-se de que trabalho de casa às sextas",
            "anota aí: reunião amanhã às 15h", "guarda isso: prefiro modo escuro", "não esqueça que minha filha faz aniversário em maio",
            "memorize que uso Windows 11", "por favor lembre que estou no projeto Neku", "salva aí que meu editor é o Antigravity",
            "grave que acordo às 6h", "pode anotar que gosto de jazz", "guarda que prefiro chá",
            # Frases que as regras nunca viram ao serem escritas.
            "você pode lembrar que meu time é o Sport?", "anote isso: a chave fica na gaveta", "Neku, grava aí: amo pizza",
            "por favor, memorize que sou canhoto", "salve que moro em Recife", "lembre que a Ana é minha irmã",
            "não esquece que hoje tem dentista", "guarde que meu aniversário é em março"]
FORGET = ["esqueça que eu gosto de café", "esquece o café", "apague da memória o café", "neko, esquece isso", "tire da memória a reunião",
          "pode esquecer o jazz", "remova da memória o dentista", "por favor, esqueça a reunião de amanhã", "apaga da memória meu time"]
CORRECT = ["corrija: meu nome é Ana", "atualize a memória: moro em Recife", "corrija a memória: prefiro chá", "pode corrigir: tenho 30 anos"]
REPLACE = ["corrija café para chá", "troque café por chá", "corrija na memória Recife para Olinda", "corrige Ana para Maria", "pode trocar segunda por terça"]
QUERY = ["o que você lembra sobre mim?", "você lembra do meu nome?", "o que você sabe sobre café?", "você se lembra que eu gosto de chá?",
         "quais são suas memórias?", "mostre suas memórias", "neko, o que você anotou?", "o que você guardou sobre a reunião?",
         "você ainda se lembra da Ana?", "você sabe meu nome?",
         "Lembra da minha viagem a Paris?", "lembra quando fomos à praia?"]
REMINDER = ["me lembra de comprar pão", "lembra de comprar pão", "lembre-me de ligar para a Ana", "me lembre de pagar a conta", "pode me lembrar de regar as plantas"]
FORGET_ALL = ["esqueça tudo", "apague todas as memórias", "limpe todas as suas memórias", "neko, esquece tudo", "delete todas as memórias"]
TRAPS = ["não lembro de nada", "esqueci minha senha", "lembrei que hoje é feriado", "quero falar de memória RAM", "a memória do meu pc está cheia",
         "lembrar de beber água é difícil", "o filme Lembranças é bom", "ele disse para lembrar que amanhã chove", "apague a luz", "corrija meu texto",
         "guarda-chuva é útil", "anota não funciona no meu celular", "salva vidas é uma profissão", "grave isso é um problema grave", "troque de roupa",
         "oi, tudo bem?", "esqueceram de mim é um bom filme", "não esqueça de respirar", "esquece, deixa pra lá", "troque ideias com a gente",
         "guarde segredo", "você sabe programar?", "a lembrança é boa", "memória muscular é incrível",
         "esqueci de comer hoje", "eu nunca esqueço um rosto", "acabei de salvar o arquivo", "minha avó sempre lembra de tudo", "ela não esquece nada",
         "esquece, foi mal", "gravei um vídeo ontem", "anotei tudo no caderno", "guardei o carro na garagem", "quem lembra disso?",
         "o que você sabe fazer?"]

class CommandTests(unittest.TestCase):
    def check(self, phrases, kind):
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                command = parse(phrase)
                self.assertIsNotNone(command)
                self.assertEqual(command.kind, kind)

    def test_remember(self):
        self.check(REMEMBER, "remember")

    def test_forget(self):
        self.check(FORGET, "forget")

    def test_correct(self):
        self.check(CORRECT, "correct")

    def test_replace(self):
        self.check(REPLACE, "replace")

    def test_query(self):
        self.check(QUERY, "query")

    def test_reminder(self):
        self.check(REMINDER, "reminder")

    def test_forget_all(self):
        self.check(FORGET_ALL, "forget_all")

    def test_traps_trigger_nothing(self):
        for phrase in TRAPS:
            with self.subTest(phrase=phrase):
                self.assertIsNone(parse(phrase))

    def test_the_list_is_broad_enough(self):
        self.assertGreaterEqual(len(REMEMBER + FORGET + CORRECT + REPLACE + QUERY + REMINDER + FORGET_ALL + TRAPS), 80)
        self.assertGreaterEqual(len(TRAPS), 30)

    def test_payload_keeps_accents_and_case(self):
        self.assertEqual(commands.statement(parse("lembre que meu nome é José").payload), "Meu nome é José")

    def test_replace_splits_both_sides(self):
        command = parse("corrija Recife para Olinda")
        self.assertEqual((command.old, command.new), ("Recife", "Olinda"))

class CategoryTests(unittest.TestCase):
    def test_files(self):
        cases = {"Eu gosto de café": "preferences.md", "Meu nome é Ana": "user_profile.md", "Moro em Recife": "user_profile.md",
                 "Estou trabalhando no projeto Neku": "projects.md", "A chave fica na gaveta": "important_memories.md",
                 "Reunião amanhã às 15h": "temporary.md", "Dentista na sexta": "temporary.md"}
        for text, name in cases.items():
            self.assertEqual(categorize(text)[0], name, text)

    def test_habits_are_not_temporary(self):
        self.assertIsNone(categorize("Trabalho de casa às sextas")[1])

    def test_temporary_has_an_expiry(self):
        self.assertIsNotNone(categorize("Reunião amanhã")[1])

class SecretTests(unittest.TestCase):
    def test_sensitive_data_is_detected(self):
        for text in ("minha senha é 123", "meu CPF é 111.222.333-44", "o cartão de crédito termina em 1", "token do github", "12345678901"):
            self.assertTrue(is_secret(text), text)

    def test_ordinary_text_is_not_flagged(self):
        for text in ("gosto de café", "moro em Recife", "paguei com cartão", "tenho 30 anos"):
            self.assertFalse(is_secret(text), text)

class SkillParserTests(unittest.TestCase):
    def check(self, phrase, skill, **expected):
        request = parse_skill(phrase)
        self.assertIsNotNone(request, phrase)
        self.assertEqual(request.name, skill, phrase)
        for key, value in expected.items():
            self.assertEqual(request.args.get(key), value, phrase)

    def test_actions(self):
        self.check("abre a pasta downloads", "open_folder", folder="downloads")
        self.check("abra meus documentos", "open_folder", folder="documents")
        self.check("abre o chrome", "open_app", target="chrome")
        self.check("neko, pode abrir o bloco de notas?", "open_app", target="bloco de notas")
        self.check("pesquisa no youtube gatos engraçados", "web_search", site="youtube", query="gatos engraçados")
        self.check("pesquisa receita de bolo", "web_search", site="google", query="receita de bolo")
        self.check("procura arquivos .pdf em documentos", "find", ext=".pdf", folder="documents")
        self.check("acha o arquivo relatório", "find", query="relatório")
        self.check("procura minhas fotos", "find", ext="imagem")
        self.check("descompacta relatorio.zip", "extract", target="relatorio.zip")
        self.check("descompacta o último zip", "extract", target="último zip")
        self.check("verifica se o arquivo foto.zip tem vírus", "scan", target="foto.zip")
        self.check("escaneia instalador.exe", "scan", target="instalador.exe")
        self.check("organiza meus downloads", "organize", folder="downloads")
        self.check("desfaz a organização", "undo")
        self.check("cria uma pasta Projetos na área de trabalho", "create_folder", name="Projetos", folder="desktop")
        self.check("cria um arquivo lista com pão e leite", "create_note", name="lista", content="pão e leite")
        self.check("renomeia foto.jpg para praia.jpg", "rename", source="foto.jpg", name="praia.jpg")
        self.check("move relatorio.pdf para documentos", "move", source="relatorio.pdf", folder="documents")
        self.check("copia foto.png para imagens", "copy", source="foto.png", folder="pictures")
        self.check("manda relatorio.pdf para a lixeira", "trash", target="relatorio.pdf")
        self.check("apaga o arquivo velho.txt", "trash", target="velho.txt")
        self.check("apaga velho.txt", "trash", target="velho.txt")
        self.check("aumenta o volume", "volume", action="aumenta")
        self.check("quanta memória eu tenho livre?", "system")
        self.check("bloqueia o pc", "lock")
        self.check("o que você sabe fazer?", "help")

    def test_timers(self):
        self.check("me avisa em 10 minutos para tirar o bolo", "timer", seconds=600, text="tirar o bolo")
        self.check("me lembra de ligar para a Ana em meia hora", "timer", seconds=1800, text="ligar para a Ana")
        self.check("me lembra de sair daqui a 2 horas", "timer", seconds=7200, text="sair")
        self.check("avisa em 30 segundos", "timer", seconds=30, text="")

    def test_conversation_is_not_an_action(self):
        for phrase in ("a memória do meu pc está cheia", "meu pc trava toda hora", "quero abrir um negócio", "apague a luz", "oi, tudo bem?",
                       "foi um dia difícil", "esqueci minha senha", "eu abro a pasta depois", "ele apagou o arquivo ontem", "abriu o chrome sozinho",
                       "como faço para abrir uma empresa?", "quanto custa um pc novo?", "remova isso", "meu computador está lento"):
            self.assertIsNone(parse_skill(phrase), phrase)
