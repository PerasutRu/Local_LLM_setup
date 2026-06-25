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
| output / profiles | `~/.local-llm-setup/output`, `profiles` |
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

### ลำดับขั้นตอนใน Wizard

1. **Doctor** — ตรวจ OS, GPU, Docker, CUDA, nginx
2. **Framework** — เลือก Ollama / vLLM / llama.cpp / SGLang
3. **Mode** — Quick หรือ Full config
4. **Model** — ใส่ชื่อ model และตัวเลือกเพิ่มเติม
5. **Capabilities** — vision, tool calling, MTP ฯลฯ
6. **Nginx** — reverse proxy และ API key (ถ้าต้องการ)
7. **Summary** — เลือก `Generate & start Docker` (default) หรือ generate อย่างเดียว
8. **Done** — generate ไฟล์ และรัน `docker compose up -d` (+ `ollama pull` ถ้าใช้ Ollama)

ไฟล์ที่สร้างจะอยู่ใน `./output/` (หรือ path ที่กำหนด)

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
local-llm-setup generate --config profiles/sample.yaml --run

# รัน stack ที่ generate แล้ว
local-llm-setup run --config profiles/default.yaml

# Validate อย่างเดียว ไม่เขียนไฟล์
local-llm-setup generate --config profiles/sample.yaml --dry-run

# ระบุ output directory
local-llm-setup generate --config profiles/sample.yaml --output ./my-output

# โหลด profile แล้วเปิด TUI
local-llm-setup tui --profile profiles/sample.yaml

# ดูคำสั่งทั้งหมด
local-llm-setup --help
```

---

## 4. หลัง Generate แล้ว — รัน LLM จริง

ถ้าเลือก **Generate & start Docker** ใน TUI ระบบจะรันให้อัตโนมัติ

หรือรันด้วย CLI:

```bash
local-llm-setup run --config profiles/default.yaml
```

หรือ generate พร้อม deploy:

```bash
local-llm-setup generate --config profiles/sample.yaml --run
```

รันด้วยมือ:

```bash
cd output
docker compose pull
docker compose up -d
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

คำสั่งครบถ้วนอยู่ใน `output/RUN.md` ที่ generate ให้อัตโนมัติ

---

## 5. รันผ่าน Docker (ไม่ต้องติดตั้ง Python)

เหมาะกับ server ที่ไม่ต้องการติดตั้ง Python บน host:

```bash
docker build -t local-llm-setup .
docker run -it --rm \
  -v "$(pwd)/output:/workspace/output" \
  local-llm-setup tui
```

ไฟล์ที่ generate จะอยู่ใน `./output/` บนเครื่อง host

---

## 6. ไฟล์ที่ได้หลัง Generate

| ไฟล์ | คำอธิบาย |
|------|----------|
| `docker-compose.yaml` | service ของ framework + nginx (ถ้าเปิด) |
| `.env` | secrets เช่น `HF_TOKEN` |
| `nginx.conf` | reverse proxy config (ถ้าเปิด nginx) |
| `api_keys.map` | API key สำหรับ nginx auth (ถ้าเปิด) |
| `RUN.md` | คำสั่ง copy-paste สำหรับรัน |

Profile ที่บันทึกจาก TUI อยู่ใน `profiles/<ชื่อ>.yaml`

---

## 7. เลือก Framework ให้ถูก

| Framework | ชื่อ model ที่ใส่ | ต้องมี GPU |
|-----------|-------------------|------------|
| Ollama | `llama3.2`, `llama3.2:latest` | ไม่จำเป็น |
| vLLM | `org/model` จาก Hugging Face | จำเป็น (NVIDIA/AMD) |
| llama.cpp | path หรือ URL ของไฟล์ `.gguf` | ไม่จำเป็น |
| SGLang | `org/model` จาก Hugging Face | จำเป็น |

**หมายเหตุ:** vLLM และ SGLang **ไม่รองรับ GGUF** โดยตรง

---

## 8. แก้ปัญหาเบื้องต้น

**Docker not found**
- macOS: `brew install --cask docker`
- Linux: `curl -fsSL https://get.docker.com | sh`

**GPU ไม่ทำงานใน container**
- ติดตั้ง NVIDIA driver + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

**vLLM/SGLang error บน Mac (Apple Silicon)**
- ใช้ Ollama หรือ llama.cpp แทน

**Port ชน**
- เปลี่ยน port ใน Full config mode หรือหยุด service ที่ใช้ port นั้น

**Model จาก Hugging Face ต้อง login**
- ใส่ `HF_TOKEN` ใน wizard หรือใน `.env`

---

## 9. Development

```bash
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

---

## สรุปเร็ว

```bash
source .venv/bin/activate
local-llm-setup tui          # ทำตาม wizard
cd output
docker compose up -d         # รัน LLM
```
