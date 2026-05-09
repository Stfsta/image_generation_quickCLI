# Suchuang API Image Generator (e.g. GPT-image-2) v0.2.1

A convenient image generation script based on the Suchuang API proxy station, supporting contextual conversation memory for iterative image refinement. Uses the `gpt-image-2` model, compatible with the OpenAI interface calling method.

[English](README.md)
[简体中文](docs/README.zh-CN.md)

## Features

- Direct call to Suchuang API station image generation interface, no complex configuration required
- Supports **conversation history memory**, allowing gradual image modification across multiple rounds of dialogue
- Command-line interaction, input Chinese/English prompts to generate images
- Automatically saves generated images to local `generated_images/` directory
- Local configuration file management for API keys, no pollution of system environment variables
- **Modular architecture**: config, history, API client, business logic, CLI layered decoupling
- **Connection pooling & auto-retry**: HTTP session reuse with exponential backoff retry
- **Atomic history file writes**: prevents data corruption
- **Safer history persistence**: lock-protected history updates with atomic file writes
- **Runtime language switch**: `lang en|zh` persists in `config.json`
- **Portable auto-reference import**: put images into `reference_images/` and they are auto-detected when no explicit ref is provided
- Lightweight, readable code structure, easy for secondary development

## Requirements

- Python 3.10 or higher
- Installed dependencies: `requests`, `Pillow`

Install dependencies (recommended):

```bash
pip install -r requirements.txt
```

Alternatively (minimal/manual):

```bash
pip install requests Pillow
```

Optional: install as a package and use the `image-generator` command:

```bash
pip install .
```

## Getting Suchuang API Key

1. Go to [Suchuang API Station](https://api.suchuang.vip) to register and log in.
2. In the console, navigate to **API Keys** page, click **Add Token** to create a new token.
3. Copy the generated key (format: `sk-xxxxxxxxxxxxxxxx`).

> **Note**: Ensure your account has sufficient balance, otherwise image generation will fail due to insufficient credits.

## Model and Endpoint Notes

- Default model is `gpt-image-2` (Suchuang platform naming).  
If your route/account rejects it, switch `model` in `config.json` to `gpt-image-1`, `dall-e-3`, or `dall-e-2`.
- Recommended host config is:
  ```json
  "api_base": "https://api.suchuang.vip"
  ```
  The client builds endpoints automatically:
  - `POST /v1/images/generations` for text-to-image and fallback reference-image flow
  - `POST /v1/images/edits` for local PNG edit flow
- Legacy `base_url` (full endpoint URL) is still backward compatible, but `api_base` is recommended for new configs.

## Quick Start

### 1. First Run & Configuration

Run the script:

```bash
python image_generator.py
```

On first run, a `config.json` file will be automatically generated in the current working directory, and you will be prompted to edit the key. Open the file with a text editor and replace the `api_key` field value with your real key (example):

```json
{
  "api_key": "sk-your-real-key",
  "api_base": "https://api.suchuang.vip",
  "base_url": "https://api.suchuang.vip/v1/images/generations",
  "model": "gpt-image-2",
  "language": "en",
  "image_dir": "./generated_images",
  "reference_dir": "./reference_images",
  "history_file": "chat_memory.json",
  "max_history": 10,
  "timeout": 90,
  "max_retries": 3,
  "retry_delay": 1.0,
  "default_size": "1024x1024"
}
```

Save and run again.

### 2. Generate Image with Text Prompt

After successful startup, the command line prompt looks like this:

`Prompt/Command >` in English mode, and `提示词/命令 >` in Chinese mode.

Simply enter an English or Chinese description and press Enter to generate an image. For example:

`Prompt/Command > A cute cat wearing a wizard hat`

After generation is complete, the image will be saved in the `generated_images/` folder, with a filename containing a timestamp.

### 3. Continuous Dialogue to Adjust Image

The script remembers previous conversation content. You can continuously input new requirements, and the AI will combine the historical description to generate new images. For example:

`Prompt/Command > Change the cat to golden fur`

The script will automatically concatenate the previous generation result (simplified description) with the new requirement to form a complete prompt for resubmission.

### 4. Image-to-Image Generation

The `gpt-image-2` model supports image-to-image generation. You can provide reference images along with your prompt. The script supports **four styles**:

#### Style 1: Inline syntax (recommended)

Include the image reference directly in your prompt:

`Prompt/Command > [image:/path/to/reference_image.jpg] Make the background a sunset scene`

#### Style 2: Command-line parameter syntax

Use `--ref` before your prompt:

`Prompt/Command > --ref /path/to/reference_image.jpg Make the background a sunset scene`

#### Style 3: Session-level reference image

Set a reference image that will be used for all subsequent generations in the current session until you run `ref clear` or switch sessions:

`Prompt/Command > ref /path/to/reference_image.jpg`  
`Prompt/Command > Make the background a sunset scene`  
`Prompt/Command > Add more clouds`  
`Prompt/Command > ref clear`

#### Style 4: Auto-reference directory (new)

When you do not pass `--ref`, `ref ...`, or `[image:...]`, the CLI scans `reference_images/` and automatically uses all image files (`.png/.jpg/.jpeg/.webp`) as references.

- If all detected files are local PNG and <= 4MB, the request uses `/v1/images/edits`.
- Otherwise it falls back to `/v1/images/generations`.
- If the folder is empty (or does not exist), generation works as text-only by default.

You can also use a URL as the reference image:

`Prompt/Command > --ref https://example.com/reference.png Add snow effect to this image`

**Notes for image-to-image:**

- Local PNG references (`.png`, <= 4MB) are sent to `/v1/images/edits` as `multipart/form-data`.
- URL references and non-PNG local references fall back to `/v1/images/generations` via private `image_url` extension behavior.
- The edits API supports optional `mask`, but the current CLI does not expose a dedicated `--mask` flag yet.
- Single-image and multi-image references are both supported.

#### Pseudo Multi-Reference Collage Mode (new)

To improve compatibility with platforms that clearly document only single-image edits, you can enable collage mode in `config.json`:

```json
{
  "multi_ref_mode": "collage",
  "collage_max_refs": 4,
  "collage_layout": "auto",
  "collage_canvas": 1024,
  "collage_annotate": true,
  "collage_prompt_hint": true
}
```

- In `collage` mode, multiple local references are merged into one PNG collage and sent to `/v1/images/edits`.
- If collage creation fails, the app automatically falls back to direct multi-reference behavior.
- If URL references are present, collage is skipped and direct behavior is used.
- `multi_ref_mode: off` keeps only the first reference image.

### 5. Output Size Settings

You can control the output image dimensions through the following methods:

#### Method A: Include size in your prompt

Use one of the supported size formats directly in your prompt:

`Prompt/Command > [size:1792x1024] A panoramic landscape view`

You can also use temporary CLI flag syntax:

`Prompt/Command > --size 1024x1792 A portrait fantasy character`

Supported size values (union of official model capabilities):


| Size        | Aspect Ratio | Description             |
| ----------- | ------------ | ----------------------- |
| `256x256`   | 1:1          | `dall-e-2` small        |
| `512x512`   | 1:1          | `dall-e-2` medium       |
| `1024x1024` | 1:1          | Common/default          |
| `1536x1024` | 3:2          | `gpt-image-1` landscape |
| `1024x1536` | 2:3          | `gpt-image-1` portrait  |
| `1792x1024` | 16:9         | `dall-e-3` landscape    |
| `1024x1792` | 9:16         | `dall-e-3` portrait     |
| `auto`      | auto         | `gpt-image-1` auto size |


#### Method B: Modify config.json

Edit the `config.json` file to add a `default_size` field:

```json
{
  "api_key": "sk-your-key",
  "default_size": "1792x1024",
  ...
}
```

Invalid sizes are ignored with a warning, and generation falls back to the next available source (`--size`/`[size:...]`/`default_size`).

#### Method C: Programmatic usage

When using the library as a module:

```python
from image_generator import ImageGenerationService

service = ImageGenerationService()
service.generate("A beautiful sunset", size="1792x1024")
```

### 6. Available Commands


| Command               | Description                         |
| --------------------- | ----------------------------------- |
| `exit` / `quit` / `q` | Exit the program                    |
| `clear`               | Clear current session history       |
| `session`             | Show current session ID             |
| `session <id>`        | Switch to specified session ID      |
| `ref <path/url>`      | Set session-level reference image   |
| `ref clear`           | Clear session-level reference image |
| `lang [en/zh]`        | Show or switch CLI display language |
| `language [en/zh]`    | Alias of `lang`                     |
| `help`                | Show help information               |


### 7. Exit Program

Type `exit`, `quit`, or `q` to exit.

## Configuration

Adjust the following parameters by editing `config.json`:


| Variable       | Description                                                                                                  | Default                                          |
| -------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------ |
| `api_key`      | Suchuang API key                                                                                             | —                                                |
| `api_base`     | API host (recommended)                                                                                       | `https://api.suchuang.vip`                       |
| `base_url`     | Legacy full endpoint URL (compatible)                                                                        | `https://api.suchuang.vip/v1/images/generations` |
| `model`        | Model name to use                                                                                            | `gpt-image-2`                                    |
| `language`     | CLI display language (`en` / `zh`)                                                                           | `en`                                             |
| `image_dir`    | Image save directory                                                                                         | `./generated_images`                             |
| `reference_dir`| Auto-reference directory scanned when no explicit reference is given                                         | `./reference_images`                             |
| `max_history`  | Maximum dialogue rounds to keep                                                                              | 10                                               |
| `history_file` | Conversation history storage file                                                                            | `chat_memory.json`                               |
| `timeout`      | API request timeout (seconds)                                                                                | 90                                               |
| `max_retries`  | Maximum retry attempts on failure                                                                            | 3                                                |
| `retry_delay`  | Base retry delay (seconds)                                                                                   | 1.0                                              |
| `default_size` | Default output size (`256x256`/`512x512`/`1024x1024`/`1536x1024`/`1024x1536`/`1792x1024`/`1024x1792`/`auto`) | `1024x1024`                                      |
| `multi_ref_mode` | Multi-reference strategy (`off`/`direct`/`collage`)                                                        | `direct`                                         |
| `collage_max_refs` | Max references used when `multi_ref_mode=collage`                                                        | 4                                                |
| `collage_layout` | Collage layout strategy (`auto`/`horizontal`/`grid`)                                                        | `auto`                                           |
| `collage_canvas` | Collage output square canvas size (px)                                                                       | 1024                                             |
| `collage_annotate` | Add A/B/C labels to collage tiles                                                                          | `true`                                           |
| `collage_keep_temp` | Keep generated temporary collage files for debugging                                                      | `false`                                          |
| `collage_prompt_hint` | Auto-inject label mapping hints into prompt                                                            | `true`                                           |


Path behavior note: `config.json`, `chat_memory.json`, `generated_images/`, and `reference_images/` are all resolved relative to the current working directory where you run the command.
Response compatibility note: the client supports both `data[].url` and `data[].b64_json`; when both are absent, generation is treated as failed.

## Project Structure

```
.
├── image_generator.py          # Compatible entry point (calls CLI in package)
├── image_generator/            # Core package
│   ├── __init__.py
│   ├── version.py              # Single source of truth for project version
│   ├── api_client.py           # HTTP client (connection pooling, retry)
│   ├── cli.py                  # Command-line interface
│   ├── config.py               # Configuration management & validation
│   ├── history.py              # Conversation history (thread-safe, atomic writes)
│   ├── image_service.py        # Business logic orchestration
│   └── reference_collage.py    # Multi-reference collage composition utility
├── docs/                       # Documentation
│   └── README.zh-CN.md         # Chinese version of this document
├── scripts/
│   └── sync_version.py         # Sync visible version strings in docs
├── .gitignore                  # Git ignore configuration
├── README.md                   # Project documentation (English)
├── config.json                 # Configuration file (auto-generated on first run)
├── chat_memory.json            # Conversation history (auto-generated)
├── generated_images/           # Generated images (auto-created)
└── reference_images/           # Optional auto-reference import directory
```

### Version Bump Workflow

- Single source of truth: `image_generator/version.py` (`__version__`)
- Update once there, then sync display strings:
  ```bash
  python scripts/sync_version.py
  ```
- This keeps CLI banner and package version source aligned, while updating visible version strings in docs/snapshot with one command.

## FAQ

**Q: What if it says "config.json generated" on first run?**  
A: This is the normal guidance process. Edit `config.json` as prompted to enter your key, then run again.

**Q: Generation fails with HTTP error?**  
A: Check if the key is correct, account balance is sufficient, and network can access `api.suchuang.vip`. The script will automatically retry recoverable errors (such as 429/500/502/503/504).

**Q: Where is the conversation history saved?**  
A: It is saved in the `chat_memory.json` file in the current directory. You can delete this file to clear memory, or type `clear` in interactive mode.

**Q: Can I generate multiple images at once?**  
A: The current CLI defaults to 1 image per request (`n=1`) and does not expose `n` as a command flag. For programmatic usage, adjust `n` when calling `generate()`.

**Q: What if the key is leaked or I want to change the key?**  
A: Directly edit `config.json` to modify the `api_key` field, or delete the file and run again to generate a new template.

## Notes

- **Key security**: Do not upload `config.json` containing real keys to public repositories. It is recommended to add `config.json` to `.gitignore`.
- **Usage limits**: Image generation will consume Suchuang account credits. Confirm your balance before frequent calls.
- **Network latency**: The generation process requires waiting for the API to return results. Depending on network and server load, it may take tens of seconds.

## Example Dialogue

```
Prompt/Command | 提示词/命令 > A cyberpunk-style city at night
[Prompt/提示词] A cyberpunk-style city at night
[Saved/已保存] generated_images/image_20240508_223044.png
[Complete/完成] Image generated: generated_images/image_20240508_223044.png
----------------------------------------
Prompt/Command | 提示词/命令 > Add rain and neon light reflections
[Prompt/提示词] Dialogue history / 对话历史:
user: A cyberpunk-style city at night
assistant: [Image generated / 已生成图片]

Latest request / 最新要求: Add rain and neon light reflections
[Saved/已保存] generated_images/image_20240508_223112.png
[Complete/完成] Image generated: generated_images/image_20240508_223112.png
```

---

*This tool is developed based on Suchuang API station documentation, for learning and personal use only.*