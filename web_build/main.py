import sys
import pygame
import time
import math
import random
import os
from core.database import GameDatabase
from core.state import PlayerState
from engine.fighting import FightingEngine
from ui.components import UIComponents

class FishBattleApp:
    def __init__(self):
        pygame.init()
        # 모바일 세로형 해상도 (360x640)
        self.screen_width = 360
        self.screen_height = 640
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Fish Battle - Real Play")
        self.clock = pygame.time.Clock()
        self.running = True
        self.fps = 60

        # 패키지 내부 데이터 폴더 경로 설정 (Windows PC & Android 공용 호환)
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "data"))
        print(f"[Info] Loading game databases from: {self.project_root}")

        # 모듈 데이터 인스턴스화
        self.db = GameDatabase(self.project_root)
        self.player = PlayerState()

        # 폰트 로딩
        pygame.font.init()
        try:
            self.font_main = pygame.font.SysFont("malgungothic", 13)
            self.font_large = pygame.font.SysFont("malgungothic", 22, bold=True)
            self.font_title = pygame.font.SysFont("malgungothic", 16, bold=True)
            self.font_judgment = pygame.font.SysFont("malgungothic", 20, bold=True)
            self.font_bite = pygame.font.SysFont("malgungothic", 36, bold=True)
        except Exception:
            self.font_main = pygame.font.SysFont(None, 16)
            self.font_large = pygame.font.SysFont(None, 24, bold=True)
            self.font_title = pygame.font.SysFont(None, 18, bold=True)
            self.font_judgment = pygame.font.SysFont(None, 22, bold=True)
            self.font_bite = pygame.font.SysFont(None, 34, bold=True)

        # 게임 대상태 (LOBBY -> CASTING -> WAITING -> FIGHTING -> RESULT | SHOP | INVENTORY)
        self.game_state = "LOBBY"
        
        # 1. Casting 관련 타이머
        self.casting_duration = 1.2
        self.casting_start_time = 0.0

        # 2. Waiting 관련 타이머 및 선택 물고기 정보
        self.waiting_duration = 0.0
        self.waiting_start_time = 0.0
        self.selected_fish_data = None
        self.bite_triggered = False
        self.bite_start_time = 0.0

        # 3. Fighting 엔진
        self.engine = None
        
        self.anim_time = 0.0

        # UI 에러 메시지 알림용
        self.ui_error_msg = ""
        self.ui_error_time = 0.0

        # 맵 리스트 관리
        self.maps_keys = sorted(list(self.db.maps.keys()))
        # 초기 맵으로 인덱스 맞추기
        if self.player.current_map_id in self.maps_keys:
            self.current_map_idx = self.maps_keys.index(self.player.current_map_id)
        else:
            self.current_map_idx = 0
            self.player.current_map_id = self.maps_keys[0] if self.maps_keys else "MAP_01"

    # ==========================================
    # 상태 전환 및 게임 루프 관리
    # ==========================================
    def start_casting(self):
        """1단계: 자동 캐스팅 시작"""
        self.game_state = "CASTING"
        self.casting_start_time = time.time()

    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(self.fps)
        pygame.quit()

    def start_waiting(self):
        """2단계: 입질 대기 상태 진입"""
        self.game_state = "WAITING"
        self.waiting_start_time = time.time()
        self.bite_triggered = False
        
        current_map = self.db.maps.get(self.player.current_map_id)
        if not current_map:
            min_wait, max_wait = 3, 10
        else:
            min_wait = current_map["min_wait"]
            max_wait = current_map["max_wait"]

        eq_stats = self.player.get_equipment_stats(self.db)
        reduced_max_wait = max_wait - eq_stats["bait_time_reduction"]

        if reduced_max_wait < min_wait + 1:
            reduced_max_wait = min_wait + 1

        self.waiting_duration = random.uniform(min_wait, reduced_max_wait)
        print(f"[Debug] Map Waiting Range: [{min_wait} ~ {reduced_max_wait}s] | Chosen: {self.waiting_duration:.2f}s")

        self.selected_fish_data = self.roll_fish(current_map, eq_stats)

    def roll_fish(self, map_data, eq_stats):
        """확률 가중치 계산하여 물고기 스폰 결정"""
        common_prob = max(map_data["common_base"], map_data["common_floor"])
        rare_prob = max(map_data["rare_base"] + eq_stats["bait_rare_bonus"], map_data["rare_floor"])
        epic_prob = max(map_data["epic_base"] + eq_stats["bait_epic_bonus"], map_data["epic_floor"])

        total = common_prob + rare_prob + epic_prob
        common_prob /= total
        rare_prob /= total
        epic_prob /= total

        roll = random.random()
        chosen_rarity = "일반"
        if roll < epic_prob:
            chosen_rarity = "전설"
        elif roll < epic_prob + rare_prob:
            chosen_rarity = "희귀"

        eligible_fishes = []
        for fish_id, f in self.db.fishes.items():
            if f["map_id"] == map_data["id"] and f["rarity"] == chosen_rarity:
                eligible_fishes.append(f)

        if not eligible_fishes:
            eligible_fishes = [f for f in self.db.fishes.values() if f["map_id"] == map_data["id"]]

        selected = random.choice(eligible_fishes) if eligible_fishes else None
        return selected

    def trigger_bite(self):
        self.bite_triggered = True
        self.bite_start_time = time.time()

    def start_fighting(self):
        """3단계: 파이팅 단계 진입"""
        self.game_state = "FIGHTING"
        eq_stats = self.player.get_equipment_stats(self.db)
        
        fish_data = {
            "name": self.selected_fish_data["name"],
            "hp": self.selected_fish_data["hp"],
            "min_dist": self.selected_fish_data["min_dist"],
            "max_dist": self.selected_fish_data["max_dist"],
            "target_radius": self.selected_fish_data["target_radius"],
            "ring_speed": self.selected_fish_data["ring_speed"],
            "hold_time": self.selected_fish_data["hold_time"],
            "rarity": self.selected_fish_data["rarity"],
            "min_size": self.selected_fish_data["min_size"],
            "max_size": self.selected_fish_data["max_size"]
        }
        
        self.engine = FightingEngine(fish_data, eq_stats)

    def trigger_result(self):
        """4단계: 결과 팝업 진입"""
        self.game_state = "RESULT"
        if self.engine.result_status == "CATCH":
            size = self.engine.get_final_fish_size()
            fish_ratio = (size - self.selected_fish_data["min_size"]) / max(1.0, (self.selected_fish_data["max_size"] - self.selected_fish_data["min_size"]))
            val = int(self.selected_fish_data["value"] * (1.0 + fish_ratio))
            
            success_add = self.player.add_fish(self.engine.fish_name, size, val, self.db)
            self.catch_success_added = success_add
            self.catch_size = size
            self.catch_gold_reward = val
            
            # 살림망이 꽉 찬 경우 경고/자동 판매 로직
            if len(self.player.inventory) >= self.player.get_max_inventory_slots(self.db):
                print(f"[System] Inventory full! Please empty your inventory at Lobby.")

    def trigger_ui_error(self, msg):
        self.ui_error_msg = msg
        self.ui_error_time = time.time()

    def get_boat_rank(self, boat_id):
        if boat_id == "BOAT_01": return 1
        if boat_id == "BOAT_02": return 2
        if boat_id == "BOAT_03": return 3
        return 1

    def change_map(self, direction):
        """방향에 맞춰 선택 맵 변경 및 보트 요구사항 확인"""
        next_idx = (self.current_map_idx + direction) % len(self.maps_keys)
        next_map_id = self.maps_keys[next_idx]
        next_map = self.db.maps[next_map_id]

        req_boat_name = next_map["boat_req"]
        req_boat_id = "BOAT_01"
        for bid, bdata in self.db.boats.items():
            if bdata["name"] == req_boat_name:
                req_boat_id = bid
                break

        player_rank = self.get_boat_rank(self.player.boat_id)
        req_rank = self.get_boat_rank(req_boat_id)

        if player_rank >= req_rank:
            self.current_map_idx = next_idx
            self.player.current_map_id = next_map_id
        else:
            self.trigger_ui_error(f"이동 실패: {req_boat_name} 이상 필요!")

    def upgrade_equipment(self, eq_type):
        """장비 강화 로직"""
        if eq_type == "rod":
            eq_id = self.player.rod_id
            lv = self.player.rod_lv
            data = self.db.rods.get(eq_id)
        elif eq_type == "reel":
            eq_id = self.player.reel_id
            lv = self.player.reel_lv
            data = self.db.reels.get(eq_id)
        elif eq_type == "bobber":
            eq_id = self.player.bobber_id
            lv = self.player.bobber_lv
            data = self.db.bobbers.get(eq_id)
        elif eq_type == "keep":
            eq_id = self.player.keep_id
            lv = self.player.keep_lv
            data = self.db.keeps.get(eq_id)
        else:
            return

        if not data:
            return

        if lv >= 5:
            self.trigger_ui_error("이미 최대 강화 수치입니다!")
            return

        cost = data["upgrade_cost"] * lv  # 레벨에 따라 강화비용 증가
        if self.player.gold >= cost:
            self.player.gold -= cost
            if eq_type == "rod": self.player.rod_lv += 1
            elif eq_type == "reel": self.player.reel_lv += 1
            elif eq_type == "bobber": self.player.bobber_lv += 1
            elif eq_type == "keep": self.player.keep_lv += 1
            print(f"[Upgrade] Upgraded {eq_type} to level {lv + 1} for {cost} G.")
        else:
            self.trigger_ui_error("골드가 부족합니다!")

    def upgrade_boat(self):
        """보트 구매/강화 로직"""
        current_boat = self.player.boat_id
        if current_boat == "BOAT_01":
            next_boat = "BOAT_02"
        elif current_boat == "BOAT_02":
            next_boat = "BOAT_03"
        else:
            self.trigger_ui_error("최고 등급 보트를 소유하고 있습니다!")
            return

        boat_data = self.db.boats.get(next_boat)
        if not boat_data:
            return

        price = boat_data["price"]
        if self.player.gold >= price:
            self.player.gold -= price
            self.player.boat_id = next_boat
            print(f"[Purchase] Bought boat {boat_data['name']} for {price} G.")
        else:
            self.trigger_ui_error("골드가 부족합니다!")

    # ==========================================
    # 이벤트 처리 및 드로잉
    # ==========================================
    def handle_events(self):
        m_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    self.start_casting()

            # 마우스 입력 처리
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    # RESULT 상태일 때: 터치로 팝업 닫고 다음 루프 순환
                    if self.game_state == "RESULT":
                        self.game_state = "LOBBY"
                        
                    elif self.game_state == "LOBBY":
                        # 하단 버튼 감지 (y >= 300)
                        if m_pos[1] >= 300:
                            # 1. 낚시 시작 (y: 360~400)
                            if 20 <= m_pos[0] <= 340 and 360 <= m_pos[1] <= 400:
                                self.start_casting()
                            # 2. 장비 상점 (y: 415~455)
                            elif 20 <= m_pos[0] <= 340 and 415 <= m_pos[1] <= 455:
                                self.game_state = "SHOP"
                            # 3. 살림망 확인 (y: 470~510)
                            elif 20 <= m_pos[0] <= 340 and 470 <= m_pos[1] <= 510:
                                self.game_state = "INVENTORY"
                            # 4. 맵 선택 좌측 (x: 20~50, y: 530~560)
                            elif 20 <= m_pos[0] <= 50 and 530 <= m_pos[1] <= 560:
                                self.change_map(-1)
                            # 5. 맵 선택 우측 (x: 310~340, y: 530~560)
                            elif 310 <= m_pos[0] <= 340 and 530 <= m_pos[1] <= 560:
                                self.change_map(1)

                    elif self.game_state == "INVENTORY":
                        if m_pos[1] >= 300:
                            # 모두 판매 (y: 510~550)
                            if 20 <= m_pos[0] <= 340 and 510 <= m_pos[1] <= 550:
                                self.player.sell_all_fishes()
                            # 뒤로가기 (y: 560~600)
                            elif 20 <= m_pos[0] <= 340 and 560 <= m_pos[1] <= 600:
                                self.game_state = "LOBBY"

                    elif self.game_state == "SHOP":
                        if m_pos[1] >= 300:
                            # 낚싯대 강화 (y: 355~380)
                            if 250 <= m_pos[0] <= 340 and 355 <= m_pos[1] <= 380:
                                self.upgrade_equipment("rod")
                            # 릴 강화 (y: 390~415)
                            elif 250 <= m_pos[0] <= 340 and 390 <= m_pos[1] <= 415:
                                self.upgrade_equipment("reel")
                            # 찌 강화 (y: 425~450)
                            elif 250 <= m_pos[0] <= 340 and 425 <= m_pos[1] <= 450:
                                self.upgrade_equipment("bobber")
                            # 살림망 강화 (y: 460~485)
                            elif 250 <= m_pos[0] <= 340 and 460 <= m_pos[1] <= 485:
                                self.upgrade_equipment("keep")
                            # 보트 구매 (y: 495~520)
                            elif 250 <= m_pos[0] <= 340 and 495 <= m_pos[1] <= 520:
                                self.upgrade_boat()
                            # 뒤로가기 (y: 570~610)
                            elif 20 <= m_pos[0] <= 340 and 570 <= m_pos[1] <= 610:
                                self.game_state = "LOBBY"

                    elif self.game_state == "FIGHTING":
                        # 하단 53% 조작계 마우스 감지 (y >= 300)
                        if m_pos[1] >= 300:
                            if self.engine.current_phase == "A":
                                mx, my = event.pos
                                dist = math.hypot(mx - self.engine.target_x, my - self.engine.target_y)
                                if dist <= self.engine.target_radius:
                                    self.engine.handle_rhythm_input(time.time())
                                else:
                                    self.engine.handle_rhythm_input(None)
                            elif self.engine.current_phase == "B":
                                self.engine.start_hold()

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and self.game_state == "FIGHTING":
                    if self.engine.current_phase == "B":
                        self.engine.release_hold()

    def update(self):
        self.anim_time += 1.0 / self.fps

        if self.game_state == "CASTING":
            if time.time() - self.casting_start_time >= self.casting_duration:
                self.start_waiting()

        elif self.game_state == "WAITING":
            elapsed = time.time() - self.waiting_start_time
            if not self.bite_triggered:
                if elapsed >= self.waiting_duration:
                    self.trigger_bite()
            else:
                if time.time() - self.bite_start_time >= 0.8:
                    self.start_fighting()

        elif self.game_state == "FIGHTING":
            # 마우스 버튼 상태를 실시간 체크하여 홀드 해제 보조
            if self.engine.current_phase == "B":
                mouse_pressed = pygame.mouse.get_pressed()
                if mouse_pressed[0] and pygame.mouse.get_pos()[1] >= 300:
                    self.engine.start_hold()
                else:
                    self.engine.release_hold()

            self.engine.update()

            if self.engine.game_over:
                self.trigger_result()

    def draw(self):
        self.screen.fill((15, 23, 42))

        # 1. 상단 47% 비주얼 구역 렌더링
        self.draw_visual_area()

        # 2. 하단 53% 게임 플레이/HUD 구역 렌더링
        self.draw_battle_area()

        if self.game_state == "RESULT":
            self.draw_result_popup()

        # 에러 메시지 알림 팝업 드로우
        if self.ui_error_msg and time.time() - self.ui_error_time < 1.8:
            err_box_w = 260
            err_box_h = 35
            err_x = (self.screen_width - err_box_w) // 2
            err_y = 120
            pygame.draw.rect(self.screen, (239, 68, 68), (err_x, err_y, err_box_w, err_box_h), border_radius=6)
            pygame.draw.rect(self.screen, (255, 255, 255), (err_x, err_y, err_box_w, err_box_h), 1, border_radius=6)
            
            err_text = self.font_main.render(self.ui_error_msg, True, (255, 255, 255))
            self.screen.blit(err_text, (self.screen_width // 2 - err_text.get_width() // 2, err_y + err_box_h // 2 - err_text.get_height() // 2))

        pygame.display.flip()

    def draw_visual_area(self):
        visual_h = 300
        
        # A. 하늘 배경 그라데이션
        for y in range(0, 220):
            factor = y / 220.0
            r = int(24 - (24 - 15) * factor)
            g = int(30 - (30 - 20) * factor)
            b = int(48 - (48 - 36) * factor)
            pygame.draw.line(self.screen, (r, g, b), (0, y), (self.screen_width, y))

        # 달
        pygame.draw.circle(self.screen, (253, 224, 71), (300, 70), 20)
        pygame.draw.circle(self.screen, (15, 23, 42), (290, 70), 18)

        # B. 파도
        sea_level = 210
        points = []
        for x in range(0, self.screen_width + 10, 10):
            y_offset = math.sin(x * 0.05 + self.anim_time * 3) * 4
            points.append((x, sea_level + y_offset))
        points.append((self.screen_width, visual_h))
        points.append((0, visual_h))
        pygame.draw.polygon(self.screen, (14, 116, 144), points)

        # C. 흔들리는 보트
        boat_x, boat_y = 70, sea_level - 5
        boat_offset = math.sin(self.anim_time * 2) * 2
        pygame.draw.polygon(self.screen, (120, 74, 50), [
            (boat_x - 30, boat_y + boat_offset),
            (boat_x + 35, boat_y + boat_offset),
            (boat_x + 25, boat_y + 18 + boat_offset),
            (boat_x - 25, boat_y + 18 + boat_offset)
        ])
        pygame.draw.rect(self.screen, (80, 50, 30), (boat_x - 15, boat_y - 5 + boat_offset, 30, 8))

        # D. 캐릭터
        char_x = boat_x - 5
        char_y = boat_y - 2 + boat_offset
        pygame.draw.rect(self.screen, (30, 41, 59), (char_x - 6, char_y - 20, 12, 20), border_radius=3)
        pygame.draw.circle(self.screen, (244, 204, 160), (char_x, char_y - 26), 6)
        pygame.draw.polygon(self.screen, (239, 68, 68), [
            (char_x - 7, char_y - 30),
            (char_x + 7, char_y - 30),
            (char_x, char_y - 37)
        ])

        # E. 낚싯대
        rod_angle = math.radians(-35)
        if self.game_state == "CASTING":
            cast_elapsed = time.time() - self.casting_start_time
            angle_deg = -30 - 60 * math.sin(min(1.0, cast_elapsed / self.casting_duration) * math.pi)
            rod_angle = math.radians(angle_deg)
        elif self.game_state == "FIGHTING" and self.engine.current_phase == "B" and self.engine.is_holding:
            vibr = math.sin(self.anim_time * 30) * 3
            rod_angle = math.radians(-50 + vibr)
        else:
            rod_angle = math.radians(-35 + math.sin(self.anim_time * 4) * 2)

        rod_len = 55
        rod_end_x = char_x + 8 + int(rod_len * math.cos(rod_angle))
        rod_end_y = char_y - 12 + int(rod_len * math.sin(rod_angle))
        pygame.draw.line(self.screen, (156, 163, 175), (char_x + 2, char_y - 10), (rod_end_x, rod_end_y), 3)

        # F. 찌(Bobber) 및 낚싯줄
        bobber_x = 240
        bobber_y = sea_level + 15 + math.sin(self.anim_time * 4) * 3
        
        # LOBBY, SHOP, INVENTORY 일 땐 캐스팅 라인 안 그림
        if self.game_state in ["LOBBY", "SHOP", "INVENTORY"]:
            pass
        elif self.game_state == "CASTING":
            cast_elapsed = time.time() - self.casting_start_time
            t = min(1.0, cast_elapsed / self.casting_duration)
            start_pos = (rod_end_x, rod_end_y)
            end_pos = (bobber_x, sea_level + 15)
            
            curr_x = start_pos[0] + (end_pos[0] - start_pos[0]) * t
            height = -80 * math.sin(t * math.pi)
            curr_y = start_pos[1] + (end_pos[1] - start_pos[1]) * t + height
            
            pygame.draw.line(self.screen, (228, 228, 231), (rod_end_x, rod_end_y), (int(curr_x), int(curr_y)), 1)
            pygame.draw.circle(self.screen, (239, 68, 68), (int(curr_x), int(curr_y)), 4)
        else:
            pygame.draw.line(self.screen, (228, 228, 231), (rod_end_x, rod_end_y), (bobber_x, int(bobber_y)), 1)
            pygame.draw.circle(self.screen, (239, 68, 68), (bobber_x, int(bobber_y) - 3), 4)
            pygame.draw.circle(self.screen, (255, 255, 255), (bobber_x, int(bobber_y) + 2), 4)

            # 물속 물고기 그림자
            if self.game_state == "WAITING":
                elapsed = time.time() - self.waiting_start_time
                if self.waiting_duration - elapsed <= 0.8:
                    appr_ratio = min(1.0, (0.8 - (self.waiting_duration - elapsed)) / 0.8)
                    shadow_x = bobber_x + 40 * (1.0 - appr_ratio)
                    shadow_y = bobber_y + 18
                    pygame.draw.ellipse(self.screen, (10, 60, 80), (shadow_x - 10, shadow_y, 20, 8))
            
            elif self.game_state == "FIGHTING":
                freq = 20 if self.engine.is_rage else 8
                shadow_offset_x = math.sin(self.anim_time * freq) * (20 if self.engine.is_rage else 12)
                shadow_offset_y = 15 + math.cos(self.anim_time * 5) * 5
                shadow_w = 26 + int(self.engine.current_hp / self.engine.max_hp * 10)
                shadow_h = 12
                pygame.draw.ellipse(self.screen, (10, 80, 100), (bobber_x - shadow_w//2 + shadow_offset_x, bobber_y + shadow_offset_y, shadow_w, shadow_h))
                
                tail_x = bobber_x - shadow_w//2 - 4 + shadow_offset_x
                pygame.draw.polygon(self.screen, (10, 80, 100), [
                    (tail_x, bobber_y + shadow_offset_y + 2),
                    (tail_x - 6, bobber_y + shadow_offset_y - 3),
                    (tail_x - 6, bobber_y + shadow_offset_y + 7)
                ])
                
                # 물결 물보라
                splash_size = 12 + int(math.sin(self.anim_time * (25 if self.engine.is_rage else 15)) * 6)
                pygame.draw.circle(self.screen, (255, 255, 255, 120), (bobber_x, int(bobber_y)), splash_size, 1)

        # 경계선
        pygame.draw.line(self.screen, (51, 65, 85), (0, visual_h), (self.screen_width, visual_h), 4)
        pygame.draw.line(self.screen, (100, 116, 139), (0, visual_h + 2), (self.screen_width, visual_h + 2), 1)

    def draw_battle_area(self):
        # 하단 블랙 필터 (y: 302 ~ 640)
        pygame.draw.rect(self.screen, (10, 15, 30), (0, 302, self.screen_width, 338))

        m_pos = pygame.mouse.get_pos()

        # 골드 및 상태 기본 렌더링
        current_map = self.db.maps.get(self.player.current_map_id)
        map_name = current_map["name"] if current_map else "은빛 호수"
        map_label = self.font_title.render(f"📍 {map_name}", True, (244, 244, 245))
        gold_label = self.font_title.render(f"💰 {self.player.gold} G", True, (250, 204, 21))
        self.screen.blit(map_label, (20, 312))
        self.screen.blit(gold_label, (230, 312))

        # 살림망 칸수
        inv_slots = len(self.player.inventory)
        max_slots = self.player.get_max_inventory_slots(self.db)
        inv_text = self.font_main.render(f"살림망: {inv_slots}/{max_slots} 마리", True, (148, 163, 184))
        self.screen.blit(inv_text, (20, 332))

        if self.game_state == "LOBBY":
            # 1. 낚시 시작 버튼
            is_hover1 = (20 <= m_pos[0] <= 340 and 360 <= m_pos[1] <= 400)
            UIComponents.draw_button(self.screen, "🎣 낚시 시작하기", 20, 360, 320, 40, is_hover1, bg_color=(16, 185, 129), hover_color=(5, 150, 105))
            
            # 2. 장비 상점 버튼
            is_hover2 = (20 <= m_pos[0] <= 340 and 415 <= m_pos[1] <= 455)
            UIComponents.draw_button(self.screen, "🛠️ 장비 강화 상점", 20, 415, 320, 40, is_hover2)

            # 3. 살림망 확인 버튼
            is_hover3 = (20 <= m_pos[0] <= 340 and 470 <= m_pos[1] <= 510)
            UIComponents.draw_button(self.screen, "🐟 살림망/인벤토리 열기", 20, 470, 320, 40, is_hover3)

            # 4. 맵 이동/선택
            is_hoverL = (20 <= m_pos[0] <= 50 and 530 <= m_pos[1] <= 560)
            UIComponents.draw_button(self.screen, "<", 20, 530, 30, 30, is_hoverL)
            
            is_hoverR = (310 <= m_pos[0] <= 340 and 530 <= m_pos[1] <= 560)
            UIComponents.draw_button(self.screen, ">", 310, 530, 30, 30, is_hoverR)

            # 중앙 맵 이름 렌더링
            self.draw_centered_text(f"[ {map_name} ]", self.font_title, (34, 211, 238), 545)
            # 배 보트 정보 렌더링
            boat_data = self.db.boats.get(self.player.boat_id)
            boat_name = boat_data["name"] if boat_data else "목선"
            boat_lbl = self.font_main.render(f"소유 보트: {boat_name}", True, (200, 200, 200))
            self.screen.blit(boat_lbl, (self.screen_width // 2 - boat_lbl.get_width() // 2, 575))

        elif self.game_state == "INVENTORY":
            # 인벤토리 목록 그리기
            lbl_title = self.font_title.render("내 살림망 물고기 정보", True, (255, 255, 255))
            self.screen.blit(lbl_title, (20, 355))

            if not self.player.inventory:
                self.draw_centered_text("살림망이 비어있습니다. 물고기를 낚아보세요!", self.font_main, (148, 163, 184), 430)
            else:
                for idx, fish in enumerate(self.player.inventory[-5:]): # 최근 5마리 출력
                    y_p = 385 + (idx * 22)
                    fish_info = f"• {fish['name']} | {fish['size']:.1f}cm | {fish['value']} G"
                    txt_fish = self.font_main.render(fish_info, True, (244, 244, 245))
                    self.screen.blit(txt_fish, (25, y_p))

            # 모두 판매 버튼
            is_hover_sell = (20 <= m_pos[0] <= 340 and 510 <= m_pos[1] <= 550)
            sell_text = "🐟 전체 정산 및 판매" if not self.player.inventory else f"🐟 전체 판매 (+{sum(f['value'] for f in self.player.inventory)} G)"
            UIComponents.draw_button(self.screen, sell_text, 20, 510, 320, 40, is_hover_sell, bg_color=(234, 179, 8), hover_color=(202, 138, 4))

            # 뒤로 가기 버튼
            is_hover_back = (20 <= m_pos[0] <= 340 and 560 <= m_pos[1] <= 600)
            UIComponents.draw_button(self.screen, "🔙 로비로 가기", 20, 560, 320, 40, is_hover_back)

        elif self.game_state == "SHOP":
            # 장비 강화 상점
            lbl_shop = self.font_title.render("🛠️ 장비 및 보트 강화 상점", True, (255, 255, 255))
            self.screen.blit(lbl_shop, (20, 350))

            eq_y = 375
            # 1. 낚싯대 (데미지배율)
            r_data = self.db.rods.get(self.player.rod_id)
            r_lv = self.player.rod_lv
            r_cost = r_data["upgrade_cost"] * r_lv if r_lv < 5 else 0
            r_desc = f"낚싯대 (Lv.{r_lv}/5) x{r_data['levels'].get(r_lv, 1.0):.1f}"
            self.screen.blit(self.font_main.render(r_desc, True, (200, 200, 200)), (20, eq_y))
            btn_txt = "Max" if r_lv >= 5 else f"{r_cost}G 강화"
            is_h = (250 <= m_pos[0] <= 340 and eq_y - 2 <= m_pos[1] <= eq_y + 20)
            UIComponents.draw_button(self.screen, btn_txt, 250, eq_y - 2, 90, 22, is_h and r_lv < 5)

            # 2. 릴 (파이팅릴링)
            eq_y += 35
            re_data = self.db.reels.get(self.player.reel_id)
            re_lv = self.player.reel_lv
            re_cost = re_data["upgrade_cost"] * re_lv if re_lv < 5 else 0
            re_desc = f"릴링력 (Lv.{re_lv}/5) pwr:{re_data['levels'].get(re_lv, 3.0):.1f}"
            self.screen.blit(self.font_main.render(re_desc, True, (200, 200, 200)), (20, eq_y))
            btn_txt = "Max" if re_lv >= 5 else f"{re_cost}G 강화"
            is_h = (250 <= m_pos[0] <= 340 and eq_y - 2 <= m_pos[1] <= eq_y + 20)
            UIComponents.draw_button(self.screen, btn_txt, 250, eq_y - 2, 90, 22, is_h and re_lv < 5)

            # 3. 찌 (판정반경)
            eq_y += 35
            b_data = self.db.bobbers.get(self.player.bobber_id)
            b_lv = self.player.bobber_lv
            b_cost = b_data["upgrade_cost"] * b_lv if b_lv < 5 else 0
            b_desc = f"찌 타겟 (Lv.{b_lv}/5) sz:+{b_data['levels'].get(b_lv, 0)}"
            self.screen.blit(self.font_main.render(b_desc, True, (200, 200, 200)), (20, eq_y))
            btn_txt = "Max" if b_lv >= 5 else f"{b_cost}G 강화"
            is_h = (250 <= m_pos[0] <= 340 and eq_y - 2 <= m_pos[1] <= eq_y + 20)
            UIComponents.draw_button(self.screen, btn_txt, 250, eq_y - 2, 90, 22, is_h and b_lv < 5)

            # 4. 살림망 (칸수)
            eq_y += 35
            k_data = self.db.keeps.get(self.player.keep_id)
            k_lv = self.player.keep_lv
            k_cost = k_data["upgrade_cost"] * k_lv if k_lv < 5 else 0
            k_desc = f"살림망 (Lv.{k_lv}/5) {k_data['levels'].get(k_lv, 5)}칸"
            self.screen.blit(self.font_main.render(k_desc, True, (200, 200, 200)), (20, eq_y))
            btn_txt = "Max" if k_lv >= 5 else f"{k_cost}G 강화"
            is_h = (250 <= m_pos[0] <= 340 and eq_y - 2 <= m_pos[1] <= eq_y + 20)
            UIComponents.draw_button(self.screen, btn_txt, 250, eq_y - 2, 90, 22, is_h and k_lv < 5)

            # 5. 보트 (맵해금)
            eq_y += 35
            current_boat = self.player.boat_id
            if current_boat == "BOAT_01":
                next_boat_id = "BOAT_02"
                b_name = "목선 ➔ 모터보트"
            elif current_boat == "BOAT_02":
                next_boat_id = "BOAT_03"
                b_name = "모터보트 ➔ 트롤선"
            else:
                next_boat_id = None
                b_name = "최고등급 보트 소유함"

            self.screen.blit(self.font_main.render(b_name, True, (34, 211, 238)), (20, eq_y))
            if next_boat_id:
                next_bdata = self.db.boats.get(next_boat_id)
                btn_txt = f"{next_bdata['price']}G 구매"
                is_h = (250 <= m_pos[0] <= 340 and eq_y - 2 <= m_pos[1] <= eq_y + 20)
                UIComponents.draw_button(self.screen, btn_txt, 250, eq_y - 2, 90, 22, is_h, bg_color=(8, 145, 178), hover_color=(6, 182, 212))
            else:
                UIComponents.draw_button(self.screen, "Max", 250, eq_y - 2, 90, 22, False)

            # 뒤로가기 버튼
            is_hover_back = (20 <= m_pos[0] <= 340 and 570 <= m_pos[1] <= 610)
            UIComponents.draw_button(self.screen, "🔙 로비로 가기", 20, 570, 320, 40, is_hover_back)

        elif self.game_state == "CASTING":
            self.draw_centered_text("미끼 던지는 중...", self.font_large, (0, 255, 200), 440)
            
        elif self.game_state == "WAITING":
            if not self.bite_triggered:
                self.draw_centered_text("입질 기다리는 중...", self.font_large, (148, 163, 184), 430)
                pulse = 3 + int(math.sin(self.anim_time * 6) * 3)
                pygame.draw.circle(self.screen, (34, 197, 94), (self.screen_width//2, 470), pulse)
            else:
                self.draw_centered_text("BITE!!!", self.font_bite, (239, 68, 68), 440)
                
        elif self.game_state == "FIGHTING":
            # 1. 물고기 체력바
            UIComponents.draw_gauge_bar(
                self.screen,
                20, 350, 320, 10,
                self.engine.current_hp,
                self.engine.max_hp,
                (239, 68, 68),
                label=f"{self.engine.fish_name} HP: {int(self.engine.current_hp)}/{self.engine.max_hp}"
            )

            # 2. 남은 거리 및 시간
            dist_label = self.font_main.render("남은 거리", True, (148, 163, 184))
            self.screen.blit(dist_label, (20, 375))
            dist_str = f"{self.engine.current_distance:.1f} m"
            dist_text = self.font_large.render(dist_str, True, (255, 255, 255))
            self.screen.blit(dist_text, (20, 393))

            time_left = max(0.0, self.engine.time_limit - self.engine.elapsed_time)
            time_color = (34, 197, 94) if time_left > 10 else (239, 68, 68)
            UIComponents.draw_gauge_bar(
                self.screen,
                200, 398, 140, 8,
                time_left,
                self.engine.time_limit,
                time_color,
                label=f"제한 시간: {time_left:.1f}초"
            )

            # 3. 판정/상태 텍스트
            if self.engine.last_judgment:
                j_color = (0, 255, 255)
                if self.engine.last_judgment in ["Special", "Perfect Release", "그린 존 유지 중! 텐션을 지키세요!"]:
                    j_color = (34, 197, 94)
                elif "Rage" in self.engine.last_judgment or "Rampage" in self.engine.last_judgment or "RAGE" in self.engine.last_judgment or "Break" in self.engine.last_judgment:
                    j_color = (239, 68, 68)
                
                judg_text = self.font_judgment.render(self.engine.last_judgment, True, j_color)
                self.screen.blit(judg_text, (self.screen_width // 2 - judg_text.get_width() // 2, 435))

            # 4. Miss 카운터 (페이즈 A용)
            for i in range(self.engine.max_miss_allowed):
                x = 320 - (i * 18)
                y = 310
                color = (239, 68, 68) if i < self.engine.miss_count else (71, 85, 105)
                pygame.draw.line(self.screen, color, (x, y), (x + 8, y + 8), 2)
                pygame.draw.line(self.screen, color, (x + 8, y), (x, y + 8), 2)

            # 5. 페이즈 전개
            if self.engine.current_phase == "A":
                UIComponents.draw_target_ring(
                    self.screen,
                    self.engine.target_x,
                    self.engine.target_y,
                    self.engine.target_radius,
                    self.engine.ring_speed,
                    time.time() - self.engine.target_spawn_time
                )
            elif self.engine.current_phase == "B":
                UIComponents.draw_tension_bar(
                    self.screen,
                    self.screen_width // 2,
                    515,
                    self.engine.tension,
                    self.engine.blue_zone_timer,
                    self.engine.red_zone_timer,
                    self.engine.is_holding,
                    self.engine.is_rage
                )

    def draw_result_popup(self):
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))

        card_w, card_h = 300, 340
        card_x = (self.screen_width - card_w) // 2
        card_y = (self.screen_height - card_h) // 2

        pygame.draw.rect(self.screen, (30, 41, 59), (card_x, card_y, card_w, card_h), border_radius=12)
        success = (self.engine.result_status == "CATCH")
        border_color = (34, 197, 94) if success else (239, 68, 68)
        pygame.draw.rect(self.screen, border_color, (card_x, card_y, card_w, card_h), 3, border_radius=12)

        if success:
            title_text = "물고기 포획 성공!"
            title_color = (34, 197, 94)
            self.draw_centered_text(title_text, self.font_large, title_color, card_y + 40)
            self.draw_centered_text(f"어종: {self.engine.fish_name}", self.font_title, (244, 244, 245), card_y + 100)
            self.draw_centered_text(f"크기: {self.catch_size} cm", self.font_large, (255, 215, 0), card_y + 140)
            
            if self.catch_success_added:
                self.draw_centered_text(f"살림망 보관 완료 (+ {self.catch_gold_reward} G)", self.font_main, (148, 163, 184), card_y + 190)
            else:
                self.draw_centered_text("살림망 부족! 로비에서 전체 판매하세요!", self.font_main, (239, 68, 68), card_y + 190)
            
            self.draw_centered_text(f"가치 환전: {self.catch_gold_reward} G", self.font_title, (34, 211, 238), card_y + 230)
        else:
            title_text = "물고기 포획 실패"
            title_color = (239, 68, 68)
            self.draw_centered_text(title_text, self.font_large, title_color, card_y + 50)
            
            reason_str = "물고기가 도망쳤습니다..."
            if self.engine.fail_reason == "LINE_BREAK":
                reason_str = "⚠️ 과부하로 낚싯줄이 터졌습니다!"
            elif self.engine.fail_reason == "ESCAPE":
                reason_str = "⚠️ 줄이 느슨해져 물고기가 도망쳤습니다!"
            elif self.engine.fail_reason == "TIMEOUT":
                reason_str = "⏱️ 제한 시간이 초과되었습니다!"
            elif self.engine.fail_reason == "MISS_LIMIT":
                reason_str = "❌ 터치 실수 한도를 초과했습니다!"
                
            self.draw_centered_text(reason_str, self.font_title, (244, 244, 245), card_y + 120)
            self.draw_centered_text("밀고 당기는 텐션 타이밍을 조율하세요!", self.font_main, (200, 200, 200), card_y + 170)
            self.draw_centered_text("상점 장비를 강화하여 다시 도전하세요!", self.font_main, (148, 163, 184), card_y + 200)

        self.draw_centered_text("화면을 터치하여 로비로 가기", self.font_title, (0, 255, 200), card_y + 295)

    def draw_centered_text(self, text_str, font, color, y):
        text = font.render(text_str, True, color)
        rect = text.get_rect(center=(self.screen_width // 2, y))
        self.screen.blit(text, rect)

def main():
    app = FishBattleApp()
    app.run()

if __name__ == '__main__':
    main()
