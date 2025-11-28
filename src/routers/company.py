from dishka import FromDishka
from pymongo.asynchronous.database import AsyncDatabase

from src.core.company import CompanyService


async def company_get(
    bin: str,
    company_svc: FromDishka[CompanyService],
    db: FromDishka[AsyncDatabase],
):
    data = await db.companys.find_one({'bin': bin})
    if not data:
        data = await company_svc.scrape_company(bin)
        await db.companys.insert_one(data)
    return data


async def company_search(
    query: str,
    company_svc: FromDishka[CompanyService],
):
    companies = await company_svc.search_companies(query)
    return {'result': companies}
