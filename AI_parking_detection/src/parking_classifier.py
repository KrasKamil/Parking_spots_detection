import cv2
import pickle
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
import os
import heapq

class ParkClassifier:
    """
    Generic parking space classifier using digital image processing.
    Responsibilities: Space classification, image processing, A* algorithm and result drawing.
    """

    def __init__(self, 
                 car_park_positions_path: str,
                 rect_width: int = 107,
                 rect_height: int = 48,
                 processing_params: dict = None):

        self.rect_height = rect_height
        self.rect_width = rect_width 
        self.car_park_positions_path = car_park_positions_path

        # Load positions
        self.car_park_positions, self.route_points = self._read_positions(car_park_positions_path)

        # Set default processing parameters
        self.processing_params = processing_params or {
            "gaussian_blur_kernel": [3, 3],
            "gaussian_blur_sigma": 1,
            "adaptive_threshold_max_value": 255,
            "adaptive_threshold_block_size": 25,
            "adaptive_threshold_c": 16,
            "median_blur_kernel": 5,
            "dilate_kernel_size": [3, 3],
            "dilate_iterations": 1
        }
        
        # --- OPTYMALIZACJA: Pre-kalkulacja grafu ---
        # Budujemy graf raz przy starcie, zamiast w każdej klatce.
        # MAX_CONNECTION_DIST: Maksymalna odległość (px) łączenia punktów.
        self.MAX_CONNECTION_DIST = 180 
        self.graph = self._build_spatial_graph(self.route_points)

        # Anti-flicker buffers
        self.stabilization_frames = 10 
        self.spot_stable_status_buffer = {}
        self.spot_candidate_status_buffer = {}

        for pos in self.car_park_positions:
            spot_id = str(pos.get('id', 'N/A'))
            self.spot_stable_status_buffer[spot_id] = 'Empty'
            self.spot_candidate_status_buffer[spot_id] = {'new_status': 'Empty', 'counter': 0}

    def _read_positions(self, car_park_positions_path: str) -> Tuple[List, List]:
        if not os.path.exists(car_park_positions_path):
            print(f"Positions file not found: {car_park_positions_path}")
            return [], []
        try:
            with open(car_park_positions_path, 'rb') as f:
                data = pickle.load(f)
                if isinstance(data, list):
                    return data, []
                else:
                    return data.get('car_park_positions', []), data.get('route_points', [])
        except Exception as e:
            print(f"Error reading positions file: {e}")
            return [], []

    def _build_spatial_graph(self, nodes: List[Tuple[int, int]]) -> Dict[Tuple[int, int], List[Tuple[int, int]]]:
        """
        Buduje graf przestrzenny (listę sąsiedztwa) raz przy inicjalizacji.
        Łączy węzły, które są bliżej niż MAX_CONNECTION_DIST.
        """
        graph = {node: [] for node in nodes}
        if not nodes:
            return graph
            
        node_list = list(nodes)
        # O(N^2) jest akceptowalne, bo punktów trasy jest zazwyczaj < 100
        for i in range(len(node_list)):
            for j in range(i + 1, len(node_list)):
                node_a = node_list[i]
                node_b = node_list[j]
                
                dist = np.linalg.norm(np.array(node_a) - np.array(node_b))
                
                if dist < self.MAX_CONNECTION_DIST:
                    graph[node_a].append(node_b)
                    graph[node_b].append(node_a)
        return graph

    def implement_process(self, image: np.ndarray) -> np.ndarray:
        params = self.processing_params
        kernel_size = np.ones(tuple(params["dilate_kernel_size"]), np.uint8)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, tuple(params["gaussian_blur_kernel"]), params["gaussian_blur_sigma"])
        thresholded = cv2.adaptiveThreshold(
            blur, params["adaptive_threshold_max_value"],
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV,
            params["adaptive_threshold_block_size"], params["adaptive_threshold_c"]
        )
        blur = cv2.medianBlur(thresholded, params["median_blur_kernel"])
        dilate = cv2.dilate(blur, kernel_size, iterations=params["dilate_iterations"])
        return dilate

    def classify(self, image: np.ndarray, processed_image: np.ndarray, threshold: int = 900) -> Tuple[np.ndarray, dict]:
        empty_spaces = 0
        occupied_spaces = 0
        space_details = []

        # Sortowanie dla stabilności
        sorted_positions = self.car_park_positions.copy()
        def sort_key(pos):
            raw_id = pos.get('id', '99999') 
            try: return int(raw_id)
            except: return 99999 
        sorted_positions.sort(key=sort_key)

        for pos in sorted_positions:
            spot_id_raw = pos.get('id')
            spot_id = str(spot_id_raw) if spot_id_raw is not None else '?'

            if isinstance(pos, dict):
                points = pos['points']
                is_irregular = pos.get('irregular', False)
                x_coords = [p[0] for p in points]
                y_coords = [p[1] for p in points]
                x_min, x_max = min(x_coords), max(x_coords)
                y_min, y_max = min(y_coords), max(y_coords)
                
                if is_irregular:
                    mask = np.zeros(processed_image.shape, dtype=np.uint8)
                    pts = np.array(points, dtype=np.int32)
                    cv2.fillPoly(mask, [pts], 255)
                    crop = cv2.bitwise_and(processed_image[y_min:y_max, x_min:x_max], 
                                        mask[y_min:y_max, x_min:x_max])
                else:
                    crop = processed_image[y_min:y_max, x_min:x_max]
                count = cv2.countNonZero(crop)
            else:
                # Backward compatibility
                x, y = pos
                points = [(x, y), (x + self.rect_width, y), 
                          (x + self.rect_width, y + self.rect_height), (x, y + self.rect_height)]
                is_irregular = False
                crop = processed_image[y:y + self.rect_height, x:x + self.rect_width]
                count = cv2.countNonZero(crop)

            # --- STABILIZATION LOGIC ---
            raw_is_empty = count < threshold
            raw_status = "Empty" if raw_is_empty else "Occupied"
            
            stable_status = self.spot_stable_status_buffer.get(spot_id, raw_status)
            candidate = self.spot_candidate_status_buffer.get(spot_id)

            if candidate is None:
                is_empty = raw_is_empty
                status = raw_status
            else:
                if raw_status == stable_status:
                    candidate['counter'] = 0
                elif raw_status == candidate['new_status']:
                    candidate['counter'] += 1
                else:
                    candidate['new_status'] = raw_status
                    candidate['counter'] = 1

                if candidate['counter'] >= self.stabilization_frames:
                    stable_status = candidate['new_status']
                    self.spot_stable_status_buffer[spot_id] = stable_status
                    candidate['counter'] = 0

                is_empty = (stable_status == "Empty")
                status = stable_status
            # ---------------------------

            if is_empty:
                empty_spaces += 1
                color = (0, 255, 0)
                thickness = 5
            else:
                occupied_spaces += 1
                color = (0, 0, 255)
                thickness = 2

            space_details.append({
                'id': spot_id, 'points': points, 'status': status,
                'pixel_count': count, 'is_empty': is_empty, 'irregular': is_irregular
            })

            pts = np.array(points, dtype=np.int32)
            cv2.polylines(image, [pts], True, color, thickness)
            center_x = sum(p[0] for p in points) // len(points)
            center_y = sum(p[1] for p in points) // len(points)
            cv2.putText(image, spot_id, (center_x - 10, center_y), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        self._draw_info_panel(image, empty_spaces, len(self.car_park_positions))
        
        # A* Pathfinding
        first_empty_space = next((s for s in space_details if s['is_empty']), None)
        occupied_spaces_details = [s for s in space_details if not s['is_empty']]
        
        if first_empty_space and self.route_points:
            self._draw_pathfinding_route(image, first_empty_space, occupied_spaces_details)
            
        stats = {
            'empty_spaces': empty_spaces,
            'occupied_spaces': occupied_spaces,
            'total_spaces': len(self.car_park_positions),
            'occupancy_rate': (occupied_spaces / len(self.car_park_positions) * 100) if self.car_park_positions else 0,
            'space_details': space_details
        }
        return image, stats

    def _draw_info_panel(self, image, empty_spaces, total_spaces):
        cv2.rectangle(image, (45, 30), (300, 85), (180, 0, 180), -1)
        ratio_text = f'Free: {empty_spaces}/{total_spaces}'
        occupancy_rate = ((total_spaces - empty_spaces) / total_spaces * 100) if total_spaces > 0 else 0
        rate_text = f'Occupancy: {occupancy_rate:.1f}%'
        cv2.putText(image, ratio_text, (50, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(image, rate_text, (50, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    def _draw_arrowhead(self, img, p1, p2, color):
        v = np.array(p2) - np.array(p1)
        if np.linalg.norm(v) == 0: return
        angle = np.arctan2(v[1], v[0])
        arrow_len = 20
        a1 = angle - np.pi/6
        a2 = angle + np.pi/6
        pt1 = (int(p2[0] - arrow_len * np.cos(a1)), int(p2[1] - arrow_len * np.sin(a1)))
        pt2 = (int(p2[0] - arrow_len * np.cos(a2)), int(p2[1] - arrow_len * np.sin(a2)))
        cv2.line(img, p2, pt1, color, 3)
        cv2.line(img, p2, pt2, color, 3)

    def _draw_pathfinding_route(self, image: np.ndarray, target_space: dict, occupied_spaces: List[dict]):
        if not self.route_points: return
        start_node = self.route_points[0]
        points = target_space['points']
        target_center = (sum(p[0] for p in points) // len(points), sum(p[1] for p in points) // len(points))
        
        end_node_before_spot = self._get_nearest_route_node(target_center)
        if end_node_before_spot is None: return

        found_path = self._find_path_a_star(start_node, end_node_before_spot, occupied_spaces)
        
        if found_path:
            final_route = found_path + [target_center] 
            color = (255, 255, 0)
            for i in range(1, len(final_route)):
                p1 = final_route[i-1]
                p2 = final_route[i]
                cv2.line(image, p1, p2, color, 4)
                self._draw_arrowhead(image, p1, p2, color) 
            cv2.circle(image, target_center, 20, color, -1)
            cv2.putText(image, "DOJAZD", (target_center[0] - 30, target_center[1] + 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    def _get_nearest_route_node(self, target_point: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        if not self.route_points: return None
        distances = [np.linalg.norm(np.array(p) - np.array(target_point)) for p in self.route_points]
        min_index = np.argmin(distances)
        return self.route_points[min_index]

    def _find_path_a_star(self, start_node: Tuple[int, int], end_node: Tuple[int, int], occupied_space_details: List[dict]) -> Optional[List[Tuple[int, int]]]:
        if start_node not in self.route_points or end_node not in self.route_points: 
            return None

        # Używamy pre-kalkulowanego grafu zamiast budować go w pętli
        #Optymalizacja wydajności
        graph = self.graph 

        def heuristic(node):
            return np.linalg.norm(np.array(node) - np.array(end_node))

        queue = [(0 + heuristic(start_node), 0, start_node, [start_node])] 
        visited_g = {start_node: 0}

        while queue:
            f, g, current_node, path = heapq.heappop(queue)

            if current_node == end_node: return path

            # Pobieramy sąsiadów z grafu
            neighbors = graph.get(current_node, [])
            
            for neighbor in neighbors:
                # Koszt ruchu
                dist = np.linalg.norm(np.array(current_node) - np.array(neighbor))
                new_g = g + dist

                # Sprawdź kolizję z zajętymi miejscami
                if self._segment_intersects_occupied_space(current_node, neighbor, occupied_space_details):
                    continue

                if neighbor not in visited_g or new_g < visited_g[neighbor]:
                    visited_g[neighbor] = new_g
                    new_f = new_g + heuristic(neighbor)
                    heapq.heappush(queue, (new_f, new_g, neighbor, path + [neighbor]))
        
        return None

    def _segment_intersects_occupied_space(self, p1: Tuple[int, int], p2: Tuple[int, int], occupied_spaces: List[dict]) -> bool:
        """
        Zoptymalizowana metoda sprawdzania kolizji.
        1. Sprawdza AABB (Bounding Box).
        2. Używa dynamicznego kroku (step size) zamiast sztywnej liczby punktów.
        """
        # Pre-kalkulacja Bounding Box dla odcinka (p1, p2) z marginesem
        line_min_x = min(p1[0], p2[0])
        line_max_x = max(p1[0], p2[0])
        line_min_y = min(p1[1], p2[1])
        line_max_y = max(p1[1], p2[1])

        vec = np.array(p2) - np.array(p1)
        length = np.linalg.norm(vec)
        if length == 0: return False
        
        # Dynamiczny krok: sprawdzamy co ok. 15 pikseli
        step_size = 15.0 
        num_steps = int(max(2, length / step_size)) # Przynajmniej 2 kroki (początek i koniec)

        for occupied_space in occupied_spaces:
            points = occupied_space['points']
            
            # Szybka eliminacja: Sprawdzenie Bounding Box Miejsca
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            spot_min_x, spot_max_x = min(xs), max(xs)
            spot_min_y, spot_max_y = min(ys), max(ys)

            # Jeśli prostokąty się nie przecinają, pomiń dokładne sprawdzanie
            if (line_max_x < spot_min_x or line_min_x > spot_max_x or 
                line_max_y < spot_min_y or line_min_y > spot_max_y):
                continue

            # Dokładne sprawdzanie
            pts = np.array(points, dtype=np.int32)
            
            for i in range(num_steps + 1):
                t = i / num_steps
                check_x = int(p1[0] * (1-t) + p2[0] * t)
                check_y = int(p1[1] * (1-t) + p2[1] * t)

                # pointPolygonTest zwraca >= 0 jeśli punkt jest wewnątrz lub na krawędzi
                if cv2.pointPolygonTest(pts, (check_x, check_y), False) >= 0:
                    return True
        return False