#!/usr/bin/env python3
"""Entry point for OmniGraph console application."""
from omnigraph.console_app import OmniGraphConsole

if __name__ == "__main__":
    import logging
    import sys
    console = OmniGraphConsole()
    try:
        console.run()
    except KeyboardInterrupt:
        print("\n\n  Interrupted. Goodbye!\n")
    except Exception as exc:
        print(f"\n  Fatal error: {exc}")
        logging.getLogger("omnigraph.console").exception("Fatal error in console application")
        sys.exit(1)
