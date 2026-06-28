# คู่มือการใช้งาน Local LLM Setup

คู่มือนี้อธิบายวิธีติดตั้ง รัน TUI wizard และ deploy local LLM ด้วย Docker

ดูสถาปัตยกรรมเพิ่มเติมได้ที่ [UML.md](UML.md)

---

## 1. ติดตั้ง (ครั้งแรก)

### ติดตั้งบน server ด้วยคำสั่งเดียว (แนะนำ)

เลียนแบบ [Hermes Agent](https://hermes-agent.nousresearch.com/) — รันบน Linux/macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/PerasutRu/Local_LLM_setup/main/install.sh | bash
```

สคริปต์จะ:

1. ติดตั้ง `uv` และ Python 3.11 (ถ้ายังไม่มี)
2. clone โปรเจกต์ไปที่ `~/.local-llm-setup/app`
3. สร้าง venv และติดตั้งแพ็กเกจ `local-llm-setup`
4. วางคำสั่ง `local-llm-setup` ใน `~/.local/bin`
5. รัน `doctor` ตรวจ Docker/GPU (ข้ามได้ด้วย `--skip-doctor`)

จากนั้นรัน wizard:

```bash
local-llm-setup tui
```

ถ้าต้องการ URL สั้นแบบ Hermes (`https://your-domain/install.sh`) ให้ host ไฟล์ `install.sh` บน GitHub Pages, nginx หรือ Cloudflare แล้วชี้โดเมนมาที่ไฟล์นั้น

> **เจอ `curl: (56) ... 404`?** repo ต้องเป็น **Public** — `raw.githubusercontent.com` ไม่ให้ดาวน์โหลดจาก private repo ไปที่ **GitHub → Settings → Danger zone → Change visibility → Public** แล้วลองใหม่

### ถอนการติดตั้ง (uninstall)

หยุด stack ก่อน (ถ้ามี):

```bash
local-llm-setup stop
# หรือลบ volumes ด้วย: local-llm-setup stop --volumes
```

จากนั้นรัน:

```bash
curl -fsSL https://raw.githubusercontent.com/PerasutRu/Local_LLM_setup/main/uninstall.sh | bash
```

สคริปต์จะลบ:

| รายการ | path |
|--------|------|
| คำสั่ง CLI | `~/.local/bin/local-llm-setup` |
| โค้ด + venv | `~/.local-llm-setup/app` |
| output / profiles | `~/.local-llm-setup/llm_local/output`, `llm_local/profiles` |
| uv ที่ติดตั้งมาพร้อมกัน | `~/.local-llm-setup/bin/uv` |

ตัวเลือก:

```bash
# เก็บ output และ profiles ไว้
curl -fsSL .../uninstall.sh | bash -s -- --keep-data --yes

# เก็บ uv ไว้ (ใช้กับโปรเจกต์อื่นได้)
curl -fsSL .../uninstall.sh | bash -s -- --keep-uv --yes
```

**ไม่ถูกลบอัตโนมัติ:** Docker images/volumes, บรรทัด PATH ใน `~/.bashrc` / `~/.zshrc` (ลบ comment block `# Local LLM Setup` เองถ้าต้องการ)

### ติดตั้งจาก source (นักพัฒนา)

```bash
cd /path/to/local_llm_setup

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

ถ้าติดตั้งแล้ว เปิดใช้งานแค่:

```bash
cd /path/to/local_llm_setup
source .venv/bin/activate
```

---

## 2. รัน TUI Wizard (แนะนำ)

```bash
local-llm-setup tui
```

หรือ

```bash
python -m local_llm_setup tui
```

### คีย์ลัดใน TUI

| ปุ่ม | การทำงาน |
|------|----------|
| `↑` / `↓` หรือ `j` / `k` | เลื่อนเลือก |
| `Space` | เลือก / ยกเลิก (multi-select) |
| `Enter` | ยืนยัน |
| `Tab` | สลับ choice list (ถ้ามีหลายรายการ) |
| `Esc` | ย้อนกลับขั้นก่อนหน้า |
| `q` | ออกจากโปรแกรม |

### Log panel (deploy / stop / `/test`)

หลัง deploy หรือรัน `/test` จะมี **log panel** ด้านล่าง:

| โหมด | คำอธิบาย |
|------|----------|
| **Pretty (ค่าเริ่มต้น)** | แสดง log แบบมีสี — ✓/✗, link สีฟ้า, หัวข้อสีทอง |
| **Copy mode** | ข้อความธรรมดา ลากเลือกแล้ว copy ได้ง่าย |

| ปุ่ม (เมื่อ focus ที่ log) | การทำงาน |
|----------------------------|----------|
| `c` | สลับ Pretty ↔ Copy mode |
| `v` หรือ `Esc` | กลับ Pretty view (จาก Copy mode) |
| `Ctrl+C` / `Cmd+C` | copy ข้อความที่เลือก (ใน Copy mode) |

ข้อความช่วยเหลือจะแสดง **เหนือ log** และใน **แถบ footer** ด้านล่าง

Slash commands ที่ใช้บ่อย: `/deploy` `/test` `/stop` `/help`

### ลำดับขั้นตอนใน Wizard

1. **Doctor** — ตรวจ OS, GPU, Docker, CUDA, nginx
2. **Framework** — เลือก Ollama / vLLM / llama.cpp / SGLang
3. **Mode** — Quick หรือ Full config (รายละเอียดแต่ละ Provider ดู [§7](#7-quick-setup-vs-full-setup-แต่ละ-provider))
4. **Model** — ใส่ชื่อ model และตัวเลือกเพิ่มเติม
5. **Runtime & Docker** — เฉพาะ **Full mode** (port, bind, env, volume, GPU)
6. **Capabilities** — vision, tool calling, MTP ฯลฯ
7. **Nginx** — reverse proxy และ API key (ถ้าต้องการ)
8. **Summary** — เลือก `Generate & start Docker` (default) หรือ generate อย่างเดียว
9. **Done** — generate ไฟล์ และรัน `docker compose up -d` (+ `ollama pull` ถ้าใช้ Ollama)

ไฟล์ที่สร้างจะอยู่ใน `llm_local/output/{profile_name}/` (หรือ path ที่กำหนดใน Full mode)

---

## 3. คำสั่ง CLI อื่นๆ

```bash
# ตรวจสอบเครื่อง (Docker, GPU, CUDA, nginx)
local-llm-setup doctor

# แสดงผลเป็น JSON
local-llm-setup doctor --json

# ตรวจ OS/hardware (เหมือน doctor)
local-llm-setup detect

# Generate และรัน Docker ทันที
local-llm-setup generate --config llm_local/profiles/sample.yaml --run

# รัน stack ที่ generate แล้ว
local-llm-setup run --config llm_local/profiles/default.yaml

# Validate อย่างเดียว ไม่เขียนไฟล์
local-llm-setup generate --config llm_local/profiles/sample.yaml --dry-run

# ระบุ output directory
local-llm-setup generate --config llm_local/profiles/sample.yaml --output ./my-output

# โหลด profile แล้วเปิด TUI
local-llm-setup tui --profile llm_local/profiles/sample.yaml

# ดูคำสั่งทั้งหมด
local-llm-setup --help
```

---

## 4. หลัง Generate แล้ว — รัน LLM ด้วย Docker Compose

ไฟล์ `llm_local/output/docker-compose.yaml` สร้าง **network เดียว** ชื่อ `local_llm` (`local-llm-setup-local_llm`) แล้วเชื่อมทุก container:

```
[host] :8080 ──► nginx ──► ollama:11434
                  ▲              ▲
                  └── cloudflared┘   (network: local_llm)
```

- LLM, nginx, cloudflared อยู่ใน Compose file เดียวกัน คุยผ่านชื่อ service (`ollama`, `vllm`, `nginx`)
- nginx proxy ไป `service_name:port` ภายใน network (ไม่พึ่ง loopback ของ host)
- เมื่อเปิด nginx แล้ว LLM **ไม่ publish port ออก host** — เข้าผ่าน nginx เท่านั้น
- หลาย framework: nginx route ที่ `/ollama/`, `/vllm/` ฯลฯ

ถ้าเลือก **Generate & start Docker** ใน TUI ระบบจะรันให้อัตโนมัติ

หรือรันด้วย CLI:

```bash
local-llm-setup run --config llm_local/profiles/default.yaml
```

หรือ generate พร้อม deploy:

```bash
local-llm-setup generate --config llm_local/profiles/sample.yaml --run
```

รันด้วยมือ:

```bash
cd llm_local/output
docker compose pull
docker compose up -d
```

### คำสั่ง Docker Compose ที่ใช้บ่อย

```bash
docker compose ps
docker compose logs -f nginx
docker compose logs -f ollama
docker network inspect local-llm-setup-local_llm
docker compose exec ollama ollama list
```

### ถ้าเลือก Ollama — pull model

```bash
docker compose exec ollama ollama pull llama3.2
```

เปลี่ยน `llama3.2` เป็นชื่อ model ที่ตั้งไว้ใน wizard

### ตรวจสอบว่ารันสำเร็จ

```bash
docker compose ps
docker compose logs -f
```

### หยุด service

```bash
docker compose down
```

คำสั่งครบถ้วนอยู่ใน `llm_local/output/RUN.md` ที่ generate ให้อัตโนมัติ

---

## 5. รันผ่าน Docker (ไม่ต้องติดตั้ง Python)

เหมาะกับ server ที่ไม่ต้องการติดตั้ง Python บน host:

```bash
docker build -t local-llm-setup .
docker run -it --rm \
  -v "$(pwd)/llm_local/output:/workspace/llm_local/output" \
  local-llm-setup tui
```

ไฟล์ที่ generate จะอยู่ใน `./llm_local/output/` บนเครื่อง host

---

## 6. ไฟล์ที่ได้หลัง Generate

ไฟล์ที่ generate อยู่ใน **`llm_local/output/{profile_name}/`** (default profile ชื่อ `default`)

| ไฟล์ | คำอธิบาย |
|------|----------|
| `docker-compose.yaml` | service ทั้งหมดบน network `local_llm` + nginx (ถ้าเปิด) |
| `.env` | secrets เช่น `HF_TOKEN` |
| `nginx.conf` | reverse proxy config (ถ้าเปิด nginx) |
| `api_keys.map` | API key สำหรับ nginx auth (ถ้าเปิด) |
| `RUN.md` | คำสั่ง copy-paste สำหรับรัน |
| `commands.log` | บันทึกคำสั่งที่รันจริงทุกครั้ง (deploy/stop/test) สำหรับ debug |
| `ACCESS.md` | URL เข้าใช้งานและตัวอย่าง curl |
| `model-{provider}/` | โฟลเดอร์ cache model บน host (bind-mount เข้า container) |

Profile ที่บันทึกจาก TUI อยู่ใน `llm_local/profiles/<ชื่อ>.yaml`

---

## 7. Quick setup vs Full setup (แต่ละ Provider)

### ภาพรวมโหมด

| โหมด | เหมาะกับ | ขั้นตอนเพิ่มใน Wizard |
|------|---------|----------------------|
| **Quick** | เริ่มใช้เร็ว ใส่แค่สิ่งจำเป็น ระบบใส่ค่า default ให้ | Model → Capabilities → Nginx → Summary |
| **Full** | production / tuning ละเอียด — port, GPU, env, vLLM flags, nginx timeout | Model → **Runtime & Docker** → Capabilities → Nginx → Summary |

**Quick** ใช้ค่าเริ่มต้นของแต่ละ Provider (port, `bind_host`, `shm_size`, context length ฯลฯ) และเปิด **Bind to 0.0.0.0** ได้จากขั้น Capabilities

**Full** มีขั้น **Runtime & Docker** แยกต่างหาก — ตั้ง `bind_host`, `port`, `publish_port`, GPU ids, volume ฯลฯ แทน toggle “expose publicly” ในขั้น Capabilities · ดู [พารามิเตอร์ร่วม](#พารามิเตอร์ร่วม-ทุก-provider) สำหรับคำอธิบายทุก field

ทั้งสองโหมด override **Docker image** ได้ (Quick: ขั้น Model · Full: ขั้น Runtime) — ปล่อยว่างเพื่อใช้ image เริ่มต้นที่ wizard แสดง

### Docker image เริ่มต้น

| Provider | Image เริ่มต้น | หมายเหตุ |
|----------|---------------|----------|
| Ollama | `ollama/ollama:latest` | |
| vLLM | `vllm/vllm-openai:latest` | เครื่อง AMD ใช้ `rocm/vllm:latest` อัตโนมัติ |
| llama.cpp | `ghcr.io/ggerganov/llama.cpp:server` | |
| SGLang | `lmsysorg/sglang:latest` | |

ตัวอย่าง override: `ollama/ollama:0.5.4` เมื่อ `latest` ไม่เข้ากับ stack ของคุณ

---

### พารามิเตอร์ร่วม (ทุก Provider)

ตารางด้านล่างใช้ได้กับทุก provider — ฟิลด์บางตัวแสดงเฉพาะ **Full mode** หรือ provider บางตัว (ระบุในคอลัมน์ "ใช้เมื่อ")

| พารามิเตอร์ | ความหมาย | ค่าเริ่มต้น | ตัวอย่างการกรอก | หมายเหตุ |
|-------------|----------|------------|-----------------|----------|
| `profile_name` | ชื่อ instance — ใช้ตั้งชื่อโฟลเดอร์ output, Docker project, container | `default` | `ollama-dev`, `gemma-vllm` | รันหลาย stack บนเครื่องเดียว: ตั้งชื่อไม่ซ้ำกัน |
| `output_dir` | โฟลเดอร์เก็บ compose, nginx, cache | `llm_local/output/{profile_name}` | ปล่อย default | ระบบ derive จาก `profile_name` อัตโนมัติ |
| `model.name` | ชื่อ/ที่อยู่ model ตาม provider | ดูแต่ละ provider | ดูตาราง provider ด้านล่าง | wizard validate ก่อน generate |
| `context_length` | ขนาด context window สูงสุด (tokens) | `8192` | `32768`, `80000`, `131072` | ค่าสูง = ใช้ RAM/VRAM มากขึ้น · Full mode เท่านั้นใน TUI |
| `image_tag` | Docker image ที่ใช้รัน provider | image เริ่มต้นของ provider | `ollama/ollama:0.5.4`, `vllm/vllm-openai:v0.6.3` | **ว่าง** = ใช้ default ที่ wizard แสดง |
| `model_cache_host_path` | โฟลเดอร์บน host เก็บ model ที่ดาวน์โหลด | `.../model-{provider}/` | `/data/llm-cache`, `~/models/ollama` | bind-mount เข้า container · path สัมพัทธ์ resolve จาก output dir |
| `port` | port ที่ service **listen ภายใน container** | 11434 / 8000 / 8080 / 30000 | `8000`, `11435` | ถ้าชนกับ instance อื่น ระบบเลื่อนอัตโนมัติ |
| `publish_port` | port บน **host** ที่ map เข้า `port` ใน container | ว่าง (= ใช้ค่า `port`) | `8002` เมื่อ `port=8000` → `8002:8000` | Full mode · ใช้เมื่อ host port ต้องต่างจาก container port |
| `bind_host` | ที่อยู่ IP บน host ที่เปิดรับ connection | `127.0.0.1` | `0.0.0.0` (ทุก interface), `192.168.1.10` | Quick: ใช้ toggle **Bind to 0.0.0.0** แทน · Full: ตั้งตรงๆ |
| `shm_size` | shared memory ของ container (`/dev/shm`) | `8gb` (Ollama/llama.cpp), `16gb` (vLLM/SGLang) | `32gb`, `64gb` | model ใหญ่ / tensor parallel สูง มักต้องเพิ่ม |
| `extra_env` | ตัวแปร environment เพิ่ม (หนึ่ง `KEY=value` ต่อบรรทัด) | ว่าง | ดูตัวอย่างด้านล่าง | รวม env ของ Ollama ใน Full mode |
| `extra_args` | argument CLI เพิ่มต่อท้ายคำสั่ง serve | ว่าง | `--dtype auto`, `--flash-attn` | vLLM/SGLang/llama.cpp append ต่อท้าย generated command |
| `gpu_count` | จำนวน GPU ที่จอง (เมื่อไม่ระบุ `gpu_device_ids`) | `1` | `2`, `4` | vLLM/SGLang · ใช้กับ Docker GPU reservation |
| `gpu_device_ids` | ระบุ GPU ตัวใดตัวหนึ่ง (comma-separated) | ว่าง | `0`, `0,1`, `1,2` | ตั้ง `NVIDIA_VISIBLE_DEVICES` ให้ตรง · มี priority กว่า `gpu_count` |
| `ipc` | Docker IPC mode | ว่าง | `host` | vLLM บาง model แนะนำ `ipc: host` |
| `extra_volumes` | volume mount เพิ่ม (หนึ่งบรรทัดต่อ mount) | ว่าง | `/mnt/hf-cache:/root/.cache/huggingface` | ถ้า mount ทับ path cache default จะไม่ mount ซ้ำ |
| `command_shell` | script bash แทน generated start command | ว่าง | ดูตัวอย่าง vLLM ด้านล่าง | vLLM Full mode · advanced |

**ตัวอย่าง `extra_env` (หลายบรรทัดใน TUI):**

```text
HF_HOME=/root/.cache/huggingface
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
OLLAMA_NUM_PARALLEL=4
```

**ตัวอย่าง `extra_volumes`:**

```text
/mnt/nvme/huggingface:/root/.cache/huggingface
/mnt/gguf:/models:ro
```

**พารามิเตอร์ Capabilities (ขั้น Capabilities ทุกโหมด):**

| ตัวเลือก | ความหมาย | ตัวอย่างเมื่อเปิด | Provider ที่รองรับ |
|----------|----------|------------------|-------------------|
| Text | text generation (เปิดเสมอ) | — | ทุกตัว |
| Vision | รับ input รูปภาพ | model multimodal เช่น LLaVA, Gemma 4 | Ollama, vLLM, llama.cpp, SGLang |
| Audio | รับ input เสียง | vLLM จะ bootstrap ติดตั้ง `vllm[audio]` ก่อน serve | vLLM เท่านั้น |
| Tool calling | เรียก function/tool | เปิดพร้อม `--enable-auto-tool-choice` (vLLM) | Ollama, vLLM, llama.cpp, SGLang |
| MTP / Speculative | speculative decoding | ใส่ drafter model เช่น `org/small-draft-model` | vLLM, SGLang |
| Bind to 0.0.0.0 | เปิดรับจาก LAN/internet โดยตรง | Quick mode เท่านั้น — ตั้ง `bind_host=0.0.0.0` | แทน `bind_host` ใน Full |

**พารามิเตอร์ Nginx:**

| พารามิเตอร์ | ความหมาย | ค่าเริ่มต้น | ตัวอย่างการกรอก |
|-------------|----------|------------|-----------------|
| `listen_port` | port บน host ที่เข้า nginx | `8080` | `80`, `8443`, `18080` |
| `server_name` | ชื่อ virtual host ของ nginx | `_` (รับทุก host) | `llm.example.com`, `api.local` |
| `bind_host` (nginx) | IP ที่ nginx bind | `0.0.0.0` | `127.0.0.1` (local only) |
| `client_max_body_size` | ขนาด upload สูงสุด | `50m` | `100m`, `1g` (vision/upload รูปใหญ่) |
| `proxy_read_timeout` | timeout รอ response จาก LLM | `600s` | `1800s`, `3600s` (context ยาว / model ช้า) |
| API key auth | บังคับ `X-API-Key` หรือ `Bearer` | ปิด | เลือก `yes_key` ใน wizard |
| CORS | เปิด header CORS | เปิด (Full เลือกได้) | ปิดถ้า client เป็น server-side เท่านั้น |
| cloudflared tunnel | sidecar tunnel ออก internet | เปิดเมื่อมี nginx | ปิดถ้า expose เองผ่าน reverse proxy |

---

### Ollama

#### Quick setup — พารามิเตอร์และตัวอย่าง

| ฟิลด์ใน TUI | ความหมาย | ตัวอย่างการกรอก | ผลหลัง generate |
|-------------|----------|-----------------|-----------------|
| ชื่อ model | tag บน Ollama Library — เหมือน `ollama pull` | `llama3.2` · `qwen2.5:7b` · `mistral:latest` · `dommage/gemma4-e4b-qat:latest` | deploy รัน `ollama pull <ชื่อ>` ให้ |
| Docker image | override image Ollama | ว่าง · `ollama/ollama:0.5.4` | compose ใช้ image ที่ระบุ |
| Model cache path | โฟลเดอร์เก็บ model บน host | ว่าง · `/mnt/ssd/ollama-models` | bind `./model-ollama` → `/root/.ollama` ใน container |

**ค่า default ที่ระบบใส่ให้ (ไม่ต้องกรอกใน Quick):** port `11434`, `bind_host=127.0.0.1`, `context_length=8192`, `shm_size=8gb`, GPU ไม่บังคับ

**ตัวอย่าง Quick — ลอง model บน laptop (local only):**

| ขั้น | กรอก |
|------|------|
| Framework | Ollama |
| Mode | Quick |
| Model name | `llama3.2` |
| Docker image | *(ว่าง)* |
| Model cache | *(ว่าง)* |
| Capabilities | tool calling ✓ · Bind 0.0.0.0 ✗ |
| Nginx | No nginx |
| Summary | Generate & start Docker |

เข้าใช้: `http://127.0.0.1:11434` · ทดสอบ: `curl http://127.0.0.1:11434/api/tags`

**ตัวอย่าง Quick — community model + เปิด LAN:**

| ขั้น | กรอก |
|------|------|
| Model name | `qwen2.5:7b` |
| Capabilities | Bind to 0.0.0.0 ✓ |
| Nginx | Yes nginx — no API key · listen_port `8080` |

เข้าใช้จากเครื่องอื่นใน LAN: `http://<ip-server>:8080/api/tags` (เมื่อเปิด nginx — single framework proxy ที่ `/`)

#### Full setup — พารามิเตอร์และตัวอย่าง

| ฟิลด์ | ความหมาย | ตัวอย่างการกรอก | หมายเหตุ |
|-------|----------|-----------------|----------|
| `context_length` | context window สูงสุด (tokens) | `8192`, `32768` | Ollama ใช้ตอน pull/run ตาม model support |
| `OLLAMA_NUM_PARALLEL` | จำนวน slot ประมวลผลพร้อมกัน | `1`, `2`, `4` | เพิ่มเมื่อมี concurrent users · ใช้ VRAM/RAM มากขึ้น |
| `profile_name` | ชื่อ instance | `ollama-prod` | output → `llm_local/output/ollama-prod/` |
| `port` | listen port ใน container | `11434`, `11435` | sync กับ `OLLAMA_HOST` อัตโนมัติเมื่อ port ถูกเลื่อน |
| `bind_host` | IP bind บน host | `127.0.0.1`, `0.0.0.0` | แทน toggle ใน Capabilities |
| `OLLAMA_MODELS` | path model **ใน container** | `/root/.ollama` | ต้องตรงกับ mount target ของ cache |
| `OLLAMA_HOST` | ที่อยู่ listen **ใน container** | `0.0.0.0:11434` | ถ้า `port=11435` ระบบอาจตั้งเป็น `0.0.0.0:11435` ให้ |
| `shm_size` | shared memory | `8gb`, `16gb` | model ใหญ่หลาย concurrent |
| `extra_env` | env เพิ่ม | `OLLAMA_KEEP_ALIVE=24h` | หนึ่งบรรทัดต่อตัวแปร |

**ตัวอย่าง Full — production หลาย request พร้อมกัน:**

| ขั้น | กรอก |
|------|------|
| Model name | `llama3.2` |
| context_length | `8192` |
| OLLAMA_NUM_PARALLEL | `4` |
| profile_name | `ollama-prod` |
| port | `11434` |
| bind_host | `0.0.0.0` |
| model_cache_host_path | `/mnt/nvme/ollama` |
| shm_size | `16gb` |
| Nginx | yes_key · listen_port `8080` · proxy_read_timeout `1800s` |

**ตัวอย่าง YAML (Full):**

```yaml
profile_name: ollama-prod
frameworks:
  - framework: ollama
    mode: full
    model:
      name: llama3.2
      context_length: 8192
    port: 11434
    bind_host: 0.0.0.0
    shm_size: 16gb
    model_cache_host_path: /mnt/nvme/ollama
    extra_env:
      OLLAMA_NUM_PARALLEL: "4"
      OLLAMA_KEEP_ALIVE: 24h
nginx:
  enabled: true
  listen_port: 8080
  api_key_auth: true
  proxy_read_timeout: 1800s
```

**เมื่อไหร่ใช้:** Quick = dev / ทดลอง · Full = parallel สูง, cache บน disk แยก, nginx timeout ยาว

**หลัง deploy:** ระบบรัน `ollama pull <model>` (ข้ามถ้ามี model บน host แล้ว)

---

### vLLM

#### Quick setup — พารามิเตอร์และตัวอย่าง

| ฟิลด์ใน TUI | ความหมาย | ตัวอย่างการกรอก | หมายเหตุ |
|-------------|----------|-----------------|----------|
| ชื่อ model | Hugging Face repo id (safetensors) | `meta-llama/Meta-Llama-3-8B-Instruct` · `Qwen/Qwen2.5-7B-Instruct` | **ห้าม** ใส่ `.gguf` |
| Docker image | override vLLM image | ว่าง · `vllm/vllm-openai:v0.6.3` | AMD → default `rocm/vllm:latest` |
| Model cache | โฟลเดอร์ cache HF บน host | ว่าง · `/mnt/hf-cache` | mount → `/root/.cache/huggingface` |

**ค่า default (Quick):** port `8000`, `tensor_parallel=1`, `context_length=8192`, `shm_size=16gb`, `gpu_count=1`, `bind_host=127.0.0.1`

**ตัวอย่าง Quick — model มาตรฐาน 1 GPU:**

| ขั้น | กรอก |
|------|------|
| Framework | vLLM |
| Mode | Quick |
| Model name | `meta-llama/Meta-Llama-3-8B-Instruct` |
| Capabilities | tool calling ✓ |
| Nginx | No nginx |

เข้าใช้: `http://127.0.0.1:8000/v1/models` · ต้องมี NVIDIA/AMD GPU + Container Toolkit

**ตัวอย่าง Quick — gated model (token ใน `.env`):**

สร้าง `llm_local/output/default/.env`:

```text
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxx
```

| ขั้น | กรอก |
|------|------|
| Model name | `meta-llama/Llama-3.1-8B-Instruct` |

#### Full setup — พารามิเตอร์และตัวอย่าง

| ฟิลด์ | ความหมาย | ตัวอย่างการกรอก | ผลใน compose |
|-------|----------|-----------------|--------------|
| `quantization` | โหมด quant ของ model | `awq`, `gptq`, `fp8`, `marlin` | `--quantization awq` |
| `tensor_parallel` | แบ่ง model ข้าม GPU | `1`, `2`, `4` | `--tensor-parallel-size 2` |
| `hf_token` / `hf_token_env` | token HF สำหรับ gated model | `hf_abc...` · env name `HF_TOKEN` | เขียนลง `.env` และ inject เป็น env |
| `gpu_memory_utilization` | สัดส่วน VRAM ที่ vLLM ใช้ | `0.3`, `0.85`, `0.95` | `--gpu-memory-utilization 0.3` · ค่าต่ำ = เหลือ VRAM ให้ process อื่น |
| `max_num_seqs` | จำนวน sequence พร้อมกัน | `1`, `4`, `16` | `--max-num-seqs 4` |
| `tool_call_parser` | parser สำหรับ tool calls | `hermes`, `gemma4`, `llama3_json` | `--tool-call-parser gemma4` |
| `reasoning_parser` | parser สำหรับ reasoning model | `gemma4` | `--reasoning-parser gemma4` |
| `kv_cache_dtype` | dtype ของ KV cache | `auto`, `fp8`, `fp8_e5m2` | `--kv-cache-dtype fp8` |
| `limit_mm_per_prompt` | จำกัด multimodal ต่อ prompt (JSON) | `{"image": 4, "audio": 1}` | `--limit-mm-per-prompt '{"image":4,"audio":1}'` |
| `trust_remote_code` | อนุญาต custom code จาก HF | `true`, `false` | `--trust-remote-code` |
| `enable_prefix_caching` | cache prefix ซ้ำ | `true`, `false` | `--enable-prefix-caching` |
| `publish_port` | host port ที่ publish | `8002` (เมื่อ `port=8000`) | `ports: ["0.0.0.0:8002:8000"]` |
| `gpu_device_ids` | pin GPU | `0`, `1`, `0,1` | `device_ids: ["0"]` + `NVIDIA_VISIBLE_DEVICES=0` |
| `ipc` | IPC mode | `host` | `ipc: host` ใน service |
| `command_shell` | script start แทน generated | ดูตัวอย่างด้านล่าง | override ทั้ง entrypoint |
| `extra_args` | flag vLLM เพิ่ม | `--dtype auto`, `--enforce-eager` | append ต่อท้าย `vllm serve` |

**ตัวอย่าง Full — Gemma 4 AWQ multimodal (production):**

| ขั้น | กรอก |
|------|------|
| model.name | `cyankiwi/gemma-4-E4B-it-AWQ-INT4` |
| context_length | `80000` |
| quantization | `awq` |
| gpu_memory_utilization | `0.3` |
| max_num_seqs | `1` |
| tool_call_parser | `gemma4` |
| reasoning_parser | `gemma4` |
| limit_mm_per_prompt | `{"image": 4, "audio": 1}` |
| hf_token | `hf_...` (ถ้า gated) |
| port | `8000` |
| publish_port | `8002` |
| gpu_device_ids | `0` |
| ipc | `host` |
| shm_size | `32gb` |
| Capabilities | vision ✓ · audio ✓ · tool calling ✓ |
| Nginx | yes_nokey · client_max_body_size `100m` · proxy_read_timeout `1800s` |

**ตัวอย่าง `command_shell` (advanced — แทน generated command):**

```bash
pip install -q vllm==0.6.3 && exec vllm serve my-org/custom-model \
  --host 0.0.0.0 --port 8000 --max-model-len 32768 --trust-remote-code
```

**ตัวอย่าง YAML (Full — AWQ 1 GPU):**

```yaml
profile_name: gemma-vllm
frameworks:
  - framework: vllm
    mode: full
    model:
      name: cyankiwi/gemma-4-E4B-it-AWQ-INT4
      context_length: 80000
      quantization: awq
      tensor_parallel: 1
    capabilities:
      text: true
      vision: true
      audio: true
      tool_calling: true
    port: 8000
    publish_port: 8002
    bind_host: 0.0.0.0
    gpu_device_ids: ["0"]
    ipc: host
    shm_size: 32gb
    vllm:
      gpu_memory_utilization: 0.3
      max_num_seqs: 1
      tool_call_parser: gemma4
      reasoning_parser: gemma4
      limit_mm_per_prompt: '{"image": 4, "audio": 1}'
nginx:
  enabled: true
  listen_port: 8080
  client_max_body_size: 100m
  proxy_read_timeout: 1800s
hf_token: hf_xxxxxxxx
```

**เมื่อไหร่ใช้:** Quick = HF model มาตรฐาน · Full = AWQ/GPTQ, multimodal, pin GPU, memory tuning

**ข้อจำกัด:** ต้องมี GPU (NVIDIA/AMD) · ไม่รองรับ Apple Silicon · ไม่รองรับ GGUF

---

### llama.cpp

#### Quick setup — พารามิเตอร์และตัวอย่าง

| ฟิลด์ใน TUI | ความหมาย | ตัวอย่างการกรอก | หมายเหตุ |
|-------------|----------|-----------------|----------|
| ชื่อ model | path ไฟล์ `.gguf` **ใน container** หรือ URL | `/models/llama-3.2-8b.Q4_K_M.gguf` · `https://huggingface.co/.../model.gguf` | mount host → `/models` |
| Docker image | override llama.cpp server image | ว่าง · `ghcr.io/ggerganov/llama.cpp:server-cuda` | เลือก tag ตาม CPU/GPU |
| Model cache | โฟลเดอร์เก็บ GGUF บน host | ว่าง · `/home/user/gguf` | bind → `/models` ใน container |

**เตรียมไฟล์ GGUF ก่อน deploy:**

```bash
mkdir -p llm_local/output/my-gguf/model-llamacpp
cp ~/Downloads/llama-3.2-8b.Q4_K_M.gguf llm_local/output/my-gguf/model-llamacpp/
```

**ตัวอย่าง Quick — รัน GGUF บน CPU (Mac/Linux):**

| ขั้น | กรอก |
|------|------|
| Framework | llama.cpp |
| Mode | Quick |
| Model name | `/models/llama-3.2-8b.Q4_K_M.gguf` |
| Capabilities | tool calling ✓ |
| Nginx | No nginx |

เข้าใช้: `http://127.0.0.1:8080/health` · OpenAI-compatible API ที่ port `8080`

#### Full setup — พารามิเตอร์และตัวอย่าง

| ฟิลด์ | ความหมาย | ตัวอย่างการกรอก | ผลใน compose |
|-------|----------|-----------------|--------------|
| `context_length` | context window (tokens) | `4096`, `8192`, `32768` | `--ctx-size 8192` |
| `n_gpu_layers` | จำนวน layer ที่ offload ไป GPU | `0` (CPU only) · `35` · `99` (เกือบทั้งหมด) | `--n-gpu-layers 35` ใน extra_args |
| `port` / `publish_port` | networking | `8080` · publish `9080` | `9080:8080` บน host |
| `bind_host` | IP bind | `127.0.0.1`, `0.0.0.0` | |
| `extra_args` | flag server เพิ่ม | `--threads 8`, `--batch-size 512` | append ต่อท้าย command |

**ตัวอย่าง Full — GGUF + GPU offload บน Linux:**

| ขั้น | กรอก |
|------|------|
| model.name | `/models/mistral-7b.Q5_K_M.gguf` |
| context_length | `8192` |
| n_gpu_layers | `35` |
| port | `8080` |
| bind_host | `0.0.0.0` |
| extra_args | `--threads 8` |
| Capabilities | vision ✓ (ถ้า model รองรับ) |

**ตัวอย่าง Full — Apple Silicon (Metal, CPU+GPU hybrid):**

| ขั้น | กรอก |
|------|------|
| n_gpu_layers | `99` |
| extra_args | *(ว่าง หรือตาม docs image)* |

**ตัวอย่าง YAML (Full):**

```yaml
profile_name: gguf-local
frameworks:
  - framework: llamacpp
    mode: full
    model:
      name: /models/llama-3.2-8b.Q4_K_M.gguf
      context_length: 8192
    port: 8080
    bind_host: 127.0.0.1
    shm_size: 8gb
    extra_args:
      - --n-gpu-layers
      - "35"
      - --threads
      - "8"
```

> **Tip:** ใน TUI Full mode ใส่ `n_gpu_layers` ในขั้น Model — ระบบแปลงเป็น `--n-gpu-layers` ให้อัตโนมัติ · ใน YAML ใส่ใน `extra_args` ได้เช่นกัน

**เมื่อไหร่ใช้:** Quick = มีไฟล์ GGUF พร้อม · Full = tune GPU layers, threads, port

---

### SGLang

#### Quick setup — พารามิเตอร์และตัวอย่าง

| ฟิลด์ใน TUI | ความหมาย | ตัวอย่างการกรอก | หมายเหตุ |
|-------------|----------|-----------------|----------|
| ชื่อ model | Hugging Face repo id | `meta-llama/Meta-Llama-3-8B-Instruct` · `Qwen/Qwen2.5-7B-Instruct` | ไม่รองรับ GGUF |
| Docker image | override SGLang image | ว่าง · `lmsysorg/sglang:v0.4.1` | |
| Model cache | โฟลเดอร์ cache HF | ว่าง · `/mnt/hf-cache` | mount → `/root/.cache/huggingface` |

**ค่า default (Quick):** port `30000`, `tensor_parallel=1`, `context_length=8192`, `shm_size=16gb`, `gpu_count=1`

**ตัวอย่าง Quick — structured generation บน 1 GPU:**

| ขั้น | กรอก |
|------|------|
| Framework | SGLang |
| Mode | Quick |
| Model name | `meta-llama/Meta-Llama-3-8B-Instruct` |
| Capabilities | tool calling ✓ |
| Nginx | No nginx |

เข้าใช้: `http://127.0.0.1:30000/v1/models`

#### Full setup — พารามิเตอร์และตัวอย่าง

| ฟิลด์ | ความหมาย | ตัวอย่างการกรอก | ผลใน compose |
|-------|----------|-----------------|--------------|
| `quantization` | โหมด quant | `awq`, `gptq`, `fp8` | `--quantization awq` |
| `tensor_parallel` | tensor parallel size | `1`, `2`, `4` | `--tp 2` |
| `context_length` | context window | `8192`, `32768` | `--context-length 32768` |
| `hf_token` | token HF | `hf_...` | inject เป็น env |
| `gpu_count` / `gpu_device_ids` | จอง/pin GPU | `2` · `0,1` | Docker GPU reservation |
| `publish_port` | host port map | `30001` (เมื่อ `port=30000`) | `30001:30000` |
| `extra_args` | flag SGLang เพิ่ม | `--mem-fraction-static 0.85` | append ต่อท้าย launch command |
| MTP + drafter | speculative decoding | drafter: `org/small-draft-model` | `--speculative-draft-model-path ...` |

**ตัวอย่าง Full — AWQ + multi-GPU + MTP:**

| ขั้น | กรอก |
|------|------|
| model.name | `Qwen/Qwen2.5-14B-Instruct-AWQ` |
| context_length | `32768` |
| quantization | `awq` |
| tensor_parallel | `2` |
| gpu_device_ids | `0,1` |
| port | `30000` |
| publish_port | `30001` |
| shm_size | `32gb` |
| Capabilities | tool calling ✓ · MTP ✓ |
| mtp_drafter | `Qwen/Qwen2.5-0.5B-Instruct` |
| hf_token | `hf_...` (ถ้า gated) |

**ตัวอย่าง YAML (Full):**

```yaml
profile_name: sglang-qwen
frameworks:
  - framework: sglang
    mode: full
    model:
      name: Qwen/Qwen2.5-14B-Instruct-AWQ
      context_length: 32768
      quantization: awq
      tensor_parallel: 2
    capabilities:
      text: true
      tool_calling: true
      mtp: true
      mtp_drafter_model: Qwen/Qwen2.5-0.5B-Instruct
    port: 30000
    publish_port: 30001
    bind_host: 0.0.0.0
    gpu_device_ids: ["0", "1"]
    shm_size: 32gb
hf_token: hf_xxxxxxxx
```

**เมื่อไหร่ใช้:** Quick = serve HF มาตรฐาน · Full = quantization, multi-GPU, MTP

**ข้อจำกัด:** ต้องมี GPU · ไม่รองรับ Apple Silicon · ไม่รองรับ GGUF

---

### Nginx ใน Quick vs Full

| ตัวเลือก | Quick | Full |
|----------|-------|------|
| เปิด/ปิด nginx + API key | ✓ (no / yes_nokey / yes_key) | ✓ |
| `listen_port` | ✓ (default `8080`) | ✓ |
| `server_name`, `bind_host` | ใช้ default | ตั้งเอง |
| `client_max_body_size` | default `50m` | ตั้งเอง (สำคัญกับ upload รูป/ไฟล์ใหญ่) |
| `proxy_read_timeout` | default `600s` | ตั้งเอง (model ช้า / context ยาว) |
| CORS | default เปิด | เลือกได้ |
| cloudflared tunnel | default เปิดเมื่อมี nginx | เลือกได้ |

**ตัวอย่างกรอก Nginx — Quick (local dev + API key):**

| ขั้น | กรอก |
|------|------|
| nginx choice | Yes nginx — with API key |
| listen_port | `8080` |

curl ทดสอบ:

```bash
curl -H "X-API-Key: your-key-from-api_keys.map" \
  http://127.0.0.1:8080/ollama/api/tags
```

**ตัวอย่างกรอก Nginx — Full (vision model + tunnel):**

| ขั้น | กรอก |
|------|------|
| nginx choice | Yes nginx — no API key |
| listen_port | `8080` |
| server_name | `llm.mycompany.local` |
| bind_host | `0.0.0.0` |
| client_max_body_size | `100m` |
| proxy_read_timeout | `1800s` |
| CORS | ✓ |
| cloudflared tunnel | ✓ |

หลัง deploy ดู URL tunnel ใน `ACCESS.md` หรือ log panel

**ความสัมพันธ์ port สำคัญ (Full mode):**

```text
# vLLM: container listen 8000 แต่ host ใช้ 8002
port: 8000
publish_port: 8002
→ docker ports: "0.0.0.0:8002:8000"

# nginx แยกต่างหาก — client ภายนอกเข้า listen_port ของ nginx
nginx.listen_port: 8080
→ http://host:8080/v1/chat/completions   # single framework: proxy ที่ /
→ http://host:8080/vllm/...              # หลาย framework: prefix /vllm/, /ollama/ ฯลฯ
```

เมื่อเปิด nginx แล้ว LLM มัก **publish port ตรงออก host ด้วย** (เพื่อ debug) แต่ client ควรเข้าผ่าน nginx path เช่น `/ollama/`, `/vllm/`

---

### สรุปเลือกโหมด

| สถานการณ์ | แนะนำ |
|-----------|-------|
| ลอง model ครั้งแรก / dev บน laptop | **Quick** + Ollama หรือ llama.cpp |
| Model Hugging Face มาตรฐาน 1 GPU | **Quick** + vLLM หรือ SGLang |
| AWQ/GPTQ, multimodal, audio, pin GPU | **Full** + vLLM |
| หลาย instance บนเครื่องเดียว | **Full** — ตั้ง `profile_name`, `port`, `publish_port` แยกกัน |
| GGUF บน CPU หรือ Mac | **Quick/Full** + llama.cpp + `n_gpu_layers` ใน Full |

Profile ที่บันทึกจาก TUI อยู่ที่ `llm_local/profiles/<ชื่อ>.yaml` — แก้ YAML แล้ว `local-llm-setup tui --profile ...` หรือ `generate --run` ได้

---

## 8. เลือก Framework ให้ถูก (สรุปสั้น)

| Framework | ชื่อ model ที่ใส่ | ต้องมี GPU |
|-----------|-------------------|------------|
| Ollama | `llama3.2`, `llama3.2:latest` | ไม่จำเป็น |
| vLLM | `org/model` จาก Hugging Face | จำเป็น (NVIDIA/AMD) |
| llama.cpp | path หรือ URL ของไฟล์ `.gguf` | ไม่จำเป็น |
| SGLang | `org/model` จาก Hugging Face | จำเป็น |

**หมายเหตุ:** vLLM และ SGLang **ไม่รองรับ GGUF** โดยตรง · รายละเอียด Quick/Full ครบอยู่ใน [§7](#7-quick-setup-vs-full-setup-แต่ละ-provider)

---

## 9. แก้ปัญหาเบื้องต้น

**Docker not found**
- macOS: `brew install --cask docker`
- Linux: `curl -fsSL https://get.docker.com | sh`

**GPU ไม่ทำงานใน container**
- ติดตั้ง NVIDIA driver + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

**vLLM/SGLang error บน Mac (Apple Silicon)**
- ใช้ Ollama หรือ llama.cpp แทน

**Port ชน**
- ระบบจะเลือก port ถัดไปที่ว่างอัตโนมัติตอน generate/deploy — รวมกรณีรัน **หลาย framework พร้อมกัน** (Ollama + vLLM + …) โดยแต่ละตัวจะได้ port ค่าเริ่มต้นของตัวเอง (`11434`, `8000`, `8080`, `30000`) หรือเลื่อนไปถัดไปถ้าซ้ำ

**Model จาก Hugging Face ต้อง login**
- ใส่ `HF_TOKEN` ใน wizard หรือใน `.env`

---

## 10. Development

```bash
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

---

## สรุปเร็ว

```bash
source .venv/bin/activate
local-llm-setup tui                    # ทำตาม wizard (Quick หรือ Full — ดู §7)
cd llm_local/output/default            # เปลี่ยน default เป็นชื่อ profile ของคุณ
docker compose up -d                   # รัน LLM
```
