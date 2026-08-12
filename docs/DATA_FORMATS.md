# Format Dữ Liệu

Tài liệu này mô tả các định dạng input/output mà tool đang dùng.

## Bộ bài để Up nhiều bài

Nên nén thành một file zip. Mỗi bài nên có các file:

```text
<ma_bai>.md
gentest_<ma_bai>.py
<ma_bai>.zip
sol_<ma_bai>.md
sol_<ma_bai>.cpp
sol_<ma_bai>.py
```

Trong đó:

- `<ma_bai>.md`: đề bài Markdown.
- `gentest_<ma_bai>.py`: code sinh test.
- `<ma_bai>.zip`: test có sẵn, dùng nếu không chạy gentest hoặc muốn dùng trực tiếp.
- `sol_<ma_bai>.md`: lời giải/thuyết minh, nếu có.
- `sol_<ma_bai>.cpp`: lời giải C++ để nộp thử, nếu có.
- `sol_<ma_bai>.py`: lời giải Python để nộp thử, nếu có.

Thông tin nào thiếu thì tool dùng mặc định hoặc bỏ qua phần đó.

Ghi chú xử lý:

- Thiếu `sol_<ma_bai>.md`, `sol_<ma_bai>.cpp`, `sol_<ma_bai>.py` vẫn chuẩn bị được; tool chỉ không bật mặc định phần upload lời giải/nộp thử tương ứng.
- Với file zip nhiều bài, mỗi bài cần có ít nhất một nguồn test: `gentest_<ma_bai>.py` hoặc `<ma_bai>.zip`.
- Nếu thiếu cả generator và zip test sẵn, tool báo lỗi rõ dạng `Missing test source for <ma_bai>`.
- Nếu zip test có `.inp` nhưng thiếu `.out` tương ứng, tool báo lỗi danh sách output bị thiếu.

## Dòng đầu file Markdown

Nên dùng:

```text
Tên bài | Mã bài | Điểm | Tags
```

Ví dụ:

```text
Tổng hai số | tonghaiso | 100 | nhập xuất, toán học
```

Sau dòng đầu là nội dung đề bài.

File Markdown tổng hợp nhiều bài cũng dùng metadata này ở từng heading:

```text
# Bài 1. Tên bài | ma_bai | Điểm | Tags
Nội dung bài 1

# Bài 2. Tên bài khác | ma_bai_khac | Điểm | Tags
Nội dung bài 2
```

Nếu đề bài không muốn lấy dòng đầu, bật tùy chọn:

```text
Bỏ dòng đầu tiên trong file đề bài
```

## Yêu cầu với gentest

File sinh test nên:

- Là file Python.
- Khi chạy tự tạo thư mục test.
- Tự sinh đủ `.inp` và `.out`.
- Tự nén thành `<ma_bai>.zip` hoặc một zip có đủ input/output.
- Không phụ thuộc đường dẫn tuyệt đối trên máy cá nhân.
- Nếu cần biên dịch C++, dùng `g++` hoặc cho phép chỉnh biến cấu hình.
- Trả lỗi rõ nếu thiếu compiler hoặc sinh thiếu output.

Tool chấp nhận nhiều kiểu tên test phổ biến, nhưng khuyến nghị đơn giản:

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

## Test zip có sẵn

Nếu có `<ma_bai>.zip`, tool có thể dùng trực tiếp thay vì chạy `gentest_<ma_bai>.py`.

Zip cần chứa đủ cặp input/output. Ví dụ:

```text
01.inp
01.out
02.inp
02.out
```

hoặc:

```text
Test01/CATHINH.inp
Test01/CATHINH.out
Test02/CATHINH.inp
Test02/CATHINH.out
```

Nếu báo thiếu output, kiểm tra tên file `.out` có đúng cặp với `.inp` không.

## Up 1 bài

Dữ liệu có thể nhập trực tiếp trên giao diện:

- Mã bài.
- Tên bài.
- Điểm.
- Tags/Dạng bài tập.
- Time limit.
- Memory limit.
- Nội dung đề.
- Code sinh test hoặc file test zip.
- Solution C++/Python nếu muốn nộp thử.

Mặc định nên bật:

```text
Cho phép điểm thành phần
```

## Quiz

Mỗi câu nên tách bằng một dòng `---`.

Format khuyến nghị:

```text
Tiêu đề: Câu hỏi 1
Loại: Trắc nghiệm 1 đáp án
Nội dung:
Nội dung câu hỏi ở đây.
Lựa chọn:
* A. Đáp án đúng
B. Đáp án sai
C. Đáp án sai
Giải thích:
Giải thích nếu cần.
---
Tiêu đề: Câu hỏi 2
Loại: Trả lời ngắn
Nội dung:
Kết quả của 1 + 1 là gì?
Đáp án:
2
```

Loại câu hỏi hỗ trợ:

- `Trắc nghiệm 1 đáp án`
- `Trắc nghiệm nhiều đáp án`
- `Trả lời ngắn`
- `Đúng / Sai`

Nhãn để trống theo mặc định.

## File tài khoản chấm bài

File CSV tài khoản nộp bài nên có các cột:

```text
name,username,password
```

Tên cột có thể linh hoạt hơn trong code, nhưng giữ format trên là dễ bảo trì nhất.

## Zip bài làm học sinh

Zip bài làm nên có thư mục theo học sinh, bên trong là file code theo bài.

Ví dụ:

```text
Nguyen Van A/
  bai1.cpp
  bai2.py
Tran Thi B/
  bai1.cpp
```

Tool sẽ map tên file với mã bài trong contest bằng normalize gần đúng.

## Data contest để lấy last submissions / cảnh báo AI

Có thể đưa:

- Một file zip của một contest.
- Một folder chứa nhiều contest đã giải nén hoặc nhiều zip contest.

Output thường là:

- Zip chứa last submissions.
- Excel cảnh báo AI/chép code, có sheet tổng quan và sheet chi tiết.
