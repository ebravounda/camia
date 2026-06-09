"""Stripe subscription/billing routes."""
import os
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest,
)

from models import utcnow, new_id
from auth import get_current_user
from routes_app import get_plan_by_id


router = APIRouter(prefix="/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    plan_id: str
    origin_url: str


def _stripe(req: Request) -> StripeCheckout:
    api_key = os.environ["STRIPE_API_KEY"]
    host_url = str(req.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    return StripeCheckout(api_key=api_key, webhook_url=webhook_url)


@router.post("/checkout")
async def create_checkout(
    payload: CheckoutRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    from server import db
    plan = get_plan_by_id(payload.plan_id)
    if not plan or plan.price_monthly <= 0:
        raise HTTPException(status_code=400, detail="Plan inválido")

    origin = payload.origin_url.rstrip("/")
    success_url = f"{origin}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/pricing"

    stripe_checkout = _stripe(request)
    metadata = {
        "user_id": user["id"],
        "user_email": user["email"],
        "plan_id": plan.id,
        "source": "smartcam_subscription",
    }
    ckreq = CheckoutSessionRequest(
        amount=float(plan.price_monthly),
        currency=plan.currency,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )
    session = await stripe_checkout.create_checkout_session(ckreq)

    await db.payment_transactions.insert_one({
        "id": new_id(),
        "user_id": user["id"],
        "session_id": session.session_id,
        "amount": float(plan.price_monthly),
        "currency": plan.currency,
        "plan_id": plan.id,
        "payment_status": "initiated",
        "status": "open",
        "metadata": metadata,
        "created_at": utcnow().isoformat(),
        "updated_at": utcnow().isoformat(),
    })

    return {"url": session.url, "session_id": session.session_id}


@router.get("/status/{session_id}")
async def get_status(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    from server import db

    tx = await db.payment_transactions.find_one({"session_id": session_id, "user_id": user["id"]}, {"_id": 0})
    if not tx:
        raise HTTPException(status_code=404, detail="Transacción no encontrada")

    # If already paid, return cached
    if tx["payment_status"] == "paid":
        return {"payment_status": "paid", "status": tx["status"], "plan_id": tx["plan_id"]}

    stripe_checkout = _stripe(request)
    status = await stripe_checkout.get_checkout_status(session_id)

    new_payment_status = status.payment_status
    new_status = status.status

    update_fields = {
        "payment_status": new_payment_status,
        "status": new_status,
        "updated_at": utcnow().isoformat(),
    }
    await db.payment_transactions.update_one({"session_id": session_id}, {"$set": update_fields})

    # If payment just became paid, activate subscription (only once)
    if new_payment_status == "paid" and tx["payment_status"] != "paid":
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {
                "subscription_plan": tx["plan_id"],
                "subscription_status": "active",
            }},
        )

    return {
        "payment_status": new_payment_status,
        "status": new_status,
        "amount_total": status.amount_total,
        "currency": status.currency,
        "plan_id": tx["plan_id"],
    }


# Public webhook (no auth)
async def stripe_webhook_handler(request: Request):
    from server import db
    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    stripe_checkout = _stripe(request)
    try:
        event = await stripe_checkout.handle_webhook(body, signature)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook inválido: {e}")

    if event.payment_status == "paid":
        tx = await db.payment_transactions.find_one({"session_id": event.session_id})
        if tx and tx.get("payment_status") != "paid":
            await db.payment_transactions.update_one(
                {"session_id": event.session_id},
                {"$set": {"payment_status": "paid", "status": "complete", "updated_at": utcnow().isoformat()}},
            )
            await db.users.update_one(
                {"id": tx["user_id"]},
                {"$set": {"subscription_plan": tx["plan_id"], "subscription_status": "active"}},
            )
    return {"received": True}
