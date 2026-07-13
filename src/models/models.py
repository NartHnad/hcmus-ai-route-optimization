# src/models.py


class Node:
    """
    Represents a map node such as an intersection, landmark, school, hospital,
    bus station, warehouse, or district.

    The canonical coordinate names are lat/lon to match mock_data.json.
    x/y are kept as aliases for GUI rendering and heuristic code that already
    uses the older contract.
    """

    def __init__(
        self,
        node_id: str,
        name: str,
        x: float = None,
        y: float = None,
        lat: float = None,
        lon: float = None,
        node_type: str = "intersection",
    ):
        self.id = node_id
        self.name = name

        self.lat = float(lat if lat is not None else x)
        self.lon = float(lon if lon is not None else y)
        self.type = node_type

        # Backward-compatible aliases for earlier GUI/heuristic code.
        self.x = self.lat
        self.y = self.lon

    def __repr__(self):
        return f"Node({self.id}, {self.name})"


class Edge:
    """
    Represents a directed urban street segment connecting two nodes.

    The canonical risk field follows mock_data.json. flooding and direction are
    retained as compatibility aliases for older code and tests.
    """

    def __init__(
        self,
        from_node: str,
        to_node: str,
        distance: float,
        travel_time: float,
        road_type: str,
        direction: str = None,
        is_oneway: bool = None,
        congestion: int = 1,
        risk: int = None,
        flooding: int = None,
        note: str = "",
    ):
        self.from_node = from_node
        self.to_node = to_node

        self.distance = float(distance)
        self.travel_time = float(travel_time)
        self.road_type = road_type
        self.congestion = int(congestion)
        self.risk = int(risk if risk is not None else (flooding if flooding is not None else 1))
        self.note = note

        if is_oneway is None:
            normalized_direction = (direction or "one-way").strip().lower()
            self.is_oneway = normalized_direction != "two-way"
        else:
            self.is_oneway = bool(is_oneway)

        self.direction = "one-way" if self.is_oneway else "two-way"

        # Backward-compatible alias for older cost/GUI code.
        self.flooding = self.risk

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
            is_oneway=self.is_oneway,
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

    def add_edge(self, edge: Edge, auto_reverse: bool = False):
        """
        Add a directed edge to the graph.

        mock_data.json already stores reverse directions explicitly, so the default
        behavior is to add only the edge passed in. Set auto_reverse=True for legacy
        callers that still expect a two-way edge to create a reverse edge.
        """
        if edge.from_node not in self.adjacency_list:
            self.adjacency_list[edge.from_node] = []
        self.adjacency_list[edge.from_node].append(edge)

        if auto_reverse and edge.direction == "two-way":
            reverse_edge = edge.reversed()
            if reverse_edge.from_node not in self.adjacency_list:
                self.adjacency_list[reverse_edge.from_node] = []
            self.adjacency_list[reverse_edge.from_node].append(reverse_edge)

    def get_neighbors(self, node_id: str):
        """Return all outgoing edges from a node."""
        return self.adjacency_list.get(node_id, [])

    def get_edge(self, from_node: str, to_node: str):
        """Return the first edge from from_node to to_node, or None."""
        for edge in self.adjacency_list.get(from_node, []):
            if edge.to_node == to_node:
                return edge
        return None
