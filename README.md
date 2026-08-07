# hcmus-ai-route-optimization

Lab 1: Search Algorithms for Vietnamese Traffic Route Optimization.

Đồ án mô phỏng và trực quan hóa các thuật toán tìm đường trên dữ liệu giao thông tại TP.HCM. Ứng dụng sử dụng PyQt5 + Qt WebEngine để hiển thị bản đồ Leaflet, cho phép chọn dataset, chọn điểm bắt đầu/kết thúc và chạy thuật toán tìm đường.

## Nội dung branch này

Branch `feature/enriched-data-node-filter` bổ sung hai nhóm thay đổi chính:

1. Làm giàu dữ liệu bản đồ bằng tên địa điểm/tên đường.
2. Ẩn các node không có tên rõ ràng và không vẽ các cạnh nối tới những node đó.

Các phần code được chỉnh riêng cho nhánh này đã được đánh dấu bằng comment:

```text
#NhatHuyChanged
```

## Dữ liệu

Dữ liệu chính mà chương trình đang đọc nằm trong thư mục `data/`:

```text
data/map_binh_tan_district.json
data/map_binh_thanh_district.json
data/map_district_1.json
data/map_district_10.json
data/map_district_12.json
data/map_district_3.json
data/map_district_4.json
data/map_district_5.json
data/map_district_6.json
data/map_district_7.json
data/map_district_8.json
data/map_go_vap_district.json
data/map_nha_be_district.json
data/map_phu_nhuan_district.json
data/map_tan_binh_district.json
data/map_tan_phu_district.json
```

Ngoài ra branch này có thêm thư mục:

```text
data/named/
```

Thư mục `data/named/` lưu bộ dữ liệu đã được cô đọng theo hướng ưu tiên node có tên, dùng để đối chiếu hoặc phát triển tiếp. Hiện tại giao diện chính vẫn tự động quét các file `data/map_*.json` ở cấp gốc.

## Thay đổi xử lý node không tên

Trước khi sửa, bản đồ vẽ toàn bộ node trong graph. Điều này làm xuất hiện nhiều điểm có tên chung chung như `Node <id>` hoặc các vị trí thuộc đường chưa có tên, khiến bản đồ rối và khó chọn điểm bắt đầu/kết thúc.

Branch này bổ sung bộ lọc node tại:

```text
src/utils/node_visibility.py
```

Node sẽ bị ẩn nếu thuộc một trong các trường hợp:

- Tên rỗng.
- Tên dạng kỹ thuật như `Node 31444008562 [intersection]`.
- Tên chứa nội dung thiếu dữ liệu như `không có`, `chưa có`, `unknown`, `no data`, `unnamed`.
- Trường `name_kind` là `unnamed_road`, `missing_data`, hoặc `no_data`.

Các cạnh nối tới node bị ẩn cũng không được vẽ trên bản đồ. Lưu ý: dữ liệu và graph thuật toán không bị xóa node/cạnh; thay đổi này chỉ ảnh hưởng phần hiển thị và dropdown chọn Start/Goal.

## Các file code đã chỉnh

```text
src/models/models.py
```

Thêm trường `name_kind` vào class `Node`.

```text
src/models/graph_factory.py
```

Đọc `name_kind` từ JSON khi tạo graph.

```text
src/utils/node_visibility.py
```

File mới chứa luật xác định node nào được hiển thị.

```text
src/gui/map_widget.py
```

Đánh dấu `visible` cho node và edge trước khi gửi dữ liệu sang Leaflet.

```text
src/gui/assets/map.html
```

Chỉ vẽ node có `visible = true`; bỏ qua edge có `visible = false`.

```text
src/gui/main_window.py
```

Dropdown Start/Goal chỉ hiển thị node có tên rõ ràng.

```text
tests/test_node_visibility.py
```

Test hồi quy cho logic ẩn node không tên và cạnh nối tới node đó.

## Thuật toán hỗ trợ

Ứng dụng hiện có các thuật toán:

- Depth-First Search (DFS)
- Breadth-First Search (BFS)
- Uniform Cost Search (UCS)
- A* Search
- Genetic Algorithm (GA)
- Mock 3 Search
- Multi-location (Nearest Neighbor + 2-Opt)

### Multi-location route

Chọn thuật toán `Multi-location (Nearest Neighbor + 2-Opt)`, chọn Start và
Goal, sau đó nhập các node trung gian vào ô `Intermediate locations (IDs)`
theo dạng `id_1, id_2, id_3`. Chương trình chạy Dijkstra giữa các địa điểm,
dùng Nearest Neighbor để tạo thứ tự ban đầu, rồi dùng 2-Opt để giảm tổng chi
phí. Goal được giữ là điểm kết thúc; các node ẩn/không có tên không được nhận
từ ô nhập này.

## Cài đặt

Yêu cầu Python 3.10+ được khuyến nghị.

Tạo môi trường ảo:

```bash
python -m venv .venv
```

Kích hoạt môi trường ảo trên Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Cài dependencies:

```bash
pip install -r requirements.txt
```

## Chạy ứng dụng

Từ thư mục project:

```bash
python run.py
```

Sau khi mở ứng dụng:

1. Chọn dataset.
2. Nhấn `Load Graph Data`.
3. Chọn thuật toán.
4. Chọn Start Node và Goal Node.
5. Nhấn `Run Search`.

## Chạy test

```bash
python -m unittest discover -s tests -v
```

Test hiện tại kiểm tra logic lọc node không tên:

- Node có tên thật được hiển thị.
- Node không tên bị ẩn.
- Edge nối tới node bị ẩn cũng bị đánh dấu không hiển thị.

## Kết quả kiểm tra dữ liệu hiện tại

Với 16 file `data/map_*.json` ở cấp gốc:

```text
Total nodes: 39,032
Visible named nodes: 23,270
Hidden unnamed nodes: 15,762
Total runtime edges: 171,944
Visible runtime edges: 92,304
Hidden runtime edges: 79,640
```

Các số trên là kết quả sau khi graph được build bằng `GraphFactory`, vì edge hai chiều sẽ được mở rộng thành cạnh thuận và cạnh ngược trong runtime graph.

## Ghi chú

- Dữ liệu không tên không bị xóa khỏi file JSON.
- Thuật toán vẫn chạy trên graph đầy đủ.
- Bộ lọc hiện tại chủ yếu phục vụ trực quan hóa và chọn Start/Goal sạch hơn.
- Những thay đổi ngoài `data/` đã được chú thích bằng `#NhatHuyChanged` để dễ review.
