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

Trạng thái hiện tại:

- Đã tạo `services/hncode.py` để gom parser/link helper của HNCode.
- `web_app.py` đã chuyển các hàm đọc contest/lesson/admin problem ID sang gọi service chung, giữ wrapper cũ để các API hiện có không đổi contract.
- Parser contest HNCode đã hỗ trợ ranking/header mới và link dạng `/contest/<contest>/problems/<ma_bai>` hoặc `/problem/<ma_bai>`.
- Đã test với `https://hncode.edu.vn/contest/nt26exam01`: lấy được 14 bài, đúng tên bài và điểm.

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

Trạng thái hiện tại:

- Đã tạo `services/problem_bundle.py` để gom phần đọc bộ bài, tách Markdown tổng hợp, đọc metadata `Tên bài | Mã bài | Điểm | Tags`, chạy gentest/zip test cho luồng up bài.
- Đã tạo `services/problem_upload.py` cho helper upload dùng chung HNCode/HNOJ: chuẩn hóa mã bài, memory limit, link bài/test, upload test, nộp thử, chọn language submit.
- `web_app.py` đã giữ các hàm wrapper cũ nhưng chuyển helper HNCode/HNOJ sang gọi service mới, để UI/API hiện tại không đổi contract.
- Đã test `services/problem_bundle.py` với `samples/bo_mau_1_bai_tonghaiso.zip`: đọc được 1 bài, 10 test, đúng điểm/tags.
- Phạm vi lần này chỉ áp dụng HNCode và HNOJ; TinHocTre giữ nguyên luồng cũ vì còn phụ thuộc cookie/WAF riêng.

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

Trạng thái hiện tại:

- Đã tạo `services/jobs.py` để chuẩn hóa ghi/đọc tiến độ theo `job_id`, `phase`, `done`, `total`, `rows`, `log`, `message`, `status`.
- `web_app.py` đã chuyển `progress_update`, `progress_finish`, `valid_progress_id`, `progress_path` sang wrapper gọi service mới.
- Endpoint `/api/progress/<progress_id>` vẫn giữ nguyên cho giao diện hiện tại, nhưng dữ liệu trả về có thêm `job_id`, `status`, `created_at`, `updated_at`.
- Service vẫn tương thích các trường cũ `finished` và `ok`, nên JS hiện tại không cần đổi.

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

Trạng thái hiện tại:

- Đã tách HTML chính ra `templates/index.html`.
- Đã tách CSS ra `static/styles.css`.
- Đã tách JS giao diện ra `static/app.js`; template chỉ còn block `window.APP_CONFIG` nhỏ để truyền dữ liệu Jinja cho JS.
- Route `/` đã chuyển từ `render_template_string` sang `render_template("index.html")`.
- Chưa tách nhỏ `static/api.js` và `static/tables.js`; nên làm ở giai đoạn sau để tránh làm vỡ JS đang có nhiều phụ thuộc chéo.

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

Trạng thái hiện tại:

- Đã tạo `tests/fixtures/` với 5 fixture HTML: contest HNCode cũ, contest HNCode mới, ranking HNCode, lesson HNCode, contest HNOJ.
- Đã tạo `tests/test_parsers.py` bằng `unittest` chuẩn, không cần thêm dependency mới.
- Đã thêm `services/hnoj.py` làm wrapper parser HNOJ để sau này nếu HNOJ đổi HTML thì sửa riêng tại service này.
- Parser HNCode đã hỗ trợ link contest dạng `/contest/<contest>/problems/<ma_bai>` có hoặc không có dấu `/` phía sau mã bài.
- Lệnh kiểm tra nhanh:

```powershell
python -m unittest discover -s tests -v
```

Kết quả hiện tại: 5/5 test parser pass.

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

Trạng thái hiện tại:

- Đã tạo thư mục `docs/`.
- Đã tạo `docs/API.md` ghi các endpoint đang có, payload chính, response và service liên quan.
- Đã tạo `docs/HNCODE_NOTES.md` ghi domain, login, link contest/lesson, upload test, metadata, quy tắc mã bài và cách xử lý khi HNCode đổi HTML.
- Đã tạo `docs/DATA_FORMATS.md` ghi format zip bộ bài, Markdown, gentest, test zip, quiz, tài khoản chấm bài và data contest.
- Đã tạo `docs/MAINTENANCE_FOR_AI.md` ghi checklist sửa parser/upload/lesson, lệnh test và quy tắc commit/deploy.

## VII. Vi?c n?n l?m ngay ti?p theo

Checklist n?y ?? ho?n t?t ? c?c giai ?o?n 1 ??n 5 v? ph?n b? sung sau ??:

1. T?o th? m?c `services/`: ?? l?m.
2. T?ch HNCode parser ??u ti?n: ?? l?m trong `services/hncode.py`.
3. T?o `docs/API.md`: ?? l?m.
4. T?o `docs/HNCODE_NOTES.md`: ?? l?m.
5. ??i c?c ch?c n?ng ?ang ??c contest HNCode sang service chung: ?? l?m ph?n ch?nh qua `services/hncode.py`.
6. Vi?t test fixtures cho HNCode contest c?/m?i: ?? l?m trong `tests/fixtures/` v? `tests/test_parsers.py`.
7. Sau khi ?n m?i t?ch upload/chuy?n b?i: ?? t?ch c?c ph?n n?n sang:

```text
services/problem_bundle.py
services/problem_upload.py
services/problem_transfer.py
```

Tr?ng th?i hi?n t?i:

- `services/problem_transfer.py` ?? gom ph?n build row chu?n b? chuy?n b?i, row l?i, ?p th?ng tin b?ng xu?ng `ProblemInfo`, v? wrapper upload transfer cho DMOJ/HNCode/HNOJ/TinHocTre qua callback.
- `web_app.py` v?n gi? route Flask v? callback form c? th? ?? kh?ng ??i contract giao di?n/API.
- ?? th?m `tests/test_problem_transfer.py` ?? ki?m tra service chuy?n b?i.
- L?nh `python -m unittest discover -s tests -v` hi?n c? 8 test pass.

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
