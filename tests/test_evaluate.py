import io

from fastapi.testclient import TestClient
from PIL import Image

from main import app


def test_evaluate_quality_endpoint_handles_blank_png():
    client = TestClient(app)
    image = Image.new("RGB", (900, 1200), color="white")
    file_buffer = io.BytesIO()
    image.save(file_buffer, format="PNG")
    file_buffer.seek(0)

    response = client.post(
        "/evaluate-quality",
        files={"file": ("blank.png", file_buffer, "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "pages" in payload
    assert len(payload["pages"]) == 1
    
    page = payload["pages"][0]
    assert page["page_number"] == 1
    assert "quality_score" in page
    assert 0.0 <= page["quality_score"] <= 1.0
    assert page["quality_checks"]["Blank page"] == "YES"
