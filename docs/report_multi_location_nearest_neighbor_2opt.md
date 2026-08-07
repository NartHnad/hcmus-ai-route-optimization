# Báo cáo thuật toán Multi-location: Nearest Neighbor + 2-Opt

## 1. Thông tin chung

**Tên thuật toán trên giao diện:** `Multi-location (Nearest Neighbor + 2-Opt)`  
**Branch:** `feature/multi-location-nearest-neighbor-2opt`  
**Mục tiêu:** tìm một lộ trình bắt đầu từ một node, đi qua nhiều địa điểm trung gian và kết thúc tại Goal đã chọn.

Thuật toán được xây dựng cho bài toán nhiều điểm dừng trên đồ thị đường giao thông. Đây là một biến thể của bài toán lập lịch lộ trình/TSP: thứ tự ghé thăm các địa điểm ảnh hưởng trực tiếp tới tổng chi phí di chuyển.

## 2. Bài toán đầu vào và đầu ra

### Đầu vào

- `Graph`: đồ thị giao thông hiện có của dự án.
- `start_id`: node bắt đầu.
- `locations`: danh sách node trung gian cần ghé qua.
- `end_id`: Goal cuối cùng; trong giao diện, Goal được giữ cố định ở vị trí kết thúc.
- `two_opt_iterations`: số lần cải thiện tối đa của 2-Opt, mặc định là 100.

Mỗi node có ID, tên, tọa độ và loại node. Mỗi edge có khoảng cách, thời gian, loại đường, tình trạng ùn tắc và rủi ro. Chi phí cạnh được tính bằng cùng hàm `Edge.calculate_cost()` đang được các thuật toán tìm đường khác sử dụng.

### Đầu ra

Thuật toán trả về `SearchResult`, gồm:

- `path`: chuỗi node đầy đủ trên bản đồ, bao gồm cả các giao lộ trung gian do đường ngắn nhất tạo ra.
- `visited_order`: thứ tự các địa điểm được ghé qua.
- `total_cost`: tổng chi phí của lộ trình.
- `steps`: các bước để giao diện hiển thị quá trình chạy.
- `success` và `message`: trạng thái và thông báo kết quả.

## 3. Kiến trúc xử lý

Quy trình gồm bốn giai đoạn:

```text
Danh sách địa điểm
        |
        v
Tính đường ngắn nhất giữa từng cặp địa điểm bằng Dijkstra
        |
        v
Nearest Neighbor tạo thứ tự lộ trình ban đầu
        |
        v
2-Opt đổi các đoạn đường để giảm tổng chi phí
        |
        v
Ghép các đường ngắn nhất thành path đầy đủ cho bản đồ
```

Điểm quan trọng là Nearest Neighbor và 2-Opt chỉ tối ưu **thứ tự các địa điểm được chọn**. Việc đi từ địa điểm này sang địa điểm khác vẫn sử dụng các cạnh thật trong graph, thay vì nối thẳng hai tọa độ bằng một đoạn giả.

## 4. Giai đoạn 1 — tính chi phí giữa các địa điểm

Hàm `_shortest_path()` trong `src/algorithms/multi_location.py` chạy Dijkstra cho từng cặp node cần thiết.

Với mỗi cặp `(source, target)`, hàm trả về:

```text
(chi phí nhỏ nhất, danh sách node trên đường đi)
```

Chi phí cạnh ưu tiên kết quả của `Edge.calculate_cost()`. Đối với graph được tạo thủ công trong test, khi giá trị chuẩn hóa chưa được thiết lập, thuật toán dùng `edge.distance` làm giá trị dự phòng. Cách này giúp thuật toán hoạt động nhất quán trên cả dữ liệu thực và graph kiểm thử nhỏ.

Kết quả được lưu vào ma trận chi phí:

```text
costs[(node_a, node_b)] = chi phí ngắn nhất từ node_a tới node_b
paths[(node_a, node_b)] = đường node tương ứng
```

Nếu một cặp node không thể đi tới nhau, chi phí được đánh dấu là vô cùng. Khi đó thuật toán trả về thất bại với thông báo không thể bao phủ tất cả địa điểm.

## 5. Giai đoạn 2 — Nearest Neighbor

Nearest Neighbor là heuristic tạo lời giải ban đầu nhanh:

1. Đặt vị trí hiện tại là `start_id`.
2. Trong các địa điểm chưa ghé, chọn địa điểm có chi phí ngắn nhất từ vị trí hiện tại.
3. Đánh dấu địa điểm vừa chọn là đã ghé.
4. Lặp lại đến khi hết các điểm trung gian.
5. Nếu có `end_id`, nối Goal vào cuối lộ trình.

Ví dụ:

```text
Start = S
Các điểm trung gian = A, B, C
Goal = G

Nearest Neighbor có thể tạo:
S -> B -> A -> C -> G
```

Ưu điểm của bước này là tốc độ tốt và luôn tạo được lời giải hợp lệ nếu các địa điểm liên thông theo lựa chọn greedy. Nhược điểm là lựa chọn gần nhất ở hiện tại chưa chắc tốt nhất cho toàn bộ lộ trình; vì vậy cần bước 2-Opt.

## 6. Giai đoạn 3 — 2-Opt

2-Opt cải thiện lộ trình bằng cách đảo ngược một đoạn liên tiếp.

Với lộ trình:

```text
S -> A -> B -> C -> G
```

một phép đổi có thể đảo đoạn `A -> B` thành:

```text
S -> B -> A -> C -> G
```

Sau mỗi phép đảo, thuật toán tính lại tổng chi phí. Nếu chi phí mới nhỏ hơn chi phí hiện tại, lời giải mới được giữ lại. Quá trình tiếp tục đến khi không còn phép đổi nào làm giảm chi phí hoặc đạt giới hạn `two_opt_iterations`.

Trong chế độ giao diện hiện tại:

- `Start` luôn được giữ ở đầu.
- `Goal` luôn được giữ ở cuối.
- Chỉ các node trung gian được phép thay đổi thứ tự.

Việc chỉ nhận phép đổi làm giảm chi phí bảo đảm kết quả sau 2-Opt không tệ hơn lời giải Nearest Neighbor ban đầu.

## 7. Giai đoạn 4 — dựng path đầy đủ

Sau khi có thứ tự tối ưu, ví dụ:

```text
S -> B -> A -> G
```

thuật toán lấy đường ngắn nhất đã lưu cho từng cặp:

```text
path(S, B) + path(B, A) + path(A, G)
```

Các node trùng ở điểm nối được loại bỏ khi ghép. Kết quả cuối cùng là danh sách node thật trong graph, nhờ đó `MapWidget` và Leaflet có thể tô màu các node/cạnh thuộc route giống các thuật toán hiện có.

## 8. Tích hợp vào mã nguồn

### File thuật toán

`src/algorithms/multi_location.py` chứa:

- `_shortest_path()`: Dijkstra giữa hai node.
- `nearest_neighbor_order()`: tạo thứ tự ban đầu.
- `two_opt()`: cải thiện thứ tự.
- `multi_location_nearest_neighbor_2opt()`: hàm điều phối chính.
- `multi_location`: alias ngắn cho hàm chính.

### Bộ điều phối thuật toán

`src/algorithms/algorithms.py` đăng ký tên thuật toán vào `ALGORITHMS`, đồng thời hỗ trợ request dạng:

```python
{
    "locations": ["id_1", "id_2"],
    "end_id": "goal_id",
}
```

Các thuật toán cũ vẫn dùng nguyên giao diện `run_algorithm(name, graph, start, goal)`.

### Giao diện người dùng

Trong `src/gui/main_window.py` đã thêm ô `Intermediate locations (IDs)`. Người dùng nhập các node trung gian bằng dấu phẩy hoặc dấu chấm phẩy:

```text
id_1, id_2, id_3
```

Ứng dụng kiểm tra node có tồn tại và có được phép hiển thị trước khi chạy. Node không tồn tại hoặc node bị ẩn sẽ bị từ chối.

## 9. Độ phức tạp

Gọi `k` là số địa điểm cần tối ưu và `V, E` lần lượt là số node/cạnh của graph.

- Tính đường giữa các cặp địa điểm: tối đa `O(k² (E log V))` với Dijkstra dùng heap.
- Nearest Neighbor: `O(k²)`.
- Mỗi vòng 2-Opt: tối đa `O(k²)` phép thử; triển khai hiện tại tính lại chi phí ứng viên nên chi phí thực tế phụ thuộc số vòng và số điểm.
- Ghép path: tuyến tính theo tổng số node trên các đoạn đường.

Do đó, thuật toán phù hợp với số lượng điểm dừng vừa phải. Nó không phù hợp để tối ưu đồng thời hàng nghìn địa điểm trong một lần chạy; khi đó cần giới hạn số điểm, cache đường đi hoặc dùng thuật toán tối ưu chuyên biệt hơn.

## 10. Xử lý lỗi và trường hợp đặc biệt

- Graph chưa được tải hoặc Start không tồn tại: trả về `success=False`.
- Có node trung gian/Goal không tồn tại: trả về danh sách node lỗi.
- Không có đường nối bao phủ đủ các điểm: trả về thất bại, không làm ứng dụng dừng đột ngột.
- Không có điểm trung gian: route được xem là Start tới Goal thông thường.
- Danh sách nhập trùng node: tự loại bỏ ID trùng.
- `return_to_start=True` được hỗ trợ ở API để tạo tour khép kín khi không dùng Goal cố định.

## 11. Kiểm thử

File `tests/test_multi_location.py` kiểm tra:

1. Nearest Neighbor tạo đúng thứ tự khởi tạo.
2. 2-Opt tìm được thứ tự có chi phí thấp hơn.
3. Kết quả trả về có Start, đủ các điểm trung gian và Goal cuối.
4. Node không tồn tại được xử lý bằng kết quả thất bại.

Đã chạy:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Kết quả hiện tại: **8/8 test đạt**, bao gồm 5 test lọc node trước đó và 3 test cho Multi-location. Mã nguồn cũng đã được kiểm tra bằng `compileall`.

## 12. Ưu điểm, hạn chế và hướng phát triển

### Ưu điểm

- Dễ giải thích và trực quan khi trình bày trên bản đồ.
- Tái sử dụng graph, chi phí cạnh và `SearchResult` hiện có.
- Có đường đi thật giữa các địa điểm, không chỉ dựa trên khoảng cách tọa độ.
- 2-Opt cải thiện lời giải greedy với chi phí triển khai thấp.
- Không làm thay đổi hành vi của DFS, BFS, UCS, A*, GA và Mock Search.

### Hạn chế

- Nearest Neighbor là heuristic nên không bảo đảm nghiệm tối ưu toàn cục.
- 2-Opt phụ thuộc vào nghiệm ban đầu và có thể dừng ở cực tiểu cục bộ.
- Tính nhiều lần Dijkstra có thể tốn thời gian khi số điểm dừng lớn.
- Đường ngắn nhất giữa hai điểm có thể đi qua một địa điểm khác đã chọn; hiện tại chưa áp dụng ràng buộc tránh điểm trung gian này.

### Hướng phát triển

- Cache kết quả Dijkstra giữa các lần chạy trên cùng dataset.
- Cho phép người dùng chọn nhiều node trực tiếp trên bản đồ thay vì nhập ID.
- Thêm tùy chọn tour khép kín quay về Start trên giao diện.
- So sánh kết quả với Held-Karp cho bộ dữ liệu nhỏ hoặc Genetic Algorithm cho bộ dữ liệu lớn.
- Hiển thị riêng chi phí trước/sau 2-Opt và số lần swap trên panel trạng thái.

## 13. Kết luận

Pipeline Multi-location đã được tích hợp theo mô hình: **Dijkstra để tính chi phí giữa các địa điểm → Nearest Neighbor để tạo lộ trình ban đầu → 2-Opt để cải thiện → ghép các đoạn đường thật để hiển thị**. Thiết kế này tận dụng được hạ tầng tìm đường hiện có, giữ tương thích với giao diện animation và cung cấp nền tảng để mở rộng thành bài toán giao hàng nhiều điểm dừng trong các phiên bản tiếp theo.
