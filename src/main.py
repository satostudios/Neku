import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from neko import diagnostics

def main():
    if "--diagnostics" in sys.argv:
        print(diagnostics.report(ROOT))
        return 0
    diagnostics.setup(ROOT)
    try:
        from neko.app import run
        return run(ROOT)
    except Exception:
        diagnostics.handle_exception(*sys.exc_info())
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
