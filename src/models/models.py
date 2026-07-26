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
        self.node_type = node_type # Giao lộ, Bệnh viện, ...

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
        congestion: int = None,
        risk: int = None,
        note: str = "",
    ):
        self.from_node = from_node
        self.to_node = to_node

        # Compulsory Attributes
        self.distance = float(distance)  # Raw physical distance (meters/kilometers)
        self.travel_time = float(travel_time)  # Estimated travel time
        self.road_type = road_type  
        self.is_one_way = is_one_way # Traffic direction: 'one-way' or 'two-way'

        # # Traffic traffic level scaled from a to b
        self.congestion = int(congestion)

        #  penalty for flooding, construction, difficult intersections, narrow roads, or unsafe areas
        self.risk = int(risk)

        self.note = note

        self.road_type = road_type

    def calculate_cost(
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
        visited_order=None,
        success: bool = True,
        message: str = "",
    ):
        self.path = path or []
        self.steps = steps or []
        self.total_cost = float(total_cost)
        self.visited_order = visited_order or []
        self.success = success
        self.message = message

    def __repr__(self):
        return (
            f"SearchResult(success={self.success}, "
            f"path={self.path}, total_cost={self.total_cost})"
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
