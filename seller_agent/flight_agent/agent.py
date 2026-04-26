from __future__ import annotations

import hashlib
from typing import Any


MOCK_FLIGHTS: list[dict[str, Any]] = [
    {
        "route": "SFO -> NRT",
        "airline": "ANA",
        "flightNumber": "NH 107",
        "stops": 0,
        "duration": "10h 45m",
        "departureLocal": "2026-05-14T12:20:00-07:00",
        "arrivalLocal": "2026-05-15T15:05:00+09:00",
        "fareUSD": 1048,
        "cabin": "Economy Flex",
    },
    {
        "route": "SFO -> HND",
        "airline": "Japan Airlines",
        "flightNumber": "JL 1",
        "stops": 0,
        "duration": "11h 05m",
        "departureLocal": "2026-05-15T11:30:00-07:00",
        "arrivalLocal": "2026-05-16T14:35:00+09:00",
        "fareUSD": 1115,
        "cabin": "Economy Saver",
    },
    {
        "route": "SFO -> NRT",
        "airline": "United + ANA",
        "flightNumber": "UA 837 / NH 12",
        "stops": 1,
        "duration": "13h 20m",
        "departureLocal": "2026-05-14T08:05:00-07:00",
        "arrivalLocal": "2026-05-15T16:25:00+09:00",
        "fareUSD": 912,
        "cabin": "Economy Basic",
    },
    {
        "route": "LAX -> NRT",
        "airline": "Singapore Airlines",
        "flightNumber": "SQ 11",
        "stops": 1,
        "duration": "14h 10m",
        "departureLocal": "2026-05-16T10:00:00-07:00",
        "arrivalLocal": "2026-05-17T17:10:00+09:00",
        "fareUSD": 978,
        "cabin": "Economy Standard",
    },
]


class FlightBookingAgent:
    def _pick_flights(self, prompt: str) -> list[dict[str, Any]]:
        prompt_lower = prompt.lower()
        if "nonstop" in prompt_lower or "direct" in prompt_lower:
            candidates = [f for f in MOCK_FLIGHTS if f["stops"] == 0]
        elif "cheap" in prompt_lower or "budget" in prompt_lower or "under" in prompt_lower:
            candidates = sorted(MOCK_FLIGHTS, key=lambda f: f["fareUSD"])
        else:
            candidates = MOCK_FLIGHTS[:]

        if "lax" in prompt_lower:
            lax = [f for f in candidates if f["route"].startswith("LAX")]
            if lax:
                candidates = lax + [f for f in candidates if f not in lax]

        seed = hashlib.md5(prompt.encode("utf-8")).hexdigest()
        offset = int(seed[:2], 16) % len(candidates)
        rotated = candidates[offset:] + candidates[:offset]
        return rotated[:2]

    def run(self, prompt: str) -> str:
        picks = self._pick_flights(prompt)
        lines = [
            f"Simulated flight recommendations for: {prompt}",
            "",
        ]
        for idx, option in enumerate(picks, start=1):
            lines.append(
                (
                    f"{idx}. {option['airline']} ({option['flightNumber']}) | {option['route']} | "
                    f"{option['stops']} stop(s) | {option['duration']} | "
                    f"Fare ~ ${option['fareUSD']} ({option['cabin']})"
                )
            )
        lines.append("")
        lines.append("Note: This is mock QA data (no live airline API used).")
        return "\n".join(lines)
