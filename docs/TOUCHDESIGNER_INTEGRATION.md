# TouchDesigner 統合ガイド

DAIMASUsystem backend が送信する OSC を TouchDesigner 側で受け取り、3 プロジェクタへ
出力する仕組み。

## OSC プロトコル

### 接続

| 方向 | port | 用途 |
|---|---|---|
| backend → TD | UDP **7000** (env `OSC_TD_PORT`) | 制御コマンド |
| TD → backend | UDP **7001** (env `OSC_ACK_PORT`) | ack (オプション) |

### 主要アドレス

#### コンテンツ制御

| address | args | 説明 |
|---|---|---|
| `/content/load` | `file_path:str`, `zone:str` | 指定ゾーン (all/1/2/3/4) にコンテンツをロード |
| `/transition` | `type:str`, `duration:float` | トランジション実行 (crossfade/cut/fade_black 等) |
| `/play` | `timeline_id:int`, `table_id:str?` | タイムライン再生開始 |
| `/pause` | — | 再生停止 |
| `/stop` | — | 停止 + 待機状態へ |

#### 演出トリガー

| address | args | 説明 |
|---|---|---|
| `/projection/blackout` | `1` or `0` | 1=黒画面強制、0=解除 |
| `/birthday/trigger` | `guest_name:str`, `video_path:str` | バースデー演出 |
| `/course/serve` | `session_id:int`, `course_key:str` | 料理提供トリガー |
| `/course/clear` | `session_id:int`, `course_key:str` | 皿下げトリガー |
| `/course/preload` | `course_key:str` | 次コース事前ロード |
| `/course/allergen_alert` | `session_id:int` | アレルギー対応シーン |
| `/audio/bgm/load` | `file_path:str`, `duration:float` | BGM プリロード |
| `/audio/bgm/play` | `volume:float`, `loop:int` | BGM 再生 |
| `/zone/content` | `zone_id:int`, `file_path:str` | ゾーン個別コンテンツ |
| `/zone/brightness` | `zone_id:int`, `brightness:float` | ゾーン個別輝度 |
| `/preset/load` | `preset_id:int` | プリセット呼び出し |

### Ack mode (オプション、env `OSC_ACK_ENABLED=1`)

backend は ack mode 時、送信メッセージの先頭に `[seq:int, ts_ms:int, ...args]` を付ける。
TouchDesigner 側パッチは:

1. arg[0] を seq、arg[1] を ts_ms として読む
2. 残り arg[2:] を実引数として使う
3. 処理完了後、UDP 7001 に `/ack/<seq>` を送り返す

ack mode 無効時 (default) は seq/ts は付与されず、従来通り `/play timeline_id` 1 引数で送る。

## TouchDesigner 側パッチ最低構成

```
OSC In CHOP (port 7000)
  ├─ Select CHOP (/content/load) → File In TOP に file_path を渡す
  ├─ Select CHOP (/transition)   → Cross TOP の blend value を duration で animate
  ├─ Select CHOP (/projection/blackout) → Constant TOP (黒) の opacity 切替
  └─ ...
```

3 PJ 出力は `Splitter TOP` → `Render TOP × 3 (PJ1/PJ2/PJ3 ぞれぞれ)` でエッジブレンド。

## 生成 video のパス規約

backend が生成した動画は以下に置かれる:

```
touchdesigner/content/themes/<theme>/<mode>/<filename>.mp4
```

例:
- `themes/zen/zone/main_zone2__gen_xxx.mp4`
- `themes/ocean/ultra_wide_i2v/main_uw__gen_xxx_band.mp4` (5520x1200 にすでに crop 済み)

OSC `/content/load` で渡される `file_path` はこの絶対パスなので、TouchDesigner 側で
File In TOP に直接渡せる。

## 互換性チェック

ack mode 切替時は TouchDesigner パッチも seq prepend に対応させる必要あり。
切替手順:

1. backend を一度停止
2. `OSC_ACK_ENABLED=1` に env 変更
3. backend 起動 (`/api/system/info` で `OSC_ACK_ENABLED: "1"` 確認)
4. TouchDesigner パッチを ack mode 対応版にロード
5. テスト送信: `curl -X POST http://localhost:8000/api/system/rehearsal/0` 後 `/api/shows/{id}/go`

ack 不一致のときは backend ログに `OSC ack timeout` が出る。

## TODO (Phase 5+)

- [ ] TD パッチを `.toe` として repo に commit (現状未バージョン管理)
- [ ] ack mode 対応の参照パッチを `touchdesigner/patches/` に追加
- [ ] エッジブレンドカリブレーション手順を別 doc に
