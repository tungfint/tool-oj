# Kế hoạch tối ưu Tool HNCode / HNOJ / TinHocTre

Mục tiêu: giữ hệ thống đang chạy ổn định, nhưng refactor dần thành kiến trúc **API lõi + service theo từng web + giao diện gọi API**. Cách này giúp sau này AI hoặc người sửa code đọc nhanh hơn, cập nhật ít rủi ro hơn khi HNCode/HNOJ/TinHocTre đổi giao diện.

## I. Nguyên tắc làm lại

Không đập đi viết lại toàn bộ.

Làm theo hướng:

1. Chức năng đang dùng được thì giữ.
2. Chức năng hay lỗi thì tách API/service trước.
3. Mỗi lần refactor phải có test nhanh bằng API thật hoặc dữ liệu mẫu.
4. Giao diện web chỉ làm nhiệm vụ nhập dữ liệu, gọi API, hiển thị bảng/log.
5. Logic đăng nhập, parse form, upload, chuyển bài, tạo contest phải nằm trong service riêng.

## II. Kiến trúc đích

```text
web_app.py
  - Flask routes
  - Render giao diện
  - Nhận request / trả JSON
  - Không chứa nhiều logic parse/upload phức tạp

services/
  auth.py
  hncode.py
  hnoj.py
  tinhoctre.py
  problem_bundle.py
  problem_upload.py
  problem_transfer.py
  contest.py
  lesson.py
  course.py
  quiz.py
  grading.py
  misc.py

schemas/
  common.py
  problem.py
  contest.py
  lesson.py
  quiz.py

docs/
  API.md
  HNCODE_NOTES.md
  DATA_FORMATS.md
  MAINTENANCE_FOR_AI.md

tests/
  test_parsers.py
  test_problem_bundle.py
  test_hncode_contest_parser.py
```

## III. Chuẩn response API

Tất cả API nên trả cùng một cấu trúc:

```json
{
  "ok": true,
  "message": "",
  "rows": [],
  "log": "",
  "errors": [],
  "download_url": "",
  "job_id": "",
  "meta": {}
}
```

Khi lỗi:

```json
{
  "ok": false,
  "message": "Mô tả lỗi ngắn",
  "errors": [
    {
      "code": "problem_code",
      "message": "Chi tiết lỗi",
      "source": "hncode"
    }
  ],
  "log": "Log xử lý"
}
```

## IV. API lõi cần chuẩn hóa

### 1. Auth

```http
POST /api/auth/check
POST /api/auth/save-cookie
POST /api/auth/status
```

Dùng chung cho:

- HNCode
- HNOJ
- TinHocTre
- Contest HNOJ subdomain nếu cần

### 2. List mã bài

```http
POST /api/problem-codes/list
```

Nguồn:

- HNCode Contest
- HNCode Lesson
- HNOJ Contest
- TinHocTre Contest nếu sau này cần

Đây là API nền rất quan trọng vì nhiều chức năng khác cần danh sách mã bài.

### 3. Up bài

```http
POST /api/problems/prepare-upload
POST /api/problems/confirm-upload
POST /api/problems/upload-one
POST /api/problems/overwrite
```

Tách rõ:

- đọc zip bộ bài,
- đọc file `.md`,
- chạy `gentest`,
- chuẩn hóa test zip,
- tạo bài,
- upload đề,
- upload test,
- cập nhật metadata,
- nộp thử.

### 4. Chuyển bài

```http
POST /api/problems/prepare-transfer
POST /api/problems/confirm-transfer
```

Nguồn/đích:

- HNCode
- HNOJ
- TinHocTre

Service phải xử lý riêng:

- ký tự `$` / `~`,
- ảnh/pdf trong đề,
- test zip,
- bài đã tồn tại,
- ghi đè đề/test.

### 5. Contest

```http
POST /api/contests/list-problems
POST /api/contests/prepare-transfer
POST /api/contests/confirm-transfer
POST /api/contests/create
POST /api/contests/add-problems
```

Phần này cần dùng chung parser contest, tránh mỗi chức năng tự regex riêng.

### 6. Lesson

```http
POST /api/lessons/list-problems
POST /api/lessons/add-problems
POST /api/lessons/copy-from-contest
```

Với HNCode, lesson hiện dùng:

```text
/course/<course>/lesson/<lesson_id>
/course/<course>/edit_lessons_new/<lesson_id>
```

Nếu HNCode đổi form lesson, chỉ sửa `services/lesson.py`.

### 7. Course

```http
POST /api/courses/clone
POST /api/courses/list-lessons
POST /api/courses/list-contests
```

Clone course nên dùng lại API lesson/contest đã chuẩn hóa, không tự parse lại từ đầu.

### 8. Quiz

```http
POST /api/quiz/prepare
POST /api/quiz/upload
```

Giữ riêng vì quiz đang ở domain/form khác.

### 9. Chấm bài

```http
POST /api/grading/prepare
POST /api/grading/confirm
GET  /api/grading/download/<job_id>
```

Chấm bài nên phụ thuộc API list problem codes của contest, không tự parse contest riêng.

### 10. Tool lẻ

```http
POST /api/misc/last-submissions
POST /api/misc/ai-code-warning
POST /api/misc/list-problem-codes
```

Sau này có thể chuyển `list-problem-codes` sang `/api/problem-codes/list`, còn endpoint cũ giữ alias để không hỏng giao diện.

## V. Thứ tự ưu tiên làm

## Giai đoạn 1: Ổn định nền parser và API chung

Mục tiêu: giảm lỗi khi HNCode đổi giao diện.

Việc cần làm:

1. Tách parser HNCode ra khỏi `web_app.py`.
2. Tạo `services/hncode.py`.
3. Tạo helper chung:

```python
list_contest_problems(session, contest_key)
list_lesson_problems(session, course_slug, lesson_id)
find_problem_admin_id(session, code)
```

4. Cho các chức năng sau dùng chung helper:

- Contest -> Lesson
- Chấm bài HNCode
- Tạo contest từ mã bài
- Chuyển contest
- Clone course
- Lấy list mã bài

Nên làm trước vì đây là chỗ vừa phát sinh lỗi thật.

Tr?ng th?i hi?n t?i:

- ?? t?o `services/hncode.py` ?? gom parser/link helper c?a HNCode.
- `web_app.py` ?? chuy?n c?c h?m ??c contest/lesson/admin problem ID sang g?i service chung, gi? wrapper c? ?? c?c API hi?n c? kh?ng ??i contract.
- Parser contest HNCode ?? h? tr? ranking/header m?i v? link d?ng `/contest/<contest>/problems/<ma_bai>` ho?c `/problem/<ma_bai>`.
- ?? test v?i `https://hncode.edu.vn/contest/nt26exam01`: l?y ???c 14 b?i, ??ng t?n b?i v? ?i?m.

## Giai đoạn 2: Tách phần upload/chuyển bài

Mục tiêu: giảm rối ở Up 1 bài, Up nhiều bài, Chuyển bài.

Tạo:

```text
services/problem_bundle.py
services/problem_upload.py
services/problem_transfer.py
```

Các hàm quan trọng:

```python
parse_problem_bundle(zip_or_folder)
normalize_statement_for_target(text, target)
prepare_tests(bundle)
create_problem(target, info)
upload_statement(target, code, statement)
upload_tests(target, code, test_zip, overwrite=False)
submit_trial_solution(target, code, solution_file)
```

Làm sau giai đoạn 1 vì phần này rộng, dễ đụng nhiều chức năng.

Tr?ng th?i hi?n t?i:

- ?? t?o `services/problem_bundle.py` ?? gom ph?n ??c b? b?i, t?ch Markdown t?ng h?p, ??c metadata `T?n b?i | M? b?i | ?i?m | Tags`, ch?y gentest/zip test cho lu?ng up b?i.
- ?? t?o `services/problem_upload.py` cho helper upload d?ng chung HNCode/HNOJ: chu?n h?a m? b?i, memory limit, link b?i/test, upload test, n?p th?, ch?n language submit.
- `web_app.py` ?? gi? c?c h?m wrapper c? nh?ng chuy?n helper HNCode/HNOJ sang g?i service m?i, ?? UI/API hi?n t?i kh?ng ??i contract.
- ?? test `services/problem_bundle.py` v?i `samples/bo_mau_1_bai_tonghaiso.zip`: ??c ???c 1 b?i, 10 test, ??ng ?i?m/tags.
- Ph?m vi l?n n?y ch? ?p d?ng HNCode v? HNOJ; TinHocTre gi? nguy?n lu?ng c? v? c?n ph? thu?c cookie/WAF ri?ng.

## Giai đoạn 3: Chuẩn hóa job/progress

Mục tiêu: mọi chức năng dài đều có tiến độ rõ.

Tạo:

```text
services/jobs.py
```

Job chuẩn:

```json
{
  "job_id": "",
  "phase": "",
  "done": 0,
  "total": 0,
  "rows": [],
  "log": "",
  "status": "running|done|failed"
}
```

Áp dụng cho:

- Up nhiều bài
- Chuyển nhiều bài
- Chuyển contest
- Chấm bài
- Cảnh báo AI code
- Clone course

## Giai đoạn 4: Tách giao diện thành client sạch

Mục tiêu: JS chỉ gọi API và render.

Nên tách:

```text
static/app.js
static/api.js
static/tables.js
static/styles.css
templates/index.html
```

Hiện tại HTML/JS/CSS nằm nhiều trong `web_app.py`, AI đọc sẽ bị nặng. Tách ra sẽ dễ sửa giao diện hơn.

## Giai đoạn 5: Viết test parser và test dữ liệu mẫu

Mục tiêu: khi HNCode đổi HTML, sửa parser xong test ngay.

Test cần có:

```text
tests/fixtures/hncode_contest_old.html
tests/fixtures/hncode_contest_new.html
tests/fixtures/hncode_ranking.html
tests/fixtures/hncode_lesson.html
tests/fixtures/hnoj_contest.html
```

Test:

```python
def test_parse_hncode_old_problem_links()
def test_parse_hncode_new_contest_problem_links()
def test_parse_hncode_ranking_problem_codes()
def test_parse_hncode_lesson_problem_codes()
def test_parse_hnoj_contest_problem_codes()
```

## VI. Tài liệu cần có để AI dễ đọc hiểu

Nên có thư mục `docs/`.

### `docs/API.md`

Ghi toàn bộ endpoint:

- URL
- payload
- response
- ví dụ lỗi
- chức năng nào gọi endpoint đó

### `docs/HNCODE_NOTES.md`

Ghi riêng các lưu ý HNCode:

- domain chính,
- login,
- contest link cũ/mới,
- lesson form,
- test data upload,
- metadata points/tags,
- quiz form.

### `docs/DATA_FORMATS.md`

Ghi cấu trúc zip bài:

```text
<ma_bai>.md
gentest_<ma_bai>.py
<ma_bai>.zip
sol_<ma_bai>.md
sol_<ma_bai>.cpp
sol_<ma_bai>.py
```

Ghi format quiz, format tài khoản, format bài làm học sinh.

### `docs/MAINTENANCE_FOR_AI.md`

File này dành riêng cho AI/maintainer.

Nội dung nên có:

```text
Khi HNCode đổi contest:
- sửa services/hncode.py
- chạy tests/test_hncode_contest_parser.py
- test API /api/problem-codes/list

Khi HNCode đổi lesson:
- sửa services/lesson.py
- test list lesson
- test add-problems-to-lesson

Khi upload test lỗi:
- kiểm tra services/problem_upload.py
- kiểm tra format zip test
```

## VII. Việc nên làm ngay tiếp theo

Nên làm theo thứ tự:

1. Tạo thư mục `services/`.
2. Tách HNCode parser đầu tiên.
3. Tạo `docs/API.md`.
4. Tạo `docs/HNCODE_NOTES.md`.
5. Đổi các chức năng đang đọc contest HNCode sang service chung.
6. Viết test fixtures cho HNCode contest cũ/mới.
7. Sau khi ổn mới tách upload/chuyển bài.

## VIII. Việc chưa nên làm ngay

Chưa nên làm ngay:

- Viết lại toàn bộ giao diện.
- Đổi framework.
- Tách database/job queue phức tạp.
- Đập `web_app.py` thành quá nhiều file trong một lần.

Lý do: tool đang dùng thật, refactor quá mạnh một lần dễ làm hỏng các luồng đang chạy.

## IX. Kết luận

Nên tối ưu hệ thống, nhưng làm theo kiểu **refactor từng lớp**.

Ưu tiên số 1 là tách các parser và API lõi dùng chung, đặc biệt cho HNCode contest/lesson. Sau đó mới tách upload/chuyển bài, rồi cuối cùng mới tách giao diện.

Mục tiêu cuối cùng:

- Giao diện dễ dùng.
- API gọi được tự động.
- Code dễ đọc cho AI.
- Khi HNCode/HNOJ/TinHocTre đổi giao diện, chỉ sửa đúng một service.
