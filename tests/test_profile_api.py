import io

from PIL import Image

from kara.avatars import get_avatar_store, reset_avatar_store


def _image_bytes(fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (0, 255, 163)).save(buf, format=fmt)
    return buf.getvalue()


class FakeAvatarStore:
    def __init__(self):
        self.uploads = []

    async def upload(self, key, data, content_type):
        self.uploads.append((key, data, content_type))

    async def signed_url(self, key):
        return f"https://cdn.example.test/{key}?sig=fake"


async def _register(client, email="karan@example.com"):
    res = await client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert res.status_code == 201
    return res.json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_register_returns_profile_fields(client):
    body = await _register(client)
    assert body["user"]["name"] is None
    assert body["user"]["avatar_url"] is None


async def test_patch_me_sets_and_strips_name(client):
    token = (await _register(client))["access_token"]
    res = await client.patch("/api/auth/me", json={"name": "  Karan  "}, headers=_auth(token))
    assert res.status_code == 200
    assert res.json()["name"] == "Karan"

    me = await client.get("/api/auth/me", headers=_auth(token))
    assert me.json()["name"] == "Karan"


async def test_patch_me_requires_auth(client):
    res = await client.patch("/api/auth/me", json={"name": "Karan"})
    assert res.status_code == 401


async def test_patch_me_rejects_blank_name(client):
    token = (await _register(client))["access_token"]
    res = await client.patch("/api/auth/me", json={"name": "   "}, headers=_auth(token))
    assert res.status_code == 422


async def test_patch_me_rejects_long_name(client):
    token = (await _register(client))["access_token"]
    res = await client.patch("/api/auth/me", json={"name": "x" * 101}, headers=_auth(token))
    assert res.status_code == 422


async def test_avatar_upload_and_serve(client):
    token = (await _register(client))["access_token"]
    fake = FakeAvatarStore()
    client.app.dependency_overrides[get_avatar_store] = lambda: fake

    res = await client.post(
        "/api/auth/avatar",
        files={"file": ("avatar.png", _image_bytes(), "image/png")},
        headers=_auth(token),
    )
    assert res.status_code == 200
    body = res.json()
    user_id = body["id"]
    assert body["avatar_url"] == f"/api/avatars/{user_id}"

    assert len(fake.uploads) == 1
    key, data, content_type = fake.uploads[0]
    assert key == f"avatars/{user_id}.jpg"
    assert content_type == "image/jpeg"
    assert data.startswith(b"\xff\xd8")

    served = await client.get(f"/api/avatars/{user_id}")
    assert served.status_code == 302
    assert served.headers["location"] == f"https://cdn.example.test/{key}?sig=fake"
    assert "max-age" in served.headers.get("cache-control", "")


async def test_avatar_requires_auth(client):
    client.app.dependency_overrides[get_avatar_store] = lambda: FakeAvatarStore()
    res = await client.post(
        "/api/auth/avatar",
        files={"file": ("avatar.png", _image_bytes(), "image/png")},
    )
    assert res.status_code == 401


async def test_avatar_rejects_wrong_content_type(client):
    token = (await _register(client))["access_token"]
    client.app.dependency_overrides[get_avatar_store] = lambda: FakeAvatarStore()
    res = await client.post(
        "/api/auth/avatar",
        files={"file": ("avatar.gif", b"GIF89a", "image/gif")},
        headers=_auth(token),
    )
    assert res.status_code == 415


async def test_avatar_rejects_oversize(client):
    token = (await _register(client))["access_token"]
    client.app.dependency_overrides[get_avatar_store] = lambda: FakeAvatarStore()
    res = await client.post(
        "/api/auth/avatar",
        files={"file": ("big.jpg", b"x" * (2 * 1024 * 1024 + 1), "image/jpeg")},
        headers=_auth(token),
    )
    assert res.status_code == 413


async def test_avatar_rejects_unreadable_image(client):
    token = (await _register(client))["access_token"]
    client.app.dependency_overrides[get_avatar_store] = lambda: FakeAvatarStore()
    res = await client.post(
        "/api/auth/avatar",
        files={"file": ("fake.jpg", b"definitely not an image", "image/jpeg")},
        headers=_auth(token),
    )
    assert res.status_code == 400


async def test_avatar_503_without_store(client):
    reset_avatar_store()
    token = (await _register(client))["access_token"]
    res = await client.post(
        "/api/auth/avatar",
        files={"file": ("avatar.png", _image_bytes(), "image/png")},
        headers=_auth(token),
    )
    assert res.status_code == 503


async def test_get_avatar_404_for_unknown_user(client):
    res = await client.get("/api/avatars/999999")
    assert res.status_code == 404


async def test_get_avatar_404_without_picture(client):
    token = (await _register(client))["access_token"]
    me = await client.get("/api/auth/me", headers=_auth(token))
    res = await client.get(f"/api/avatars/{me.json()['id']}")
    assert res.status_code == 404
