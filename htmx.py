import json


def hx_show_message(response, message, level="success"):
    """Set HX-Trigger on a response to fire a toastr notification."""
    response["HX-Trigger"] = json.dumps(
        {"showMessage": {"type": level, "message": message}}
    )
    return response
