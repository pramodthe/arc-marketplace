from __future__ import annotations

import os
from google import genai
from dotenv import load_dotenv

class ItineraryWriterAgent:
    def __init__(self) -> None:
        load_dotenv()
        # Force AI Studio instead of Vertex AI and remove ADC to prevent hanging
        os.environ.pop("GOOGLE_GENAI_USE_VERTEXAI", None)
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
        self.client = genai.Client(
            api_key=os.getenv("GOOGLE_API_KEY", "")
        )
        self.model = os.getenv("GOOGLE_ADK_MODEL", "gemini-2.5-flash")

    def run(self, prompt: str) -> str:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    "You are a travel itinerary specialist. Produce a structured "
                    "day-by-day plan with pacing and practical logistics.",
                    prompt
                ]
            )
            return response.text or "No itinerary generated."
        except Exception as e:
            return f"Itinerary generation failed: {e}"
