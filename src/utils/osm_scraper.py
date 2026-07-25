import osmnx as ox
import json
import time

def scrape_osm_to_json(place_query, output_file):
    """
    Tải bản đồ từ OpenStreetMap dựa vào tên khu vực và xuất ra file JSON 
    phù hợp với định dạng của Route Optimization Visualizer.
    
    Args:
        place_query (str): Tên khu vực (VD: 'District 1, Ho Chi Minh City, Vietnam')
        output_file (str): Đường dẫn file JSON đầu ra
    """
    print(f"Đang tải bản đồ cho khu vực: {place_query}...")
    print("Quá trình này có thể mất vài phút tùy vào độ lớn của khu vực...")
    
    start_time = time.time()
    
    try:
        # Tải đồ thị đường dành cho xe ô tô/xe máy (drive)
        # Hệ thống OSMnx sẽ tự động tìm kiếm ranh giới hành chính của nơi này trên bản đồ
        # và cào TOÀN BỘ các con đường bên trong ranh giới đó.
        G = ox.graph_from_place(place_query, network_type='drive')
    except Exception as e:
        print(f"Lỗi khi tải dữ liệu từ OSM: {e}")
        return

    print(f"Tải thành công! Mất {round(time.time() - start_time, 1)} giây.")
    print(f"Đồ thị có {len(G.nodes)} nút (giao lộ) và {len(G.edges)} cạnh (đoạn đường).")
    
    data = {"nodes": [], "edges": []}
    
    # Bóc tách dữ liệu Nodes
    print("Đang xử lý dữ liệu Nodes...")
    for node_id, node_data in G.nodes(data=True):
        data["nodes"].append({
            "id": str(node_id),
            "name": f"Node {node_id}", # Thường node giao lộ trên OSM không có tên
            "lat": float(node_data['y']),
            "lon": float(node_data['x']),
            "node_type": "intersection"
        })
        
    # Bóc tách dữ liệu Edges
    print("Đang xử lý dữ liệu Edges...")
    for u, v, key, edge_data in G.edges(keys=True, data=True):
        # Tên đường
        name = edge_data.get('name', 'Unknown Road')
        if isinstance(name, list): 
            name = name[0] # Có lúc 1 đoạn đường có 2 tên, ta lấy tên đầu tiên
            
        # Khoảng cách (OSM trả về theo mét, ta chia 1000 để ra km)
        length_km = edge_data.get('length', 0) / 1000.0
        
        # Đường 1 chiều
        oneway = edge_data.get('oneway', False)
        
        # Random hoặc mặc định các thông số kẹt xe/rủi ro vì OSM không có
        # Bạn có thể phát triển thêm bằng cách map với API giao thông thật
        congestion = 1
        risk = 1

        data["edges"].append({
            "from": str(u),
            "to": str(v),
            "distance": round(length_km, 3),
            "travel_time": round(length_km / 40.0 * 60, 2), # Giả sử đi 40km/h
            "road_type": str(edge_data.get('highway', 'unknown')),
            "is_one_way": bool(oneway),
            "congestion": congestion,
            "risk": risk,
            "note": str(name)
        })
        
    # Lưu file JSON
    print(f"Đang lưu dữ liệu ra file {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        
    print("Hoàn tất! 🎉")

if __name__ == "__main__":
    # Danh sách các quận/huyện đã được kiểm chứng là tải thành công từ OpenStreetMap
    districts = [
        "District 1",
        "District 3",
        "District 4",
        "District 5",
        "District 6",
        "District 7",
        "District 8",
        "District 10",
        "District 12",
        "Phu Nhuan District",
        "Binh Thanh District",
        "Go Vap District",
        "Tan Binh District",
        "Tan Phu District",
        "Binh Tan District",
        "Nha Be District"
    ]
    
    for district in districts:
        query = f"{district}, Ho Chi Minh City, Vietnam"
        
        # Tạo tên file chuẩn hóa (VD: "District 1" -> "district_1")
        safe_name = district.lower().replace(" ", "_")
        output_path = f"data/map_{safe_name}.json"
        
        try:
            scrape_osm_to_json(query, output_path)
            print("-" * 50)
        except Exception as e:
            print(f"Bỏ qua {district} do lỗi: {e}")
            print("-" * 50)
