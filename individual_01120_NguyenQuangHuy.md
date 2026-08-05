# BÁO CÁO CÁ NHÂN — DAY 9: MULTI-AGENT A2A

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Quang Huy |
| MSSV (5 số cuối) | 01120 |
| Khóa/Lớp | K4 |
| Vai trò chính | Thiết kế và triển khai Supervisor DAG; tích hợp, thử nghiệm model và hoàn thiện pipeline sinh output |
| Ngày hoàn thành báo cáo | 05/08/2026 |

## 2. Tổng quan phần việc đã thực hiện

Trong bài lab này, tôi phụ trách phần lớn quá trình xây dựng pipeline giải quyết khiếu nại thương mại điện tử từ đầu vào đến output. Công việc không chỉ dừng ở việc tạo nhiều lớp mang tên “agent”, mà bao gồm cả luồng điều phối, hợp đồng dữ liệu giữa các thành phần, truy xuất dữ liệu Olist, tính toán, gọi model, kiểm tra kết quả và lưu trace phục vụ audit.

Các mốc công việc chính có thể đối chiếu trong lịch sử Git:

| Mốc | Nội dung |
| --- | --- |
| `2e95dba` — `upload input` | Đưa đủ 50 case `EC_001` đến `EC_050` vào thư mục `input/`. |
| `5c11aa3` — `supervisor dag` | Xây dựng cấu trúc Supervisor DAG ban đầu, các agent chuyên môn, schema, data repository, policy, validator, prompt và tài liệu kiến trúc. |
| `c1f1b82` — `update requirements.txt` | Bổ sung các dependency cần cho runtime và kiểm thử. |
| `ba56d9e` — `change model` | Chuyển hướng model, hoàn thiện runtime chạy model, sinh output, trace, metadata, runbook và các bài test tích hợp. |
| Worktree hiện tại | Refactor kiến trúc để giảm phụ thuộc rule-based: tách worker xác định khỏi agent suy luận, bổ sung Independent Evaluator, Comparator, Adjudicator tùy chọn, validation và namespace theo từng run. |

### Các hạng mục cụ thể

- Thiết kế luồng Supervisor/DAG và state của một case từ lúc nhận input, điều tra dữ liệu, áp policy, kiểm tra đến khi ghi output.
- Xây dựng các vai trò Customer, Order & Product, Payment, Delivery, Policy và Verifier trong phiên bản đầu.
- Xây dựng repository đọc dữ liệu Olist, các tool truy cập có giới hạn, phép tính tiền, giao hàng và seller handoff.
- Tạo Pydantic schema cho input, handoff, facts, policy decision, verification report và output cuối.
- Viết prompt riêng cho các vai trò có sử dụng model và ràng buộc structured JSON output.
- Thêm retry, trace JSONL, metadata model/runtime, output writer và hướng dẫn chạy trong `RUNBOOK.md`.
- Chạy thử nhiều hướng model, phân tích lỗi giữa Policy Agent và Verifier, sau đó thay đổi lại kiến trúc.
- Bổ sung unit, contract, failure, integration và golden test cho toàn bộ 50 case.

## 3. Luồng kỹ thuật tôi đã triển khai

Pipeline hiện tại hoạt động theo luồng sau:

1. Đọc và validate `input/EC_XXX.json`.
2. Customer Facts Worker và Order & Product Facts Worker truy xuất dữ liệu song song.
3. Sau khi có thông tin đơn hàng, Payment Reconciliation Worker và Delivery Analysis Worker tiếp tục chạy song song.
4. Các handoff được validate và rút gọn thành `ValidatedPolicyFacts`.
5. Policy Agent và Independent Policy Evaluator nhận cùng facts nhưng dùng prompt/request độc lập để sinh hai quyết định có cấu trúc.
6. Code dựng output từ facts và quyết định của Policy Agent, sau đó kiểm tra schema, source grounding, số tiền, ID và các invariant liên trường.
7. Comparator so sánh hai quyết định. Nếu bất đồng, hai agent được chạy lại trong giới hạn retry; nếu vẫn không thống nhất thì case chuyển sang `needs_review` hoặc Adjudicator nếu được cấu hình.
8. Chỉ case vượt qua toàn bộ gate mới được ghi vào `output/<run_id>/`; trạng thái từng case được lưu trong manifest và trace.

Tôi chủ động tách hai loại công việc:

- Phần xác định bằng code: đọc/join dữ liệu, cộng tiền, tính thời gian, kiểm tra schema, ID và nguồn dữ liệu, quản lý state, retry và ghi file.
- Phần cần suy luận bằng model: chọn primary/secondary issue, root cause, bên chịu trách nhiệm, refund và resolution action theo `EC_POLICY_V2`.

## 4. Quá trình lựa chọn và thử model

Việc chọn model là khó khăn lớn nhất của bài vì model vừa phải tuân thủ giới hạn tối đa 10B tham số, vừa phải đủ tốt để hiểu policy, giữ đúng thứ tự ưu tiên và trả JSON đúng schema.

| Model/hướng thử | Mục tiêu và lý do chọn | Kết quả thực tế | Kết luận |
| --- | --- | --- | --- |
| `Qwen/Qwen3.5-9B` | Lựa chọn ban đầu vì kích thước khai báo 9B, sát giới hạn 10B và dự kiến chạy qua endpoint tương thích OpenAI. | Model xuất hiện trong cấu hình và kiến trúc của commit `5c11aa3`, nhưng phiên bản này chủ yếu mới là scaffold; repo không có trace chứng minh một lượt chạy hoàn chỉnh bằng model này. | Phù hợp trên lý thuyết nhưng chưa có runtime ổn định để xác minh. |
| `Qwen/Qwen3-1.7B-GGUF`, file `Qwen3-1.7B-Q8_0.gguf` | Chuyển sang model local nhỏ để chắc chắn dưới 10B, chạy offline bằng llama.cpp và không phụ thuộc API key. | Có trace chạy thật case `EC_001`. Model hoàn thành các handoff nhưng Policy Agent chọn `valid_split_payment`, còn Verifier chọn `unsupported_late_claim`; sau retry case vẫn thất bại, kết quả 0/1. | Chạy được trên máy local nhưng chất lượng suy luận policy và độ ổn định giữa các vai trò chưa đủ. |
| `gpt-4o-mini` | Dùng structured output ổn định hơn, tốc độ tốt hơn và giảm lỗi JSON/semantic so với model local 1.7B. | Snapshot thực tế trong một run là `gpt-4o-mini-2024-07-18`. Một run đầy đủ hiện tại đạt 1/50; run sau đạt 0/50 do lỗi kết nối OpenAI. Một trace cũ hơn chạy được đến lúc bắt đầu `EC_042` nhưng không có sự kiện `run_completed`. | Chất lượng phản hồi tốt hơn, nhưng kết quả hiện chưa ổn định vì validator/prompt và kết nối. Ngoài ra số tham số chính thức không được công bố, nên chưa có bằng chứng chắc chắn để đối chiếu điều kiện ≤10B của đề. |

### Những khó khăn chính khi chọn model

1. **Giới hạn ≤10B và bằng chứng về số tham số:** model local có thông tin kích thước rõ ràng nhưng chất lượng thấp; model API tốt hơn lại không công bố số tham số chính thức.
2. **Giới hạn phần cứng:** model local phải chạy CPU/llama.cpp. Model 1.7B đủ nhẹ nhưng suy luận policy chưa ổn định; model gần 9B cần nhiều RAM và thời gian hơn.
3. **Structured output:** mỗi agent phải trả đúng JSON Schema. Chỉ cần sai enum, thiếu field, thêm text hoặc chọn giá trị không có trong facts là cả case phải retry hoặc fail.
4. **Tính nhất quán giữa các vai trò:** Policy Agent và Verifier/Evaluator có thể đọc cùng facts nhưng chọn hai policy khác nhau. Model nhỏ đặc biệt dễ không giữ đúng priority của `EC_POLICY_V2`.
5. **Chi phí và độ trễ:** kiến trúc ban đầu gọi model ở quá nhiều bước. Với 50 case và nhiều agent, số request lớn, runtime dài và dễ gặp rate limit hoặc lỗi kết nối.
6. **Ranh giới giữa validation và rule-based:** code cần kiểm tra tính đúng của output nhưng không được thay model quyết định policy. Nếu validator chứa cả bảng đáp án và tự chọn kết quả, hệ thống vẫn bị xem là rule-based dù bên ngoài có nhiều agent.

## 5. Lần nộp duy nhất có điểm và lỗi rule-based

Lần nộp duy nhất mà hệ thống chấm trả về điểm là bộ 50 output được sinh trong giai đoạn kiến trúc đầu. Tuy nhiên, lần này bị đánh dấu **rule-based**, vì vậy kết quả đó không thể hiện đúng yêu cầu trọng tâm của bài về multi-agent dùng model để đưa ra quyết định.

Nguyên nhân gốc có thể xác minh trực tiếp trong commit `5c11aa3`:

- Tồn tại `src/ecommerce_dispute/policies/ec_policy_v2.py`, triển khai decision table bằng code.
- `Policy Agent` gọi tool `evaluate_ec_policy_v2` thay vì tự suy luận và tạo quyết định policy.
- `architecture.md` tại thời điểm đó mô tả rõ `Deterministic Policy Engine` và các rule first-match.
- Model chủ yếu tham gia điều phối/handoff, trong khi quyết định quan trọng nhất đã được code xác định trước.

Vì vậy, dù output có thể đúng và hệ thống có Supervisor cùng nhiều agent, grader vẫn có cơ sở xem đây là một policy engine rule-based được bọc bởi kiến trúc agent.

Sau lỗi này, tôi đã thay đổi hướng triển khai:

- Xóa policy engine production tự chọn đáp án.
- Để Policy Agent sinh trực tiếp structured decision từ facts và policy prompt.
- Thêm Independent Evaluator không được nhìn draft của Policy Agent.
- Dùng Comparator để phát hiện bất đồng thay vì ép model theo một đáp án được code chọn sẵn.
- Giữ deterministic code cho các thao tác cơ học và validation.

Tuy nhiên, phiên bản hiện tại vẫn còn rủi ro bị đánh giá rule-based vì `validation/policy.py` đang chứa mapping invariant khá chi tiết cho từng primary issue. Dù hàm này chỉ kiểm tra lựa chọn của model và không trực tiếp chọn primary issue, ranh giới này cần tiếp tục được làm gọn và giải thích rõ trước lần nộp tiếp theo.

Repo không lưu ảnh hoặc JSON phản hồi từ leaderboard, nên tôi không ghi một con số điểm cụ thể để tránh báo cáo sai bằng chứng. Thông tin chắc chắn có thể xác nhận là: đây là lần duy nhất có điểm và lần đó bị gắn lỗi rule-based.

## 6. Kết quả hiện tại

| Hạng mục | Kết quả hiện tại | Bằng chứng |
| --- | --- | --- |
| Ruff/static checks | Pass | `.venv\Scripts\python.exe -m ruff check src tests` trả về `All checks passed!`. |
| Test suite offline | 12 test pass | `.venv\Scripts\python.exe -m pytest -q` trả về `12 passed in 4.26s`. |
| Golden flow 50 case | Pass bằng scripted oracle | `tests/golden/test_all_cases.py` chạy đủ `EC_001` đến `EC_050`, nhưng không gọi model thật. |
| Run thật `run-full-001` | 1/50 thành công, 49/50 thất bại | `logging/run-full-001/metadata.json` và `manifest.json`; case thành công là `EC_038`. |
| Run thật `run-openai-20260805-001` | 0/50 thành công | Trace ghi lỗi kết nối OpenAI sau ba lần retry ở các model call. |
| Bộ output có thể nộp ngay | Chưa đạt | Chưa có một run model thật, cùng một phiên bản code, tạo đủ 50 output đã pass toàn bộ gate. |

Điểm quan trọng là kết quả test offline chỉ chứng minh DAG, schema, validator, retry và output writer hoạt động khi model trả đáp án chuẩn. Nó không chứng minh `gpt-4o-mini` hoặc model local hiện có thể tự giải đúng cả 50 case. Do đó tôi không xem 50 JSON cũ ở thư mục output là bằng chứng cho một run hiện tại thành công.

Hai nhóm lỗi chính của run thật hiện tại là:

- **Lỗi semantic/validator:** model chọn primary issue không đủ điều kiện hoặc trả các field phụ không đúng mapping rất chặt của validator; run `run-full-001` chỉ ghi được `EC_038`.
- **Lỗi hạ tầng:** run tiếp theo không gọi được OpenAI API và kết thúc 0/50 do `Connection error`.

## 7. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** kiến trúc cũ có output đúng hơn nhờ deterministic policy engine nhưng bị lỗi rule-based.
- **Các phương án cân nhắc:** giữ policy engine để tối đa độ chính xác; dùng hoàn toàn model ở mọi agent; hoặc tách data worker xác định khỏi các agent thực sự cần suy luận.
- **Phương án chọn:** dùng deterministic worker cho dữ liệu/phép tính/orchestration, còn Policy Agent và Independent Evaluator chịu trách nhiệm quyết định semantic.
- **Lý do:** cách này giảm số model call, giảm hallucination ở dữ liệu và vẫn giữ phần quyết định nghiệp vụ ở model.
- **Trade-off:** kết quả live khó ổn định hơn policy engine và cần prompt/validator tốt hơn; đổi lại kiến trúc phản ánh đúng mục tiêu multi-agent hơn và audit được từng quyết định.

## 8. Cách xác minh

```powershell
# Kiểm tra code
.venv\Scripts\python.exe -m ruff check src tests

# Chạy toàn bộ test offline
.venv\Scripts\python.exe -m pytest -q

# Chạy một case với model thật
.venv\Scripts\python.exe -m ecommerce_dispute.main --case EC_001 --no-write

# Xem kết quả run thật gần nhất
Get-Content logging\run-full-001\metadata.json
Get-Content logging\run-full-001\manifest.json
Get-Content logging\run-openai-20260805-001\trace.jsonl -Tail 20

# Kiểm tra các mốc công việc cá nhân
git show --stat 2e95dba
git show --stat 5c11aa3
git show --stat c1f1b82
git show --stat ba56d9e
```

## 9. Điều học được và bước tiếp theo

Qua bài này, tôi rút ra rằng việc “có nhiều agent” không đồng nghĩa với một hệ thống multi-agent đúng nghĩa. Cần xác định rõ agent nào thực sự đưa ra quyết định bằng model, agent nào chỉ là worker/tool, dữ liệu được handoff ra sao và ai có quyền ghi output.

Các bước tiếp theo để có một submission đáng tin cậy:

1. Chọn model có tài liệu chính thức chứng minh không vượt 10B và đủ khả năng structured reasoning.
2. Giảm validator từ bảng đáp án chi tiết xuống các kiểm tra grounding/arithmetic/invariant tối thiểu, tránh tiếp tục bị xem là policy engine ẩn.
3. Cải thiện prompt bằng cách mô tả rõ priority và ràng buộc field, sau đó đánh giá trên một tập case nhỏ trước khi chạy đủ 50 case.
4. Tách nguyên nhân lỗi model khỏi lỗi kết nối, cấu hình timeout/concurrency phù hợp và chỉ tạo zip từ một run hoàn chỉnh.
5. Lưu lại phản hồi chấm, điểm và submission ID thành artifact không chứa secret để báo cáo lần sau có bằng chứng đầy đủ.

## 10. Cam kết cá nhân

- [x] Báo cáo phản ánh đúng phần việc có thể đối chiếu từ lịch sử Git và artifact trong repo.
- [x] Không ghi “đã chạy thành công” cho lượt chạy model thật chưa hoàn thành.
- [x] Phân biệt rõ test offline bằng scripted oracle với kết quả inference thật.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Các hạn chế và lỗi hiện tại được ghi rõ, không che giấu kết quả thất bại.

**Người báo cáo:** Nguyễn Quang Huy  
**Ngày xác nhận:** 05/08/2026
