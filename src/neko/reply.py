from dataclasses import dataclass
from typing import Callable, Optional

@dataclass
class Confirmation:
    question: str
    on_yes: Callable[[], "Reply"]
    on_no: Optional[Callable[[], "Reply"]] = None
    yes_label: str = "Sim"
    no_label: str = "Não"

@dataclass
class Reply:
    text: str
    mood: str = "happy"
    effect: Optional[str] = None
    confirm: Optional[Confirmation] = None
    difficulty: int = 0
    xp: int = 0
