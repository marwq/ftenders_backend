import base64
from asyncio import EventLoop
from concurrent.futures import Executor
from io import BytesIO
from typing import Literal, TypedDict

from anthropic import beta_async_tool
from anthropic.lib.tools import BetaAsyncBuiltinFunctionTool
from anthropic.lib.tools._beta_functions import BetaAsyncRunnableTool
from anthropic.types.beta import BetaImageBlockParam, BetaRequestDocumentBlockParam, BetaToolUnionParam
import httpx
from loguru import logger
import mammoth
from pymongo.asynchronous.database import AsyncDatabase

from src.core.ai.templates import tool_responses
from src.core.company import CompanyService
from src.routers.company import company_get, company_search
from src.routers.product import product_satu_search, product_satu_details
from src.routers.tender import tender_get


class SupplierAnalysis(TypedDict):
    label: str
    price: float
    delivery_price: float | None


class TenderAnalysis(TypedDict):
    tender_id: str
    price: float
    tax_percent: float | None
    suppliers: list[SupplierAnalysis]


class AnthropicTool(BetaAsyncBuiltinFunctionTool):
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def to_dict(self) -> BetaToolUnionParam:
        return self.kwargs # type: ignore

    async def call(self, _: object):
        raise NotImplementedError('Must be executed on Anthropic API side')


def setup_tools(
    db: AsyncDatabase,
    company_svc: CompanyService,
    event_loop: EventLoop,
    executor: Executor,
) -> list[BetaAsyncRunnableTool]:


    @beta_async_tool(name='check_company', description='''
Retrieves comprehensive risk analysis for company or IE(individual enterpreuner) by it's BIN or IIN.
This tool provides:
- Company details: name, registration date, legal address, director, business activity
- Classification codes
- Contact information: email, website, phone numbers
- Risk indicators: court cases, violations, debts, bankruptcy records, inactive status, address issues
- Court case details: case numbers, dates, plaintiffs, defendants, judges, claims, results
- Licenses information
- Government procurement (Goszakup) data
- Related entities: branches and similar companies by address or director

Note: Some data fields may be missing or incomplete as this information is aggregated from publicly \
available sources.

If you don't have company's BIN/IIN, then use search_company to find by name.

USE THIS TOOL ONLY IF USER ASKED TO VERIFY COMPANY OR ASSESS *RISKS*.
    '''.strip())
    async def check_company(iin_or_bin: str) -> str:
        logger.debug(f'[check_company] {iin_or_bin=!r}')
        data = await company_get(iin_or_bin, company_svc, db)
        return tool_responses['check_company'].render(data)


    @beta_async_tool(name='search_companies', description='''
Searches for Kazakhstan company by name or partial name. Returns:
- BIN/IIN (12-digit identification number)
- Company's full title
- Registration information

USE THIS TOOL ONLY IF YOU NEED TO GET COMPANY'S BIN/IIN by its name(title).
    '''.strip())
    async def search_companies(query: str) -> str:
        logger.debug(f'[search_companies] {query=!r}')
        data = await company_search(query, company_svc)
        return tool_responses['search_companies'].render(data)


    @beta_async_tool(name='search_satu_products', description='''
Searches for products on satu.kz marketplace by query string. Returns product listings with details \
including prices, companies, ratings, and availability. Optional filter: set price cap using \
`price_lower_than` (searches for items priced lower or equal). If you need more results - fetch next page.

Use this tool when you need to find products/services on satu.kz.
    '''.strip())
    async def search_satu_products(query: str, page: int = 0, price_lower_than: int | None = None) -> str:
        logger.debug(f'[search_satu_products] {query=!r} {page=!r} {price_lower_than=!r}')
        data = await product_satu_search(query, db, page, price_lower_than)
        return tool_responses['search_satu_products'].render(data)


    @beta_async_tool(name='fetch_satu_product_details', description='''
Returns:
- Company contact information (phone numbers, website, last activity, operating status)
- Delivery regions (with sub-regions)
- Payment options (cash, non-cash, etc.)
- Delivery methods with comments and available payment options

But this tool DOESN'T PROVIDE ADDITIONAL PRODUCT DESCRIPTION OR SIMILIAR PRODUCTS.
    '''.strip())
    async def fetch_satu_product_details(product_id: int) -> str:
        logger.debug(f'[fetch_satu_product_details] {product_id=!r}')
        data = await product_satu_details(product_id, db)
        return tool_responses['fetch_satu_product_details'].render(data)


    @beta_async_tool(name='add_keyboard', description='''
Adds up to 3 quick-reply buttons under your final message so the user can tap a ready-made follow-up.

Always add a keyboard in your last reply with scenario-appropriate options (max 3). Examples: \
offer to show more products, adjust price cap, or switch category if no good margin was found.
    '''.strip())
    async def add_keyboard(buttons: list[str]) -> str:
        logger.debug(f'[add_keyboard] {buttons=!r}')
        if len(buttons) > 3:
            buttons = buttons[:3]
        return 'OK'


    @beta_async_tool(name='fetch_tender', description='''
Retrieves detailed content of a specific tender from the database.

Use this tool when you don't have contents of some tender and you need it.
    '''.strip())
    async def fetch_tender(tender_id: str) -> str:
        data = await tender_get(db, tender_id)
        logger.debug(f'[fetch_tender] {tender_id=!r} ')
        return tool_responses['fetch_tender'].render(data)


    @beta_async_tool(name='fetch_document', description='''
Retrieves contents of Pdf/Docx/Text/Image file. You can use this fetch_document tool even if you're not sure \
about target document type, because this fetch_document tool returns just document type if it's neither \
docx nor pdf nor text nor image.
Text type include all content types starting with "text/" like "text/csv", "text/plain"
Image type include JPEG, PNG, GIF, WebP formats. You can understand not only text on image, but also visual.
If you are sure that document is image, put is_image=true, so it would be rendered as image to user.
    '''.strip())
    async def fetch_document(url: str, is_image: bool | None = None):
        logger.debug(f'[fetch_document] {url=!r}')
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)

        content_type = str(resp.headers.get('Content-Type', ''))
        filename = resp.headers.get('content-disposition', '').split('filename=')[-1].strip('"')
        if not filename:
            filename = url.strip('/').split('/')[-1]

        if filename.endswith('.pdf') or content_type == 'application/pdf':
            pdf_response: BetaRequestDocumentBlockParam = {
                'type': 'document',
                'source': {
                    'data': base64.b64encode(resp.content).decode(),
                    'media_type': 'application/pdf',
                    'type': 'base64',
                },
                'title': filename,
                'cache_control': {
                    'type': 'ephemeral',
                }
            }
            return [pdf_response]

        if content_type.startswith('text/'):
            text_response: BetaRequestDocumentBlockParam = {
                'type': 'document',
                'source': {
                    'data': resp.text,
                    'media_type': 'text/plain',
                    'type': 'text',
                },
                'title': filename,
            }
            return [text_response]

        if (
            filename.endswith('.docx') or filename.endswith('.doc') or
            content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ):
            text = await event_loop.run_in_executor(
                executor,
                mammoth.convert_to_markdown,
                BytesIO(resp.content)
            )
            docx_response: BetaRequestDocumentBlockParam = {
                'type': 'document',
                'source': {
                    'data': text.value,
                    'media_type': 'text/plain',
                    'type': 'text',
                },
                'title': filename,
            }
            return [docx_response]

        image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp')

        if filename.lower().endswith(image_extensions) or content_type.startswith('image/'):
            media_type: Literal["image/jpeg", "image/png", "image/gif", "image/webp"]

            normalized_content_type = content_type.split(';', 1)[0].strip().lower()

            if normalized_content_type in ('image/jpeg', 'image/jpg'):
                media_type = 'image/jpeg'
            elif normalized_content_type == 'image/png':
                media_type = 'image/png'
            elif normalized_content_type == 'image/gif':
                media_type = 'image/gif'
            elif normalized_content_type == 'image/webp':
                media_type = 'image/webp'

            if media_type is None:
                lower_name = filename.lower()
                if lower_name.endswith(('.jpeg', '.jpg')):
                    media_type = 'image/jpeg'
                elif lower_name.endswith('.png'):
                    media_type = 'image/png'
                elif lower_name.endswith('.gif'):
                    media_type = 'image/gif'
                elif lower_name.endswith('.webp'):
                    media_type = 'image/webp'
                else:
                    return f'Unsupported image type: {content_type=!r}, {filename=!r}'

            image_response: BetaImageBlockParam = {
                'type': 'image',
                'source': {
                    'data': base64.b64encode(resp.content).decode(),
                    'media_type': media_type,
                    'type': 'base64',
                },
                'cache_control': {
                    'type': 'ephemeral',
                }
            }
            return [image_response]

        return f'Incorrect file type: {content_type=!r}, {filename=!r}'


    @beta_async_tool(name='report', description='''
A tool for generating a report for tender.
The report should contain detailed information about tenders, including:
- Financial details: Revenue, taxes
- Suppliers: Risks, Price, Delivery, Availability of certificates if required in the tender
- Information about the tender and its organizer, including technical requirements

You should fill:
- content: You can use markdown and emojies to format report. You shouldn't include here \
information about margin, because system will calculate and show histogram with \
margins based on `tenders` argument you provided.
- tenders: A short financial analysis separately for each tender in this report:
```
{
    tender_id: string,
    price: number,
    tax_percent: number | null,
    suppliers: {
        label: string,
        price: number,
        delivery_price: number | null,
    }[],
}[]
```
                     
tax_percent is float from 0 to 1. You can google tax for this type of good in Kazakhstan.

USE THIS TOOL ONLY IF THE USER EXPLICITLY ASKED YOU TO MAKE A REPORT.
'''.strip())
    async def report(content: str, tenders: list[TenderAnalysis] | None = None):
        return 'OK'

    return [
        check_company,
        search_companies,
        fetch_tender,
        search_satu_products,
        fetch_satu_product_details,
        add_keyboard,
        fetch_document,
        report,
        AnthropicTool(
            type='web_search_20250305',
            name='web_search',
            max_uses=30,
            blocked_domains=["satu.kz"],
        ),
        AnthropicTool(
            type='web_fetch_20250910',
            name='web_fetch',
            max_uses=30,
        ),
    ]
