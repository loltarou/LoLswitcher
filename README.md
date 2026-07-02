# LoL Account Switcher

タスクトレイに常駐し、League of Legendsの複数アカウントをシームレスに切り替えるためのサポートツールです [cite: 88]。

## Features

*アカウントの高速切り替え:** 保存したセッションデータを利用して、ワンクリックで別アカウントへログイン・クライアント起動を行います [cite: 88]。
*アカウントの自動登録:** 新規追加時は、自動マクロによってID/PWを入力し、セッションを安全に保存します [cite: 88]。
*現在ランクの自動表示:** アカウント一覧のRiot IDの横に、現在のランク（例: `G4`、`un`）を自動で取得して表示します [cite: 88]。
*PUUID ⇄ Riot ID 変換ツール:** APIを利用して、IDからPUUID、PUUIDからIDを相互に検索・履歴保存できます [cite: 88]。

## Getting Started

本ツールの一部機能（ランク表示、PUUIDツール）を利用するには、Riot Developer Portalから取得したAPIキーが必要です [cite: 89][cite_start]。以下の手順で設定ファイルを必ず作成してください 。

1. APIキーの取得:** Riot Developer Portalにログインし、テスト用のAPIキー（`RGAPI-` から始まる文字列）をコピーします 。
2. *`.env` ファイルの作成:** メモ帳を開き、以下の一文のみを貼り付けます（空白や `""` などの記号は不要です） 。
   ```env
   RIOT_API_KEY=RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
