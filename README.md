# Tool HNCode

Project hỗ trợ chuẩn bị dữ liệu, tạo bài mới, upload test, nộp thử lời giải và chuyển bài giữa 3 hệ thống:

- HNOJ: `https://hnoj.edu.vn`
- HNCode: `https://hncode.edu.vn`
- TinHocTre: `https://tinhoctre.vn`

Tool ưu tiên tạo bài qua admin form:

- `https://hnoj.edu.vn/admin/judge/problem/add/`
- `https://tinhoctre.vn/admin/judge/problem/add/`
- `https://hncode.edu.vn/admin/judge/problem/add/`

Ghi chú HNCode: trang upload test đúng là
`https://hncode.edu.vn/problem/<ma_bai>/test_data`. Trang này dùng
FineUploader gọi endpoint con `/problem/<ma_bai>/test_data/upload`. Nếu server
trả lỗi dạng `Read-only file system: /mnt/efs/problems/...` thì đây là lỗi ghi
storage phía HNCode; tool đã gửi đúng endpoint nhưng backend HNCode chưa lưu
được file test. Form HNCode mới cũng bắt buộc mỗi test có
`batch_scoring=sum`, tool đã tự gửi field này khi lưu metadata test.
Trước khi upload lên HNCode, tool tự chuẩn hoá zip test về dạng phẳng
`01.inp/01.out`, `02.inp/02.out`, ... để tránh lỗi do thư mục con hoặc tên file
test không đồng nhất.
Khi upload lại test HNCode, tool tự xoá toàn bộ test cũ trước rồi mới upload bộ
test mới, nên có thể thay bộ nhiều test bằng bộ ít test hơn.

Với chức năng tạo/chuyển contest: nếu mã contest đã tồn tại ở đích, tool không
báo lỗi mà mở form sửa contest và thêm các bài chưa có vào cuối danh sách theo
đúng thứ tự mã bài gửi lên. Bài đã có sẵn trong contest được bỏ qua để tránh
trùng.
Riêng HNOJ, trường `max_submissions` của bài trong contest phải để trống nếu
muốn không giới hạn lượt nộp; đặt `0` sẽ bị HNOJ hiểu là không thể nộp và báo
lỗi khi thêm bài vào contest.

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
Tên bài | Mã bài | Điểm | Các Tags
```

## Tab Up nhiều bài

Luồng sử dụng:

1. Chọn web đích: `HNOJ`, `HNCode` hoặc `TinHocTre`.
2. Chọn file zip bộ bài hoặc file Markdown tổng hợp bằng cách dán đường dẫn hoặc bấm `Chọn file`.
   - File zip dùng cấu trúc: mỗi bài có file đề, test zip hoặc `gentest`, lời giải Markdown nếu có.
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
6. Tích `Bỏ dòng đầu tiên trong file đề bài` nếu file Markdown có dòng đầu dạng `Tên bài | Mã bài | Điểm | Các Tags` và không muốn đưa dòng này vào đề bài.
7. Nếu mã bài đã có trên web đích và muốn cập nhật lại, tích:
   - `Ghi đè đề bài nếu mã bài đã có`: cập nhật lại tên và nội dung đề.
   - `Ghi đè test nếu mã bài đã có`: upload lại bộ test mới cho bài đã tồn tại.
8. Bấm `Chuẩn bị dữ liệu`.
9. Kiểm tra bảng bài, sửa mã/tên nếu cần. Có nút `Chọn tất cả` và `Bỏ chọn tất cả` cho bảng.
10. Bấm `Xác nhận Up nhiều bài`.

Khi upload thành công, cột trạng thái có chữ `Link`. Bấm vào chữ này để mở trang bài vừa tạo.
Nếu mã bài đã tồn tại trên web đích và không tích ghi đè, dòng đó sẽ báo `Bài đã tồn tại`, bị bỏ qua hoàn toàn và các bài khác vẫn tiếp tục được xử lý.

## Tab Up 1 bài

Tab này dùng khi chỉ cần tạo hoặc cập nhật một bài, không cần đóng gói cả bộ zip.

Luồng sử dụng:

1. Chọn `Web đích`.
2. Nhập `Mã bài`, `Tên bài toán`, `Điểm`, `Tag` nếu cần.
   - Với HNCode, mã bài được chuẩn hóa về chữ thường và số, ví dụ `nc1_calfunc1` thành `nc1calfunc1`.
   - Ô `Tag` có thể để trống. Nếu nhập số ID, tool dùng số đầu tiên làm `Problem types`.
3. Chỉnh `Giới hạn thời gian` và `Giới hạn bộ nhớ`.
   - Mặc định time là `1.0`.
   - Mặc định memory là `1024M`, khi gửi form sẽ đổi về `1048576` KB.
4. Mặc định bật `Cho phép điểm thành phần`.
5. Nếu bài đã có và muốn cập nhật lại đề/test, tích `Ghi đè nếu mã bài đã có`.
6. Mở từng phần cần dùng:
   - `Đề bài`: dán Markdown hoặc chọn file `.md`.
   - `Code sinh test`: dán `gentest` Python hoặc chọn file `.py`; cũng có thể chọn zip test có sẵn.
   - `Lời giải / hướng dẫn`: dán Markdown hoặc chọn file `.md`.
7. Bấm `Chuẩn bị dữ liệu` để tool kiểm tra:
   - Có đề hay không.
   - Có sinh được test hay không.
   - Số test trong zip.
   - Có lời giải Markdown hay không.
8. Kiểm tra bảng, có thể sửa mã, tên, điểm, time, memory, rồi bấm `Xác nhận Up 1 bài`.

Thiếu phần nào thì tool không up phần đó. Ví dụ chỉ có đề thì chỉ tạo/cập nhật đề; có đề và test thì tạo/cập nhật cả hai.

Ghi chú về code sinh test:

- Tool chạy tự động file Python `gentest`.
- Với C++ generator, tool compile bằng `g++`, chạy file sinh test, rồi dùng zip do generator tạo hoặc tự nén các cặp `.inp/.out`.
- Nếu nội dung bị Markdown đổi `__name__` thành `**name**`, tool tự sửa lại thành `if __name__ == "__main__":`.
- Nếu gentest in tiếng Việt hoặc emoji trên Windows, tool ép stdout/stderr UTF-8 để tránh lỗi encoding.

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

Ghi chú mã bài HNCode: khi tạo bài mới, HNCode mới yêu cầu mã dạng chữ thường và số. Tuy nhiên một số bài cũ có thể vẫn có dấu gạch dưới. Nếu mã có gạch dưới đã tồn tại, tool giữ đúng mã cũ để ghi đè đề/test; nếu tạo bài mới thì tool mới tự đổi sang dạng hợp lệ.

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

Cấu trúc zip bộ bài nên dùng:

```text
bo_bai.zip
├─ tht26_tongbi.md
├─ gentest_tht26_tongbi.py
├─ sol_tht26_tongbi.py
├─ sol_tht26_tongbi.cpp
├─ tht26_quatang.md
├─ tht26_quatang.zip
├─ sol_tht26_quatang.py
└─ sol_tht26_quatang.cpp
```

Trong đó:

- `<ma_bai>.md`: file đề bài, dòng đầu nên là `Tên bài | Mã bài | Điểm | Các Tags`.
- `gentest_<ma_bai>.py`: file sinh test. Nếu có file này, tool ưu tiên chạy để tạo `<ma_bai>.zip`.
- `<ma_bai>.zip`: bộ test có sẵn, dùng khi không có file `gentest`.
- `sol_<ma_bai>.md`: lời giải/hướng dẫn Markdown để up vào trang lời giải nếu bật trong bảng.
- `sol_<ma_bai>.cpp`, `sol_<ma_bai>.py`: lời giải để nộp thử nếu bật tùy chọn nộp thử.

File mẫu 1 bài đơn giản nằm ở:

```text
samples/bo_mau_1_bai_tonghaiso.zip
```

Ví dụ bài `Tổng bi`, mã `tongbi` hoặc `tht26_tongbi`, tool thử tìm:

- `tongbi.zip`
- `tht26_tongbi.zip`
- `1_tht26_tongbi.zip`
- `tongbi_test.zip`
- `tongbi_tests.zip`

Nếu không có file lời giải tương ứng, tool vẫn tạo bài và upload test; chỉ bỏ qua lượt nộp thử của ngôn ngữ đó.

## File Markdown tổng hợp nhiều đề

Tab `Up nhiều bài` cũng hỗ trợ file `.md` tổng hợp nhiều đề bài trong cùng một file. Cấu trúc mỗi bài:

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

1. Bấm `Mở Edge đăng nhập TinHocTre`.
2. Đăng nhập trong cửa sổ Edge vừa mở và đảm bảo truy cập được `https://tinhoctre.vn/admin/judge/problem/add/`.
3. Quay lại tool, bấm `Lấy cookie từ Edge`.
4. Tool tự điền Cookie TinHocTre, lưu tạm và kiểm tra cookie mở được form admin tạo bài.

Tool ưu tiên Edge profile mặc định để dùng lại mật khẩu đã lưu trong Edge. Nếu bấm `Lấy cookie từ Edge` không kết nối được, hãy đóng hết cửa sổ Edge đang mở rồi bấm `Mở Edge đăng nhập TinHocTre` lại.

Nhanh nhất: bấm `Lấy cookie nhanh từ Edge`. Tool sẽ tự đóng Edge, mở lại Edge bằng profile mặc định, lấy Cookie TinHocTre và kiểm tra quyền admin. Edge thường khôi phục lại các tab cũ sau khi mở lại.

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

Nếu contest đã tồn tại ở đích, tool mở form sửa contest và thêm các bài chưa có vào cuối danh sách theo đúng thứ tự gửi lên. Bài đã có trong contest được bỏ qua để tránh trùng.

## Tab Tạo contest

Tab này tạo contest cơ bản từ các mã bài đã có sẵn trên web đích.

Nhập:

- Web đích.
- Mã contest.
- Tên contest.
- Thời gian bắt đầu/kết thúc, định dạng ví dụ `2026-05-17 10:00:00`.
- Danh sách mã bài.

Sau khi tạo xong, người dùng có thể vào admin của web đích để chỉnh setup chi tiết hơn.

## Tab Tạo Lesson

- Nhập link lesson HNCode đã có và danh sách mã bài hoặc link bài.
- Tool giữ đúng thứ tự nhập, nhận cả link `/problem/<ma_bai>` và `/contest/<contest>/problems/<ma_bai>`.
- Bấm `Chuẩn bị dữ liệu` để xem tên bài, điểm và trạng thái trước khi thêm.
- Bài đã có trong lesson hoặc không tồn tại trên HNCode được báo rõ và tự động bỏ qua.
- Có thể sửa điểm từng bài hoặc áp dụng một mức điểm cho toàn bộ bảng.

## Tab Contest → Lesson

Tab này sao chép danh sách bài từ một contest HNCode/HNOJ vào một lesson HNCode.

HNCode hiện dùng domain chính `https://hncode.edu.vn`. Tool vẫn nhận link cũ `https://oj.hncode.edu.vn` ở một số ô nhập cũ, nhưng sẽ ưu tiên chuẩn hóa sang `https://hncode.edu.vn` khi xử lý bài/contest/lesson.

Luồng sử dụng:

1. Chọn nguồn contest `HNCode` hoặc `HNOJ`. Nếu URL có `hnoj.edu.vn` hoặc `hncode.edu.vn`, backend sẽ tự nhận lại nguồn theo URL để tránh chọn nhầm.
2. Nhập URL contest nguồn, ví dụ `https://hncode.edu.vn/contest/nt26exam01`.
3. Nhập URL lesson đích, ví dụ `https://hncode.edu.vn/course/nt26_tuyen3/lesson/3123`.
4. Bấm `Chuẩn bị dữ liệu`.
5. Bảng sẽ hiển thị từng bài theo đúng thứ tự trong contest, gồm STT, mã bài, tên bài, điểm lesson và trạng thái.
6. Chọn/bỏ chọn từng bài, chỉnh điểm lesson nếu cần. Có thể nhập `Điểm chung` rồi bấm `Áp dụng điểm cho tất cả bài`.
7. Bấm `Sao chép bài`.

Tool mở form sửa lesson `edit_lessons_new/<lesson_id>`, giữ nguyên nội dung lesson và quiz hiện có, chỉ thêm các problem còn thiếu vào cuối danh sách. Nếu bài đã có trong lesson, dòng đó báo `Đã có trong lesson` và bị bỏ qua để tránh trùng.

Để chống thay đổi giao diện của HNCode, tool dùng parser chung cho contest và nhận các dạng link bài:

- Link bài cũ: `/problem/<ma_bai>`.
- Link bài contest mới: `/contest/<contest>/problems/<ma_bai>`.
- Header bảng xếp hạng có `.problem-code`.

Khi HNCode trả điểm contest dạng `1p`, tool đổi thành `1` để điền vào điểm lesson. Nếu điểm trong bảng contest là một số lớn không phù hợp làm điểm lesson, người dùng có thể chỉnh lại trong bảng trước khi bấm `Sao chép bài`.

API nội bộ tương ứng:

```http
POST /api/prepare-contest-to-lesson
POST /api/confirm-contest-to-lesson
```

Luồng API: gọi `prepare`, lấy `prepare_id` và `rows`, chỉnh `rows[].selected` hoặc `rows[].score` nếu cần, rồi gọi `confirm`.

Ví dụ payload `prepare`:

```json
{
  "source": "hncode",
  "account": {"username": "hncode", "password": "..."},
  "source_account": {"username": "hncode", "password": "..."},
  "contest_url": "https://hncode.edu.vn/contest/nt26exam01",
  "lesson_url": "https://hncode.edu.vn/course/nt26_tuyen3/lesson/3123"
}
```

`confirm` sẽ thêm từng bài một thay vì gửi cả lô, để nếu HNCode bỏ qua hoặc lỗi một bài thì các bài khác vẫn được xử lý và trạng thái từng bài vẫn rõ ràng.

## Tool lẻ: Lấy list mã bài

Tool này lấy danh sách mã bài theo đúng thứ tự để copy nhanh sang các chức năng khác.

Nguồn hỗ trợ:

- `HNCode / Contest`: nhập URL dạng `https://hncode.edu.vn/contest/<ma_contest>`.
- `HNCode / Lesson`: nhập URL dạng `https://hncode.edu.vn/course/<course>/lesson/<lesson_id>`.
- `HNOJ / Contest`: nhập URL dạng `https://hnoj.edu.vn/contest/<ma_contest>`.

Kết quả gồm:

- Ô textarea chứa mỗi mã bài một dòng để copy.
- Bảng chi tiết gồm STT, mã bài, tên bài, điểm nếu đọc được.

API nội bộ:

```http
POST /api/misc/list-problem-codes
```

Payload mẫu:

```json
{
  "site": "hncode",
  "source_type": "contest",
  "url": "https://hncode.edu.vn/contest/nt26exam01",
  "account": {"username": "hncode", "password": "..."}
}
```

Với HNCode Lesson, đổi `source_type` thành `lesson`.

## Tab Up Quiz

Tab này up danh sách câu hỏi lên HNCode Quiz qua form:

```text
https://oj.hncode.edu.vn/quiz/questions/create/
```

Tool hỗ trợ 4 loại câu hỏi:

- `MC`: Trắc nghiệm 1 đáp án.
- `MA`: Trắc nghiệm nhiều đáp án.
- `SA`: Trả lời ngắn.
- `TF`: Đúng / Sai.

Nhãn để trống. Hai lựa chọn `Xáo trộn lựa chọn` và `Công khai` được chọn trực tiếp trên giao diện.
Trước khi up thật, bấm `Chuẩn bị dữ liệu` để tool kiểm tra format và hiển thị bảng gồm `STT`, `Tiêu đề`, `Loại`, `Trạng thái`. Khung `Thông tin trả về` sẽ ghi chi tiết từng câu hợp lệ hoặc lỗi cụ thể.

Format mỗi câu hỏi:

```text
Loại: MC
Tiêu đề: Câu hỏi ví dụ 1
Nội dung:
Trong Python, hàm nào dùng để in ra màn hình?
Lựa chọn:
- A. input()
- B. print()
- C. len()
- D. range()
Đáp án: B
Giải thích:
`print()` dùng để in dữ liệu ra màn hình.
---
Loại: MA
Tiêu đề: Số nguyên tố
Nội dung:
Những số nào sau đây là số nguyên tố?
Lựa chọn:
- A. 2
- B. 3
- C. 4
- D. 9
Đáp án: A, B
---
Loại: SA
Tiêu đề: Kết quả phép tính
Nội dung:
Tính 6 * 7.
Đáp án:
- 42
- bốn mươi hai
---
Loại: TF
Tiêu đề: Đúng sai
Nội dung:
Python là một ngôn ngữ lập trình.
Đáp án: Đúng
```

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
