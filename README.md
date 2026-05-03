# 🎟️ TicketHub

<p align="left">
  <img alt="Python" src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="Flask" src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white">
  <img alt="MySQL" src="https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white">
  <img alt="SQLAlchemy" src="https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white">
  <img alt="Cloudinary" src="https://img.shields.io/badge/Cloudinary-3448C5?style=for-the-badge&logo=cloudinary&logoColor=white">
  <img alt="Google OAuth" src="https://img.shields.io/badge/Google%20OAuth-4285F4?style=for-the-badge&logo=google&logoColor=white">
</p>

Hệ thống **bán vé sự kiện trực tuyến** được xây dựng nhằm hỗ trợ quản lý sự kiện, bán vé, thanh toán, phát hành vé điện tử và kiểm soát check-in cho người tham gia. Dự án hướng tới việc số hóa quy trình tổ chức sự kiện, giúp khách hàng đặt vé thuận tiện hơn, đồng thời hỗ trợ nhà tổ chức và quản trị viên quản lý dữ liệu hiệu quả.

## Mục lục

- [✨ Tính năng](#-tính-năng)
- [🛠️ Yêu cầu môi trường](#️-yêu-cầu-môi-trường)
- [🚀 Bắt đầu](#-bắt-đầu)
- [🔧 Cấu hình biến môi trường](#-cấu-hình-biến-môi-trường)
- [📂 Cấu trúc thư mục](#-cấu-trúc-thư-mục)
- [👥 Phân quyền người dùng](#-phân-quyền-người-dùng)
- [🧪 Kiểm thử](#-kiểm-thử)
- [📧 Liên hệ](#-liên-hệ)

---

## ✨ Tính năng

### 1. Quản lý tài khoản và xác thực

- Đăng ký, đăng nhập tài khoản
- Hỗ trợ đăng nhập bằng Google
- Quản lý hồ sơ người dùng
- Phân quyền theo vai trò: **Khách hàng**, **Nhà tổ chức**, **Quản trị viên**

### 2. Quản lý sự kiện

- Tạo, chỉnh sửa và cập nhật thông tin sự kiện
- Quản lý loại sự kiện
- Quản lý loại vé và giá vé
- Cấu hình phương thức check-in cho sự kiện:
  - Check-in bằng **QR**
  - Check-in bằng **khuôn mặt**

### 3. Đặt vé và thanh toán

- Chọn loại vé và số lượng vé
- Nhập thông tin cho từng vé
- Thanh toán trực tuyến qua VNPay
- Tạo đơn đặt vé và cập nhật trạng thái thanh toán
- Hỗ trợ gửi vé điện tử qua email

### 4. Vé điện tử và check-in

- Phát hành vé điện tử cho từng người tham gia
- Sinh mã QR cho vé đối với sự kiện dùng check-in QR
- Hỗ trợ quét vé tại cổng
- Hỗ trợ check-in bằng khuôn mặt đối với sự kiện đã bật xác thực khuôn mặt

### 5. Dashboard và báo cáo

- Dashboard riêng cho **nhà tổ chức**
- Dashboard quản trị cho **admin**
- Theo dõi doanh thu, số lượng vé bán ra, trạng thái sự kiện
- Thống kê dữ liệu liên quan đến hoạt động bán vé

### 6. Quản trị hệ thống

- Quản lý người dùng
- Quản lý sự kiện
- Quản lý đơn đặt vé
- Quản lý thanh toán
- Quản lý vé
- Khu vực quản trị riêng tại `/admin`

---

## 🛠️ Yêu cầu môi trường

Để chạy dự án, bạn cần chuẩn bị:

- **Python 3.10+**
- **MySQL**
- **Cloudinary** để lưu ảnh
- **Tài khoản Gmail / SMTP** để gửi email
- **Google OAuth credentials** nếu dùng đăng nhập Google

---

## 🚀 Bắt đầu

Sau khi cài đặt Python, chạy các lệnh sau để khởi động dự án:

```bash
# clone project
git clone https://github.com/TrangThaoHuynh/TicketHub.git

# di chuyển vào thư mục project
cd TicketHub

# tạo môi trường ảo
python -m venv venv

# kích hoạt môi trường ảo
# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# cài đặt thư viện
pip install -r requirements.txt

# chạy ứng dụng
python run.py
```
