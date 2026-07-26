[README.md](https://github.com/user-attachments/files/30383818/README.md)
# Switch — Riot / League of Legends アカウント切り替えツール

システムトレイに常駐し、**Riot のセッションファイルを入れ替える方式**で複数アカウントをワンクリックで切り替える Windows 用アプリです。保存済みセッションが無効な場合は、**UI Automation で Riot Client のログイン欄に直接入力**して自動ログインします（グローバルなキー入力を使わないため、Discord など他アプリへの誤爆が起きません）。

---

## 主な機能

- **アカウント切り替え** — トレイからアカウントを選ぶだけで、セッションを入れ替えて対象アカウントに切り替え → League of Legends を自動起動
- **自動ログイン（UI Automation 方式）** — セッションが切れている場合、Riot Client のログイン欄（ユーザー名 / パスワード）に値を直接セットし、「サインイン状態を維持」を自動でON、Enter で送信
- **アカウント新規登録** — ID / パスワードを登録すると、初回ログイン後にセッションを自動保存
- **ランク表示** — 各アカウントのソロランク（例: `D2`, `G4`）をボタンに表示（Riot API 使用、24時間キャッシュ）
- **PUUID ⇄ Riot ID 変換ツール** — Riot API で相互変換、履歴保存
- **多重起動防止** — 常に1インスタンスのみ

---

## 仕組み

切り替え時に以下のファイルを `%LOCALAPPDATA%\Switch\Profiles\<RiotID>\` と Riot Client の実データの間でコピーして入れ替えます。

| ファイル | 相対パス |
|---|---|
| `RiotGamesPrivateSettings.yaml` | `Data/RiotGamesPrivateSettings.yaml` |
| `Sessions`（フォルダ） | `Data/Sessions` |
| `RiotClientSettings.yaml` | `Config/RiotClientSettings.yaml` |

- 切り替え後、ローカル API（`chat/v1/session`）で認証が生きているか検証します。無効なら保存済みプロファイルを破棄し、ログイン画面で自動入力を実行します。
- 自動ログインには「**サインイン状態を維持**」のONが必須です（永続トークンが `RiotGamesPrivateSettings.yaml` に保存され、次回以降の切り替えが成立します）。本アプリは自動でONにします。

---

## 動作要件

- Windows 10 / 11
- Riot Client / League of Legends がインストール済み
- **ソースから実行する場合**は Python 3.x と以下のパッケージ

```bash
pip install PyQt6 requests urllib3 pyautogui pywin32 uiautomation comtypes
```

> `uiautomation` / `comtypes` は自動ログイン（直接入力）に必須です。

---

## セットアップ

### API キー（ランク表示・PUUID ツールを使う場合のみ）

[Riot Developer Portal](https://developer.riotgames.com/) で取得した API キーを `.env` に記述します。

```
RIOT_API_KEY=RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

`.env` は以下のどちらに置いても読み込まれます（**exe の隣が最優先**）。

1. `main.exe`（またはソース）と同じフォルダ
2. `%LOCALAPPDATA%\Switch\.env`

> API キーが無くてもアカウント切り替え自体は動作します（ランク表示と PUUID ツールが無効になるだけ）。

---

## 使い方

タスクトレイのアイコンを操作します。

| 操作 | 動作 |
|---|---|
| **左クリック** | 登録アカウント一覧を表示（同時にランクを更新） |
| **右クリック** | メニュー（PUUID ツール / 設定 / 終了）を表示 |
| アカウントを**左クリック** | そのアカウントに切り替え |
| アカウントを**右クリック** | 変更 / 削除パネルを表示 |
| **[+] アカウントを追加** | ID・パスワードを入力して新規登録 |

### 新規アカウント追加の流れ

1. 一覧下部の「**[+] アカウントを追加**」から ID / パスワードを入力
2. 既存の Riot プロセスを終了 → Riot Client を起動
3. ログイン画面が出ると、入力欄へ自動入力してログイン
4. ログイン確認後、セッションを `Profiles/<RiotID>` に自動保存し、LoL を起動

---

## 設定・データの保存場所

すべて `%LOCALAPPDATA%\Switch\` 配下に保存されます（exe の場所に依存しません）。

```
%LOCALAPPDATA%\Switch\
├── settings.json      … アカウント情報・PUUID履歴・ランクキャッシュ
├── .env               … （任意）APIキーをここに置くことも可能
└── Profiles\
    └── <RiotID>\      … アカウントごとのセッションファイル一式
```

`settings.json` は右クリックメニューの「**設定（メモ帳）**」から直接編集できます。

---

## ソースから実行

```bash
python main.py
```

## ビルド（単一 exe を作成）

[PyInstaller](https://pyinstaller.org/) を使用します。

```bash
pip install pyinstaller
pyinstaller main.spec
```

- 出力: `dist\main.exe`（onefile・単一ファイル）
- アイコン（`assets\icon.ico`）は exe とトレイ表示の両方に同梱されます
- 生成された `main.exe` は**任意の場所に移動して動作**します

### 診断用フラグ

UI Automation がその実行環境で動作するかを確認できます（結果は `%TEMP%\switch_uia_selftest.txt` に出力）。

```bash
main.exe --uia-selftest
```

---

## 注意事項

- 本ツールは Riot Client のセッションファイルを直接操作します。仕様変更により動作しなくなる可能性があります。
- パスワードは `settings.json` に**平文で保存**されます。取り扱いに注意してください。
- 自動ログインが UI Automation で失敗した場合は、Riot Client が前面にあることを検証したうえでキー入力にフォールバックします（この場合も他アプリへの誤爆はしません）。
- Riot Games / League of Legends は Riot Games, Inc. の商標です。本ツールは非公式・個人利用向けであり、Riot Games とは一切関係ありません。
