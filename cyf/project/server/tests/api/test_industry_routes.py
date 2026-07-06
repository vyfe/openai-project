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


def test_industry_board_save_appends_symbol(auth_client):
    boards_resp = auth_client.get("/never_guess_my_usage/quant/industry/boards")
    board = next(item for item in boards_resp.get_json()["data"] if item["board_key"] == "tungsten")
    original_symbols = board["symbols"]

    resp = auth_client.post(
        "/never_guess_my_usage/quant/industry/board/save",
        json={
            "board_key": board["board_key"],
            "name": board["name"],
            "description": board["description"],
            "keywords": board["keywords"],
            "symbols": [
                *original_symbols,
                {
                    "symbol": "600519.SH",
                    "name": "贵州茅台",
                    "role": "",
                    "weight": 1,
                    "status": "active",
                    "keywords": ["贵州茅台", "600519"],
                },
            ],
            "status": "active",
        },
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True

    updated_resp = auth_client.get("/never_guess_my_usage/quant/industry/boards")
    updated = next(item for item in updated_resp.get_json()["data"] if item["board_key"] == "tungsten")
    symbols = {item["symbol"] for item in updated["symbols"]}
    assert "000657.SZ" in symbols
    assert "600519.SH" in symbols
