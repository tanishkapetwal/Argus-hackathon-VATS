import asyncio
import json
from google import genai
from google.genai import types
from pydantic import BaseModel
from app.core.config import get_settings
from app.schemas import NutritionPlan

async def main():
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    
    schema_str = json.dumps(NutritionPlan.model_json_schema())
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        system_instruction=f"You MUST return ONLY valid JSON matching this schema:\n{schema_str}",
        max_output_tokens=4096,
        temperature=0.2
    )
    print("Sending request to gemini without response_schema...")
    try:
        resp = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents="Create a simple 1 day nutrition plan hitting 2000 kcal, 150g protein, 200g carbs, 60g fat.",
            config=config
        )
        print("resp.text:", repr(resp.text)[:200])
        parsed = NutritionPlan.model_validate_json(resp.text)
        print("Parsed successfully!")
    except Exception as e:
        print("Exception:", e)

asyncio.run(main())
