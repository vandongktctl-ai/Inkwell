# Bản cải tiến đọc sách cho PPW4

## Thay đổi

- Màn hình chính: đồng hồ gọn, nút **Continue reading** mở sách gần nhất; hiển thị tiến độ. Khi chưa có lịch sử, nút mở thư viện.
- Biểu tượng ứng dụng chia thành hai trang, tối đa 9 ứng dụng/trang, vùng chạm lớn hơn. Bấm **Apps 1/2** để đổi trang. Books và các công cụ thường dùng nằm trước trò chơi. Vẫn kéo để đổi vị trí trong cùng trang.
- Books: tìm theo tên sách/tệp, lọc **Reading** (các sách đã mở), hiển thị định dạng, số trang và phần trăm trên dòng riêng. **Refresh** cập nhật sách mới được chép vào.
- Quay lại thư viện sau khi đọc không quét lại toàn bộ thư mục. Dùng Refresh khi thêm hoặc xóa sách bên ngoài.
- Giữ thêm một trang EPUB/văn bản đã dàn trang trong RAM (khoảng 1,5 MiB ở độ phân giải PPW4) để quay lại trang vừa xem mà không gọi MuPDF dựng lại. Không tự dựng trang trước, không thêm tiến trình nền; không giữ ảnh PDF/truyện lớn trong cache này.
- Sao chép ảnh trang EPUB/PDF theo từng hàng thay vì xử lý từng điểm ảnh.
- Lưu cả cột PDF/khung truyện hiện tại khi đổi trang, thoát hoặc bấm nút nguồn. Định dạng trạng thái cũ vẫn đọc được.
- Tệp ảnh trang hỏng hoặc cấp phát bộ nhớ thất bại không ghi đè ảnh hợp lệ trước đó.

## Cài hoặc cập nhật

1. Tải artifact mới từ **Actions → Build Inkwell PPW4**. Giải nén artifact, rồi giải nén `Inkwell-ppw4-reading-1.zip` để lấy `linux` và `documents`.
2. Nếu đang chạy Inkwell, vào **Settings → Open the stock Kindle UI once** trước. Sau đó mở KOReader/SSH để chép qua Wi-Fi.
3. Sao lưu thư mục `linux/reader` nếu đã đọc sách và muốn giữ thêm một bản dự phòng. Chép gộp `linux` và `documents` vào `/mnt/us`, thay `alpine.img`, `boot.sh`, `ownlinux.conf` và các tệp đi kèm. **Không xóa toàn bộ thư mục linux**; giữ nguyên thư mục `reader`, sách và ghi chú.
4. Với máy chưa cài Inkwell: thoát KOReader về thư viện Kindle và mở **Inkwell: install**. Với máy đã cài: khởi động lại để mở ảnh mới; nếu đã tắt Inkwell, dùng **Inkwell: start**.

Không chép đè `alpine.img` trong khi Inkwell đang dùng ảnh đó. Bản này không thay đổi cơ chế boot, driver màn hình, Wi-Fi hoặc jailbreak.

## Kiểm tra đã thực hiện

- Biên dịch cú pháp GCC, bật `-Wall -Wextra` cho `books.c` và `home.c`.
- Biên dịch hai ứng dụng thành ARMv7 static để kiểm tra đường biên dịch.
- Chạy hồi quy với AddressSanitizer/UndefinedBehaviorSanitizer: cache và đổi sách/cỡ chữ; lưu vị trí cột; tìm kiếm; clipping ảnh; ảnh bị cắt cụt; phân trang 0–16 ứng dụng; sách gần nhất đã bị xóa.
- Dựng thử màn hình chính và thư viện bằng chính mã vẽ, ở độ phân giải 1072 × 1448.

Chạy lại kiểm tra trên Linux có GCC/Python 3:

```sh
python3 tests/reader-regression.py
```

Chưa đo thời gian mở sách, lật trang hoặc mức pin trên PPW4 thật. Cần kiểm tra thêm trên firmware 5.18.1.1.1 của chủ máy. Bản này cải tiến giao diện và bộ đọc; chưa Việt hóa các nhãn tiếng Anh.
