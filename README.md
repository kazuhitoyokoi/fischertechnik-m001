# fischertechnik-m001 シミュレータ

本リポジトリは、fischertechnik M001 の入出力モデルを Python で再現し、以下 3 つの観点で検証できる構成です。

- GPIO 制御ロジックそのものの単体検証
- OPC UA ノードへの状態同期検証
- Streamlit UI による手動操作と自動シナリオ可視化

実機がなくても、`gpiozero` の mock pin を使って同等の状態遷移を再現できます。

## ファイル構成と役割

- `typeM001_gpiozero.py`
GPIO 入出力モデルと本体制御ロジック（`control_logic()`）を提供。

- `typeM001_opcua.py`
OPC UA サーバーを起動し、`typeM001_gpiozero.py` のログ文字列を解析して OPC UA ノードへ同期。

- `app.py`
手動トグル UI。センサー状態を操作し、1 ステップずつ `control_logic()` を実行して結果を表示。

- `app_opcua.py`
OPC UA サーバー内蔵の自動シナリオ UI。シナリオログを連続投入し、ノード値をリアルタイム表示。

- `typeM001_rpigpio.py`
物理 GPIO を使う実機寄りの参考実装。

- `tests/test_typeM001_gpiozero.py`
制御ロジックのシナリオテスト。

- `tests/test_typeM001_opcua.py`
OPC UA 同期ロジック（文字列パースとノード値更新）のテスト。

## 動作環境

- Python 3.9+
- Linux 想定（Raspberry Pi を含む）

依存ライブラリは `requirements.txt` の固定バージョンを使用します。

- `gpiozero==2.0.1`
- `opcua==0.98.13`
- `pytest==9.0.3`
- `streamlit==1.58.0`

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 制御ロジック仕様（typeM001_gpiozero.py）

### 1. ピン割り当て

| 対象 | 種別 | GPIO |
| --- | --- | --- |
| フォトセンサ | 入力 | 5 |
| 磁気センサ | 入力 | 6 |
| 非常停止スイッチ | 入力 | 16 |
| モーター正転 | 出力 | 22 |
| モーター逆転ダミー | 出力 | 24 |
| LED01（投光器） | 出力 | 23 |
| LED02（ステータス） | 出力 | 25 |

### 2. 入力極性（pull_up=True のため論理反転あり）

`Button(..., pull_up=True)` を使っているため、`is_active` と制御上の意味が一致しない入力があります。制御側の内部値は次のように計算されます。

- `current_photo = 0 if photo.is_active else 1`
- `current_sw = 0 if sw.is_active else 1`
- `current_magnet = 0 if magnet.is_active else 1`

運用上は次の意味になります。

| 入力 | 制御値 0 | 制御値 1 |
| --- | --- | --- |
| フォトセンサ | ワークなし | ワーク検知 |
| 非常停止SW | 解除/通常 | 非常停止中 |
| 磁気センサ | 磁気検知 | 磁気なし |

### 3. 出力制御ルール

- LED01 は初期化直後に `on()` され、制御ロジック内で変更しません。
- 非常停止が `1` の間は最優先でモーターを強制停止します。
- 非常停止が `0` かつフォトセンサが `1` であればモーターを起動します。
- 磁気センサが `0`（磁気検知）ならモーター停止し、LED02 を点灯します。
- 磁気センサが `1`（磁気なし）なら LED02 を消灯します。

注記: フォトセンサが `0`（ワークなし）へ戻っても、非常停止や磁気検知がなければモーター状態は保持されます（テストで保証）。

## OPC UA サーバー仕様（typeM001_opcua.py）

### 1. 接続情報

- サーバー起動エンドポイント: `opc.tcp://0.0.0.0:4840/m001`
- ローカルクライアント接続先: `opc.tcp://127.0.0.1:4840/m001`
- Namespace URI: `urn:local:l1`
- Namespace Index: `1`（固定運用）

### 2. ノード構成

- `Objects/Sensors/PhotoSensor` -> `ns=1;s=Sensors.PhotoSensor`
- `Objects/Sensors/PushSwitch` -> `ns=1;s=Sensors.PushSwitch`
- `Objects/Sensors/MagnetSensor` -> `ns=1;s=Sensors.MagnetSensor`
- `Objects/Actuators/ProjectorLED` -> `ns=1;s=Actuators.ProjectorLED`
- `Objects/Actuators/ConveyorMotor` -> `ns=1;s=Actuators.ConveyorMotor`
- `Objects/Actuators/StatusLED` -> `ns=1;s=Actuators.StatusLED`

### 3. 同期方式

`typeM001_opcua.py` は、子プロセスまたはモックプロセスの標準出力を行単位で監視し、キーワードに応じてノード値を更新します。

キーワード判定の例:

- フォトセンサ: `HIGH` / `ワーク検知` -> `True`、`LOW` / `ワークなし` -> `False`
- 非常停止: `HIGH` / `作動中` -> `True`、`LOW` / `解除` -> `False`
- 磁気: `LOW` / `検知` -> `True`、`HIGH` / `磁気なし` -> `False`
- モーター: `起動` / `ON` -> `True`、`停止` / `OFF` -> `False`
- LED01: `ON` / `点灯` -> `True`、`OFF` / `消灯` -> `False`
- LED02: `HIGH` / `点灯` -> `True`、`LOW` / `消灯` -> `False`

値が変化した場合のみ更新とイベントログ出力を行います（重複更新抑制）。

## UI 起動方法

### 1. 手動操作 UI

```bash
streamlit run app.py
```

ブラウザで `http://localhost:8501` を開きます。

この UI は入力トグル操作後、`control_logic()` を 1 回実行して結果を反映します。

### 2. OPC UA サーバー単体

```bash
python typeM001_opcua.py
```

`typeM001_gpiozero.py` を子プロセス起動してログを解析し、OPC UA へ同期します。

### 3. 自動シナリオ + OPC UA 可視化 UI

```bash
streamlit run app_opcua.py
```

この UI はアプリ内で OPC UA サーバーを初期化し、定義済みシナリオをバックグラウンドで無限ループ実行します。

## テスト

全テスト:

```bash
pytest -v
```

個別実行:

```bash
pytest tests/test_typeM001_gpiozero.py -v
pytest tests/test_typeM001_opcua.py -v
```

## 実行モードに関する注意点

- `app.py` と `tests/test_typeM001_gpiozero.py` では PWM 非対応環境向けに `MockPin._set_frequency` を差し替えています。
- `typeM001_gpiozero.py` は `if __name__ == '__main__'` のときのみ無限ループ実行します。モジュール import 時は `control_logic()` を外部から呼び出す設計です。
- `typeM001_rpigpio.py` は `STREAMLIT_RUNNING` 環境変数が未設定の場合に常時ループします。
