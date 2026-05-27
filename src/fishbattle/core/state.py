class PlayerState:
    def __init__(self):
        self.gold = 500  # 기본 골드 (상점 테스트를 위해 초기 500G 지급)
        self.current_map_id = "MAP_01"
        self.inventory = []  # 살림망 내 물고기 목록

        # 장비 아이템 ID 및 강화 레벨
        self.rod_id = "ROD_01"
        self.rod_lv = 1
        
        self.reel_id = "REEL_01"
        self.reel_lv = 1
        
        self.bobber_id = "BOB_01"
        self.bobber_lv = 1
        
        self.keep_id = "KEEP_01"
        self.keep_lv = 1
        
        self.boat_id = "BOAT_01"
        self.bait_id = "BAIT_01"
        self.bait_count = 999  # 기본 떡밥 무제한 느낌

    def get_max_inventory_slots(self, db):
        """살림망 등급에 따른 최대 인벤토리 크기"""
        keep_data = db.keeps.get(self.keep_id)
        if keep_data:
            return keep_data["levels"].get(self.keep_lv, 5)
        return 5

    def add_fish(self, fish_name, size, val, db):
        """물고기 살림망 추가 (성공 시 True, 가득 차면 False)"""
        max_slots = self.get_max_inventory_slots(db)
        if len(self.inventory) < max_slots:
            self.inventory.append({
                "name": fish_name,
                "size": size,
                "value": val
            })
            return True
        return False

    def sell_all_fishes(self):
        """살림망 비우고 골드 정산"""
        total_gold = sum(f["value"] for f in self.inventory)
        self.gold += total_gold
        self.inventory.clear()
        return total_gold

    def get_equipment_stats(self, db):
        """현재 장비 스펙 계산하여 딕셔너리로 반환"""
        stats = {
            "damage_mult": 1.0,
            "reeling_power": 3.0,
            "target_radius_bonus": 0,
            "time_bonus": 0.0,
            "bait_time_reduction": 0.0,
            "bait_rare_bonus": 0.0,
            "bait_epic_bonus": 0.0
        }

        # 1. 낚싯대 배율
        rod_data = db.rods.get(self.rod_id)
        if rod_data:
            stats["damage_mult"] = rod_data["levels"].get(self.rod_lv, 1.0)

        # 2. 릴 파워
        reel_data = db.reels.get(self.reel_id)
        if reel_data:
            stats["reeling_power"] = reel_data["levels"].get(self.reel_lv, 3.0)

        # 3. 찌 보너스
        bobber_data = db.bobbers.get(self.bobber_id)
        if bobber_data:
            stats["target_radius_bonus"] = bobber_data["levels"].get(self.bobber_lv, 0)

        # 4. 미끼 보너스
        bait_data = db.baits.get(self.bait_id)
        if bait_data:
            stats["bait_time_reduction"] = bait_data["time_reduction"]
            stats["bait_rare_bonus"] = bait_data["rare_bonus"]
            stats["bait_epic_bonus"] = bait_data["epic_bonus"]

        return stats
