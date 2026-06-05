import asyncio
from google import genai
from google.genai import types
from pydantic import BaseModel
from app.core.config import get_settings

class TestModel(BaseModel):
    name: str

async def main():
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=TestModel,
    )
    resp = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents="My name is Alice",
        config=config
    )
    print("resp.text:", repr(resp.text))
    print("resp.parsed:", repr(getattr(resp, "parsed", None)))
    print("type of parsed:", type(getattr(resp, "parsed", None)))
    print("resp.function_calls:", resp.function_calls)
    print("dir(resp):", dir(resp))

asyncio.run(main())
