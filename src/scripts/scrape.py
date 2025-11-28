import asyncio
import sys

import tenacity
import httpx
from pymongo.asynchronous.database import AsyncDatabase
from loguru import logger

from src.di import setup_di


PAGE_LIMIT = 100
MAX_CONCURRENT_WORKERS = 20
REQUEST_TIMEOUT = 60

semaphore = asyncio.Semaphore(MAX_CONCURRENT_WORKERS)


@tenacity.retry(
    retry=tenacity.retry_if_exception_type(httpx.HTTPError),
    wait=tenacity.wait_exponential(multiplier=1, min=2, max=30),
    stop=tenacity.stop_after_attempt(5),
    reraise=True,
)
async def scrape_announcement_ids(page: int, client: httpx.AsyncClient) -> list[int]:
    resp = await client.get(f'/_lots/?limit={PAGE_LIMIT}&offset={page*100}&ord=-offer_start_date')
    data = resp.json()
    return [i['announcement_id'] for i in data['results']]


@tenacity.retry(
    retry=tenacity.retry_if_exception_type(httpx.HTTPError),
    wait=tenacity.wait_exponential(multiplier=1, min=2, max=30),
    stop=tenacity.stop_after_attempt(5),
    reraise=True,
)
async def scrape_announcement(id: int, db: AsyncDatabase, client: httpx.AsyncClient):
    async with semaphore:
        announcement = (await client.get(f'/announcements/{id}/')).json()
        lots = (await client.get(f'/announcements/{id}/lots/')).json()
        general_files = (await client.get(f'/announcements/{id}/general-files/')).json()

    await db.tenders.insert_one({
        'announcement': announcement,
        'lots': lots,
        'general_files': general_files,
    })

    logger.info(f'Saved announcement({id})')


async def main(page_count: int = 1):
    container = setup_di()
    db = await container.get(AsyncDatabase)

    async with httpx.AsyncClient(base_url='https://zakup.gov.kz/api/core/api/core', timeout=REQUEST_TIMEOUT) as client:
        for page in range(page_count):
            announcement_ids = await scrape_announcement_ids(page, client)

            existing_ids = await db.tenders.distinct('announcement.id', {'announcement.id': {'$in': announcement_ids}})
            not_existing_announcement_ids = set(announcement_ids).difference(existing_ids)

            logger.info(f'Page {page}: Scraping {len(not_existing_announcement_ids)} announcements')

            await asyncio.gather(*(
                scrape_announcement(id, db, client)
                for id in not_existing_announcement_ids
            ))


if __name__ == '__main__':
    match sys.argv:
        case [_, page_count]:
            asyncio.run(main(int(page_count)))
        case [_]:
            asyncio.run(main())
        case _:
            print("Usage: python -m src.scripts.scrape [page_count]")
            sys.exit(1)
