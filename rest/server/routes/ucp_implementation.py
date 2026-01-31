#   Copyright 2026 UCP Authors
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""Implementation of UCP routes.

Injects business logic into generated routes.
"""

import logging
from typing import Annotated, Any

import dependencies
from fastapi import APIRouter
from fastapi import Body
from fastapi import Depends
from fastapi import Path
from fastapi.routing import APIRoute
import models
from models import UnifiedCheckoutCreateRequest
from services.checkout_service import CheckoutService
from ucp_sdk.models.schemas.shopping.ap2_mandate import Ap2CompleteRequest
from ucp_sdk.models.schemas.shopping.order import Order
from ucp_sdk.models.schemas.shopping.payment_create_req import (
  PaymentCreateRequest,
)

logger = logging.getLogger(__name__)


async def create_checkout(
  checkout_req: Annotated[UnifiedCheckoutCreateRequest, Body(...)],
  common_headers: Annotated[
    dependencies.CommonHeaders, Depends(dependencies.common_headers)
  ],
  idempotency_key: Annotated[str, Depends(dependencies.idempotency_header)],
  checkout_service: Annotated[
    CheckoutService, Depends(dependencies.get_checkout_service)
  ],
) -> dict[str, Any]:
  """Create Checkout Implementation."""
  del common_headers  # Unused
  req_dict = checkout_req.model_dump(exclude_unset=True, by_alias=True)
  unified_req = models.UnifiedCheckoutCreateRequest(**req_dict)

  result = await checkout_service.create_checkout(unified_req, idempotency_key)
  return result.model_dump(mode="json", by_alias=True)


async def get_checkout(
  checkout_id: Annotated[str, Path(..., alias="id")],
  common_headers: Annotated[
    dependencies.CommonHeaders, Depends(dependencies.common_headers)
  ],
  checkout_service: Annotated[
    CheckoutService, Depends(dependencies.get_checkout_service)
  ],
) -> dict[str, Any]:
  """Get Checkout Implementation."""
  del common_headers  # Unused
  result = await checkout_service.get_checkout(checkout_id)
  return result.model_dump(mode="json", by_alias=True)


async def update_checkout(
  checkout_id: Annotated[str, Path(..., alias="id")],
  checkout_req: Annotated[models.UnifiedCheckoutUpdateRequest, Body(...)],
  common_headers: Annotated[
    dependencies.CommonHeaders, Depends(dependencies.common_headers)
  ],
  idempotency_key: Annotated[str, Depends(dependencies.idempotency_header)],
  checkout_service: Annotated[
    CheckoutService, Depends(dependencies.get_checkout_service)
  ],
) -> dict[str, Any]:
  """Update Checkout Implementation."""
  del common_headers  # Unused
  req_dict = checkout_req.model_dump(exclude_unset=True, by_alias=True)
  unified_req = models.UnifiedCheckoutUpdateRequest(**req_dict)

  result = await checkout_service.update_checkout(
    checkout_id, unified_req, idempotency_key
  )
  return result.model_dump(mode="json", by_alias=True)


async def complete_checkout(
  checkout_id: Annotated[str, Path(..., alias="id")],
  payment_data: Annotated[dict[str, Any], Body(...)],
  risk_signals: Annotated[dict[str, Any], Body(...)],
  common_headers: Annotated[
    dependencies.CommonHeaders, Depends(dependencies.common_headers)
  ],
  idempotency_key: Annotated[str, Depends(dependencies.idempotency_header)],
  checkout_service: Annotated[
    CheckoutService, Depends(dependencies.get_checkout_service)
  ],
  ap2: Annotated[Ap2CompleteRequest | None, Body()] = None,
) -> dict[str, Any]:
  """Complete Checkout with Hedera Payment."""
  del common_headers  # Unused

  # Create payment request with raw Hedera payment data
  payment_req = PaymentCreateRequest(
    selected_instrument_id=payment_data.get("id"),
    instruments=[],
  )
  payment_req._raw_crypto_payment = payment_data

  checkout_result = await checkout_service.complete_checkout(
    checkout_id, payment_req, risk_signals, idempotency_key, ap2=ap2
  )
  return checkout_result.model_dump(mode="json", by_alias=True)


async def cancel_checkout(
  checkout_id: Annotated[str, Path(..., alias="id")],
  common_headers: Annotated[
    dependencies.CommonHeaders, Depends(dependencies.common_headers)
  ],
  idempotency_key: Annotated[str, Depends(dependencies.idempotency_header)],
  checkout_service: Annotated[
    CheckoutService, Depends(dependencies.get_checkout_service)
  ],
) -> models.UnifiedCheckout:
  """Cancel Checkout Implementation."""
  del common_headers  # Unused
  return await checkout_service.cancel_checkout(checkout_id, idempotency_key)


async def order_event_webhook(
  partner_id: str,
  payload: Annotated[Order, Body(...)],
  # CommonHeaders checks ucp-agent, which might not be present in webhook?
  # Webhook server used specific headers.
  # We verify signature using dependency.
  signature: Annotated[None, Depends(dependencies.verify_signature)],
  checkout_service: Annotated[
    CheckoutService, Depends(dependencies.get_checkout_service)
  ],
) -> dict[str, Any]:
  """Order Event Webhook Implementation."""
  del partner_id, signature  # Unused
  payload_dict = payload.model_dump(mode="json", by_alias=True)
  await checkout_service.update_order(payload.id, payload_dict)
  return {"status": "ok"}


# Map operation_id to implementation
IMPLEMENTATIONS = {
  "create_checkout": create_checkout,
  "get_checkout": get_checkout,
  "update_checkout": update_checkout,
  "complete_checkout": complete_checkout,
  "cancel_checkout": cancel_checkout,
  "order_event_webhook": order_event_webhook,
}


def apply_implementation(router: APIRouter) -> None:
  """Replace router endpoints with implementations.

  Args:
      router: The APIRouter to modify.

  """
  new_routes = []
  for route in router.routes:
    if isinstance(route, APIRoute) and route.operation_id in IMPLEMENTATIONS:
      impl = IMPLEMENTATIONS[route.operation_id]
      # Create a new route with the implementation but keeping metadata from
      # original route. We must use the new endpoint to generate correct
      # dependencies.
      new_route = APIRoute(
        path=route.path,
        endpoint=impl,
        methods=route.methods,
        response_model=route.response_model,
        status_code=route.status_code,
        tags=route.tags,
        summary=route.summary,
        description=route.description,
        operation_id=route.operation_id,
        # We do NOT copy route.dependencies because we want the dependencies
        # from the NEW endpoint (impl). If the original route had
        # dependencies (e.g. router level), they are usually added when
        # including router. Here we are modifying the router's own routes.
        # APIRoute(endpoint=impl) will parse impl's signature. If we passed
        # `dependencies=route.dependencies`, it would be valid (list of
        # dependencies). Generated ucp_routes.py doesn't seem to have
        # route-level dependencies.
        dependencies=route.dependencies,
        response_class=route.response_class,
        name=route.name,
        callbacks=route.callbacks,
        openapi_extra=route.openapi_extra,
        generate_unique_id_function=route.generate_unique_id_function,
      )
      new_routes.append(new_route)
    else:
      new_routes.append(route)

  router.routes = new_routes
