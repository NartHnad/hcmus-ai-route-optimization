# UI/UX Review Plan

## 1. Tổng quan giao diện hiện tại

### Cấu trúc giao diện

Giao diện hiện tại là ứng dụng desktop PyQt5, gồm ba lớp chính:

* **Header**: tên “Route Optimization Visualizer”, hai nút đổi Light/Dark Mode và nút chuyển “Mobile”.
* **Khu vực desktop**: sidebar cố định rộng 280 px ở bên trái và bản đồ Leaflet ở bên phải.
* **Sidebar**: lần lượt có Dataset Control, Algorithm, Parameters, Execution và Status.
* **Khu vực mobile**: ẩn sidebar, giữ bản đồ và thêm card “Delivery Information” ở dưới.
* **Bản đồ**: hiển thị node, edge, start, goal, node được duyệt, cạnh được kiểm tra và đường đi cuối cùng bằng màu sắc.

Luồng thao tác chính hiện nay là:

1. Chọn dataset và nhấn **Load Graph Data**.
2. Chọn thuật toán, start node, goal node và tốc độ animation.
3. Nhấn **Run**.
4. Dùng Pause, Resume, Next Step, Replay hoặc Reset Map để điều khiển mô phỏng.
5. Theo dõi màu trên bản đồ và log chữ trong vùng Status.

### Thành phần UI quan trọng

* `MainWindow` chịu trách nhiệm bố cục, điều khiển và status log.
* `MapWidget` nối kết quả thuật toán Python với bản đồ Leaflet.
* `map.html` định nghĩa màu và cách vẽ các bước `expand`, `discover`, `update`, `finish`.
* `SearchResult` đã có `success`, `path`, `total_cost`, `message`, `visited_order`.
* Các bước tìm kiếm đã hỗ trợ `metrics`; A* đã phát sinh `g`, `h`, `f`.
* `DeliveryPanel` đã tồn tại dưới dạng component riêng nhưng chưa được dùng trong `MainWindow`.

### Điểm mạnh hiện tại

* Bản đồ là nội dung trung tâm và được dành phần lớn diện tích ngang.
* Thứ tự Dataset → Algorithm → Parameters → Execution tương đối đúng với luồng thao tác.
* Có đủ điều khiển cơ bản để trình diễn từng bước: chạy, dừng, tiếp tục, đi một bước, phát lại và reset.
* Start và goal có màu riêng, tooltip có ID và tên node.
* Contract `SearchStep`/`SearchResult` đã tạo nền tảng tốt để xây dựng bảng trạng thái và kết quả mà không cần sửa bản chất thuật toán.
* Có empty state trên bản đồ, trạng thái disabled cho button và hai theme sáng/tối.

### Ghi nhận khi kiểm tra giao diện thực tế

* Mặc dù code gọi `resize(1100, 750)`, tổng chiều cao tối thiểu do sidebar tạo ra vào khoảng **1021 px**; trên màn hình thấp, cửa sổ không thể thu gọn về chiều cao dự kiến.
* Ở chế độ “Mobile”, code gọi `resize(430, 850)` nhưng header làm chiều rộng tối thiểu thực tế vào khoảng **708 px**.
* Sau khi chạy A*, Status ghi nhiều lần “Visiting node” cho cùng một node vì mọi step có trường `node` đều bị diễn giải là bước visit, kể cả discover/finish.
* Kết quả A* có chi phí, thứ tự duyệt và `g/h/f`, nhưng sau khi hoàn tất giao diện chỉ thêm dòng “Search completed.”.

## 2. Các vấn đề cần xem xét

| ID | Khu vực | Vấn đề hiện tại | Mức độ ảnh hưởng | Lý do |
| --- | --- | --- | --- | --- |
| UI-01 | Bố cục desktop | Sidebar chứa năm group và sáu nút execution xếp dọc, không có vùng cuộn; size hint ép cửa sổ lên khoảng 1021 px chiều cao thay vì 750 px. | Cao | Dễ vượt khỏi màn hình laptop, làm phần Status hoặc control phía dưới khó tiếp cận và khiến bố cục không responsive theo chiều dọc. |
| UI-02 | Responsive/mobile | “Mobile” là chế độ bật thủ công, không phản ứng theo kích thước cửa sổ; khi bật lại ẩn toàn bộ control cần để cấu hình và chạy thuật toán. | Cao | Người dùng màn hình hẹp chỉ xem được bản đồ và không thể hoàn thành luồng thao tác chính. |
| UI-03 | Header mobile | Header vẫn giữ title dài và ba button có min-width; yêu cầu 430 px nhưng cửa sổ thực tế bị ép rộng khoảng 708 px. | Cao | Giao diện không sử dụng được như một layout hẹp thực sự; nội dung header chiếm nhiều không gian hơn bản thân tác vụ. |
| UI-04 | Delivery Information | Các label mobile `Start`, `Goal`, `Algorithm`, `Status` không được cập nhật; đồng thời `DeliveryPanel` riêng không được sử dụng. | Trung bình | Hiển thị dữ liệu “-” tạo cảm giác chức năng chưa hoàn thiện và có hai nguồn UI kết quả dễ lệch nhau khi phát triển tiếp. |
| UI-05 | Trạng thái thuật toán | Không có khu vực riêng cho current node, frontier, explored và visited order. | Cao | Người xem chỉ thấy màu tích lũy trên bản đồ, không hiểu cấu trúc dữ liệu tìm kiếm đang thay đổi như thế nào; mục tiêu trình diễn AI chưa đạt rõ. |
| UI-06 | Chỉ số A* | `g(n)`, `h(n)`, `f(n)` đã có trong step nhưng bị bỏ qua ở cả `MainWindow` và `map.html`. | Cao | Mất phần giải thích quan trọng nhất khi trình bày A* và không thể kiểm chứng vì sao một node được ưu tiên. |
| UI-07 | Kết quả | `success`, `path`, `total_cost`, `message`, `visited_order` có trong `SearchResult` nhưng không có result summary; chưa có distance, runtime hay số node đã duyệt ở trạng thái hoàn tất. | Cao | Người dùng không thể đọc hoặc so sánh kết quả; phần đồ án mới cho thấy animation chứ chưa cho thấy hiệu quả thuật toán. |
| UI-08 | Chú giải bản đồ | Không có legend thường trực giải thích màu node/edge, start, goal, explored, inspect và final path. | Trung bình | Người mới phải đoán ý nghĩa màu hoặc đọc tài liệu ngoài ứng dụng; khó thuyết trình trực tiếp trước giảng viên. |
| UI-09 | Ngữ nghĩa trực quan hóa | Node `expand` giữ màu vàng lâu dài nên không tách current khỏi explored; `discover` chỉ tô edge chứ không biểu diễn node trong frontier; `update` dùng cùng màu xanh với final path. | Cao | Ba trạng thái cốt lõi bị trộn lẫn và cạnh từng được relax có thể bị hiểu nhầm là đường đi cuối cùng. |
| UI-10 | Start/goal và final path | Animation có thể ghi đè style start/goal bằng visit/path, khiến hai đầu tuyến không còn dấu hiệu riêng sau khi chạy. | Trung bình | Người xem khó nhận biết hướng tuyến và điểm đầu/cuối trong kết quả dài hoặc dày cạnh. |
| UI-11 | Status log | `on_step_changed` ghi “Visiting node” cho mọi step có `node`; kiểm tra thực tế cho thấy log node bị lặp và sai loại sự kiện. | Cao | Log mâu thuẫn với animation, làm giảm độ tin cậy của phần trình diễn thuật toán. |
| UI-12 | Khả năng đọc Status | Status bị đặt cuối sidebar, thường chỉ còn chiều cao nhỏ; nội dung graph summary dùng block text dài, không có step number, loại sự kiện hay phân cấp success/error rõ. | Trung bình | Thông tin quan trọng bị chìm trong log tuần tự và phải cuộn liên tục. |
| UI-13 | Execution controls | Run, Pause, Resume, Next Step, Replay, Reset Map là sáu button full-width xếp dọc; Pause và Resume luôn chiếm hai hàng dù loại trừ nhau. | Trung bình | Khu vực điều khiển chiếm khoảng 347 px chiều cao và là nguyên nhân chính làm sidebar quá dài. |
| UI-14 | Trạng thái button | Next Step dừng timer bên trong `MapWidget` nhưng UI vẫn có thể giữ Pause enabled/Resume disabled; Replay được bật ngay khi bắt đầu chạy thay vì sau khi có trạng thái phù hợp. | Cao | Trạng thái hiển thị của control có thể khác trạng thái animation thật, gây thao tác khó đoán. |
| UI-15 | Tốc độ animation | Giá trị mặc định là mục đầu tiên `0 ms`; animation có thể kết thúc gần như tức thời. | Trung bình | Người dùng mới dễ bỏ lỡ toàn bộ quá trình duyệt, trái với mục tiêu quan sát thuật toán. |
| UI-16 | Dataset và node selection | Dataset hiển thị tên file kỹ thuật như `_map_data.json`; start/goal chỉ hiển thị ID và dùng combo thường. | Trung bình | Khó hiểu dataset đại diện khu vực nào, khó tìm node khi danh sách lớn và không tận dụng tên địa điểm đã có trong model. |
| UI-17 | Theme | Dark Mode chỉ đổi QSS của Qt; bản đồ, tile, empty message và màu inline trong HTML vẫn theo nền sáng. Nút theme cũng không chỉ ra mode đang active. | Trung bình | Tạo tương phản thị giác mạnh giữa sidebar tối và bản đồ sáng; trạng thái theme không rõ ràng và thiếu nhất quán. |
| UI-18 | Visual hierarchy | Tất cả button dùng cùng màu xanh và kích thước gần giống nhau; Run không nổi bật hơn Replay/Reset, label section và label field chủ yếu dựa vào bold mặc định của GroupBox. | Trung bình | Người dùng không nhận ra primary action, secondary action và action phục hồi; giao diện mang cảm giác form kỹ thuật hơn là sản phẩm trình diễn hoàn chỉnh. |
| UI-19 | Thuật toán thử nghiệm | “Mock 3 Search” xuất hiện trong danh sách người dùng nhưng phát step type legacy (`visit_node`, `inspect_edge`, `path_edge`) mà `map.html` không xử lý. | Cao | Một lựa chọn công khai có animation sai hoặc thiếu cho đến bước finish; tên “Mock” cũng làm giảm tính chuyên nghiệp khi demo. |
| UI-20 | Phản hồi và empty/error state | Lỗi load, lỗi chạy và kết quả không tìm thấy đường chỉ đi vào log; bản đồ ban đầu chỉ có dòng “Waiting for graph data...” và không hướng dẫn bước tiếp theo. | Trung bình | Người mới có thể không biết cần làm gì hoặc không nhận ra thao tác vừa thất bại. |
| UI-21 | Phạm vi sản phẩm giao hàng | Tên “Route Optimization” và “Delivery Information” gợi ý điều phối giao hàng, nhưng UI hiện chỉ hỗ trợ một start và một goal, không giải thích đây là chế độ single-route. | Trung bình | Kỳ vọng của người xem không khớp chức năng hiện có; dễ bị hỏi về multi-stop khi thuyết trình. |
| UI-22 | So sánh thuật toán | Mỗi lần chạy thay thế trạng thái trước đó; không lưu bảng kết quả theo thuật toán. | Trung bình | Khó chứng minh khác biệt BFS/DFS/A*/GA về cost, số node duyệt và runtime, trong khi đây là giá trị học thuật chính của đồ án. |

## 3. Đề xuất cải thiện

| ID | Đề xuất | Kết quả mong đợi | File có thể liên quan | Độ khó | Rủi ro |
| --- | --- | --- | --- | --- | --- |
| UI-01 | Đưa sidebar vào vùng cuộn dọc hoặc chia nội dung thành các section thu gọn; đặt content area co giãn và không để tổng size hint của group ép chiều cao cửa sổ. | Bố cục không vỡ trên màn hình laptop, mọi control vẫn tiếp cận được và bản đồ giữ được diện tích ưu tiên. | `src/gui/main_window.py`, `src/gui/themes/light.qss`, `src/gui/themes/dark.qss` | Trung bình | Vùng cuộn lồng nhau với Status cần được kiểm tra để tránh trải nghiệm cuộn khó chịu. |
| UI-02 | Thay toggle “Mobile” bằng breakpoint theo chiều rộng; ở layout hẹp, dùng một nút mở control drawer/bottom sheet thay vì ẩn chức năng. | Luồng Load → Configure → Run vẫn hoàn chỉnh ở mọi kích thước và giảm thao tác chuyển mode thủ công. | `src/gui/main_window.py` | Cao | PyQt desktop không có CSS breakpoint; cần quản lý `resizeEvent` và trạng thái widget cẩn thận. |
| UI-03 | Rút gọn header hẹp: title ngắn hơn hoặc hai dòng, gộp Light/Dark thành một icon toggle, chuyển control phụ vào menu overflow. | Đạt chiều rộng gần 430 px thật, giảm lộn xộn và dành không gian cho bản đồ. | `src/gui/main_window.py`, hai file QSS | Trung bình | Icon-only cần tooltip/accessibility name để không làm giảm khả năng hiểu. |
| UI-04 | Chọn một component kết quả duy nhất; dùng `DeliveryPanel` hoặc thay bằng `ResultSummary`, bind trực tiếp start/goal/algorithm/status và tái sử dụng ở desktop/mobile. | Loại bỏ dữ liệu “-”, tránh component trùng lặp và tăng tính nhất quán. | `src/gui/main_window.py`, `src/gui/delivery_panel.py` | Trung bình | Cần xác định rõ component thuộc “delivery” hay “search result” trước khi đặt API ổn định. |
| UI-05 | Thêm panel “Algorithm State” có bốn vùng ngắn: Current, Frontier, Explored, Visited order; dùng badge/chip và giới hạn số phần tử hiển thị, có nút mở chi tiết khi danh sách dài. | Làm nổi bật trực quan hóa AI mà không che bản đồ; người xem theo dõi được từng bước và giảm phụ thuộc vào log. | `src/gui/main_window.py`, `src/gui/map_widget.py`, `src/models/models.py`, các file thuật toán | Cao | Contract step hiện chưa gửi snapshot frontier/explored; cần chuẩn hóa dữ liệu giữa mọi thuật toán. |
| UI-06 | Với thuật toán heuristic, thêm bảng nhỏ Node, g, h, f và highlight hàng current; với thuật toán không dùng heuristic, ẩn tab/cột này thay vì để trống. | Giải thích được quyết định của A*, giúp kiểm chứng số liệu và tăng giá trị học thuật. | `src/gui/main_window.py`, `src/gui/map_widget.py`, `src/models/models.py`, `src/algorithms/a_star.py` | Trung bình | Cần thống nhất đơn vị giữa edge cost và heuristic trước khi trình bày số. |
| UI-07 | Tạo Result Summary sau finish gồm success/failure, route, total cost/distance, estimated time nếu tính được, visited count và measured runtime; dùng 3–4 metric card cùng một dòng và phần route chi tiết thu gọn. | Kết quả dễ đọc, dễ so sánh và phù hợp trình bày trước giảng viên mà không làm màn hình quá dày. | `src/gui/main_window.py`, `src/gui/delivery_panel.py`, `src/models/models.py`, các file thuật toán | Cao | Hiện `total_cost` không hoàn toàn cùng ý nghĩa giữa thuật toán; distance/time cần tính và ghi đơn vị nhất quán. |
| UI-08 | Thêm legend nổi gọn ở góc bản đồ hoặc hàng ngang trên bản đồ; dùng cả màu, ký hiệu và nhãn cho Start, Goal, Current, Frontier, Explored, Final path. | Người mới hiểu bản đồ ngay, tăng accessibility và giảm nhu cầu tra tài liệu. | `src/gui/assets/map.html`, `src/gui/map_widget.py` | Thấp | Legend có thể che bản đồ ở màn hình hẹp; cần dạng collapse. |
| UI-09 | Định nghĩa lại state style: current có viền/ring riêng và chỉ tồn tại một bước; frontier tô node; explored dùng màu dịu; inspected/relaxed edge không dùng màu final path; chỉ finish mới dùng style final. | Phân biệt chính xác current/frontier/explored/final path và tránh diễn giải sai. | `src/gui/assets/map.html`, `src/gui/map_widget.py`, `src/models/models.py`, các file thuật toán | Cao | Thay đổi event semantics có thể ảnh hưởng tất cả thuật toán và replay cũ. |
| UI-10 | Vẽ start/goal bằng marker hoặc lớp overlay độc lập với state search; giữ biểu tượng S/G sau khi node nằm trên final path. | Điểm đầu/cuối luôn nhận biết được và hướng tuyến rõ ràng. | `src/gui/assets/map.html` | Trung bình | Nhiều lớp marker có thể làm node dày; cần kiểm tra zoom và kích thước. |
| UI-11 | Log theo `step['type']`, ví dụ EXPAND, DISCOVER, UPDATE, FINISH; thêm step index và chỉ dùng “Visiting” cho EXPAND. | Log khớp animation, dễ kiểm tra thuật toán và tăng độ tin cậy của demo. | `src/gui/main_window.py`, `src/gui/map_widget.py` | Thấp | Log chi tiết có thể tăng nhanh; cần giới hạn hoặc filter. |
| UI-12 | Đổi Status thành tab “Event Log” riêng hoặc drawer có thể mở rộng; dùng prefix/badge màu cho info, step, success, error và giữ graph summary thành card thay vì text block. | Thông tin dễ quét, giảm rối sidebar và dành chiều cao cho control thiết yếu. | `src/gui/main_window.py`, hai file QSS | Trung bình | Di chuyển log có thể làm người dùng hiện tại mất vị trí quen thuộc; cần giữ truy cập một bước. |
| UI-13 | Gộp Pause/Resume thành một toggle; đặt Run là primary full-width; đưa Step, Replay, Reset thành toolbar 2×2 hoặc hàng icon có nhãn. | Giảm đáng kể chiều cao, làm rõ hành động chính và giảm sự lộn xộn. | `src/gui/main_window.py`, hai file QSS | Trung bình | Cần đảm bảo label/icon rõ ở cả theme và trạng thái disabled. |
| UI-14 | Xây dựng một animation state machine (`idle`, `ready`, `running`, `paused`, `finished`) và cập nhật toàn bộ button từ một hàm duy nhất. | Loại bỏ trạng thái control mâu thuẫn và làm luồng thao tác dễ đoán. | `src/gui/main_window.py`, `src/gui/map_widget.py` | Trung bình | Chạm vào nhiều handler; cần test mọi chuỗi Run/Pause/Step/Replay/Reset. |
| UI-15 | Chọn mặc định 250 hoặc 500 ms; thay combo bằng slider/segmented control có nhãn Slow–Fast và vẫn cho phép 0 ms dưới tên “Instant”. | Người dùng quan sát được thuật toán ngay lần chạy đầu và giảm thao tác không cần thiết. | `src/gui/main_window.py` | Thấp | Dataset lớn ở tốc độ chậm có thể kéo dài; cần nút skip/instant dễ thấy. |
| UI-16 | Hiển thị dataset bằng tên thân thiện kèm district/node count; start/goal theo mẫu `ID — Name`, có search/filter và hành động chọn trực tiếp trên bản đồ nếu phù hợp. | Làm rõ luồng chọn dữ liệu, giảm nhầm lẫn và dùng được với graph lớn. | `src/gui/main_window.py`, `src/gui/map_widget.py`, `src/gui/assets/map.html`, `src/data/data_loader.py` | Cao | Chọn trên map cần cầu nối JavaScript → Python và xử lý node dày. |
| UI-17 | Đồng bộ theme vào map: truyền theme sang JavaScript, đổi control/overlay/legend và cân nhắc tile layer phù hợp; thay hai button bằng một toggle có trạng thái selected rõ. | Màu sắc nhất quán, giảm chói ở Dark Mode và tạo cảm giác hoàn thiện. | `src/gui/main_window.py`, `src/gui/map_widget.py`, `src/gui/assets/map.html`, hai file QSS | Trung bình | Dark tile có thể phụ thuộc nhà cung cấp ngoài và attribution; màu thuật toán phải giữ đủ tương phản. |
| UI-18 | Xây hierarchy ba cấp: primary Run, secondary playback, tertiary Reset/theme; chuẩn hóa font size, spacing 4/8/12/16 và chiều cao input/button giữa hai theme. | Giao diện nhất quán, chuyên nghiệp hơn và làm rõ luồng thao tác mà không trang trí quá mức. | `src/gui/main_window.py`, hai file QSS | Trung bình | Thay đổi global selector có thể tác động mọi widget; nên thêm object name/property để scope style. |
| UI-19 | Ẩn thuật toán mock khỏi build demo hoặc chuyển vào Developer mode; nếu giữ lại thì chuyển event về `expand/discover/update/finish` trước khi hiển thị. | Mọi lựa chọn công khai đều trực quan hóa đúng và danh sách thuật toán phù hợp đồ án học thuật. | `src/algorithms/algorithms.py`, `src/algorithms/mock3_algorithm.py`, `src/gui/assets/map.html` | Thấp | Có thể mất công cụ test thủ công nếu xóa hẳn; nên giữ đường bật riêng cho developer. |
| UI-20 | Dùng inline alert/toast cho load/run error và no-path; empty map hiển thị ba bước ngắn “Chọn dataset → Load → Chọn điểm”; trạng thái loading khóa action liên quan. | Người mới biết bước tiếp theo, lỗi dễ thấy và giảm thao tác lặp. | `src/gui/main_window.py`, `src/gui/assets/map.html`, hai file QSS | Trung bình | Toast tự biến mất có thể bị bỏ lỡ; lỗi quan trọng vẫn cần lưu trong Event Log. |
| UI-21 | Gắn nhãn rõ “Single-route search” cho phạm vi hiện tại; chỉ thêm multi-stop/delivery queue sau khi người dùng xác nhận đây là mục tiêu của đồ án. | Kỳ vọng khớp chức năng, tránh mở rộng quá mức và giữ giao diện đơn giản. | `src/gui/main_window.py`, `src/gui/delivery_panel.py` | Thấp nếu chỉ đổi nhãn; Cao nếu thêm multi-stop | Multi-stop thay đổi cả mô hình bài toán, thuật toán và layout; không nên xem là chỉnh UI đơn thuần. |
| UI-22 | Nếu cần so sánh học thuật, thêm tab “Comparison” lưu mỗi run thành một hàng: algorithm, start/goal, success, cost, visited count, runtime; không đặt bảng này cạnh bản đồ khi đang chạy. | So sánh thuật toán dễ hơn mà không làm loãng visualization chính. | `src/gui/main_window.py`, `src/models/models.py`, các file thuật toán | Cao | Cần chuẩn hóa metric và đơn vị; bảng lịch sử có thể gây hiểu sai nếu input giữa các run khác nhau. |

## 4. Đề xuất bố cục mới

### Desktop từ 1024 px trở lên

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Route Visualizer   Dataset: District 10   A* Search   ● Ready   Theme / More │
├──────────────────────┬───────────────────────────────────────────────────────┤
│ SETUP                │ MAP / ALGORITHM VISUALIZATION                         │
│ Dataset              │                                                       │
│ Start                │  [Legend: S  G  Current  Frontier  Explored  Path]   │
│ Goal                 │                                                       │
│ Algorithm            │                                                       │
│ Speed                │                                                       │
│ [       Run       ]  │                                                       │
│                      │                                                       │
│ PLAYBACK             │                                                       │
│ [Pause/Resume] [Step]│                                                       │
│ [Replay]       [Reset]│                                                       │
├──────────────────────┼───────────────────────────────┬───────────────────────┤
│ Collapsible setup    │ ALGORITHM STATE               │ RESULT SUMMARY        │
│ or Event Log tab     │ Current | Frontier | Explored │ Cost | Nodes | Runtime│
│                      │ A*: g(n) | h(n) | f(n)        │ Route / Message       │
└──────────────────────┴───────────────────────────────┴───────────────────────┘
```

Nguyên tắc:

* Bản đồ vẫn là vùng lớn nhất.
* Sidebar chỉ giữ setup và playback; Event Log không chiếm chiều cao thường trực.
* Algorithm State và Result Summary tách riêng vì một bên thay đổi theo từng bước, một bên chỉ chốt khi hoàn tất.
* Hàng dưới có thể co về tab `State | Result | Log` khi chiều cao hạn chế.

### Layout hẹp

```text
┌──────────────────────────────────────┐
│ Route Visualizer     ● Ready   ☰  ◐ │
├──────────────────────────────────────┤
│ MAP                                  │
│ [Legend ▾]                           │
│                                      │
│                                      │
├──────────────────────────────────────┤
│ [State] [Result] [Log]               │
│ Current: N12    Step: 08/31           │
│ Frontier: N04, N18, +3               │
├──────────────────────────────────────┤
│ [      Pause/Resume      ] [Step]    │
└──────────────────────────────────────┘

☰ mở Control Drawer:
Dataset → Start → Goal → Algorithm → Speed → Run
```

Nguyên tắc:

* Không ẩn khả năng cấu hình; setup nằm trong drawer có thể mở lại.
* Playback đang dùng được ghim ở đáy trong lúc chạy.
* Result/State/Log dùng tab để tránh xếp tất cả theo chiều dọc.
* Header chỉ giữ một theme toggle và một menu.

## 5. Phân nhóm ưu tiên

### Ưu tiên 1 — Cần xử lý trước

* `UI-01` — Layout desktop bị ép chiều cao và thiếu vùng cuộn.
* `UI-02` — Layout hẹp ẩn toàn bộ control.
* `UI-03` — Header ngăn cửa sổ đạt chiều rộng mobile.
* `UI-05` — Thiếu current/frontier/explored/visited order.
* `UI-06` — A* không hiển thị `g/h/f`.
* `UI-07` — Không có result summary.
* `UI-09` — Màu không phân biệt đúng state thuật toán.
* `UI-11` — Log diễn giải sai loại step.
* `UI-14` — Trạng thái button có thể lệch animation.
* `UI-19` — Thuật toán mock công khai nhưng không tương thích renderer.

### Ưu tiên 2 — Nên cải thiện

* `UI-04` — Hợp nhất panel kết quả và bind dữ liệu thật.
* `UI-08` — Thêm legend.
* `UI-10` — Giữ start/goal nổi bật xuyên suốt.
* `UI-12` — Tổ chức lại Status/Event Log.
* `UI-13` — Giảm mật độ execution controls.
* `UI-15` — Sửa tốc độ mặc định.
* `UI-16` — Làm dataset/node selection dễ hiểu và dễ tìm.
* `UI-17` — Đồng bộ dark theme với bản đồ.
* `UI-18` — Chuẩn hóa hierarchy, typography và spacing.
* `UI-20` — Cải thiện empty/error/loading feedback.

### Ưu tiên 3 — Hoàn thiện giao diện

* `UI-21` — Làm rõ phạm vi single-route hoặc mở rộng delivery sau khi chốt yêu cầu.
* `UI-22` — Thêm màn hình so sánh thuật toán nếu cần cho phần báo cáo/demo.
* Sau khi state machine ổn định, mới thêm transition nhẹ khi current node đổi, panel mở/đóng hoặc kết quả xuất hiện; không animation các metric liên tục gây mất tập trung.

## 6. Thứ tự triển khai đề xuất

1. **`UI-19` — Chuẩn hóa danh sách thuật toán công khai.** Cần bảo đảm mọi lựa chọn phát cùng event contract trước khi thiết kế UI dùng contract đó.
2. **`UI-14` — Xây dựng animation state machine.** Đây là nền cho enable/disable control, status header và responsive playback.
3. **`UI-11` — Sửa ngữ nghĩa Event Log.** Cho phép kiểm chứng state thuật toán trước khi đổi màu hoặc thêm panel mới.
4. **`UI-01` — Gỡ giới hạn chiều cao desktop.** Cần có layout co giãn ổn định trước khi đưa thêm Algorithm State/Result vào màn hình.
5. **`UI-13` — Thu gọn execution controls.** Giải phóng không gian trong sidebar và giảm nguyên nhân gây min-height lớn.
6. **`UI-02` và `UI-03` — Thiết kế responsive thực và header hẹp.** Thực hiện sau khi control đã được gom nhóm để drawer mobile không lặp lại bố cục cũ quá dài.
7. **`UI-09` và `UI-10` — Chuẩn hóa state/màu bản đồ.** Xác lập ngôn ngữ trực quan trước khi viết legend.
8. **`UI-08` — Thêm legend.** Làm sau khi bộ màu và ký hiệu đã ổn định để tránh phải sửa hai lần.
9. **`UI-05` — Thêm Algorithm State.** Khi event contract và layout đã ổn định mới bind current/frontier/explored.
10. **`UI-06` — Thêm bảng `g/h/f`.** Là phần mở rộng theo thuật toán của Algorithm State và nên tái sử dụng cấu trúc panel đã có.
11. **`UI-07` và `UI-04` — Tạo Result Summary duy nhất.** Chuẩn hóa metric và bỏ panel mobile tĩnh cùng lúc để tránh hai nguồn dữ liệu.
12. **`UI-12` — Chuyển Status thành Event Log có phân cấp.** Sau khi State và Result đã có vị trí riêng, log không còn phải gánh mọi loại thông tin.
13. **`UI-15`, `UI-16`, `UI-18`, `UI-20` — Hoàn thiện luồng nhập và visual hierarchy.** Đây là các cải tiến ít phụ thuộc contract nhưng nên áp dụng trên layout cuối cùng.
14. **`UI-17` — Đồng bộ theme.** Làm sau khi màu state, legend và component mới đã chốt để kiểm tra contrast một lần có hệ thống.
15. **`UI-21` — Chốt phạm vi giao hàng.** Chỉ đổi cấu trúc chức năng khi người dùng đã quyết định single-route hay multi-stop.
16. **`UI-22` — Thêm Comparison nếu được chọn.** Cần dựa trên Result Summary và metric đã chuẩn hóa nên phải thực hiện sau cùng.

## 7. Những nội dung chưa nên chỉnh sửa

* Không nên thay thuật toán hoặc công thức cost chỉ để phục vụ bố cục; trước hết cần thống nhất đơn vị và ý nghĩa metric.
* Không nên thay Leaflet hoặc OpenStreetMap: map hiện pan/zoom tốt, fit bounds và tooltip node đã đáp ứng nền tảng trình diễn.
* Không nên bỏ contract `SearchStep`/`SearchResult`; nên mở rộng có kiểm soát vì đây là ranh giới tốt giữa thuật toán và UI.
* Không nên biến tất cả thông tin thành card luôn hiển thị. Bản đồ phải tiếp tục là vùng thị giác chính; State/Result/Log có thể dùng tab hoặc collapse.
* Không nên thêm animation trang trí trước khi xử lý event semantics, button state và responsive.
* Không nên thêm lớp congestion/risk/flood lên bản đồ ngay trong đợt sửa layout; dữ liệu này nên là layer tùy chọn sau khi legend và state color không còn xung đột.
* Không nên tạo thêm một result component mới song song với `DeliveryPanel` trước khi quyết định component nào là nguồn duy nhất.
* Không nên đổi toàn bộ bảng màu chỉ vì thẩm mỹ; màu mới phải ưu tiên khả năng phân biệt state, contrast và tính nhất quán giữa Light/Dark.

## 8. Các câu hỏi cần người dùng quyết định

1. Trong lúc chạy, diện tích nên ưu tiên tuyệt đối cho **bản đồ** hay dành khoảng 25–30% chiều ngang/chiều cao cho **Algorithm State**?
2. Sidebar desktop nên luôn mở, có thể thu gọn, hay chuyển hoàn toàn thành drawer giống layout hẹp?
3. Result Summary nên ưu tiên **metric card dễ thuyết trình** hay **bảng chi tiết dễ so sánh số liệu**?
4. Chế độ chạy mặc định nên là autoplay 250/500 ms hay bắt đầu ở step-by-step và chờ người dùng nhấn Next?
5. Có cần màn hình Comparison lưu nhiều lần chạy để phục vụ báo cáo BFS/DFS/A*/GA không?
6. Phạm vi đồ án hiện tại là tìm đường một start–goal hay phải hỗ trợ multi-stop/delivery routing trong giao diện này?
7. Dark Mode có bắt buộc dùng dark map tile hay chỉ cần các control/overlay tối trong khi giữ tile OSM hiện tại?

Với phạm vi đồ án hiện tại và việc sau này có thêm **Graph Mode chỉ hiển thị node–edge**, tôi đề xuất chốt như sau.

# Quyết định cho Map Mode hiện tại

| Vấn đề           | Quyết định đề xuất                                                    |
| ---------------- | --------------------------------------------------------------------- |
| Diện tích bản đồ | Bản đồ chiếm khoảng **70–75%** khu vực chính                          |
| Algorithm State  | Chiếm khoảng **25–30%**, có thể thu gọn                               |
| Sidebar desktop  | Luôn mở mặc định nhưng **có nút collapse**                            |
| Result Summary   | Dùng **metric card trước**, bảng chi tiết đặt bên dưới hoặc trong tab |
| Chế độ chạy      | Mặc định **autoplay 500 ms**, có Pause, Next, Previous                |
| Comparison       | Có, nhưng phát triển sau khi luồng chạy đơn ổn định                   |
| Phạm vi routing  | Thiết kế UI hỗ trợ multi-stop, nhưng trước mắt hoàn thiện start–goal  |
| Dark Mode        | Không bắt buộc dark map tile ở giai đoạn này                          |
| Mode mới         | Có `Map View` và `Graph View`, nhưng chỉ triển khai `Map View` trước  |

---

## 1. Bản đồ hay Algorithm State?

### Đề xuất

Dành khoảng:

* **70–75% cho bản đồ**
* **25–30% cho Algorithm State**

Không nên để bản đồ chiếm tuyệt đối 100%, vì mục tiêu đồ án không chỉ là tìm đường mà còn phải **trình diễn cách thuật toán hoạt động**.

Bố cục desktop hợp lý:

```text
┌──────────────────────────────────────────────────────────────┐
│ Header                                                       │
├──────────────┬───────────────────────────────┬───────────────┤
│ Sidebar      │ Map                           │ Algorithm     │
│ 18–22%       │ 55–60%                        │ State 22–27%  │
│              │                               │               │
│ Controls     │ Route visualization           │ Current node  │
│ Inputs       │ Frontier / explored overlay   │ Frontier      │
│ Run buttons  │ Final path                    │ Explored      │
│              │                               │ g / h / f     │
├──────────────┴───────────────────────────────┴───────────────┤
│ Result Summary                                               │
└──────────────────────────────────────────────────────────────┘
```

### Lý do

Nếu Algorithm State quá nhỏ:

* Không đọc được frontier.
* Không thấy rõ `g(n)`, `h(n)`, `f(n)`.
* Khó trình bày thuật toán trước giảng viên.

Nếu Algorithm State quá lớn:

* Bản đồ bị thu hẹp.
* Tuyến đường và node khó quan sát.
* Giao diện giống dashboard số liệu hơn là hệ thống tìm đường.

### Cách xử lý tốt nhất

Algorithm State nên có nút:

```text
[Collapse]
```

Khi thu gọn, bản đồ tự mở rộng. Như vậy người dùng có thể chọn:

* Quan sát thuật toán.
* Hoặc tập trung xem tuyến đường.

---

## 2. Sidebar desktop nên như thế nào?

### Đề xuất

Desktop:

* Sidebar **mở mặc định**.
* Có nút thu gọn.
* Khi thu gọn chỉ còn icon hoặc một nút mở lại.

Mobile hoặc màn hình hẹp:

* Sidebar chuyển thành **drawer**.

Không nên dùng drawer hoàn toàn trên desktop, vì người dùng thường xuyên cần:

* Chọn thuật toán.
* Chọn start và goal.
* Điều chỉnh tốc độ.
* Nhấn Run, Pause, Reset.
* Chọn heuristic hoặc tham số.

Nếu mỗi lần cần thao tác đều phải mở drawer, luồng sử dụng sẽ chậm và khó trình diễn.

### Trạng thái đề xuất

```text
Desktop:
[ Sidebar ][ Map ][ Algorithm State ]

Desktop collapsed:
[ > ][          Map          ][ Algorithm State ]

Mobile:
[Menu] [Map]
       Drawer mở khi cần
```

---

## 3. Result Summary nên dùng card hay bảng?

### Đề xuất

Ưu tiên **metric card** cho một lần chạy.

Ví dụ:

```text
┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│ Distance       │ │ Runtime        │ │ Visited Nodes  │
│ 4.82 km        │ │ 18.4 ms        │ │ 127            │
└────────────────┘ └────────────────┘ └────────────────┘

┌────────────────┐ ┌────────────────┐
│ Path Cost      │ │ Estimated Time │
│ 5,240          │ │ 16 minutes     │
└────────────────┘ └────────────────┘
```

Metric card phù hợp để:

* Nhìn nhanh.
* Trình bày trước giảng viên.
* Làm nổi bật kết quả chính.
* Không khiến giao diện bị nặng.

Bảng nên dành cho:

* Comparison Mode.
* Lịch sử nhiều lần chạy.
* So sánh BFS, DFS, UCS, A*, GA.

Ví dụ bảng comparison:

| Algorithm | Distance | Runtime | Visited | Path Cost | Found |
| --------- | -------: | ------: | ------: | --------: | ----- |
| BFS       |   5.2 km |   14 ms |     184 |     5,800 | Yes   |
| A*        |   4.8 km |    9 ms |      62 |     5,240 | Yes   |
| GA        |   4.9 km |  120 ms |       — |     5,310 | Yes   |

Vì vậy nên phân biệt:

* **Single Run:** metric cards.
* **Multiple Runs:** comparison table.

---

## 4. Chế độ chạy mặc định nên thế nào?

### Đề xuất

Mặc định:

```text
Autoplay: 500 ms / bước
```

Có các điều khiển:

```text
[Run] [Pause] [Previous] [Next] [Reset]
Speed: [250 ms] [500 ms] [1000 ms]
```

Không nên mặc định ở step-by-step hoàn toàn, vì:

* Người dùng mới có thể không biết phải nhấn Next.
* Trình diễn thuật toán dài sẽ mất thời gian.
* Với graph lớn, nhấn từng bước rất bất tiện.

Không nên mặc định 250 ms vì có thể quá nhanh để quan sát.

`500 ms` là mức cân bằng:

* Đủ thấy node đang được mở rộng.
* Không khiến animation quá chậm.
* Phù hợp demo trên lớp.

### Quy tắc hành vi

* Nhấn **Run**: autoplay.
* Nhấn **Pause**: dừng tại bước hiện tại.
* Nhấn **Next**: đi một bước.
* Nhấn **Previous**: quay lại trạng thái trước, nếu hệ thống có lưu snapshot.
* Thay đổi tốc độ không làm reset thuật toán.
* Khi hoàn thành, hiển thị final path và Result Summary.

Nếu chưa muốn làm `Previous` vì phức tạp, giai đoạn đầu có thể chỉ cần:

```text
Run | Pause | Next | Reset
```

---

## 5. Có cần màn hình Comparison không?

### Có, nhưng không nên làm ngay.

Comparison là chức năng rất giá trị cho đồ án, vì giảng viên thường quan tâm:

* Thuật toán nào chạy nhanh hơn?
* Thuật toán nào duyệt ít node hơn?
* Đường đi có tối ưu không?
* Heuristic ảnh hưởng thế nào?
* BFS, DFS, UCS và A* khác nhau ra sao?

Tuy nhiên nên chia thành hai giai đoạn.

### Giai đoạn hiện tại

Hoàn thiện:

1. Chạy một thuật toán.
2. Hiển thị animation đúng.
3. Hiển thị Result Summary.
4. Reset và chạy lại ổn định.

### Giai đoạn sau

Thêm:

```text
[Save Run]
```

Mỗi lần lưu một record:

```json
{
  "algorithm": "A*",
  "start": "A",
  "goal": "F",
  "distance": 4820,
  "runtime_ms": 18.4,
  "visited_nodes": 62,
  "path_cost": 5240
}
```

Sau đó hiển thị trong Comparison View.

### Lưu ý về GA

GA không cùng loại hoàn toàn với BFS, DFS và A*.

* BFS, DFS, A*: tìm đường trên graph.
* GA thường phù hợp hơn với bài toán tối ưu nhiều điểm giao hàng hoặc thứ tự ghé thăm.

Do đó comparison phải ghi rõ:

* Cùng dataset.
* Cùng start và goal.
* Cùng cost function.
* Cùng điều kiện chạy.

Không nên đặt GA vào bảng so sánh start–goal nếu GA đang giải một bài toán khác.

---

## 6. Start–goal hay multi-stop?

Theo yêu cầu đồ án giao hàng, hướng cuối cùng nên là **multi-stop delivery routing**.

Tuy nhiên trước mắt nên hoàn thiện `start–goal` trước.

### Giai đoạn 1 — Start–goal

UI chỉ cần:

```text
Start Location
Goal Location
Algorithm
Run
```

Mục tiêu:

* Kiểm tra BFS, DFS, UCS, A*.
* Kiểm tra animation.
* Kiểm tra frontier và explored.
* Kiểm tra đường đi cuối.
* Chuẩn hóa metrics.

### Giai đoạn 2 — Multi-stop

Thêm danh sách:

```text
Start:
  HCMUS

Delivery Stops:
  1. Nguyễn Thị Minh Khai
  2. Võ Văn Tần
  3. Lê Văn Sỹ
  4. Điện Biên Phủ

[Add Stop]
[Remove]
[Reorder]
```

### Thiết kế ngay từ bây giờ

Dù chưa triển khai multi-stop, không nên code input theo kiểu chỉ có hai biến UI cố định khó mở rộng.

Nên coi dữ liệu đầu vào là:

```python
start_node
delivery_nodes = []
```

Ở giai đoạn hiện tại:

```python
delivery_nodes = [goal_node]
```

Sau này có thể mở rộng:

```python
delivery_nodes = [node_a, node_b, node_c]
```

Như vậy UI hiện tại vẫn là start–goal nhưng kiến trúc không bị khóa.

---

## 7. Dark Mode có cần dark map tile không?

### Đề xuất hiện tại

Không bắt buộc dùng dark map tile.

Có thể áp dụng Dark Mode cho:

* Header.
* Sidebar.
* Algorithm State.
* Result cards.
* Button.
* Input.
* Modal.
* Tooltip.

Trong khi giữ tile OSM hiện tại.

### Vì sao?

Dark map tile tạo thêm các vấn đề:

* Phải tìm tile provider phù hợp.
* Có thể cần API key.
* Có thể bị giới hạn request.
* Màu route, frontier và explored phải chỉnh lại.
* Khó đảm bảo attribution.
* Làm tăng phạm vi công việc nhưng không trực tiếp cải thiện thuật toán.

Với đồ án học thuật, ưu tiên:

1. Thuật toán đúng.
2. Trực quan hóa rõ.
3. Giao diện dễ sử dụng.
4. Metrics chính xác.

Dark tile là phần hoàn thiện sau.

Nếu giữ tile sáng trong dark mode, nên thêm đường viền nhẹ quanh map để tách map khỏi control tối.

---

# Thiết kế hai mode

Bạn muốn có:

1. **Map View**: hiển thị bản đồ thực tế.
2. **Graph View**: chỉ hiển thị node và edge.

Đây là hướng rất tốt vì hai mode phục vụ hai mục đích khác nhau.

## Map View

Phục vụ:

* Bối cảnh giao hàng thực tế.
* Đường phố TP.HCM.
* Khoảng cách địa lý.
* Tuyến đường thực tế.
* Kẹt xe, ngập hoặc trạng thái đường.

## Graph View

Phục vụ:

* Quan sát graph rõ hơn.
* Nhìn node, edge và trọng số.
* Giải thích BFS, DFS, UCS, A*.
* Thấy frontier và explored không bị ảnh hưởng bởi chi tiết bản đồ.
* Dễ trình bày thuật toán trong báo cáo.

## Cách chuyển mode

Nên đặt ở header:

```text
View Mode: [ Map ] [ Graph ]
```

Hoặc dùng segmented control:

```text
┌─────────────┬──────────────┐
│  Map View   │  Graph View  │
└─────────────┴──────────────┘
```

Không nên tạo hai ứng dụng hoặc hai trang hoàn toàn tách biệt ngay từ đầu.

Hai mode nên dùng chung:

* Algorithm selector.
* Start và goal.
* Run state.
* Frontier.
* Explored.
* Current node.
* Path result.
* Metrics.

Chỉ khác phần renderer:

```text
MapRenderer
GraphRenderer
```

Cấu trúc tư duy:

```text
Algorithm Engine
       │
       ├── Search State
       │   ├── current
       │   ├── frontier
       │   ├── explored
       │   └── finalPath
       │
       └── Visualization
           ├── Map View
           └── Graph View
```

Điều này giúp tránh việc sau này phải viết lại thuật toán riêng cho Graph View.

---

# Phạm vi triển khai theo giai đoạn

Phần dưới đây là thứ tự chốt ở thời điểm lập kế hoạch ban đầu. Map View đã ổn định và **Graph View hiện cũng đã được triển khai** theo đúng kiến trúc dùng chung state/playback; chỉ Comparison và multi-stop còn để cho giai đoạn sau.

Thứ tự nên là:

1. Chia lại layout: sidebar, map, algorithm state.
2. Làm sidebar có thể thu gọn.
3. Chuẩn hóa controls Run, Pause, Next, Reset.
4. Hiển thị Algorithm State rõ ràng.
5. Thêm Result Summary dạng metric card.
6. Hoàn thiện start–goal.
7. Chuẩn bị cấu trúc dữ liệu cho multi-stop.
8. Thêm nút chuyển `Map View / Graph View`; bước này đã hoàn thành và placeholder `Coming soon` đã được thay bằng Canvas graph thật.
9. Sau khi Map View ổn định, phát triển Graph View dùng chung playback; bước này đã hoàn thành.
10. Cuối cùng mới làm Comparison và Dark Mode nâng cao.

# Kết luận chốt cho Agent

Các quyết định ban đầu (được giữ lại để đối chiếu lịch sử triển khai):

```text
- Ưu tiên đánh giá và hoàn thiện Map View trước.
- Graph View chỉ bắt đầu sau khi Map View ổn định; điều kiện này đã đạt và Graph View đã hoàn thành.
- Tuy nhiên, layout và component architecture phải dự phòng cho hai mode:
  Map View và Graph View.
- Bản đồ chiếm khoảng 70–75% khu vực nội dung chính.
- Algorithm State chiếm khoảng 25–30% và có thể thu gọn.
- Sidebar desktop mở mặc định nhưng có thể collapse.
- Result Summary dùng metric cards cho một lần chạy.
- Comparison table là chức năng giai đoạn sau.
- Autoplay mặc định 500 ms, đồng thời hỗ trợ Pause, Next và Reset.
- Hoàn thiện start–goal trước nhưng không thiết kế kiến trúc khóa khả năng multi-stop.
- Dark Mode chưa cần dark map tile.
- Agent chỉ cập nhật plan.md, tuyệt đối chưa sửa code.
```

---

# Báo cáo triển khai Map View

**Nhánh triển khai:** `feature/redesign_ui_3`  
**Ngày cập nhật:** 03/08/2026  
**Phạm vi:** Hoàn thiện Map View và Graph View dùng chung playback; Comparison đầy đủ tiếp tục thuộc giai đoạn sau.

> **Ghi chú về phạm vi:** Quy tắc “chỉ cập nhật `plan.md`, chưa sửa code” ở giai đoạn review phía trên đã kết thúc khi người dùng yêu cầu triển khai toàn bộ kế hoạch. Phần dưới ghi lại chính xác những nội dung đã được hiện thực hóa sau yêu cầu đó.

## 1. Trạng thái theo từng UI-ID

| ID | Trạng thái | Nội dung đã triển khai |
| --- | --- | --- |
| UI-01 | Hoàn thành | Sidebar đã được đưa vào `QScrollArea`; layout không còn bị năm group và các nút playback ép chiều cao. Sidebar desktop dùng splitter kéo bằng chuột trong khoảng 260–520 px; khi đổi chiều rộng, Map View co/giãn trực tiếp theo phần không gian còn lại. Cửa sổ hỗ trợ kích thước tối thiểu `430×620`. |
| UI-02 | Hoàn thành | Thêm responsive breakpoint; ở màn hình hẹp sidebar trở thành drawer mở bằng nút menu và vẫn giữ đầy đủ luồng Load → Configure → Run. |
| UI-03 | Hoàn thành | Header được rút gọn thành “Route Lab”; Map/Graph và State control phụ được ẩn theo breakpoint, theme chuyển thành nút gọn trên màn hình hẹp. |
| UI-04 | Hoàn thành | Loại bỏ panel mobile tĩnh không đồng bộ. `ResultSummaryPanel` trở thành nguồn hiển thị kết quả duy nhất cho cả desktop và layout hẹp. |
| UI-05 | Hoàn thành | Thêm `AlgorithmStatePanel` hiển thị Current node, Frontier, Explored, Visited order và số bước hiện tại/tổng số bước. Panel có thể kéo rộng đến 680 px và làm map co lại tương ứng; Frontier/Explored/Visited có `View all (N)` để xem, cuộn và copy toàn bộ node. |
| UI-06 | Hoàn thành | Hiển thị `g`, `h`, `f` từ `SearchStep.metrics`; metric bổ sung của GA/UCS được hiển thị dưới state panel. |
| UI-07 | Hoàn thành | Result Summary có trạng thái success/failure, distance, runtime, visited nodes, path cost, estimated time, route và bảng chi tiết từng đoạn đường. |
| UI-08 | Hoàn thành | Thêm legend trên bản đồ cho Start, Goal, Current, Frontier, Explored và Final path; legend tự thu gọn ở màn hình hẹp. |
| UI-09 | Hoàn thành | Tách style Current, Frontier, Explored, inspected edge, relaxed edge và Final path. Chỉ step `finish` dùng màu final path. |
| UI-10 | Hoàn thành | Start và Goal dùng marker `S/G` độc lập với state node nên không bị animation hoặc final path ghi đè. |
| UI-11 | Hoàn thành | Event Log ghi đúng loại `EXPAND`, `DISCOVER`, `UPDATE`, `FINISH`; có step index và không còn diễn giải mọi node là “Visiting”. |
| UI-12 | Hoàn thành | Status cũ được thay bằng tab Event Log có timestamp và phân loại màu INFO, STEP, SUCCESS, ERROR. Graph summary được tách khỏi log. |
| UI-13 | Hoàn thành | Pause/Resume được gộp thành một nút; Run là primary action; Previous, Next, Replay và Reset nằm trong lưới playback gọn hơn. |
| UI-14 | Hoàn thành | Thêm execution state machine `idle`, `loading`, `ready`, `computing`, `running`, `paused`, `finished`; toàn bộ trạng thái enable/disable được cập nhật tập trung. `loading/computing` giúp giao diện phản hồi đúng trong lúc map hoặc worker chưa sẵn sàng. |
| UI-15 | Hoàn thành | Autoplay dùng profile `Instant`, `Fast · ~5 s`, `Balanced · ~15 s` và `Detailed · ~30 s`; mặc định Balanced. Bổ sung `Step by step · Manual`: timer/autoplay luôn tắt, kết quả search chờ ở step 0 và chỉ dịch chuyển đúng một raw event khi người dùng bấm Previous/Next. Replay trong manual mode chỉ quay về trạng thái đầu, không tự chạy lại. Dataset lớn ở các profile autoplay cũ vẫn tự gom adjacent event theo thời lượng mục tiêu. Timer tính cả thời gian render/state update thay vì chờ thêm sau khi vẽ. Thay đổi tốc độ không reset thuật toán; Instant khôi phục đầy đủ Algorithm State nhưng chỉ dựng final path trên map. |
| UI-16 | Hoàn thành | Dataset hiển thị tên thân thiện kèm số node; start/goal hiển thị `ID — Name`, sắp xếp tự nhiên và hỗ trợ tìm kiếm bằng completer. |
| UI-17 | Hoàn thành trong phạm vi đã chốt | Light/Dark theme được chuẩn hóa cho header, sidebar, state, result, log và overlay bản đồ. Tile OSM vẫn sáng đúng quyết định chưa cần dark tile. |
| UI-18 | Hoàn thành | Chuẩn hóa primary/secondary/tertiary button, typography, spacing, input, card, tab, badge và disabled state giữa hai theme. |
| UI-19 | Hoàn thành | “Mock 3 Search” đã bị ẩn khỏi danh sách demo. Thêm UCS chuẩn hóa cùng contract `expand/discover/update/finish`. |
| UI-20 | Hoàn thành | Thêm alert banner cho success/error, map message cho empty/loading/completed và hướng dẫn bước tiếp theo khi chưa load graph. |
| UI-21 | Hoàn thành nền tảng | UI ghi rõ “Single-route search”; dữ liệu đầu vào đã có `delivery_nodes`, hiện chứa goal duy nhất và có thể mở rộng thành multi-stop sau này. |
| UI-22 | Hoãn theo kế hoạch | Đã thêm tab `Comparison · Soon` và chuẩn bị các metric cần thiết. Chưa triển khai lưu lịch sử/bảng so sánh vì kế hoạch chốt thực hiện sau khi single-run ổn định. |
| UI-23 | Hoàn thành | Graph View Canvas đã thay thế placeholder: hiển thị node/edge, tên node, `g/h/f`, cost/distance edge, state inspect/relax/final path; hỗ trợ pan, zoom, Fit graph, label mode và dùng chung toàn bộ playback với Map View. |

## 2. Các quyết định thiết kế đã áp dụng

* Bản đồ giữ khoảng 70–75% vùng visualization; Algorithm State giữ khoảng 25–30% và có thể thu gọn.
* Sidebar desktop mở mặc định, có nút collapse; layout hẹp dùng drawer.
* Ranh giới Sidebar/Map có thanh kéo rộng 10 px, đổi màu khi hover/drag và resize trực tiếp; combobox co giãn theo độ rộng sidebar nên không còn bị map che hoặc cắt layout.
* Ranh giới Map/Algorithm State cũng là thanh kéo 10 px và resize trực tiếp. State panel hỗ trợ khoảng rộng 210–680 px; danh sách dài có chế độ xem toàn bộ trong vùng cuộn riêng.
* Layout hẹp dùng các tab `State`, `Result`, `Log`, `Compare` để tránh xếp mọi thông tin theo chiều dọc.
* Result Summary ưu tiên metric cards; bảng chi tiết tuyến nằm bên dưới.
* Playback mặc định Balanced với mục tiêu khoảng 15 giây và hỗ trợ Pause, Previous, Next, Replay, Reset. Người dùng có thể chọn `Step by step · Manual` để tắt hoàn toàn autoplay và điều khiển từng raw event bằng Previous/Next; Replay chỉ đưa visualization về step 0. Search lớn ở các profile autoplay vẫn tự batch raw event; Previous/Next luôn di chuyển đúng một raw event.
* Map View và Graph View là hai renderer hoạt động trong cùng `QStackedWidget`; chỉ view đang mở repaint để tránh trả gấp đôi chi phí Canvas. Cả hai dùng chung một kết quả thuật toán và một playback controller.
* Start–goal được hoàn thiện trước; cấu trúc `delivery_nodes` dự phòng multi-stop.
* Dark Mode giữ tile OSM sáng, chỉ đồng bộ control, panel, overlay và đường viền map.

## 3. Các file đã sửa hoặc bổ sung

| File | Nội dung thay đổi |
| --- | --- |
| `src/gui/main_window.py` | Viết lại layout responsive, header, sidebar/drawer, state machine, playback controls, profile `Step by step · Manual`, Result/Event Log tabs, Map/Graph switch, Comparison placeholder, theme và route metrics. |
| `src/gui/map_widget.py` | Chuẩn hóa playback có backpressure, manual mode không schedule timer, Instant final-path, Previous bằng bounded snapshot, physical-edge dedup, graph-ready polling, step metadata, theme bridge và map message. |
| `src/gui/assets/map.html` | Viết lại visual state, marker S/G, legend, message overlay, Canvas renderer, node index O(1), render batch, large-graph LOD, responsive và theme overlay. |
| `src/gui/graph_widget.py` | File mới: bridge Python–WebEngine cho Graph View, physical-edge payload, theme/selection, readiness và đồng bộ batch/history/reset từ MapWidget playback. |
| `src/gui/assets/graph.html` | File mới: Canvas node-edge renderer, hybrid force/geographic layout, pan/zoom/Fit, node name + `g/h/f`, edge cost/distance và visual state thuật toán. |
| `src/gui/algorithm_state_panel.py` | File mới cho Current, Frontier, Explored, Visited order và `g/h/f`; phục hồi state từ delta, lazy/debounce nội dung `View all`. |
| `src/gui/delivery_panel.py` | Chuyển thành `ResultSummaryPanel`, bổ sung metric cards và bảng chi tiết route; giữ alias tương thích `DeliveryPanel`. |
| `src/gui/themes/light.qss` | Chuẩn hóa đầy đủ light theme và visual hierarchy. |
| `src/gui/themes/dark.qss` | Chuẩn hóa đầy đủ dark theme, giữ map tile sáng theo quyết định. |
| `src/models/models.py` | Mở rộng `SearchStep` với compact delta/frontier position, vẫn tương thích snapshot legacy; `SearchResult` có runtime/distance/time. |
| `src/algorithms/bfs.py` | Phát compact delta theo đúng thao tác queue, không sao chép full state ở mỗi event. |
| `src/algorithms/dfs.py` | Phát compact delta với `frontier_position=front` để UI biểu diễn stack đúng hướng; giữ thứ tự duyệt và visited order. |
| `src/algorithms/a_star.py` | Phát compact delta cùng `g/h/f`; bỏ việc sort frontier chỉ để chụp snapshot, không thay đổi priority queue dùng chọn node. |
| `src/algorithms/genetic_algorithm.py` | Phát state/metric snapshot và giới hạn số lần tạo population/child để tránh lặp vô hạn. |
| `src/algorithms/ucs.py` | File mới: triển khai Uniform Cost Search theo contract visualization chung; phát priority delta thay cho full snapshot. |
| `src/algorithms/algorithms.py` | Đưa UCS vào danh sách công khai và loại Mock 3 khỏi UI demo. |
| `src/data/data_loader.py` | Thêm metadata dataset để hiển thị tên thân thiện và số node. |
| `tests/test_search_contract.py` | Test contract, result metrics, compact-event invariant, regression khóa đường đi/chi phí BFS/DFS/UCS/A* và physical-edge payload của Graph View. |

## 4. Kết quả kiểm thử sau triển khai

| Hạng mục | Kết quả |
| --- | --- |
| Python compile (`compileall`) | Đạt |
| JavaScript syntax của `map.html` | Đạt |
| `git diff --check` | Đạt |
| Contract/regression tests mới | `5 passed` |
| GUI smoke test desktop | Đạt |
| GUI smoke test `430×700` | Đạt |
| Load toàn bộ 17 dataset hiện có | Đạt |
| Load → Run A* → Finish → Previous → Next | Đạt |
| Step by step: Run → chờ step 0 → Next/Previous từng event → Replay | Đạt; timer không active, Replay giữ ở step 0 và các profile autoplay cũ vẫn chạy bình thường. |
| Map View ↔ Graph View trước/trong/sau playback | Đạt |
| Khởi động trực tiếp `Graph View → Load → Run` khi Map còn ẩn | Đạt; Graph readiness độc lập, Map callback không còn chặn playback. |
| Graph View District 12 (7.984 node, 9.358 physical edge) | Đạt; Fast hoàn tất khoảng 5,10 giây, giữ đủ final path/metrics. |
| Light/Dark theme và chuyển desktop/compact | Đạt |

Full test suite còn 3 lỗi legacy đã có từ baseline trước redesign:

1. Test gọi constructor `Node(x=..., y=...)` trong khi model hiện dùng `lat/lon`.
2. Thiếu fixture `data/mock_data.json`.
3. Thiếu fixture `data/map_data.json`.

Ba lỗi này không phát sinh từ thay đổi UI và chưa được sửa để tránh mở rộng ngoài phạm vi kế hoạch.

## 5. Nội dung còn lại cho giai đoạn sau

* Lưu lịch sử run và xây Comparison table với điều kiện so sánh được chuẩn hóa.
* Mở rộng `delivery_nodes` thành UI thêm/xóa/sắp xếp nhiều điểm giao hàng.
* Chỉ cân nhắc dark map tile khi có tile provider, attribution và bộ màu thuật toán phù hợp.

## 6. Bổ sung tối ưu dataset lớn và khả năng phản hồi UI

**Ngày cập nhật:** 02/08/2026  
**Dataset kiểm chứng chính:** `data/map_district_12.json` — 7.984 node, 18.027 raw edge và 35.273 directed adjacency edge.

### 6.1. Nguyên nhân đã xác nhận

* Search chạy đồng bộ trên GUI thread nên Algorithm State bị reset nhưng chưa thể nhận step; các nút trông như bị liệt trong lúc thuật toán chưa trả kết quả.
* BFS/DFS/UCS/A* từng lưu toàn bộ `frontier`, `explored` và `visited_order` trong mỗi event. Với cặp node xa của District 12, thiết kế cũ sao chép khoảng 127 triệu node ID, có lower-bound payload trên 1,2 GiB.
* Renderer cũ gọi `Array.find()` trên gần 8.000 node cho từng directed edge, tương đương khoảng 282 triệu lượt so sánh ở District 12.
* Leaflet tạo hơn 35.000 directed polyline và gần 8.000 marker cùng lúc; mỗi playback event lại quét/style toàn bộ node.
* `AlgorithmStatePanel` dựng `QTextDocument` chứa toàn bộ danh sách ngay cả khi `View all` đang đóng.
* QTimer gửi JavaScript theo interval cố định mà không đợi WebEngine xử lý xong; `Previous` replay toàn bộ lịch sử trên Leaflet.

### 6.2. Nội dung đã triển khai

| Hạng mục | Thay đổi |
| --- | --- |
| Bảo toàn thuật toán | Giữ nguyên queue/stack/priority queue, điều kiện relax, parent reconstruction, path và cost. Thêm regression test khóa kết quả BFS/DFS/UCS/A*. |
| Compact event | BFS/DFS/UCS/A* phát delta `expand/discover/update/finish`; không giữ ba full snapshot trong từng step. DFS mang `frontier_position=front`; UCS/A* mang priority metrics để UI phục hồi đúng thứ tự hiển thị. Contract snapshot cũ vẫn được hỗ trợ cho producer nhỏ/legacy như GA. |
| Worker thread | `SearchWorker` chạy `run_algorithm()` bằng `QThread`. UI có state riêng `loading` và `computing`; cấu hình bị khóa an toàn trong lúc render/search nhưng event loop và cửa sổ vẫn phản hồi. |
| Graph readiness | Map render theo batch và báo `graph_ready`; nút Run chỉ mở sau khi renderer sẵn sàng. Có token để hủy callback render cũ và báo lỗi render về Event Log. |
| Payload bản đồ | Hai directed edge của cùng đoạn đường được gom thành một physical layer nhưng cả hai direction vẫn trỏ tới layer đó khi highlight. Payload District 12 giảm từ khoảng 7,46 triệu xuống 2,68 triệu ký tự; còn 9.358 physical edge layer. |
| Leaflet lookup/render | Dùng JavaScript `Map` để tra node O(1), Leaflet Canvas renderer, render theo `requestAnimationFrame`, bỏ edge tooltip trong large-graph mode và cập nhật state theo delta O(1) thay vì quét mọi node. |
| Large-graph LOD | Ở zoom cấp quận vẫn vẽ đầy đủ mạng đường; marker node chỉ được materialize khi thuật toán chạm tới hoặc khi zoom từ mức 16. Viewport gần giới hạn 1.500 marker để tránh chồng lấp và lag. |
| Playback backpressure | Step kế tiếp chỉ được schedule sau callback JavaScript trước. Autoplay dùng profile Fast/Balanced/Detailed, adaptive batching và deadline khoảng 5/15/30 giây; selected cadence đã bao gồm thời gian render. Chế độ Instant vẫn tính/khôi phục Algorithm State đầy đủ nhưng bản đồ dựng trực tiếp final path. |
| Previous | Không replay hàng chục nghìn event trên Leaflet. Python tạo một bounded visual snapshot; State panel vẫn phục hồi đầy đủ frontier/explored/visited. |
| Algorithm State | State được phục hồi tăng dần từ delta. Preview chỉ xử lý tối đa 8 node; nội dung đầy đủ chỉ được dựng khi `View all` mở và được debounce 120 ms. |
| Node selectors | Start và Goal dùng chung một `QStandardItemModel` được tạo theo batch thay vì thêm 7.984 item hai lần bằng signal riêng lẻ. |

### 6.3. Kết quả benchmark và kiểm thử

| Kiểm tra | Kết quả |
| --- | --- |
| BFS cặp xa District 12 | 15.945 step, 7.972 visited, path 150 node, 0,154 giây, peak `tracemalloc` 4,6 MiB. |
| Qt Map ready District 12 | Khoảng 3,64 giây trên smoke-test desktop; UI vẫn xử lý event trong lúc `rendering`. |
| Instant playback 2.586 event | Khoảng 0,89 giây sau khi map ready. |
| Worst-case GUI search/playback | 16.061 event, 7.972 visited, path 150 node; khoảng 2,31 giây sau map ready. |
| Previous tại step 16.060 | Khoảng 1,81 giây; state chuyển `paused`, giữ đủ 7.972 explored node; Next trở lại `finished`. |
| Regression contract | `5 passed`: 4 test khóa đường đi/chi phí baseline của BFS/DFS/UCS/A* và 1 test Graph payload/direction. |
| Python compile / JavaScript syntax / diff check | Đạt. |

Full suite tiếp tục còn đúng 3 lỗi legacy đã ghi nhận ở mục 4: constructor `Node(x/y)` cũ và hai fixture không tồn tại (`mock_data.json`, `map_data.json`). Các lỗi này không phát sinh từ tối ưu dataset lớn.

### 6.4. So sánh trước và sau — cải thiện gì, vì sao phải cải thiện

| Khu vực | Trước cải thiện | Sau cải thiện | Vì sao bắt buộc phải cải thiện |
| --- | --- | --- | --- |
| Luồng chạy thuật toán | `run_algorithm()` chạy trực tiếp trên GUI thread. Từ lúc bấm Run đến khi có `SearchResult`, Qt không xử lý repaint/click bình thường. | Search chạy trong `SearchWorker/QThread`; GUI thread chỉ nhận kết quả qua signal. | Algorithm State được reset trước khi search nên ở bản cũ nó trống trong suốt lúc tính; Pause/Next chưa có step để dùng và cửa sổ trông như bị liệt. Worker thread giải quyết khả năng phản hồi, không thay logic search. |
| Trạng thái thực thi | Chỉ có `idle/ready/running/paused/finished`; giai đoạn parse/render/search bị biểu diễn bằng badge rời rạc. | Có thêm `loading` và `computing`; control được khóa/mở theo một state machine tập trung. | Tránh người dùng đổi dataset/start/goal khi graph đang render hoặc worker đang đọc graph; đồng thời phân biệt rõ “đang tính” với “đang playback”. |
| Dữ liệu mỗi SearchStep | Mỗi event giữ ba list đầy đủ: `frontier`, `explored`, `visited_order`; hai list sau thường trùng nhau. | Core search chỉ giữ event delta và metric cần thiết. UI tự phục hồi state; snapshot cũ vẫn được chấp nhận cho producer nhỏ/legacy. | Thiết kế cũ tăng gần O(V²) về số phần tử lưu khi traversal dài. District 12 đã cho thấy khoảng 127 triệu ID/lower-bound trên 1,2 GiB, có thể làm swap hoặc hết RAM trước khi playback bắt đầu. |
| Độ đúng thuật toán | Việc tạo snapshot xen giữa vòng lặp làm code thuật toán nặng và khó phân biệt logic search với logic trình diễn. | Queue/stack/heap, điều kiện visited/relax, `came_from`, reconstruction và cost được giữ nguyên; visualization metadata được thu gọn. | Tối ưu phải nằm ở telemetry/visualization, không được đổi node nào được lấy ra tiếp theo. Regression test khóa path và cost để ngăn tối ưu hiệu năng làm sai thuật toán. |
| A*/UCS frontier | Mỗi lần phát event lại sort toàn bộ heap để tạo list frontier hiển thị, dù sort này không phục vụ quyết định của thuật toán. | Event gửi `g/f` và `frontier_position=priority`; State panel tự sắp xếp phần hiển thị. Heap thật vẫn do `heapq` quản lý như cũ. | Loại công việc phụ khỏi vòng lặp nóng, nhất là graph lớn/nhiều relaxation, mà không can thiệp thứ tự pop của heap thật. |
| Tra node trong JavaScript | Mỗi edge gọi `graphData.nodes.find(...)` hai lần. | Tạo `nodeIndex = new Map(...)` và lookup O(1). | Với District 12, bản cũ có thể thực hiện khoảng 282 triệu lượt so sánh endpoint chỉ để bắt đầu vẽ edge. |
| Số layer edge | Cạnh hai chiều trong adjacency được gửi/vẽ thành hai polyline; một số key còn trỏ đè layer trong khi layer cũ vẫn nằm trên map. | Hai direction cùng trỏ tới một physical polyline; highlight vẫn nhận cả `u→v` và `v→u`. | Giảm payload, layer, hit-testing và redraw mà không làm mất hướng đi của graph thuật toán. District 12 còn 9.358 physical edge thay vì 35.273 directed layer. |
| Leaflet renderer | Hàng chục nghìn SVG/path-like layer và tooltip được tạo đồng loạt. | Canvas renderer; edge tooltip chỉ bật cho graph nhỏ; layer được tạo theo batch bằng `requestAnimationFrame`. | Render đồng loạt khiến Chromium renderer bận lâu, làm map đè/không repaint kịp và tạo cảm giác các panel Qt bên cạnh không hoạt động. Batch render nhường frame cho giao diện và cho phép hiển thị tiến độ. |
| Marker node lớn | Gần 8.000 marker được tạo ở zoom toàn quận, dù chúng chồng lên nhau và không đọc được. | Large-graph LOD: map nền vẫn có toàn bộ đường; node chỉ materialize khi được search chạm tới hoặc khi zoom ≥16, tối đa 1.500 node trong viewport gần. | Giảm layer và clutter. Đây là thay đổi ở mức hiển thị, không xóa node khỏi `Graph`, start/goal selector hay Algorithm State. |
| Cập nhật màu mỗi step | `applyStateSnapshot()` quét mọi node layer và set lại style ở mỗi event. | `expand/discover/update` chỉ thay đổi node/edge liên quan; renderer giữ `frontier/explored/current` bằng Set. | Với hàng nghìn node và hàng chục nghìn event, quét toàn graph mỗi step tạo khối lượng O(V×S), là nguyên nhân playback càng chạy càng chậm. |
| Giao tiếp Python ↔ WebEngine | QTimer tiếp tục gửi `runJavaScript()` dù lệnh trước chưa hoàn tất; Instant có thể làm đầy IPC queue. | Step sau chỉ schedule từ callback của JavaScript trước; Instant gửi final visualization một lần. | Backpressure giữ độ dài queue có giới hạn, nhờ đó Pause/Next và các widget Qt tiếp tục nhận event. |
| Algorithm State | Mỗi step gọi `setPlainText()` cho toàn bộ Frontier/Explored/Visited kể cả khi `View all` đang đóng. | Preview chỉ dựng 8 phần tử đầu và count; full text chỉ dựng khi mở, cập nhật được debounce 120 ms. | `QTextDocument` layout hàng nghìn dòng ba lần mỗi tick chạy trên GUI thread; thao tác này đủ làm click bị trễ dù thuật toán đã chuyển sang worker. |
| Instant | Vẫn lần lượt materialize mọi current/frontier/explored node trên bản đồ. | State logic xử lý đầy đủ mọi delta nhưng map chỉ dựng final path. | “Instant” có mục tiêu xem kết quả ngay, không cần trả chi phí render animation trung gian. Người dùng muốn xem diễn tiến dùng Fast/Balanced/Detailed. |
| Previous | Reset map rồi replay từ step 1 đến step hiện tại; càng gần cuối càng tốn thời gian. | Python dựng một visual snapshot giới hạn; State panel replay delta nhẹ để giữ danh sách đầy đủ. | Previous ở step ~16.000 trước đây có thể làm renderer đứng lâu. Sau sửa, map chỉ dựng tối đa phần trạng thái có ý nghĩa trực quan; danh sách chi tiết không bị cắt. |
| Start/Goal selector | Thêm gần 8.000 item vào hai combobox riêng, phát nhiều model signal. | Hai combobox dùng chung một `QStandardItemModel` tạo theo batch. | Giảm thời gian populate, bộ nhớ trùng lặp và số lần Qt cập nhật view khi load dataset. |

### 6.5. Ranh giới giữa tối ưu hiệu năng và tính đúng

Các thay đổi trên tuân theo ba nguyên tắc:

1. **Không thay đổi graph đầu vào của thuật toán.** Large-graph LOD và physical-edge dedup chỉ áp dụng cho layer hiển thị. `Graph.nodes`, adjacency list và edge cost giữ nguyên.
2. **Không thay đổi quyết định search.** BFS vẫn dùng FIFO queue; DFS vẫn dùng LIFO stack; UCS/A* vẫn pop từ `heapq` và giữ nguyên điều kiện cập nhật cost/parent.
3. **Không đánh đổi state chi tiết lấy tốc độ.** Map có thể giới hạn marker không đọc được ở mức zoom rộng, nhưng Algorithm State và `View all` vẫn giữ toàn bộ Frontier/Explored/Visited. Instant bỏ animation trung gian trên map nhưng vẫn xử lý đủ event để Result và State chính xác.

Vì vậy, kết quả cải thiện tập trung vào ba chỉ số độc lập với thuật toán: lượng telemetry được giữ trong RAM, số layer/thao tác vẽ và thời gian GUI thread bị chiếm dụng. Path, path cost, visited order và success/failure vẫn là kết quả do chính thuật toán tạo ra.

### 6.6. Hiệu chỉnh Autoplay Speed theo tốc độ thực tế

#### Vấn đề của thiết kế cũ

Các giá trị `250/500/1000 ms` trước đây được dùng như delay **sau** callback JavaScript. Chu kỳ quan sát thực tế là:

```text
thời gian một nhịp = thời gian WebEngine render
                    + thời gian Qt cập nhật State/Log
                    + delay đã chọn
```

Với 2.586 event, ngay cả `250 ms/event` cũng cần tối thiểu khoảng 10,8 phút nếu phát từng raw event; với 16.000 event có thể kéo dài hơn một giờ. Khi Canvas render chậm hơn interval, phần render trở thành chi phí chung lớn nên ba lựa chọn đều cho cảm giác rất chậm và gần giống nhau. Vì vậy nhãn “ms per step” không còn phù hợp cho graph lớn.

#### Thiết kế mới

| Profile | Cadence mục tiêu | Thời lượng mục tiêu khi search lớn | Hành vi |
| --- | --- | --- | --- |
| Instant | Không animation trung gian | Gần như ngay lập tức | Xử lý đủ delta cho State/Result, map chỉ dựng final path. |
| Fast | 20 rendered updates/s | Khoảng 5 giây | Gom nhiều raw event hơn trong mỗi rendered update. |
| Balanced | 10 rendered updates/s | Khoảng 15 giây | Mặc định; cân bằng quan sát và thời gian hoàn tất. |
| Detailed | 5 rendered updates/s | Khoảng 30 giây | Nhiều thời gian hơn để theo dõi từng nhóm event. |
| Step by step | Không schedule timer | Do người dùng quyết định | Chờ ở step 0; Previous/Next dịch chuyển đúng một raw event. Replay chỉ quay về step 0 và không tự chạy. |

Adaptive batching tính số raw event cần xử lý trong mỗi frame từ số step còn lại và deadline của profile. Sau mỗi callback, hệ thống đo tổng thời gian JavaScript + Qt State/Log đã dùng, trừ thời gian đó khỏi cadence và tăng batch nếu renderer đang chậm hơn mục tiêu. Pause không làm deadline trôi; khi Resume, deadline được dịch thêm đúng thời gian đã pause.

`Step by step` là một nhánh điều phối playback mới, không thay đổi adaptive batching hay cadence của bốn profile cũ. Khi profile này được chọn, playback controller giữ trạng thái manual/paused, không khởi động hoặc tái khởi động `QTimer`; nút Pause/Resume được vô hiệu hóa để không thể vô tình bật autoplay. Previous, Next, Replay và Reset tiếp tục dùng state machine và dữ liệu step hiện có, nên không tạo nhánh logic search riêng.

Điểm quan trọng về tính đúng:

* Batching chỉ gom nhiều visualization event vào một lần repaint; các delta vẫn được áp dụng theo đúng thứ tự.
* Algorithm State xử lý toàn bộ event trong batch trước khi hiển thị state cuối của frame.
* `Previous` và `Next` luôn đi đúng một raw event, không đi theo batch autoplay.
* Trong `Step by step`, kết quả thuật toán được tính như cũ nhưng visualization không tự áp dụng event nào trước thao tác Next đầu tiên.
* Kết quả path, cost, visited order và số step không thay đổi.

Smoke test District 12 với 2.586 event cho thấy các profile đã tách biệt rõ: lần đo trước adaptive deadline là Fast 9,46 giây, Balanced 16,31 giây và Detailed 29,65 giây; sau khi thêm deadline correction, Fast giảm còn khoảng 5,41 giây. Balanced/Detailed vốn đã gần mục tiêu và cùng dùng cơ chế correction nếu renderer bị trễ.

## 7. Bổ sung Graph View phục vụ mô phỏng thuật toán

### 7.1. Mục tiêu và nguyên tắc

Graph View thay đúng vùng Map View bằng một đồ thị node–edge, còn Sidebar, Algorithm State, Playback và Result Summary được giữ nguyên. Đây là **renderer thứ hai của cùng một kết quả search**, không phải một phiên bản thuật toán khác. Nhờ vậy, chuyển view trước, trong hoặc sau playback không thể làm thay đổi thứ tự duyệt, path hay cost.

### 7.2. Thông tin hiển thị

| Thành phần | Nội dung | Lý do |
| --- | --- | --- |
| Node | Tên node; `g`, `h`, `f` khi thuật toán đã phát metric; ID đầy đủ trong tooltip. | Tên giúp thuyết trình dễ đọc, còn bộ metric cho thấy vì sao UCS/A* chọn node tiếp theo. Không hiển thị metric chưa tồn tại để tránh tạo giá trị giả cho BFS/DFS. |
| Trạng thái node | Start, Goal, Frontier, Explored, Current và Final path dùng màu thống nhất với Map View. | Người dùng có thể đổi view mà không phải học lại legend hoặc cách đọc tiến trình. |
| Edge | Cost và distance trên edge đang quan trọng; tooltip bổ sung distance, travel time, road type/note; cạnh một chiều có mũi tên. | Cost là giá trị thuật toán dùng để relax; distance/time là thông tin giải thích. Chỉ hiện label quan trọng giúp graph lớn không biến thành một khối chữ. |
| Trạng thái edge | Inspect, Relaxed và Final path. | Cho thấy thuật toán đang xem cạnh nào, đã cập nhật đường đi nào và kết quả cuối cùng đi qua đâu. |

Graph View hỗ trợ kéo để pan, cuộn chuột để zoom, `Fit graph` để đưa toàn bộ graph vào khung và ba chế độ label `Auto / All / Off`.

### 7.3. Kiến trúc và hiệu năng

* `QStackedWidget` chứa MapWidget và GraphWidget trong cùng vùng visualization; việc kéo splitter với Sidebar/Algorithm State vẫn làm view đang mở co giãn đúng theo chiều tương ứng.
* MapWidget tiếp tục làm playback controller. Mỗi raw event chỉ được tính một lần rồi đồng bộ sang GraphWidget, nên không có nhánh logic search riêng cho Graph View.
* Renderer đang ẩn vẫn nhận state nhưng không repaint. Khi đổi view, renderer dựng lại trạng thái hiện tại; cách này tránh trả gấp đôi chi phí Canvas trong autoplay.
* Graph nhỏ (tối đa 180 node) dùng force-directed layout xác định để tách node và làm cấu trúc liên kết dễ đọc. Graph lớn dùng tọa độ địa lý chuẩn hóa để tránh chi phí layout O(V²).
* Canvas, tra cứu bằng `Map`/`Set`, edge physical dedup và label theo zoom giúp Graph View vẫn phản hồi với dataset hàng nghìn node. Tooltip edge được giới hạn ở graph vừa/nhỏ để tránh hit-testing quá nặng.

### 7.4. Kiểm chứng

| Kiểm tra | Kết quả |
| --- | --- |
| Payload cạnh hai chiều | Hai directed adjacency được vẽ thành một physical edge nhưng vẫn giữ đủ hai direction để highlight đúng. |
| Graph nhỏ | Node được tách bằng force layout; tên và `g/h/f` đọc được; current/frontier/explored/path đồng bộ với playback. |
| Chuyển Map ↔ Graph | Đạt trước, trong và sau playback; khi quay lại Map, snapshot trực quan hiện tại được phục hồi. |
| District 12 | 7.984 node, 9.358 physical edge; Fast hoàn tất khoảng 5,10 giây, Graph state giữ 1.359 metric và final path 21 node trong ca smoke test. |
| Contract/regression | `5 passed`; không thay path/cost của các thuật toán lõi. |

### 7.5. Cải thiện so với placeholder cũ

Trước đây nút Graph View chỉ báo `Coming soon`, nên người dùng buộc phải quan sát thuật toán trên tile bản đồ nhiều chi tiết. Sau cải thiện, cùng một run có thể xem theo hai ngữ cảnh: Map View để hiểu vị trí thực tế và Graph View để tập trung vào quan hệ node–edge, trọng số, frontier/explored và `g/h/f`. Việc tái sử dụng event contract còn giúp tránh sai lệch thường gặp khi mỗi view tự chạy một bản thuật toán riêng.

### 7.6. Sửa khóa Run khi khởi động trực tiếp ở Graph View

Lần tích hợp đầu tiên vẫn còn hai phụ thuộc ngầm vào Map View: trạng thái load chờ **cả hai renderer** sẵn sàng và playback chờ callback `resetVisualization()` của Map WebEngine. Khi người dùng chọn Graph View trước rồi load dataset, Map là trang ẩn nên Chromium có thể trì hoãn render/callback; kết quả là nút Run không mở hoặc playback đứng dù Graph đã hiển thị dữ liệu.

Bản sửa áp dụng readiness độc lập theo view đang hoạt động. Graph View mở Run ngay khi Graph renderer sẵn sàng; Map renderer còn lại tiếp tục chuẩn bị nền và không còn chặn control. Khi Map bị ẩn, playback controller bỏ qua callback vẽ Map nhưng vẫn phát từng event theo đúng thứ tự sang Graph View và Algorithm State. Khi quay lại Map, visual snapshot hiện tại được dựng lại như trước.

Smoke test theo đúng chuỗi `Graph View → Load 20 nodes → Instant Run` đạt `finished`, xử lý `36/36` event; Graph renderer giữ 17 explored node, 19 node metric và 18 edge state. Thay đổi này chỉ sửa điều phối renderer, không thay queue/stack/heap, path hoặc cost của thuật toán.
