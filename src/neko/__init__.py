import os

# Precisa vir antes do numpy: sem isso, ele reserva cerca de 360 MB para threads que a rede não usa.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

__version__ = "0.9.0"
