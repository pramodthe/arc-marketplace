from __future__ import annotations

import hashlib
from typing import Any


MOCK_HOTELS: list[dict[str, Any]] = [
    {
        "name": "Shibuya Green Stay",
        "district": "Shibuya",
        "nightlyUSD": 148,
        "rating": 4.4,
        "walkToTransitMin": 5,
        "cancellation": "Free cancellation until 48h",
        "fit": "Great for first-time visitors and nightlife access",
    },
    {
        "name": "Tokyo Station Business Inn",
        "district": "Marunouchi",
        "nightlyUSD": 165,
        "rating": 4.5,
        "walkToTransitMin": 3,
        "cancellation": "Free cancellation until 72h",
        "fit": "Best for business travelers and bullet-train access",
    },
    {
        "name": "Asakusa Culture Hotel",
        "district": "Asakusa",
        "nightlyUSD": 122,
        "rating": 4.2,
        "walkToTransitMin": 6,
        "cancellation": "Partial refund until 24h",
        "fit": "Budget-friendly with traditional neighborhood vibe",
    },
    {
        "name": "Shinjuku Central Tower Rooms",
        "district": "Shinjuku",
        "nightlyUSD": 181,
        "rating": 4.6,
        "walkToTransitMin": 4,
        "cancellation": "Free cancellation until 24h",
        "fit": "Strong for late arrivals and major transit connectivity",
    },
]


class HotelFinderAgent:
    def _pick_hotels(self, prompt: str) -> list[dict[str, Any]]:
        prompt_lower = prompt.lower()
        if "budget" in prompt_lower or "under" in prompt_lower or "cheap" in prompt_lower:
            candidates = sorted(MOCK_HOTELS, key=lambda h: h["nightlyUSD"])
        elif "business" in prompt_lower:
            candidates = sorted(MOCK_HOTELS, key=lambda h: (-h["rating"], h["walkToTransitMin"]))
        else:
            candidates = MOCK_HOTELS[:]

        if "shinjuku" in prompt_lower:
            preferred = [h for h in candidates if h["district"].lower() == "shinjuku"]
            candidates = preferred + [h for h in candidates if h not in preferred]
        elif "shibuya" in prompt_lower:
            preferred = [h for h in candidates if h["district"].lower() == "shibuya"]
            candidates = preferred + [h for h in candidates if h not in preferred]

        seed = hashlib.md5(prompt.encode("utf-8")).hexdigest()
        offset = int(seed[-2:], 16) % len(candidates)
        rotated = candidates[offset:] + candidates[:offset]
        return rotated[:3]

    def run(self, prompt: str) -> str:
        picks = self._pick_hotels(prompt)
        lines = [
            f"Simulated hotel recommendations for: {prompt}",
            "",
        ]
        for idx, hotel in enumerate(picks, start=1):
            lines.append(
                (
                    f"{idx}. {hotel['name']} ({hotel['district']}) | ${hotel['nightlyUSD']}/night | "
                    f"Rating {hotel['rating']} | {hotel['walkToTransitMin']} min to transit | "
                    f"{hotel['cancellation']} | {hotel['fit']}"
                )
            )
        lines.append("")
        lines.append("Note: This is mock QA data (no live hotel API used).")
        return "\n".join(lines)
