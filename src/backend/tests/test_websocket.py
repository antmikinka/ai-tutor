import base64
import io

from PIL import Image


def _connect(client, client_id="ws-test"):
    ws = client.websocket_connect(f"/ws/{client_id}")
    ws.__enter__()
    hello = ws.receive_json()
    assert hello["type"] == "connected"
    assert hello["capabilities"]["symbolic_solver"] is True
    return ws


def test_ping_pong(client):
    with client.websocket_connect("/ws/ping") as ws:
        ws.receive_json()
        ws.send_json({"type": "ping", "request_id": "p1"})
        pong = ws.receive_json()
        assert pong["type"] == "pong" and pong["request_id"] == "p1"


def test_math_input_roundtrip(client):
    with client.websocket_connect("/ws/math") as ws:
        ws.receive_json()
        ws.send_json({"type": "math_input", "content": "integrate x^2 from 0 to 3", "request_id": "r1"})
        msg = ws.receive_json()
        assert msg["type"] == "math_solution"
        assert msg["request_id"] == "r1"
        assert msg["solution"]["solution"] == "9"
        assert msg["solution"]["steps"]


def test_verify_message(client):
    with client.websocket_connect("/ws/verify") as ws:
        ws.receive_json()
        ws.send_json({"type": "verify", "problem": "solve 2x = 8", "solution": "x = 4"})
        msg = ws.receive_json()
        assert msg["type"] == "verification"
        assert msg["data"]["is_correct"] is True


def test_drawing_message_accepts_object_payload(client):
    image = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    with client.websocket_connect("/ws/draw") as ws:
        ws.receive_json()
        ws.send_json({"type": "drawing", "data": {"image": data_url, "objects": []}})
        msg = ws.receive_json()
        assert msg["type"] == "drawing_analysis"
        assert msg["data"]["available"] is False
        assert msg["data"]["image_analysis"]["is_blank"] is True


def test_invalid_messages_do_not_kill_connection(client):
    with client.websocket_connect("/ws/bad") as ws:
        ws.receive_json()
        ws.send_text("not json")
        assert ws.receive_json()["code"] == "INVALID_JSON"
        ws.send_json({"type": "bogus"})
        assert ws.receive_json()["code"] == "INVALID_MESSAGE"
        ws.send_json({"type": "math_input"})  # missing content
        assert ws.receive_json()["code"] == "INVALID_MESSAGE"
        ws.send_json({"type": "ping"})
        assert ws.receive_json()["type"] == "pong"


def test_audio_message_reports_unavailable(client):
    with client.websocket_connect("/ws/audio") as ws:
        ws.receive_json()
        ws.send_json({"type": "audio", "data": base64.b64encode(b"\x00\x01").decode()})
        msg = ws.receive_json()
        assert msg["type"] == "audio_transcription"
        assert msg["available"] is False


def test_connection_count_tracks_clients(client):
    with client.websocket_connect("/ws/a") as a:
        a.receive_json()
        with client.websocket_connect("/ws/b") as b:
            b.receive_json()
            assert client.get("/health").json()["websocket_connections"] == 2
    assert client.get("/health").json()["websocket_connections"] == 0
