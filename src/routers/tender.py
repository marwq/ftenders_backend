from time import time

from bson import ObjectId
from dishka import FromDishka
from fastapi import Query
from pymongo import DESCENDING
from pymongo.asynchronous.database import AsyncDatabase

from src.core.exceptions import NotFoundError


def _is_active(tender: dict) -> bool | None:
    current_timestamp = int(time())

    announcement = tender['announcement']
    offer_end_date = announcement.get("repeated_offer_end_date") or announcement.get("offer_end_date")

    if offer_end_date is not None:
        return offer_end_date > current_timestamp

    return None


async def tender_list(
    db: FromDishka[AsyncDatabase],
    offset: int,
    limit: int = Query(le=100),
    query: str | None = None,
    is_active: bool | None = None,
    price_from: float | None = None,
    price_to: float | None = None,
):
    projection = {
        'lots': 0,
        'general_files': 0,
    }

    filter_conditions = []

    if query:
        filter_conditions.append({'$text': {'$search': query}})

    if price_from is not None:
        filter_conditions.append({'announcement.total_price': {'$gte': price_from}})
    if price_to is not None:
        filter_conditions.append({'announcement.total_price': {'$lte': price_to}})

    if is_active is not None:
        current_timestamp = int(time())
        if is_active:
            filter_conditions.append({
                '$or': [
                    {'announcement.repeated_offer_end_date': {'$gt': current_timestamp}},
                    {
                        'announcement.repeated_offer_end_date': {'$in': [None]},
                        'announcement.offer_end_date': {'$gt': current_timestamp}
                    }
                ]
            })
        else:
            filter_conditions.append({
                '$or': [
                    {'announcement.repeated_offer_end_date': {'$lte': current_timestamp}},
                    {
                        'announcement.repeated_offer_end_date': {'$in': [None]},
                        'announcement.offer_end_date': {'$lte': current_timestamp}
                    }
                ]
            })

    filter_query = {'$and': filter_conditions} if filter_conditions else {}

    total = await db.tenders.count_documents(filter_query)
    cursor = db.tenders.find(filter_query, projection).skip(offset).limit(limit).sort('announcement.publish_date', DESCENDING)
    tenders = await cursor.to_list(length=limit)

    for tender in tenders:
        tender['is_active'] = _is_active(tender)

    return {
        'total': total,
        'result': tenders,
    }


async def tender_get(
    db: FromDishka[AsyncDatabase],
    id: str,
):
    tender = await db.tenders.find_one({'_id': ObjectId(id)})
    if not tender:
        raise NotFoundError()

    tender['is_active'] = _is_active(tender)
    return tender
