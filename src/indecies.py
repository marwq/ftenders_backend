from pymongo import ASCENDING
from src.di import setup_di
from pymongo.asynchronous.database import AsyncDatabase


async def on_startup():
    container = setup_di()
    async with container() as request_container:
        db = await request_container.get(AsyncDatabase)
        await db.tenders.create_index([('announcement.offer_end_date', ASCENDING)])
        await db.tenders.create_index([('announcement.publish_date', ASCENDING)])
        await db.tenders.create_index([
            ('announcement.name', 'text'),
            ('lots.plan_items.description', 'text'),
            ('lots.plan_items.extra_description', 'text')
        ])
