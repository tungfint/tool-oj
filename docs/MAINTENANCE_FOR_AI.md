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
  contest.py
  course.py
  hncode.py
  hnoj.py
  jobs.py
  lesson.py
  problem_bundle.py
  problem_transfer.py
  problem_upload.py
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
POST /api/prepare-course-clone
POST /api/confirm-course-clone
```

Test nền hiện có:

```powershell
python -m unittest tests.test_contest_lesson -v
python -m unittest tests.test_course_clone -v
python -m unittest tests.test_grading -v
```

## Khi chuyển bài hoặc upload test lỗi

Kiểm tra:

```text
services/problem_bundle.py
services/problem_upload.py
services/problem_transfer.py
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
python -m py_compile web_app.py services\hncode.py services\hnoj.py services\problem_bundle.py services\problem_upload.py services\jobs.py
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

Luồng xử lý:

1. Dùng browser local/Edge để đăng nhập.
2. Lấy cookie còn sống.
3. Dùng endpoint cookie TinHocTre trong tool.

Không nên hard-code cookie vào repo.

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
python -m py_compile web_app.py services\api_response.py services\contest.py services\lesson.py services\course.py services\grading.py services\quiz.py services\misc.py services\hncode.py services\hnoj.py services\problem_bundle.py services\problem_upload.py services\problem_transfer.py services\jobs.py
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
python3 -m py_compile web_app.py services/api_response.py services/contest.py services/lesson.py services/course.py services/grading.py services/quiz.py services/misc.py services/hncode.py services/hnoj.py services/problem_bundle.py services/problem_upload.py services/problem_transfer.py services/jobs.py
systemctl restart tool-oj.service
systemctl is-active tool-oj.service
```

## Checklist trước khi commit

- Test parser pass.
- `py_compile` pass.
- Không có file runtime/debug/log lớn bị add nhầm.
- Tài liệu cập nhật nếu đổi API/format.
- Giao diện local vẫn HTTP 200.
