# XII. Limitations

The current system has the following limitations. The statements in this section are based on the source code and datasets currently stored in the repository.

### 1. Dataset

The project uses a **hybrid, simplified real-world dataset collection**. Road topology, node coordinates, road length, road type, and one-way information are obtained from OpenStreetMap through OSMnx. The project then supplements these records with estimated or synthetic traffic attributes.

The GUI currently discovers 18 top-level JSON files in the `data/` directory. These files contain 23,370 node records and 48,788 stored edge records in total. These totals describe the repository inventory, not one combined graph: every JSON file is loaded and searched independently, and the collection contains overlapping District 5 subsets. Individual datasets range from 50 to 4,075 nodes and from 83 to 8,596 stored edges.

The dataset-generation script estimates travel time using a fixed speed of 40 km/h:

\[
T(e)=\frac{D(e)}{40}\times 60
\]

where distance is measured in kilometers and time in minutes. It assigns synthetic placeholder values to congestion and risk. In the current top-level JSON files, both attributes are set to 1 for every stored edge. A random traffic-update helper exists in the codebase, but it is not called by the dataset loader. The GUI instead allows users to modify travel time, congestion, and risk manually for the current session.

Consequently, the road geometry is based on real map data, but travel time, congestion, and risk should not be interpreted as observed traffic measurements. The files also do not record an OSM extraction timestamp, data version, or provenance metadata for each generated graph.

### 2. Static Traffic During Search

Traffic conditions remain fixed during each algorithm execution. The interface prevents edge editing while a search is running, so travel time, congestion, and risk cannot change midway through a route computation.

Users may manually edit an edge before starting another search. The system recalculates the edge's normalized travel time and composite cost after such an edit, but this is a session-level simulation rather than an automatic traffic feed.

### 3. No Real-Time Traffic API

The system does not retrieve live congestion, incidents, road closures, weather hazards, or travel-time estimates from an external traffic service. OSMnx is used by an offline utility to obtain road-network data, while the Leaflet map uses OpenStreetMap tiles only as a visual background. Neither mechanism provides live traffic conditions to the routing algorithms.

### 4. No Live GPS or Automatic Rerouting

Users select start and delivery locations from predefined graph nodes. The application does not read the shipper's current GPS coordinates, map-match a moving vehicle to the road network, track route progress, or automatically rerun the search after a deviation.

This also means that locations outside the loaded graph cannot be used directly. A real coordinate would first need to be matched or connected to an appropriate graph node.

### 5. Fixed Cost Function

For graphs loaded through `build_graph`, the system uses the following composite edge cost:

\[
C(e)
=0.25D_{norm}(e)
+0.45T_{norm}(e)
+0.20C(e)
+0.10R(e)
\]

where:

\[
D_{norm}(e)=\frac{D(e)}{D_{max}},
\qquad
T_{norm}(e)=\frac{T(e)}{T_{max}}
\]

The total route cost is:

\[
C(P)=\sum_{e\in P}C(e)
\]

The weights are constants in `src/constants.py` and cannot currently be changed from the GUI. They therefore do not adapt to rush hour, weather, vehicle type, delivery urgency, or user preferences. Furthermore, because the current JSON inventory assigns congestion and risk a value of 1 on every edge, these two terms initially add the same penalty of 0.30 to every traversed edge. Until users edit the values, they do not distinguish traffic or safety conditions between roads and may indirectly favor routes containing fewer edges.

There is also a reporting inconsistency in the current algorithm implementations: DFS reports the sum of raw edge distances as `total_cost`, while cost-based algorithms such as UCS, A*, Beam Search, and Bidirectional UCS use `Edge.calculate_cost()`. Cross-algorithm evaluation must therefore recompute every returned path with the canonical cost function rather than compare the algorithms' raw `total_cost` fields directly.

### 6. Algorithm Limitations

The single-route registry currently exposes BFS, DFS, UCS, A*, weighted Bidirectional Search, Beam Search, and Genetic Algorithm. The multi-location registry exposes Genetic Algorithm, Simulated Annealing, and Nearest Neighbor + 2-Opt, together with a mock algorithm intended for UI support.

Each production algorithm has different constraints:

- BFS optimizes hop count rather than weighted traffic cost.
- DFS depends on adjacency order and guarantees neither the shortest nor the least-cost route.
- UCS is optimal for the implemented objective when all edge costs are non-negative, but it can expand many nodes.
- A* depends on the correctness and scale of its geographic heuristic.
- Bidirectional UCS requires non-negative edge costs and additional forward/backward state; its improvement depends on graph structure.
- Beam Search deliberately prunes candidates, so it is neither complete nor optimal.
- Genetic Algorithm and Simulated Annealing are stochastic approximations whose results and runtimes depend on their parameter settings and random choices.

For multi-location routing, **Nearest Neighbor + 2-Opt provides an approximate solution**. It first precomputes directed shortest routes between selected locations, constructs an initial order greedily, and then applies 2-Opt improvements. It does not guarantee the globally optimal visit order. The pairwise shortest-route cache and the number of 2-Opt candidates both grow as more destinations are added, so runtime and memory use increase with the delivery count.

### 7. Experimental-Evaluation Limitations

The repository contains a benchmark runner, but no generated `benchmarks/results` artifacts are currently committed. The runner also imports NN + 2-Opt from `src.algorithms.multi_location`, which does not exist in the current source tree; the production implementation is located in `src.algorithms.nearest_neighbor_2opt`. Bidirectional UCS is not included in that runner's algorithm registry either. Therefore, the current benchmark runner cannot support a complete, reproducible comparison of all algorithms without correction and a fresh run.

One separate validation case is documented in [report_bidirectional_search.md](report_bidirectional_search.md). On `map_phu_nhuan_district.json`, UCS and Bidirectional UCS returned the same route cost, `20.764285083068`. UCS expanded 600 nodes, while Bidirectional UCS expanded 378 nodes, a reduction of 222 nodes or 37%. Their reported 30-run average times, 1.243 ms and 1.263 ms respectively, were nearly equal and are machine-dependent. This isolated case should not be generalized into a ranking of all algorithms or datasets.

---

# XIII. Future Work

### 1. Broader and Reproducible Map Data

The project already obtains road networks from OpenStreetMap through OSMnx. Future work should improve this pipeline by recording the extraction date, query boundary, OSM/OSMnx version, preprocessing configuration, and checksums alongside every generated dataset.

Coverage could be expanded beyond individual districts and the two District 5 samples. The importer should also be reviewed for duplicate directed edges, turn restrictions, disconnected components, and consistent handling of OSM one-way roads. External routing platforms such as Google Maps Platform or openrouteservice could be evaluated for comparison or enrichment, subject to their licensing, attribution, cost, and API restrictions.

### 2. Dynamic Traffic

A future version could connect to an authorized live or periodically refreshed traffic source and update:

- congestion levels;
- estimated travel times;
- incidents and road closures;
- construction, flooding, and other risk factors.

The routing model would then need timestamped edge states and a defined update policy. Long-running or active routes should be invalidated and recomputed when a material network change occurs.

### 3. Live GPS and Automatic Rerouting

GPS support could detect the shipper's actual position, map-match it to the road network, track route progress, and trigger rerouting after a deviation or traffic change. This requires handling noisy coordinates, off-road positions, location permissions, update frequency, and privacy controls.

### 4. Multi-Vehicle Routing

The current multi-location mode plans a route for one shipper. It could be extended to a Vehicle Routing Problem that assigns deliveries across multiple vehicles while considering vehicle capacity, delivery time windows, depot returns, driver constraints, and route balancing.

### 5. Adaptive Cost Function

The fixed coefficients could become a configurable routing profile. Users could choose or learn weights based on:

- rush hour and time of day;
- weather and flooding;
- vehicle type;
- delivery priority or deadline;
- safety preferences;
- fuel, toll, or emissions objectives.

Any adaptive design should preserve compatible units and normalization, validate weight ranges, and show the active objective clearly in the GUI and exported results.

### 6. Advanced Optimization

Genetic Algorithm and Simulated Annealing are already implemented in the current project, so future work should focus on improving and comparing them rather than listing them as unimplemented features. Possible extensions include:

- Ant Colony Optimization;
- Adaptive Large Neighborhood Search;
- exact or bounded optimization for small multi-location instances;
- time-dependent A* or incremental replanning algorithms;
- reinforcement learning after a suitable training environment and evaluation protocol are available.

All new methods should be evaluated against exact solutions on small instances and against deterministic baselines on larger instances.

### 7. Reproducible Benchmarking

The benchmark runner should be aligned with the production registries, including the current NN + 2-Opt module and Bidirectional UCS. A complete evaluation should then be generated and committed with:

- fixed datasets and route scenarios;
- random seeds for stochastic algorithms;
- warm-up and repeat counts;
- runtime, peak memory, expanded nodes, success rate, distance, and canonical route cost;
- machine, Python, dependency, and Git revision metadata;
- raw results as well as aggregate tables and charts.

---

# XIV. Conclusion

## 1. Conclusion

This project developed a desktop delivery-route optimization and visualization application for Ho Chi Minh City. It models each loaded road network as a directed graph and evaluates routes using normalized distance, estimated travel time, congestion, and risk rather than physical distance alone.

The implemented single-route methods are:

- Breadth-First Search;
- Depth-First Search;
- Uniform Cost Search, which follows Dijkstra's cost-ordering principle;
- A* Search;
- weighted Bidirectional Search, implemented as bidirectional UCS/Dijkstra;
- Beam Search;
- Genetic Algorithm.

The implemented production multi-location methods are:

- Nearest Neighbor + 2-Opt;
- Simulated Annealing;
- Genetic Algorithm.

The application provides Map View and Graph View, algorithm-state metrics, event logs, automatic and manual step-by-step playback, result summaries, multi-location endpoint ordering, and in-session edge editing. These features make the relationship between frontier operations, explored nodes, optimization iterations, and the final route visible to the user.

The documented Bidirectional UCS case study found the same weighted route cost as UCS while expanding 37% fewer nodes, although its measured runtime was approximately the same in that case. No complete benchmark output is currently available for a defensible overall ranking of BFS, DFS, UCS, A*, Beam Search, Genetic Algorithm, Simulated Annealing, and NN + 2-Opt. The final comparative conclusion should therefore be added only after the benchmark runner is corrected and executed.

Overall, the project demonstrates how classical graph search, heuristic search, and approximate optimization can be integrated into an urban delivery-routing interface. Its main remaining gap is not the number of algorithms, but the realism and reproducibility of the input and evaluation pipeline. Live traffic, GPS-based rerouting, configurable objectives, reproducible benchmarks, and multi-vehicle routing would make the system substantially closer to a deployable logistics tool.

---

# 2. References

The following IEEE-style references are limited to data sources and technologies directly evidenced in the repository. Course materials or other algorithm references should be added only if the group actually used them.

[1] OpenStreetMap contributors, “Copyright and License,” *OpenStreetMap*. [Online]. Available: https://www.openstreetmap.org/copyright. [Accessed: Aug. 17, 2026].

[2] G. Boeing, “Modeling and Analyzing Urban Networks and Amenities with OSMnx,” *Geographical Analysis*, vol. 57, no. 4, pp. 567–577, 2025, doi: 10.1111/gean.70009.

[3] OSMnx contributors, “OSMnx User Reference,” *OSMnx Documentation*. [Online]. Available: https://osmnx.readthedocs.io/en/stable/user-reference.html. [Accessed: Aug. 17, 2026].

[4] Riverbank Computing Ltd., “PyQt: Python Bindings for the Qt Application Framework.” [Online]. Available: https://riverbankcomputing.com/software/pyqt/. [Accessed: Aug. 17, 2026].

[5] V. Agafonkin and Leaflet contributors, “Leaflet API Reference, Version 1.9.4.” [Online]. Available: https://leafletjs.com/reference. [Accessed: Aug. 17, 2026].

> **To be completed by the group:** Add the course slides, textbook, papers, or websites actually consulted for BFS, DFS, UCS/Dijkstra, A*, Beam Search, Haversine distance, Genetic Algorithm, Simulated Annealing, and TSP/2-Opt. Do not add suggested sources that were not used.

---

# 3. Appendix

### Appendix A — Dataset Inventory

The table reports records stored in each selectable JSON file. `Graph.add_edge()` creates an additional reverse edge for records marked as two-way, so the number of directed edges shown by the GUI can be larger than the stored-edge count.

| Dataset | Nodes | Stored Edges |
|---|---:|---:|
| `district5_subgraph_50nodes.json` | 50 | 97 |
| `map_binh_tan_district.json` | 4,075 | 8,596 |
| `map_binh_thanh_district.json` | 1,788 | 3,702 |
| `map_district_1.json` | 700 | 1,381 |
| `map_district_10.json` | 783 | 1,753 |
| `map_district_12.json` | 1,829 | 2,733 |
| `map_district_3.json` | 455 | 928 |
| `map_district_4.json` | 315 | 631 |
| `map_district_5.json` | 436 | 893 |
| `map_district_5_50_nodes.json` | 50 | 83 |
| `map_district_6.json` | 791 | 1,763 |
| `map_district_7.json` | 1,929 | 4,500 |
| `map_district_8.json` | 1,268 | 2,879 |
| `map_go_vap_district.json` | 3,706 | 7,736 |
| `map_nha_be_district.json` | 791 | 1,208 |
| `map_phu_nhuan_district.json` | 666 | 1,396 |
| `map_tan_binh_district.json` | 1,491 | 3,254 |
| `map_tan_phu_district.json` | 2,247 | 5,255 |
| **Repository inventory total** | **23,370** | **48,788** |

The inventory total is not a deduplicated city-wide network because files may overlap and are loaded separately.

For the final submission, this appendix may additionally include selected node and edge records with:

- node ID, name, latitude, longitude, and type;
- source and destination node IDs;
- distance and estimated time;
- road type and direction;
- congestion and risk;
- normalized values and computed edge cost.

### Appendix B — Experimental Results

#### B.1 Existing Bidirectional UCS Case Study

| Metric | UCS | Bidirectional UCS |
|---|---:|---:|
| Dataset | `map_phu_nhuan_district.json` | `map_phu_nhuan_district.json` |
| Route found | Yes | Yes |
| Total weighted cost | 20.764285083068 | 20.764285083068 |
| Nodes in route | 67 | 67 |
| Expanded nodes | 600 | 378 |
| Reference mean runtime over 30 runs | 1.243 ms | 1.263 ms |

#### B.2 Unified Benchmark

> **Pending:** Add the generated benchmark tables and charts after correcting the benchmark registry and running the benchmark under a recorded environment. No consolidated benchmark output is currently present in the repository.

### Appendix C — GUI Screenshots

Add screenshots from the final tested build showing:

- dataset selection and the main interface;
- Map View and Graph View;
- step-by-step search visualization;
- Algorithm State and Event Log;
- the final route and result summary;
- multi-location ordering and route playback;
- manual edge editing, if discussed in the report.

### Appendix D — Additional Technical Details

Recommended source-backed materials include:

- algorithm pseudocode and workflow diagrams;
- the composite cost calculation;
- the normalized Haversine heuristic;
- `SearchResult` and `SearchStep` event contracts;
- benchmark scenario construction and validation rules;
- multi-location metric-closure and 2-Opt details.

---

# 4. AI Usage Declaration

### AI Tools Used

- **[To be completed by the group]**

### Purpose

AI tools were used for the following purposes, subject to confirmation by the group:

- code explanation and debugging;
- refactoring suggestions;
- algorithm explanation;
- report drafting and grammar improvement;
- **[add or remove items to match actual usage]**.

### Declaration

> We declare that AI tools were used as supporting tools during the development and documentation of this project. All AI-generated content and code suggestions were reviewed, tested, and verified by the group before being included in the final submission.

**AI tools:** [To be completed by the group]  
**Main purposes:** [To be completed by the group]  
**Sections/tasks assisted by AI:** [To be completed by the group]
