"""Fingerprint capture bridge — spawns FingerprintBridge.exe and streams events."""
from .bridge_client import ScannerBridge, PIPE_NAME

__all__ = ["ScannerBridge", "PIPE_NAME"]
