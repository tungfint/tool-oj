# Ghi chú API và link HNCode

## Domain HNCode

Tool ưu tiên dùng domain:

```text
https://hncode.edu.vn
```

Một số chức năng cũ có thể vẫn nhận link `https://oj.hncode.edu.vn`, nhưng khi xử lý bài, contest, lesson nên dùng `https://hncode.edu.vn`.

## Parser contest HNCode

HNCode đã thay đổi link bài trong contest. Tool dùng helper chung để đọc danh sách bài và hỗ trợ các dạng sau:

```text
/problem/<ma_bai>
/contest/<ma_contest>/problems/<ma_bai>
.problem-code trong bảng ranking
```

Các chức năng đang dùng parser chung:

- Contest -> Lesson.
- Chấm bài HNCode: đọc danh sách bài trong contest.
- Đọc danh sách bài public của contest để chuyển contest/bài.

Nếu HNCode đổi cấu trúc contest lần nữa, ưu tiên sửa helper đọc contest trong `web_app.py` thay vì sửa từng chức năng riêng.

## API Contest -> Lesson

Chuẩn bị dữ liệu:

```http
POST /api/prepare-contest-to-lesson
```

Payload mẫu:

```json
{
  "source": "hncode",
  "account": {"username": "hncode", "password": "..."},
  "source_account": {"username": "hncode", "password": "..."},
  "contest_url": "https://hncode.edu.vn/contest/nt26exam01",
  "lesson_url": "https://hncode.edu.vn/course/nt26_tuyen3/lesson/3123"
}
```

Kết quả trả về gồm `prepare_id`, `rows`, `can_copy`, `lesson_link`, `log`.

Xác nhận sao chép:

```http
POST /api/confirm-contest-to-lesson
```

Payload mẫu:

```json
{
  "prepare_id": "<prepare_id>",
  "account": {"username": "hncode", "password": "..."},
  "source_account": {"username": "hncode", "password": "..."},
  "rows": []
}
```

Thông thường lấy nguyên `rows` từ bước prepare, chỉnh `selected` hoặc `score` nếu cần, rồi gửi sang confirm.

## Lưu ý điểm lesson

HNCode có thể hiển thị điểm contest dạng `1p`. Tool đổi dạng này thành `1` khi điền điểm lesson.

Nếu điểm contest là số lớn kiểu rating hoặc metadata khác, nên chỉnh lại điểm trong bảng trước khi xác nhận sao chép.
