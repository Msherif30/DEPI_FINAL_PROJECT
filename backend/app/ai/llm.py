"""Optional OpenAI-compatible LLM integration with whitelisted tools.

If no LLM_API_KEY is configured, or the provider fails, the kiosk silently
falls back to the deterministic local engine. The LLM never receives database
credentials, raw SQL capability, or permission to submit an order.
"""
from __future__ import annotations

import json
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import KioskSession

from .kiosk import localized, money
from .tools import KioskTools

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "search_menu",
            "description": "Search real menu items by Arabic or English name/synonym.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_menu_item",
            "description": "Get one exact menu item, including description and real price.",
            "parameters": {
                "type": "object",
                "properties": {"item_id": {"type": "integer"}},
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_item_price",
            "description": "Get the authoritative database price of a menu item.",
            "parameters": {
                "type": "object",
                "properties": {"item_id": {"type": "integer"}},
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check whether a menu item is currently available.",
            "parameters": {
                "type": "object",
                "properties": {"item_id": {"type": "integer"}},
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_item_to_cart",
            "description": "Add a validated menu item to the kiosk cart.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "integer"},
                    "quantity": {"type": "integer"},
                    "special_instructions": {"type": "string"},
                },
                "required": ["item_id", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_cart_item",
            "description": "Set the quantity of an item already in the cart.",
            "parameters": {
                "type": "object",
                "properties": {"item_id": {"type": "integer"}, "quantity": {"type": "integer"}},
                "required": ["item_id", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_cart_item",
            "description": "Remove an item from the kiosk cart.",
            "parameters": {
                "type": "object",
                "properties": {"item_id": {"type": "integer"}},
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cart_summary",
            "description": "Read the current cart with database prices and the subtotal.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

SYSTEM_PROMPT = """You are RestoMate AI, a friendly restaurant ordering assistant.
Rules:
- Reply in the customer's language (Egyptian Arabic, Modern Standard Arabic, or English).
- NEVER invent menu items, prices, ingredients, or availability. Always use tools.
- Prices come only from tool results and are in EGP.
- You may add/update/remove cart items only through tools.
- You cannot submit an order. Ask the customer to confirm explicitly; the app handles submission.
- Keep replies short and conversational. If a request is ambiguous, ask one clarifying question.
"""


def _execute(tools: KioskTools, name: str, arguments: dict) -> dict:
    handlers = {
        "search_menu": lambda: tools.search_menu(arguments.get("query", ""), int(arguments.get("limit", 5))),
        "get_menu_item": lambda: tools.get_menu_item(int(arguments["item_id"])),
        "get_item_price": lambda: tools.get_item_price(int(arguments["item_id"])),
        "check_availability": lambda: tools.check_availability(int(arguments["item_id"])),
        "add_item_to_cart": lambda: tools.add_item_to_cart(
            int(arguments["item_id"]),
            int(arguments.get("quantity", 1)),
            arguments.get("special_instructions"),
        ),
        "update_cart_item": lambda: tools.update_cart_item(
            int(arguments["item_id"]), int(arguments["quantity"])
        ),
        "remove_cart_item": lambda: tools.remove_cart_item(int(arguments["item_id"])),
        "get_cart_summary": lambda: tools.get_cart_summary(),
    }
    if name not in handlers:
        return {"error": "Tool not permitted"}
    try:
        return handlers[name]()
    except Exception as exc:  # noqa: BLE001 - validation error returned to model
        return {"error": str(getattr(exc, "detail", exc))}


def run_llm(
    db: Session, *, session: KioskSession, message: str, language: str
) -> Optional[dict]:
    if not settings.llm_api_key:
        return None
    tools = KioskTools(db, session)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + f"\nCurrent language: {language}."},
        {"role": "user", "content": message},
    ]
    try:
        with httpx.Client(timeout=25.0) as client:
            for _ in range(4):
                response = client.post(
                    f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                    json={
                        "model": settings.llm_model,
                        "messages": messages,
                        "tools": TOOL_SPECS,
                        "temperature": 0.2,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                choice = payload["choices"][0]["message"]
                messages.append(choice)
                tool_calls = choice.get("tool_calls") or []
                if not tool_calls:
                    text = choice.get("content") or ""
                    break
                for call in tool_calls:
                    try:
                        arguments = json.loads(call["function"].get("arguments") or "{}")
                    except json.JSONDecodeError:
                        arguments = {}
                    result = _execute(tools, call["function"]["name"], arguments)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": json.dumps(result, ensure_ascii=False, default=str),
                        }
                    )
            else:
                text = ""
    except Exception:  # noqa: BLE001 - provider failure -> deterministic fallback
        db.rollback()
        return None

    db.flush()
    summary = tools.get_cart_summary()
    return {
        "reply": text or ("تم تحديث طلبك." if language == "ar" else "Your order was updated."),
        "state": session.state,
        "cart": summary["cart"],
        "subtotal": summary["subtotal"],
        "order_id": session.order_id,
        "requires_confirmation": bool(summary["cart"]),
        "suggestions": tools.suggestions(4),
    }
