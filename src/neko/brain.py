"""Acrescenta à rede do motor o que o agente precisa, sem alterar o arquivo da rede."""
from pestinha.core import nervous_system as ns
from pestinha.ui import rotulos

def extend():
    """Precisa rodar antes de criar a rede. Rodar de novo não duplica nada."""
    if "AJUDAR" in ns.DECISION_MOTORS:
        return
    ns.SENSORY_SPEC.update({
        "TELA": (6, 60.0, 0.0002, 600.0),      # a tela mudou (habitua: rotina perde a graça)
        "ERRO": (6, 80.0, 0.0001, 600.0),      # apareceu um erro na tela
    })
    ns.MOTOR_SPEC.append(("AJUDAR", 10, 60.0, 0.030, 4.0))
    ns.CONNECTIONS.extend([
        ("TELA", "CURIOUS", 0.06, 0.6),
        ("TELA", "ALERT", 0.03, 0.6),
        ("ERRO", "ALERT", 0.10, 0.6),
        ("ERRO", "FOCUS", 0.08, 0.6),
        ("ERRO", "AJUDAR", 0.45, 0.6),
        ("CURIOUS", "AJUDAR", 0.30, 0.6),
        ("FOCUS", "AJUDAR", 0.15, 0.6),
        ("CALM", "AJUDAR", 0.05, 0.6),
        ("QUIET", "AJUDAR", -0.40, 0.6),
        ("TIRED", "AJUDAR", -0.30, 0.6),
        ("FRUSTRATION", "AJUDAR", -0.30, 0.6),
        ("GLOOM", "AJUDAR", -0.25, 0.6),
    ])
    ns.DECISION_MOTORS.add("AJUDAR")
    rotulos.CANAIS_SENSORIAIS.update({"TELA": "tela", "ERRO": "erro na tela"})
    getattr(rotulos, "MOTORES", {}).update({"AJUDAR": "ajudar"})
