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
    '/seat/content': 'seat_router',
}

# 席 (投影エリア) ごとの TouchDesigner 出力グループ名のマッピング。
# backend の ProjectionConfig.id → TD 内の出力 COMP / Container 名。
# 実環境ではここを店舗の物理 PJ 構成に合わせて編集する。
SEAT_OUTPUT_MAP = {
    1: 'seat1_output',   # 例: メインテーブル (3PJ ブレンド)
    2: 'seat2_output',   # 例: VIP個室 (1PJ)
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
    elif address == '/seat/content':
        handle_seat_content(args)


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


def handle_seat_content(args):
    """席 (投影エリア) 単位のコンテンツロード。

    OSC: /seat/content seat_id file_path zone mode

    backend (api/services/osc_controller.load_content_seat) から送られる。
    複数席を別々の演出で同時投影するための基本ハンドラ。

    mode:
      - unified:      席の全幅に 1 動画を連結投影 (zone は無視 / "all")
      - per_zone:     ゾーンごとに別動画 (zone="all" は全ゾーン更新、"1,2" は部分)
      - synchronized: 全ゾーンに同じ動画を同期再生

    TD 実装方針 (コメントは擬似コード):
      1. seat_id → SEAT_OUTPUT_MAP で出力グループ COMP を引く
      2. その COMP 配下の File In TOP に file_path を設定
      3. mode で zone 分割の有無を切り替える
    """
    if len(args) < 2:
        print(f"[Seat Content] invalid args (need seat_id, file_path): {args}")
        return

    try:
        seat_id = int(args[0])
    except (ValueError, TypeError):
        print(f"[Seat Content] invalid seat_id: {args[0]!r}")
        return

    file_path = args[1]
    zone = args[2] if len(args) >= 3 else 'all'
    mode = args[3] if len(args) >= 4 else 'unified'

    output_group = SEAT_OUTPUT_MAP.get(seat_id)
    if output_group is None:
        print(f"[Seat Content] WARNING: seat_id {seat_id} not in SEAT_OUTPUT_MAP "
              f"({sorted(SEAT_OUTPUT_MAP)}). コンテンツをロードできません。")
        return

    print(f"[Seat Content] seat={seat_id} ({output_group}) "
          f"file={file_path} zone={zone} mode={mode}")

    if mode == 'unified':
        # 席の全幅に 1 動画。例:
        # op(output_group).op('unified_in').par.file = file_path
        # op(output_group).par.zonesplit = 0
        pass
    elif mode == 'synchronized':
        # 全ゾーンに同じ動画を同期再生。例:
        # for z in range(zone_count_of(seat_id)):
        #     op(output_group).op(f'zone{z}_in').par.file = file_path
        pass
    elif mode == 'per_zone':
        # ゾーンごとに別動画。zone="all" は全ゾーン、"1,2" は該当のみ。
        targets = _parse_zone_spec(zone, seat_id)
        for z in targets:
            # op(output_group).op(f'zone{z}_in').par.file = file_path
            print(f"  [per_zone] zone{z} <- {file_path}")
    else:
        print(f"[Seat Content] unknown mode '{mode}', falling back to unified")


def _parse_zone_spec(zone, seat_id):
    """zone 指定文字列を 0-based のゾーン index リストに変換する。

    "all" → 全ゾーン (SEAT_ZONE_COUNT より、ここでは簡易に 0..3)。
    "1,2" → [0, 1] (1-based 入力を 0-based に変換)。
    """
    if zone == 'all' or not zone:
        # 実環境では seat_id ごとの zone_count を引く。ここでは最大 4 を仮定。
        return list(range(4))
    out = []
    for tok in str(zone).split(','):
        tok = tok.strip()
        if tok.isdigit():
            out.append(int(tok) - 1)
    return out


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
    dispatcher.map("/seat/content", lambda addr, *args: onReceiveOSC(addr, list(args)))

    server = ThreadingOSCUDPServer(("0.0.0.0", OSC_PORT), dispatcher)
    print(f"OSC Server listening on port {OSC_PORT}")
    print("Waiting for messages from FastAPI backend...")
    server.serve_forever()
