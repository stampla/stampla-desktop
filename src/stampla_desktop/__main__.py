import multiprocessing
import sys

from stampla_desktop.app import main

# Guarded because parallel hashing uses spawn-based worker processes,
# which re-import the main module (see stampla.hashing). In a frozen
# bundle sys.executable is the app itself, so without freeze_support()
# every hash worker would launch the whole GUI again.
if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
