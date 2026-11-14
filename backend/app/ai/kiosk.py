"""Deterministic bilingual kiosk conversation engine.

This engine is the default runtime: it is fully functional without any LLM
API key, and it can only manipulate the cart through KioskTools.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KioskMessage, MenuItem

from .matcher import detect_intent, extract_quantity, rank_items, split_order_segments
from .tools import KioskTools


def money(value: float) -> str:
    return f"{value:,.2f}"


def localized(item: MenuItem, lang: str) -> str:
    if lang == "ar" and item.item_name_ar:
        return item.item_name_ar
    return item.item_name


def _reply_text(*, lang: str, ar: str, en: str) -> str:
    return ar if lang == "ar" else en


def _save(db: Session, session_id: str, role: str, content: str, lang: str) -> None:
    db.add(KioskMessage(session_id=session_id, role=role, content=content, language=lang))


def _cart_reply(tools: KioskTools, lang: str, intro: Optional[str] = None) -> str:
    summary = tools.get_cart_summary()
    if not summary["cart"]:
        return _reply_text(
            lang=lang,
            ar="السلة فاضية. تحب أرشحلك حاجة من المنيو؟",
            en="Your cart is empty. Would you like a recommendation from the menu?",
        )
    lines = []
    for line in summary["cart"]:
        name = line["item_name_ar"] if lang == "ar" and line["item_name_ar"] else line["item_name"]
        lines.append(f"• {line['quantity']} × {name} — {money(line['line_total'])} EGP")
    body = "\n".join(lines)
    if lang == "ar":
        head = intro or "طلبك الحالي:"
        return f"{head}\n{body}\n\nالإجمالي: {money(summary['subtotal'])} EGP\nهل تحب أأكد الأوردر؟"
    head = intro or "Your current order:"
    return f"{head}\n{body}\n\nTotal: {money(summary['subtotal'])} EGP\nWould you like me to confirm the order?"


def process_message(
    db: Session,
    *,
    session,
    message: str,
    language: str,
) -> dict:
    tools = KioskTools(db, session)
    lang = language if language in ("ar", "en") else session.language
    session.language = lang
    _save(db, session.session_id, "user", message, lang)

    intent = detect_intent(message)
    summary = tools.get_cart_summary()
    suggestions = tools.suggestions(4)
    order_id = None
    result_state = session.state

    # --------------------------------------------------------------- #
    # Explicit confirmation
    # --------------------------------------------------------------- #
    if intent == "confirm":
        if session.state == "awaiting_confirmation" and summary["cart"]:
            submitted = tools.submit_confirmed_order(
                payment_method="cash",
                customer_name=session.customer_name,
                customer_phone=session.customer_phone,
            )
            order_id = submitted["order_id"]
            text = _reply_text(
                lang=lang,
                ar=(
                    f"تم تأكيد الأوردر ✅\nرقم الأوردر: #{order_id}\n"
                    f"الإجمالي: {money(submitted['total_amount'])} EGP\n"
                    "الدفع عند الكاشير. الأوردر في الطابور الآن."
                ),
                en=(
                    f"Order confirmed ✅\nOrder number: #{order_id}\n"
                    f"Total: {money(submitted['total_amount'])} EGP\n"
                    "Payment at the counter. Your order is now in the queue."
                ),
            )
            result_state = "submitted"
        else:
            text = _cart_reply(tools, lang, intro=_reply_text(
                lang=lang,
                ar="لسه محتاج تأكيد واضح. راجع طلبك:",
                en="I need an explicit confirmation. Please review your order:",
            ))
            result_state = "awaiting_confirmation" if summary["cart"] else "idle"

    # --------------------------------------------------------------- #
    # Remove / cancel lines
    # --------------------------------------------------------------- #
    elif intent in ("remove", "cancel"):
        if intent == "cancel":
            session.state = "idle"
            for line in list(session.cart_items):
                db.delete(line)
            db.flush()
            summary = tools.get_cart_summary()
            text = _reply_text(
                lang=lang,
                ar="تم إلغاء محتويات السلة. تحب نبدأ من جديد؟",
                en="I cleared the cart. Would you like to start again?",
            )
            result_state = "idle"
        else:
            candidates = []
            for line in summary["cart"]:
                item = db.get(MenuItem, line["item_id"])
                if item and any(token in message for token in (item.item_name, item.item_name_ar)):
                    candidates.append(item)
            if not candidates and len(summary["cart"]) == 1:
                candidates = [db.get(MenuItem, summary["cart"][0]["item_id"])]
            if candidates:
                tools.remove_cart_item(candidates[0].item_id)
                text = _cart_reply(
                    tools,
                    lang,
                    intro=_reply_text(
                        lang=lang,
                        ar=f"تم حذف {localized(candidates[0], lang)}. طلبك الحالي:",
                        en=f"Removed {localized(candidates[0], lang)}. Your current order:",
                    ),
                )
            else:
                text = _reply_text(
                    lang=lang,
                    ar="قولّي تحب أشيل أنهي صنف من السلة.",
                    en="Tell me which item you want to remove from the cart.",
                )
            result_state = session.state

    # --------------------------------------------------------------- #
    # Summary
    # --------------------------------------------------------------- #
    elif intent == "summary":
        text = _cart_reply(tools, lang)
        result_state = "awaiting_confirmation" if summary["cart"] else "idle"

    # --------------------------------------------------------------- #
    # Price / availability questions
    # --------------------------------------------------------------- #
    elif intent in ("price", "availability"):
        items = db.scalars(
            select(MenuItem).where(MenuItem.item_name.is_not(None))
        ).all()
        ranked = rank_items(items, message, limit=3)
        ask_subject = not ranked or ranked[0][1] < 50
        if ask_subject:
            text = _reply_text(
                lang=lang,
                ar="تحب تعرف سعر أو توفر أنهي صنف؟ اكتب اسم الصنف من المنيو.",
                en="Which item would you like the price or availability for? Please name it from the menu.",
            )
        else:
            parts = []
            for item, _score in ranked:
                availability = _reply_text(lang=lang, ar="متوفر", en="available") if item.is_available else _reply_text(lang=lang, ar="غير متوفر", en="unavailable")
                parts.append(
                    f"{localized(item, lang)} — {money(float(item.price))} EGP ({availability})"
                )
            text = "\n".join(parts)
            if intent == "availability":
                text = _reply_text(lang=lang, ar="حالة الأصناف:\n", en="Item availability:\n") + text
        result_state = session.state

    # --------------------------------------------------------------- #
    # Greeting / menu / recommendations
    # --------------------------------------------------------------- #
    elif intent in ("greeting", "menu"):
        if intent == "menu":
            intro = _reply_text(
                lang=lang,
                ar="دي ترشيحات من المنيو الحقيقي:",
                en="Here are recommendations from the real menu:",
            )
        else:
            intro = _reply_text(
                lang=lang,
                ar="أهلاً بيك في RestoMate AI 👋 أقدر أساعدك تطلب من المنيو الحقيقي. جرّب تقول: «عايز اتنين أو جي برجر وموهيتو أو جي».",
                en="Welcome to RestoMate AI 👋 I can help you order from the real menu. Try: \"I want two OG Burgers and an OG Mojito.\"",
            )
        lines = [
            f"• {s['item_name_ar'] if lang == 'ar' and s.get('item_name_ar') else s['item_name']} — {money(s['price'])} EGP"
            for s in suggestions
        ]
        text = intro + "\n" + "\n".join(lines)
        result_state = session.state

    # --------------------------------------------------------------- #
    # Order composition
    # --------------------------------------------------------------- #
    else:
        all_items = db.scalars(
            select(MenuItem).where(MenuItem.is_available.is_(True))
        ).all()
        updated = False
        added_names: list[str] = []
        ambiguous: list[str] = []
        unknown: list[str] = []
        for segment in split_order_segments(message):
            quantity, cleaned = extract_quantity(segment)
            query = cleaned.strip()
            if not query:
                continue
            ranked = rank_items(all_items, query, limit=4)
            if not ranked:
                unknown.append(query)
                continue
            top_item, top_score = ranked[0]
            if len(ranked) > 1 and top_score < 95 and ranked[0][1] - ranked[1][1] < 4:
                options = "، ".join(dict.fromkeys(localized(candidate, lang) for candidate, _ in ranked[:3])) if lang == "ar" else ", ".join(dict.fromkeys(localized(candidate, lang) for candidate, _ in ranked[:3]))
                ambiguous.append(options)
                continue
            if top_score < 42:
                unknown.append(localized(top_item, lang) if top_score >= 20 else query)
                continue
            tools.add_item_to_cart(top_item.item_id, quantity)
            added_names.append(f"{quantity} × {localized(top_item, lang)}")
            updated = True

        if added_names:
            summary = tools.get_cart_summary()
            intro = _reply_text(
                lang=lang,
                ar="تمت الإضافة:\n" + "\n".join(f"• {name}" for name in added_names) + "\n\nطلبك الحالي:",
                en="Added:\n" + "\n".join(f"• {name}" for name in added_names) + "\n\nYour current order:",
            )
            if unknown:
                intro = _reply_text(
                    lang=lang,
                    ar="مش لاقي في المنيو: " + "، ".join(unknown) + ".\n\n" + intro,
                    en="I couldn't find on the menu: " + ", ".join(unknown) + ".\n\n" + intro,
                )
            text = _cart_reply(tools, lang, intro=intro)
            result_state = "awaiting_confirmation"
        elif ambiguous:
            text = _reply_text(
                lang=lang,
                ar="في أكتر من صنف ممكن تقصدهم: " + " | ".join(ambiguous) + ". اكتب الاسم بالظبط.",
                en="I found more than one possible match: " + " | ".join(ambiguous) + ". Please use the exact name.",
            )
        else:
            text = _reply_text(
                lang=lang,
                ar="مش متأكد من الصنف. من فضلك اكتبه من المنيو، أو قول «منيو» لترشيحات.",
                en="I'm not sure which item you mean. Please name it from the menu, or say \"menu\" for suggestions.",
            )
            result_state = session.state

    _save(db, session.session_id, "assistant", text, lang)
    db.flush()
    summary = tools.get_cart_summary()
    if result_state != "submitted":
        session.state = result_state
    return {
        "reply": text,
        "state": result_state,
        "cart": summary["cart"],
        "subtotal": summary["subtotal"],
        "order_id": order_id or session.order_id,
        "requires_confirmation": result_state == "awaiting_confirmation" and bool(summary["cart"]),
        "suggestions": suggestions,
    }
