import cv2
import pickle
import numpy as np
from typing import List, Tuple, Optional, Union, Dict, Any
import os
import heapq # For implemeting priority queue A*
import string

class ParkClassifier:
    """Generic parking space classifier using digital image processing"""
    
    def __init__(self, 
                 car_park_positions_path: str,
                 rect_width: int = 107,
                 rect_height: int = 48,
                 processing_params: dict = None):
        
        self.car_park_positions, self.route_points = self._read_positions(car_park_positions_path)
        self.rect_height = rect_height
        self.rect_width = rect_width
        self.car_park_positions_path = car_park_positions_path
        
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
    
    def _read_positions(self, car_park_positions_path: str) -> Tuple[List, List]:
        """Read parking positions and route points from pickle file"""
        if not os.path.exists(car_park_positions_path):
            print(f"Positions file not found: {car_park_positions_path}")
            return [], []
        try:
            with open(car_park_positions_path, 'rb') as f:
                data = pickle.load(f)

                if isinstance(data, list):
                    # Stary format (tylko lista pozycji)
                    return data, []
                else:
                    # Nowy format (słownik)
                    return data.get('car_park_positions', []), data.get('route_points', [])

        except Exception as e:
            print(f"Error reading positions file: {e}")
            return [], []
    
    def classify(self, 
            image: np.ndarray, 
            processed_image: np.ndarray,
            threshold: int = 900) -> Tuple[np.ndarray, dict]:
            """
            Classify parking spaces. Spaces are processed in order of their stable, 
            numerical ID to ensure correct route prioritization.
            """
            
            empty_spaces = 0
            occupied_spaces = 0
            space_details = []

            # --- KLUCZOWA ZMIANA: SORTOWANIE WEDŁUG NUMERYCZNEGO ID ---
            
            # 1. Kopiowanie listy przed sortowaniem, aby nie modyfikować self.car_park_positions trwale
            sorted_positions = self.car_park_positions.copy()
            
            # 2. Funkcja klucza sortowania: próbuje zamienić ID na INT, jeśli się nie da, używa dużej liczby.
            def sort_key(pos):
                raw_id = pos.get('id', '99999') 
                try:
                    # Sortuj według wartości numerycznej
                    return int(raw_id)
                except:
                    # Nieudane parsowanie (np. ID to 'A1' lub '?') - ustawia dużą wartość na koniec.
                    return 99999 

            sorted_positions.sort(key=sort_key)
            # --- KONIEC SORTOWANIA ---

            # Iteracja po POSORTOWANEJ liście gwarantuje, że priorytet jest według ID (1, 2, 3...)
            for pos in sorted_positions: 
                
                # POBIERANIE STAŁEGO ID
                spot_id_raw = pos.get('id')
                spot_id = str(spot_id_raw) if spot_id_raw is not None else '?'
                
                # Handle both rectangle (4 points) and polygon formats
                if isinstance(pos, dict):
                    # Nowy format
                    points = pos['points']
                    is_irregular = pos.get('irregular', False)
                    
                    # Get bounding box (potrzebne do wycięcia crop)
                    x_coords = [p[0] for p in points]
                    y_coords = [p[1] for p in points]
                    x_min, x_max = min(x_coords), max(x_coords)
                    y_min, y_max = min(y_coords), max(y_coords)
                    
                    # Create mask for irregular shapes
                    if is_irregular:
                        # Logika maskowania
                        mask = np.zeros(processed_image.shape, dtype=np.uint8)
                        pts = np.array(points, dtype=np.int32)
                        cv2.fillPoly(mask, [pts], 255)
                        crop = cv2.bitwise_and(processed_image[y_min:y_max, x_min:x_max], 
                                            mask[y_min:y_max, x_min:x_max])
                    else:
                        crop = processed_image[y_min:y_max, x_min:x_max]
                    
                    # Count non-zero pixels
                    count = cv2.countNonZero(crop)
                    
                else:
                    # Stary format (dla kompatybilności wstecznej)
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
                
                # Classify space
                is_empty = count < threshold
                if is_empty:
                    empty_spaces += 1
                    color = (0, 255, 0)  # Green for empty
                    thickness = 5
                    status = "Empty"
                else:
                    occupied_spaces += 1
                    color = (0, 0, 255)  # Red for occupied
                    thickness = 2
                    status = "Occupied"
                
                # Store space details (UŻYWA STAŁEGO ID)
                space_details.append({
                    'id': spot_id, 
                    'points': points,
                    'status': status,
                    'pixel_count': count,
                    'is_empty': is_empty,
                    'irregular': is_irregular
                })
                
                # Draw polygon
                pts = np.array(points, dtype=np.int32)
                cv2.polylines(image, [pts], True, color, thickness)
                
                # Draw space number (UŻYWA STAŁEGO ID)
                center_x = sum(p[0] for p in points) // len(points)
                center_y = sum(p[1] for p in points) // len(points)
                
                cv2.putText(image, spot_id, (center_x - 10, center_y), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
            # Draw info panel
            self._draw_info_panel(image, empty_spaces, len(self.car_park_positions))
            
            # Ponieważ space_details jest teraz posortowane według ID, to gwarantuje
            # priorytet nawigacji dla najniższego numeru ID.
            first_empty_space = next((s for s in space_details if s['is_empty']), None)
            
            # 2. Zbuduj listę przeszkód
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
    
    def _draw_pathfinding_route(self, image: np.ndarray, target_space: dict, occupied_spaces: List[dict]):
        """Wyznacza i rysuje trasę A* do celu."""
        
        # 1. Węzeł startowy (pierwszy punkt trasy)
        start_node = self.route_points[0]
        
        # 2. Węzeł docelowy: Znajdź najbliższy węzeł trasy do celu
        points = target_space['points']
        target_center = (sum(p[0] for p in points) // len(points), sum(p[1] for p in points) // len(points))
        
        # Najpierw docieramy do najbliższego węzła trasy, który jest najbliżej miejsca
        # (lub do ostatniego, jeśli to miejsce jest na końcu trasy)
        end_node_before_spot = self._get_nearest_route_node(target_center)
        
        if end_node_before_spot is None:
            return

        # 3. Uruchom Pathfinding
        found_path = self._find_path_a_star(start_node, end_node_before_spot, occupied_spaces)
        
        if found_path:
            # Dodaj ostatni segment: z ostatniego węzła do środka miejsca
            final_route = found_path + [target_center] 
            
            color = (255, 255, 0)
            
            # Rysowanie wyznaczonej trasy
            for i in range(1, len(final_route)):
                p1 = final_route[i-1]
                p2 = final_route[i]
                
                cv2.line(image, p1, p2, color, 4)
                self._draw_arrowhead(image, p1, p2, color) 
                
            # Podświetlenie celu
            cv2.circle(image, target_center, 20, color, -1)
            cv2.putText(image, "DOJAZD", (target_center[0] - 30, target_center[1] + 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        else:
            # Jeśli nie znaleziono trasy (np. całkowicie zablokowane)
            print("Nie znaleziono bezpiecznej trasy do miejsca docelowego.")
    
    def _draw_route_to_space(self, image: np.ndarray, target_space: dict): 
        """Draw route from route points to the target parking space"""
        if not self.route_points:
            return
            
        # Środek wolnego miejsca (używamy target_space)
        points = target_space['points'] 
        end_x = sum(p[0] for p in points) // len(points)
        end_y = sum(p[1] for p in points) // len(points)
        end_point = (end_x, end_y)

        color = (255, 255, 0) # Żółty/cyjan

        # Użyj wszystkich punktów trasy dojazdu
        route_path = list(self.route_points)
        route_path.append(end_point)

        for i in range(1, len(route_path)):
            p1 = route_path[i-1]
            p2 = route_path[i]

            # Rysowanie linii
            cv2.line(image, p1, p2, color, 3)

            # Dodanie strzałki na końcu każdego segmentu
            self._draw_arrowhead(image, p1, p2, color) # Rysuj grot strzałki na każdym segmencie (wizualizacja kierunku)
            

        # 2. Podświetlenie numeru wolnego miejsca
        center_x = end_point[0]
        center_y = end_point[1]
        cv2.circle(image, end_point, 15, color, 4)

        cv2.putText(image, "DOJAZD", (center_x - 30, center_y + 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    
    def _draw_arrowhead(self, img, p1, p2, color):
        """Draw a simple arrowhead on the line segment from p1 to p2"""
        v = np.array(p2) - np.array(p1)
        
        # Zabezpieczenie przed zerową długością wektora
        if np.linalg.norm(v) == 0:
            return
            
        # Oblicz wektor kierunkowy i jednostkowy
        v_norm = v / np.linalg.norm(v)

        # Kąt wektora
        angle = np.arctan2(v[1], v[0])

        # Długość strzałki
        arrow_len = 20

        # Obliczenie punktów bocznych (pod kątem +/- 30 stopni)
        a1 = angle - np.pi/6
        a2 = angle + np.pi/6

        pt1 = (int(p2[0] - arrow_len * np.cos(a1)), int(p2[1] - arrow_len * np.sin(a1)))
        pt2 = (int(p2[0] - arrow_len * np.cos(a2)), int(p2[1] - arrow_len * np.sin(a2)))

        cv2.line(img, p2, pt1, color, 3)
        cv2.line(img, p2, pt2, color, 3)
        
    def _draw_info_panel(self, image: np.ndarray, empty_spaces: int, total_spaces: int):
        """Draw information panel on image"""
        # Background rectangle
        cv2.rectangle(image, (45, 30), (300, 85), (180, 0, 180), -1)
        
        # Text
        ratio_text = f'Free: {empty_spaces}/{total_spaces}'
        occupancy_rate = ((total_spaces - empty_spaces) / total_spaces * 100) if total_spaces > 0 else 0
        rate_text = f'Occupancy: {occupancy_rate:.1f}%'
        
        cv2.putText(image, ratio_text, (50, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(image, rate_text, (50, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
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
    
    def _get_nearest_route_node(self, target_point: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """Find the nearest route point to the target point"""
        if not self.route_points:
            return None
        
        # Calculating Euclidean distances
        distances = [np.linalg.norm(np.array(p) - np.array(target_point)) for p in self.route_points]
        min_index = np.argmin(distances)
        return self.route_points[min_index]
    
    def _find_path_a_star(self, start_node: Tuple[int, int], end_node: Tuple[int, int], occupied_space_details: List[dict]) -> Optional[List[Tuple[int, int]]]:
        """Implementacja uproszczonego algorytmu A* na grafie Route Points."""
        
        if start_node not in self.route_points or end_node not in self.route_points:
            # Jeśli punkty Start lub End nie są węzłami Route Points, coś jest nie tak (lub trzeba je tymczasowo dodać)
            return None

        nodes = self.route_points
        # Tworzenie krawędzi grafu (połączenie z sąsiadami)
        graph = {node: [] for node in nodes}
        
        # Dla prostego grafu opartym na kolejności, każdy węzeł łączy się z sąsiadami na liście
        for i in range(len(nodes)):
            if i > 0:
                graph[nodes[i]].append(nodes[i-1]) # Połączenie wstecz
            if i < len(nodes) - 1:
                graph[nodes[i]].append(nodes[i+1]) # Połączenie do przodu

        # Heurystyka (odległość Euklidesowa do celu)
        def heuristic(node):
            return np.linalg.norm(np.array(node) - np.array(end_node))

        # Algorytm A*
        queue = [(0 + heuristic(start_node), 0, start_node, [start_node])] # (f, g, node, path)
        visited_g = {start_node: 0} # Przechowuje najmniejszy koszt g znaleziony dla węzła

        while queue:
            f, g, current_node, path = heapq.heappop(queue)

            if current_node == end_node:
                return path # ZNALEZIONO ŚCIEŻKĘ!

            for neighbor in graph[current_node]:
                # Edge cost = 1 ( or use Euclidean distance if we want shorter paths)
                # We use Euclidean distance for cost
                cost = np.linalg.norm(np.array(current_node) - np.array(neighbor)) 
                new_g = g + cost

                # Checking for collisions (Przeszkody)
                # Sprawdź, czy segment (current_node -> neighbor) przechodzi przez ZAJĘTE miejsce parkingowe
                if self._segment_intersects_occupied_space(current_node, neighbor, occupied_space_details):
                    continue # Ignore this path (endless obstacle)

                if neighbor not in visited_g or new_g < visited_g[neighbor]:
                    visited_g[neighbor] = new_g
                    new_f = new_g + heuristic(neighbor)
                    heapq.heappush(queue, (new_f, new_g, neighbor, path + [neighbor]))
        
        return None # The path was not found
    
    def _segment_intersects_occupied_space(self, p1: Tuple[int, int], p2: Tuple[int, int], occupied_spaces: List[dict]) -> bool:
        """Check if the line segment p1->p2 intersects any occupied parking space"""
        # UŻYJMY ZAAWANSOWANEGO UPROSZCZENIA: Sprawdź 5 punktów na krawędzi
    
        for occupied_space in occupied_spaces:
            # Pomiń sprawdzenie dla miejsc nieregularnych, jeśli ich maska koliduje (założenie: trasa ma omijać parkingi)
            
            # Omijamy sprawdzanie, jeśli polygon jest zbyt skomplikowany. 
            # Zamiast tego, dla bezpieczeństwa, sprawdźmy bounding box zajętego miejsca
            points = occupied_space['points']
            pts = np.array(points, dtype=np.int32)

            # Sprawdzenie punktów na linii p1-p2
            num_checks = 5
            for i in range(num_checks + 1):
                t = i / num_checks
                check_x = int(p1[0] * (1-t) + p2[0] * t)
                check_y = int(p1[1] * (1-t) + p2[1] * t)
                
                # Jeśli punkt na ścieżce znajduje się wewnątrz zajętego polygonu: KOLIZJA!
                if cv2.pointPolygonTest(pts, (check_x, check_y), False) >= 0:
                    return True
        


class CoordinateDenoter:
    """Generic coordinate annotation tool with rectangular and irregular modes"""
    
    def __init__(self, 
                 rect_width: int = 107, 
                 rect_height: int = 48, 
                 car_park_positions_path: str = "data/CarParkPos"):
        
        self.rect_width = rect_width
        self.rect_height = rect_height
        self.car_park_positions_path = car_park_positions_path
        self.car_park_positions : List[Dict[str, Any]] = []
        
        # Mode settings
        self.mode = 'p'  # 'p' for rectangular (default), 'i' for irregular, 't' for route points,'e': edit ID
        self.irregular_points = []  # Temporary storage for irregular shape points
        self.route_points = [] # Points for visualizing route/arrows
        self.temp_image = None  # For displaying temporary points
        
        # Nowe zmienne dla symulowanego pola tekstowego
        self.is_editing_id = False
        self.edit_target_index = -1
        self.input_buffer = ""
        self.edit_box_pos: Tuple[int, int] = (0, 0)
        self.blink_state = True # Do symulacji migającego kursora
        
        os.makedirs(os.path.dirname(car_park_positions_path), exist_ok=True)
      
        
    def _get_next_id(self) -> int:
        """
        Generates the next unique integer ID. 
        It prioritizes finding the lowest available ID (filling gaps) 
        before returning the next consecutive ID after the max.
        """
        if not self.car_park_positions:
            return 1
            
        existing_int_ids = set()
        for pos in self.car_park_positions:
            spot_id = pos.get('id')
            try:
                # Wczytujemy tylko ID, które da się bezpiecznie przekształcić na INT,
                # ponieważ tylko numeryczne ID są brane pod uwagę przy lukach
                if isinstance(spot_id, str) and spot_id.isdigit():
                    existing_int_ids.add(int(spot_id))
                elif isinstance(spot_id, int):
                    existing_int_ids.add(spot_id)
            except:
                pass 
        
        if not existing_int_ids:
            return 1

        sorted_ids = sorted(list(existing_int_ids))
        
        # Sprawdź luki: Najniższa dostępna ID, zaczynając od 1
        expected_id = 1
        for current_id in sorted_ids:
            if current_id > expected_id:
                # Znaleziono lukę! Zwróć najniższą wolną ID.
                return expected_id
            expected_id = current_id + 1
            
        # Jeśli nie znaleziono luk (lista jest ciągła), zwróć następną po największej.
        return expected_id # To jest max(sorted_ids) + 1
    
    
    def set_mode(self, mode: str):
        """Set annotation mode: 'p', 'i', 't', or 'e'"""
        if mode in ['p', 'i', 't', 'e']:
            self.mode = mode
            self.irregular_points = []
            
            if mode == 'p': text = 'Rectangular (P)'
            elif mode == 'i': text = 'Irregular (I)'
            elif mode == 't': text = 'Route Points (T)'
            elif mode == 'e': text = 'Edit ID (E)'
                
            print(f"Mode changed to: {text}")
        else:
            print(f"Invalid mode: {mode}. Use 'p', 'i', 't' or 'e'.")
    
    def read_positions(self) -> List[Dict[str, Any]]:
        """Read positions from file"""
        if os.path.exists(self.car_park_positions_path):
            try:
                with open(self.car_park_positions_path, 'rb') as f:
                    data = pickle.load(f)

                    if isinstance(data, list):
                        # Old format (lista pozycji)
                        self.car_park_positions = data
                        self.route_points = []
                    else:
                        # Nowy format (słownik)
                        self.car_park_positions = data.get('car_park_positions', [])
                        self.route_points = data.get('route_points', [])
                    
                    self._convert_old_format() # Upewnij się, że ID i format są poprawne

            except Exception as e:
                print(f"Error reading positions: {e}")
                self.car_park_positions = []
                self.route_points = []

        return self.car_park_positions
        
    
    def _convert_old_format(self):
        """Convert old formats to new dict format and ensure 'id' exists."""
        converted = []
        next_id = 1
        
        # 1. Ustal, od jakiego ID zacząć numerację nowych pozycji
        existing_ids = []
        for pos in self.car_park_positions:
            if isinstance(pos, dict) and 'id' in pos:
                try:
                    spot_id = pos['id']
                    if isinstance(spot_id, str) and spot_id.isdigit():
                         existing_ids.append(int(spot_id))
                    elif isinstance(spot_id, int):
                        existing_ids.append(spot_id)
                except:
                    pass
        
        if existing_ids:
            next_id = max(existing_ids) + 1
        
        # 2. Przekonwertuj i uzupełnij brakujące ID
        changed = False
        for pos in self.car_park_positions:
            if isinstance(pos, tuple):
                # Format: (x, y) - stary prostokąt
                x, y = pos
                converted.append({
                    'id': str(next_id), # Dodaj ID
                    'points': [
                        (x, y),
                        (x + self.rect_width, y),
                        (x + self.rect_width, y + self.rect_height),
                        (x, y + self.rect_height)
                    ],
                    'irregular': False
                })
                next_id += 1
                changed = True
            elif 'id' not in pos:
                # Brakujące ID w nowym formacie
                pos['id'] = str(next_id) 
                converted.append(pos)
                next_id += 1
                changed = True
            else:
                # Poprawny format
                converted.append(pos)
        
        if changed:
            self.car_park_positions = converted
            print("Converted positions to new format and ensured unique IDs.")
            self.save_positions()
    
    
    def save_positions(self):
        """Save positions to file"""
        data_to_save = {
            'car_park_positions': self.car_park_positions,
            'route_points': self.route_points
        }
        try:
            with open(self.car_park_positions_path, 'wb') as f:
                pickle.dump(data_to_save, f)
            print(f"Saved {len(self.car_park_positions)} positions and {len(self.route_points)} route points to {self.car_park_positions_path}")
        except Exception as e:
            print(f"Error saving positions: {e}")
    
    def _handle_text_input(self, key_code: int):
        """Handles keyboard input when in ID editing state."""
        char = chr(key_code)
        
        # 1. ENTER (zatwierdzenie)
        if key_code == 13: # Enter key
            if self.input_buffer:
                new_id_str = self.input_buffer.strip()
                current_spot_index = self.edit_target_index
                
                # Walidacja: Unikalność
                existing_ids = [str(pos['id']) for i, pos in enumerate(self.car_park_positions) if i != self.edit_target_index]
                
                if not new_id_str:
                    print("ID change cancelled - empty input.")
                else:
                    # Sprawdź, czy nowy ID już istnieje i czy nie jest to obecne ID
                    existing_spot_index = -1
                    for i, pos in enumerate(self.car_park_positions):
                        if i != current_spot_index and str(pos.get('id')) == new_id_str:
                            existing_spot_index = i
                            break
                            
                    if existing_spot_index != -1:
                        # --- LOGIKA ZAMIANY ID ---
                        old_id_of_current_spot = str(self.car_park_positions[current_spot_index]['id'])
                        
                        # 1. Przypisz stare ID obecnego miejsca do miejsca istniejącego
                        self.car_park_positions[existing_spot_index]['id'] = old_id_of_current_spot
                        
                        # 2. Przypisz nowe ID do miejsca edytowanego
                        self.car_park_positions[current_spot_index]['id'] = new_id_str
                        
                        print(f"SUCCESS: Swapped ID '{new_id_str}' (was at index {existing_spot_index}) with ID '{old_id_of_current_spot}' (now at index {existing_spot_index}).")
                        
                    else:
                        # --- LOGIKA NADPISANIA/USTAWIENIA NOWEGO UNIKALNEGO ID ---
                        self.car_park_positions[current_spot_index]['id'] = new_id_str
                        print(f"SUCCESS: ID updated to '{new_id_str}'.")

                    self.save_positions()
            else:
                print("ID change cancelled - input was cleared.")
            
            # Zakończ edycję
            self.is_editing_id = False
            self.input_buffer = ""
            self.edit_target_index = -1
            self.set_mode('p') # Powrót do trybu domyślnego
            return True

        # 2. BACKSPACE
        elif key_code == 8: # Backspace key
            self.input_buffer = self.input_buffer[:-1]
            return True

        # 3. Zwykłe znaki (litery, cyfry)
        elif char in string.ascii_letters or char in string.digits or char in [' ', '-', '_']:
            if len(self.input_buffer) < 20: # Ograniczenie długości
                self.input_buffer += char
            return True
        
        return False # Nieobsługiwany klawisz
    
    def mouseClick(self, events: int, x: int, y: int, flags: int, params: int):
        """Mouse callback function with mode support"""
        if events == cv2.EVENT_LBUTTONDOWN:
            if self.mode == 'p':
                # Rectangular mode (automatyczne dodawanie)
                new_position = {
                    'id': str(self._get_next_id()), # ID jako string
                    'points': [
                        (x, y),
                        (x + self.rect_width, y),
                        (x + self.rect_width, y + self.rect_height),
                        (x, y + self.rect_height)
                    ],
                    'irregular': False
                }
                self.car_park_positions.append(new_position)
                print(f"Added rectangular position (ID: {new_position['id']}) at: ({x}, {y})")
                self.save_positions()
                
            elif self.mode == 'i':
                # Irregular mode: collect 4 points
                self.irregular_points.append((x, y))
                print(f"Point {len(self.irregular_points)}/4 added: ({x}, {y})")
                
                if len(self.irregular_points) == 4:
                    # Save the irregular shape
                    new_position = {
                        'id':str(self._get_next_id()), # ID jako string
                        'points': self.irregular_points.copy(),
                        'irregular': True
                    }
                    self.car_park_positions.append(new_position)
                    print(f"Added irregular position with points: {self.irregular_points}")
                    self.irregular_points = []  # Reset for next shape
                    self.save_positions()
            elif self.mode == 't': # Route points mode
                self.route_points.append((x, y))
                print(f"Added route point at: ({x}, {y})")
                self.save_positions()
                
            elif self.mode == 'e': 
                if self.is_editing_id: # Jeśli już edytujemy, zignoruj kliknięcie
                    return

                # Znajdź kliknięte miejsce
                target_spot_index = -1
                for i, pos in enumerate(self.car_park_positions):
                    points = pos['points']
                    pts = np.array(points, dtype=np.int32)
                    if cv2.pointPolygonTest(pts, (x, y), False) >= 0:
                        target_spot_index = i
                        break
                
                if target_spot_index != -1:
                    # Rozpocznij edycję
                    self.edit_target_index = target_spot_index
                    self.input_buffer = str(self.car_park_positions[target_spot_index]['id'])
                    self.is_editing_id = True
                    self.edit_box_pos = (x, y) # Lokalizacja pola tekstowego (opcjonalnie, można użyć centrum)
                    print(f"Entering edit mode for ID: {self.input_buffer}")
                else:
                    print("No spot found at clicked location.")
                    
        elif events == cv2.EVENT_RBUTTONDOWN:
            # Domyślne usuwanie pozycji
            for index, pos in enumerate(self.car_park_positions):
                points = pos['points']
                
                pts = np.array(points, dtype=np.int32)
                if cv2.pointPolygonTest(pts, (x, y), False) >= 0:
                    removed_pos = self.car_park_positions.pop(index)
                    print(f"Removed position (ID: {removed_pos.get('id', 'N/A')})")
                    self.save_positions()
                    break
                
                            
            # Also cancel current irregular drawing on right-click
            if self.mode == 'i' and self.irregular_points:
                print(f"Cancelled irregular shape (had {len(self.irregular_points)} points)")
                self.irregular_points = []
                
            # Remove nearest route point on right-click in mode 't'    
            if self.mode == 't' and self.route_points:
                # Find nearest route point to remove
                distances = [np.sqrt((px - x)**2 + (py - y)**2) for px, py in self.route_points]
                min_dist_index = np.argmin(distances)

                if distances[min_dist_index] < 50: # Usuń tylko jeśli jest blisko (np. 50px)
                    removed_point = self.route_points.pop(min_dist_index)
                    print(f"Removed route point: {removed_point}. Remaining: {len(self.route_points)}")
                    self.save_positions()
        

    def draw_positions(self, image: np.ndarray) -> np.ndarray:
        """Draw all positions on image, including text input box if active."""
        display_image = image.copy()
        
        # Draw existing positions
        for i, pos in enumerate(self.car_park_positions):
            points = pos['points']
            is_irregular = pos.get('irregular', False)
            spot_id = str(pos.get('id', '?'))

            # Choose color
            color = (0, 0, 255) # Domyślny kolor (Niebieski/Biały)
            if is_irregular: 
                color = (255, 0, 255) # Irregular (Fioletowy)
            
            # Highlight currently edited spot (Zielony)
            if self.is_editing_id and i == self.edit_target_index:
                 color = (0, 255, 0) 

            # Draw polygon
            pts = np.array(points, dtype=np.int32)
            cv2.polylines(display_image, [pts], True, color, 2)
            
            # Draw space ID at center
            center_x = sum(p[0] for p in points) // len(points)
            center_y = sum(p[1] for p in points) // len(points)
            cv2.putText(display_image, spot_id, (center_x - 10, center_y), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        # --- Rysowanie symulowanego pola tekstowego (Edit ID) ---
        if self.is_editing_id:
            # Użyj centrum edytowanego miejsca jako punktu odniesienia
            points = self.car_park_positions[self.edit_target_index]['points']
            center_x = sum(p[0] for p in points) // len(points)
            center_y = sum(p[1] for p in points) // len(points)
            
            # Pozycja pola tekstowego (wyśrodkowane nad lub pod miejscem)
            box_width = 160
            box_height = 30
            box_start = (center_x - box_width // 2, center_y - box_height - 10)
            box_end = (center_x + box_width // 2, center_y - 10)

            # Rysowanie tła (miga)
            if self.blink_state:
                 # Aktywny stan: Białe tło i niebieska (lub żółta) ramka
                 bg_color = (255, 255, 255) # Białe tło
                 border_color = (255, 255, 0) # Żółta/Cyjan ramka (kontrastowa)
            else:
                 # Nieaktywny stan (mruganie): Szare tło
                 bg_color = (150, 150, 150) # Szare tło
                 border_color = (0, 0, 0) # Czarna ramka
            
            cv2.rectangle(display_image, box_start, box_end, bg_color, -1) 
            cv2.rectangle(display_image, box_start, box_end, border_color, 2)
            # Rysowanie tekstu
            text_x = box_start[0] + 5
            text_y = box_end[1] - 8
            
            # Wyświetl aktualny bufor wpisywanego tekstu
            cv2.putText(display_image, self.input_buffer, 
                        (text_x, text_y), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        
        # --- Draw temporary irregular points (Tryb 'i') ---
        if self.mode == 'i' and self.irregular_points:
            for idx, point in enumerate(self.irregular_points):
                cv2.circle(display_image, point, 5, (0, 255, 255), -1)
                cv2.putText(display_image, str(idx + 1), 
                            (point[0] + 10, point[1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            
            if len(self.irregular_points) > 1:
                for i in range(len(self.irregular_points) - 1):
                    cv2.line(display_image, self.irregular_points[i], 
                             self.irregular_points[i + 1], (0, 255, 255), 1)
                             
        # --- CODE FOR ROUTE POINTS (Tryb 't') ---
        if self.route_points:
            for i in range(len(self.route_points)):
                cv2.circle(display_image, self.route_points[i], 8, (255, 255, 0), -1) 
                cv2.putText(display_image, str(i), 
                             (self.route_points[i][0] + 10, self.route_points[i][1] - 10),
                             cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

                if i > 0:
                    cv2.line(display_image, self.route_points[i-1], 
                             self.route_points[i], (255, 255, 0), 2)

        return display_image