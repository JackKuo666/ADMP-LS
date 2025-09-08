import json


def formate_message(type: str, message: str):
    message = {"type": type, "label": message}
    formatted_message = (
        f"\n```bio-chat-agent-task\n{json.dumps(message, ensure_ascii=False)}\n```\n"
    )
    return formatted_message
