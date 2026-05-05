"""Instagram OSINT Knowledge Graph Agent — public package.

The course pins the package name to ``myproject``. All public-facing modules
(``api``, ``router``, ``retriever``, ``generator``, ``pipeline``) live here.

The heavier internal implementation lives under ``src/agents`` and ``src/schemas``;
this package is the thin facade those modules are wired through. Spec
regeneration (see ``scripts/regenerate.sh``) only ever produces files under
``src/myproject/`` — that is the contract enforced by ``docs/SPEC.md``.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
