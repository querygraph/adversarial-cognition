#!/usr/bin/env python3
"""Render the Adversarial Cognition book cover from a composed SVG.

Reproducible, no external art asset. Run with:
  DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
    uv run --with cairosvg -- python3 scripts/build_book_cover.py
"""

from __future__ import annotations

from pathlib import Path

import cairosvg

OUT = Path(__file__).resolve().parents[1] / "docs" / "book" / "cover" / "adversarial-cognition-cover.png"
W, H = 1275, 1650


def svg() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#0e1424"/>
      <stop offset="0.5" stop-color="#0a0d15"/>
      <stop offset="1" stop-color="#070a11"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.5" cy="0.32" r="0.5">
      <stop offset="0" stop-color="#e0ab54" stop-opacity="0.16"/>
      <stop offset="1" stop-color="#e0ab54" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="cu" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#f4c877"/>
      <stop offset="0.5" stop-color="#e0ab54"/>
      <stop offset="1" stop-color="#b07d2e"/>
    </linearGradient>
    <radialGradient id="cr" cx="0.5" cy="0.4" r="0.6">
      <stop offset="0" stop-color="#20283c"/>
      <stop offset="1" stop-color="#0e1220"/>
    </radialGradient>
  </defs>

  <rect width="{W}" height="{H}" fill="url(#bg)"/>
  <rect width="{W}" height="{H}" fill="url(#glow)"/>
  <rect x="40" y="40" width="{W-80}" height="{H-80}" fill="none" stroke="#26304a" stroke-width="1.5" opacity="0.7"/>

  <!-- eyebrow -->
  <text x="{W/2}" y="250" text-anchor="middle" fill="#e0ab54" font-family="Menlo, monospace"
        font-size="24" letter-spacing="10">ADVERSARIAL BENCHMARKS · QUERYGRAPH</text>

  <!-- seal -->
  <g transform="translate({W/2} 470) scale(2.7)">
    <path d="M0 -46 L41 -23 L41 23 L0 46 L-41 23 L-41 -23 Z" fill="url(#cr)" stroke="url(#cu)" stroke-width="2.4"/>
    <circle cx="0" cy="0" r="34" fill="none" stroke="url(#cu)" stroke-width="1.1" opacity="0.7"/>
    <circle cx="0" cy="0" r="30" fill="none" stroke="url(#cu)" stroke-width="1.1" opacity="0.35"/>
    <g stroke="#e0ab54" stroke-width="1.3">
      <line x1="0" y1="-33" x2="0" y2="-28"/><line x1="0" y1="28" x2="0" y2="33"/>
      <line x1="-33" y1="0" x2="-28" y2="0"/><line x1="28" y1="0" x2="33" y2="0"/>
    </g>
    <g fill="url(#cu)">
      <path d="M-12 8 Q-20 -10 -4 -17 Q-12 -6 -6 -2 Q-13 0 -9 6 Z"/>
      <path d="M0 -20 L12 12 L5 12 L2.5 5 L-2.5 5 L-5 12 L-9 12 Z M-1 -1 L4 -1 L1.5 -8 Z"/>
      <circle cx="0" cy="-23" r="4.4" fill="none" stroke="url(#cu)" stroke-width="1.4"/>
    </g>
  </g>

  <!-- title -->
  <text x="{W/2}" y="820" text-anchor="middle" fill="#f4f6fb" font-family="Georgia, serif"
        font-size="118" font-weight="bold" letter-spacing="-1">Adversarial</text>
  <text x="{W/2}" y="938" text-anchor="middle" fill="url(#cu)" font-family="Georgia, serif"
        font-size="118" font-weight="bold" letter-spacing="-1">Cognition</text>

  <line x1="{W/2-190}" y1="1010" x2="{W/2+190}" y2="1010" stroke="#b07d2e" stroke-width="2"/>

  <!-- subtitle -->
  <text x="{W/2}" y="1082" text-anchor="middle" fill="#c7cfe0" font-family="Georgia, serif" font-size="37">Governed Memory and Unforgeable Lineage</text>
  <text x="{W/2}" y="1130" text-anchor="middle" fill="#c7cfe0" font-family="Georgia, serif" font-size="37">in the QueryGraph Stack</text>

  <!-- author -->
  <text x="{W/2}" y="1470" text-anchor="middle" fill="#eef1f8" font-family="Georgia, serif" font-size="44">Alexy Khrabrov</text>
  <text x="{W/2}" y="1540" text-anchor="middle" fill="#98a3bd" font-family="Menlo, monospace"
        font-size="22" letter-spacing="6">FIRST PAIR PRESS</text>
</svg>"""


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cairosvg.svg2png(bytestring=svg().encode("utf-8"), write_to=str(OUT),
                     output_width=W, output_height=H)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
