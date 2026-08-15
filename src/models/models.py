# src/models.py

from src.constants import (
    DEFAULT_ALPHA,
    DEFAULT_BETA,
    DEFAULT_DELTA,
    DEFAULT_GAMMA,
    StepType,
)
from dataclasses import dataclass

from src.constants import StepType


@dataclass(frozen=True)
class RouteRequest:
    """An immutable snapshot of the locations selected for a route search."""

    start_node: str
    delivery_nodes: tuple[str, ...]
    respect_goal_order: bool = False
    return_to_start: bool = False

    @property
    def route_mode(self) -> str:
        """Return the algorithm registry mode required by this request."""
        return "multi" if len(self.delivery_nodes) >= 2 else "single"


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
        lat: float,
        lon: float,
        node_type: str = "intersection",
    ):
        self.id = node_id
        self.name = name

        self.lat = lat  # latitude: Vi do
        self.lon = lon  # longitude: Kinh do
        self.node_type = node_type  # Giao lộ, Bệnh viện, ...

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
        road_type: str,
        is_one_way: bool = False,
        congestion: float = 0.0,
        risk: float = 0.0,
        note: str = "",
    ):
        self.from_node = from_node
        self.to_node = to_node

        # Compulsory Attributes
        self.distance = float(distance)  # Raw physical distance (kilometers)
        self.travel_time = float(travel_time)  # Estimated travel time (minutes)
        self.road_type = road_type
        self.is_one_way = is_one_way  # Traffic direction: 'one-way' or 'two-way'

        # Normalized Values 0.0 -> 1.0
        self.norm_distance = 0.0
        self.norm_travel_time = 0.0

        # Traffic traffic level scaled from a to b
        self.congestion = float(congestion)  # 0.0 -> 1.0
        # Penalty for flooding, construction, difficult intersections, narrow roads, or unsafe areas
        self.risk = float(risk)  # 0.0 -> 1.0
        self.note = note

        # Cached Cost Value
        self.weight = 0.0

    def calculate_cost(
        self,
        alpha: float = DEFAULT_ALPHA,
        beta: float = DEFAULT_BETA,
        gamma: float = DEFAULT_GAMMA,
        delta: float = DEFAULT_DELTA,
    ) -> float:
        """
        Dynamically evaluate the edge's weight based on different routing strategies.

        Cost = alpha * Distance + beta * Time + gamma * Congestion + delta * Risk
        Cost = 0.25 * Distance_norm + 0.45 * Time_norm + 0.2 * Congestion + 0.1 * Risk

        Mode:
        Shortest Distance
        Fastest Route
        Safest Route
        Optimal Route
        """
        # Lightweight/test graphs may be assembled directly without the
        # factory's normalization pass. Preserve the legacy raw-cost fallback
        # for those graphs while loaded datasets continue to use the weighted
        # normalized formula below.
        if self.norm_distance == 0.0 and self.norm_travel_time == 0.0:
            return self.distance + self.travel_time

        return (
            (alpha * self.norm_distance)
            + (beta * self.norm_travel_time)
            + (gamma * self.congestion)
            + (delta * self.risk)
        )

    def reversed(self):
        """Return a reversed copy of this edge for legacy two-way graph building."""
        if self.is_one_way:
            raise ValueError(
                f"Cannot reverse one-way edge: " f"{self.from_node} -> {self.to_node}"
            )

        rev_edge = Edge(
            from_node=self.to_node,
            to_node=self.from_node,
            distance=self.distance,
            travel_time=self.travel_time,
            road_type=self.road_type,
            is_one_way=False,
            congestion=self.congestion,
            risk=self.risk,
            note=self.note,
        )

        rev_edge.norm_distance = self.norm_distance
        rev_edge.norm_travel_time = self.norm_travel_time
        rev_edge.weight = self.weight

        return rev_edge

    def __repr__(self):
        return f"Edge({self.from_node} -> {self.to_node}, cost={self.calculate_cost()})"


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

    ``frontier``/``explored``/``visited_order`` remain supported for small,
    legacy producers. Core graph-search algorithms emit compact delta events
    instead: DISCOVER/UPDATE adds ``node`` to the frontier and EXPAND removes
    it and appends it to the explored/visited order. ``frontier_position``
    preserves stack ordering for DFS without copying the entire stack.
    """

    def __init__(
        self,
        step_type: StepType,
        node_id: str = None,
        edge_from: str = None,
        edge_to: str = None,
        metrics: dict = None,  # g, h, f of heuristic function
        frontier=None,
        explored=None,
        visited_order=None,
        frontier_position: str = None,
    ):
        self.step_type = step_type
        self.node_id = node_id
        self.edge_from = edge_from
        self.edge_to = edge_to
        self.metrics = metrics or {}
        # Optional state snapshots keep playback deterministic and allow the UI
        # to move both forwards and backwards without re-running an algorithm.
        self.frontier = None if frontier is None else list(frontier)
        self.explored = None if explored is None else list(explored)
        self.visited_order = None if visited_order is None else list(visited_order)
        self.frontier_position = frontier_position

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

        if self.frontier is not None:
            data["frontier"] = list(self.frontier)

        if self.explored is not None:
            data["explored"] = list(self.explored)

        if self.visited_order is not None:
            data["visited_order"] = list(self.visited_order)

        if self.frontier_position is not None:
            data["frontier_position"] = self.frontier_position

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
        runtime_ms: float = 0.0,
        total_distance=None,
        estimated_time=None,
        goal_visit_order=None,
    ):
        self.path = path or []
        self.steps = steps or []
        self.total_cost = float(total_cost)
        self.success = success
        self.message = message
        self.visited_order = visited_order or []
        self.runtime_ms = float(runtime_ms)
        self.total_distance = None if total_distance is None else float(total_distance)
        self.estimated_time = None if estimated_time is None else float(estimated_time)
        # Ordered delivery destinations for multi-location searches. This is
        # intentionally separate from ``visited_order``, which records graph
        # nodes expanded by the search algorithm.
        self.goal_visit_order = list(goal_visit_order or [])

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
            "runtime_ms": self.runtime_ms,
            "total_distance": self.total_distance,
            "estimated_time": self.estimated_time,
            "goal_visit_order": list(self.goal_visit_order),
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
            f"path={self.path}, "
            f"total_cost={self.total_cost})"
        )


class Graph:
    def __init__(self):
        # Map Node ID to Node Object
        self.nodes = {}
        # Directed Adjacency List mapping Node ID to its outgoing Edge objects
        self.adjacency_list = {}

        # Max distance
        self.max_distance = 1.0
        # Max time
        self.max_time = 1.0

    def add_node(self, node: Node):
        """Register a node into the graph network and initialize its adjacency list."""
        self.nodes[node.id] = node
        if node.id not in self.adjacency_list:
            self.adjacency_list[node.id] = []

    def add_edge(self, edge: Edge):
        """
        Add an edge to the graph.
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
