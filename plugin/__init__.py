"""Directory-plugin shim for hermes-a2a.

The real, testable plugin implementation lives in ``hermes_a2a_plugin``.
Importing this shim must not start services, create state, or import the
runtime ``hermes_a2a`` package.
"""
from __future__ import annotations

from hermes_a2a_plugin import register

__all__ = ["register"]
