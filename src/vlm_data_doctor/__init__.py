"""Offline preflight checks for image-text fine-tuning datasets."""

__version__ = "0.3.1"

from .audit import audit

__all__ = ["audit", "__version__"]
