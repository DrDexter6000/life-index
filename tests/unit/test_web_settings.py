from unittest.mock import AsyncMock, patch


def test_submit_settings_test_only_does_not_persist_config() -> None:
    from fastapi.testclient import TestClient
    from web.app import create_app

    with patch("web.routes.settings.save_llm_config") as mock_save_llm:
        with patch("web.routes.settings.save_default_location") as mock_save_location:
            with patch(
                "web.routes.settings._check_llm_connectivity",
                new=AsyncMock(return_value=(True, "连接成功")),
            ):
                client = TestClient(create_app())
                response = client.post(
                    "/settings",
                    data={
                        "api_key": "sk-test",
                        "base_url": "https://api.openai.com/v1",
                        "base_url_preset": "https://api.openai.com/v1",
                        "model": "gpt-4o-mini",
                        "default_location": "Lagos, Nigeria",
                        "test_only": "1",
                    },
                )

    assert response.status_code == 200
    assert "测试完成" in response.text
    mock_save_llm.assert_not_called()
    mock_save_location.assert_not_called()


def test_submit_weights_persists_search_weights() -> None:
    from fastapi.testclient import TestClient
    from web.app import create_app

    with patch("web.routes.settings.save_search_weights") as mock_save_weights:
        client = TestClient(create_app())
        response = client.post(
            "/settings/weights",
            data={
                "fts_weight": "0.65",
                "semantic_weight": "0.35",
            },
        )

    assert response.status_code == 200
    # weight_save_message is set in route context but no longer rendered
    # by the redesigned settings template; verify save logic was called
    mock_save_weights.assert_called_once_with(0.65, 0.35)
