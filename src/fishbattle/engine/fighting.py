import random
import time

class FightingEngine:
    def __init__(self, fish_data, equipment_stats):
        """
        fish_data: dict, 물고기 정보
        equipment_stats: dict, 장비 성능
        """
        self.fish_data = fish_data
        self.equipment_stats = equipment_stats

        # 물고기 기본 스펙 로드
        self.fish_name = fish_data.get("name", "피라미")
        self.max_hp = fish_data.get("hp", 100)
        self.current_hp = self.max_hp

        # 시작 거리 랜덤 결정 [Min ~ Max]
        min_dist = fish_data.get("min_dist", 10)
        max_dist = fish_data.get("max_dist", 20)
        self.start_distance = random.uniform(min_dist, max_dist)
        self.current_distance = self.start_distance

        # 파이팅 제한 시간 (30초 + 낚싯줄 보너스)
        self.time_limit = 30.0 + equipment_stats.get("time_bonus", 0.0)
        self.start_time = time.time()
        self.elapsed_time = 0.0

        # 판정 상태
        self.size_score = 0
        self.max_size_score = 0
        self.miss_count = 0
        self.max_miss_allowed = 5

        # 상태 제어
        self.current_phase = "A"  # "A" (리듬), "B" (텐션 파이팅), "CATCH", "FAIL"
        self.game_over = False
        self.result_status = None # "CATCH", "FAIL"
        self.fail_reason = ""     # "TIMEOUT", "MISS_LIMIT", "LINE_BREAK" (줄끊어짐), "ESCAPE" (바늘털이)

        # 페이즈 A (리듬) 세부 설정
        self.ring_speed = fish_data.get("ring_speed", 1.5)
        self.target_radius_base = fish_data.get("target_radius", 40)
        self.target_radius = self.target_radius_base + equipment_stats.get("target_radius_bonus", 0)
        
        self.rhythm_count = 0
        self.max_rhythm_rounds = 3
        self.target_x = 0
        self.target_y = 0
        self.target_spawn_time = 0.0
        self.target_active = False
        self.last_judgment = ""

        # [리뉴얼] 페이즈 B (텐션 홀드 & 릴리즈) 세부 설정
        self.tension = 0.0  # 현재 낚싯줄 텐션 게이지 (0.0 ~ 100.0)
        self.is_holding = False  # 플레이어가 릴을 감는 탭 홀드 중인지 여부
        
        # 텐션 물리 수치 (물고기 등급별 스케일링)
        self.rarity = fish_data.get("rarity", "common")
        
        # 기본 텐션 상승/하락 속도 (초당 게이지 증가/감소 수치)
        if self.rarity == "legendary":
            self.tension_rise_rate = 65.0  # 전설 물고기는 텐션이 극도로 빠르게 상승
            self.tension_fall_rate = 55.0
            self.fish_escape_speed = 2.0   # 손을 떼었을 때 도망가는 속도 (m/s)
        elif self.rarity == "rare":
            self.tension_rise_rate = 50.0
            self.tension_fall_rate = 50.0
            self.fish_escape_speed = 1.2
        else:
            self.tension_rise_rate = 40.0
            self.tension_fall_rate = 45.0
            self.fish_escape_speed = 0.8

        # 위험 구간 누적 타이머
        self.blue_zone_timer = 0.0  # 3.0초 한도
        self.red_zone_timer = 0.0   # 0.7초 한도
        
        # 페이즈 B 총 진행 시간 제어 (예: 8초 동안 밀당 후 다시 페이즈 A 리듬으로 복귀)
        self.phase_b_duration = 8.0
        self.phase_b_start_time = 0.0
        self.phase_b_elapsed = 0.0

        # 물고기 광분(Rage) 상태 제어 (페이즈 B 중 무작위 발생)
        self.is_rage = False
        self.rage_start_time = 0.0
        self.rage_duration = 0.0

        self.start_phase_a()

    def update(self):
        if self.game_over:
            return

        self.elapsed_time = time.time() - self.start_time
        
        # 1. 제한 시간 초과 체크
        if self.elapsed_time >= self.time_limit:
            self.trigger_fail("TIMEOUT")
            return

        # 2. 누적 Miss 한도 초과 체크 (페이즈 A용)
        if self.miss_count >= self.max_miss_allowed:
            self.trigger_fail("MISS_LIMIT")
            return

        # 3. 거리 0m 도달 체크 (포획 성공)
        if self.current_distance <= 0:
            self.trigger_catch()
            return

        # 페이즈별 업데이트
        if self.current_phase == "A":
            self.update_phase_a()
        elif self.current_phase == "B":
            self.update_phase_b()

    # ==========================================
    # PHASE A: 리듬 타겟 로직
    # ==========================================
    def start_phase_a(self):
        self.current_phase = "A"
        self.rhythm_count = 0
        self.spawn_rhythm_target()

    def spawn_rhythm_target(self):
        # 하단 53% 구역 (y: 440 ~ 580, x: 60 ~ 300) 내 무작위 생성
        self.target_x = random.randint(60, 300)
        self.target_y = random.randint(440, 580)
        self.target_spawn_time = time.time()
        self.target_active = True
        self.max_size_score += 5

    def update_phase_a(self):
        if not self.target_active:
            return

        target_elapsed = time.time() - self.target_spawn_time
        if target_elapsed > self.ring_speed + 0.3:
            self.handle_rhythm_input(None)

    def handle_rhythm_input(self, input_time):
        if not self.target_active:
            return

        self.target_active = False

        if input_time is None:
            self.last_judgment = "Miss"
            self.size_score -= 3
            self.miss_count += 1
            self.apply_miss_penalty()
        else:
            elapsed = input_time - self.target_spawn_time
            diff = abs(elapsed - self.ring_speed)

            if diff <= 0.05:
                self.last_judgment = "Special"
                damage_factor = 1.0
                self.size_score += 5
            elif diff <= 0.15:
                self.last_judgment = "Very Good"
                damage_factor = 0.75
                self.size_score += 2
            elif diff <= 0.30:
                self.last_judgment = "Good"
                damage_factor = 0.50
            else:
                self.last_judgment = "Miss"
                damage_factor = 0.0
                self.size_score -= 3
                self.miss_count += 1
                self.apply_miss_penalty()

            # 데미지 적용
            if damage_factor > 0:
                base_damage = 25.0
                damage = base_damage * damage_factor * self.equipment_stats.get("damage_mult", 1.0)
                self.current_hp -= damage
                if self.current_hp < 0:
                    self.current_hp = 0

        self.rhythm_count += 1
        if self.rhythm_count >= self.max_rhythm_rounds:
            # 리듬 라운드 종료 시 파이팅 텐션 배틀로 전이
            self.start_phase_b()
        else:
            self.spawn_rhythm_target()

    def apply_miss_penalty(self):
        penalty = 5.0 if self.rarity == "legendary" else 3.0
        self.current_distance += penalty
        if self.current_distance > self.start_distance * 1.5:
            self.current_distance = self.start_distance * 1.5

    # ==========================================
    # [리뉴얼] PHASE B: 텐션 홀드 & 릴리즈 로직
    # ==========================================
    def start_phase_b(self):
        self.current_phase = "B"
        self.is_holding = False
        
        # 텐션 초기화 (그린 존 초입인 40%로 세팅하여 중간 줄타기 시작 유도)
        self.tension = 40.0
        self.blue_zone_timer = 0.0
        self.red_zone_timer = 0.0
        
        self.phase_b_start_time = time.time()
        self.phase_b_elapsed = 0.0
        
        self.is_rage = False
        self.last_judgment = "TENSION BATTLE!"

    def start_hold(self):
        """플레이어가 하단 영역을 누르고 있을 때 호출"""
        self.is_holding = True

    def release_hold(self):
        """플레이어가 터치를 뗐을 때 호출"""
        self.is_holding = False

    def update_phase_b(self):
        dt = 1.0 / 60.0  # 프레임 델타
        self.phase_b_elapsed = time.time() - self.phase_b_start_time

        # 1. 8초 밀당 제한시간 초과 시, 다시 1단계 리듬 터치로 물고기가 발악하며 도망침
        if self.phase_b_elapsed >= self.phase_b_duration:
            self.last_judgment = "물고기 요동침!"
            self.current_distance += 3.0  # 교체 충격으로 인한 거리 벌어짐
            self.start_phase_a()
            return

        # 2. 물고기 광분(Rage) 패턴 무작위 제어
        if not self.is_rage:
            # 1.5% 확률로 광분 돌입
            if random.random() < 0.008:
                self.is_rage = True
                self.rage_start_time = time.time()
                self.rage_duration = random.uniform(1.2, 2.2) # 1.2초 ~ 2.2초 동안 광분
                self.last_judgment = "물고기 발악! (Rage)"
        else:
            if time.time() - self.rage_start_time >= self.rage_duration:
                self.is_rage = False
                self.last_judgment = "진정됨"

        # 3. 실시간 텐션 게이지 연산
        if self.is_holding:
            # 릴 감기: 텐션 상승
            rise_multiplier = 1.8 if self.is_rage else 1.0
            self.tension += self.tension_rise_rate * rise_multiplier * dt
            
            # 거리 감소 연산 (그린 존일 때 100% 효율, 레드 존은 끊어질 스릴로 인해 70% 효율, 블루 존은 느슨해서 10% 효율)
            reeling_power = self.equipment_stats.get("reeling_power", 5.0)
            hp_factor = 1.5 - (self.current_hp / self.max_hp)  # 물고기 체력 비례 (0.5 ~ 1.5)
            
            if 36.0 <= self.tension <= 80.0:
                eff = 1.0  # 그린 존
            elif self.tension > 80.0:
                eff = 0.7  # 레드 존 (아슬아슬하게 감음)
            else:
                eff = 0.1  # 블루 존 (너무 느슨함)
                
            self.current_distance -= reeling_power * hp_factor * eff * dt
            if self.current_distance < 0:
                self.current_distance = 0
        else:
            # 릴 풀기: 텐션 하락
            fall_multiplier = 0.6 if self.is_rage else 1.0 # 광분 중엔 줄을 풀어도 텐션이 잘 안 내려감
            self.tension -= self.tension_fall_rate * fall_multiplier * dt
            
            # 줄을 풀어두면 물고기가 도망침 (거리 증가)
            self.current_distance += self.fish_escape_speed * dt
            if self.current_distance > self.start_distance * 1.5:
                self.current_distance = self.start_distance * 1.5

        # 텐션 범위 클램프
        self.tension = max(0.0, min(100.0, self.tension))

        # 4. 위험 게이지 타이머 체크 및 실패 판정
        # (A) 블루 존 (0% ~ 35%) : 바늘털이
        if self.tension < 35.0:
            self.blue_zone_timer += dt
            if self.blue_zone_timer >= 3.0:
                self.trigger_fail("ESCAPE")
                return
        else:
            self.blue_zone_timer = 0.0

        # (B) 레드 존 (81% ~ 100%) : 라인 브레이크
        if self.tension >= 100.0:
            self.red_zone_timer += dt
            if self.red_zone_timer >= 0.7:  # 0.7초의 유예 시간 초과
                self.trigger_fail("LINE_BREAK")
                return
        else:
            self.red_zone_timer = 0.0

    # ==========================================
    # 종료 처리
    # ==========================================
    def trigger_catch(self):
        self.game_over = True
        self.result_status = "CATCH"
        self.current_phase = "CATCH"

    def trigger_fail(self, reason):
        self.game_over = True
        self.result_status = "FAIL"
        self.current_phase = "FAIL"
        self.fail_reason = reason

    def get_final_fish_size(self):
        min_size = self.fish_data.get("min_size", 5.0)
        max_size = self.fish_data.get("max_size", 15.0)
        
        if self.max_size_score <= 0:
            score_ratio = 0.5
        else:
            score_ratio = max(0.0, min(1.0, self.size_score / self.max_size_score))

        final_size = min_size + (max_size - min_size) * score_ratio
        return round(final_size, 1)
