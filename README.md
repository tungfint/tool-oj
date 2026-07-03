# Tool HNCode

Project hỗ trợ chuẩn bị dữ liệu, tạo bài mới, upload test, nộp thử lời giải và chuyển bài giữa 3 hệ thống:

- HNOJ: `https://hnoj.edu.vn`
- HNCode: `https://oj.hncode.edu.vn`
- TinHocTre: `https://tinhoctre.vn`

Tool ưu tiên tạo bài qua admin form:

- `https://hnoj.edu.vn/admin/judge/problem/add/`
- `https://tinhoctre.vn/admin/judge/problem/add/`
- `https://oj.hncode.edu.vn/admin/judge/problem/add/`

Giao diện dùng favicon từ `static/favicon-HNCode.svg`.

Quy tắc ký tự công thức trong đề bài:

- Khi up hoặc chuyển bài lên `HNOJ` và `TinHocTre`, đề bài dùng `~` thay cho `$`.
- Khi up hoặc chuyển bài lên `HNCode`, đề bài dùng `$` thay cho `~`.

## Chạy giao diện web

```powershell
cd C:\Users\Admin\Documents\_ChuyenBai
pip install -r requirements.txt
python web_app.py
```

Khi chạy production bằng Gunicorn/nginx, nên đặt timeout đủ dài vì bước `Chuẩn bị dữ liệu` có thể chạy nhiều file `gentest`:

```text
gunicorn --timeout 300 -w 2 -b 127.0.0.1:5051 web_app:app
```

Mở:

```text
http://127.0.0.1:5050
```

## Tab Tài khoản & Hướng dẫn

Lưu tạm tài khoản admin của 3 trang trên trình duyệt máy đang dùng bằng `localStorage`.

Có các nút:

- `Lưu tạm`
- `Xóa thông tin đã lưu`
- `Ẩn / Hiện hướng dẫn prompt`

Hướng dẫn prompt yêu cầu mỗi bài có đủ:

- `gentest_<ma_bai>.py`
- `sol_<ma_bai>.py`
- `sol_<ma_bai>.cpp`
- `<ma_bai>.md`

Dòng đầu file Markdown nên có dạng:

```text
Tên bài | Mã bài
```

## Tab Up bài

Luồng sử dụng:

1. Chọn web đích: `HNOJ`, `HNCode` hoặc `TinHocTre`.
2. Chọn file zip bộ bài hoặc file Markdown tổng hợp bằng cách dán đường dẫn hoặc bấm `Chọn file`.
   - File zip dùng cấu trúc cũ: mỗi bài có file đề, test zip hoặc `gentest`.
   - File Markdown tổng hợp dùng để up đề bài, mỗi bài bắt đầu bằng dòng `# Bài 1. Tên bài | ma_bai`.
3. Kiểm tra `Giới hạn thời gian`, `Giới hạn bộ nhớ`, `Ngôn ngữ cho phép`.
4. Bấm `Mở rộng thông tin khác` nếu cần xem/sửa nhóm thông tin phụ:
   - Người tạo (Creators): mặc định `mrtee`.
   - Dạng đề (Problem types): `Chưa phân loại`.
   - Nhóm bài (Problem group): `Chưa phân loại`.
5. Chọn nhu cầu nộp thử:
   - `Nộp bài chấm thử C++`: dùng `sol_<ma_bai>.cpp`.
   - `Nộp bài chấm thử Python`: dùng `sol_<ma_bai>.py`.
   - `Không nộp bài chấm thử`: bỏ qua toàn bộ bước nộp thử.
6. Tích `Bỏ dòng đầu tiên trong file đề bài` nếu file Markdown có dòng đầu dạng `Tên bài | Mã bài` và không muốn đưa dòng này vào đề bài.
7. Bấm `Chuẩn bị dữ liệu`.
8. Kiểm tra bảng bài, sửa mã/tên nếu cần. Có nút `Chọn tất cả` và `Bỏ chọn tất cả` cho bảng.
9. Bấm `Xác nhận Up bài`.

Khi upload thành công, cột trạng thái có chữ `Link`. Bấm vào chữ này để mở trang bài vừa tạo.
Nếu mã bài đã tồn tại trên web đích, dòng đó sẽ báo `Bài đã tồn tại`, bị bỏ qua hoàn toàn và các bài khác vẫn tiếp tục được xử lý.

## Ngôn ngữ mặc định

HNOJ:

- `C++17`
- `Pascal`
- `Python 3`
- `Scratch`

HNCode:

- `C++17`
- `C++20`
- `Pascal`
- `Python 3`
- `PyPy 3`

TinHocTre:

- `C++17`
- `C++20`
- `Pascal`
- `Python 3`
- `PyPy 3`
- `Scratch`

Nếu admin form của một hệ thống không hỗ trợ trực tiếp field nào đó, backend bỏ qua an toàn và ghi chú trong log.

## Bộ test

Tool dùng một trong hai cách:

- Có `gentest_<ma_bai>.py`: chạy file này để sinh zip test.
- Không có gentest nhưng có sẵn zip test: dùng trực tiếp zip tìm được.

Ví dụ bài `Tổng bi`, mã `tongbi` hoặc `tht26_tongbi`, tool thử tìm:

- `tongbi.zip`
- `tht26_tongbi.zip`
- `1_tht26_tongbi.zip`
- `tongbi_test.zip`
- `tongbi_tests.zip`

Nếu không có file lời giải tương ứng, tool vẫn tạo bài và upload test; chỉ bỏ qua lượt nộp thử của ngôn ngữ đó.

## File Markdown tổng hợp nhiều đề

Tab `Up bài` cũng hỗ trợ file `.md` tổng hợp nhiều đề bài trong cùng một file. Cấu trúc mỗi bài:

```markdown
# Bài 1. Xếp mâm cơm | tht26kv_xepmamcom

Nội dung đề bài...

# Bài 2. Ghép khúc gỗ | tht26kv_ghepkhucgo

Nội dung đề bài...
```

Khi bấm `Chuẩn bị dữ liệu`, tool tự tách từng heading `# Bài n. Tên bài | mã_bài` thành một bài riêng. Vì file này chỉ có đề, bảng chuẩn bị sẽ mặc định bỏ tích `Up test`; nếu cần upload test thì dùng file zip bộ bài hoặc thêm test/gentest theo luồng zip cũ.

## Tab Chuyển bài

Luồng sử dụng:

1. Chọn nguồn: `HNOJ`, `HNCode` hoặc `TinHocTre`.
2. Chọn đích: `HNOJ`, `HNCode` hoặc `TinHocTre`.
3. Chỉnh thông số đích nếu cần:
   - Giới hạn thời gian mặc định.
   - Giới hạn bộ nhớ mặc định.
   - Ngôn ngữ cho phép ở đích.
   - Người tạo, dạng đề, nhóm bài trong phần mở rộng.
   - `Áp dụng cho tất cả các bài`: lấy time/memory mặc định điền xuống toàn bộ bảng.
   - `Mặc định`: trả time/memory của từng bài về thông số lấy từ nguồn.
4. Nhập danh sách mã bài cần chuyển, cách nhau bằng dấu cách, dấu phẩy hoặc xuống dòng.
5. Bấm `Chuẩn bị dữ liệu`.
6. Bảng sẽ hiển thị:
   - Mã bài.
   - Tên bài toán.
   - Time limit.
   - Memory limit.
   - Link `Bộ test` trỏ tới `/problem/<ma_bai>/test_data`.
   - Số lượng test.
   - Trạng thái.
7. Có thể sửa mã bài, tên bài, time limit, memory limit trước khi bấm `Xác nhận chuyển bài`.

Khi chuyển thành công, cột trạng thái có chữ `Link` để mở trang bài ở hệ thống đích.
Nếu mã bài đích đã tồn tại, dòng đó sẽ báo `Bài đã tồn tại`, bị bỏ qua và các dòng khác vẫn tiếp tục chuyển.

Riêng nguồn `TinHocTre`, tool đăng nhập qua `/accounts/login/` thay vì admin form `/admin/judge/problem/add/`. Nếu TinHocTre bật WAF/challenge và không trả form đăng nhập, hãy dùng ô `Cookie TinHocTre` trong tab `Tài khoản & Hướng dẫn`:

1. Mở `https://tinhoctre.vn` trên trình duyệt và đăng nhập admin.
2. Mở DevTools `F12` → tab `Network`.
3. Bấm vào một request tới `tinhoctre.vn`, ví dụ `/problem/<ma_bai>/edit`.
4. Trong `Request Headers`, copy nguyên dòng `Cookie`.
5. Dán vào ô `Cookie TinHocTre`, bấm `Lưu tạm`, rồi chạy lại `Chuyển bài`.

Trên máy local có thể dùng cách tiện hơn:

1. Bấm `Mở Chrome đăng nhập TinHocTre`.
2. Đăng nhập trong cửa sổ Chrome riêng vừa mở và đảm bảo truy cập được `https://tinhoctre.vn/admin/judge/problem/add/`.
3. Quay lại tool, bấm `Lấy cookie từ Chrome`.
4. Tool tự điền Cookie TinHocTre, lưu tạm và kiểm tra cookie mở được form admin tạo bài.

## Tab Chuyển contest

Tab này dùng cho các contest kiểu DMOJ/VNOJ trên `HNOJ`, `HNCode`, `TinHocTre`, và nguồn phụ `HNOJ Contest` (`https://contest.hnoj.edu.vn`).

Luồng sử dụng:

1. Chọn `Nguồn` và `Đích`.
2. Nhập danh sách mã contest, mỗi mã một dòng hoặc cách nhau bằng dấu cách.
3. Giữ `Nếu bài đã có ở đích thì dùng lại bài đó` để tránh tạo trùng problem.
4. Giữ `Tự chuyển bài/test còn thiếu trước khi tạo contest` nếu muốn tool tự kéo đề và test cho các bài chưa có ở đích.
5. Bấm `Chuẩn bị dữ liệu` để xem tên contest, thời gian và danh sách bài.
6. Bấm `Xác nhận chuyển contest`.

Tool chỉ chuyển contest, problem và test. Tool không chuyển bài nộp của học sinh.

Trong bảng chuẩn bị dữ liệu, mỗi contest có bảng con liệt kê từng bài, gồm mã bài, điểm, thứ tự, trạng thái và ô chọn/bỏ chọn bài đó khi chuyển.

Khi chuyển bài/contest, nếu đề nguồn chỉ có file PDF mà không có nội dung Markdown, tool tự tạo mô tả dạng link `Tải file đề bài`. Nếu đề dùng ảnh hoặc link tương đối như `/martor/...`, `/pdf/...`, tool tự đổi sang URL tuyệt đối của web nguồn để khi sang web đích vẫn mở được.

Sau khi bấm `Chuẩn bị dữ liệu`, trạng thái chuẩn bị của phần chuyển contest được lưu xuống `.runtime/contest_transfer_<prepare_id>/state.json`. Vì vậy nếu request xác nhận đi sang worker khác hoặc service vừa restart nhẹ, nút `Xác nhận chuyển contest` vẫn có thể tiếp tục dùng dữ liệu đã chuẩn bị.

Nếu contest đã tồn tại ở đích, tool báo rõ `Contest đã tồn tại` và hiển thị `Link`, không tự ghi đè setup cũ.

## Tab Tạo contest

Tab này tạo contest cơ bản từ các mã bài đã có sẵn trên web đích.

Nhập:

- Web đích.
- Mã contest.
- Tên contest.
- Thời gian bắt đầu/kết thúc, định dạng ví dụ `2026-05-17 10:00:00`.
- Danh sách mã bài.

Sau khi tạo xong, người dùng có thể vào admin của web đích để chỉnh setup chi tiết hơn.

## Script dòng lệnh

Các script dòng lệnh vẫn dùng được để dry-run hoặc xử lý riêng từng site.

```powershell
python upload_tinhoctre_batch.py "duong_dan_file_zip.zip" --dry-run
python upload_hncode_batch.py "duong_dan_file_zip.zip" --dry-run
python upload_hnoj_batch.py "duong_dan_file_zip.zip" --dry-run
```

Chỉ xử lý một vài bài:

```powershell
python upload_tinhoctre_batch.py "duong_dan_file_zip.zip" --only tht26_tongbi tht26_quatang
```

## Đóng gói sang máy khác

Các file cần giữ:

- `web_app.py`
- `upload_tinhoctre_batch.py`
- `upload_hncode_batch.py`
- `upload_hnoj_batch.py`
- `transfer_tinhoctre_to_hncode.py`
- `requirements.txt`
- `README.md`
- `PROMPT_NANG_CAP_CHUYEN_BAI.md`

Không cần đóng gói các thư mục sinh tạm như `.runtime`, `__pycache__`, `*_upload_artifacts`.
