import asyncio

from anthropic import AsyncAnthropic
from anthropic.lib.tools._beta_functions import BetaAsyncRunnableTool

from src.di import setup_di


container = setup_di()

async def main():
    async with container() as request_container:
        tools = await request_container.get(list[BetaAsyncRunnableTool])
        client = await request_container.get(AsyncAnthropic)

        runner = client.beta.messages.tool_runner(
            model='claude-sonnet-4-5',
            max_tokens=2048,
            tools=tools,
            betas=['web-fetch-2025-09-10'],
            messages=[
                {"role": "user", "content": "загугли компанию qazaqvibe (только через websearch)"},
            ],
        )

        async for message in runner:
            print(message)

asyncio.run(main())
