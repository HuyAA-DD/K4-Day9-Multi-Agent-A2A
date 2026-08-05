from ecommerce_dispute.config import (
    MODEL_FILE,
    MODEL_NAME,
    MODEL_PARAMETER_SIZE,
    MODEL_QUANTIZATION,
    Settings,
)


def test_model_runtime_is_fixed_to_cached_local_qwen(monkeypatch) -> None:
    monkeypatch.delenv("MODEL_GPU_LAYERS", raising=False)

    settings = Settings.from_environment()

    assert MODEL_NAME == "Qwen/Qwen3-1.7B-GGUF"
    assert MODEL_FILE == "Qwen3-1.7B-Q8_0.gguf"
    assert MODEL_PARAMETER_SIZE == "1.7B"
    assert MODEL_QUANTIZATION == "Q8_0"
    assert settings.model_gpu_layers == 0
    assert "api_key" not in Settings.__dataclass_fields__
    assert "base_url" not in Settings.__dataclass_fields__
