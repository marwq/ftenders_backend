from typing import Any
from dishka import FromDishka
from pymongo.asynchronous.database import AsyncDatabase
import httpx


SEARCH_QUERY = """
query SearchListingQuery($search_term: String!, $offset: Int, $limit: Int, $params: Any, $company_id: Int, $sort: String, $regionId: Int = null, $subdomain: String = null) {
listing: searchListing(
search_term: $search_term
limit: $limit
offset: $offset
params: $params
company_id: $company_id
sort: $sort
region: {id: $regionId, subdomain: $subdomain}
) {
searchTerm
page {
correctedSearchTerm
...ProductsListFragment
__typename
}
__typename
}
}

fragment ProductsListFragment on ListingPage {
products {
...ProductsItemFragment
__typename
}
__typename
}

fragment ProductsItemFragment on ProductItem {
product_item_id
algSource
...ProductTileProductItemFragment
product {
id
labels {
isEvoPayEnabled
__typename
}
company {
id
__typename
}
__typename
}
__typename
}

fragment ProductTileProductItemFragment on ProductItem {
product {
id
is14Plus
isService
presence {
presence
__typename
}
urlText
groupId
productTypeKey
priceOriginal
priceUSD
categoryId
categoryIds
company_id
discountedPrice
newModelId
productOpinionCounters {
rating
count
__typename
}
company {
id
deliveryStats {
id
deliverySpeed
__typename
}
...ProductTileCompanyDetailsFragment
__typename
}
category {
id
areModelsEnabled
forceProductContent
verticalDomain
__typename
}
model {
id
name
urlText
images(width: 200, height: 200)
images400x400: images(width: 400, height: 400)
category {
id
isAdult
is14Plus
verticalDomain
__typename
}
counters {
count
rating
__typename
}
__typename
}
payPartsButtonText
...SchemaOrgProductFragment
...ProductTileImageFragment
...ProductPresenceFragment
...ProductPriceFragment
...ProductPayPartsPriceFragment
...ConversionBlockProductFragment
...FavoriteProductFragment
__typename
}
productModel {
model_id
min_price
product_count
company_count
max_price
model_product_ids
__typename
}
algSource
...FavoriteProductItemFragment
__typename
}

fragment SchemaOrgProductFragment on Product {
id
name: nameForCatalog
sku
imageForProductSchema: image(width: 200, height: 200)
urlText
categoryIds
priceCurrency
price
discountDays
discountedPrice
hasDiscount
isAdult
buyButtonDisplayType
measureUnitCommonCode
productOpinionCounters {
rating
count
__typename
}
wholesalePrices {
id
measureUnitCommonCode
minimumOrderQuantity
price
__typename
}
presence {
presence
__typename
}
company {
id
name
returnPolicy {
id
returnTerms
notRefundable
__typename
}
opinionStats {
id
opinionPositivePercent
opinionTotal
__typename
}
__typename
}
manufacturerInfo {
id
name
__typename
}
__typename
}

fragment ProductTileImageFragment on Product {
id
image(width: 200, height: 200)
image400x400: image(width: 400, height: 400)
imageAlt: image(width: 640, height: 640)
is14Plus
isAdult
name: nameForCatalog
__typename
}

fragment ProductPresenceFragment on Product {
presence {
presence
isAvailable
isEnding
isOrderable
isUnknown
isWait
isPresenceSure
__typename
}
catalogPresence {
value
title
titleExt
titleUnavailable
availabilityDate
__typename
}
__typename
}

fragment ProductPriceFragment on Product {
id
price
priceCurrencyLocalized
hasDiscount
discountedPrice
noPriceText
measureUnit
priceFrom
discountDaysLabel
canShowPrice
wholesalePrices {
id
price
__typename
}
sellingType
__typename
}

fragment ProductPayPartsPriceFragment on Product {
id
payPartsPrice
priceCurrencyLocalized
__typename
}

fragment ConversionBlockProductFragment on Product {
id
company_id
discountedPrice
price
priceCurrencyLocalized
image(width: 200, height: 200)
name: nameForCatalog
signed_id
buyButtonDisplayType
report_start_chat_url
groupId
company {
id
isChatVisible
__typename
}
__typename
}

fragment FavoriteProductFragment on Product {
id
discountedPrice
categoryIds
company_id
price
priceCurrency
groupId
productTypeKey
priceOriginal
priceUSD
categoryId
payPartsButtonText
newModelId
category {
id
areModelsEnabled
forceProductContent
__typename
}
labels {
isEvoPayEnabled
__typename
}
presence {
isPresenceSure
__typename
}
company {
id
deliveryStats {
id
deliverySpeed
__typename
}
opinionStats {
id
opinionPositivePercent
__typename
}
__typename
}
__typename
}

fragment FavoriteProductItemFragment on ProductItem {
productModel {
model_id
min_price
product_count
company_count
max_price
model_product_ids
__typename
}
__typename
}

fragment ProductTileCompanyDetailsFragment on Company {
id
name
slug
regionName
countryName
...CompanyRatingFragment
__typename
}

fragment CompanyRatingFragment on Company {
id
inTopSegment
isService
opinionStats {
id
opinionPositivePercent
opinionTotal
__typename
}
combinedOpinionStats {
id
opinionPositivePercent
opinionTotal
__typename
}
deliveryStats {
id
deliverySpeed
__typename
}
__typename
}
"""

CONTACT_QUERY = """
query OverlayCallbackQuery($productID: Long!) {
product(id: $productID) {
id
company {
id
name
phones {
id
number
__typename
}
isChatVisible
slug
webSiteUrl
lastActivityTime
isOperating
isWorkingNow
__typename
}
__typename
}
}
"""

DELIVERY_PAYMENT_QUERY = """
query DeliveryAndPaymentsQuery($productId: Long!) {
product(id: $productId) {
id
company {
id
deliveryRegions {
id
name
subRegions {
id
name
subRegions {
id
name
__typename
}
__typename
}
__typename
}
__typename
}
paymentOptions {
id
name
raw_type
__typename
}
deliveryOptions {
id
raw_type
name
available_payment_option_ids
comment
__typename
}
__typename
}
}
"""


async def product_satu_search(
    query: str,
    db: FromDishka[AsyncDatabase],
    page: int = 0,
    price_lower_than: int | None = None,
):
    limit = 3
    offset = page * limit

    cache_key = f"{query}:{page}:{price_lower_than}"
    cached = await db.product_satu_queries.find_one({'query': cache_key})
    if cached:
        return cached['result']

    params: dict[str, Any] = {'binary_filters': []}
    if price_lower_than is not None:
        params['price_local__lte'] = str(price_lower_than)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            'https://satu.kz/graphql',
            json={
                'operationName': 'SearchListingQuery',
                'variables': {
                    'regionId': None,
                    'includePremiumAdvBlock': False,
                    'search_term': query,
                    'params': params,
                    'limit': limit,
                    'offset': offset,
                },
                'query': SEARCH_QUERY,
            },
            headers={
                'Content-Type': 'application/json',
            }
        )
        result = resp.json()

    await db.product_satu_queries.insert_one({
        'query': cache_key,
        'result': result,
    })

    return result


async def product_satu_details(
    product_id: int,
    db: FromDishka[AsyncDatabase],
):
    cached = await db.product_satu_details.find_one({'product_id': product_id})
    if cached:
        return cached['result']

    async with httpx.AsyncClient() as client:
        contacts_resp = await client.post(
            'https://satu.kz/graphql',
            json={
                'operationName': 'OverlayCallbackQuery',
                'variables': {
                    'productID': product_id,
                },
                'query': CONTACT_QUERY,
            },
            headers={
                'Content-Type': 'application/json',
            }
        )
        contacts_result = contacts_resp.json()

        delivery_payment_resp = await client.post(
            'https://satu.kz/graphql',
            json={
                'operationName': 'DeliveryAndPaymentsQuery',
                'variables': {
                    'productId': product_id,
                },
                'query': DELIVERY_PAYMENT_QUERY,
            },
            headers={
                'Content-Type': 'application/json',
            }
        )
        delivery_payment_result = delivery_payment_resp.json()

    result = {
        'contacts': contacts_result,
        'delivery_payment': delivery_payment_result,
    }

    await db.product_satu_details.insert_one({
        'product_id': product_id,
        'result': result,
    })

    return result
