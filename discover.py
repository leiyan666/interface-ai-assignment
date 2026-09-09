"""CLI entry point for LLM-driven discovery."""

from __future__ import annotations

import argparse

from computer_use.discovery import discover
from computer_use.llm import OpenAIClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover a reusable capability with an LLM")
    parser.add_argument("--goal", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    print(f"Saved capability: {discover(args.goal, args.target, OpenAIClient(), headless=args.headless)}")


if __name__ == "__main__":
    main()
