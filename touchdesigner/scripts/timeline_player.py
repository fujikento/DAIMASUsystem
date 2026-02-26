"""
TouchDesigner タイムライン再生制御スクリプト

タイムラインデータ（JSON）を読み込み、時間に応じてコンテンツを切り替える
TouchDesigner内のTimer CHOPと連携して動作
"""

import json
from pathlib import Path

# タイムラインデータキャッシュ
_current_timeline = None
_current_items = []
_playback_state = 'stopped'  # stopped, playing, paused
_elapsed_time = 0.0


def load_timeline(timeline_json_path):
    """タイムラインJSONファイルを読み込み"""
    global _current_timeline, _current_items

    path = Path(timeline_json_path)
    if not path.exists():
        print(f"[Timeline] File not found: {timeline_json_path}")
        return False

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    _current_timeline = data.get('timeline', {})
    _current_items = sorted(
        data.get('items', []),
        key=lambda x: x.get('start_time', 0)
    )

    print(f"[Timeline] Loaded: {_current_timeline.get('name', 'Unknown')}")
    print(f"[Timeline] Items: {len(_current_items)}")
    return True


def get_active_item(elapsed_seconds):
    """
    経過時間に基づいて現在アクティブなアイテムを返す

    Args:
        elapsed_seconds: 再生開始からの経過秒数

    Returns:
        dict: アクティブなアイテムデータ or None
    """
    for item in reversed(_current_items):
        start = item.get('start_time', 0)
        duration = item.get('duration', 0)
        if start <= elapsed_seconds < start + duration:
            return item
    return None


def get_next_item(elapsed_seconds):
    """次に再生されるアイテムを返す"""
    for item in _current_items:
        if item.get('start_time', 0) > elapsed_seconds:
            return item
    return None


def on_timer_update(elapsed_seconds):
    """
    Timer CHOPからのコールバック（毎フレーム呼ばれる）

    TouchDesigner内では以下のように接続:
    Timer CHOP → Script CHOP (this script)
    """
    global _elapsed_time
    _elapsed_time = elapsed_seconds

    if _playback_state != 'playing':
        return

    current = get_active_item(elapsed_seconds)
    if current is None:
        return

    # コンテンツの切り替えが必要か判定
    # op('content_loader')の現在のファイルと比較
    content_path = current.get('content_file_path', '')
    zone = current.get('zone', 'all')
    transition = current.get('transition', 'crossfade')

    # TouchDesigner内での実行:
    # current_file = op('content_loader').par.file.eval()
    # if current_file != content_path:
    #     # トランジション付きで切り替え
    #     op('transition_engine').par.type = transition
    #     op('transition_engine').par.trigger.pulse()
    #     op('content_loader').par.file = content_path
    #     op('zone_selector').par.activeZone = zone

    print(f"[Timeline] t={elapsed_seconds:.1f}s - Playing: {content_path} (Zone: {zone})")


def get_total_duration():
    """タイムライン全体の長さを返す"""
    if not _current_items:
        return 0
    last = _current_items[-1]
    return last.get('start_time', 0) + last.get('duration', 0)


def get_progress():
    """再生進捗（0.0〜1.0）を返す"""
    total = get_total_duration()
    if total <= 0:
        return 0.0
    return min(_elapsed_time / total, 1.0)


# ====================================================================
# スタンドアロンテスト
# ====================================================================
if __name__ == '__main__':
    # テスト用タイムラインデータ
    test_data = {
        "timeline": {
            "name": "水曜日 - Ocean Deep",
            "course_type": "dinner",
            "day_of_week": "wednesday"
        },
        "items": [
            {
                "content_file_path": "/content/themes/ocean/welcome.mp4",
                "start_time": 0,
                "duration": 180,
                "zone": "all",
                "transition": "fade_in"
            },
            {
                "content_file_path": "/content/themes/ocean/appetizer_coral.mp4",
                "start_time": 180,
                "duration": 120,
                "zone": "all",
                "transition": "crossfade"
            },
            {
                "content_file_path": "/content/themes/ocean/main_deep_sea.mp4",
                "start_time": 300,
                "duration": 180,
                "zone": "all",
                "transition": "wave"
            },
            {
                "content_file_path": "/content/themes/ocean/dessert_jellyfish.mp4",
                "start_time": 480,
                "duration": 180,
                "zone": "all",
                "transition": "bubble"
            }
        ]
    }

    # テスト用JSONファイル書き出し
    test_path = Path('/tmp/test_timeline.json')
    with open(test_path, 'w') as f:
        json.dump(test_data, f, indent=2)

    load_timeline(str(test_path))

    # シミュレーション
    import time
    _playback_state = 'playing'
    for t in range(0, 660, 30):
        on_timer_update(float(t))
        progress = get_progress()
        print(f"  Progress: {progress:.1%}")
