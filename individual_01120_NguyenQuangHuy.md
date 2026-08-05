# BÁO CÁO CÁ NHÂN — DAY 9: MULTI-AGENT A2A

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Quang Huy |
| MSSV (5 số cuối) | 01120 |
| Khóa/Lớp | K4 |
| Vai trò chính | Thiết kế kiến trúc agent, xây dựng deterministic workflow, tích hợp model và hoàn thiện pipeline sinh output |
| Ngày cập nhật báo cáo | 05/08/2026 |

## 2. Tổng quan phần việc đã thực hiện

Trong bài lab này, tôi phụ trách phần lớn pipeline giải quyết khiếu nại thương mại điện tử từ đầu vào đến output. Công việc bao gồm thiết kế luồng điều phối, hợp đồng dữ liệu giữa các thành phần, truy xuất dữ liệu Olist, tính toán facts, gọi model, kiểm tra kết quả và lưu trace phục vụ audit.

Các mốc chính có thể đối chiếu trong lịch sử Git:

| Mốc | Nội dung |
| --- | --- |
| `2e95dba` — `upload input` | Đưa đủ 50 case `EC_001` đến `EC_050` vào `input/`. |
| `5c11aa3` — `supervisor dag` | Xây dựng phiên bản Supervisor DAG ban đầu, schema, data repository, policy, validator, prompt và tài liệu kiến trúc. |
| `c1f1b82` — `update requirements.txt` | Bổ sung dependency cho runtime và kiểm thử. |
| `ba56d9e` — `change model` | Hoàn thiện runtime gọi model, output, trace, metadata, runbook và test tích hợp. |
| Worktree hiện tại | Loại bỏ production policy oracle, tách worker xác định khỏi agent suy luận, bổ sung Independent Evaluator, Comparator, Adjudicator tùy chọn và namespace theo từng run. |

Các hạng mục cụ thể:

- Xây dựng deterministic workflow để quản lý state, thứ tự chạy, retry, review và ghi output.
- Xây dựng các facts worker cho Customer, Order & Product, Payment và Delivery.
- Xây dựng repository đọc dữ liệu Olist và các phép tính tiền, thời gian giao hàng, seller handoff.
- Tạo Pydantic schema cho input, handoff, facts, policy decision, verification report và output cuối.
- Viết prompt riêng cho các vai trò dùng model, yêu cầu structured output đúng JSON Schema.
- Xây dựng Policy Agent, Independent Policy Evaluator và Adjudicator độc lập.
- Thêm trace JSONL, metadata model/runtime, manifest theo case và output writer.
- Bổ sung unit, contract, failure, integration và golden test cho 50 case.

## 3. Kiến trúc và luồng kỹ thuật hiện tại

Pipeline hiện tại hoạt động theo luồng sau:

1. Đọc và validate `input/EC_XXX.json`.
2. Customer Facts Worker và Order & Product Facts Worker truy xuất dữ liệu song song.
3. Payment Reconciliation Worker và Delivery Analysis Worker tiếp tục chạy song song sau khi có thông tin đơn hàng.
4. Các handoff được validate và hợp nhất thành `ValidatedPolicyFacts`.
5. Policy Agent và Independent Policy Evaluator nhận cùng facts nhưng dùng request độc lập để sinh hai quyết định có cấu trúc.
6. Code dựng output từ facts và quyết định của model, sau đó chỉ kiểm tra schema, source grounding, định dạng tiền, ID và tính nhất quán liên trường ở mức tổng quát.
7. Comparator so sánh hai quyết định. Nếu bất đồng, hai agent được retry; nếu vẫn không thống nhất thì case chuyển sang `needs_review` hoặc được Adjudicator xử lý khi có cấu hình.
8. Chỉ output vượt qua toàn bộ gate mới được ghi vào `output/<run_id>/`; trạng thái từng case được lưu trong manifest và trace.

Ranh giới trách nhiệm được xác định rõ:

- Deterministic code chỉ làm công việc cơ học: đọc/join dữ liệu, tính toán facts, validate schema và grounding, quản lý state, retry, trace và ghi file.
- Model chịu trách nhiệm cho quyết định semantic: chọn primary/secondary issue, root cause, bên chịu trách nhiệm, trạng thái xử lý, refund và resolution action theo `EC_POLICY_V2`.
- Production code không còn decision table hoặc hàm ánh xạ primary issue sang một đáp án policy cố định.

## 4. Quá trình lựa chọn và thử model

| Model/hướng thử | Kết quả thực tế | Kết luận |
| --- | --- | --- |
| `Qwen/Qwen3.5-9B` | Có trong cấu hình/kiến trúc ban đầu nhưng repo không có trace chứng minh một lượt chạy hoàn chỉnh. | Phù hợp giới hạn kích thước trên lý thuyết nhưng chưa có runtime ổn định để xác minh. |
| `Qwen3-1.7B-Q8_0.gguf` | Chạy local được nhưng Policy Agent và Verifier bất đồng ngay ở case thử; chất lượng reasoning chưa đủ ổn định. | Đúng giới hạn dưới 10B nhưng không phù hợp để sinh bộ kết quả cuối. |
| `gpt-4o-mini-2024-07-18` | Lượt non-rule-based chính xử lý trực tiếp 47/50 case; 3 case bất đồng được tách ra adjudicate và đều hoàn thành. | Structured output và tốc độ tốt, nhưng vẫn bỏ sót một số secondary issue/action. OpenAI không công bố số tham số nên không thể dùng model này làm bằng chứng chắc chắn cho điều kiện ≤10B. |
| `gpt-4o` cho Adjudicator | Giải quyết thành công ba case `EC_002`, `EC_005`, `EC_007` còn bất đồng. | Hữu ích ở nhánh review, nhưng cũng không có thông tin số tham số công khai. |

Khó khăn chính là cân bằng giữa chất lượng suy luận, structured output, độ trễ, chi phí và yêu cầu model không quá 10B. Model local có kích thước rõ ràng nhưng reasoning yếu hơn; model API ổn định hơn nhưng không có bằng chứng chính thức về số tham số. Ngoài ra, hai agent độc lập có thể đọc cùng facts nhưng đưa ra quyết định khác nhau, nên pipeline cần Comparator, retry và Adjudicator thay vì dùng code ép về một đáp án có sẵn.

## 5. Kết quả các lần nộp và vấn đề rule-based

### Lần nộp trước: 67.2893 điểm

Bộ output của kiến trúc cũ đạt **67.2893 điểm** nhưng bị đánh dấu **rule-based**. Nguyên nhân có thể xác minh trong phiên bản cũ:

- `src/ecommerce_dispute/policies/ec_policy_v2.py` triển khai decision table bằng code.
- Policy Agent gọi tool `evaluate_ec_policy_v2` thay vì tự sinh quyết định policy.
- Kiến trúc cũ mô tả `Deterministic Policy Engine` và các rule first-match.
- Model chủ yếu tham gia điều phối/handoff, còn quyết định nghiệp vụ quan trọng đã được code xác định trước.

Vì vậy, dù output có độ chính xác cao hơn và hệ thống có nhiều thành phần mang tên agent, grader vẫn có cơ sở coi đây là policy engine rule-based được bọc bởi kiến trúc agent.

### Lần nộp hiện tại: 66.5438 điểm

Bộ output mới đạt **66.5438 điểm**, thấp hơn lần trước **0.7455 điểm**. Bộ này được tạo từ code path hiện tại, sau khi production policy oracle và mapping đáp án theo từng primary issue đã được loại bỏ. Policy Agent, Independent Evaluator và Adjudicator sinh quyết định bằng model; code chỉ điều phối và kiểm tra tính hợp lệ tổng quát.

Phản hồi được cung cấp cho lần này mới chỉ có điểm số **66.5438**; repo chưa lưu artifact từ hệ thống chấm cho biết submission có còn bị gắn cờ rule-based hay không. Vì vậy báo cáo chỉ khẳng định kiến trúc/code path đã chuyển sang non-rule-based, không tự suy diễn trạng thái đánh giá của grader.

Khi so bộ non-rule-based với bộ output trước đó, có 25 case khác nhau, nhưng khác biệt chỉ nằm ở `secondary_issues` hoặc `resolution_actions`; primary issue, status và tổng refund không đổi. Đây là dấu hiệu cho thấy việc loại bỏ mapping cố định đã làm model bỏ sót một số chi tiết như `repeat_customer`, `split_payment`, `coordinate_multi_seller_case` hoặc `verify_payment_allocation`. Tôi đánh giá đây là nguyên nhân có khả năng góp phần làm điểm giảm, nhưng không thể khẳng định là toàn bộ nguyên nhân khi chưa có breakdown chính thức từ grader.

## 6. Kết quả chạy và kiểm thử hiện tại

| Hạng mục | Kết quả | Bằng chứng |
| --- | --- | --- |
| Điểm submission mới nhất | **66.5438 điểm** | Kết quả nhận trực tiếp từ hệ thống chấm; repo chưa có response artifact của grader. |
| Điểm submission trước | **67.2893 điểm**, bị đánh dấu **rule-based** | Kết quả lịch sử do người thực hiện ghi nhận. |
| Ruff/static checks | Pass | `python -m ruff check src tests` trả về `All checks passed!`. |
| Test suite offline | **14 test pass** | `python -m pytest -q`. |
| Run chính `run-openai-nonrule-20260805-001` | **47 success, 0 failed, 3 needs_review** | `logging/run-openai-nonrule-20260805-001/metadata.json` và `manifest.json`. |
| Ba run adjudication | **3/3 success** | Các run riêng cho `EC_002`, `EC_005`, `EC_007`. |
| Bộ output tổng hợp cuối | **50/50 file đúng Pydantic schema** | `output/run-openai-nonrule-20260805-final/`. |
| File nộp | `output-run-openai-nonrule-20260805-final.zip` | SHA-256: `287725D4E1453AF7FEE8015FF03B44746B70B5F3DDE6818735E32E8A48B622C4`. |

Bộ cuối gồm 47 kết quả được hai agent đồng thuận trực tiếp và 3 kết quả qua nhánh adjudication. Đây là bộ output model-backed hoàn chỉnh, không phải kết quả của scripted oracle. Việc tổng hợp từ nhiều run được ghi rõ để không trình bày sai rằng cả 50 case hoàn thành trong một run duy nhất.

## 7. Quyết định kỹ thuật quan trọng

- **Bối cảnh:** kiến trúc cũ cho output đúng hơn nhờ deterministic policy engine nhưng vi phạm mục tiêu non-rule-based.
- **Phương án chọn:** dùng deterministic worker cho dữ liệu, phép tính và orchestration; để Policy Agent, Independent Evaluator và Adjudicator chịu trách nhiệm cho quyết định semantic.
- **Lý do:** giảm hallucination ở dữ liệu và giảm số model call không cần thiết, nhưng vẫn giữ quyết định nghiệp vụ ở model.
- **Trade-off:** output kém ổn định hơn policy engine và cần prompt/evaluation tốt hơn; đổi lại kiến trúc phản ánh đúng mục tiêu multi-agent và audit được từng quyết định.

## 8. Cách xác minh

```powershell
# Kiểm tra code
py -3.11 -m ruff check src tests

# Chạy toàn bộ test offline
py -3.11 -m pytest -q

# Chạy một case bằng model thật, không ghi output
py -3.11 -m ecommerce_dispute.main --case EC_001 --no-write

# Chạy đủ 50 case; mỗi lần phải dùng run-id mới
py -3.11 -m ecommerce_dispute.main --all --run-id <run-id-moi>

# Xem bằng chứng của lượt non-rule-based chính
Get-Content logging\run-openai-nonrule-20260805-001\metadata.json
Get-Content logging\run-openai-nonrule-20260805-001\manifest.json

# Kiểm tra file nộp cuối
Get-FileHash -Algorithm SHA256 output-run-openai-nonrule-20260805-final.zip
```

## 9. Điều học được và bước tiếp theo

Qua bài này, tôi rút ra rằng việc “có nhiều agent” không tự động tạo thành một hệ thống multi-agent đúng nghĩa. Cần xác định rõ thành phần nào thực sự ra quyết định bằng model, thành phần nào chỉ là worker/tool, dữ liệu được handoff ra sao và thành phần nào có quyền ghi output.

Các bước cải thiện tiếp theo:

1. Chọn model có tài liệu chính thức chứng minh không vượt 10B nhưng đủ khả năng structured reasoning.
2. Xây dựng tập eval riêng cho `secondary_issues` và `resolution_actions`, hai nhóm field đang có nhiều khác biệt nhất.
3. Cải thiện prompt bằng ví dụ chính sách tổng quát, không đưa đáp án của từng test case hoặc tái tạo decision table trong code.
4. Cấu hình Adjudicator cho các bất đồng kéo dài và lưu đầy đủ provenance của từng quyết định.
5. Lưu response chấm, submission ID và breakdown điểm thành artifact không chứa secret để các lần đánh giá sau có bằng chứng đầy đủ.

## 10. Cam kết cá nhân

- [x] Báo cáo phản ánh phần việc có thể đối chiếu từ lịch sử Git và artifact trong repo.
- [x] Phân biệt rõ deterministic orchestration với quyết định semantic do model sinh.
- [x] Không trình bày 50 output tổng hợp như một run duy nhất.
- [x] Ghi đúng điểm mới nhất là **66.5438** và mức chênh lệch với lần trước.
- [x] Không khẳng định trạng thái rule-based của lần chấm mới khi chưa có phản hồi tương ứng từ grader.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.

**Người báo cáo:** Nguyễn Quang Huy  
**Ngày xác nhận:** 05/08/2026
