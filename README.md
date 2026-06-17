# guagua-fifa-2026

靜態 2026 FIFA 世界盃賽程頁。

```sh
python scripts/update_data.py --check
python scripts/update_data.py
python -m http.server 8000
```

資料來源：ESPN 公開 scoreboard endpoint。網站只讀 `data/*.json`。
射手榜資料來自 ESPN 單場 summary 的 `keyEvents`。
守門員榜資料來自 ESPN 單場 summary 的 `rosters`。

GitHub Actions 會在每天台灣時間 00:10、03:10、06:10、09:10、12:10 更新資料。cron 使用 UTC，所以設定為：

```yaml
10 16,19,22,1,4 * * *
```
