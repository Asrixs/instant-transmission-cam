import sys

from .app import main

try:
    sys.exit(main())
except KeyboardInterrupt:
    sys.exit(0)
except RuntimeError as error:
    print(f"\n[Fout] {error}")
    sys.exit(1)
