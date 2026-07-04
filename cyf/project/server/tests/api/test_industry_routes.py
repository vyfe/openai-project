def test_industry_boards(auth_client):
    resp = auth_client.get("/never_guess_my_usage/quant/industry/boards")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert {item["board_key"] for item in data["data"]} >= {"tungsten", "pcb_drill"}


def test_industry_dashboard_empty(auth_client):
    resp = auth_client.get("/never_guess_my_usage/quant/industry/dashboard", params={"board_key": "tungsten"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["data"]["board"]["board_key"] == "tungsten"
    assert "latest_cards" in data["data"]
