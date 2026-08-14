# src/constants.py

from enum import Enum


class StepType(Enum):
    EXPAND = "expand"  # Lấy node ra khỏi hàng đợi để xét (Visited)
    DISCOVER = "discover"  # Tìm thấy node mới lần đầu (Frontier Add)
    UPDATE = "update"  # Tìm thấy đường đi rẻ hơn đến node đã biết (Relaxation)

    FINISH = "finish"


class RoadType(Enum):
    """Định nghĩa tất cả các loại đường hợp lệ trong hệ thống"""

    HIGHWAY = "highway"  # Đường cao tốc
    TRUNK = "trunk"  # Trục đường lớn / Quốc lộ
    PRIMARY = "primary"  # Đường chính đô thị
    SECONDARY = "secondary"  # Đường phụ / Đường quận
    RESIDENTIAL = "residential"  # Đường nội bộ / KDC
    ALLEY = "alley"  # Đường hẹp / Hẻm


class CongestionLevel(Enum):
    CLEAR = 0.0  # Thông thoáng (Xe chạy đúng/vượt tốc độ tối đa)
    LIGHT = 0.25  # Mật độ đông nhẹ (Di chuyển bình thường)
    MODERATE = 0.5  # Kẹt xe trung bình (Chậm, nhích từng chút)
    HEAVY = 0.75  # Kẹt xe nặng (Ún tắc kéo dài)
    GRIDLOCK = 1.0  # Tắc nghẽn hoàn toàn (Đứng yên)


class RiskLevel(Enum):
    """Định nghĩa phân ngưỡng Risk theo yêu cầu thiết kế (0.0 - 1.0)."""

    NONE = 0.0  # Không có rủi ro
    NARROW = 0.15  # < 0.2: Đường hẹp / Ngõ
    CONSTRUCTION = 0.35  # 0.2 - 0.5: Đường đang thi công
    FLOODED = 0.7  # > 0.5: Triều cường / Ngập nước
    HAZARD = 1.0  # Điểm đen tai nạn / Hạn chế tối đa


# Bảng tra cứu tốc độ trung bình theo loại đường (Đơn vị: km/h)
DEFAULT_SPEED_MAP = {
    RoadType.HIGHWAY: 80.0,
    RoadType.TRUNK: 50.0,
    RoadType.PRIMARY: 40.0,
    RoadType.SECONDARY: 30.0,
    RoadType.RESIDENTIAL: 20.0,
    RoadType.ALLEY: 15.0,
}

# Default composite edge-cost weights, shared by Edge.calculate_cost()
# and the A* heuristic. Cost = alpha*d_norm + beta*t_norm + gamma*congestion + delta*risk.
# The heuristic MUST use the same alpha as calculate_cost() to stay admissible.
DEFAULT_ALPHA = 0.25
DEFAULT_BETA = 0.45
DEFAULT_GAMMA = 0.20
DEFAULT_DELTA = 0.10
