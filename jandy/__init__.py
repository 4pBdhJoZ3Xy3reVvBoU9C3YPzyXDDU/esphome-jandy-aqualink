"""Minimal Jandy Aqualink RS-485 decoder (Phase 0 host prototype).

This is the curiosity/learning build's read-only foundation. The frame layer
here is intentionally a simple byte-at-a-time state machine so it ports
verbatim to an ESP-IDF C UART task later. Validate every layer against real
captured bus data before building the next.
"""
