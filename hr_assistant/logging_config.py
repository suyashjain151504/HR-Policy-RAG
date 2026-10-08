"""One place to turn on readable console logging.

Library modules emit progress through logging at INFO, not print().
Errors go through logger.warning / logger.exception.
Entry points call configure_logging() so those lines show on stdout
or the Streamlit server console — not in the chat UI.
print() is only for a script's own output.
"""

import logging
import os

_CONFIGURED = False


def configure_logging(level: "str | int | None" = None) -> None:
    """Attach a plain-message handler to the root logger, once per process.

    Level: the explicit arg, else $LOG_LEVEL, else INFO.
    Safe to call from every entry point and from a Streamlit rerun.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    resolved = level or os.getenv("LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=resolved,
        format="%(message)s",
    )
    # Streamlit often configures the root logger first, so basicConfig
    # can be a no-op. Force this package's logger to the same level.
    logging.getLogger("hr_assistant").setLevel(resolved)
    _CONFIGURED = True
