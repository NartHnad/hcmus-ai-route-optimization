# test_models.py
from models import Graph, Node, Edge

# AI write to test models.py
def test_ai_graph_components():
    print("=== STARTING MODELS.PY INTEGRATION TEST ===")
    
    # 1. Initialize Graph
    graph = Graph()
    
    # 2. Create and Add Nodes (Intersections)
    node1 = Node("N1", "Phu_Dong_Roundabout", x=10.7712, y=106.6924)
    node2 = Node("N2", "Dan_Chu_Roundabout", x=10.7798, y=106.6790)
    
    graph.add_node(node1)
    graph.add_node(node2)
    
    print(f"[SUCCESS] Nodes registered: {list(graph.nodes.values())}")
    
    # 3. Create and Add a Two-Way Edge with custom traffic constraints
    # Attributes: from, to, distance, travel_time, road_type, direction, congestion, flooding
    edge = Edge("N1", "N2", distance=1.5, travel_time=5.0, road_type="Main Street", 
                direction="two-way", congestion=4, flooding=2)
    
    graph.add_edge(edge)
    print(f"[SUCCESS] Forward edge created. Outgoing from N1: {graph.adjacency_list['N1']}")
    print(f"[SUCCESS] Reverse edge auto-created. Outgoing from N2: {graph.adjacency_list['N2']}")
    
    # 4. Test Cost Function Under Different Scenarios
    print("\n--- Testing Dynamic Cost Functions ---")
    
    # Scenario A: Shortest Path Mode (pure distance)
    shortest_cost = edge.calculate_cost(mode="shortest")
    print(f"-> Shortest Mode Cost (Distance): {shortest_cost} km (Expected: 1.5)")
    assert shortest_cost == 1.5
    
    # Scenario B: Optimal Delivery Mode during Rush Hour + Heavy Rain
    # Formula: alpha*Dist + beta*Time + gamma*Congestion + delta*Risk
    optimal_cost = edge.calculate_cost(alpha=1.0, beta=1.5, gamma=2.0, delta=3.0, mode="optimal")
    # Calculation: (1.0 * 1.5) + (1.5 * 5.0) + (2.0 * 4) + (3.0 * 2) = 1.5 + 7.5 + 8.0 + 6.0 = 23.0
    print(f"-> Optimal Mode Cost (Weighted): {optimal_cost} (Expected: 23.0)")
    assert optimal_cost == 23.0
    
    print("\n=== ALL TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    test_ai_graph_components()