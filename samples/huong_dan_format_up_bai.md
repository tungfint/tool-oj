# Hướng dẫn format Up 1 bài và Up nhiều bài

## 1. Up 1 bài

Trên giao diện, điền trực tiếp các ô:

- `Mã bài`: ví dụ `tonghaiso`.
- `Tên bài toán`: ví dụ `Tổng hai số`.
- `Điểm`: điểm/rating của bài, ví dụ `800` hoặc `100`.
- `Dạng bài tập / Tags`: ví dụ `nhập xuất, toán học`. Nếu để trống hoặc tag không nhận diện được trên HNCode, tool sẽ báo cảnh báo và dùng mặc định `Chưa phân loại - 591`.
- `Giới hạn thời gian`: ví dụ `1.0`.
- `Giới hạn bộ nhớ`: ví dụ `1024M` hoặc `1048576`.
- `Đề bài`: dán Markdown hoặc chọn file `.md`.
- `Code sinh test`: dán `gentest_<ma_bai>.py` hoặc chọn file.
- `Zip test có sẵn`: nếu đã có test zip thì chọn trực tiếp, tool ưu tiên zip này.
- `Lời giải / hướng dẫn`: dán Markdown hoặc chọn `sol_<ma_bai>.md`.

Nếu thiếu phần nào thì tool bỏ qua phần đó. Riêng test cần có một trong hai nguồn:

- Code sinh test tạo được file zip test.
- Zip test có sẵn.

## 2. Up nhiều bài

Nén các file vào một file zip. Mỗi bài nên có:

```text
<ma_bai>.md
gentest_<ma_bai>.py
<ma_bai>.zip
sol_<ma_bai>.md
sol_<ma_bai>.cpp
sol_<ma_bai>.py
```

Ý nghĩa:

- `<ma_bai>.md`: đề bài Markdown.
- `gentest_<ma_bai>.py`: code sinh test, tự tạo `<ma_bai>.zip`.
- `<ma_bai>.zip`: zip test có sẵn; nếu có thì tool dùng trực tiếp.
- `sol_<ma_bai>.md`: lời giải/hướng dẫn để up vào phần Solutions.
- `sol_<ma_bai>.cpp`: code C++ để nộp thử nếu bật nộp thử C++.
- `sol_<ma_bai>.py`: code Python để nộp thử nếu bật nộp thử Python.

## 3. Dòng đầu file đề bài `.md`

Dòng đầu nên có đúng cấu trúc:

```text
Tên bài | Mã bài | Điểm | Tags
```

Ví dụ:

```text
Tổng hai số | tonghaiso | 800 | nhập xuất, toán học
```

Sau dòng đầu là nội dung đề bài. Nếu bật tùy chọn `Bỏ dòng đầu tiên trong file đề bài`, dòng metadata này chỉ dùng để lấy tên/mã/điểm/tags và không đưa vào nội dung đề trên web.

Nếu thiếu `Điểm` hoặc `Tags`, tool dùng giá trị mặc định trên giao diện. Với HNCode, nếu `Tags` trống hoặc không khớp tag/Type ID mà tool nhận diện được, tool dùng `Chưa phân loại - 591` và ghi cảnh báo trong bảng chuẩn bị dữ liệu.

## 4. Format đề bài HNCode

Bài đọc từ stdin/stdout:

````text
Tổng hai số | tonghaiso | 800 | nhập xuất, toán học

Cho hai số nguyên $a$ và $b$.

**Yêu cầu:** Tính tổng $a+b$.

#### Input
- Một dòng chứa hai số nguyên $a$ và $b$.

#### Output
- In ra tổng của hai số.

#### Example
!!! question "Test 1"
    ???+ "Input"
        ```sample
        1 2
        ```
    ???+ success "Output"
        ```sample
        3
        ```
````

Bài đọc ghi file:

````text
Phân loại | phanloai | 1200 | chuỗi, mô phỏng

Cho file `PHANLOAI.INP` chứa dữ liệu.

**Yêu cầu:** Ghi kết quả ra file `PHANLOAI.OUT`.

#### Input
- Dữ liệu được đọc từ file `PHANLOAI.INP`.

#### Output
- Ghi kết quả ra file `PHANLOAI.OUT`.

#### Example
!!! question "Test 1"
    ???+ "PHANLOAI.INP"
        ```sample
        3
        ```
    ???+ success "PHANLOAI.OUT"
        ```sample
        YES
        ```
````

Không viết thêm heading `# Đề bài` ở đầu nội dung.

## 5. Ràng buộc với `gentest_<ma_bai>.py`

File sinh test nên:

- Là Python.
- Không chờ nhập từ bàn phím.
- Không phụ thuộc đường dẫn tuyệt đối trên máy cá nhân.
- Tự sinh đủ cặp `.inp/.out`.
- Tự nén thành `<ma_bai>.zip`.
- Chạy trong khoảng 120 giây.
- Nếu gọi C++ thì dùng `g++` và báo lỗi rõ khi máy không có compiler.

Tên test khuyến nghị:

```text
01.inp
01.out
02.inp
02.out
...
```

hoặc:

```text
test01.inp
test01.out
test02.inp
test02.out
...
```
