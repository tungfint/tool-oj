# Prompt nâng cấp project ChuyenBai

Bạn đang làm việc trong project:

```text
C:\Users\Admin\Documents\_ChuyenBai
```

Hãy nâng cấp project web tool hiện có, đặt tên giao diện là `Tool HNCode`, để hỗ trợ quản lý, chuẩn bị, upload, nộp thử và chuyển bài giữa 3 hệ thống:

```text
HNOJ
HNCode
TinHocTre
```

Mục tiêu là tạo một giao diện web dễ dùng, khoa học, có hướng dẫn rõ ràng, dùng được lâu dài để up bài mới hoặc chuyển bài giữa các hệ thống.

Trước khi sửa code, hãy nghiên cứu kỹ các link tạo bài/admin form của từng trang:

```text
https://hnoj.edu.vn/admin/judge/problem/add/
https://tinhoctre.vn/admin/judge/problem/add/
https://oj.hncode.edu.vn/admin/judge/problem/add/
```

Yêu cầu quan trọng:

- Khi tạo bài mới, ưu tiên dùng admin form `/admin/judge/problem/add/`.
- Không dùng form tạo bài public/bên ngoài nếu admin form dùng được.
- Nếu một trang không hỗ trợ một field nào đó trong form hiện tại, backend phải bỏ qua an toàn và ghi chú trong log.
- Dùng favicon HNCode từ file `static/favicon-HNCode.svg`.
- Khi up hoặc chuyển bài lên `HNOJ` và `TinHocTre`, đề bài dùng ký tự `~` thay cho ký tự `$`.
- Khi up hoặc chuyển bài lên `HNCode`, đề bài dùng ký tự `$` thay cho ký tự `~`.

## I. Tab Tài khoản & Hướng dẫn

Tạo tab `Tài khoản & Hướng dẫn`.

Trong tab này có khu vực lưu tài khoản admin của 3 trang:

```text
HNOJ
HNCode
TinHocTre
```

Yêu cầu:

- Trên máy hiện tại, vẫn lưu lại các tài khoản đã từng dùng.
- Cho phép sửa tài khoản/mật khẩu.
- Có nút `Lưu tạm`.
- Có nút `Xóa thông tin đã lưu`.
- Thông tin có thể lưu bằng `localStorage` hoặc cơ chế local phù hợp.

Phần hướng dẫn prompt tạo bộ bài cần có nút `Ẩn / Hiện hướng dẫn`.

Nội dung hướng dẫn:

```text
Với mỗi bài trong danh sách dưới đây, hãy tạo đủ 4 file:

1. File sinh test:
   - Tên file: gentest_<ma_bai>.py
   - Ví dụ: gentest_tht26_tongbi.py

2. File lời giải Python:
   - Tên file: sol_<ma_bai>.py
   - Ví dụ: sol_tht26_tongbi.py

3. File lời giải C++:
   - Tên file: sol_<ma_bai>.cpp
   - Ví dụ: sol_tht26_tongbi.cpp

4. File đề bài Markdown:
   - Tên file: <ma_bai>.md
   - Ví dụ: tht26_tongbi.md
   - Dòng đầu tiên của file phải có đúng cấu trúc:
     Tên bài | Mã bài
   - Ví dụ:
     Tổng bi | tht26_tongbi
   - Sau dòng đầu tiên là toàn bộ nội dung đề bài.

Yêu cầu đối với file sinh test:

- File sinh test là file Python.
- Trong file sinh test phải nhúng lời giải chuẩn bằng C++ để sinh output.
- Khi chạy file sinh test, chương trình tự tạo thư mục test cho bài tương ứng.
- Tên thư mục test nên là mã bài, ví dụ:
  tht26_tongbi/
- Các file test trong thư mục có dạng:
  01.inp, 01.out
  02.inp, 02.out
  ...
- Sau khi sinh test, file sinh test tự nén thư mục test thành:
  tht26_tongbi.zip

Yêu cầu đối với bộ test:

- Bộ test phải đủ mạnh, phủ đủ các trường hợp đặc biệt và trường hợp biên.
- Dữ liệu phải đúng giới hạn của đề bài.
- Nếu đề có subtask, số lượng test phải phân bố đúng theo tỉ lệ subtask.
- Nếu bài đơn giản, chỉ cần khoảng 10 test.
- Nếu bài cần nhiều trường hợp để kiểm tra chặt chẽ hơn, có thể sinh khoảng 20 test hoặc nhiều hơn.
- Cần có 01 test ví dụ, các test nhỏ, test biên, test ngẫu nhiên có kiểm soát, test đủ các trường hợp và test lớn.

Sau khi tạo xong, hãy nén toàn bộ các file đã tạo thành một file zip duy nhất và gửi lại cho tôi.

Ví dụ với bài:

Tổng bi | tht26_tongbi

Cần tạo 4 file:

- gentest_tht26_tongbi.py
- sol_tht26_tongbi.py
- sol_tht26_tongbi.cpp
- tht26_tongbi.md

Hãy thực hiện cho toàn bộ các bài được cung cấp bên dưới.
```

## II. Tab Up bài

Tạo tab `Up bài`.

Tab này dùng để up bài mới lên một trong ba hệ thống:

```text
HNOJ
HNCode
TinHocTre
```

### 1. Chọn web đích

```text
HNOJ / HNCode / TinHocTre
```

### 2. Chọn file zip bộ bài

- Có thể paste đường dẫn file zip.
- Có nút `Chọn file` để chọn file zip trực tiếp trong trình duyệt.

### 3. Các thông tin chính hiển thị trên giao diện

```text
Giới hạn thời gian:
- Mặc định: 1.0

Giới hạn bộ nhớ:
- Mặc định: 1048576

Ngôn ngữ cho phép:
- Hiển thị theo từng web đích.
- Mặc định tích hết các ngôn ngữ tương ứng.
```

### 4. Các thông tin khác đặt trong phần Mở rộng / Thu gọn

Trong phần này hiển thị:

```text
Người tạo / Creators:
- Mặc định: mrtee
- Có thể để trống.

Dạng đề / Problem types:
- Mặc định: Chưa phân loại.

Nhóm bài / Problem group:
- Mặc định: Chưa phân loại.
```

### 5. Ngôn ngữ cho phép / Allowed languages

Với HNOJ:

```text
Pascal
C++17
Python 3
Scratch
```

Với HNCode:

```text
Pascal
C++17
C++20
Python 3
PyPy 3
```

Với TinHocTre:

```text
Pascal
C++17
C++20
Python 3
PyPy 3
Scratch
```

Nếu hệ thống đích không hỗ trợ chọn ngôn ngữ ở form hiện tại thì vẫn hiển thị trên giao diện, nhưng backend cần xử lý an toàn: bỏ qua trường không hỗ trợ và ghi chú trong log.

### 6. Nộp bài chấm thử

Có 3 ô tích:

```text
Nộp bài chấm thử C++
Nộp bài chấm thử Python
Không nộp bài chấm thử
```

Yêu cầu:

- `Nộp bài chấm thử C++` dùng file `sol_<ma_bai>.cpp`.
- `Nộp bài chấm thử Python` dùng file `sol_<ma_bai>.py`.
- Nếu không có file lời giải tương ứng thì bỏ qua lượt nộp thử đó và ghi log.
- Nếu tích `Không nộp bài chấm thử` thì bỏ qua toàn bộ bước nộp thử.

### 7. Các thông tin mặc định, không cần hiển thị trên giao diện

```text
Điểm: 100
Cho phép nhận điểm với từng test đúng: bật
```

### Chuẩn bị dữ liệu

Có nút:

```text
Chuẩn bị dữ liệu
```

Khi bấm nút này:

- Giải nén file zip bộ bài.
- Đọc danh sách bài.
- Đọc mã bài và tên bài từ dòng đầu tiên của file `.md` theo dạng:

```text
Tên bài | Mã bài
```

- Với mỗi bài, xác định bộ test bằng một trong hai cách:

Cách 1: Có file sinh test:

```text
gentest_<ma_bai>.py
```

Thì chạy file này để tạo:

```text
<ma_bai>.zip
```

Cách 2: Không có file gentest, nhưng có zip test sẵn:

```text
<ma_bai>.zip
```

Ví dụ:

```text
tongbi.zip
tht26_tongbi.zip
1_tht26_tongbi.zip
```

Sau khi xử lý xong, hiển thị bảng chuẩn bị dữ liệu gồm:

```text
Chọn bài cần up
Mã bài
Tên bài toán
Up đề bài
Up test
File test
Số lượng test
Trạng thái
```

Khi upload thành công, hiển thị chữ `Link`; bấm vào chữ `Link` thì mở trang bài đó trên website.

Yêu cầu thêm:

- Bảng có nút `Chọn tất cả`.
- Bảng có nút `Bỏ chọn tất cả`.
- Nếu mã bài đã tồn tại trên web đích thì thông báo rõ `Bài đã tồn tại`, bỏ qua bài đó hoàn toàn và tiếp tục up các bài khác.

## III. Tab Chuyển bài

Tạo tab `Chuyển bài`.

Tab này dùng để chuyển bài giữa các hệ thống.

Giao diện gồm:

### 1. Chọn nguồn

```text
HNOJ / HNCode / TinHocTre
```

### 2. Chọn đích

```text
HNOJ / HNCode / TinHocTre
```

### 3. Hiển thị và cho sửa thông số như tab Up bài

Các thông số cần hiển thị:

```text
Giới hạn thời gian mặc định
Giới hạn bộ nhớ mặc định
Ngôn ngữ cho phép ở đích
```

Bên cạnh phần time/memory mặc định cần có hai nút:

```text
Áp dụng cho tất cả các bài
Mặc định
```

Yêu cầu:

- `Áp dụng cho tất cả các bài`: lấy `Giới hạn thời gian mặc định` và `Giới hạn bộ nhớ mặc định` điền xuống toàn bộ các dòng trong bảng chuyển bài.
- `Mặc định`: trả time/memory của từng dòng về đúng thông tin lấy từ bài nguồn.

Các thông số trong phần Mở rộng / Thu gọn:

```text
Người tạo / Creators
Dạng đề / Problem types
Nhóm bài / Problem group
```

Người dùng có thể tùy chỉnh các thông số này trước khi chuyển.

### 4. Nhập danh sách mã bài cần chuyển

Cho phép nhập nhiều mã bài, cách nhau bằng:

```text
dấu cách
dấu phẩy
xuống dòng
```

Ví dụ:

```text
tht26_tongbi
tht26_quatang
tht26_tichlt
```

### 5. Chuẩn bị dữ liệu

Có nút:

```text
Chuẩn bị dữ liệu
```

Khi bấm nút này:

- Đăng nhập hệ thống nguồn.
- Đọc tên bài toán từ bài nguồn.
- Đọc time limit, memory limit từ bài nguồn nếu có.
- Đọc bộ test từ link:

```text
/problem/<ma_bai>/test_data
```

- Hiển thị link `Bộ test` trỏ tới `/problem/<ma_bai>/test_data`.
- Đếm số lượng test.

Bảng chuẩn bị dữ liệu cần có:

```text
Chọn
Mã bài
Tên bài toán
Time
Memory
Up đề bài
Up test
Bộ test
Số test
Trạng thái
```

Yêu cầu:

- Có thể sửa mã bài khi chuyển sang đích.
- Có thể sửa tên bài toán.
- Có thể sửa time limit.
- Có thể sửa memory limit.
- Có thể chọn/bỏ chọn upload đề.
- Có thể chọn/bỏ chọn upload test.
- Bảng có nút `Chọn tất cả`.
- Bảng có nút `Bỏ chọn tất cả`.

### 6. Xác nhận chuyển bài

Có nút:

```text
Xác nhận chuyển bài
```

Khi chuyển bài:

- Lấy đề bài từ dữ liệu đã chuẩn bị.
- Lấy test từ dữ liệu đã chuẩn bị.
- Tạo bài ở đích qua admin form `/admin/judge/problem/add/`.
- Upload test sang đích.
- Hiển thị trạng thái từng bài.
- Nếu thành công, hiển thị chữ `Link` để mở trang bài ở đích.
- Nếu mã bài đích đã tồn tại thì thông báo rõ `Bài đã tồn tại`, bỏ qua bài đó hoàn toàn và tiếp tục chuyển các bài khác.

## IV. Yêu cầu chung

- Giao diện viết bằng tiếng Việt có dấu.
- Các mục upload bài cần đồng bộ giao diện tối đa.
- Các thao tác nguy hiểm cần có log rõ ràng.
- Không làm mất dữ liệu cũ nếu bài đã tồn tại, trừ khi người dùng chủ động chọn upload lại.
- Có thể chạy local bằng:

```powershell
python web_app.py
```

- Sau khi sửa xong, kiểm tra bằng dry-run trước.
- Test giao diện local bằng `http://127.0.0.1:5050`.
- Dọn các file tạm, snapshot HTML, artifact sinh ra trong quá trình test để project có thể đóng gói gửi sang máy khác.
