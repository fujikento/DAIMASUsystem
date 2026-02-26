"""
TouchDesigner トランジションエンジン

映像切替時のエフェクト制御
TouchDesigner内のSwitch TOPやComposite TOPと連携
"""

# 利用可能なトランジションタイプ
TRANSITIONS = {
    'cut': {
        'description': '即切替（カット）',
        'default_duration': 0.0,
    },
    'crossfade': {
        'description': 'クロスフェード',
        'default_duration': 1.5,
    },
    'fade_in': {
        'description': '黒からフェードイン',
        'default_duration': 2.0,
    },
    'fade_out': {
        'description': '黒へフェードアウト',
        'default_duration': 2.0,
    },
    'wave': {
        'description': '波紋エフェクト（海テーマ用）',
        'default_duration': 2.5,
    },
    'fire': {
        'description': '炎エフェクト（火テーマ用）',
        'default_duration': 2.0,
    },
    'particles': {
        'description': 'パーティクル散布',
        'default_duration': 3.0,
    },
    'bubble': {
        'description': '泡エフェクト',
        'default_duration': 2.5,
    },
    'sakura': {
        'description': '桜吹雪（和テーマ用）',
        'default_duration': 3.0,
    },
    'sparkle': {
        'description': 'キラキラエフェクト（宝テーマ用）',
        'default_duration': 2.0,
    },
    'stars': {
        'description': '星雲ワイプ（宇宙テーマ用）',
        'default_duration': 3.0,
    },
    'page_turn': {
        'description': 'ページめくり（物語テーマ用）',
        'default_duration': 2.0,
    },
    'forest_grow': {
        'description': '蔦が伸びる（森テーマ用）',
        'default_duration': 3.0,
    },
}

# 曜日テーマに適したデフォルトトランジション
THEME_TRANSITIONS = {
    'monday': ['sakura', 'fade_in', 'crossfade'],      # 和
    'tuesday': ['fire', 'crossfade', 'fade_in'],        # 火
    'wednesday': ['wave', 'bubble', 'crossfade'],        # 海
    'thursday': ['forest_grow', 'crossfade', 'fade_in'], # 森
    'friday': ['sparkle', 'particles', 'crossfade'],     # 宝
    'saturday': ['stars', 'particles', 'crossfade'],     # 宇宙
    'sunday': ['page_turn', 'crossfade', 'fade_in'],     # 物語
}


class TransitionController:
    """トランジション制御クラス"""

    def __init__(self):
        self._current_transition = None
        self._is_transitioning = False
        self._progress = 0.0

    def start_transition(self, transition_type='crossfade', duration=None):
        """
        トランジション開始

        Args:
            transition_type: トランジションタイプ名
            duration: 秒数（Noneの場合はデフォルト値）
        """
        if transition_type not in TRANSITIONS:
            print(f"[Transition] Unknown type: {transition_type}, falling back to crossfade")
            transition_type = 'crossfade'

        config = TRANSITIONS[transition_type]
        actual_duration = duration if duration is not None else config['default_duration']

        self._current_transition = transition_type
        self._is_transitioning = True
        self._progress = 0.0

        print(f"[Transition] Starting: {transition_type} ({config['description']}) - {actual_duration}s")

        # TouchDesigner内での実行:
        # switch_top = op('transition_switch')
        # blend_chop = op('transition_blend')
        #
        # if transition_type == 'crossfade':
        #     blend_chop.par.length = actual_duration * project.cookRate
        #     blend_chop.par.cuepulse.pulse()
        #
        # elif transition_type == 'wave':
        #     op('wave_effect').par.active = True
        #     op('wave_effect').par.duration = actual_duration
        #     op('wave_effect').par.trigger.pulse()
        #
        # elif transition_type == 'fire':
        #     op('fire_effect').par.active = True
        #     op('fire_effect').par.duration = actual_duration
        #     op('fire_effect').par.trigger.pulse()

        return actual_duration

    def update(self, progress):
        """トランジション進行度更新（0.0〜1.0）"""
        self._progress = progress
        if progress >= 1.0:
            self._is_transitioning = False
            self._current_transition = None

    @property
    def is_transitioning(self):
        return self._is_transitioning

    @property
    def current_type(self):
        return self._current_transition

    def get_recommended_transitions(self, day_of_week):
        """曜日に応じた推奨トランジションリストを返す"""
        return THEME_TRANSITIONS.get(day_of_week, ['crossfade', 'fade_in'])


# ====================================================================
# スタンドアロンテスト
# ====================================================================
if __name__ == '__main__':
    controller = TransitionController()

    print("=== Available Transitions ===")
    for name, config in TRANSITIONS.items():
        print(f"  {name}: {config['description']} ({config['default_duration']}s)")

    print("\n=== Theme Recommendations ===")
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    for day in days:
        recommended = controller.get_recommended_transitions(day)
        print(f"  {day}: {', '.join(recommended)}")

    print("\n=== Transition Test ===")
    duration = controller.start_transition('wave', 2.5)
    print(f"  Duration: {duration}s")
    print(f"  Is transitioning: {controller.is_transitioning}")
    controller.update(1.0)
    print(f"  After complete: {controller.is_transitioning}")
