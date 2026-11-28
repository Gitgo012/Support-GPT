
import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.api.routes.store import normalize_email
from app.services.chat_service import chat_service
from app.services.database import database


router = APIRouter()
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Customer message",
    )

    session_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Conversation session ID",
    )
    customer_email: str | None = Field(default=None, max_length=254)
    order_id: str | None = Field(default=None, max_length=40)
    product_id: str | None = Field(default=None, max_length=80)


class ChatResponse(BaseModel):
    response: str
    session_id: str
    ticket_id: str | None = None
    escalation_available: bool = False


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "model_loaded": chat_service.assistant is not None,
        "device": chat_service.device,
        "adapter_source": chat_service.adapter_source,
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    message = request.message.strip()

    if not message:
        raise HTTPException(
            status_code=422,
            detail="Message cannot be empty.",
        )

    session_id = (
        request.session_id.strip()
        if request.session_id
        else str(uuid4())
    )

    if not session_id:
        raise HTTPException(
            status_code=422,
            detail="Session ID cannot be empty.",
        )

    customer_context = None
    email = None
    history = None
    selected_order_id = None
    if request.customer_email:
        email = normalize_email(request.customer_email)
        customer = database.get_customer(email)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found.")
        if not database.conversation_belongs_to(session_id, email):
            raise HTTPException(status_code=403, detail="Conversation belongs to another customer.")
        customer_context = {"customer": customer}
        history = database.conversation_messages(session_id, email) or []
        mentioned_order = chat_service.ORDER_ID.search(message)
        selected_order_id = request.order_id.strip().upper() if request.order_id else None
        if not selected_order_id and mentioned_order:
            selected_order_id = mentioned_order.group(0).upper()
        if not selected_order_id:
            selected_order_id = database.conversation_order_id(session_id, email)
        if selected_order_id:
            order = database.get_order(selected_order_id, email)
            if not order:
                raise HTTPException(status_code=404, detail="Order not found for this customer.")
            customer_context["order"] = order
            selected_order_id = order["id"]
    if request.product_id:
        product = database.get_product(request.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found.")
        if customer_context is None:
            customer_context = {}
        customer_context["product"] = product

    try:
        ticket = None
        if customer_context:
            response = await run_in_threadpool(
                chat_service.generate_response,
                message,
                session_id,
                customer_context,
                history,
            )
            intent = chat_service.classify_intent(message)
            escalation_available = chat_service.escalation_available(message)
            if intent == "human" and email:
                ticket = database.create_ticket(
                    email,
                    "Customer requested human support",
                    message,
                    selected_order_id,
                )
                if ticket is None:
                    raise HTTPException(
                        status_code=400,
                        detail="Could not link the support ticket to this order.",
                    )
                escalation_available = False
                response += (
                    f" I've created demo support ticket {ticket['id']} for the sample "
                    "support queue. No live support agent is connected."
                )
            if email is not None:
                database.save_exchange(
                    session_id,
                    email,
                    message,
                    response,
                    selected_order_id,
                )
        else:
            response = await run_in_threadpool(
                chat_service.generate_response,
                message,
                session_id,
            )
            escalation_available = chat_service.escalation_available(message)

        return ChatResponse(
            response=response,
            session_id=session_id,
            ticket_id=ticket["id"] if ticket else None,
            escalation_available=escalation_available,
        )

    except HTTPException:
        raise
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Support chat response failed (%s).", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while generating the response.",
        )
