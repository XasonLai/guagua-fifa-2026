# guagua-fifa-2026

靜態 2026 FIFA 世界盃賽程頁。

```sh
python scripts/update_data.py --check
python scripts/update_data.py
python -m http.server 8000
```

資料來源：ESPN 公開 scoreboard endpoint。網站只讀 `data/*.json`，GitHub Actions 每天台灣時間 02:10 更新。
