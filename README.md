# Tool OJ

Project hỗ trợ chuẩn bị dữ liệu, tạo bài mới, upload test, nộp thử lời giải và sao chép dữ liệu giữa 4 hệ thống:

- HNOJ: `https://hnoj.edu.vn`
- HNCode: `https://hncode.edu.vn`
- TinHocTre: `https://tinhoctre.vn`
- LQDOJ: `https://lqdoj.edu.vn`

Tài khoản admin được nhập trong tab `Tài khoản & Hướng dẫn`. Tool không hard-code mật khẩu trong source.

Tool ưu tiên tạo bài qua admin form:

- `https://hnoj.edu.vn/admin/judge/problem/add/`
- `https://tinhoctre.vn/admin/judge/problem/add/`
- `https://hncode.edu.vn/admin/judge/problem/add/`
- `https://lqdoj.edu.vn/admin/judge/problem/add/`

LQDOJ có thể bật Cloudflare challenge. Khi đăng nhập trực tiếp bị chặn, bấm `Mở Edge đăng nhập LQDOJ`, đăng nhập admin trong cửa sổ vừa mở, rồi bấm `Lấy cookie LQDOJ từ Edge`. Cookie chỉ lưu tạm trong `localStorage` của trình duyệt dùng Tool OJ.

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

- Khi up hoặc chuyển bài lên `HNOJ` và `LQDOJ`, đề bài dùng `~` thay cho `$`.
- Khi up hoặc chuyển bài lên `HNCode` và `TinHocTre`, đề bài dùng `$` thay cho `~`.

## Chạy giao diện web

```powershell
cd C:\Users\Admin\Documents\ChuyenBai
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

Lưu tạm tài khoản admin của 4 trang trên trình duyệt máy đang dùng bằng `localStorage`.

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

1. Chọn web đích: `HNOJ`, `HNCode`, `TinHocTre` hoặc `LQDOJ`.
2. Chọn file zip bộ bài hoặc file Markdown tổng hợp bằng cách dán đường dẫn hoặc bấm `Chọn file`.
   - File zip dùng cấu trúc: mỗi bài có đề Markdown, đề PDF hoặc cả hai; test zip hoặc `gentest`; lời giải Markdown nếu có.
   - File Markdown tổng hợp dùng để up đề bài, mỗi bài bắt đầu bằng dòng `# Bài 1. Tên bài | ma_bai`.
3. Kiểm tra `Giới hạn thời gian`, `Giới hạn bộ nhớ`, `Ngôn ngữ cho phép`.
4. Bấm `Mở rộng thông tin khác` nếu cần xem/sửa nhóm thông tin phụ:
   - Người tạo (Creators): mặc định `mrtee`.
   - Dạng đề (Problem types): `Chưa phân loại`.
   - Nhóm bài (Problem group): `Chưa phân loại`.

Mặc định khi không có `Problem types` hoặc `Problem group`, hoặc tag không khớp với form của trang đích:

- HNCode: `problemtype = 591`, `problemgroup = 105`.
- TinHocTre: `problemtype = 13`, `problemgroup = 13`.
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
   - Với HNCode và TinHocTre, mã bài được chuẩn hóa về chữ thường, số và dấu gạch dưới; dấu gạch dưới được giữ nguyên.
   - Ô `Tag` có thể để trống. Nếu nhập số ID, tool dùng số đầu tiên làm `Problem types`.
3. Chỉnh `Giới hạn thời gian` và `Giới hạn bộ nhớ`.
   - Mặc định time là `1.0`.
   - Mặc định memory là `1024M`, khi gửi form sẽ đổi về `1048576` KB.
4. Mặc định bật `Cho phép điểm thành phần`.
5. Nếu bài đã có và muốn cập nhật lại đề/test, tích `Ghi đè nếu mã bài đã có`.
6. Mở từng phần cần dùng:
   - `Đề bài`: dán Markdown, chọn file `.md` hoặc chọn file `.pdf`.
   - `Code sinh test`: dán `gentest` Python hoặc chọn file `.py`; cũng có thể chọn zip test có sẵn.
   - `Lời giải / hướng dẫn`: dán Markdown hoặc chọn file `.md`.
7. Bấm `Chuẩn bị dữ liệu` để tool kiểm tra:
   - Có đề hay không.
   - Có sinh được test hay không.
   - Số test trong zip.
   - Có lời giải Markdown hay không.
8. Kiểm tra bảng, có thể sửa mã, tên, điểm, time, memory, rồi bấm `Xác nhận Up 1 bài`.

Thiếu phần nào thì tool không up phần đó. Ví dụ chỉ có PDF thì tool tạo bài với mô tả ngắn và upload PDF; có đề và test thì tạo/cập nhật cả hai.

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

Ghi chú mã bài HNCode: mã bài mới được phép dùng chữ thường, số và dấu gạch dưới theo dạng `^[a-z0-9_]+$`; tool không bỏ dấu gạch dưới.

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
├─ tht26_tongbi.pdf
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
- `<ma_bai>.pdf`: file đề bài PDF. Có thể dùng cùng file Markdown hoặc dùng riêng; khi chỉ có PDF, tên/mã lấy từ tên file và các metadata thiếu dùng giá trị mặc định.
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

1. Chọn nguồn: `HNOJ`, `HNCode`, `TinHocTre` hoặc `LQDOJ`.
2. Chọn đích: `HNOJ`, `HNCode`, `TinHocTre` hoặc `LQDOJ`.
3. Chỉnh thông số đích nếu cần:
   - Giới hạn thời gian mặc định.
   - Giới hạn bộ nhớ mặc định tính theo MB, mặc định `1024` MB.
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
   - Memory limit tính theo MB.
   - Link `Bộ test` trỏ tới `/problem/<ma_bai>/test_data`.
   - Số lượng test.
   - Trạng thái.
7. Có thể sửa mã bài, tên bài, time limit, memory limit trước khi bấm `Xác nhận chuyển bài`.
8. Nếu mã bài đã có ở đích, bảng báo rõ và mặc định không ghi đè. Chỉ khi tích `Ghi đè nếu trùng`, tool mới cập nhật đề/metadata/test theo các phần đang được chọn.

Các ô memory trong bảng Chuyển bài luôn hiển thị theo MB. Tool tự đổi sang KB khi gửi form quản trị; cũng chấp nhận giá trị có hậu tố như `512MB`, `1GB` hoặc `1048576KB`.

Khi chuyển thành công, cột trạng thái có chữ `Link` để mở trang bài ở hệ thống đích.
Nếu mã bài đích đã tồn tại và không tích ghi đè, tool dùng nguyên bài đích, không thay đề hoặc test. Mọi chức năng chuyển đều là **sao chép**; tool không sửa hoặc xóa dữ liệu nguồn.

Khi đọc bộ test nguồn, tool hỗ trợ cả form dùng `<input>` và form mới dùng `<select>` cho tên file test. Nếu trang test không còn metadata từng case, tool suy ra các cặp `.inp/.out`, `.in/.out`, `.in/.ans` hoặc `.input/.output` trực tiếp từ file zip.

TinHocTre hiện dùng hệ thống mới tương tự HNCode. Tool đăng nhập trực tiếp bằng tài khoản trong tab `Tài khoản & Hướng dẫn` và dùng admin form `/admin/judge/problem/add/`; luồng cookie/Edge cũ không còn nằm trong giao diện chính.

## Tab Chuyển contest

Tab này dùng cho contest trên `HNOJ`, `HNCode`, `TinHocTre` và `LQDOJ`.

Luồng sử dụng:

1. Chọn `Nguồn` và `Đích`.
2. Nhập danh sách mã contest, mỗi mã một dòng hoặc cách nhau bằng dấu cách.
3. Bài đã có ở đích luôn được dùng lại nguyên trạng để tránh tạo trùng problem.
4. Giữ `Tự chuyển bài/test còn thiếu trước khi tạo contest` nếu muốn tool tự kéo đề và test cho các bài chưa có ở đích.
5. Bấm `Chuẩn bị dữ liệu` để xem tên contest, thời gian và danh sách bài.
6. Bấm `Xác nhận chuyển contest`.

Tool chỉ sao chép contest, problem và test. Tool không chuyển bài nộp của học sinh và không thay đổi nguồn.

Trong bảng chuẩn bị dữ liệu, mỗi contest có bảng con liệt kê từng bài, gồm mã bài, điểm, thứ tự, trạng thái và ô chọn/bỏ chọn bài đó khi chuyển.

Khi chuyển bài, tool dò và tải file PDF thực tế từ bài nguồn rồi upload lại vào bài đích trên cả HNOJ, HNCode và TinHocTre. Nếu nguồn có cả Markdown và PDF, đích nhận cả hai; nếu chỉ có PDF, tool dùng mô tả ngắn để bài hợp lệ và gắn PDF trực tiếp. Nếu không tải được PDF nhưng còn URL công khai, tool mới dùng liên kết làm phương án dự phòng. Ảnh hoặc link tương đối như `/martor/...`, `/pdf/...` vẫn được đổi sang URL tuyệt đối của web nguồn.

Sau khi bấm `Chuẩn bị dữ liệu`, trạng thái chuẩn bị của phần chuyển contest được lưu xuống `.runtime/contest_transfer_<prepare_id>/state.json`. Vì vậy nếu request xác nhận đi sang worker khác hoặc service vừa restart nhẹ, nút `Xác nhận chuyển contest` vẫn có thể tiếp tục dùng dữ liệu đã chuẩn bị.

Nếu contest đã tồn tại ở đích, tool mở form sửa contest, cập nhật metadata/setup và bổ sung bài còn thiếu. Các bài đã có được cập nhật điểm, thứ tự và các thiết lập contest-problem tương thích, không tạo dòng trùng.

Tool sao chép các thiết lập contest tương thích như tên, mô tả, thời gian, visibility, scoreboard, format, rate/freeze/strict settings, điểm và thiết lập từng bài. Khi chuyển chéo website, ảnh trong mô tả được tải từ nguồn, upload sang website đích và lưu bằng URL tương đối. Link nội bộ như bài, contest, lesson và course cũng được đổi sang đường dẫn tương đối hoặc mã tương ứng ở đích; nội dung không giữ URL tuyệt đối của website nguồn. Tài khoản quản trị, thành viên riêng tư và các quan hệ người dùng không tự động sao chép chéo website vì ID người dùng không dùng chung.

Mỗi bài được xử lý độc lập. Một bài lỗi được ghi rõ trong bảng con và `Thông tin trả về`; tool tiếp tục bài kế tiếp và tiếp tục các contest còn lại. Contest có cả bài thành công và bài lỗi được đánh dấu `Hoàn thành một phần`.

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

Chức năng này chỉ làm việc với HNCode. Nhập URL của một Lesson đã có và danh sách mã bài hoặc link bài HNCode, mỗi bài một dòng. Tool giữ đúng thứ tự nhập, tự bỏ qua bài đã nằm trong Lesson và báo riêng mã bài không tồn tại.

Luồng sử dụng:

1. Nhập link dạng `https://hncode.edu.vn/course/<course>/lesson/<id>`.
2. Nhập danh sách mã bài, link `/problem/<ma_bai>` hoặc link `/contest/<contest>/problems/<ma_bai>`.
3. Nhập điểm mặc định rồi bấm `Chuẩn bị dữ liệu`.
4. Kiểm tra bảng STT, mã bài, tên bài, điểm và trạng thái; có thể sửa điểm từng bài hoặc áp dụng một điểm cho tất cả.
5. Bấm `Thêm bài vào Lesson`. Tool chỉ thêm các dòng được chọn và không thay đổi những bài đã có.

Trạng thái chuẩn bị được lưu trong `.runtime`, vì vậy bước xác nhận vẫn dùng được khi hai request đi vào hai Gunicorn worker khác nhau.

## Tab Contest → Lesson

Tab này sao chép danh sách bài từ một contest HNCode/HNOJ/LQDOJ vào một lesson HNCode/LQDOJ.

HNCode hiện dùng domain chính `https://hncode.edu.vn`. Tool vẫn nhận link cũ `https://oj.hncode.edu.vn` ở một số ô nhập cũ, nhưng sẽ ưu tiên chuẩn hóa sang `https://hncode.edu.vn` khi xử lý bài/contest/lesson.

Luồng sử dụng:

1. Chọn nguồn contest `HNCode`, `HNOJ` hoặc `LQDOJ`, rồi chọn web chứa Lesson đích.
2. Nhập URL contest nguồn, ví dụ `https://hncode.edu.vn/contest/nt26exam01`.
3. Nhập URL lesson đích, ví dụ `https://hncode.edu.vn/course/nt26_tuyen3/lesson/3123`.
4. Bấm `Chuẩn bị dữ liệu`.
5. Bảng sẽ hiển thị từng bài theo đúng thứ tự trong contest, gồm STT, mã bài, tên bài, điểm lesson và trạng thái.
6. Chọn/bỏ chọn từng bài, chỉnh điểm lesson nếu cần. Có thể nhập `Điểm chung` rồi bấm `Áp dụng điểm cho tất cả bài`.
7. Bấm `Sao chép bài`.

Tool mở form sửa lesson `edit_lessons_new/<lesson_id>`, giữ nguyên nội dung lesson và quiz hiện có, chỉ thêm các problem còn thiếu vào cuối danh sách. Nếu bài đã có trong lesson, dòng đó báo `Đã có trong lesson` và bị bỏ qua để tránh trùng.

Nếu problem đã có trên web đích nhưng chưa nằm trong Lesson, tool dùng ID problem đích hiện có. Tool chỉ sao chép problem từ nguồn khi mã đó còn thiếu ở đích.

## Tab Chuyển Lesson

Nhập URL Lesson nguồn và URL Course đích, chọn HNCode/LQDOJ ở hai phía rồi bấm `Chuẩn bị dữ liệu`. Bảng hiển thị mã nguồn, mã đích và trạng thái từng bài. Khi xác nhận:

- Lesson cùng tên đã có ở Course đích: dùng lại, cập nhật tên/mô tả/điểm/thứ tự/visibility và không tạo trùng.
- Problem đã có ở web đích: dùng lại nguyên trạng.
- Problem còn thiếu: sao chép đề và test rồi gắn ID mới vào Lesson đích.
- Dữ liệu Lesson và problem nguồn chỉ được đọc, không bị sửa.
- Một problem lỗi được ghi vào báo cáo; các problem sau vẫn tiếp tục. Ảnh trong nội dung Lesson được upload sang website đích và dùng URL tương đối; link bài được đổi sang mã bài tương ứng ở đích.
- Quiz trong Lesson được giữ đầy đủ khi sao chép trong cùng một website. Khi chuyển chéo website, tool báo và bỏ qua quiz vì ID câu hỏi/quiz không dùng chung; không tự gắn nhầm quiz theo ID.

## Tab Chuyển Course

Sao chép toàn bộ Lesson và Contest đã chọn giữa HNCode và LQDOJ. Nếu Course đích chưa tồn tại, tool tự tạo Course bằng slug đã nhập rồi sao chép tên, mô tả, trạng thái công khai/mở và organization tương thích từ nguồn. Nếu Course đích đã tồn tại, slug, vai trò và thành viên hiện có được giữ nguyên; organization chỉ được đồng bộ khi tìm thấy organization cùng tên ở đích.

Lesson cùng tên và Contest đã nằm trong Course đích được dùng lại để cập nhật metadata/setup và bổ sung bài còn thiếu. Tool giữ điểm/thứ tự Lesson, điểm/thứ tự Contest trong Course, mô tả và cấu hình Contest, thứ tự/điểm từng bài; problem trùng được dùng lại theo ID ở website đích. Ảnh được chuyển sang storage của đích; link nội bộ được lưu tương đối, không giữ domain HNCode/LQDOJ nguồn. Nếu một Lesson, Contest hoặc problem lỗi, dòng đó được ghi báo cáo và tiến trình tiếp tục với các mục còn lại.

LQDOJ áp dụng quy tắc mã chặt hơn:

- Mã bài: `^[a-z0-9]+$`, tối đa 30 ký tự.
- Mã contest: `^[a-z0-9]+$`, tối đa 20 ký tự.
- Mã course: chữ, số và dấu gạch ngang; không dùng dấu gạch dưới.

Tool hiển thị mã đã chuẩn hóa trong bước chuẩn bị để người dùng kiểm tra trước khi thực hiện.

Các ô URL Contest/Lesson/Course tự nhận diện HNCode, HNOJ hoặc LQDOJ và đồng bộ ô chọn website trước khi gửi yêu cầu. Backend cũng kiểm tra domain; nếu URL và website được chọn không khớp, tool báo rõ hai website thay vì chỉ trả lỗi HTTP 404.

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

## Tool lẻ: Xuất đề bài ra Markdown

Tool lấy đề bài từ `HNOJ`, `HNCode` hoặc `TinHocTre`. Dữ liệu nhập hỗ trợ:

- Link Contest hoặc mã contest.
- Link Lesson trên HNCode/TinHocTre.
- Một mã bài, nhiều mã bài hoặc các link `/problem/<ma_bai>`.

Chọn một trong hai kiểu kết quả:

- `Mỗi bài một file đề`: tải ZIP chứa các file `<ma_bai>.md`. Dòng đầu mỗi file là `Tên bài | Mã bài`.
- `Tất cả trong một file đề`: tải một file `tong_hop_de_bai_<web>.md`, các bài giữ đúng thứ tự nguồn.

Tool ưu tiên đọc Markdown gốc từ trang sửa bài bằng tài khoản admin. Liên kết ảnh tương đối được chuyển thành URL tuyệt đối; nếu một bài lỗi, các bài còn lại vẫn được xuất và bảng kết quả hiển thị lỗi riêng.

API nội bộ:

```http
POST /api/misc/export-problem-statements
GET  /api/misc/download-problem-statements/<export_id>
```

Payload mẫu:

```json
{
  "site": "hncode",
  "input_type": "contest",
  "source_input": "https://hncode.edu.vn/contest/nt26exam01",
  "mode": "separate",
  "account": {"username": "...", "password": "..."}
}
```

`input_type` nhận `auto`, `contest`, `lesson`, `codes`; `mode` nhận `separate` hoặc `combined`.

## Tool lẻ: Lấy last submissions

Tool hỗ trợ ba nguồn `HNOJ`, `HNCode`, `TinHocTre` và tự nhận hai cấu trúc ZIP:

- ZIP mã nguồn có tên file dạng `<submission_id>_<tài khoản>.<ngôn_ngữ>`.
- Gói export có `submissions.json`, `submissions.csv` và thư mục `sources`; tên mã nguồn có thể dạng `<tài khoản>__sub<submission_id>__<trạng_thái>_<điểm>.<phần_mở_rộng>`.

- Tool dùng tài khoản đã nhập ở tab Tài khoản để đọc mã bài từ trang `/submission/<id>`.
- Nếu ZIP đã có metadata mã bài trong `submissions.json`, tool dùng trực tiếp và không gọi web; chỉ các dòng thiếu metadata mới cần đăng nhập để bổ sung.
- Với từng cặp `tài khoản + mã bài`, submission có ID lớn nhất được giữ lại.
- ZIP kết quả có cấu trúc `<tài khoản>/<mã_bài>.<ngôn_ngữ>` và file `report.csv`.
- Các submission không đọc được mã bài vẫn được ghi vào báo cáo cùng nguyên nhân lỗi.
- Dữ liệu thư mục `.sb3` theo cấu trúc cũ vẫn được tự động nhận diện.

API giữ nguyên để tương thích giao diện hiện tại:

```http
POST /api/misc/last-submissions
```

Request là `multipart/form-data` gồm `zip_file`, `source` và `account` (JSON chứa thông tin đăng nhập của web nguồn).

## Tab Up Quiz

Tab này up danh sách câu hỏi lên Quiz. Trên giao diện chọn được web đích:

```text
HNCode: https://hncode.edu.vn/quiz/questions/create/
TinHocTre: https://tinhoctre.vn/quiz/questions/create/
```

Với `HNCode`, tool dùng tài khoản HNCode trong tab `Tài khoản & Hướng dẫn`.
Với `TinHocTre`, tool dùng tài khoản TinHocTre trong tab `Tài khoản & Hướng dẫn`.

Tool hỗ trợ 5 loại câu hỏi:

- `MC`: Trắc nghiệm 1 đáp án.
- `MA`: Trắc nghiệm nhiều đáp án.
- `SA`: Trả lời ngắn.
- `FB`: Điền vào chỗ trống.
- `TF`: Đúng / Sai.

Nhãn để trống. Hai lựa chọn `Xáo trộn lựa chọn` và `Công khai` được chọn trực tiếp trên giao diện.
Trước khi up thật, bấm `Chuẩn bị dữ liệu` để tool kiểm tra format và hiển thị bảng gồm `STT`, `Tiêu đề`, `Loại`, `Trạng thái`. Khung `Thông tin trả về` sẽ ghi chi tiết từng câu hợp lệ hoặc lỗi cụ thể.

Khi bấm `Up Quiz`, server khởi động một tác vụ nền và giao diện đọc tiến độ qua
`/api/progress/<progress_id>`. Trạng thái được cập nhật sau từng câu hỏi, vì vậy
việc up danh sách dài không giữ một HTTP request liên tục và tránh lỗi timeout
`524` của Cloudflare. Endpoint đồng bộ `/api/upload-quiz` vẫn được giữ để tương
thích; giao diện sử dụng `/api/upload-quiz-start`.

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
Loại: FB
Tiêu đề: Điền vào chỗ trống
Nội dung:
An và Bình có $5$ viên bi. An có hơn Bình đúng $1$ viên bi.
Vậy An có \_\_\_(1)\_\_\_ viên bi và Bình có \_\_\_(2)\_\_\_ viên bi.
Đáp án:
- Số bi của An: 3
- Số bi của Bình: 2
---
Loại: FB
Tiêu đề: Nhiều cách nhập đáp án
Nội dung:
Điền kết quả đúng vào hai chỗ trống:
$2 + 3 =$ \_\_\_(1)\_\_\_ và tên ngôn ngữ lập trình Python viết thường là \_\_\_(2)\_\_\_.
Đáp án:
- Ô 1: 5 | năm
- Ô 2: python
Giải thích:
Mỗi dòng đáp án tương ứng một ô trống. Các đáp án đúng thay thế cho cùng một ô có thể ngăn bằng dấu `|`, `,` hoặc `;`.
---
Loại: TF
Tiêu đề: Đúng sai
Nội dung:
Python là một ngôn ngữ lập trình.
Đáp án: Đúng
```

Với `FB`, trong `Nội dung` đánh dấu ô trống theo dạng `\_\_\_(1)\_\_\_`, `\_\_\_(2)\_\_\_`, ... để hệ thống nhận đúng vị trí cần điền.
Mỗi dòng trong phần `Đáp án` có dạng `Nhãn: đáp án`, ví dụ `Ô 1: 5 | năm`. Nếu không ghi nhãn, tool tự đặt `Ô 1:`, `Ô 2:`, ...
Nếu một ô có nhiều đáp án đúng, ngăn các đáp án bằng `|`, `,` hoặc `;`. Tool chấm không phân biệt hoa/thường.

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
