import json
import re
import string
import asyncio

from loguru import logger
import httpx
from bs4 import BeautifulSoup

from src.core.exceptions import NotFoundError


class CompanyService:
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(base_url='https://api.infostats.co')

    async def search_companies(self, query: str) -> list[dict]:
        resp = await self.client.get(
            '/company-search/v2/search',
            params={
                'query': query,
                'page': 1,
                'limit': 4,
                'state': 'null',
                'size': 'null',
                'form': 'null',
                'activities': 'null',
                'regions': 'null',
            }
        )
        data = resp.json()
        return data.get('result', [])

    async def _get_company_id(self, bin: str) -> int:
        companies = await self.search_companies(bin)

        for company in companies:
            if company.get('bin') == bin:
                return int(company['id'])

        raise NotFoundError()

    async def _get_contacts_egov(self, bin: str) -> str | None:
        resp = await self.client.get(
            'https://data.egov.kz/datasets/getdata',
            params={
                'index': 'gbd_ul',
                'version': 'v1',
                'page': '1',
                'count': '5',
                'text': bin,
                'column': 'id',
                'order': 'ascending',
            },
            headers={
                'Referer': 'https://data.egov.kz/datasets/view?index=gbd_ul',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0',
                'X-Requested-With': 'XMLHttpRequest',
            }
        )
        data = resp.json()
        if data.get('elements'):
            address = data['elements'][0].get('addressru', '')
            match = re.search(r'тел\. ([^а-яА-Яa-zA-Z,\.]+)', address)
            if match:
                return ''.join(c for c in match.group(1) if c in string.digits)
        return None

    async def _get_contacts_goszakup(self, bin: str) -> dict:
        resp = await self.client.post(
            'https://ows.goszakup.gov.kz/v3/graphql',
            json={
                'query': 'query($bin: String) { Subjects(filter: {bin: $bin}) { bin nameRu email phone website } }',
                'variables': {'bin': bin}
            },
            headers={'Content-Type': 'application/json'}
        )
        data = resp.json()
        subjects = data.get('data', {}).get('Subjects', [])

        if subjects:
            subject = subjects[0]
        else:
            subject = {}

        return {
            'email': subject.get('email'),
            'phone': subject.get('phone'),
            'website': subject.get('website'),
        }

    async def scrape_company(self, bin: str):
        goszakup_contacts_task = asyncio.create_task(self._get_contacts_goszakup(bin))
        egov_phone_task = asyncio.create_task(self._get_contacts_egov(bin))

        company_id = await self._get_company_id(bin)

        courts_task = asyncio.create_task(self.client.get(f'/companies/{company_id}/courts'))
        risks_task = asyncio.create_task(self.client.get(f'/companies/{company_id}/risks'))
        licenses_task = asyncio.create_task(self.client.get(f'/companies/{company_id}/licenses'))

        company_page_task = asyncio.create_task(self.client.get(f'https://infostats.co/companies/kz/{company_id}'))

        courts_resp, risks_resp, licenses_resp, goszakup_contacts, egov_phone, company_page_resp = await asyncio.gather(
            courts_task, risks_task, licenses_task, goszakup_contacts_task, egov_phone_task, company_page_task,
        )

        soup = BeautifulSoup(company_page_resp.text, 'html.parser')
        next_data_script = soup.find('script', {'id': '__NEXT_DATA__', 'type': 'application/json'})

        if next_data_script and next_data_script.string:
            props = json.loads(next_data_script.string)['props']
            company = props.get('pageProps', {}).get('company', {})
        else:
            company = {}
            logger.error(f'Error when scraping https://infostats.co/companies/kz/{company_id}')

        contacts = {
            'email': goszakup_contacts['email'],
            'website': goszakup_contacts['website'],
            'phones': [i for i in [egov_phone, goszakup_contacts['phone']] if i is not None],
        }

        return {
            'bin': bin,
            'courts': courts_resp.json(),
            'risks': risks_resp.json(),
            'licenses': licenses_resp.json(),
            'company': company,
            'contacts': contacts,
        }
