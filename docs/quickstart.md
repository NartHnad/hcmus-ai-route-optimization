# Hướng dẫn Khởi chạy Route Optimization Visualizer

Tài liệu này hướng dẫn cách cài đặt môi trường và khởi chạy giao diện trực quan hóa tối ưu hóa tuyến đường (Route Optimization Visualizer) viết bằng PyQt5 và tích hợp bản đồ Leaflet.js.

## 1. Yêu cầu hệ thống
- **Python**: Phiên bản 3.10 trở lên.
- **Hệ điều hành**: Windows, macOS, hoặc Linux có hỗ trợ giao diện đồ họa.

## 2. Hướng dẫn cài đặt môi trường ảo và thư viện

### Bước 1: Tạo môi trường ảo (venv)
Mở terminal tại thư mục gốc của dự án (`hcmus-ai-route-optimization`) và chạy lệnh sau để khởi tạo môi trường ảo:
```bash
python -m venv venv
```

### Bước 2: Kích hoạt môi trường ảo
Tùy thuộc vào hệ điều hành của bạn, hãy chạy lệnh tương ứng:

- **Windows (Command Prompt / cmd)**:
  ```cmd
  venv\Scripts\activate.bat
  ```
- **Windows (PowerShell)**:
  ```powershell
  venv\Scripts\Activate.ps1
  ```
  *(Lưu ý: Nếu gặp lỗi quyền thực thi tập lệnh trên PowerShell, bạn có thể chạy PowerShell với quyền Administrator và chạy lệnh `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force` trước).*
- **macOS / Linux**:
  ```bash
  source venv/bin/activate
  ```

### Bước 3: Cài đặt các thư viện phụ thuộc
Khi môi trường ảo đã được kích hoạt, hãy cài đặt các gói cần thiết thông qua file `requirements.txt`:
```bash
pip install -r requirements.txt
```

---

## 3. Khởi chạy Ứng dụng Visualizer

Sau khi đã kích hoạt môi trường ảo và cài đặt đầy đủ thư viện, khởi chạy ứng dụng bằng lệnh sau:
```bash
python -m src.gui.main_window
```

---

## 4. Hướng dẫn Sử dụng Giao diện (GUI)

Khi ứng dụng khởi chạy, bạn sẽ thấy giao diện gồm sidebar điều khiển bên trái và bản đồ Leaflet bên phải. Các bước thao tác như sau:

1. **Load dữ liệu đồ thị (Dataset Control)**:
   - Trong ô xổ xuống **Select Dataset**, chọn file dữ liệu muốn trực quan hóa:
     - `mock_data.json`: Dữ liệu đồ thị mẫu mới (sử dụng tọa độ `lat`/`lon` và các cạnh có thuộc tính phong phú).
     - `map_data.json`: Dữ liệu bản đồ cũ (sử dụng tọa độ `x`/`y` và cấu trúc đường 2 chiều cũ).
   - Nhấn nút **Load Graph Data** để vẽ đồ thị lên bản đồ và hiển thị thông tin thống kê số lượng Node/Edge trong ô **Status Console**.
2. **Thiết lập Tìm đường (Pathfinding Setup)**:
   - Sau khi load dữ liệu thành công, danh sách các Node ID sẽ được cập nhật tự động vào hai ô **Start Node** và **Goal Node**.
   - Chọn điểm bắt đầu và điểm kết thúc bạn muốn tìm đường.
3. **Chạy Mô phỏng (Run Mock Search)**:
   - Nhấn nút **Run Mock Search** để khởi chạy animation mô phỏng quá trình tìm kiếm đường đi từng bước.
   - Bản đồ sẽ tự động tô màu và di chuyển (pan/zoom) theo quá trình duyệt:
     - **Màu vàng**: Node đang duyệt qua (`visit_node`).
     - **Màu cam**: Cạnh đang được kiểm tra (`inspect_edge`).
     - **Màu xanh lá**: Đường đi kết quả cuối cùng (`path_edge` / `finish`).
4. **Khôi phục bản đồ (Reset Map Style)**:
   - Nhấn nút **Reset Map Style** để đưa tất cả màu sắc của các node và đường nối trên bản đồ về trạng thái mặc định ban đầu.

---

## 5. Cấu trúc thư mục của phần GUI

```text
src/
  ├── gui/
  │    ├── assets/
  │    │    └── map.html         # Giao diện HTML & JS chứa bản đồ Leaflet và logic vẽ/màu sắc
  │    ├── main_window.py        # Dựng layout giao diện PyQt5, Sidebar điều khiển và xử lý sự kiện
  │    └── map_widget.py         # Cầu nối giữa Python (PyQt5 QWebEngineView) và Javascript (Leaflet)
  │
  ├── algorithms/
  │    └── mock_algorithm.py     # Thuật toán giả lập (mock search) tạo các bước animation mẫu
  │
  └── models/
       ├── models.py             # Định nghĩa cấu trúc dữ liệu Graph, Node, Edge, SearchResult
       └── graph_factory.py      # Đọc và phân tích dữ liệu JSON (Factory Pattern) sang Graph object
```
