import json

VALID = {"email": "journey@example.com", "password": "password-123"}


async def test_registered_user_full_journey(client):
    register = await client.post("/api/auth/register", json=VALID)
    assert register.status_code == 201
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = await client.get("/api/auth/me", headers=headers)
    assert me.json()["email"] == "journey@example.com"

    ask = await client.post("/api/ask/stream", json={"question": "What is rate limiting?", "max_sources": 4}, headers=headers)
    events = [json.loads(line) for line in ask.text.splitlines() if line.strip()]
    assert events[-1]["type"] == "done"
    conv_id = events[0]["id"]

    conversations = await client.get("/api/conversations", headers=headers)
    items = conversations.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "What is rate limiting?"

    turns = await client.get(f"/api/conversations/{conv_id}", headers=headers)
    assert turns.json()["items"][0]["question"] == "What is rate limiting?"

    login = await client.post("/api/auth/login", json=VALID)
    assert login.status_code == 200
    again = await client.get("/api/conversations", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert again.json()["items"][0]["title"] == "What is rate limiting?"
