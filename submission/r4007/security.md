# Bảo mật khi xử lý lô luyện tập 4007

## 1. Hết giờ khi đang làm lô

Lưu tiến độ review vào nơi làm việc của nhóm, khóa phiên và báo người phụ trách những ảnh còn chờ. Nếu cần làm tiếp ở ca sau, xin dùng máy hoặc kênh truy cập đã được cấp quyền. Chép ảnh ra USB hay gửi qua email cá nhân sẽ tạo thêm một bản dữ liệu ngoài nơi nhóm kiểm soát. Nhờ người quen xem hộ còn để người ngoài job tiếp cận ảnh và làm sai thông tin người review.

## 2. Năm hành vi khi làm việc với dữ liệu dự án

| Hành vi | Quyết định và lý do |
|---|---|
| Mở job được giao trên máy công ty | Được. Đăng nhập bằng tài khoản của mình và chỉ mở các ảnh thuộc phạm vi được giao. |
| Chụp màn hình gửi người quen | Không. Ảnh chụp có thể lộ khuôn mặt và nhãn cho người ngoài nhóm. Khi cần hỗ trợ, gửi mã ảnh qua kênh nội bộ cho người có quyền. |
| Chép lô ra USB cá nhân | Không. Thiết bị có thể thất lạc và nhóm khó thu hồi các bản sao. Lưu công việc tại kho được cấp quyền. |
| Dán nhãn thật lên chatbot công cộng | Không. Thao tác này chuyển dữ liệu dự án cho dịch vụ bên ngoài. Khi cần hỏi về định dạng YOLO, dùng ví dụ tự tạo. |
| Cho đồng nghiệp mượn tài khoản CVAT | Không. Nhật ký sẽ gán thao tác cho sai người. Đề nghị người quản lý cấp quyền trên tài khoản của đồng nghiệp. |

## 3. Khuôn mặt nhìn rõ khi guideline yêu cầu làm mờ

Nếu phát hiện trường hợp này, đặt lô ở trạng thái **Hold** và báo người phụ trách dữ liệu qua kênh nội bộ, kèm mã ảnh, mã job và yêu cầu của guideline. Giữ nguyên v1 để có thể truy vết. Người được giao xử lý tạo bản sửa, người kiểm xác nhận kết quả rồi người phụ trách mới quyết định phát hành. Tự xóa ảnh hoặc sửa trực tiếp v1 sẽ làm sai nội dung đã bàn giao và hash trong manifest.

**Ví dụ trong lô 4007.** Vũ Duy Khanh đã mở ảnh `000000001296.jpg` và xác nhận khuôn mặt nhìn rõ. Ảnh thuộc cảnh `scene_228`, job `J01`. Phiếu nội bộ cần nêu mã ảnh và job để người phụ trách điều phối người gán `A04` và người kiểm `Q02`. Với yêu cầu làm mờ trong tình huống này, giữ trạng thái Hold đến khi bản sửa được kiểm tra.
