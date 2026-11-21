import re
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.database import database


router = APIRouter()


class CustomerRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=1, max_length=80)


class OrderRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    product_id: str = Field(min_length=1, max_length=80)
    quantity: int = Field(default=1, ge=1, le=5)


class TicketRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    subject: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=10, max_length=2000)
    order_id: str | None = Field(default=None, max_length=40)


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    return normalized


@router.get("/products")
async def products(
    search: Annotated[str, Query(max_length=100)] = "",
    category: Annotated[str, Query(max_length=40)] = "",
):
    return database.list_products(search=search.strip(), category=category.strip())


@router.get("/categories")
async def categories():
    return sorted({product["category"] for product in database.list_products()})


@router.post("/customers")
async def create_customer(request: CustomerRequest):
    email = normalize_email(request.email)
    if not request.name.strip():
        raise HTTPException(status_code=422, detail="Name cannot be empty.")
    customer = database.create_customer(email, request.name)
    return {"customer": customer, "demo_mode": True}


@router.get("/customers/{email}")
async def customer(email: str):
    customer_record = database.get_customer(normalize_email(email))
    if not customer_record:
        raise HTTPException(status_code=404, detail="Customer not found.")
    return customer_record


@router.get("/customers/{email}/orders")
async def customer_orders(email: str):
    normalized_email = normalize_email(email)
    if not database.get_customer(normalized_email):
        raise HTTPException(status_code=404, detail="Customer not found.")
    return database.list_orders(normalized_email)


@router.get("/orders/{order_id}")
async def order_details(order_id: str, email: str = Query(min_length=3, max_length=254)):
    order = database.get_order(order_id, normalize_email(email))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found for this customer.")
    return order


@router.post("/orders", status_code=201)
async def create_order(request: OrderRequest):
    email = normalize_email(request.email)
    order = database.create_order(email, request.product_id, request.quantity)
    if not order:
        raise HTTPException(status_code=404, detail="Customer or product not found.")
    return order


@router.post("/tickets", status_code=201)
async def create_ticket(request: TicketRequest):
    email = normalize_email(request.email)
    if not database.get_customer(email):
        raise HTTPException(status_code=404, detail="Customer not found.")
    subject = request.subject.strip()
    message = request.message.strip()
    if len(subject) < 3 or len(message) < 10:
        raise HTTPException(
            status_code=422,
            detail="Ticket subject and message cannot be blank.",
        )
    ticket = database.create_ticket(
        email=email,
        subject=subject,
        message=message,
        order_id=request.order_id,
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Order not found for this customer.")
    return ticket


@router.get("/customers/{email}/tickets")
async def customer_tickets(email: str):
    normalized_email = normalize_email(email)
    if not database.get_customer(normalized_email):
        raise HTTPException(status_code=404, detail="Customer not found.")
    with database.connection() as connection:
        rows = connection.execute(
            "SELECT * FROM tickets WHERE customer_email = ? ORDER BY created_at DESC",
            (normalized_email,),
        ).fetchall()
        return [dict(row) for row in rows]


@router.get("/conversations/{session_id}")
async def conversation_history(
    session_id: str,
    email: str = Query(min_length=3, max_length=254),
):
    messages = database.conversation_messages(session_id, normalize_email(email))
    if messages is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return messages


@router.get("/customers/{email}/conversations")
async def customer_conversations(email: str):
    normalized_email = normalize_email(email)
    if not database.get_customer(normalized_email):
        raise HTTPException(status_code=404, detail="Customer not found.")
    return database.list_conversations(normalized_email)
