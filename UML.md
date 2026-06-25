# UML — Local LLM Setup

เอกสารนี้อธิบายสถาปัตยกรรมของ `local-llm-setup` ด้วย UML diagrams (Mermaid) อ้างอิงจากโค้ดใน `src/local_llm_setup/`

---

## 1. Package / Component Diagram

แสดงโมดูลหลักและความสัมพันธ์ระหว่าง layer

```mermaid
flowchart TB
    subgraph entry [Entry Layer]
        CLI[cli.py<br/>Typer commands]
        Main[__main__.py]
    end

    subgraph ui [UI Layer]
        TUI[tui/app.py<br/>LocalLLMSetupApp]
        Widgets[tui/widgets.py<br/>ChoiceList ChoiceItem]
    end

    subgraph core [Core Layer]
        Models[models/config.py<br/>Pydantic schemas]
        Validation[models/validation.py<br/>Model name rules]
        Frameworks[frameworks/<br/>Plugin registry]
        Detect[detect/host.py<br/>Doctor checks]
        Profiles[profiles/store.py<br/>YAML I/O]
        Renderers[renderers/<br/>Artifact generation]
    end

    subgraph output [Generated Artifacts]
        Compose[docker-compose.yaml]
        Env[.env]
        NginxConf[nginx.conf]
        ApiKeys[api_keys.map]
        RunMd[RUN.md]
    end

    Main --> CLI
    CLI --> TUI
    CLI --> Detect
    CLI --> Profiles
    CLI --> Renderers

    TUI --> Widgets
    TUI --> Detect
    TUI --> Frameworks
    TUI --> Models
    TUI --> Profiles
    TUI --> Renderers

    Frameworks --> Models
    Frameworks --> Validation
    Detect --> Models
    Profiles --> Models
    Renderers --> Frameworks
    Renderers --> Models

    Renderers --> Compose
    Renderers --> Env
    Renderers --> NginxConf
    Renderers --> ApiKeys
    Renderers --> RunMd
```

---

## 2. Class Diagram — Domain Models

โมเดลกลางที่ใช้ร่วมกันระหว่าง CLI, TUI, renderers และ tests

```mermaid
classDiagram
    class SetupConfig {
        +str profile_name
        +Path output_dir
        +HostInfo host
        +list~FrameworkConfig~ frameworks
        +NginxConfig nginx
        +str hf_token
        +primary_framework() FrameworkConfig
    }

    class HostInfo {
        +OSType os_type
        +str os_version
        +str arch
        +bool is_wsl
        +GPUVendor gpu_vendor
        +str gpu_name
        +float vram_gb
        +float ram_gb
        +bool docker_installed
        +bool compose_installed
        +str nvidia_driver
        +str cuda_version
        +bool nvidia_container_toolkit
        +list~DoctorCheck~ checks
    }

    class DoctorCheck {
        +str name
        +CheckStatus status
        +str message
        +str hint
    }

    class FrameworkConfig {
        +Framework framework
        +ConfigMode mode
        +ModelConfig model
        +Capabilities capabilities
        +int port
        +str bind_host
        +str image_tag
        +int gpu_count
        +str shm_size
    }

    class ModelConfig {
        +str name
        +str quantization
        +int context_length
        +int tensor_parallel
        +str hf_token_env
    }

    class Capabilities {
        +bool text
        +bool vision
        +bool audio
        +bool tool_calling
        +bool mtp
        +str mtp_drafter_model
    }

    class NginxConfig {
        +bool enabled
        +int listen_port
        +str server_name
        +int upstream_port
        +bool enable_cors
        +bool api_key_auth
        +list~ApiKeyEntry~ api_keys
    }

    class ApiKeyEntry {
        +str key
        +str label
    }

    class GeneratedOutput {
        +str compose_yaml
        +str env_file
        +str nginx_conf
        +str api_keys_map
        +list~str~ run_commands
        +list~str~ warnings
    }

    class ValidationIssue {
        +str level
        +str message
        +str field
    }

    class Framework {
        <<enumeration>>
        OLLAMA
        VLLM
        LLAMACPP
        SGLANG
    }

    class OSType {
        <<enumeration>>
        LINUX
        MACOS
        WINDOWS
        WSL
        UNKNOWN
    }

    class GPUVendor {
        <<enumeration>>
        NVIDIA
        AMD
        APPLE
        NONE
        UNKNOWN
    }

    SetupConfig "1" --> "0..1" HostInfo
    SetupConfig "1" --> "*" FrameworkConfig
    SetupConfig "1" --> "1" NginxConfig
    FrameworkConfig "1" --> "1" ModelConfig
    FrameworkConfig "1" --> "1" Capabilities
    FrameworkConfig --> Framework
    NginxConfig "1" --> "*" ApiKeyEntry
    HostInfo "1" --> "*" DoctorCheck
    HostInfo --> OSType
    HostInfo --> GPUVendor
```

---

## 3. Class Diagram — Framework Plugins

แต่ละ inference framework เป็น plugin ที่มี metadata, defaults และ validation ของตัวเอง

```mermaid
classDiagram
    class FrameworkPlugin {
        <<abstract>>
        +FrameworkMeta meta
        +default_config(model_name, mode) FrameworkConfig
        +validate(config, host) list~ValidationIssue~
        +image_for_host(host, tag) str
    }

    class FrameworkMeta {
        +Framework framework
        +str display_name
        +str description
        +int default_port
        +str default_image
        +bool supports_gguf
        +bool supports_hf
        +bool supports_vision
        +bool supports_audio
        +bool supports_tool_calling
        +bool supports_mtp
        +bool requires_gpu
        +dict quick_defaults
    }

    class OllamaPlugin {
        +default_config()
        +validate()
    }

    class VllmPlugin {
        +default_config()
        +validate()
        +image_for_host()
    }

    class LlamaCppPlugin {
        +default_config()
        +validate()
    }

    class SglangPlugin {
        +default_config()
        +validate()
    }

    class FrameworkRegistry {
        +get_plugin(framework) FrameworkPlugin
        +list_frameworks() list
        +validate_setup(configs, host) list~ValidationIssue~
    }

    FrameworkPlugin <|-- OllamaPlugin
    FrameworkPlugin <|-- VllmPlugin
    FrameworkPlugin <|-- LlamaCppPlugin
    FrameworkPlugin <|-- SglangPlugin
    FrameworkPlugin "1" --> "1" FrameworkMeta
    FrameworkRegistry --> FrameworkPlugin
    FrameworkRegistry ..> validate_model_name : uses
```

| Plugin | Model source | GGUF | GPU | MTP |
|--------|-------------|------|-----|-----|
| OllamaPlugin | Ollama registry | No | Optional | No |
| VllmPlugin | Hugging Face | No | Required | Yes |
| LlamaCppPlugin | GGUF path/URL | Yes | Optional | No |
| SglangPlugin | Hugging Face | No | Required | Yes |

---

## 4. Class Diagram — TUI

```mermaid
classDiagram
    class App {
        <<Textual>>
    }

    class LocalLLMSetupApp {
        +WizardState state
        +int _step_idx
        +_show_step()
        +_next()
        +_back()
        +_step_doctor()
        +_step_framework()
        +_step_mode()
        +_step_model()
        +_step_capabilities()
        +_step_nginx()
        +_step_summary()
        +_step_done()
    }

    class WizardState {
        +Path output_dir
        +HostInfo host
        +Framework framework
        +ConfigMode mode
        +str model_name
        +Capabilities capabilities
        +bool nginx_enabled
        +to_config() SetupConfig
    }

    class ChoiceList {
        +bool multi
        +key_up()
        +key_down()
        +key_space()
        +key_enter()
        +selected_ids() list~str~
    }

    class ChoiceItem {
        +str choice_id
        +str choice_label
        +bool selected
        +bool checked
        +toggle_checked()
    }

    class ChoiceListSubmitted {
        <<Message>>
        +list selected_ids
        +bool multi
    }

    App <|-- LocalLLMSetupApp
    LocalLLMSetupApp --> WizardState
    LocalLLMSetupApp --> ChoiceList
    ChoiceList "1" --> "*" ChoiceItem
    ChoiceList --> ChoiceListSubmitted
```

---

## 5. State Diagram — TUI Wizard Steps

```mermaid
stateDiagram-v2
    [*] --> Doctor: local-llm-setup tui

    Doctor --> Framework: Continue
    Framework --> Mode: Select framework
    Mode --> Model: Quick / Full
    Model --> Capabilities: Enter model name
    Capabilities --> Nginx: Select caps + bind
    Nginx --> Summary: Continue
    Summary --> Done: Generate
    Summary --> Capabilities: Esc (if errors)
    Done --> [*]

    state Doctor {
        [*] --> RunDetect
        RunDetect --> ShowChecks
        ShowChecks --> [*]
    }

    state Summary {
        [*] --> BuildConfig
        BuildConfig --> ValidateSetup
        ValidateSetup --> ShowIssues: has errors
        ValidateSetup --> ConfirmGenerate: ok
        ShowIssues --> [*]
        ConfirmGenerate --> [*]
    }

    state Done {
        [*] --> GenerateFiles
        GenerateFiles --> SaveProfile
        SaveProfile --> ShowRunCommands
        ShowRunCommands --> [*]
    }
```

ลำดับ step ตาม `STEPS` ใน `tui/app.py`:

```
doctor → framework → mode → model → capabilities → nginx → summary → done
```

---

## 6. Sequence Diagram — TUI Wizard (Happy Path)

```mermaid
sequenceDiagram
    actor User
    participant CLI as cli.tui
    participant App as LocalLLMSetupApp
    participant State as WizardState
    participant Detect as detect.host
    participant FW as FrameworkRegistry
    participant Val as validate_setup
    participant Gen as renderers.generate
    participant Prof as profiles.store

    User->>CLI: local-llm-setup tui
    CLI->>App: run_tui(output_dir)

    App->>State: __init__
    State->>Detect: detect_host()
    Detect-->>State: HostInfo

    App->>User: Step doctor (checks + hints)
    User->>App: Continue

    App->>User: Step framework
    User->>App: Select ollama/vllm/llamacpp/sglang
    App->>State: framework = ...

    App->>User: Step mode (quick/full)
    User->>App: Select mode

    App->>User: Step model
    User->>App: Enter model name + options

    App->>User: Step capabilities
    User->>App: Space toggle + Enter

    App->>User: Step nginx
    User->>App: Configure proxy + API keys

    App->>State: to_config()
    State->>FW: get_plugin().default_config()
    State-->>App: SetupConfig

    App->>Val: validate_setup(frameworks, host)
    Val-->>App: ValidationIssue[]

    App->>User: Summary (confirm generate)
    User->>App: Generate

    App->>Gen: generate(config)
    Gen->>Val: validate_setup()
    Gen->>Gen: render_compose / nginx / env
    Gen-->>App: GeneratedOutput

    App->>Prof: save_profile(config)
    App->>User: Show run commands + API keys
```

---

## 7. Sequence Diagram — `generate` Command

```mermaid
sequenceDiagram
    actor User
    participant CLI as cli.generate_cmd
    participant Prof as profiles.store
    participant Gen as renderers.generate
    participant Val as validate_setup
    participant Compose as renderers.compose
    participant Nginx as renderers.nginx
    participant FS as Filesystem

    User->>CLI: generate --config profiles/sample.yaml
    CLI->>Prof: load_profile(path)
    Prof-->>CLI: SetupConfig

    CLI->>Gen: generate(config, dry_run=false)

    Gen->>Val: validate_setup(frameworks, host)
    alt validation errors
        Val-->>Gen: ValidationIssue[level=error]
        Gen-->>CLI: raise ValueError
        CLI-->>User: Error message
    else validation ok
        Val-->>Gen: warnings

        Gen->>Compose: render_compose(config)
        Compose-->>Gen: compose_yaml

        Gen->>Compose: render_env(config)
        Compose-->>Gen: env_file

        opt nginx.enabled
            Gen->>Nginx: render_nginx_conf(config)
            Nginx-->>Gen: nginx_conf
            Gen->>Nginx: render_api_keys_map(config)
            Nginx-->>Gen: api_keys_map
        end

        Gen->>Compose: render_run_commands(config)
        Compose-->>Gen: run_commands[]

        Gen->>FS: write docker-compose.yaml
        Gen->>FS: write .env
        Gen->>FS: write nginx.conf (optional)
        Gen->>FS: write api_keys.map (optional)
        Gen->>FS: write RUN.md

        Gen-->>CLI: GeneratedOutput
        CLI-->>User: Success + run commands
    end
```

---

## 8. Sequence Diagram — `doctor` Command

```mermaid
sequenceDiagram
    actor User
    participant CLI as cli.doctor
    participant Detect as detect.host
    participant OS as platform/subprocess
    participant Rich as rich.Console

    User->>CLI: doctor [--json]
    CLI->>Detect: run_doctor()

    Detect->>OS: detect_os()
    Detect->>OS: detect_docker()
    Detect->>OS: detect_compose()
    Detect->>OS: detect_gpu() / nvidia-smi
    Detect->>OS: detect_nvidia() / nvcc
    Detect->>OS: detect_rocm()
    Detect->>OS: detect_nginx()
    Detect->>Detect: build DoctorCheck list + install hints

    Detect-->>CLI: HostInfo

    alt --json
        CLI->>Rich: print_json(HostInfo)
    else table view
        CLI->>Rich: Table(checks)
    end

    CLI-->>User: Doctor report
```

---

## 9. Deployment Diagram

```mermaid
flowchart LR
    subgraph host [Host Machine]
        subgraph cli_mode [CLI Mode]
            UserCLI[User]
            Venv[Python venv<br/>local-llm-setup]
            OutDir[./output/]
        end

        subgraph docker_mode [Dockerized Setup App]
            UserDocker[User]
            SetupContainer[local-llm-setup container]
            MountVol[/workspace/output]
        end

        subgraph runtime [Generated Runtime]
            DockerEngine[Docker Engine]
            LLMContainer[ollama / vllm / llamacpp / sglang]
            NginxContainer[nginx optional]
        end
    end

    UserCLI --> Venv
    Venv --> OutDir

    UserDocker --> SetupContainer
    SetupContainer --> MountVol

    OutDir --> DockerEngine
    MountVol --> DockerEngine
    DockerEngine --> LLMContainer
    DockerEngine --> NginxContainer
    NginxContainer -->|proxy| LLMContainer
```

---

## 10. Activity Diagram — Validation Pipeline

```mermaid
flowchart TD
    Start([SetupConfig]) --> ModelVal[validate_model_name per framework]
    ModelVal --> CapVal[check_capabilities per plugin]
    CapVal --> HostVal[Host/GPU checks per plugin]
    HostVal --> PortVal[Port conflict check]
    PortVal --> Collect{Any errors?}

    Collect -->|Yes| Fail([raise ValueError])
    Collect -->|No| Render[Render artifacts]
    Render --> Write[Write files to output_dir]
    Write --> Done([GeneratedOutput])
```

ระดับความรุนแรงของ `ValidationIssue`:

| level | ผลลัพธ์ |
|-------|---------|
| `error` | หยุด generate |
| `warn` | แสดงเตือน แต่ generate ต่อได้ |
| `info` | แจ้งข้อมูลเพิ่มเติม |

---

## 11. File Map

```
src/local_llm_setup/
├── cli.py                 # Typer: tui, doctor, detect, generate, save
├── __main__.py            # python -m local_llm_setup
├── detect/
│   └── host.py            # OS/GPU/Docker doctor
├── frameworks/
│   ├── base.py            # FrameworkPlugin ABC, FrameworkMeta
│   ├── ollama.py
│   ├── vllm.py
│   ├── llamacpp.py
│   ├── sglang.py
│   └── __init__.py        # Registry + validate_setup()
├── models/
│   ├── config.py          # Pydantic domain models
│   └── validation.py      # Model name format rules
├── profiles/
│   └── store.py           # YAML save/load
├── renderers/
│   ├── compose.py         # docker-compose.yaml, .env, RUN.md
│   ├── nginx.py           # nginx.conf, api_keys.map
│   └── __init__.py        # generate()
└── tui/
    ├── app.py             # LocalLLMSetupApp wizard
    └── widgets.py         # ChoiceList, ChoiceItem
```

---

## 12. CLI Commands Overview

```mermaid
flowchart LR
    Root[local-llm-setup]

    Root --> TUI[tui<br/>Interactive wizard]
    Root --> Doctor[doctor<br/>Dependency checks]
    Root --> Detect[detect<br/>Alias of doctor]
    Root --> Generate[generate<br/>From YAML profile]
    Root --> Save[save<br/>Save profile]

    TUI --> Out1[output/]
    Generate --> Out2[output/]
```

---

## การอ่าน diagram

- เปิดไฟล์นี้ใน GitHub, GitLab หรือ VS Code (Markdown Preview) เพื่อ render Mermaid
- Class diagram แสดง **โครงสร้างข้อมูล** ไม่ใช่ทุก method ในโค้ด
- Sequence diagram แสดง **flow หลัก** ของ happy path; error handling ย่อไว้ใน validation pipeline
