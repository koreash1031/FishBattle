import os
import re

class GameDatabase:
    def __init__(self, project_root):
        self.project_root = project_root
        self.maps = {}
        self.fishes = {}
        self.rods = {}
        self.reels = {}
        self.bobbers = {}
        self.keeps = {}
        self.boats = {}
        self.baits = {}
        
        self.load_all()

    def parse_markdown_table(self, file_path):
        """마크다운 파일에서 표(Table) 구조 데이터를 파싱합니다."""
        if not os.path.exists(file_path):
            print(f"[Warning] File not found: {file_path}")
            return []

        table_data = []
        headers = []
        
        # Windows 한글 인코딩 폴백 지원 (utf-8 -> utf-8-sig -> cp949)
        encodings = ['utf-8', 'utf-8-sig', 'cp949']
        lines = []
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    lines = f.readlines()
                break  # 성공 시 탈출
            except UnicodeDecodeError:
                continue

        if not lines:
            print(f"[Error] Failed to read {file_path} with standard encodings.")
            return []
            
        in_table = False
        for line in lines:
            line = line.strip()
            if not line.startswith('|'):
                in_table = False
                continue
            
            # 표의 셀 데이터 분리
            cells = [c.strip() for c in line.split('|')[1:-1]]
            
            # 구분선(| :--- |) 감지
            if all(re.match(r'^:?-+:?$', c) for c in cells) and cells:
                continue
            
            if not in_table:
                # 헤더 정의
                headers = cells
                in_table = True
            else:
                # 데이터 행
                row = dict(zip(headers, cells))
                table_data.append(row)
                
        return table_data

    def clean_val(self, text):
        """강조 표시 제거 및 텍스트 앞뒤 트림"""
        return text.replace("**", "").strip()

    def parse_float(self, text, default=0.0):
        """문자열에서 첫 번째 실수를 추출하여 반환 (인코딩 깨짐이나 추가 한글 텍스트 방어)"""
        text = self.clean_val(text).replace(",", "")
        match = re.search(r'[-+]?\d*\.\d+|\d+', text)
        if match:
            try:
                return float(match.group())
            except ValueError:
                pass
        return default

    def parse_int(self, text, default=0):
        """문자열에서 첫 번째 정수를 추출하여 반환"""
        text = self.clean_val(text).replace(",", "")
        match = re.search(r'\d+', text)
        if match:
            try:
                return int(match.group())
            except ValueError:
                pass
        return default

    def find_key(self, row, contains_str):
        """한글 인코딩 깨짐에 대응하여 특정 단어를 포함하는 키의 값을 찾음"""
        for k, v in row.items():
            if contains_str in k:
                return v
        return ""

    def load_all(self):
        # 1. 지역(Map) 로드
        map_path = os.path.join(self.project_root, "map_database.md")
        map_rows = self.parse_markdown_table(map_path)
        for row in map_rows:
            map_id = self.clean_val(self.find_key(row, "ID"))
            if map_id:
                # 대기 시간 파싱 (예: "3초 / 10초")
                wait_time_str = self.find_key(row, "대기 시간")
                times = [self.parse_int(t) for t in wait_time_str.split('/')]
                min_time = times[0] if len(times) > 0 else 3
                max_time = times[1] if len(times) > 1 else 10

                # 확률 파싱 (예: "80% / 60%")
                def parse_prob(prob_str):
                    parts = prob_str.split('/')
                    base = self.parse_float(parts[0]) / 100.0 if len(parts) > 0 else 0.5
                    floor = self.parse_float(parts[1]) / 100.0 if len(parts) > 1 else 0.1
                    return base, floor

                common_base, common_floor = parse_prob(self.find_key(row, "일반"))
                rare_base, rare_floor = parse_prob(self.find_key(row, "희귀"))
                epic_base, epic_floor = parse_prob(self.find_key(row, "전설"))

                self.maps[map_id] = {
                    "id": map_id,
                    "name": self.clean_val(self.find_key(row, "이름")),
                    "boat_req": self.clean_val(self.find_key(row, "해금")).replace(" 이상", ""),
                    "min_wait": min_time,
                    "max_wait": max_time,
                    "common_base": common_base,
                    "common_floor": common_floor,
                    "rare_base": rare_base,
                    "rare_floor": rare_floor,
                    "epic_base": epic_base,
                    "epic_floor": epic_floor,
                }

        # 2. 물고기(Fish) 로드
        fish_path = os.path.join(self.project_root, "fish_database.md")
        fish_rows = self.parse_markdown_table(fish_path)
        for row in fish_rows:
            fish_id = self.clean_val(self.find_key(row, "ID"))
            if fish_id:
                # 크기 범위 (예: "5 ~ 15")
                size_str = self.find_key(row, "크기")
                sizes = [self.parse_float(s) for s in size_str.split('~')]
                min_size = sizes[0] if len(sizes) > 0 else 5.0
                max_size = sizes[1] if len(sizes) > 1 else 15.0

                # 시작 거리 범위 (예: "10 ~ 20")
                dist_str = self.find_key(row, "거리")
                dists = [self.parse_float(d) for d in dist_str.split('~')]
                min_dist = dists[0] if len(dists) > 0 else 10.0
                max_dist = dists[1] if len(dists) > 1 else 20.0

                self.fishes[fish_id] = {
                    "id": fish_id,
                    "name": self.clean_val(self.find_key(row, "이름")),
                    "map_id": self.clean_val(self.find_key(row, "지역")),
                    "rarity": self.clean_val(self.find_key(row, "등급")),
                    "min_size": min_size,
                    "max_size": max_size,
                    "hp": self.parse_float(self.find_key(row, "체력")),
                    "min_dist": min_dist,
                    "max_dist": max_dist,
                    "ring_speed": self.parse_float(self.find_key(row, "속도"), 1.5),
                    "target_radius": self.parse_float(self.find_key(row, "크기"), 40.0),
                    "hold_time": self.parse_float(self.find_key(row, "시간"), 2.0),
                    "value": self.parse_int(self.find_key(row, "가치")),
                }

        # 3. 아이템/상점 로드
        item_path = os.path.join(self.project_root, "item_database.md")
        
        # 마크다운 파일에 여러 테이블이 존재하므로 파서를 통해 개별적으로 처리
        encodings = ['utf-8', 'utf-8-sig', 'cp949']
        content = ""
        for enc in encodings:
            try:
                with open(item_path, 'r', encoding=enc) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        if not content:
            print("[Error] Failed to read item_database.md")
            return

        # 테이블 섹션 분리 파싱
        tables = re.findall(r'(\|.*?\|\n\|.*?\n(?:\|.*?\|\n)+)', content)
        
        for idx, table_str in enumerate(tables):
            rows = []
            lines = [l.strip() for l in table_str.strip().split('\n')]
            headers = [c.strip() for c in lines[0].split('|')[1:-1]]
            
            for line in lines[2:]:
                cells = [c.strip() for c in line.split('|')[1:-1]]
                if len(cells) == len(headers):
                    rows.append(dict(zip(headers, cells)))
            
            if not rows:
                continue

            first_row = rows[0]
            # ID 컬럼 감지
            id_val = self.clean_val(self.find_key(first_row, "ID"))
            
            if id_val.startswith("ROD"):
                for r in rows:
                    self.rods[self.clean_val(self.find_key(r, "ID"))] = self.build_level_stats(r, is_mult=True)
            elif id_val.startswith("REEL"):
                for r in rows:
                    self.reels[self.clean_val(self.find_key(r, "ID"))] = self.build_level_stats(r, is_mult=False)
            elif id_val.startswith("BOB"):
                for r in rows:
                    self.bobbers[self.clean_val(self.find_key(r, "ID"))] = self.build_level_stats(r, is_mult=False)
            elif id_val.startswith("KEEP"):
                for r in rows:
                    self.keeps[self.clean_val(self.find_key(r, "ID"))] = self.build_level_stats(r, is_mult=False)
            elif id_val.startswith("BOAT"):
                for r in rows:
                    boat_id = self.clean_val(self.find_key(r, "ID"))
                    self.boats[boat_id] = {
                        "id": boat_id,
                        "name": self.clean_val(self.find_key(r, "이름")),
                        "price": self.parse_int(self.find_key(r, "구매 가격")),
                        "unlock_map": self.clean_val(self.find_key(r, "해금 효과")).split('(')[0].strip()
                    }
            elif id_val.startswith("BAIT"):
                for r in rows:
                    bait_id = self.clean_val(self.find_key(r, "ID"))
                    prob_str = self.find_key(r, "희귀도")
                    
                    rare_bonus = 0.0
                    epic_bonus = 0.0
                    if "희귀 확률" in prob_str:
                        m = re.search(r'희귀 확률\s*\+(\d+)', prob_str)
                        if m: rare_bonus = float(m.group(1)) / 100.0
                    if "전설 확률" in prob_str:
                        m = re.search(r'전설 확률\s*\+(\d+)', prob_str)
                        if m: epic_bonus = float(m.group(1)) / 100.0

                    self.baits[bait_id] = {
                        "id": bait_id,
                        "name": self.clean_val(self.find_key(r, "이름")),
                        "price": self.parse_int(self.find_key(r, "가격")),
                        "time_reduction": self.parse_float(self.find_key(r, "단축")),
                        "rare_bonus": rare_bonus,
                        "epic_bonus": epic_bonus
                    }

    def build_level_stats(self, row, is_mult):
        eq_id = self.clean_val(self.find_key(row, "ID"))
        name = self.clean_val(self.find_key(row, "이름"))
        price = self.parse_int(self.find_key(row, "구매 가격"))
        upgrade_cost = self.parse_int(self.find_key(row, "강화"))

        levels = {}
        for lv in [1, 2, 3, 4, 5]:
            header_key = f"Lv.{lv}"
            # 유연한 레벨 매칭
            lv_val_str = ""
            for k, v in row.items():
                if f"Lv.{lv}" in k:
                    lv_val_str = v
                    break
            
            if is_mult:
                val = self.parse_float(lv_val_str, 1.0)
            else:
                val = self.parse_float(lv_val_str) if "." in lv_val_str else self.parse_int(lv_val_str)
            
            levels[lv] = val

        return {
            "id": eq_id,
            "name": name,
            "price": price,
            "upgrade_cost": upgrade_cost,
            "levels": levels
        }
