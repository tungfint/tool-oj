# API Tool HNCode / HNOJ / TinHocTre

Tài liệu này mô tả các endpoint đang có trong `web_app.py`. Mục tiêu là giúp AI/maintainer nhìn nhanh luồng dữ liệu trước khi sửa code.

## Quy ước chung

- Hầu hết endpoint trả JSON.
- Response mới nên có đủ `ok`, `message`, `rows`, `log`, `errors`, `meta`.
- Trong giai đoạn chuyển tiếp, endpoint vẫn có thể giữ field cũ như `error`, `prepare_id`, `download_url`, `codes_text` để giao diện hiện tại không hỏng.
- Các nhóm đã được gom về helper `services/api_response.py`: chuyển bài, chuyển contest, Contest → Lesson, Clone Course, Chấm bài HNCode, một số endpoint upload/misc nền.
- Luồng dài thường có `progress_id`; client đọc tiến độ qua `GET /api/progress/<progress_id>`.
- Các endpoint `prepare-*` tạo `prepare_id` và dữ liệu tạm trong bộ nhớ/thư mục `.runtime/`.
- Các endpoint `confirm-*` nhận lại `prepare_id`, danh sách dòng đã chọn, tài khoản và cấu hình để thực hiện thật.
- Khi lỗi, nhiều endpoint hiện trả `{"error": "..."}` hoặc `{"ok": false, "error": "..."}`. Đây là điểm nên chuẩn hóa dần về response chung.

Helper response chung:

```text
services/api_response.py
```

## Giao diện và mẫu

### `GET /`

Render giao diện chính từ `templates/index.html`.

### `GET /samples/bo_mau_1_bai_tonghaiso.zip`

Tải bộ mẫu 1 bài để test phần Up bài.

### `POST /api/sample/tonghaiso`

Tạo hoặc trả thông tin bộ mẫu `tonghaiso`.

## Đăng nhập

### `POST /api/check-login`

Kiểm tra đăng nhập theo target.

Payload chính:

```json
{
  "target": "hncode",
  "account": {
    "username": "...",
    "password": "..."
  }
}
```

Target thường dùng: `hncode`, `hnoj`, `tinhoctre`, `hncode_oj`, `contest_hnoj`.

## Lấy danh sách mã bài

### `POST /api/misc/list-problem-codes`

Lấy mã bài từ HNCode/HNOJ.

Payload:

```json
{
  "site": "hncode",
  "source_type": "contest",
  "url": "https://hncode.edu.vn/contest/nt26exam01",
  "account": {
    "username": "...",
    "password": "..."
  }
}
```

Giá trị hỗ trợ:

- `site=hncode`, `source_type=contest`
- `site=hncode`, `source_type=lesson`
- `site=hnoj`, `source_type=contest`

Service/parser liên quan:

- `services/hncode.py`
- `services/hnoj.py`

## Up nhiều bài

### `POST /api/prepare-upload`

Đọc file zip/folder bộ bài, sinh hoặc nhận test zip, trả bảng bài chuẩn bị up.

Dữ liệu vào thường là multipart form:

- `target`
- `zip_path` hoặc file upload
- `time_limit`
- `memory_limit`
- `allowed_languages`
- `skip_first_line`
- `no_statement`
- `no_tests`
- `submit_cpp`
- `submit_python`
- `overwrite_statement`
- `overwrite_tests`
- `progress_id`

Kết quả chính:

```json
{
  "prepare_id": "...",
  "rows": [],
  "log": "..."
}
```

### `POST /api/confirm-upload`

Up các bài đã chuẩn bị.

Payload chính:

```json
{
  "prepare_id": "...",
  "target": "hncode",
  "account": {"username": "...", "password": "..."},
  "rows": [],
  "settings": {},
  "progress_id": "..."
}
```

Service liên quan:

- `services/problem_bundle.py`
- `services/problem_upload.py`
- Các hàm upload form cụ thể hiện vẫn còn trong `web_app.py`.

## Up 1 bài

### `POST /api/prepare-single-upload`

Chuẩn bị dữ liệu cho một bài nhập thủ công: mã bài, tên, điểm, tags, statement, gentest/test zip, solution.

### `POST /api/confirm-single-upload`

Tạo hoặc ghi đè một bài từ dữ liệu đã chuẩn bị.

## Chuyển bài

### `POST /api/prepare-transfer`

Đọc bài nguồn, statement, test, số test và metadata để chuẩn bị chuyển sang đích.

Nguồn/đích thường dùng:

- `hncode`
- `hnoj`
- `tinhoctre`

### `POST /api/confirm-transfer`

Tạo/cập nhật bài ở đích, upload statement/test, metadata, nộp thử nếu được chọn.

Service liên quan:

- `services/problem_transfer.py`: build bảng chuẩn bị, áp override từ bảng xuống `ProblemInfo`, wrapper upload transfer theo target.
- `services/problem_upload.py`: normalize mã bài, URL bài/test, ngôn ngữ, statement theo target.
- `transfer_tinhoctre_to_hncode.py` và các hàm form trong `web_app.py`: fetch source problem và submit form cụ thể.

Lưu ý:

- HNCode dùng `$` cho công thức.
- HNOJ/TinHocTre dùng `~` cho công thức.
- Khi mã bài đã tồn tại, luồng có thể ghi đè đề/test tùy cấu hình.

## Contest

### `POST /api/prepare-contest-transfer`

Đọc một hoặc nhiều contest nguồn, liệt kê bài trong contest, kiểm tra bài/test ở đích.

### `POST /api/confirm-contest-transfer`

Chuyển contest sang đích; bài thiếu có thể được tạo trước rồi thêm vào contest.

### `POST /api/create-contest`

Tạo contest từ danh sách mã bài. Nếu mã contest đã tồn tại, tool thêm bài vào contest hiện có.

Service nền:

- `services/contest.py`: parse mã contest, nhận diện nguồn HNCode/HNOJ từ URL, build URL contest.

## Contest sang Lesson

### `POST /api/prepare-contest-to-lesson`

Đọc contest nguồn HNCode/HNOJ, so với lesson đích HNCode, trả bảng từng bài.

### `POST /api/confirm-contest-to-lesson`

Thêm bài vào lesson HNCode. Nếu nguồn là HNOJ và bài chưa có ở HNCode, tool có thể chuyển bài trước.

Service nền:

- `services/lesson.py`: parse URL lesson, build URL lesson/edit lesson, parse/build formset lesson, build bảng chuẩn bị Contest -> Lesson và merge dòng xác nhận.

## Clone Course

### `POST /api/prepare-course-clone`

Đọc lesson/contest của course nguồn và kiểm tra course đích.

### `POST /api/confirm-course-clone`

Clone lesson và contest sang course đích.

Service nền:

- `services/course.py`: parse course slug, build course URL, parse danh sách lesson/contest từ HTML course, chuẩn hóa mã contest clone mặc định, build bảng chuẩn bị Clone Course và merge rows xác nhận.

## Quiz

### `POST /api/prepare-quiz`

Parse nội dung quiz, kiểm tra từng câu và trả bảng trạng thái.

### `POST /api/upload-quiz`

Tạo câu hỏi tại HNCode OJ quiz form.

Service nền:

- `services/quiz.py`: parse Markdown quiz, validate câu hỏi, build rows chuẩn bị upload.

## Chấm bài HNCode

### `POST /api/prepare-hncode-grading`

Nhận zip bài làm, CSV tài khoản, URL contest. Tool đọc danh sách bài contest và map file bài làm theo học sinh.

### `POST /api/confirm-hncode-grading`

Đăng nhập từng tài khoản, join contest nếu cần, nộp từng bài và chờ kết quả.

### `GET /api/download-hncode-grading/<prepare_id>`

Tải file Excel kết quả chấm.

Service nền:

- `services/grading.py`: đọc CSV tài khoản, chuẩn hóa tên học sinh/tên file, map file bài làm vào mã bài contest, build/merge rows chuẩn bị chấm, parse bảng rank và xuất Excel kết quả.

## Tool lẻ

## AI chuẩn hóa đề bài

### `POST /api/ai/prepare-file`

Nhận file đề bài rời (`.md`, `.txt`, `.pdf`, `.docx`, ảnh phổ biến), trích text nếu có và trả `source_text`, `mime_type`, `file_base64`.

### `POST /api/ai/prepare-normalize`

Chuẩn bị dữ liệu chuẩn hóa. Có 2 nguồn:

- `source_mode=codes`: đọc danh sách mã bài HNCode bằng tài khoản đã lưu.
- `source_mode=file`: dùng nội dung/file rời đã đưa lên.

Trả `prepare_id` và bảng rows.

### `POST /api/ai/normalize`

Gọi Google AI bằng API key người dùng nhập, trả về Markdown đề bài, points, tags, solution, nhận xét test và issues theo từng bài. Test tự động mock endpoint này, không gọi mạng thật.

### `POST /api/ai/validate-statement`

Kiểm tra nhanh Markdown AI trả về: dòng đầu metadata, mã bài, điểm, ký hiệu công thức `$`/`~`, phần thân đề.

Service nền:

- `services/ai_assistant.py`: đọc file, build prompt theo tài liệu chuẩn hóa, gọi Gemini REST `generateContent`, parse JSON AI trả về và validate Markdown.
- Tool dùng Google AI API key, không đăng nhập hoặc lưu mật khẩu Google/Gemini web.

### `POST /api/misc/last-submissions`

Nhận zip/folder data contest, trả zip chứa lần nộp cuối.

### `POST /api/misc/ai-code-warning`

Nhận folder hoặc zip data contest, phân tích dấu hiệu AI code và chép code, trả Excel báo cáo.

Service nền:

- `services/misc.py`: chọn last submission Scratch, phân tích input code zip, chuẩn hóa token/code fingerprint phục vụ cảnh báo AI và chép code.

## Cookie TinHocTre

Service nền:

- `services/tinhoctre.py`: build URL TinHocTre, normalize đề bài `$` -> `~`, nhận diện WAF/challenge, parse lỗi form đơn giản, lưu/đọc cookie tạm và apply cookie vào session. Cookie vẫn lấy từ browser/người dùng, không hard-code trong code.

### `POST /api/tinhoctre-browser/start`

Mở browser local để lấy cookie TinHocTre khi bị WAF/challenge.

### `POST /api/tinhoctre-browser/cookie`

Nhận cookie TinHocTre do người dùng paste.

### `POST /api/tinhoctre-browser/quick-cookie`

Lấy nhanh cookie từ browser local nếu phiên đăng nhập còn sống.

## Progress

### `GET /api/progress/<progress_id>`

Đọc trạng thái job/progress.

Response thường có:

```json
{
  "job_id": "...",
  "phase": "...",
  "done": 1,
  "total": 10,
  "rows": [],
  "log": "",
  "message": "",
  "status": "running",
  "finished": false,
  "ok": true
}
```
