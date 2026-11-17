<div align="center">

<img src="docs/media/hero.jpg" alt="Năm khung hình từ các short làm bằng engine này" width="100%">

# Video Short Animation

**Xưởng làm phim hoạt hình bằng mã nguồn: nhân vật 2D trong thế giới 3D, không dùng máy sinh video AI.**

Một truyện ra hai bản: short dọc 9:16 (60–90 giây) và bản dài ngang 16:9 (5–8 phút).

![Remotion](https://img.shields.io/badge/Remotion-4.0-0B84F3?style=for-the-badge)
![three.js](https://img.shields.io/badge/three.js-r175-000000?style=for-the-badge&logo=threedotjs&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.8-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Modal](https://img.shields.io/badge/Render-Modal_GPU-7FEE64?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-F5C542?style=for-the-badge)

[Tính năng](#tính-năng) · [Dây chuyền](#dây-chuyền) · [Bắt đầu nhanh](#bắt-đầu-nhanh) · [Giọng đọc](#giọng-đọc) · [Cấu hình](#cấu-hình) · [Cấu trúc](#cấu-trúc-thư-mục)

<br>

<table>
<tr>
<td align="center"><img src="docs/media/river.gif" alt="Bóng ma trồi lên giữa sông" width="250"></td>
<td align="center"><img src="docs/media/boat.gif" alt="Con thuyền cập bến" width="250"></td>
<td align="center"><img src="docs/media/ghost.gif" alt="Cái xác đứng dậy sau lưng cậu bé" width="250"></td>
</tr>
<tr>
<td align="center"><sub>Hiệu ứng nước, ánh sáng đêm</sub></td>
<td align="center"><sub>Đám đông, máy quay lướt</sub></td>
<td align="center"><sub>Biểu cảm, bóng đổ, nét mực</sub></td>
</tr>
</table>

<sub>Short dọc 9:16, render bằng chính engine trong repo.</sub>

<br><br>

<table>
<tr>
<td><img src="docs/media/long-ml-1069.jpg" alt="Hai đứa trẻ câu cá trên bến sông" width="100%"></td>
<td><img src="docs/media/long-cl-2000.jpg" alt="Chàng trai bên bến sông lúc hoàng hôn" width="100%"></td>
</tr>
<tr>
<td><img src="docs/media/long-ql-4600.jpg" alt="Bóng trắng đuổi theo cậu bé trong đêm" width="100%"></td>
<td><img src="docs/media/long-cl-3600.jpg" alt="Dấu chân trên cầu thuyền" width="100%"></td>
</tr>
</table>

<sub>Bản dài ngang 16:9, cùng một engine.</sub>

</div>

> **English.** A code-first studio for cartoon story videos, short and long form: flat 2D characters in a painted 3D world, rendered with three.js inside Remotion, local TTS with word-level timing, synthesized music and SFX, parallel GPU rendering on Modal, automated frame QA and scheduled posting. Docs are in Vietnamese, code comments in English.

## Mục lục

- [Tính năng](#tính-năng)
- [Dây chuyền](#dây-chuyền)
- [Tập mẫu](#tập-mẫu)
- [Bắt đầu nhanh](#bắt-đầu-nhanh)
- [Giọng đọc](#giọng-đọc)
- [Cấu hình](#cấu-hình)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Dùng với Claude Code](#dùng-với-claude-code)
- [Giấy phép](#giấy-phép)

## Tính năng

| | Tính năng | Mô tả |
|:-:|---|---|
| 🎬 | **Hình là mã nguồn** | Mỗi khung hình là TypeScript: sửa một dòng, render lại đúng cảnh đó. Engine dùng chung có 213 hàm và hằng cho nhân vật, bối cảnh, ánh sáng, nét mực, mờ ống kính, chỉnh màu. |
| 🎙️ | **Giọng khớp từng chữ** | Giọng đọc từ model TTS chạy local, kèm mốc thời gian từng chữ để hình bám theo lời. |
| 🎼 | **Nhạc tự tổng hợp** | Nhạc và hiệu ứng tạo bằng numpy/scipy, tự hạ nhạc khi có lời. |
| ☁️ | **Render vài phút** | Chia tập thành nhiều đoạn, render song song trên GPU của Modal. |
| 🔍 | **Kiểm tự động** | Script soi từng khung của bản render: khung đen, khung trắng, đứng hình, nhảy hình, độ to của tiếng. |
| 🧩 | **Tập mẫu đầy đủ** | Một short 67 giây kèm mã hình, kịch bản và script âm thanh: chép ra, đổi truyện là có khung cho tập mới. |
| 🤖 | **Làm cùng Claude Code** | Skill `cartoon-3d-short` dẫn Claude Code đi hết quy trình, từ chọn truyện tới bản render cuối. |

## Dây chuyền

Bốn chặng, mười một bước. Mỗi bước ghi tiến trình vào `progress.json` bằng `scripts/xuong.py`.

<p align="center"><img src="docs/media/pipeline.svg" alt="Dây chuyền bốn chặng: viết, tiếng, hình, xuất" width="100%"></p>

| | Công đoạn | Công nghệ | Công cụ | Kết quả |
|:-:|---|---|---|---|
| ✍️ | Kịch bản | Skill dẫn từng bước | [`SKILL.md`](skill/cartoon-3d-short/SKILL.md) | `SCRIPT.md` |
| 🎙️ | Giọng đọc | Model TTS chạy local | `scripts/voice/voice_local.py` | `voice.wav`, `words.json` |
| 🎼 | Nhạc, hiệu ứng | numpy, scipy | [`audio/`](cartoon-shorts/audio) | `mix.wav` |
| 🎨 | Hình | Remotion, three.js, React Three Fiber | [`src/engine/`](cartoon-shorts/src/engine) · [`API.md`](cartoon-shorts/src/engine/API.md) | composition |
| 🖼️ | Khung thử | Remotion still | `scripts/render/bridge-stills.mjs` | ảnh `.jpg` |
| ☁️ | Render | Modal GPU hoặc máy cá nhân | `scripts/render/render-cloud.sh` | `.mp4` 2K |
| 🔍 | Kiểm khung | ffmpeg, Python | `scripts/qa/short_qa.py` · `long_qa.py` | báo cáo `.md` |
| 💬 | Phụ đề | Mốc thời gian từng chữ | `scripts/voice/make_srt.py` | `.srt` |
| 📅 | Đăng bài | Facebook Graph API | [`autopost/`](autopost) | bài hẹn giờ |

### Một khung hình được dựng thế nào

<p align="center"><img src="docs/media/frame-layers.svg" alt="Năm lớp dựng một khung hình" width="100%"></p>

### Render song song trên Modal

<p align="center"><img src="docs/media/modal-render.svg" alt="Render song song trên Modal" width="100%"></p>

## Tập mẫu

**The Bridge That Fell for a Song**: short tiếng Anh, 67 giây, dùng để học và chép làm khung cho tập mới.

<table>
<tr>
<td><img src="docs/media/still-150.jpg" alt="Cây cầu treo và dân làng" width="100%"></td>
<td><img src="docs/media/still-270.jpg" alt="Tháp cầu nhìn từ mặt nước" width="100%"></td>
<td><img src="docs/media/still-560.jpg" alt="Đoàn lính trên cầu" width="100%"></td>
<td><img src="docs/media/still-1450.jpg" alt="Xích đu lúc hoàng hôn" width="100%"></td>
</tr>
</table>

| Phần | Vị trí |
|---|---|
| Mã hình | [`cartoon-shorts/src/videos/bridge/`](cartoon-shorts/src/videos/bridge) |
| Kịch bản, giọng, âm thanh | [`cartoon-shorts/shorts/bridge/`](cartoon-shorts/shorts/bridge) |

## Bắt đầu nhanh

### Yêu cầu

| Công cụ | Phiên bản |
|---|---|
| Node.js | 20 trở lên |
| pnpm | 10.34.9 (khóa trong `packageManager`) |
| Python | 3.12 trở lên |
| ffmpeg | bản bất kỳ |

### Cài đặt

```bash
git clone https://github.com/DuongVuIT/video-short-animation.git
```

```bash
cd video-short-animation/cartoon-shorts
corepack enable
pnpm install --frozen-lockfile
```

Nếu bản Node.js không kèm Corepack, cài pnpm 10.34.9 theo [hướng dẫn pnpm](https://pnpm.io/installation).

```bash
pip install -r requirements.txt
```

### Chạy

Mở trình xem trước của Remotion:

```bash
pnpm studio
```

Render ba khung thử của tập mẫu, ảnh ra `out/stills/`:

```bash
COMP=BridgeShort node scripts/render/bridge-stills.mjs out/stills/x_ 60,700,1460 0.5
```

Render bản cuối 2K trên Modal:

```bash
EPISODE=bridge scripts/render/render-cloud.sh BridgeShort shorts/bridge/audio/mix.wav exports/bridge_2k.mp4
```

Các lệnh khác (render trên máy, kiểm khung) có trong [`cartoon-shorts/README.md`](cartoon-shorts/README.md).

## Giọng đọc

Giọng đọc có thể dùng **ElevenLabs API** hoặc model TTS chạy local. Cả hai dùng chung script
`scripts/voice/voice_local.py` và xuất `voice.wav`, `words.json`, `lines.json`, `report.txt`.

### ElevenLabs

Chạy các lệnh dưới đây trong `cartoon-shorts/`:

1. Cài thư viện: `pip install -r requirements.txt`.
2. Nếu chưa có `.env`, chép từ `.env.example`. Nếu đã có, thêm hai biến dưới đây vào file đó:

   ```dotenv
   ELEVENLABS_API_KEY=your-api-key
   ELEVENLABS_VOICE_ID=your-voice-id
   ```

   Tạo API key có quyền Text to Speech trong tài khoản ElevenLabs; lấy Voice ID từ thư viện giọng.
   Biến môi trường đã export được ưu tiên hơn `.env`. Không ghi API key vào `narration.json`.

3. Tạo thư mục lời đọc và chép cấu hình mẫu:

   ```bash
   mkdir -p shorts/ten-tap/voice
   cp scripts/voice/narration.elevenlabs.example.json shorts/ten-tap/voice/narration.json
   ```

4. Sửa `lines` trong `narration.json`, rồi thu giọng:

   ```bash
   python3 scripts/voice/voice_local.py shorts/ten-tap/voice
   ```

Mẫu dùng `eleven_flash_v2_5` và `language_code: "vi"` cho tiếng Việt. Có thể đổi sang model/ngôn ngữ
được tài khoản hỗ trợ; nếu không khai báo model, mặc định là `eleven_multilingual_v2`.
`voice` trong JSON ghi đè `ELEVENLABS_VOICE_ID`; `speed` từ 0.7 đến 1.2. Có thể thêm `voice_settings`
theo API ElevenLabs (ví dụ `stability`, `similarity_boost`); `speed` cấp ngoài được ưu tiên.

Không cần cài model TTS hay chạy server local. Cần Internet, FFmpeg và credit ElevenLabs; nội dung lời đọc
được gửi đến dịch vụ. Script lấy timestamp của **văn bản gốc** rồi nhóm theo khoảng trắng để giữ đúng
số chữ cho engine. Nếu API trả alignment thiếu hoặc không khớp, script báo lỗi thay vì đoán thời gian.

Mỗi câu được cache trong `out/cache/voice-local/`, theo giọng, model, ngôn ngữ, tốc độ, thiết lập và nội dung.
Chạy lại cùng cấu hình sẽ dùng cache; đổi cấu hình hoặc xoá cache sẽ gọi API lại và có thể tốn credit.
Script không tự thử lại khi API lỗi. Dùng video thương mại cần kiểm tra quyền của giọng và gói ElevenLabs.
Đổi lời đọc cho tập có sẵn có thể cần chỉnh lại timing của hình và trộn lại `mix.wav`.

### TTS local

Script thu giọng gọi model qua một endpoint HTTP trên máy. Server TTS không kèm trong repo.

**Yêu cầu gửi đi**

```http
POST http://127.0.0.1:<port>/api/tts
Content-Type: application/json

{ "text": "Câu cần đọc", "voice": "<voice id>", "speed": 1.0 }
```

**Phản hồi cần có**

```json
{
  "audio": "<file âm thanh, mã hoá base64>",
  "duration": 2.4,
  "engine": "<tên model>",
  "words": [ { "start": 0.00, "end": 0.31 }, { "start": 0.31, "end": 0.58 } ]
}
```

`words` có một phần tử cho mỗi chữ của câu, theo thứ tự.

**Các bước**

| Bước | Việc | Lệnh | Kết quả |
|:-:|---|---|---|
| 1 | Chạy máy chủ TTS local | theo model của bạn | endpoint `/api/tts` |
| 2 | Thu giọng một tập | `python3 scripts/voice/voice_local.py shorts/<tập>/voice` | `voice.wav`, `words.json` |
| 3 | Tạo nhạc và bản trộn | script trong `shorts/<tập>/audio/` | `mix.wav` |

Tập mẫu đã có sẵn `words.json`, nên phần hình render được ngay cả khi chưa thu giọng.

## Cấu hình

Khoá và tài khoản điền vào file `.env`, chép từ `.env.example` cùng thư mục.

| Dịch vụ | Cần gì | Điền ở đâu |
|---|---|---|
| Modal | Tài khoản modal.com, chạy `modal token new` | `~/.modal.toml` (do Modal tự tạo) |
| ElevenLabs | API key, Voice ID | `cartoon-shorts/.env` |
| Facebook | App ID, Page ID, Page access token | `autopost/.env` |

> [!IMPORTANT]
> File `.env` đã nằm trong `.gitignore`. Đừng commit khoá và đừng dán khoá vào issue.

## Cấu trúc thư mục

```text
video-short-animation/
├── cartoon-shorts/              Dự án Remotion
│   ├── src/
│   │   ├── engine/              Engine dùng chung: nhân vật, bối cảnh, ánh sáng, nét mực, màu
│   │   └── videos/bridge/       Mã hình của tập mẫu
│   ├── shorts/bridge/           Kịch bản, giọng, âm thanh của tập mẫu
│   ├── audio/                   Thư viện tổng hợp nhạc và hiệu ứng
│   ├── public/kenney/           Mô hình 3D
│   ├── cloud/                   Render trên Modal
│   └── scripts/
│       ├── voice/               Thu giọng, mốc thời gian, phụ đề
│       ├── render/              Khung thử, render trên máy, render trên Modal
│       ├── qa/                  Kiểm khung, bảng ảnh, bảng nhân vật, kiểm engine
│       └── xuong.py             Ghi tiến trình 11 bước
├── skill/cartoon-3d-short/      Skill cho Claude Code
├── autopost/                    Hẹn giờ đăng Trang Facebook
└── docs/media/                  Hình minh hoạ của README
```

## Dùng với Claude Code

1. Chép thư mục skill vào nơi Claude Code đọc skill:

   ```bash
   cp -R skill/cartoon-3d-short ~/.claude/skills/
   ```

2. Mở Claude Code trong `cartoon-shorts/`.
3. Yêu cầu: *"dùng skill cartoon short, làm một tập về …"*.

## Giấy phép

Phát hành theo giấy phép [MIT](LICENSE).
