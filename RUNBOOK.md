# Runbook

## 1. Cài runtime

Dùng Python 3.11 trở lên:

```powershell
py -3.11 -m pip install -r requirements.txt
py -3.11 -m pip install -e . --no-deps
```

`requirements.txt` dùng CPU wheel index của `llama-cpp-python`. Tải model GGUF chính thức một lần:

```powershell
hf download Qwen/Qwen3-1.7B-GGUF Qwen3-1.7B-Q8_0.gguf
```

Khi chạy, model chỉ được mở từ cache bằng `local_files_only=True`; không cần API key.

## 2. Cấu hình

Có thể copy `.env.example` thành `.env`:

```dotenv
MODEL_GPU_LAYERS=0
MODEL_CONTEXT_TOKENS=4096
MODEL_THREADS=6
```

`MODEL_GPU_LAYERS=0` là CPU. Chỉ đặt giá trị lớn hơn 0 khi `llama-cpp-python` đã được cài bằng CUDA wheel và máy có CUDA runtime tương thích.

## 3. Kiểm thử

```powershell
py -3.11 -m ruff check src tests
py -3.11 -m pytest -q
```

Unit/integration tests dùng scripted local model, không tải model thật và không có chế độ deterministic production.

## 4. Chạy một case

```powershell
py -3.11 -m ecommerce_dispute.main --case EC_001
```

Thêm `--no-write` để chạy đầy đủ DAG và validation nhưng không thay đổi `output/`.

## 5. Chạy toàn bộ 50 case

```powershell
py -3.11 -m ecommerce_dispute.main --all
```

CLI báo `[case hiện tại/tổng]`, trạng thái và lỗi nếu có. Mỗi run tạo mới `logging/trace.jsonl`; output chỉ được ghi sau khi mechanical gates và Verifier đều pass.

Đóng gói submission sau khi xác minh đủ 50 JSON:

```powershell
Compress-Archive -Path output\EC_*.json -DestinationPath output.zip -Force
```

Zip phải chứa trực tiếp `EC_001.json` đến `EC_050.json`, không chứa thư mục cha hoặc file lạ.

## 6. Privacy và xử lý lỗi

Inference chạy local qua llama.cpp. Code không gọi endpoint và không đọc `OPENAI_API_KEY`. Trace không ghi prompt đầy đủ, raw CSV row hoặc secret.

Nếu báo model chưa có trong cache, chạy lại lệnh `hf download`. Nếu CUDA wheel không load được DLL, cài CPU wheel từ `requirements.txt` và giữ `MODEL_GPU_LAYERS=0`.
