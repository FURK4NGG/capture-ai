#!/usr/bin/env python3
import sys
import json
import base64
import mimetypes
import base64
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timezone

import requests

CONFIG_PATH = Path.home() / ".config" / "capture-ai" / "config.json"
CACHE_BASE = Path.home() / ".cache" / "capture-ai"
REFS_CACHE_DIR = CACHE_BASE / "refs"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

GLOBAL_SYSTEM_PROMPT = (
    "Bu konuşmada sana zaman zaman e-posta, kod, komut, yapılandırma dosyası "
    "veya birebir kopyalanması gereken metinler yazdırılabilir.\n\n"

    "FORMAT KURALI:\n"
    "Eğer kullanıcıdan gelen istekte doğrudan kopyalanabilir bir içerik "
    "(örneğin kod, script, terminal komutu, yapılandırma dosyası vb.) "
    "üretmen gerekiyorsa aşağıdaki formatı kullan:\n\n"

    "title\n"
    "<kısa ve açıklayıcı başlık>\n"
    "title\n"
    "copy\n"
    "<kod veya kopyalanacak içerik>\n"
    "copy\n\n"

    "Kurallar:\n"
    "- 'title' ve 'copy' kelimeleri tek başına satır olmalıdır.\n"
    "- 'title' bloğu kod bloğundan önce gelmelidir.\n"
    "- Kod yoksa bu formatı kullanma.\n"
    "- Normal sohbet cevaplarında bu formatı kullanma.\n"
    "- Sadece gerçekten kopyalanabilir içerik varsa bu formatı kullan.\n"

    "\n\n[FILE] BLOKLARI HAKKINDA:\n"
    "- Eğer kullanıcı bir dosya eklediyse, dosya içeriği bu mesaj içinde "
    "[FILE] ... [CONTENT] ... [/CONTENT] formatında ZATEN verilmiştir.\n"
    "- Bu durumda kullanıcıdan 'kodu buraya yapıştır' veya 'dosyayı paylaş' deme.\n"
    "- Değişiklik gerekiyorsa [CONTENT] içeriğini okuyarak işlem yap.\n"
    "- Dosya içeriğini tekrar isteme.\n"
    "- path alanı olarak [FILE] bloğunda verilen path değerini aynen kullan.\n"

    "\n\nDOSYA DEĞİŞİKLİĞİ KURALI:\n"
    "- [FILE] bloklarında 'editable: true' ise dosyada değişiklik önerebilirsin.\n"
    "- 'editable: false' olan dosyalar için ASLA dosyaya uygulanacak değişiklik isteme.\n"
    "- editable:false dosyalar için apply bloğu üretme.\n"
    "- Eğer değişiklik gerekmiyorsa apply bloğu hiç koyma.\n"

    "\n\nAPPLY (OTOMATİK UYGULAMA) PROTOKOLÜ:\n"
    "Eğer ve sadece eğer kullanıcı 'editable: true' bir dosyada değişiklik istiyorsa,\n"
    "cevabının SONUNA aşağıdaki blok formatıyla ekle (başka yerde kullanma):\n\n"

    "apply\n"
    "[\n"
    "  {\n"
    "    \"path\": \"/absolute/path/to/file\",\n"
    "    \"find\": \"DOSYADA BİREBİR GEÇEN ANCHOR METİN\",\n"
    "    \"mode\": \"before|after|replace\",\n"
    "    \"text\": \"EKLENECEK/YERİNE GEÇECEK METİN\"\n"
    "  }\n"
    "]\n"
    "apply\n\n"

    "Kurallar:\n"
    "- 'apply' kelimesi tek başına satır olmalı (başlangıç ve bitiş).\n"
    "- apply bloğunun içi SADECE JSON olmalı (başka açıklama koyma).\n"
    "- JSON sadece object/array olmalı, yorum (//) veya trailing virgül olamaz.\n"
    "- mode sadece: before, after, replace.\n"
    "- path MUTLAKA absolute path olmalı.\n"
    "- find, dosyada birebir bulunan kısa/orta bir anchor olmalı.\n"
    "- text, eklenecek içerik ve sonunda '\\n' gerekiyorsa ekle.\n"
    "\n\nAPPLY ÖZET SATIRI KURALI:\n"
    "- Eğer apply bloğu üretiyorsan, 'Başarıyla yaptım' gibi kesin/bitmiş ifade ASLA kullanma.\n"
    "- apply bloğundan ÖNCE sadece 1 satır özet yaz.\n"
    "- Özet formatı TAM olarak şu olsun:\n"
    "  'Bu satırı <MODE> ediyorum: <FIND>  ->  <TEXT>'\n"
    "  MODE: replace|before|after\n"
    "- <FIND> ve <TEXT> çok uzunsa 120 karakterde kes ve '...' ekle.\n"
    "- Özet dışında ekstra açıklama yazma.\n"
)

def _safe_read_text(path: Path, max_bytes: int = 250_000) -> str:
    try:
        data = path.read_bytes()
        if len(data) > max_bytes:
            data = data[:max_bytes]
        return data.decode("utf-8", errors="replace")
    except Exception as e:
        return f"[Dosya okunamadı: {e}]"


def _is_text_file(path: Path) -> bool:
    ext = path.suffix.lower()
    return ext in {
        ".txt", ".md", ".py", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
        ".sh", ".bash", ".zsh", ".js", ".ts", ".tsx", ".jsx", ".css", ".html", ".xml",
        ".c", ".cpp", ".h", ".hpp", ".rs", ".go", ".java", ".kt", ".cs", ".sql"
    }

def _img_path_to_data_url(p: str) -> str | None:
    try:
        fp = Path(p)
        if not fp.exists():
            return None
        mime, _ = mimetypes.guess_type(str(fp))
        if not mime:
            mime = "image/png"
        b64 = base64.b64encode(fp.read_bytes()).decode("utf-8")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None

def _die(msg: str, code: int = 1):
    sys.stderr.write(msg + "\n")
    sys.exit(code)


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        _die("Config dosyası bulunamadı.", 1)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception as e:
        _die(f"Config okunamadı: {e}", 1)


def _save_config(cfg: dict):
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # config yazılamasa bile AI çalışsın
        pass


def _parse_selected_indexes(arg: str) -> list[int]:
    out = []
    if not arg:
        return out
    for x in arg.split(","):
        x = x.strip()
        if x.isdigit():
            out.append(int(x))

    # uniq + stable
    seen = set()
    uniq = []
    for i in out:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    return uniq


def _mime_for(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def _data_url_for_image(path: Path) -> str:
    mime = _mime_for(path)
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _role_map(chat_role: str) -> str:
    return "assistant" if chat_role == "bot" else "user"


def _safe_chat_key(chat_file: Path) -> str:
    return chat_file.stem.replace("/", "_").replace("\\", "_")


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _copy_to_cache(src: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    base = src.stem.replace(" ", "_")
    ext = src.suffix or ".img"
    dest = dest_dir / f"{base}{ext}"
    if dest.exists():
        dest = dest_dir / f"{base}_{_utc_stamp()}{ext}"
    shutil.copy2(src, dest)
    return dest


def _build_blocks_and_cache_info(msg: dict, cache_images_dir: Path | None):
    blocks = []
    cached_image = None

    # 1) Text
    txt = msg.get("content") or ""
    if txt:
        blocks.append({"type": "text", "text": txt})

    # 2) Images (legacy "image" + new "images")
    imgs = []
    one = msg.get("image")
    if one:
        imgs.append(one)

    many = msg.get("images")
    if isinstance(many, list):
        imgs.extend([str(x) for x in many if x])

    # uniq
    seen = set()
    uniq_imgs = []
    for p in imgs:
        if p not in seen:
            seen.add(p)
            uniq_imgs.append(p)

    for img_raw in uniq_imgs:
        img_path = Path(img_raw)
        if not img_path.exists():
            continue

        if cache_images_dir is not None:
            try:
                cached_image = _copy_to_cache(img_path, cache_images_dir)
            except Exception:
                cached_image = cached_image  # önceki varsa kalsın

        try:
            blocks.append({
                "type": "image_url",
                "image_url": {"url": _data_url_for_image(img_path)}
            })
        except Exception:
            pass

    # 3) Files (new: "files": [{"path","name","edit"}])
    files = msg.get("files") or []
    if isinstance(files, list):
        for f in files:
            if not isinstance(f, dict):
                continue

            p_raw = str(f.get("path") or "").strip()
            if not p_raw:
                continue
            p = Path(p_raw)
            if not p.exists() or not p.is_file():
                continue

            editable = bool(f.get("edit"))
            name = (f.get("name") or p.name or "").strip()
            mime = _mime_for(p)

            if _is_text_file(p):
                file_text = _safe_read_text(p)
                blocks.append({
                    "type": "text",
                    "text": (
                        "\n[FILE]\n"
                        f"name: {name}\n"
                        f"path: {str(p)}\n"
                        f"mime: {mime}\n"
                        f"editable: {'true' if editable else 'false'}\n"
                        "type: text\n"
                        "[CONTENT]\n"
                        f"{file_text}\n"
                        "[/CONTENT]\n"
                        "[/FILE]\n"
                    )
                })
            else:
                # Excel/PDF/DOCX vb. şu an içerik aktarmıyoruz (metadata gönderiyoruz)
                blocks.append({
                    "type": "text",
                    "text": (
                        "\n[FILE]\n"
                        f"name: {name}\n"
                        f"path: {str(p)}\n"
                        f"mime: {mime}\n"
                        f"editable: {'true' if editable else 'false'}\n"
                        "type: binary_or_unsupported_preview\n"
                        "note: Bu dosya türü şu an içerik olarak gönderilmiyor.\n"
                        "[/FILE]\n"
                    )
                })

    if not blocks:
        blocks = [{"type": "text", "text": ""}]

    return blocks, (str(cached_image) if cached_image else None)


def _pick_model(cfg: dict, chat_file: Path, cli_model: str | None) -> str:
    """
    Öncelik:
      1) CLI --model verilmişse onu kullan (alternatif)
      2) chat_models[chat_file.name]
      3) ai_models[0] (en üst = en son kullanılan)
    Eğer chat'in modeli config'te yoksa/silinmişse otomatik ai_models[0]'a düzeltir.
    """
    models = cfg.get("ai_models", [])
    if not isinstance(models, list):
        models = []
    models = [str(m).strip() for m in models if str(m).strip()]

    if not models:
        _die("Config içinde ai_models boş. En az 1 model olmalı.", 1)

    if cli_model:
        return str(cli_model).strip()

    chat_models = cfg.get("chat_models", {})
    if not isinstance(chat_models, dict):
        chat_models = {}

    chat_key = chat_file.name
    chosen = str(chat_models.get(chat_key) or "").strip()

    if (not chosen) or (chosen not in models):
        chosen = models[0]
        chat_models[chat_key] = chosen
        cfg["chat_models"] = chat_models
        _save_config(cfg)

    return chosen


def main():
    # Args
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("chat_file", nargs="?")
    parser.add_argument("selected_indexes", nargs="?")
    parser.add_argument("--model", dest="model", default=None)

    if len(sys.argv) < 2:
        sys.exit(1)

    args, _unknown = parser.parse_known_args()

    if not args.chat_file:
        sys.exit(1)

    chat_file = Path(args.chat_file)
    if not chat_file.exists():
        sys.exit(1)

    selected_indexes = []
    if args.selected_indexes:
        try:
            selected_indexes = _parse_selected_indexes(args.selected_indexes)
        except Exception:
            selected_indexes = []

    # Config + API key
    cfg = _load_config()
    API_KEY = (cfg.get("open_router_key") or "").strip()
    if not API_KEY:
        _die("OpenRouter API Key bulunamadı.", 1)

    # model seçimi (chat’e göre)
    model_name = _pick_model(cfg, chat_file, args.model)

    # Read chat
    try:
        messages = json.loads(chat_file.read_text(encoding="utf-8")) or []
    except Exception as e:
        _die(f"Chat okunamadı: {e}", 1)

    if not messages:
        sys.exit(0)

    last = messages[-1]
    final_messages = []
    editable_map = {}  # path(str) -> bool

    final_messages.append({
        "role": "system",
        "content": GLOBAL_SYSTEM_PROMPT
    })

    # Cache setup
    REFS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Reference system (TEXT + IMAGE) + CACHE
    if selected_indexes:
        chat_key = _safe_chat_key(chat_file)
        bundle_id = _utc_stamp()
        bundle_dir = REFS_CACHE_DIR / chat_key / bundle_id
        bundle_images_dir = bundle_dir / "images"
        bundle_dir.mkdir(parents=True, exist_ok=True)

        final_messages.append({
            "role": "system",
            "content": (
                "Aşağıdaki mesajlar sadece son kullanıcı mesajını anlaman için referans olarak verilmiştir. "
                "Bu mesajlara cevap verme. Sadece en son kullanıcı mesajını yanıtla."
            )
        })

        cache_items = []
        for i in selected_indexes:
            if i < len(messages) - 1:
                msg = messages[i]
                role = _role_map(msg.get("role"))

                # editable_map doldur (referans mesajın file edit izinleri)
                files_meta = msg.get("files") or []
                if isinstance(files_meta, list):
                    for ff in files_meta:
                        if not isinstance(ff, dict):
                            continue
                        p_raw = str(ff.get("path") or "").strip()
                        if not p_raw:
                            continue
                        editable_map[p_raw] = bool(ff.get("edit"))

                # images?
                if msg.get("image") and Path(str(msg["image"])).exists():
                    has_any_attach = True
                imgs = msg.get("images")
                if isinstance(imgs, list) and any(Path(str(p)).exists() for p in imgs):
                    has_any_attach = True

                # files?
                files = msg.get("files")
                if isinstance(files, list) and any(Path(str(f.get("path") or "")).exists() for f in files if isinstance(f, dict)):
                    has_any_attach = True

                if has_any_attach:
                    blocks, cached_img = _build_blocks_and_cache_info(msg, bundle_images_dir)
                    final_messages.append({"role": role, "content": blocks})
                else:
                    final_messages.append({"role": role, "content": msg.get("content", "")})
                    cached_img = None

                cache_items.append({
                    "index": i,
                    "role": msg.get("role", ""),
                    "content": msg.get("content", ""),
                    "image_original": msg.get("image", None),
                    "image_cached": cached_img
                })

        bundle = {
            "bundle_id": bundle_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "chat_file": str(chat_file),
            "selected_indexes": selected_indexes,
            "items": cache_items
        }
        try:
            (bundle_dir / "bundle.json").write_text(
                json.dumps(bundle, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception:
            pass

    # Last message (answer) - TEXT + (image / images)
    # last message editable_map doldur
    files_last = last.get("files") or []
    if isinstance(files_last, list):
        for ff in files_last:
            if not isinstance(ff, dict):
                continue
            p_raw = str(ff.get("path") or "").strip()
            if not p_raw:
                continue
            editable_map[p_raw] = bool(ff.get("edit"))

    # Last message (answer) - TEXT + (images/files)
    role = _role_map(last.get("role"))

    has_any_attach = False

    # images?
    if last.get("image") and Path(str(last["image"])).exists():
        has_any_attach = True

    imgs = last.get("images")
    if isinstance(imgs, list) and any(Path(str(p)).exists() for p in imgs):
        has_any_attach = True

    # files?
    files = last.get("files")
    if isinstance(files, list) and any(
        Path(str(f.get("path") or "")).exists()
        for f in files
        if isinstance(f, dict)
    ):
        has_any_attach = True

    if has_any_attach:
        blocks, _ = _build_blocks_and_cache_info(last, cache_images_dir=None)
        final_messages.append({"role": role, "content": blocks})
    else:
        final_messages.append({"role": role, "content": last.get("content", "")})

    # Payload
    payload = {
        "model": model_name,
        "messages": final_messages,
        "max_tokens": 5120
    }

    # Request
    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost",
                "X-Title": "capture-ai"
            },
            json=payload,
            timeout=120
        )

        if response.status_code != 200:
            sys.stderr.write(f"OpenRouter API ERROR ({response.status_code}): {response.text}\n")
            sys.exit(1)

        data = response.json()

        try:
            reply = data["choices"][0]["message"]["content"]
        except Exception:
            sys.stderr.write("OpenRouter beklenmeyen cevap formatı döndürdü.\n")
            sys.exit(1)

    except requests.exceptions.Timeout:
        sys.stderr.write("İstek zaman aşımına uğradı (timeout).\n")
        sys.exit(1)

    except requests.exceptions.ConnectionError:
        sys.stderr.write("Bağlantı hatası. İnternet bağlantınızı kontrol edin.\n")
        sys.exit(1)

    except Exception as e:
        sys.stderr.write(f"AI ERROR: {str(e)}\n")
        sys.exit(1)

    # Save bot reply
    messages.append({"role": "bot", "content": reply})

    try:
        chat_file.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        sys.stderr.write(f"Chat yazılamadı: {e}\n")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
