from typing import AsyncGenerator
from anthropic import AsyncAnthropic

from src.config import settings


async def setup_anthropic_client() -> AsyncGenerator[AsyncAnthropic]:
    async with AsyncAnthropic(api_key=settings.anthropic_api_key) as client:
        yield client
