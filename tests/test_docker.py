"""Running Mortal Ascent in Docker (docs/docker.md): the health check page and what stays out of the image."""
import os

from fastapi.testclient import TestClient

from web import app as web_app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_health_check_answers_at_any_address_without_login(tmp_path):
    settings = web_app.Settings(client_id="cid", client_secret="secret", db_path=str(tmp_path / "ma.db"),
                                session_secret="test")
    c = TestClient(web_app.create_app(settings), base_url="http://127.0.0.1:8000", follow_redirects=False)
    r = c.get("/healthz")
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert c.get("/").status_code == 303          # the home page bounces to the official address; healthz must not


def test_secrets_and_the_database_never_go_into_the_image():
    with open(os.path.join(ROOT, ".dockerignore")) as f:
        ignored = {line.strip() for line in f if line.strip() and not line.startswith("#")}
    for must in (".env", "*.db", "*.db-wal", "data/", ".git/"):
        assert must in ignored


def test_the_box_keeps_the_database_outside_and_runs_as_an_ordinary_user():
    with open(os.path.join(ROOT, "Dockerfile")) as f:
        text = f.read()
    assert "MORTAL_DB_PATH=/data/mortal_ascent.db" in text and 'VOLUME ["/data"]' in text
    assert "USER game" in text and "/healthz" in text
    assert "COPY .env" not in text
