def get_api_hint(request: str) -> str:
    hints = []
    req = request.lower()
    if "stripe" in req or "payment" in req:
        hints.append("STRIPE: Use stripe.checkout.Session.create() for payments")
    if "clerk" in req or "auth" in req:
        hints.append("CLERK: Use @require_auth decorator, get_user_id() for JWT")
    if "socket" in req or "realtime" in req or "chat" in req:
        hints.append("SOCKETIO: Use flask_socketio, emit events to rooms")
    return "\n".join(hints)
