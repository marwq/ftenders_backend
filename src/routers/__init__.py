from fastapi import APIRouter
from dishka.integrations.fastapi import DishkaRoute

from src.routers.ai import ai_websocket
from src.routers.company import company_get, company_search
from src.routers.tender import tender_get, tender_list
from src.routers.product import product_satu_search, product_satu_details


router = APIRouter(route_class=DishkaRoute)

router.add_api_route('/company/{bin}', company_get, methods=['GET'])
router.add_api_route('/company/', company_search, methods=['GET'])

router.add_api_route('/tender/', tender_list, methods=['GET'])
router.add_api_route('/tender/{id}', tender_get, methods=['GET'])

router.add_api_route('/product/satu/', product_satu_search, methods=['GET'])
router.add_api_route('/product/satu/{product_id}/details', product_satu_details, methods=['GET'])

router.add_api_websocket_route('/ai/ws', ai_websocket)
