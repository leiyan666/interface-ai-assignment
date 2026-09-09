"""Synthetic records used only by the local demo application."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Member:
    number: str
    name: str
    checking: float | None
    savings: float | None


MEMBERS = {
    "10001": Member("10001", "Alice Chen", 2340.10, 4250.32),
    "10002": Member("10002", "Bob Smith", 1520.00, 8921.10),
    "10003": Member("10003", "Maria Lee", 780.45, None),
}
