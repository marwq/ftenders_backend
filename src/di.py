import asyncio
import concurrent.futures
import typing

from anthropic import AsyncAnthropic
from anthropic.lib.tools._beta_functions import BetaAsyncRunnableTool
from dishka import AsyncContainer, Provider, Scope, make_async_container
from dishka.integrations.fastapi import FastapiProvider

from src.core.ai.tools import setup_tools
from src.core.ai.client import setup_anthropic_client
from src.core.company import CompanyService
from src.db import setup_mongo_client, setup_mongo_db


def db_provider() -> Provider:
    provider = Provider()

    provider.provide(setup_mongo_client, scope=Scope.APP)
    provider.provide(setup_mongo_db, scope=Scope.APP)

    return provider


def services_provider() -> Provider:
    provider = Provider()

    provider.provide(CompanyService, scope=Scope.SESSION)

    return provider


def ai_provider() -> Provider:
    provider = Provider()

    provider.provide(setup_anthropic_client, scope=Scope.SESSION, provides=AsyncAnthropic)
    provider.provide(setup_tools, scope=Scope.SESSION, provides=list[BetaAsyncRunnableTool])

    return provider


def concurrency_provider() -> Provider:
    provider = Provider()

    def get_executor() -> typing.Generator[concurrent.futures.Executor]:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            yield pool

    provider.provide(get_executor, scope=Scope.APP, provides=concurrent.futures.Executor)
    provider.provide(asyncio.get_running_loop, scope=Scope.APP, provides=asyncio.EventLoop)


    return provider


def setup_providers() -> list[Provider]:
    return [
        db_provider(),
        services_provider(),
        ai_provider(),
        concurrency_provider(),
    ]


def setup_di() -> AsyncContainer:
    container = make_async_container(
        *setup_providers(),
    )

    return container


def setup_http_di() -> AsyncContainer:
    container = make_async_container(
        *setup_providers(),
        FastapiProvider(),
    )

    return container