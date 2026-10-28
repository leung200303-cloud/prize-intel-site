# UI 操作流程：盤點優先（inventory-first）

## 錯嘅舊流程（唔再用）
任務 → 憑視覺搵目標圖樣 → 直接發 HID 點擊
問題：遇到唔認得嘅圖標（copy icon、svg、icon font）就卡死。

## 正確流程（每次操作 UI 都要跟）
1. **盤點**：對當前畫面做一次全域可互動元件掃描，得出清單（index | tag | label | x | y）。
2. **分類**：睇清單，按 label / tag / 位置分辨每個掣做咩；唔肯定就 zoom 該區。
3. **配對**：由任務（例如「複製 token」）喺清單配對功能，而唔係靠圖樣搜尋。
4. **執行**：用清單座標發 HID 點擊（或 `__ui.click(index)` 走 DOM click）。
5. **驗證**：動作後抽一幀確認生效；失敗重盤點，唔好盲重試同一坐標。

## 工具
`tools/ui_inventory.js` → 貼入 DevTools Console：
- `__ui()` 印清單 `index|tag|label|x|y`
- `__ui.find("copy")` 按關鍵字搵
- `__ui.click(n)` 直接觸發
- `__ui.coords(n)` 拎屏幕像素座標交 ESP32 HID

桌面程式用 Windows UIA `BoundingRectangle`；瀏覽器內頁面用 DOM/AX Tree（兩個唔同 API）。

## 已知陷阱
- 表單驗證未過 → 按鈕天生 `disabled`，點幾多次都冇反應；先補必填（例如權限政策要綁資源範圍）。
- 長字串（JS/URL）用 HID 逐字打會漏字 → 拆短句、或寫檔再引用；複製 token 用頁面 copy 掣（靠清單定位）唔好靠 OCR。
- 截圖座標換算：1920×1080 截圖、預覽 1708×961 → 真實 = 預覽 × 1.1241。
