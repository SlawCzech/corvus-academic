"""Reading a model's reply back out of a chat message."""

from pydantic import BaseModel, TypeAdapter

from src.application.json_output import extract_json, message_text


class _Reply(BaseModel):
    topic: str


def test_a_plain_string_is_the_reply() -> None:
    assert message_text('{"topic": "x"}') == '{"topic": "x"}'


def test_only_the_text_parts_of_a_reply_in_parts_count() -> None:
    """What Claude returns with thinking on: the reasoning, then the answer."""
    content = [
        {"type": "thinking", "thinking": "Let me think…", "signature": "EvEC"},
        {"type": "text", "text": '{"topic": "Koszty transakcyjne"}', "index": 0},
    ]

    reply = TypeAdapter(_Reply).validate_json(extract_json(message_text(content)))

    assert reply.topic == "Koszty transakcyjne"


def test_text_split_across_parts_is_joined_in_order() -> None:
    content = [
        {"type": "text", "text": '{"topic": '},
        '"x"',
        {"type": "text", "text": "}"},
    ]

    assert message_text(content) == '{"topic": "x"}'


def test_content_without_any_text_is_rendered_whole() -> None:
    content = [{"type": "json", "value": {"doi": "10.1/x"}}]

    assert message_text(content) == '[{"type": "json", "value": {"doi": "10.1/x"}}]'
