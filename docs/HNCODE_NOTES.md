# Ghi Chú HNCode

File này gom các điểm dễ vỡ của HNCode để khi site đổi HTML/link/form thì sửa đúng chỗ.

## Domain

Domain chính hiện dùng cho bài, contest, course:

```text
https://hncode.edu.vn
```

Một số chức năng quiz cũ vẫn dùng:

```text
https://oj.hncode.edu.vn
```

Trong code, cấu hình chính nằm ở `TARGETS` trong `web_app.py`.

## Đăng nhập

HNCode/HNOJ dùng chung helper đăng nhập kiểu DMOJ:

```python
login_hncode(base_url, username, password)
```

Nếu lỗi `"login did not create a session"`, cần kiểm tra:

- form login có đổi field hay không,
- CSRF token,
- cookie session,
- domain đang dùng là `hncode.edu.vn` hay `oj.hncode.edu.vn`.

## Link contest

Parser HNCode đang hỗ trợ các dạng:

```text
/contest/<contest>
/contest/<contest>/problems
/contest/<contest>/ranking/
/contest/<contest>/problems/<ma_bai>
/contest/<contest>/problems/<ma_bai>/
/problem/<ma_bai>
```

Code chính:

```text
services/hncode.py
```

Test chính:

```powershell
python -m unittest discover -s tests -v
```

Fixture liên quan:

```text
tests/fixtures/hncode_contest_old.html
tests/fixtures/hncode_contest_new.html
tests/fixtures/hncode_ranking.html
```

## Link lesson

Lesson HNCode thường có:

```text
/course/<course>/lesson/<lesson_id>
/course/<course>/edit_lessons_new/<lesson_id>
/course/<course>/edit_lessons
```

Parser public lesson đọc link `/problem/<ma_bai>` trong lesson page.

Khi form lesson đổi, kiểm tra các helper trong `web_app.py`:

- `lesson_problem_rows_from_page`
- `lesson_quiz_rows_from_page`
- `append_lesson_problem_formset`
- `append_lesson_quiz_formset`
- `copy_hncode_contest_to_lesson`

Phần parser thuần đang có trong:

```text
services/hncode.py
```

## Admin problem

Các thao tác quan trọng:

```text
/admin/judge/problem/add/
/admin/judge/problem/<id>/change/
/problem/<ma_bai>/edit
/problem/<ma_bai>/test_data
/problem/<ma_bai>/submit
```

Metadata cần chú ý khi up bài:

- `Problem Name`
- `Points`
- `Problem Types`
- `Allows partial points`
- `Allowed languages`
- `Time limit`
- `Memory limit`

Nếu điểm/tags không cập nhật, kiểm tra luồng save ở trang:

```text
/problem/<ma_bai>/edit -> Content -> Metadata
```

## Upload test

HNCode upload test qua:

```text
https://hncode.edu.vn/problem/<ma_bai>/test_data
```

Khi ghi đè test, cần xóa test cũ trước nếu số test mới ít hơn số test cũ. Nếu không, form có thể báo kiểu:

```text
File input cho test 21 không tồn tại
```

Các helper liên quan:

- `upload_hncode_tests`
- `delete_hncode_existing_tests` nếu có trong luồng hiện tại
- `services/problem_upload.py`

## Quy tắc mã bài

HNCode hiện cho phép `_` trong mã bài, mã contest, mã lesson. Không tự động bỏ `_`.

Khi chuyển sang hệ khác, chỉ normalize nếu đích thật sự yêu cầu.

## Công thức trong đề

- HNCode dùng `$`.
- HNOJ/TinHocTre dùng `~`.

Luồng chuyển bài/up bài cần normalize statement theo đích.

## Khi HNCode đổi HTML

Thứ tự xử lý nên là:

1. Lưu HTML mới thành fixture trong `tests/fixtures/`.
2. Sửa parser ở `services/hncode.py`.
3. Chạy `python -m unittest discover -s tests -v`.
4. Test endpoint bị ảnh hưởng trên local.
5. Deploy VPS sau khi test pass.

