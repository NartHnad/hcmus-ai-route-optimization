# hcmus-ai-route-optimization

Lab 1: Search Algorithms for Vietnamese Traffic Route Optimization.

Ứng dụng mô phỏng và trực quan hóa các thuật toán tìm đường trên dữ liệu giao
thông tại TP.HCM bằng PyQt5, Qt WebEngine và bản đồ Leaflet.

## Phạm vi branch

Branch `feature/multi-location-nearest-neighbor-2opt` tập trung vào task:

**Multi-location: Nearest Neighbor + 2-Opt**

Task này mở rộng bài toán tìm đường Start–Goal thành lộ trình đi qua nhiều
địa điểm trung gian. Các thay đổi làm giàu dữ liệu và lọc node thuộc branch
khác, không phải nội dung chính của branch này.

## Thuật toán Multi-location

Người dùng chọn:

- `Start Node`: điểm xuất phát.
- `Goal Node`: điểm kết thúc cố định.
- `Intermediate locations (IDs)`: các địa điểm trung gian, nhập bằng dấu
  phẩy hoặc dấu chấm phẩy, ví dụ:

```text
id_1, id_2, id_3
```

Pipeline xử lý:

```text
Các địa điểm
    ↓
Dijkstra giữa từng cặp địa điểm
    ↓
Nearest Neighbor tạo thứ tự ban đầu
    ↓
2-Opt cải thiện thứ tự
    ↓
Ghép các đường thật thành route hiển thị trên bản đồ
```

Nearest Neighbor chọn địa điểm gần nhất chưa được ghé từ vị trí hiện tại.
2-Opt thử đảo các đoạn của route và chỉ giữ thay đổi làm giảm tổng chi phí.
Start luôn ở đầu và Goal luôn ở cuối trong chế độ giao diện.

Chi phí sử dụng cùng `Edge.calculate_cost()` với các thuật toán tìm đường
khác. Kết quả trả về theo chuẩn `SearchResult`, nên có thể chạy qua hệ thống
animation hiện có.

## Các file liên quan đến task

```text
src/algorithms/multi_location.py
```

Triển khai Dijkstra theo từng cặp, Nearest Neighbor, 2-Opt và hàm điều phối
`multi_location_nearest_neighbor_2opt()`.

```text
src/algorithms/algorithms.py
```

Đăng ký thuật toán vào danh sách lựa chọn và hỗ trợ request nhiều địa điểm.

```text
src/gui/main_window.py
```

Thêm ô nhập các node trung gian và truyền chúng vào thuật toán.

```text
tests/test_multi_location.py
```

Kiểm thử thứ tự Nearest Neighbor, cải thiện 2-Opt, route đầu ra và lỗi node
không tồn tại.

```text
docs/report_multi_location_nearest_neighbor_2opt.md
```

Báo cáo kỹ thuật chi tiết của task.

## Các thuật toán hiện có

- Depth-First Search (DFS)
- Breadth-First Search (BFS)
- Uniform Cost Search (UCS)
- A* Search
- Genetic Algorithm (GA)
- Mock 3 Search
- Multi-location (Nearest Neighbor + 2-Opt)

## Cài đặt

Yêu cầu Python 3.10+.

```bash
python -m venv .venv
```

Trên Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Chạy ứng dụng

Từ thư mục project:

```bash
python run.py
```

Trong giao diện:

1. Chọn dataset và nhấn `Load Graph Data`.
2. Chọn `Multi-location (Nearest Neighbor + 2-Opt)`.
3. Chọn Start và Goal.
4. Nhập các node trung gian vào `Intermediate locations (IDs)`.
5. Nhấn `Run`.

## Chạy test

```bash
python -m unittest discover -s tests -v
```

Kết quả kiểm thử hiện tại: **8/8 test đạt**, gồm test cho task
Multi-location và các test hồi quy của project.

## Độ phức tạp và giới hạn

Với `k` địa điểm, `V` node và `E` cạnh, bước tính đường giữa các cặp có chi
phí tối đa xấp xỉ `O(k² E log V)`. Nearest Neighbor có độ phức tạp `O(k²)`;
2-Opt có tối đa `O(k²)` phép thử trong mỗi vòng cải thiện.

Đây là heuristic nên không bảo đảm nghiệm tối ưu toàn cục. Thuật toán phù hợp
với số lượng điểm dừng vừa phải; số điểm quá lớn sẽ làm nhiều lần Dijkstra
tốn thời gian hơn.

## Báo cáo

Xem [báo cáo Multi-location](docs/report_multi_location_nearest_neighbor_2opt.md)
để đọc mô tả đầy đủ về thiết kế, quy trình, độ phức tạp, kiểm thử và hướng
phát triển.
