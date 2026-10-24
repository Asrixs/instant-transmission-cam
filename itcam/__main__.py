import sys
import traceback

from .app import main


def run() -> None:
    frozen = getattr(sys, "frozen", False)
    try:
        code = main()
    except KeyboardInterrupt:
        code = 0
    except RuntimeError as error:
        print(f"\n[Fout] {error}")
        code = 1
    except Exception:
        if not frozen:
            raise
        traceback.print_exc()
        code = 1
    if frozen and code != 0 and sys.stdin is not None and sys.stdin.isatty():
        # Anders sluit het venster van de .exe voordat je de melding kunt lezen.
        input("\nDruk op Enter om af te sluiten...")
    sys.exit(code)


if __name__ == "__main__":
    run()
