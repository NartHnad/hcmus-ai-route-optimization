# src/models.py


class Node:
    """
    Represents a physical traffic intersection, landmark, school, hospital, bus station, warehouse, or district.
    It stores coordinates (lat, lon) 
    and computing Heuristic distances (e.g., Euclidean) for informed search algorithms like A* and Greedy BFS.
    """

    def __init__(
        self,
        node_id: str,
        name: str,
        lat: float = None,
        lon: float = None,
        node_type: str = "intersection",
    ):
        self.id = node_id
        self.name = name

        self.lat = lat  # latitude: Vi do
        self.lon = lon  # longitude: Kinh do
        self.node_type = node_type

    # Magic Method: define how a Node object is represented as a string
    def __repr__(self):
        return f"Node({self.id}, {self.name})"


class Edge:
    """
    Represents a directed urban street segment connecting two intersection.
    """

    def __init__(
        self,
        from_node: str,
        to_node: str,
        distance: float,
        travel_time: float,
        road_type: str = None,
        is_one_way: bool = False,
        congestion: int = 0,
        risk: int = 0,
        note: str = "",
    ):
        self.from_node = from_node
        self.to_node = to_node

        # Compulsory Attributes
        self.distance = float(distance)  # Raw physical distance (meters/kilometers)
        self.travel_time = float(travel_time)  # Estimated travel time
        self.road_type = road_type  
        self.is_one_way = is_one_way # Traffic direction: 'one-way' or 'two-way'

        # Traffic traffic level scaled from a to b
        self.congestion = int(congestion)

        # Penalty for flooding, construction, difficult intersections, narrow roads, or unsafe areas
        self.risk = int(risk)

        self.note = note

    def calculate_cost( #need to be updated
        self,
        alpha: float = 1.0,
        beta: float = 1.0,
        gamma: float = 1.0,
        delta: float = 1.0,
        mode: str = "optimal",
    ):
        """
        Dynamically evaluate the edge's weight based on different routing strategies.

        Cost = alpha * Distance + beta * Time + gamma * Congestion + delta * Risk
        """

        if mode == "shortest":
            return self.distance

        return (
            (alpha * self.distance)
            + (beta * self.travel_time)
            + (gamma * self.congestion)
            + (delta * self.risk)
        )

    def reversed(self):
        """Return a reversed copy of this edge for legacy two-way graph building."""
        return Edge(
            from_node=self.to_node,
            to_node=self.from_node,
            distance=self.distance,
            travel_time=self.travel_time,
            road_type=self.road_type,
            congestion=self.congestion,
            risk=self.risk,
            note=self.note,
        )

    def __repr__(self):
        return f"Edge({self.from_node} -> {self.to_node}, cost={self.calculate_cost()})"

from enum import Enum

class StepType(Enum):
    EXPAND = "expand"           # Lấy node ra khỏi hàng đợi để xét (Visited)
    DISCOVER = "discover"       # Tìm thấy node mới lần đầu (Frontier Add)
    UPDATE = "update"           # Tìm thấy đường đi rẻ hơn đến node đã biết (Relaxation)

    FINISH = "finish"


class SearchStep:
    """
    Represents a single search event emitted in chronological order.

    Algorithm → GUI contract:
    - EXPAND: Node removed from frontier for expansion.
    - DISCOVER: First time a node is found and added to frontier.
    - UPDATE: Better path to an existing node is found.
    - FINISH: Search terminates (success or failure).

    Rules:
    - Emit exactly one SearchStep when the event occurs.
    - Do not batch or reconstruct events afterward.
    - Unused fields must be None.
    """

    def __init__(
        self,
        step_type: StepType,
        node_id: str = None,
        edge_from: str = None,
        edge_to: str = None,
        metrics: dict = None,  # g, h, f of heuristic function
    ):
        self.step_type = step_type
        self.node_id = node_id
        self.edge_from = edge_from
        self.edge_to = edge_to
        self.metrics = metrics or {}

    def to_dict(self):
        """
        Serialize to the plain-dict schema the GUI / JavaScript side consumes.
        Fields that are None are omitted to keep the JSON payload small.
        """
        data = {"type": self.step_type.value}

        if self.node_id is not None:
            data["node"] = self.node_id

        if self.edge_from is not None:
            data["from"] = self.edge_from

        if self.edge_to is not None:
            data["to"] = self.edge_to

        if self.metrics:
            data["metrics"] = dict(self.metrics)

        return data

    def __repr__(self):
        parts = [f"type={self.step_type.value}"]
        if self.node_id is not None:
            parts.append(f"node={self.node_id}")
        if self.edge_from is not None or self.edge_to is not None:
            parts.append(f"edge={self.edge_from}->{self.edge_to}")
        if self.metrics:
            parts.append(f"metrics={self.metrics}")
        return f"SearchStep({', '.join(parts)})"

class SearchResult:
    """
    Standard return object for search algorithms.

    GUI code can consume steps directly, while algorithm code can also expose
    path, total cost, visited order, success state, and a human-readable message.
    """

    def __init__(
        self,
        path=None,
        steps=None,
        total_cost: float = 0.0,
        success: bool = False,
        message: str = "",
        visited_order=None,
    ):
        self.path = path or []
        self.steps = steps or []
        self.total_cost = float(total_cost)
        self.success = success
        self.visited_order = visited_order or []

    def to_dict(self):
        """
        Serialize the whole result into one JSON-ready dict.
        """
        return {
            "success": self.success,
            "path": list(self.path),
            "total_cost": self.total_cost,
            "message": getattr(self, "message", ""),
            "visited_order": list(self.visited_order),
            # Accept both SearchStep objects and plain dicts (mock steps),
            # so mixed lists still serialize cleanly.
            "steps": [
                step.to_dict() if hasattr(step, "to_dict") else step
                for step in self.steps
            ],
        }

    def __repr__(self):
        return (
            f"SearchResult(success={self.success}, "
            f"path={self.path}, total_cost={self.total_cost}, "
        )


class Graph:
    def __init__(self):
        # Map Node ID to Node Object
        self.nodes = {}
        # Directed Adjacency List mapping Node ID to its outgoing Edge objects
        self.adjacency_list = {}

    def add_node(self, node: Node):
        """Register a node into the graph network and initialize its adjacency list."""
        self.nodes[node.id] = node
        if node.id not in self.adjacency_list:
            self.adjacency_list[node.id] = []

    def add_edge(self, edge: Edge):
        """
        Establish connectivity between nodes.
        Automatically handles one-way constraints and creates a reverse edge if the road type direction is specified as 'two-way'.
        """
        # Add the forward edge
        if edge.from_node not in self.adjacency_list:
            self.adjacency_list[edge.from_node] = []

        self.adjacency_list[edge.from_node].append(edge)

        # If it is a two-way street, create the reverse path
        if not edge.is_one_way:
            reverse_edge = edge.reversed()

            if reverse_edge.from_node not in self.adjacency_list:
                self.adjacency_list[reverse_edge.from_node] = []
            
            self.adjacency_list[reverse_edge.from_node].append(reverse_edge)


    def get_node(self, node_id):
        return self.nodes.get(node_id)
    
    def get_neighbors(self, node_id: str):
        """Return all outgoing edges from a node."""
        return self.adjacency_list.get(node_id, [])

    def get_edge(self, from_node: str, to_node: str):
        """Return the first edge from from_node to to_node, or None."""
        for edge in self.adjacency_list.get(from_node, []):
            if edge.to_node == to_node:
                return edge
        return None
    
    def clear(self):
        self.nodes.clear()
        self.adjacency_list.clear()
