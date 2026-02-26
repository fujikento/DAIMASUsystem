"""
TouchDesigner OSC受信スクリプト
FastAPI バックエンドからのOSCメッセージを受信し、映像制御を行う

TouchDesigner内のScript CHOPまたはScript TOPに配置して使用
"""

# TouchDesigner内で実行される場合のグローバル変数
# td モジュールはTouchDesigner環境で自動的に利用可能

OSC_PORT = 7000

# OSCアドレスと対応するTouchDesignerオペレータのマッピング
OSC_MAP = {
    '/play': 'timeline_player',
    '/pause': 'timeline_player',
    '/stop': 'timeline_player',
    '/content/load': 'content_loader',
    '/transition': 'transition_engine',
    '/birthday/trigger': 'birthday_controller',
    '/zone/select': 'zone_selector',
}


def onReceiveOSC(address, args):
    """
    OSCメッセージ受信時のコールバック

    Args:
        address: OSCアドレス (e.g., '/play', '/content/load')
        args: メッセージ引数のリスト
    """
    print(f"[OSC] Received: {address} {args}")

    if address == '/play':
        handle_play(args)
    elif address == '/pause':
        handle_pause()
    elif address == '/stop':
        handle_stop()
    elif address == '/content/load':
        handle_content_load(args)
    elif address == '/transition':
        handle_transition(args)
    elif address == '/birthday/trigger':
        handle_birthday(args)
    elif address == '/zone/select':
        handle_zone_select(args)


def handle_play(args):
    """タイムライン再生開始"""
    timeline_id = args[0] if args else None
    # TouchDesignerのタイムラインCHOPを制御
    # op('timeline_player').par.play = True
    print(f"[Play] Timeline: {timeline_id}")
    store_status('playing', timeline_id)


def handle_pause():
    """再生一時停止"""
    # op('timeline_player').par.play = False
    print("[Pause]")
    store_status('paused')


def handle_stop():
    """再生停止"""
    # op('timeline_player').par.play = False
    # op('timeline_player').par.cue = True
    print("[Stop]")
    store_status('stopped')


def handle_content_load(args):
    """コンテンツ読み込み"""
    if len(args) >= 1:
        file_path = args[0]
        zone = args[1] if len(args) >= 2 else 'all'
        print(f"[Content Load] File: {file_path}, Zone: {zone}")
        # op('content_loader').par.file = file_path
        # ゾーン指定がある場合は該当区画のみに投影
        if zone != 'all':
            # op('zone_selector').par.activeZone = zone
            pass


def handle_transition(args):
    """トランジション実行"""
    transition_type = args[0] if args else 'crossfade'
    duration = float(args[1]) if len(args) >= 2 else 1.0
    print(f"[Transition] Type: {transition_type}, Duration: {duration}s")
    # op('transition_engine').par.type = transition_type
    # op('transition_engine').par.duration = duration
    # op('transition_engine').par.trigger.pulse()


def handle_birthday(args):
    """誕生日サプライズ演出トリガー"""
    video_path = args[0] if args else None
    guest_name = args[1] if len(args) >= 2 else ''
    print(f"[Birthday] Video: {video_path}, Guest: {guest_name}")
    # 誕生日テンプレートにキャラクター映像を合成
    # op('birthday_controller').par.characterVideo = video_path
    # op('birthday_controller').par.guestName = guest_name
    # op('birthday_controller').par.trigger.pulse()


def handle_zone_select(args):
    """投影ゾーン選択"""
    zone = args[0] if args else 'all'
    print(f"[Zone Select] Zone: {zone}")
    # 'all' = テーブル全体, '1'-'4' = 各区画
    # op('zone_selector').par.activeZone = zone


def store_status(status, timeline_id=None):
    """再生状態を保存（ステータス問い合わせ用）"""
    # TouchDesignerのストレージに保存
    # op('status_store').store('playback_status', status)
    # if timeline_id:
    #     op('status_store').store('current_timeline', timeline_id)
    pass


# ====================================================================
# スタンドアロンテスト用（TouchDesigner外で動作確認）
# ====================================================================
if __name__ == '__main__':
    from pythonosc.dispatcher import Dispatcher
    from pythonosc.osc_server import ThreadingOSCUDPServer

    dispatcher = Dispatcher()
    dispatcher.map("/play", lambda addr, *args: onReceiveOSC(addr, list(args)))
    dispatcher.map("/pause", lambda addr, *args: onReceiveOSC(addr, list(args)))
    dispatcher.map("/stop", lambda addr, *args: onReceiveOSC(addr, list(args)))
    dispatcher.map("/content/load", lambda addr, *args: onReceiveOSC(addr, list(args)))
    dispatcher.map("/transition", lambda addr, *args: onReceiveOSC(addr, list(args)))
    dispatcher.map("/birthday/trigger", lambda addr, *args: onReceiveOSC(addr, list(args)))
    dispatcher.map("/zone/select", lambda addr, *args: onReceiveOSC(addr, list(args)))

    server = ThreadingOSCUDPServer(("0.0.0.0", OSC_PORT), dispatcher)
    print(f"OSC Server listening on port {OSC_PORT}")
    print("Waiting for messages from FastAPI backend...")
    server.serve_forever()
