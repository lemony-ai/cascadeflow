from cascadeflow.utils.messages import detect_multi_turn


def test_detect_multi_turn_from_messages():
    messages = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
        {"role": "user", "content": "Follow-up question"},
    ]
    assert detect_multi_turn("User: Hi\nAssistant: Hello\nUser: Follow-up question", messages)


def test_detect_multi_turn_from_prompt_only():
    prompt = "User: Hi\nAssistant: Hello\nUser: Continue the conversation"
    assert detect_multi_turn(prompt, None)


def test_detect_multi_turn_single_turn_false():
    prompt = "User: Hi\nAssistant: Hello"
    assert not detect_multi_turn(prompt, [{"role": "user", "content": "Hi"}])
