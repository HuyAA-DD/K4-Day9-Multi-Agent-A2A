# Runbook

## 1. Cài runtime

Dùng Python 3.11 trở lên:

```powershell
py -3.11 -m pip install -r requirements.txt
py -3.11 -m pip install -e . --no-deps
```

Runtime production dùng OpenAI Python SDK và model cố định `gpt-4o-mini`.

## 2. Cấu hình

Copy `.env.example` thành `.env`, sau đó điền khóa thật ở máy chạy:

```dotenv
OPENAI_API_KEY=<your-key>
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_TIMEOUT_SECONDS=60
```

Không commit `.env`. `OPENAI_BASE_URL` và `OPENAI_TIMEOUT_SECONDS` là tùy chọn; các giá trị
trên là mặc định.

## 3. Kiểm thử offline

```powershell
py -3.11 -m ruff check src tests
py -3.11 -m pytest -q
```

Bộ test dùng scripted model, không gọi API. File `tests/test_all_cases.py` tạo đúng 50 test
end-to-end độc lập, tương ứng `EC_001` đến `EC_050`:

```powershell
py -3.11 -m pytest tests/test_all_cases.py -q
```

## 4. Chạy một case thật

```powershell
py -3.11 -m ecommerce_dispute.main --case EC_001
```

Thêm `--no-write` để chạy đầy đủ DAG và validation nhưng không thay đổi `output/`.
Lưu ý: trace và metadata của lượt chạy vẫn được tạo mới.

## 5. Chạy toàn bộ 50 case thật

```powershell
py -3.11 -m ecommerce_dispute.main --all
```

Lệnh này gọi OpenAI API và gửi các facts rút gọn của từng case cho model. CLI báo
`[case hiện tại/tổng]`, trạng thái và lỗi nếu có. Mỗi run tạo mới `logging/trace.jsonl`;
output chỉ được ghi sau khi mechanical gates và Verifier đều pass.

Đóng gói submission sau khi xác minh đủ 50 JSON:

```powershell
Compress-Archive -Path output\EC_*.json -DestinationPath output.zip -Force
```

Zip phải chứa trực tiếp `EC_001.json` đến `EC_050.json`, không chứa thư mục cha hoặc file lạ.

## 6. Privacy và xử lý lỗi

- Production inference gọi OpenAI API; cần phê duyệt việc gửi facts của case ra dịch vụ ngoài
  nếu dữ liệu thuộc phạm vi nhạy cảm.
- Code không ghi API key, system prompt đầy đủ hoặc raw CSV row vào trace.
- Nếu thiếu khóa, CLI báo `OPENAI_API_KEY is missing from the environment`.
- Nếu gặp lỗi kết nối, kiểm tra proxy/firewall, `OPENAI_BASE_URL` và quyền truy cập mạng.
- Mỗi model decision được retry tối đa ba lần; case vẫn fail nếu hết số lần retry.
