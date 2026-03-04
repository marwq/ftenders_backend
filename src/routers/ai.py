import asyncio
from typing import TypedDict

from anthropic import AsyncAnthropic
from anthropic.lib.tools._beta_functions import BetaAsyncRunnableTool
from anthropic.types.beta import BetaMessageParam
from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger
from pymongo.asynchronous.database import AsyncDatabase

from src.core.ai.templates import prompts, tool_responses
from src.routers.tender import tender_get


class MessageIn(TypedDict):
    text: str
    mentioned_tenders: list[str] | None
    mentioned_satu_products: list[int] | None
    mentioned_file_urls: list[str] | None


async def to_content(msg: MessageIn, db: AsyncDatabase, is_first_message: bool) -> str:
    tenders = await asyncio.gather(*[
        tender_get(db, tender_id)
        for tender_id in (msg['mentioned_tenders'] or [])
    ])

    mentioned_tenders_contents = None
    if is_first_message:
        mentioned_tenders_contents = [
            tool_responses['fetch_tender'].render(tender)
            for tender in tenders
        ]

    return prompts['message'].render({
        **msg,
        'mentioned_tenders_contents': mentioned_tenders_contents,
    })


@inject
async def ai_websocket(
    ws: WebSocket,
    client: FromDishka[AsyncAnthropic],
    tools: FromDishka[list[BetaAsyncRunnableTool]],
    db: FromDishka[AsyncDatabase],
):
    await ws.accept()

    try:
        is_first_message = True
        messages: list[BetaMessageParam] = []

        while True:
            logger.debug('WS: Waiting for message')
            msg: MessageIn = await ws.receive_json()
            logger.debug(f'WS: Accepted message: {msg=!r}')

            messages.append({
                'role': 'user',
                'content': [{
                    'text': await to_content(msg, db, is_first_message),
                    'type': 'text',
                    'cache_control': {
                        'type': 'ephemeral',
                    },
                }],
            })

            logger.debug('WS: Sending request to Anthropic')
            runner = client.beta.messages.tool_runner(
                model='claude-sonnet-4-5',
                max_tokens=8192,
                tools=tools,
                betas=['web-fetch-2025-09-10'],
                system=prompts['system'].render(),
                messages=messages,
            )

            async for message in runner:
                logger.debug(f'WS: Received message from Anthropic: stop_reason={message.stop_reason}, blocks={len(message.content)}')
                for block in message.model_dump()['content']:
                    logger.debug(f'WS: Sending block to client: type={block["type"]}')
                    await ws.send_json(block)

            messages = list(runner._params["messages"])
            logger.debug('WS: Sending end signal to client')
            await ws.send_json({'type': 'end'})

            is_first_message = False

    except WebSocketDisconnect:
        pass
