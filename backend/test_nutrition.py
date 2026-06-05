import asyncio
from google import genai
from google.genai import types
from pydantic import BaseModel
from app.core.config import get_settings
from app.schemas import NutritionPlan, MacroTargets

async def main():
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=NutritionPlan,
        max_output_tokens=4096,
        temperature=0.2
    )
    print("Sending request to gemini...")
    try:
        resp = await client.aio.models.generate_content(
            model="gemini-2.5-pro",
            contents="Create a simple 1 day nutrition plan hitting 2000 kcal, 150g protein, 200g carbs, 60g fat.",
            config=config
        )
        print("resp.text:", repr(resp.text))
        print("resp.parsed:", getattr(resp, "parsed", None))
        print("candidates:", getattr(resp, "candidates", []))
    except Exception as e:
        print("Exception:", e)

asyncio.run(main())
