import sys

from stampla_desktop.app import main

# Guarded because parallel hashing uses spawn-based worker processes,
# which re-import the main module (see stampla.hashing).
if __name__ == "__main__":
    sys.exit(main())
