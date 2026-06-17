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

GitHub Actions 會在每天以下台灣時間更新資料：

- 00:10
- 05:10
- 08:10
- 11:10
- 14:10
- 16:10

cron 使用 UTC，所以設定為：

```yaml
10 16,21,0,3,6,8 * * *
```
