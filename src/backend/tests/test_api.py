import base64
import io

from PIL import Image, ImageDraw


def _png_b64(draw=None, size=(200, 100)) -> str:
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    if draw:
        draw(ImageDraw.Draw(image))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "healthy"
    assert body["services"]["ai_service"] is True
    assert body["services"]["model_service"] is True
    assert body["timestamp"].endswith("+00:00")


def test_root(client):
    assert client.get("/").json()["websocket"] == "/ws/{client_id}"


def test_solve_endpoint(client):
    r = client.post("/api/math/solve", json={"problem": "solve x^2 - 5x + 6 = 0"})
    assert r.status_code == 200
    body = r.json()
    assert body["solution"] == "x = 2 or x = 3"
    assert body["problem_type"] == "equation"
    assert body["metadata"]["model_used"] == "sympy"
    assert body["confidence"] > 0.9


def test_solve_rejects_empty(client):
    assert client.post("/api/math/solve", json={"problem": ""}).status_code == 422


def test_solve_unknown_input_is_honest(client):
    body = client.post("/api/math/solve", json={"problem": "tell me a joke about triangles"}).json()
    assert body["confidence"] == 0.0
    assert body["problem_type"] == "unknown"
    assert body["metadata"]["model_used"] == "none"


def test_verify_endpoint(client):
    body = client.post("/api/math/verify", json={"problem": "derivative of x^3", "solution": "3x^2"}).json()
    assert body["is_correct"] is True
    assert body["expected"] == "f'(x) = 3*x**2"


def test_batch_solve(client):
    body = client.post("/api/math/batch-solve", json={"problems": ["2+2", "factor x^2-1"]}).json()
    assert body["successful_solutions"] == 2


def test_history_and_statistics(client):
    client.delete("/api/math/history")
    client.post("/api/math/solve", json={"problem": "solve 2x = 8"})
    client.post("/api/math/solve", json={"problem": "derivative of x^5"})
    history = client.get("/api/math/history").json()
    assert history["total"] == 2
    assert history["history"][0]["problem"] == "derivative of x^5"  # newest first
    stats = client.get("/api/math/statistics").json()["statistics"]
    assert stats["total_problems_solved"] >= 2
    item_id = history["history"][0]["id"]
    assert client.delete(f"/api/math/history/{item_id}").status_code == 200
    assert client.delete(f"/api/math/history/{item_id}").status_code == 404


def test_problem_types(client):
    assert "derivative" in client.get("/api/math/problem-types").json()["problem_types"]


def test_analyze_drawing_blank_canvas(client):
    body = client.post("/api/math/analyze-drawing", json={"drawing_data": "data:image/png;base64," + _png_b64()}).json()
    assert body["available"] is False
    assert body["equations"] == []
    assert body["image_analysis"]["is_blank"] is True


def test_analyze_drawing_with_ink(client):
    body = client.post(
        "/api/drawing/process-drawing",
        json={"drawing_data": _png_b64(lambda d: d.line((10, 10, 150, 60), fill=(0, 0, 0, 255), width=4))},
    ).json()
    stats = body["processed_data"]["image_analysis"]
    assert stats["is_blank"] is False
    assert stats["components"] == 1
    assert stats["bounding_box"]["x"] >= 8


def test_analyze_drawing_bad_data(client):
    r = client.post("/api/drawing/process-drawing", json={"drawing_data": "not-an-image"})
    assert r.status_code == 400


def test_stroke_classification(client):
    import math

    line = {"points": [{"x": i, "y": 2 * i} for i in range(0, 100, 5)]}
    circle = {"points": [{"x": 50 + 40 * math.cos(t / 10), "y": 50 + 40 * math.sin(t / 10)} for t in range(0, 64)]}
    body = client.post("/api/drawing/analyze-strokes", json={"strokes": [line, circle]}).json()
    types = [s["type"] for s in body["recognized_shapes"]]
    assert types == ["line", "circle"]


def test_speech_to_text_reports_unavailable(client):
    body = client.post("/api/audio/speech-to-text", json={"audio_data": base64.b64encode(b"abc").decode()}).json()
    assert body["available"] is False
    assert body["text"] == ""


def test_text_to_speech_reports_unavailable(client):
    body = client.post("/api/audio/text-to-speech", json={"text": "hello"}).json()
    assert body["available"] is False
    assert body["audio_data"] is None


def test_models_listing_and_load_refusal(client):
    body = client.get("/api/models").json()
    names = {m["name"] for m in body["models"]}
    assert "Qwen3-Omni-30B-A3B-Thinking" in names
    r = client.post("/api/models/load/ai")
    assert r.status_code == 409  # ML stack not installed / not downloaded: refused, not faked
    assert client.get("/api/models/ai/status").json()["status"] in {"unavailable", "not_downloaded"}
    assert client.get("/api/models/nope/status").status_code == 404


def test_system_status_and_config(client):
    status = client.get("/api/system/status").json()
    assert status["services"]["ai_service"]["symbolic_engine"] == "sympy"
    config = client.get("/api/system/config").json()["config"]
    assert "secret_key" not in config
    assert config["ai_device"] == "cpu"


def test_system_logs_endpoint(client):
    body = client.get("/api/system/logs?limit=5").json()
    assert "logs" in body and "total_count" in body


def test_cors_allows_dev_origin(client):
    r = client.options(
        "/api/math/solve",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
