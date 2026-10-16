# Website quản lý thư viện trường học
Chạy: `python server.py` (cần Python 3.8+, không cần cài thêm gì) rồi mở http://localhost:8000
CSDL SQLite `library.db` tự tạo kèm dữ liệu mẫu ở lần chạy đầu (xóa file để tạo lại).

| Vai trò | Tên đăng nhập | Mật khẩu |
|---|---|---|
| Thủ thư | thuthu | admin123 |
| Sinh viên | sv001 (hoặc mã SV001) | 123456 |
| Sinh viên | sv002 | 123456 |

Kiến trúc: `index.html` (giao diện) -> `/api/*` -> nghiệp vụ trong `server.py` -> SQLite (ràng buộc PK/FK/UNIQUE/CHECK).
Mật khẩu băm PBKDF2-SHA256 + salt (100.000 vòng). Quyền kiểm tra ở server (API `a_*` chỉ thủ thư).
Vòng đời phiếu: Chờ duyệt -> Đã duyệt -> Đang mượn -> Đã trả (hoặc Từ chối / Đã hủy). Mượn 14 ngày, tối đa 5 cuốn, phạt 5.000đ/ngày.
Quên mật khẩu (demo): xác minh bằng tên đăng nhập + email, chưa gửi email thật.
