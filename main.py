# game.py — MVP: 스테이지/이벤트/체력/타이머/추가이벤트(Freeze/즉시실패)
import random, time
import pyglet
from pyglet.window import key, mouse
from pyglet import shapes

# ----------------------- 게임 규칙 상수 -----------------------
MAX_HEALTH     = 4
START_HEALTH   = 3
BASE_TIME      = 10.0       # 첫 스테이지 이벤트 제한시간(초)
TIME_DEC_STEP  = 0.7        # 스테이지가 진행될수록 이벤트 제한시간 감소량
MIN_TIME       = 4.0
EVENTS_PER_STAGE = 3
FREEZE_EXTRA_PROB = 0.12     # 이벤트 중 추가이벤트(Freeze) 발동 확률
SUDDEN_FAIL_PROB  = 0.08     # 이벤트 즉시실패 확률

# ----------------------- 유틸 -----------------------
def clamp(x, lo, hi): return max(lo, min(hi, x))

# ----------------------- 이벤트 베이스 -----------------------
class BaseEvent:
    """모든 이벤트의 공통 인터페이스"""
    name = "BaseEvent"
    def __init__(self, game, time_limit: float):
        self.game = game
        self.time_limit = time_limit
        self.t = 0.0
        self.success = False
        self.failed = False
        self.extra_freeze_until = 0.0  # n초 동안 입력/이동 금지
        self.batch = pyglet.graphics.Batch()  # 자식 렌더링
        self.hint_label = pyglet.text.Label(
            "", x=20, y=game.h-40, anchor_x='left', anchor_y='center',
            font_size=14, color=(240,240,240,255), batch=self.batch
        )

    # 공통 루프
    def update(self, dt: float):
        self.t += dt
        # 추가 이벤트: Freeze
        if (not self.success and not self.failed and
            random.random() < FREEZE_EXTRA_PROB*dt and self.extra_freeze_until < self.t):
            freeze_sec = random.choice([1.5, 2.0, 2.5])
            self.extra_freeze_until = self.t + freeze_sec
            self.game.push_toast(f"추가이벤트: {freeze_sec:.1f}s 동결!")
        # 추가 이벤트: 즉시 실패
        if (not self.success and not self.failed and random.random() < SUDDEN_FAIL_PROB*dt):
            self.fail(reason="추가이벤트: 즉시 실패!")

        if self.t >= self.time_limit and not (self.success or self.failed):
            self.fail(reason="시간초과")

    def is_frozen(self) -> bool:
        return self.t < self.extra_freeze_until

    def on_key_press(self, symbol, modifiers): pass
    def on_mouse_press(self, x, y, button, modifiers): pass
    def on_mouse_motion(self, x, y, dx, dy): pass
    def draw(self): self.batch.draw()

    def succeed(self):
        if not (self.success or self.failed):
            self.success = True
            self.game.push_toast("성공!")

    def fail(self, reason="실패"):
        if not (self.success or self.failed):
            self.failed = True
            self.game.push_toast(reason)

    def cleanup(self): pass  # 리소스 정리 시 훅

    def time_left(self) -> float:
        return clamp(self.time_limit - self.t, 0.0, 999.0)

# ----------------------- 간단 이벤트 1: 도달 -----------------------
class ReachZoneEvent(BaseEvent):
    name = "목표 지점 도달"
    def __init__(self, game, time_limit: float):
        super().__init__(game, time_limit)
        self.player = shapes.Rectangle(80, 100, 40, 40, color=(60, 200, 255), batch=self.batch)
        gx = random.randint(300, game.w-120)
        gy = random.randint(120, game.h-160)
        self.goal = shapes.Rectangle(gx, gy, 60, 60, color=(60, 255, 120), batch=self.batch)
        self.hint_label.text = "← → 로 이동해 초록색 영역에 들어가세요."
        self.vx = 0.0

    def update(self, dt):
        super().update(dt)
        # 입력 동결 상태면 이동X
        if self.is_frozen(): return
        # 이동
        self.player.x += self.vx * dt
        self.player.x = clamp(self.player.x, 0, self.game.w - self.player.width)
        # 충돌 체크
        if self._intersects(self.player, self.goal):
            self.succeed()

    def on_key_press(self, symbol, modifiers):
        if self.is_frozen(): return
        if symbol == key.LEFT:  self.vx = -260
        if symbol == key.RIGHT: self.vx =  260

    def on_key_release(self, symbol, modifiers):
        if symbol in (key.LEFT, key.RIGHT): self.vx = 0.0

    def _intersects(self, a, b):
        return not (a.x+a.width < b.x or b.x+b.width < a.x or
                    a.y+a.height < b.y or b.y+b.height < a.y)

# ----------------------- 간단 이벤트 2: 키 탭 -----------------------
class KeyTapEvent(BaseEvent):
    name = "키 입력"
    KEYS = [key.A, key.S, key.D, key.J, key.K, key.L]

    def __init__(self, game, time_limit: float):
        super().__init__(game, time_limit)
        self.target = random.choice(self.KEYS)
        name = pyglet.window.key.symbol_string(self.target)
        self.hint_label.text = f"제한시간 내에 '{name}' 키를 누르세요!"
        self.box = shapes.Rectangle(game.w//2-80, game.h//2-50, 160, 100, color=(255,180,60), batch=self.batch)
        self.key_label = pyglet.text.Label(name, x=game.w//2, y=game.h//2,
                                           anchor_x='center', anchor_y='center',
                                           font_size=28, color=(20,20,20,255), batch=self.batch)

    def on_key_press(self, symbol, modifiers):
        if self.is_frozen(): return
        if symbol == self.target:
            self.succeed()
        else:
            # 잘못된 키 여러 번 입력하면 위험
            if random.random() < 0.25:
                self.fail("오입력!")

# ----------------------- 간단 이벤트 3: 클릭 -----------------------
class ClickTargetEvent(BaseEvent):
    name = "표적 클릭"
    def __init__(self, game, time_limit: float):
        super().__init__(game, time_limit)
        cx = random.randint(120, game.w-120)
        cy = random.randint(160, game.h-160)
        self.target = shapes.Circle(cx, cy, radius=30, color=(255,80,120), batch=self.batch)
        self.hint_label.text = "빨간 원을 클릭하세요!"

    def on_mouse_press(self, x, y, button, modifiers):
        if self.is_frozen(): return
        if button == mouse.LEFT:
            dx, dy = x - self.target.x, y - self.target.y
            if dx*dx + dy*dy <= self.target.radius**2:
                self.succeed()
            else:
                if random.random() < 0.20:
                    self.fail("엉뚱한 곳 클릭!")

# ----------------------- 스테이지/게임 매니저 -----------------------
class StageManager:
    def __init__(self):
        self.stage_idx = 1
        self.events_done = 0

    def current_time_limit(self):
        t = BASE_TIME - (self.stage_idx-1)*TIME_DEC_STEP
        return max(MIN_TIME, t)

    def next_event(self, game):
        # 이벤트 순환/랜덤
        evt_cls = random.choice([ReachZoneEvent, KeyTapEvent, ClickTargetEvent])
        return evt_cls(game, self.current_time_limit())

    def stage_advance(self):
        self.stage_idx += 1
        self.events_done = 0

# ----------------------- 메인 게임 앱 -----------------------
class GameApp(pyglet.window.Window):
    def __init__(self, w=960, h=600):
        super().__init__(w, h, "Stage/Event Game (MVP)", resizable=False)
        self.w, self.h = w, h
        self.health = START_HEALTH
        self.stage = StageManager()
        self.current_event = None
        self.ui_batch = pyglet.graphics.Batch()
        self.toast = ""
        self.toast_until = 0.0

        self.lbl_stage = pyglet.text.Label("", x=20, y=h-20, anchor_x='left', anchor_y='center',
                                           font_size=14, color=(230,230,230,255), batch=self.ui_batch)
        self.lbl_timer = pyglet.text.Label("", x=w-20, y=h-20, anchor_x='right', anchor_y='center',
                                           font_size=14, color=(230,230,230,255), batch=self.ui_batch)
        self.health_hearts = []
        self.timer_bar_bg = shapes.Rectangle(20, h-55, w-40, 10, color=(60,60,80), batch=self.ui_batch)
        self.timer_bar_fg = shapes.Rectangle(20, h-55, 0, 10, color=(120,220,120), batch=self.ui_batch)

        self.toast_label = pyglet.text.Label("", x=w//2, y=h-90, anchor_x='center', anchor_y='center',
                                             font_size=16, color=(255,220,120,255), batch=self.ui_batch)
        self.gameover = False
        self.victory = False

        self._update_hearts()
        self.load_next_event()

        pyglet.clock.schedule_interval(self.update, 1/60)

    # ------------- 토스트/헬스/타이머 UI -------------
    def push_toast(self, msg, sec=1.2):
        self.toast = msg
        self.toast_until = time.time() + sec

    def _update_hearts(self):
        for s in self.health_hearts: s.delete()
        self.health_hearts.clear()
        for i in range(MAX_HEALTH):
            col = (220,60,60) if i < self.health else (90,90,90)
            r = shapes.Rectangle(20 + i*28, self.h-85, 22, 22, color=col, batch=self.ui_batch)
            self.health_hearts.append(r)

    def load_next_event(self):
        if self.health <= 0:
            self.gameover = True
            return
        if self.stage.events_done >= EVENTS_PER_STAGE:
            # 스테이지 클리어
            self.stage.stage_advance()
            self.push_toast(f"스테이지 {self.stage.stage_idx-1} 클리어!", sec=1.2)

        # 다음 이벤트 생성
        if not self.gameover:
            if self.current_event: self.current_event.cleanup()
            self.current_event = self.stage.next_event(self)
            self.stage.events_done = 0 if self.current_event and self.stage.events_done >= EVENTS_PER_STAGE else self.stage.events_done

    # ------------- 메인 업데이트 루프 -------------
    def update(self, dt):
        if self.gameover:
            return

        ev = self.current_event
        if ev:
            ev.update(dt)
            # 타이머 바/라벨
            t_left = ev.time_left()
            t_tot  = ev.time_limit
            ratio  = 0 if t_tot <= 0 else t_left / t_tot
            self.timer_bar_fg.width = int((self.w-40) * ratio)
            self.lbl_timer.text = f"{t_left:0.1f}s"
            self.lbl_stage.text = f"Stage {self.stage.stage_idx} — {ev.name}  ({self.stage.events_done+1}/{EVENTS_PER_STAGE})"

            # 이벤트 종료 처리
            if ev.success or ev.failed:
                if ev.success:
                    self.stage.events_done += 1
                else:
                    self.health = max(0, self.health - 1)
                    self._update_hearts()

                # 스테이지 내 다음 이벤트 or 다음 스테이지
                if self.health <= 0:
                    self.gameover = True
                elif self.stage.events_done >= EVENTS_PER_STAGE:
                    self.stage.stage_advance()
                    self.push_toast(f"스테이지 {self.stage.stage_idx-1} 클리어!", sec=1.2)
                # 새 이벤트 로드
                self.current_event.cleanup()
                self.current_event = self.stage.next_event(self)

        # 토스트 표시 시간
        self.toast_label.text = self.toast if time.time() < self.toast_until else ""

    # ------------- 입력 전달 -------------
    def on_key_press(self, symbol, modifiers):
        if self.gameover: 
            if symbol == key.R: self.reset()
            return
        if hasattr(self.current_event, "on_key_press"):
            self.current_event.on_key_press(symbol, modifiers)

    def on_key_release(self, symbol, modifiers):
        if self.gameover: return
        if hasattr(self.current_event, "on_key_release"):
            self.current_event.on_key_release(symbol, modifiers)

    def on_mouse_press(self, x, y, button, modifiers):
        if self.gameover: return
        if hasattr(self.current_event, "on_mouse_press"):
            self.current_event.on_mouse_press(x, y, button, modifiers)

    def on_mouse_motion(self, x, y, dx, dy):
        if self.gameover: return
        if hasattr(self.current_event, "on_mouse_motion"):
            self.current_event.on_mouse_motion(x, y, dx, dy)

    # ------------- 렌더링 -------------
    def on_draw(self):
        self.clear()
        # 배경
        shapes.Rectangle(0,0,self.w,self.h, color=(20,22,30)).draw()

        if self.gameover:
            pyglet.text.Label("GAME OVER",
                              x=self.w//2, y=self.h//2+20, anchor_x='center', anchor_y='center',
                              font_size=36, bold=True, color=(255,90,90,255)).draw()
            pyglet.text.Label("R 키로 재시작",
                              x=self.w//2, y=self.h//2-20, anchor_x='center', anchor_y='center',
                              font_size=16, color=(230,230,230,255)).draw()
            self.ui_batch.draw()
            return

        # 이벤트 씬
        if self.current_event:
            self.current_event.draw()

        # UI
        self.ui_batch.draw()

    def reset(self):
        self.health = START_HEALTH
        self.stage = StageManager()
        self._update_hearts()
        self.gameover = False
        self.current_event = None
        self.load_next_event()

# ----------------------- 실행 -----------------------
if __name__ == "__main__":
    win = GameApp(960, 600)
    pyglet.app.run()
