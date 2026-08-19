# Maintenance Cho AI / Maintainer

Đọc file này trước khi sửa project. Mục tiêu là sửa đúng chỗ, test nhanh, không làm vỡ các luồng đang chạy thật.

## Nguyên tắc

1. Không viết lại toàn bộ `web_app.py` trong một lần.
2. Ưu tiên thêm/sửa service nhỏ trong `services/`.
3. Parser HTML phải có fixture trong `tests/fixtures/`.
4. Sau mỗi thay đổi parser, chạy `python -m unittest discover -s tests -v`.
5. Sau mỗi thay đổi backend, chạy `python -m py_compile ...`.
6. Không xóa hoặc revert thay đổi người dùng nếu không được yêu cầu.

## Cấu trúc hiện tại

```text
web_app.py
templates/index.html
static/app.js
static/styles.css
services/
  api_response.py
  ai_assistant.py
  contest.py
  course.py
  hncode.py
  hnoj.py
  jobs.py
  lesson.py
  misc.py
  problem_bundle.py
  problem_transfer.py
  problem_upload.py
  quiz.py
  tinhoctre.py
tests/
  fixtures/
  test_api.py
  test_parsers.py
  test_problem_transfer.py
docs/
```

`web_app.py` vẫn còn nhiều logic lớn. Refactor tiếp nên làm từng lớp.

## Khi HNCode đổi contest

Sửa:

```text
services/hncode.py
```

Thêm fixture:

```text
tests/fixtures/hncode_contest_*.html
```

Chạy:

```powershell
python -m unittest discover -s tests -v
```

Endpoint cần test thêm:

```text
POST /api/misc/list-problem-codes
POST /api/misc/export-hncode-statements
POST /api/prepare-contest-to-lesson
POST /api/prepare-hncode-grading
```

## Khi HNCode đổi lesson

Kiểm tra:

```text
services/hncode.py
web_app.py: lesson_problem_rows_from_page
web_app.py: lesson_quiz_rows_from_page
web_app.py: append_lesson_problem_formset
web_app.py: append_lesson_quiz_formset
```

Endpoint cần test:

```text
POST /api/misc/list-problem-codes
POST /api/prepare-contest-to-lesson
POST /api/confirm-contest-to-lesson
POST /api/prepare-lesson-from-list
POST /api/confirm-lesson-from-list
POST /api/prepare-course-clone
POST /api/confirm-course-clone
```

Test nền hiện có:

```powershell
python -m unittest tests.test_ai_assistant -v
python -m unittest tests.test_ui_smoke -v
python -m unittest tests.test_contest_lesson -v
python -m unittest tests.test_course_clone -v
python -m unittest tests.test_grading -v
```

## Khi sửa AI chuẩn hóa đề bài

Kiểm tra:

```text
services/ai_assistant.py
web_app.py: /api/ai/prepare-file
web_app.py: /api/ai/prepare-normalize
web_app.py: /api/ai/normalize
web_app.py: /api/ai/validate-statement
static/misc.js
templates/index.html: panel-ai-normalize
```

Nguyên tắc:

- Chỉ dùng Google AI API key do người dùng nhập.
- Không đăng nhập hoặc lưu mật khẩu Google/Gemini web.
- Test tự động phải mock API, không gọi Google AI thật.
- Kết quả AI chỉ nên đưa ra bảng để giáo viên kiểm tra trước; không tự ghi đè HNCode nếu chưa có nút xác nhận riêng.

Test nhanh:

```powershell
python -m unittest tests.test_ai_assistant tests.test_ui_smoke -v
```

## Khi chuyển bài hoặc upload test lỗi

Kiểm tra:

```text
services/problem_bundle.py
services/problem_upload.py
services/problem_transfer.py
services/tinhoctre.py
web_app.py: upload_hncode_tests
web_app.py: upload_hnoj_tests
web_app.py: upload_transfer_to_dmoj
web_app.py: upload_transfer_to_tinhoctre
```

Các lỗi hay gặp:

- Zip thiếu `.out`.
- Tên input/output không match.
- Test cũ nhiều hơn test mới nhưng chưa xóa.
- HNCode đổi form `/problem/<ma_bai>/test_data`.

Test nhanh:

```powershell
python -m unittest discover -s tests -v
python -m py_compile web_app.py services\ai_assistant.py services\hncode.py services\hnoj.py services\tinhoctre.py services\problem_bundle.py services\problem_upload.py services\jobs.py
```

## Khi điểm/tags không lưu

Kiểm tra trang:

```text
/problem/<ma_bai>/edit -> Content -> Metadata
```

Các field cần cùng save:

- `Points`
- `Problem Types`
- `Allows partial points`
- `Problem Name`

Nếu chỉ tạo bài qua admin form mà chưa save metadata public edit page, điểm/tags có thể vẫn mặc định.

## Khi TinHocTre lỗi đăng nhập/WAF

TinHocTre có thể bật WAF/challenge nên tool không lấy được CSRF bằng `requests`.

Khi sửa TinHocTre, ưu tiên sửa:

```text
services/tinhoctre.py
tests/test_tinhoctre.py
```

Luồng xử lý:

1. Dùng browser local/Edge để đăng nhập.
2. Lấy cookie còn sống.
3. Dùng endpoint cookie TinHocTre trong tool.

Không nên hard-code cookie vào repo.

Test nhanh:

```powershell
python -m unittest tests.test_tinhoctre -v
python -m py_compile web_app.py services\tinhoctre.py
```

## Khi thêm endpoint mới

Nên làm theo mẫu:

1. Tách logic chính vào `services/<module>.py` nếu có thể.
2. Route Flask chỉ đọc request, gọi service, trả JSON.
3. Nếu chạy lâu, dùng `progress_id`.
4. Trả response qua `services/api_response.py` nếu endpoint không phải file download.
5. Ghi endpoint vào `docs/API.md`.
6. Thêm test parser/data nếu có xử lý HTML hoặc zip.

## Khi sửa JS giao diện

Các file JS đã tách theo vai trò:

```text
static/api.js
static/progress.js
static/app.js
static/upload.js
static/transfer.js
static/contest.js
static/lesson.js
static/misc.js
```

Không có bundler. Các file được load bằng `<script>` thường trong `templates/index.html`, nên thứ tự load quan trọng.

## Lệnh test chuẩn

Local:

```powershell
python -m unittest discover -s tests -v
python -m py_compile web_app.py services\api_response.py services\ai_assistant.py services\contest.py services\lesson.py services\course.py services\grading.py services\quiz.py services\misc.py services\hncode.py services\hnoj.py services\tinhoctre.py services\problem_bundle.py services\problem_upload.py services\problem_transfer.py services\jobs.py
node --check static\api.js
node --check static\progress.js
node --check static\app.js
node --check static\upload.js
node --check static\transfer.js
node --check static\contest.js
node --check static\lesson.js
node --check static\misc.js
```

Kiểm tra giao diện:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5050/
```

VPS:

```bash
cd /opt/tool-oj
python3 -m unittest discover -s tests -v
python3 -m py_compile web_app.py services/api_response.py services/ai_assistant.py services/contest.py services/lesson.py services/course.py services/grading.py services/quiz.py services/misc.py services/hncode.py services/hnoj.py services/tinhoctre.py services/problem_bundle.py services/problem_upload.py services/problem_transfer.py services/jobs.py
systemctl restart tool-oj.service
systemctl is-active tool-oj.service
```

## Checklist trước khi commit

- Test parser pass.
- `py_compile` pass.
- Không có file runtime/debug/log lớn bị add nhầm.
- Tài liệu cập nhật nếu đổi API/format.
- Giao diện local vẫn HTTP 200.

### Cập nhật 2026-08-13: nút Chuẩn hóa ghi lên HNCode

Panel AI có ba bước:

1. `Chuẩn bị dữ liệu`: đọc bài hoặc file nguồn, tạo bảng và link mở file `.md` tạm.
2. `Chuẩn hóa bằng AI`: gọi Google AI API bằng API key người dùng nhập, cập nhật bảng và file `.md` kết quả.
3. `Chuẩn hoá`: nếu chưa chuẩn bị/chưa gọi AI thì tự chạy các bước trước, sau đó gọi `/api/ai/apply-normalize` để cập nhật HNCode.

Khi sửa phần này cần nhớ:

- Không lưu Google AI API key vào repo; UI chỉ lưu tạm trong `localStorage` theo lựa chọn của người dùng.
- Không dùng mật khẩu Google/Gemini web để tự động đăng nhập.
- Endpoint apply chỉ nên cập nhật live sau khi người dùng bấm nút xác nhận riêng.
- Test phải mock `login_hncode`, `update_hncode_statement_markdown`, `update_hncode_problem_metadata`, `update_problem_solution_markdown`.
