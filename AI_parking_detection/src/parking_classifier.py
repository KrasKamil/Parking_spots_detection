import cv2
import pickle
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
import os
import heapq

# === ParkClassifier Class (Responsible for Classification and Analysis) ===
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
        
        # Dimensions are now read-only (used in backward compatibility/calculations)
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
        
        # -----------------------------------------------------------------
        # === NOWA LOGIKA: BUFOR STABILIZACYJNY (ANTI-FLICKER) ===
        # -----------------------------------------------------------------
        
        # Definiuje, przez ile kolejnych klatek stan musi się zgadzać,
        # zanim zostanie on oficjalnie zmieniony (np. 5 klatek)
        self.stabilization_frames = 5 
        
        # Przechowuje "stabilny" (potwierdzony) stan dla każdego miejsca
        # Format: {'id_miejsca': 'Empty' | 'Occupied'}
        self.spot_stable_status_buffer = {}
        
        # Przechowuje "kandydacki" stan i licznik klatek
        # Format: {'id_miejsca': {'new_status': 'Empty', 'counter': 2}}
        self.spot_candidate_status_buffer = {}

        # Inicjalizujemy bufory
        for pos in self.car_park_positions:
            spot_id = str(pos.get('id', 'N/A'))
            # Na starcie zakładamy, że wszystkie miejsca są puste (można zmienić na 'Occupied' jeśli wolisz)
            self.spot_stable_status_buffer[spot_id] = 'Empty'
            self.spot_candidate_status_buffer[spot_id] = {'new_status': 'Empty', 'counter': 0}
        
        # -----------------------------------------------------------------
    
    def _read_positions(self, car_park_positions_path: str) -> Tuple[List, List]:
        """Read parking positions and route points from pickle file"""
        if not os.path.exists(car_park_positions_path):
            print(f"Positions file not found: {car_park_positions_path}")
            return [], []
        try:
            with open(car_park_positions_path, 'rb') as f:
                data = pickle.load(f)

                if isinstance(data, list):
                    # Old format (positions list only) - backward compatibility
                    print("Warning: Loaded old position format (list). Using default dimensions.")
                    return data, []
                else:
                    # New format (dictionary)
                    return data.get('car_park_positions', []), data.get('route_points', [])

        except Exception as e:
            print(f"Error reading positions file: {e}")
            return [], []
    
    def implement_process(self, image: np.ndarray) -> np.ndarray:
        """Process image using configurable parameters"""
        params = self.processing_params
        
        # Create kernel
        kernel_size = np.ones(tuple(params["dilate_kernel_size"]), np.uint8)
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Gaussian blur
        blur = cv2.GaussianBlur(gray, 
                               tuple(params["gaussian_blur_kernel"]), 
                               params["gaussian_blur_sigma"])
        
        # Adaptive threshold
        thresholded = cv2.adaptiveThreshold(
            blur,
            params["adaptive_threshold_max_value"],
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            params["adaptive_threshold_block_size"],
            params["adaptive_threshold_c"]
        )
        
        # Median blur
        blur = cv2.medianBlur(thresholded, params["median_blur_kernel"])
        
        # Dilate
        dilate = cv2.dilate(blur, kernel_size, iterations=params["dilate_iterations"])
        
        return dilate
        
    def classify(self, 
            image: np.ndarray, 
            processed_image: np.ndarray,
            threshold: int = 900) -> Tuple[np.ndarray, dict]:
            """
            Classify parking spaces. Spaces are processed in order of their stable, 
            numerical ID to ensure correct route prioritization.
            (Implementacja jest identyczna jak w utils.py, z zachowaniem logiki sortowania)
            """
            
            empty_spaces = 0
            occupied_spaces = 0
            space_details = []

            # --- SORTING BY NUMERIC ID ---
            sorted_positions = self.car_park_positions.copy()
            def sort_key(pos):
                raw_id = pos.get('id', '99999') 
                try:
                    return int(raw_id)
                except:
                    return 99999 

            sorted_positions.sort(key=sort_key)
            # --- END OF SORTING ---

            for pos in sorted_positions: 
                
                spot_id_raw = pos.get('id')
                spot_id = str(spot_id_raw) if spot_id_raw is not None else '?'
                
                # Using new format (dict)
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
                    # Old format (for backward compatibility)
                    x, y = pos
                    points = [(x, y), 
                            (x + self.rect_width, y), 
                            (x + self.rect_width, y + self.rect_height), 
                            (x, y + self.rect_height)]
                    is_irregular = False
                    
                    col_start, col_stop = x, x + self.rect_width
                    row_start, row_stop = y, y + self.rect_height
                    crop = processed_image[row_start:row_stop, col_start:col_stop]
                    count = cv2.countNonZero(crop)
                
                # -----------------------------------------------------------------
                # === NOWA LOGIKA: BUFOR STABILIZACYJNY (Anti-Flicker) ===
                # -----------------------------------------------------------------
                
                # 1. Uzyskaj "surową" klasyfikację z tej klatki
                raw_is_empty = count < threshold
                raw_status = "Empty" if raw_is_empty else "Occupied"
                
                # 2. Pobierz dane z buforów
                stable_status = self.spot_stable_status_buffer.get(spot_id, raw_status)
                candidate = self.spot_candidate_status_buffer.get(spot_id)
                
                # 3. Zastosuj logikę bufora
                if candidate is None:
                    # (Fallback, gdyby miejsce nie zostało zainicjowane)
                    is_empty = raw_is_empty
                    status = raw_status
                else:
                    if raw_status == stable_status:
                        # Stan surowy zgadza się ze stabilnym. Zresetuj kandydata.
                        candidate['counter'] = 0
                    elif raw_status == candidate['new_status']:
                        # Stan surowy zgadza się z kandydatem. Zwiększ licznik.
                        candidate['counter'] += 1
                    else:
                        # Stan surowy jest nowy. Ustaw nowego kandydata.
                        candidate['new_status'] = raw_status
                        candidate['counter'] = 1
                        
                    # 4. Sprawdź, czy kandydat osiągnął próg stabilności
                    if candidate['counter'] >= self.stabilization_frames:
                        # Tak! Awansuj kandydata na status stabilny
                        stable_status = candidate['new_status']
                        self.spot_stable_status_buffer[spot_id] = stable_status
                        candidate['counter'] = 0
                
                    # 5. ZAWSZE UŻYWAJ STABILNEGO STANU DO RYSOWANIA I LOGIKI
                    is_empty = (stable_status == "Empty")
                    status = stable_status

                # -----------------------------------------------------------------
                # === KONIEC LOGIKI BUFORA ===
                # -----------------------------------------------------------------
                
                # Classify space (używa teraz 'is_empty' i 'status' z bufora)
                if is_empty:
                    empty_spaces += 1
                    color = (0, 255, 0)  # Green for empty
                    thickness = 5
                    # status = "Empty" (już ustawione)
                else:
                    occupied_spaces += 1
                    color = (0, 0, 255)  # Red for occupied
                    thickness = 2
                    # status = "Occupied" (już ustawione)
                
                # Store space details (używa stabilnego statusu)
                space_details.append({
                    'id': spot_id, 
                    'points': points,
                    'status': status,
                    'pixel_count': count, # Zapisujemy surową liczbę pikseli dla debugowania
                    'is_empty': is_empty,
                    'irregular': is_irregular
                })
                
                # Draw polygon
                pts = np.array(points, dtype=np.int32)
                cv2.polylines(image, [pts], True, color, thickness)
                
                # Draw space number
                center_x = sum(p[0] for p in points) // len(points)
                center_y = sum(p[1] for p in points) // len(points)
                
                cv2.putText(image, spot_id, (center_x - 10, center_y), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
            # Draw info panel
            self._draw_info_panel(image, empty_spaces, len(self.car_park_positions))
            
            # Pathfinding
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
            
    # Drawing Functions (display analysis results)
    def _draw_info_panel(self, image: np.ndarray, empty_spaces: int, total_spaces: int):
        """Draw information panel on image"""
        cv2.rectangle(image, (45, 30), (300, 85), (180, 0, 180), -1)
        ratio_text = f'Free: {empty_spaces}/{total_spaces}'
        occupancy_rate = ((total_spaces - empty_spaces) / total_spaces * 100) if total_spaces > 0 else 0
        rate_text = f'Occupancy: {occupancy_rate:.1f}%'
        cv2.putText(image, ratio_text, (50, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(image, rate_text, (50, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
    def _draw_arrowhead(self, img, p1, p2, color):
        """Draw a simple arrowhead on the line segment from p1 to p2"""
        v = np.array(p2) - np.array(p1)
        if np.linalg.norm(v) == 0: return
        v_norm = v / np.linalg.norm(v)
        angle = np.arctan2(v[1], v[0])
        arrow_len = 20
        a1 = angle - np.pi/6
        a2 = angle + np.pi/6
        pt1 = (int(p2[0] - arrow_len * np.cos(a1)), int(p2[1] - arrow_len * np.sin(a1)))
        pt2 = (int(p2[0] - arrow_len * np.cos(a2)), int(p2[1] - arrow_len * np.sin(a2)))
        cv2.line(img, p2, pt1, color, 3)
        cv2.line(img, p2, pt2, color, 3)
        
    def _draw_pathfinding_route(self, image: np.ndarray, target_space: dict, occupied_spaces: List[dict]):
        """Determines and draws A* route to the target."""
        
        start_node = self.route_points[0]
        points = target_space['points']
        target_center = (sum(p[0] for p in points) // len(points), sum(p[1] for p in points) // len(points))
        end_node_before_spot = self._get_nearest_route_node(target_center)
        
        if end_node_before_spot is None:
            return

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
        # else:
            # print("No safe route found to target location.") # Disabled to avoid console spam
            
    # --- Pathfinding Functions (A*) ---
    def _get_nearest_route_node(self, target_point: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """Find the nearest route point to the target point"""
        if not self.route_points:
            return None
        distances = [np.linalg.norm(np.array(p) - np.array(target_point)) for p in self.route_points]
        min_index = np.argmin(distances)
        return self.route_points[min_index]
    
    def _find_path_a_star(self, start_node: Tuple[int, int], end_node: Tuple[int, int], occupied_space_details: List[dict]) -> Optional[List[Tuple[int, int]]]:
        """
        Wersja z 'Siatką Połączeń' (Mesh): Łączy punkty na podstawie odległości,
        dając algorytmowi swobodę wyboru trasy (objazdu).
        """
        
        if start_node not in self.route_points or end_node not in self.route_points: return None

        nodes = self.route_points
        
        # Build graph based on proximity
        graph = {node: [] for node in nodes}
        
        # Max distance to connect nodes
        # IF TOO SMALL -> isolated nodes
        # IF TOO LARGE -> performance hit
        CONNECTION_RADIUS = 250
        
        for i, node_a in enumerate(nodes):
            for j, node_b in enumerate(nodes):
                if i == j: continue # Nie łącz punktu samego ze sobą
                
                # Oblicz dystans między punktami
                dist = np.linalg.norm(np.array(node_a) - np.array(node_b))
                
                if dist < CONNECTION_RADIUS:
                    
                    graph[node_a].append(node_b)
        
        def heuristic(node):
            return np.linalg.norm(np.array(node) - np.array(end_node))

        queue = [(0 + heuristic(start_node), 0, start_node, [start_node])] # (f, g, node, path)
        visited_g = {start_node: 0}

        while queue:
            f, g, current_node, path = heapq.heappop(queue)

            if current_node == end_node: return path

            # Jeśli nie ma sąsiadów, to znaczy że punkt jest "samotną wyspą" (zwiększ CONNECTION_RADIUS)
            for neighbor in graph[current_node]:
                cost = np.linalg.norm(np.array(current_node) - np.array(neighbor)) 
                new_g = g + cost

                if self._segment_intersects_occupied_space(current_node, neighbor, occupied_space_details):
                    continue

                if neighbor not in visited_g or new_g < visited_g[neighbor]:
                    visited_g[neighbor] = new_g
                    new_f = new_g + heuristic(neighbor)
                    heapq.heappush(queue, (new_f, new_g, neighbor, path + [neighbor]))
        
        return None
    
    def _segment_intersects_occupied_space(self, p1: Tuple[int, int], p2: Tuple[int, int], occupied_spaces: List[dict]) -> bool:
        """
        Sprawdza, czy linia p1->p2 przecina jakiekolwiek zajęte miejsce.
        Wersja ulepszona: gęste próbkowanie + margines bezpieczeństwa.
        """
        
        if not occupied_spaces:
            return False

        # 1. Oblicz wektor i długość odcinka
        p1_arr = np.array(p1)
        p2_arr = np.array(p2)
        dist_total = np.linalg.norm(p1_arr - p2_arr)
        
        if dist_total == 0: return False

        # 2. Dynamiczna liczba punktów: Sprawdzamy co 10 pikseli
        # Dla odcinka 500px -> 51 punktów. Dla 20px -> 3 punkty.
        step_size = 10 
        num_checks = int(dist_total / step_size) + 2 
        
        for occupied_space in occupied_spaces:
            points = occupied_space['points']
            # Zamiana na format oczekiwany przez OpenCV
            pts = np.array(points, dtype=np.int32)

            for i in range(num_checks):
                t = i / (num_checks - 1) # t od 0.0 do 1.0
                
                # Interpolacja punktu na linii
                check_x = int(p1[0] * (1-t) + p2[0] * t)
                check_y = int(p1[1] * (1-t) + p2[1] * t)
                
                # 3. Test z marginesem (measureDist=True)
                # dist_to_border: >0 wewnątrz, <0 na zewnątrz.
                # Warunek >= -5 oznacza: "Wewnątrz LUB bliżej niż 5px od krawędzi"
                dist_to_border = cv2.pointPolygonTest(pts, (check_x, check_y), True)
                
                if dist_to_border >= -5:
                    return True
                    
        return False

