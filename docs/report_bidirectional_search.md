# Báo cáo thuật toán Bidirectional Search

## 1. Mục tiêu

Chức năng này bổ sung **Bidirectional Search** cho bài toán tìm đường
giữa hai địa điểm. Thuật toán không thay thế chức năng Multi-location:

- Bidirectional Search: tìm đường từ một điểm bắt đầu đến một điểm đích.
- Nearest Neighbor + 2-Opt: xác định thứ tự và tuyến đường qua nhiều điểm.

Hai thuật toán được đăng ký trong hai nhóm riêng và hoạt động song song
trên giao diện.

## 2. Lý do chọn biến thể có trọng số

Bidirectional BFS thuần túy chỉ tối ưu số cạnh. Dữ liệu giao thông của dự án
lại gán chi phí khác nhau cho từng đoạn đường:

```text
Cost = α × Distance_norm
     + β × Time_norm
     + γ × Congestion
     + δ × Risk
```

Vì vậy, dự án triển khai **Bidirectional Uniform-Cost Search**, hay
**Bidirectional Dijkstra**. Tên hiển thị trên GUI là
`Bidirectional Search (UCS)` để thể hiện rõ đây là Bidirectional Search
cho đồ thị có trọng số.

## 3. Nguyên lý hoạt động

Thuật toán duy trì hai phép tìm kiếm:

1. Phía xuất phát duyệt các cạnh đi ra từ `start`.
2. Phía đích duyệt ngược các cạnh đi vào `goal`.

Mỗi phía có một hàng đợi ưu tiên, bảng khoảng cách và bảng cha riêng.
Để hỗ trợ đường một chiều, `Graph` duy trì thêm danh sách cạnh đi vào.
Phép tìm kiếm ngược chỉ duyệt ngược để tính toán; tuyến kết quả vẫn
luôn tuân theo hướng thật của cạnh.

Khi một node đã có khoảng cách từ cả hai phía, ta có một tuyến ứng viên:

```text
candidate = distance_forward[node] + distance_backward[node]
```

Giá trị nhỏ nhất hiện có được lưu trong `best_path`. Thuật toán dừng khi:

```text
min_forward + min_backward >= best_path
```

Vế trái là cận dưới của mọi tuyến chưa xét. Khi cận dưới không
còn nhỏ hơn tuyến ứng viên, không thể xuất hiện một kết quả tốt hơn.

## 4. Mã giả

```text
forward_queue  <- [(0, start)]
backward_queue <- [(0, goal)]
best_path      <- infinity

while both queues are not empty:
    remove stale queue entries
    if both sides have expanded and
       min_forward + min_backward >= best_path:
        break

    expand the side with the smaller minimum cost
    relax its outgoing edges (forward)
        or incoming edges (backward)

    whenever a node is known by both sides:
        update best_path and meeting_node

join start -> meeting_node with meeting_node -> goal
```

## 5. Tính đúng đắn

Với điều kiện mọi cạnh có chi phí không âm:

- Mỗi phía tuân theo nguyên tắc của UCS/Dijkstra.
- Node lấy ra hợp lệ từ hàng đợi có khoảng cách nhỏ nhất chưa xử lý.
- `best_path` luôn là chi phí của một tuyến hoàn chỉnh đã biết.
- Điều kiện dừng bảo đảm không còn tuyến chưa duyệt nào có thể rẻ hơn.

Do đó thuật toán **đầy đủ** trên đồ thị hữu hạn có đường đi và
**tối ưu** theo hàm chi phí hiện tại.

## 6. Độ phức tạp

Trong trường hợp xấu nhất:

- Thời gian: `O((V + E) log V)`.
- Bộ nhớ: `O(V + E)` do hai tập trạng thái và chỉ mục cạnh đi vào.

Bidirectional Search thường duyệt ít node hơn UCS một chiều khi hai địa điểm
cách xa nhau. Tuy nhiên, thời gian thực tế không luôn giảm do thuật toán phải
quản lý hai hàng đợi và hai bộ trạng thái.

## 7. Tích hợp giao diện

Thuật toán được thêm vào registry `single`, vì vậy chỉ xuất hiện khi người
dùng chọn một đích. Khi có từ hai đích trở lên, GUI chuyển sang registry
Multi-location và vẫn hiển thị Nearest Neighbor + 2-Opt.

Mỗi `SearchStep` của Bidirectional Search có metadata
`search_direction=forward|backward`:

- Xanh dương: tìm kiếm từ điểm xuất phát.
- Hồng: tìm kiếm ngược từ điểm đích.
- Xanh lá: tuyến kết quả sau khi hai phía gặp nhau.

Map View, Graph View, chế độ chạy tự động, xem từng bước và quay lại
bước trước đều giữ được thông tin hai hướng.

## 8. Các thay đổi trong mã nguồn

### Phần được thêm

- `src/algorithms/bidirectional_search.py`: cài đặt thuật toán, dựng tuyến và
  phát sinh các bước trực quan hóa.
- `tests/test_bidirectional_search.py`: kiểm thử trọng số, đường một chiều,
  node không tồn tại, không có đường đi, `start = goal` và so sánh với
  Dijkstra tham chiếu trên nhiều đồ thị có hướng.

### Phần được chỉnh sửa

- `src/algorithms/algorithms.py`: đăng ký thuật toán trong nhóm hai địa điểm.
- `src/models/models.py`: bổ sung chỉ mục cạnh đi vào để tìm kiếm ngược
  hiệu quả và luôn đồng bộ khi thêm/xóa graph.
- `src/gui/assets/map.html`: hiển thị node và cạnh theo hai màu tìm kiếm.
- `src/gui/assets/graph.html`: hiển thị hai phía tương tự trong Graph View.
- `src/gui/map_widget.py`: giữ metadata hướng khi dựng lại snapshot để xem
  bước trước.

Các vị trí thay đổi code được đánh dấu bằng `#NhatHuyChanged` hoặc chú
thích tương đương của HTML. Không xóa Nearest Neighbor + 2-Opt hay bất kỳ
thuật toán cũ nào.

## 9. Kiểm thử

Lệnh kiểm thử độc lập, không yêu cầu khởi chạy PyQt:

```powershell
py -m unittest tests.test_bidirectional_search -v
py -m compileall -q src tests
```

Kết quả: 7/7 nhóm kiểm thử thành công. Ca ngẫu nhiên có kiểm soát
so sánh 60 cặp start/goal trên sáu đồ thị có hướng với Dijkstra tham chiếu.

Các kiểm thử hồi quy của Multi-location và NN + 2-Opt cũng được chạy lại,
tất cả 11 ca thành công.

## 10. Kiểm chứng trên dữ liệu thật

Thử nghiệm trên `map_phu_nhuan_district.json`, từ node `366367996`
(Giao Trường Sa × Đặng Văn Ngữ) đến node `2036141659` (Điểm trên Nguyễn Văn Trỗi):

| Chỉ số | UCS | Bidirectional UCS |
|---|---:|---:|
| Tìm thấy đường | Có | Có |
| Tổng chi phí | 20.764285083068 | 20.764285083068 |
| Số node trên tuyến | 67 | 67 |
| Số node đã mở rộng | 600 | 378 |
| Thời gian trung bình 30 lần chạy tham khảo | 1.243 ms | 1.263 ms |

Bidirectional UCS giảm 222 node mở rộng, tương đương 37%, và cho cùng
chi phí tối ưu với UCS. Thời gian ở ca nhỏ này gần tương đương; các con số
thời gian phụ thuộc máy và chỉ mang tính tham khảo.

## 11. Giới hạn và hướng phát triển

- Chỉ dùng cho bài toán hai địa điểm.
- Yêu cầu chi phí cạnh không âm.
- Số node duyệt và thời gian cải thiện phụ thuộc cấu trúc đồ thị.
- Có thể phát triển thành Bidirectional A* nếu thiết kế được hai heuristic
  tương thích và chứng minh được điều kiện dừng.
