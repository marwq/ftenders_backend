import asyncio

from pymongo.asynchronous.database import AsyncDatabase

from src.di import setup_di


async def main():
    container = setup_di()
    db = await container.get(AsyncDatabase)

    pipeline = [
        {"$unwind": "$general_files"},
        {"$match": {"general_files.group.template_file": {"$ne": None}}},
        {"$group": {
            "_id": "$general_files.group.template_file",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}}
    ]

    cursor = await db.tenders.aggregate(pipeline)
    results = []
    async for doc in cursor:
        results.append(doc)

    for result in results:
        template = result['_id']
        count = result['count']
        print(f"Count: {count}")
        print(f"ID: {template.get('id')}")
        print(f"Name: {template.get('name')}")
        print(f"URL: {template.get('file_url')}")
        print()

    print('Total unique templates:', len(results))


if __name__ == '__main__':
    asyncio.run(main())
