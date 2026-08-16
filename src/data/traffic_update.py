# src/data/traffic_update.py

import random

from src.constants import CongestionLevel, RiskLevel


def generate_random_traffic_updates(
    json_path: str, affected_ratio: float = 0.2
) -> dict:
    """Tạo ngẫu nhiên dữ liệu traffic_updates từ file dataset JSON để test.

    :param json_path: Đường dẫn tới file JSON dataset (ví dụ:
    'data/map_data.json')
    :param affected_ratio: Tỷ lệ số cạnh bị ảnh hưởng (mặc định 0.2 = 20% tổng số
    đoạn đường)
    :return: dict traffic_updates dạng {"A01->A02": {"congestion": 0.8, "risk":
    0.35}}
    """
    import json
    import os

    if not os.path.exists(json_path):
        print(f"⚠️ [WARN] Không tìm thấy file {json_path}")
        return {}

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    edges = data.get("edges", [])
    if not edges:
        return {}

    # 1. Lấy ngẫu nhiên k cạnh từ danh sách edges
    num_affected = max(1, int(len(edges) * affected_ratio))
    selected_edges = random.sample(edges, num_affected)

    traffic_updates = {}

    for edge in selected_edges:
        u = str(edge.get("u", edge.get("from"))).strip()
        v = str(edge.get("v", edge.get("to"))).strip()
        edge_key = f"{u}->{v}"

        # Random congestion từ 0.3 đến 1.0 (làm tròn 2 chữ số thập phân)
        random_congestion = random.choice(list(CongestionLevel)).value

        # Random rủi ro
        random_risk = random.choice(list(RiskLevel)).value

        traffic_updates[edge_key] = {
            "congestion": random_congestion,
            "risk": random_risk,
        }

        # Nếu là đường 2 chiều, cập nhật luôn cho chiều ngược lại (v->u)
        if not edge.get("is_one_way", False):
            reverse_key = f"{v}->{u}"
            traffic_updates[reverse_key] = {
                "congestion": random_congestion,
                "risk": random_risk,
            }

    print(f"🎲 [TEST] Đã tạo ngẫu nhiên sự cố cho {len(traffic_updates)} đoạn đường!")
    return traffic_updates
