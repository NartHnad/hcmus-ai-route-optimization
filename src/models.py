# src/models.py


class Node:
    """
    Represents a physical traffic intersection, landmark, school, hospital, bus station, warehouse, or district.
    It stores coordinates (x, y) which are essential for GUI rendering
    and computing Heuristic distances (e.g., Euclidean) for informed search algorithms like A* and Greedy BFS.
    """

    def __init__(self, node_id: str, name: str, x: float, y: float):
        self.id = node_id
        self.name = name

        # X-coordinate, Y-coordinate for GUI visualization and Heuristic calculation
        self.x = x
        self.y = y

    # Magic Method: define how a Node object is represented as a string
    def __repr__(self):
        return f"Node({self.id}, {self.name})"


class Edge:
    """
    Represents a one-way urban street segment connecting two intersections.
    Instead of using static physical distance, it wraps a dynamic cost function
    that aggregates real-time traffic constraints (congestion, flooding) modulated by user-controlled GUI weights.
    """

    def __init__(
        self,
        from_node: str,
        to_node: str,
        distance: float,
        travel_time: float,
        road_type: str,
        direction: str = "one-way",
        congestion: int = 1,
        flooding: int = 1,
    ):
        self.from_node = from_node
        self.to_node = to_node

        # Compulsory Attributes
        self.distance = distance  # Raw physical distance (meters/kilometers)
        self.travel_time = travel_time  # Estimated travel time
        self.road_type = road_type  # Type of road
        self.direction = direction  # Traffice direction: 'one-way' or 'two-way'
        self.congestion = congestion  # Traffic traffic level scaled from 1 to 5

        # Optional Risk Factors
        self.flooding = flooding  # Rain flooding level scaled from 1 to 5

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
        This directly implements the formula from section 4.3 Cost Function:
        Cost = alpha * Distance + beta * Time + gamma * Congestion + delta * Risk

        Where:
        - Distance: raw physical length of the road segment.
        - Time: estimated travel time based on speed and traffic condition.
        - Congestion: traffic level (scale 1 to 5).
        - Risk: penalty for flooding, construction, narrow roads, etc. (scale 1 to 5).
        """

        if mode == "shortest":
            return self.distance

        # Return cost_value
        return (
            (alpha * self.distance)
            + (beta * self.travel_time)
            + (gamma * self.congestion)
            + (delta * self.flooding)
        )


class Graph:
    def __init__(self):
        # Map Node ID to Node Object
        self.nodes = {}
        # Directed Adjacency List mapping Node ID to its outgoing Edge objects
        self.adjacency_list = {}

    def add_node(self, node: Node):
        """
        Register a new intersection into the graph network and initialize its adjacency list.
        """

        self.nodes[node.id] = node
        if node.id not in self.adjacency_list:
            self.adjacency_list[node.id] = []

    def add_edge(self, edge: Edge):
        """
        Establish connectivity between nodes.
        Automatically handles one-way constraints and creates a reverse edge if the road type direction is specified as 'two-way'.
        """
        # Add the forward edge
        if edge.from_node in self.adjacency_list:
            self.adjacency_list[edge.from_node].append(edge)

        # If it is a two-way street, create the reverse path
        if edge.direction == "two-way":
            # create a reversed edge
            reverse_edge = Edge(
                from_node=edge.to_node,
                to_node=edge.from_node,
                distance=edge.distance,
                travel_time=edge.travel_time,
                road_type=edge.road_type,
                direction=edge.direction,
                congestion=edge.congestion,
                flooding=edge.flooding,
            )

            # Add the reversed edge
            if reverse_edge.from_node not in self.adjacency_list:
                self.adjacency_list[reverse_edge.from_node] = []
            self.adjacency_list[edge.from_node].append(reverse_edge)
