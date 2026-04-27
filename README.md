# TicketHub

TicketHub là hệ thống bán vé sự kiện trực tuyến được xây dựng bằng Flask, hướng tới 3 nhóm người dùng chính: khách hàng, nhà tổ chức sự kiện và quản trị viên. Hệ thống hỗ trợ quản lý sự kiện, quản lý loại vé, đặt vé trực tuyến, quản lý đơn mua, phát hành vé điện tử dạng QR, theo dõi báo cáo thống kê và vận hành qua khu quản trị riêng.

## Mục tiêu dự án

Dự án được xây dựng nhằm số hóa quy trình tổ chức và bán vé sự kiện, giúp:

- Khách hàng dễ dàng tìm kiếm, xem chi tiết và đặt vé sự kiện
- Nhà tổ chức quản lý sự kiện, vé, đơn mua và theo dõi hiệu quả kinh doanh
- Quản trị viên quản lý người dùng, dữ liệu hệ thống và theo dõi thống kê tổng quan

## Công nghệ sử dụng

### Backend

- Python
- Flask
- Flask-SQLAlchemy
- SQLAlchemy
- PyMySQL

### Xác thực và tích hợp

- Flask-Login
- Authlib
- Google OAuth
- Flask-Mail
- Cloudinary

### Quản trị và tiện ích

- Flask-Admin
- qrcode
- Pillow
- requests

### Frontend

- HTML
- CSS
- JavaScript

## Kiến trúc dự án

Dự án sử dụng mô hình app factory của Flask và tổ chức mã nguồn theo hướng tách lớp rõ ràng:

- `models`: mô hình dữ liệu
- `routes`: xử lý request/response
- `services`: nghiệp vụ hệ thống
- `utils`: hàm tiện ích
- `templates`: giao diện HTML
- `static`: CSS, JavaScript, hình ảnh tĩnh
- `tests`: kiểm thử

## Chức năng chính

### 1. Khách hàng

- Đăng ký, đăng nhập tài khoản
- Hỗ trợ cấu hình đăng nhập Google
- Xem danh sách sự kiện
- Xem chi tiết sự kiện
- Chọn loại vé và đặt vé
- Xem danh sách vé đã mua
- Xem chi tiết đơn mua
- Xem vé điện tử và mã QR của từng vé

### 2. Nhà tổ chức sự kiện

- Tạo và quản lý sự kiện
- Quản lý loại vé
- Theo dõi đơn mua theo từng sự kiện
- Kiểm tra / check-in vé theo luồng nghiệp vụ của hệ thống
- Xem dashboard báo cáo thống kê cho sự kiện của mình

### 3. Quản trị viên

- Quản lý người dùng
- Quản lý sự kiện
- Quản lý loại sự kiện và loại vé
- Quản lý đơn mua, thanh toán, vé
- Truy cập dashboard quản trị tại `/admin`
- Xem báo cáo thống kê toàn hệ thống
- Duyệt nhà tổ chức qua giao diện quản trị

## Vé điện tử và QR

Hệ thống có phần xử lý vé điện tử và mã QR:

- Mỗi vé có mã vé riêng
- Hệ thống có thể tạo token QR đã ký
- Có route xuất ảnh QR cho vé
- Người dùng có thể xem chi tiết vé trong khu “Vé của tôi”

## Dashboard và quản trị

Hệ thống có 2 nhóm dashboard chính:

- Dashboard báo cáo cho **nhà tổ chức**
- Dashboard báo cáo cho **admin**

Ngoài ra, hệ thống tích hợp **Flask-Admin** để quản lý dữ liệu hệ thống tại đường dẫn `/admin`.

## Cấu trúc thư mục tham khảo

```text
TicketHub/
├── app/
│   ├── models/
│   ├── routes/
│   ├── services/
│   ├── static/
│   ├── templates/
│   ├── tests/
│   ├── utils/
│   ├── __init__.py
│   ├── admin.py
│   └── config.py
├── requirements.txt
├── run.py
└── README.md
```
