# guagua-fifa-2026

靜態 2026 FIFA 世界盃賽程頁。

此專案使用 OpenAI Codex 協助開發，內容僅供快速瀏覽賽程、比分與簡易統計參考。正式賽事資訊、完整數據與公告請以 FIFA 官方網站為準。

```sh
python scripts/update_data.py --check
python scripts/update_data.py
python -m http.server 8000
```

資料來源：ESPN 公開 scoreboard endpoint。網站只讀 `data/*.json`。
射手榜資料來自 ESPN 單場 summary 的 `keyEvents`。
守門員榜資料來自 ESPN 單場 summary 的 `rosters`。
市場參考機率由 ESPN odds 換算，僅供參考，不是官方預測。
小組積分資料來自 ESPN standings endpoint。

GitHub Actions 會在台灣時間每天 22:07 開始，到隔日 15:37 每 30 分鐘更新一次資料：

- 22:07 / 22:37
- 23:07 / 23:37
- 00:07 / 00:37
- 01:07 / 01:37
- 02:07 / 02:37
- 03:07 / 03:37
- 04:07 / 04:37
- 05:07 / 05:37
- 06:07 / 06:37
- 07:07 / 07:37
- 08:07 / 08:37
- 09:07 / 09:37
- 10:07 / 10:37
- 11:07 / 11:37
- 12:07 / 12:37
- 13:07 / 13:37
- 14:07 / 14:37
- 15:07 / 15:37

cron 使用 UTC，所以設定為：

```yaml
7,37 14-23,0-7 * * *
```
