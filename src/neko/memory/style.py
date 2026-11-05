"""Aprende o seu jeito de falar só com o que você escreve para o Neku, em um arquivo que você pode editar."""
import random, re
from pathlib import Path
from .commands import is_secret
from .store import read_text, write_text
from .text import fold

FILE_NAME = "linguajar.md"
HEADER = ("# Meu linguajar\n\nPalavras que o Neku aprendeu com o que você escreve para ele. "
          "Pode editar ou apagar qualquer linha.\n\n")
LINE = re.compile(r"^- (abertura: )?(.+) \((\d+)\)\s*$")
MAX_WORDS = 150
MIN_UNKNOWN_USES = 3

SLANG = frozenset(
    "vc vcs tb tbm blz mano cara mina vlw tmj pq oq kkk rs haha tipo bora massa dahora suave show top demais fechou "
    "firmeza oxe uai bah tche eita opa salve slk pprt mds nossa vei veio bicho trem mermao ow fala seguinte beleza "
    "valeu parceiro brother irmao meu_deus sinistro brabo dale daora tranquilo".split())
COMMON = frozenset(
    "a o as os um uma uns umas de do da dos das em no na nos nas e ou que com para pra por se eu tu ele ela nos eles "
    "elas meu minha meus minhas seu sua seus suas voce nao sim mas mais muito muita muitos muitas como ao aos sobre "
    "isso esse essa este esta aquilo aquele aquela la aqui ali ja foi ser ter tem sou era me te lhe quando onde qual "
    "quais quem porque porem entao assim tambem ainda depois antes agora hoje amanha ontem sempre nunca tudo nada "
    "todo toda todos todas algo alguem cada outro outra outros outras mesmo mesma bem mal bom boa melhor pior grande "
    "pequeno novo nova velho primeiro ultimo fazer faz faco fez feito fazendo dizer diz disse falar fala falo ver vejo "
    "vi visto ir vou vai vamos foram estar estou esta estao estava sei sabe saber querer quero quer pode posso poder "
    "deve devo dever precisa preciso precisar dar dou deu dado ficar fica fico usar uso usa colocar coloca abrir abre "
    "abra olha olhar coisa coisas vez vezes dia dias ano anos hora horas tempo pessoa pessoas gente casa trabalho "
    "arquivo arquivos pasta computador notebook mouse tela texto conversa jeito lembre lembra esquece corrija neko "
    "ate apos sem sob contra entre durante pelo pela pelos pelas num numa nele nela disso nisso dessa desse deste "
    "desta quanto quanta menos tanto tanta poucos pouco pouca aquilo cuja cujo teu tua lembrar esquecer quase talvez".split())
MIRROR = {"blz": "Blz!", "beleza": "Beleza!", "mano": "Fechou, mano!", "tmj": "Tmj!", "suave": "Suave!", "show": "Show!",
          "top": "Top!", "massa": "Massa!", "dahora": "Da hora!", "daora": "Daora!", "uai": "Uai!", "bah": "Bah!",
          "oxe": "Oxe!", "fechou": "Fechou!", "firmeza": "Firmeza!", "cara": "Opa, cara!", "bora": "Bora!", "vlw": "Vlw!"}
GREETINGS = {"salve": "Salve!", "fala": "Fala!", "opa": "Opa!", "eai": "E aí!", "eae": "E aí!", "oi": "Oi!", "ola": "Olá!"}

class Style:
    def __init__(self, memory_dir: Path, config):
        self.path = memory_dir / FILE_NAME
        self.config = config

    def counts(self):
        if not self.path.exists():
            return {}
        found = {}
        for line in read_text(self.path)[0].splitlines():
            match = LINE.match(line)
            if match:
                found[(match[1] or "") + match[2]] = int(match[3])
        return found

    def _save(self, counts):
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:MAX_WORDS]
        body = "".join(f"- {word} ({count})\n" for word, count in ranked)
        write_text(self.path, HEADER + body, "utf-8")

    def observe(self, text):
        if not self.config.get("learn_language", True) or is_secret(text):
            return
        counts = self.counts()
        changed = False
        for index, match in enumerate(re.finditer(r"[^\W\d_]+", text)):
            word = match[0]
            if index and word[0].isupper():
                continue
            key = re.sub(r"k{3,}", "kkk", re.sub(r"(ha){2,}", "haha", fold(word)))
            if key in SLANG or (key not in COMMON and 3 <= len(key) <= 14):
                counts[key] = counts.get(key, 0) + 1
                changed = True
        first = re.match(r"\s*([^\W\d_]+)\s*,", text)
        if first and len(text.split()) > 2:
            key = "abertura: " + fold(first[1])
            counts[key] = counts.get(key, 0) + 1
            changed = True
        if changed:
            self._save(counts)

    def favorites(self, limit=8):
        counts = self.counts()
        words = [word for word, count in counts.items()
                 if not word.startswith("abertura: ") and count >= (1 if word in SLANG else MIN_UNKNOWN_USES)]
        return sorted(words, key=lambda word: -counts[word])[:limit]

    def greeting(self, default):
        counts = self.counts()
        known = [word for word in GREETINGS if counts.get(word, 0) + counts.get("abertura: " + word, 0) >= 2]
        if not known:
            return default
        best = max(known, key=lambda word: counts.get(word, 0) + counts.get("abertura: " + word, 0))
        return GREETINGS[best] + " " + default.split("! ", 1)[-1]

    def flavor(self, text, rng=random):
        """De vez em quando começa a resposta com uma expressão que é sua."""
        mirrored = [MIRROR[word] for word in self.favorites() if word in MIRROR]
        if mirrored and rng.random() < 0.5:
            return f"{mirrored[0]} {text}"
        return text

    def guide(self):
        words = self.favorites()
        if not words:
            return ""
        return "Expressões que o usuário costuma usar: " + ", ".join(words)
