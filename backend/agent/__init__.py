"""
agent — Forensic document analysis pipeline.

Public API::

    from agent import run_analysis

    for update in run_analysis("path/to/id.jpg", "path/to/selfie.jpg"):
        print(update["step"], update["status"], update["message"])
"""

from agent.forensic_agent import run_analysis  # noqa: F401

from agent.types import (  # noqa: F401 — re-export for consumers
    BiometricResult,
    OcrResult,
    StepUpdate,
    TamperResult,
    Verdict,
)
