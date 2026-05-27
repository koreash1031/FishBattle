import pygame
import math
import time

class UIComponents:
    @staticmethod
    def draw_gauge_bar(screen, x, y, width, height, value, max_value, color, bg_color=(40, 50, 65), label=""):
        """게이지 바 그리기 (둥근 테두리와 HSL 스타일 효과)"""
        # 배경바
        pygame.draw.rect(screen, bg_color, (x, y, width, height), border_radius=4)
        
        # 채우기
        if max_value > 0:
            fill_width = int(width * (max(0.0, min(1.0, value / max_value))))
            if fill_width > 0:
                pygame.draw.rect(screen, color, (x, y, fill_width, height), border_radius=4)
        
        # 겉 테두리
        pygame.draw.rect(screen, (100, 120, 140), (x, y, width, height), 1, border_radius=4)

        # 라벨 텍스트
        if label:
            font = pygame.font.SysFont("malgungothic", 12)
            text = font.render(label, True, (240, 240, 240))
            screen.blit(text, (x + 5, y - 18))

    @staticmethod
    def draw_target_ring(screen, x, y, base_radius, ring_duration, elapsed_time):
        """페이즈 A 리듬 타겟 링 축소 효과 그리기"""
        # 1. 내부 타겟 중심점 그리기 (Special 판정선)
        pygame.draw.circle(screen, (255, 215, 0), (x, y), base_radius, 2)
        pygame.draw.circle(screen, (255, 215, 0), (x, y), 5)

        # 2. 축소되는 링 반경 계산
        progress = max(0.0, elapsed_time / ring_duration)
        if progress <= 1.0:
            current_radius = base_radius + (base_radius * 2) * (1.0 - progress)
            accuracy_diff = abs(elapsed_time - ring_duration)
            if accuracy_diff < 0.15:
                color = (0, 255, 255)
            else:
                color = (255, 100, 100)
            
            pygame.draw.circle(screen, color, (x, y), int(current_radius), 2)
        else:
            color = (255, 0, 0)
            pygame.draw.circle(screen, color, (x, y), base_radius, 3)

    @staticmethod
    def draw_tension_bar(screen, center_x, center_y, tension, blue_zone_timer, red_zone_timer, is_holding, is_rage):
        """[리뉴얼] 페이즈 B 실시간 텐션 게이지 그리기"""
        bar_w = 300
        bar_h = 16
        bar_x = center_x - bar_w // 2
        bar_y = center_y

        # A. 가이드 텍스트 안내
        font_hint = pygame.font.SysFont("malgungothic", 11)
        font_warn = pygame.font.SysFont("malgungothic", 14, bold=True)
        
        # 기본 조작 안내문구
        guide_str = "화면 터치(Hold): 감기 [텐션▲]  |  떼기(Release): 풀기 [텐션▼]"
        text_guide = font_hint.render(guide_str, True, (156, 163, 175))
        screen.blit(text_guide, (center_x - text_guide.get_width() // 2, bar_y - 48))

        # 물고기 광분(Rage) 상태일 때 게이지 전체 적색 이글거림 효과
        if is_rage:
            pulse = math.sin(time.time() * 25) * 4
            glow_rect = pygame.Rect(bar_x - 4 - int(pulse//2), bar_y - 4 - int(pulse//2), bar_w + 8 + int(pulse), bar_h + 8 + int(pulse))
            pygame.draw.rect(screen, (239, 68, 68), glow_rect, 0, border_radius=6)
            
            rage_text = font_warn.render("★ 물고기 발악 중! (Rage) 텐션 급증! ★", True, (255, 255, 255))
            screen.blit(rage_text, (center_x - rage_text.get_width() // 2, bar_y - 25))
        else:
            # 경고 메시지 출력 (위험 구간)
            if tension < 35.0:
                # 블루 존 경고
                esc_sec_left = max(0.0, 3.0 - blue_zone_timer)
                esc_text = font_warn.render(f"⚠️ 느슨함! 릴을 감으세요! ({esc_sec_left:.1f}초 전)", True, (59, 130, 246))
                screen.blit(esc_text, (center_x - esc_text.get_width() // 2, bar_y - 25))
            elif tension >= 80.0:
                # 레드 존 경고
                brk_sec_left = max(0.0, 0.7 - red_zone_timer)
                brk_color = (255, 255, 255) if int(time.time() * 10) % 2 == 0 else (239, 68, 68)
                brk_text = font_warn.render(f"⚠️ 과부하! 손을 떼세요! ({brk_sec_left:.1f}초 전)", True, brk_color)
                screen.blit(brk_text, (center_x - brk_text.get_width() // 2, bar_y - 25))
            else:
                # 그린 존 최적 상태
                ok_text = font_warn.render("그린 존 유지 중! 텐션을 지키세요!", True, (34, 197, 94))
                screen.blit(ok_text, (center_x - ok_text.get_width() // 2, bar_y - 25))

        # B. 텐션 게이지 영역 색칠 (블루 -> 그린 -> 레드)
        # 배경 슬롯
        pygame.draw.rect(screen, (30, 41, 59), (bar_x, bar_y, bar_w, bar_h), border_radius=4)
        
        # 블루 존 (0% ~ 35%): 파랑
        blue_w = int(bar_w * 0.35)
        pygame.draw.rect(screen, (59, 130, 246), (bar_x, bar_y, blue_w, bar_h), border_top_left_radius=4, border_bottom_left_radius=4)

        # 그린 존 (36% ~ 80%): 녹색
        green_w = int(bar_w * 0.45)
        pygame.draw.rect(screen, (34, 197, 94), (bar_x + blue_w, bar_y, green_w, bar_h))

        # 레드 존 (81% ~ 100%): 빨강
        red_w = bar_w - blue_w - green_w
        pygame.draw.rect(screen, (239, 68, 68), (bar_x + blue_w + green_w, bar_y, red_w, bar_h), border_top_right_radius=4, border_bottom_right_radius=4)

        # 각 파트 경계선
        pygame.draw.line(screen, (15, 23, 42), (bar_x + blue_w, bar_y), (bar_x + blue_w, bar_y + bar_h), 2)
        pygame.draw.line(screen, (15, 23, 42), (bar_x + blue_w + green_w, bar_y), (bar_x + blue_w + green_w, bar_y + bar_h), 2)

        # 전체 바깥 아웃라인
        pygame.draw.rect(screen, (148, 163, 184), (bar_x, bar_y, bar_w, bar_h), 2, border_radius=4)

        # C. 지시 바늘 (Indicator) 그리기
        # tension 백분율 값에 대응하는 x 좌표 계산
        indicator_x = bar_x + int(bar_w * (tension / 100.0))
        
        # 아래쪽을 향하는 흰색 삼각형 침 그리기
        pygame.draw.polygon(screen, (255, 255, 255), [
            (indicator_x, bar_y - 2),
            (indicator_x - 6, bar_y - 10),
            (indicator_x + 6, bar_y - 10)
        ])
        
        # 수직 빨간 선
        pygame.draw.line(screen, (255, 255, 255), (indicator_x, bar_y), (indicator_x, bar_y + bar_h), 2)
        
        # 게이지 위 바늘 테두리
        pygame.draw.polygon(screen, (15, 23, 42), [
            (indicator_x, bar_y - 2),
            (indicator_x - 6, bar_y - 10),
            (indicator_x + 6, bar_y - 10)
        ], 1)
        
        # 텐션 백분율 텍스트
        text_pct = font_hint.render(f"{int(tension)}%", True, (244, 244, 245))
        screen.blit(text_pct, (indicator_x - text_pct.get_width() // 2, bar_y - 23))

    @staticmethod
    def draw_button(screen, text_str, x, y, width, height, is_hovered, bg_color=(30, 41, 59), hover_color=(51, 65, 85), border_color=(100, 120, 140), text_color=(244, 244, 245)):
        """둥근 사각형 버튼 렌더링"""
        color = hover_color if is_hovered else bg_color
        pygame.draw.rect(screen, color, (x, y, width, height), border_radius=6)
        pygame.draw.rect(screen, border_color, (x, y, width, height), 1, border_radius=6)
        
        # 폰트 로딩 폴백 처리
        try:
            font = pygame.font.SysFont("malgungothic", 12, bold=True)
        except Exception:
            font = pygame.font.SysFont(None, 14, bold=True)
            
        text = font.render(text_str, True, text_color)
        text_rect = text.get_rect(center=(x + width // 2, y + height // 2))
        screen.blit(text, text_rect)
