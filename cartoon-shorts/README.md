# cartoon-shorts

Các video ngắn hoạt hình "nhân vật 2D trong thế giới 3D" (Remotion + three.js), làm bằng skill `cartoon-3d-short`.

## Thư mục

| Thư mục | Chứa gì |
|---|---|
| `exports/` | **Video hoàn chỉnh** (2K, có tiếng). Chỉ chứa thành phẩm. |
| `shorts/<tên>/` | Đồ sản xuất của từng video: kịch bản (`SCRIPT.md`), giọng đọc (`voice/`), nhạc + hiệu ứng + bản trộn (`audio/`), danh sách shot cho QA |
| `src/videos/<tên>/` | Code hình của từng video (phân cảnh, máy quay, bối cảnh, nhân vật) |
| `src/engine/` | Phần dùng chung của mọi tập (vẽ nhân vật, texture, khối dựng cảnh, ánh sáng, màu, nét mực). Xem `src/engine/README.md`; danh mục hàm ở `src/engine/API.md` |
| `audio/` | Thư viện tổng hợp âm thanh dùng chung: xử lý tín hiệu (`dsp.py`), nhạc cụ, hiệu ứng |
| `backup/` | Khung chuẩn để kiểm tra engine, tự tạo bằng `scripts/qa/engine-check.sh save` (không kèm trong repo) |
| `src/Root.tsx` | Đăng ký các video (hiện có `BridgeShort`) |
| `public/kenney/` | Mô hình 3D Kenney (CC0), dùng chung |
| `scripts/` | Công cụ, chia nhóm: `voice/` (thu và kiểm giọng, phụ đề), `render/` (khung thử, render trên máy, render Modal), `qa/` (kiểm khung, bảng ảnh, kiểm engine); `xuong.py` ghi tiến trình, `clean.sh` dọn file tạm |
| `cloud/` | Render trên Modal (`remotion_modal.py`) |
| `out/` | **Chỉ file tạm** (ảnh thử, bundle render, cache). Xoá lúc nào cũng được: `scripts/clean.sh` |
| `node_modules/`, `.venv/` | Thư viện đã cài (Node, Python) |

Tập mẫu có sẵn: `BridgeShort`, "The Bridge That Fell for a Song" (tiếng Anh, 67 giây), nằm ở `src/videos/bridge/` và
`shorts/bridge/`. Tập mới: chép `src/videos/bridge/` sang tên khác rồi đăng ký trong `src/Root.tsx`. Bản dài 16:9 dùng
cùng engine, chỉ khác khung 1920x1080 (xem ghi chú trong `src/Root.tsx`).

## Xưởng phim (tiến trình realtime trong AutoVideo Studio)

Mỗi tập có `shorts/<tập>/progress.json`: 11 bước (nguồn truyện → kịch bản → giọng → phân cảnh → bối cảnh → nhân vật →
âm thanh → duyệt khung → render → kiểm tra → xuất bản), nhật ký, khung hình mới nhất, tiến độ render. Mọi script ghi vào đó
qua `scripts/xuong.py`; AutoVideo Studio → nút **Xưởng phim** theo dõi file và hiện ngay khi có thay đổi.

```bash
python3 scripts/xuong.py init <tập> --title "..." --number 1
```

```bash
python3 scripts/xuong.py start <tập> giong "..."
```

`done` / `fail` / `log` / `progress` / `frame` / `artifact` dùng tương tự (`python3 scripts/xuong.py -h`). Các script
`voice_local.py --ep`, `bridge-stills.mjs` (`XUONG_EP=`), `render.sh` (`XUONG_EP=`) tự báo tiến trình.

## Lệnh hay dùng (chạy trong thư mục này)

Thu giọng bằng ElevenLabs: điền `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` trong `.env`, chép
`scripts/voice/narration.elevenlabs.example.json` thành `shorts/<tập>/voice/narration.json`, sửa lời đọc rồi chạy:

```bash
python3 scripts/voice/voice_local.py shorts/<tập>/voice
```

Xem hướng dẫn đầy đủ ở mục **Giọng đọc → ElevenLabs** trong `../README.md`.
TTS local hiện có vẫn dùng cấu hình `engine`, `port`, `voice` (không cần `provider`).

Render thử vài khung (ảnh ra `out/stills/`, bundle tạm tự xoá):
```bash
COMP=BridgeShort node scripts/render/bridge-stills.mjs out/stills/x_ 60,700,1460 0.5
```

Render bản cuối 2K và ghép tiếng vào `exports/` **trên Modal** (mặc định; máy của bạn không bị giật;
mỗi máy một cột tiến độ trong Xưởng phim). Tuỳ chọn: `WORKERS=10` nhanh nhất, `LOCAL_SHARE=0.15` cho máy của bạn render cùng 15%:
```bash
EPISODE=bridge scripts/render/render-cloud.sh BridgeShort shorts/bridge/audio/mix.wav exports/bridge_2k.mp4
```

Render ngay trên máy (không tốn tiền, chậm hơn nhiều, máy giật vì GPU bận):
```bash
XUONG_EP=bridge scripts/render/render.sh BridgeShort shorts/bridge/audio/mix.wav exports/bridge_2k.mp4
```

Kiểm tra từng khung của video đã render (báo cáo ra `out/qa/`):
```bash
.venv/bin/python scripts/qa/short_qa.py exports/bridge_2k.mp4 out/qa/bridge shorts/bridge/shots.json
```

Dọn toàn bộ file tạm (cho vào Thùng rác):
```bash
scripts/clean.sh
```

Quy ước: file trung gian (ảnh thử, cache, stem, bundle) luôn để trong `out/`. Cạnh code chỉ giữ code và kết quả cần dùng lại
(`voice.wav`, `words.json`, `mix.wav`, `cues.md`).
