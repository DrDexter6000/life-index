"""
Bootstrap module for search_journals CLI.

Handles stdout/stderr encoding protection on Windows (R10 fix):
- Reconfigures sys.stdout/stderr to UTF-8 with error replacement
- Suppresses transformers/torch progress bar noise, but ONLY when an
  embedding host imported those libraries first

This module must never import transformers/torch/sentence_transformers
itself: they are not project dependencies, and on machines where they
happen to be installed, importing them costs seconds of startup and
hundreds of MB of RSS per CLI invocation. Guards below follow the
"only if already in sys.modules" pattern of _suppress_st_stdout.
"""

from __future__ import annotations

import sys
import tempfile


def _maybe_reconfigure(stream: object) -> None:
    """Reconfigure a text stream to UTF-8 when supported."""
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")


def ensure_utf8_io() -> None:
    """
    Protect CLI stdout/stderr from encoding issues on Windows.

    Call this at the very start of __main__.py, before any other
    imports that might emit subprocess-visible output.

    Three protections:
    1. sys.stdout/stderr.reconfigure(encoding='utf-8', errors='replace')
       — ensures all output uses UTF-8, replacing undecodable bytes
    2. transformers.logging.set_verbosity_error()
       — prevents progress bars and info messages from polluting stderr;
         only applied when an embedding host already imported transformers
    3. Windows non-TTY: torch stderr redirect to temp file
       — prevents GBK-encoded bytes from reaching the subprocess parent;
         only applied when an embedding host already imported torch

    Protections 2/2b/3 never import the guarded library themselves —
    importing transformers/torch here is what this function used to do,
    and it cost ~4s of startup on machines where they are installed.
    """
    # Protection 1: Reconfigure stdout/stderr to UTF-8
    _maybe_reconfigure(sys.stdout)
    _maybe_reconfigure(sys.stderr)

    # Protection 2: Suppress transformers logging noise (only if an
    # embedding host already imported it — never import it here)
    _suppress_transformers_logging()

    # Protection 2b: Suppress legacy model-loading prints to stdout if old
    # integrations have already imported optional ML libraries.
    _suppress_st_stdout()

    # Protection 3: Windows non-TTY torch stderr redirect
    if sys.platform == "win32" and hasattr(sys.stderr, "isatty") and not sys.stderr.isatty():
        _redirect_torch_stderr_windows()


def _suppress_transformers_logging() -> None:
    """Set transformers logging to ERROR to prevent progress bar pollution.

    Only acts when transformers is ALREADY in sys.modules (an embedding
    host imported it earlier). Must never import it: importing here made
    every CLI invocation pay the full transformers startup cost on
    machines where it happens to be installed.
    """
    if "transformers" not in sys.modules:
        return
    try:
        transformers = sys.modules["transformers"]
        transformers_logging = getattr(transformers, "logging", None)
        if transformers_logging is not None:
            transformers_logging.set_verbosity_error()
    except Exception:
        pass  # best-effort suppression; never crash the CLI


def _suppress_st_stdout() -> None:
    """Suppress legacy optional model-loading print statements.

    Active search no longer loads embedding models, but this guard remains for
    older integrations that may import optional ML libraries before CLI JSON is
    emitted.

    Strategy: Patch SentenceTransformer.__init__ if the module is
    already loaded. If not loaded yet, no action needed — the prints
    only happen during __init__, and the subprocess test extracts JSON
    from stdout.
    """
    try:
        enc = sys.stdout.encoding
        if not isinstance(enc, str):
            return
    except AttributeError:
        return

    if "sentence_transformers" not in sys.modules:
        return

    try:
        import io
        import contextlib
        import functools

        st_mod = sys.modules["sentence_transformers"]
        if hasattr(st_mod, "SentenceTransformer"):
            _orig_init = st_mod.SentenceTransformer.__init__

            @functools.wraps(_orig_init)
            def _quiet_init(self: object, *args: object, **kwargs: object) -> None:
                with contextlib.redirect_stdout(io.StringIO()):
                    _orig_init(self, *args, **kwargs)

            st_mod.SentenceTransformer.__init__ = _quiet_init
    except Exception:
        pass


def _redirect_torch_stderr_windows() -> None:
    """
    On Windows non-TTY (subprocess calls), redirect torch's stderr
    to prevent GBK-encoded bytes from corrupting the subprocess output.

    Torch emits progress/info messages during model loading that may
    contain GBK bytes on Windows. When an Agent calls the CLI via
    subprocess with encoding='utf-8', these bytes cause
    UnicodeDecodeError in the reader thread.

    Only acts when torch is ALREADY in sys.modules (an embedding host
    imported it earlier). Must never import it: importing here made
    every CLI invocation pay the full torch startup cost on machines
    where it happens to be installed.
    """
    if "torch" not in sys.modules:
        return
    try:
        torch = sys.modules["torch"]

        # Only redirect if torch has the _C module (real installation)
        if hasattr(torch, "_C"):
            _original_stderr = sys.stderr
            tmp = tempfile.TemporaryFile(mode="w", encoding="utf-8", errors="replace")
            try:
                sys.stderr = tmp
            except Exception:
                # If redirect fails, restore and move on
                sys.stderr = _original_stderr
                tmp.close()
    except Exception:
        # Best-effort protection: on non-Windows runners, tests may mock
        # sys.platform="win32" while installed torch still expects Windows-only
        # ctypes attributes. Redirect failure must never crash the CLI.
        pass
