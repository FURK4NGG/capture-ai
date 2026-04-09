#!/usr/bin/env python3
import os
import sys
import json
import base64
import shutil
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime

CONFIG_PATH = Path.home() / ".config" / "capture-ai" / "config.json"
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

BASE_DIR = Path.home() / ".cache" / "capture-ai"
CHAT_DIR = BASE_DIR / "chats"
AI_SCRIPT = str(Path.home() / "capture-ai" / "ai.py")
GENERATED_DIR = BASE_DIR / "generated_images"

CHAT_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_DIR.mkdir(parents=True, exist_ok=True)


def fix_mojibake(s: str) -> str:
    if not s:
        return s
    if ("Ã" not in s) and ("Å" not in s) and ("â" not in s):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except Exception:
        return s


class ChatCLI:
    def __init__(self):
        self.pending_images = []
        self.pending_files = []

        cfg = self.load_config()
        last_chat_name = str(cfg.get("last_chat", "default.json") or "default.json").strip()
        if not last_chat_name:
            last_chat_name = "default.json"

        self.current_chat = CHAT_DIR / last_chat_name
        if not self.current_chat.exists():
            self.current_chat.write_text("[]", encoding="utf-8")

        self.ensure_base_config()
        self.ensure_ui_i18n_config()
        self.active_model = self.get_chat_model(self.current_chat)

    def clear_screen(self):
        os.system("clear")

    def _read_input(self, prompt=""):
        try:
            return input(prompt)
        except EOFError:
            return ""

    def _is_escape_input(self, s: str) -> bool:
        s = str(s or "")

        if not s:
            print(f"{self('o_Empty_Input')}")
            self._read_input(f"{self('o_to_Menu')}")
            return True

        return s == "\x1b" or s.strip().lower() in {"esc", ":q"}

    # ---------------- CONFIG ----------------

    def load_config(self):
        try:
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f) or {}
        except Exception as e:
            print(f"config read error: {e}")
        return {}

    def save_config(self, cfg: dict):
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"config save error: {e}")

    def ensure_ui_i18n_config(self):
        cfg = self.load_config()
        changed = False

        if not isinstance(cfg.get("ui_language"), str) or not str(cfg.get("ui_language")).strip():
            cfg["ui_language"] = "en"
            changed = True

        if not isinstance(cfg.get("ui_strings"), dict):
            cfg["ui_strings"] = {}
            changed = True

        if changed:
            self.save_config(cfg)

    def get_ui_strings_map(self) -> dict:
        cfg = self.load_config()
        raw = cfg.get("ui_strings", {})
        return raw if isinstance(raw, dict) else {}

    def get_ui_lang_map(self, lang: str | None = None) -> dict:
        if lang is None:
            lang = self.get_ui_language()

        all_strings = self.get_ui_strings_map()
        selected = all_strings.get(lang, {})
        if not isinstance(selected, dict):
            selected = {}
        return selected

    def __call__(self, key: str) -> str:
        lang_map = self.get_ui_lang_map()
        return str(lang_map.get(key, key))

    def ensure_base_config(self):
        cfg = self.load_config()
        changed = False

        if "show_usage" not in cfg:
            cfg["show_usage"] = True
            changed = True

        if "ui_language" not in cfg:
            cfg["ui_language"] = "tr"
            changed = True

        if "response_style" not in cfg:
            cfg["response_style"] = ""
            changed = True

        if "force_ui_language" not in cfg:
            cfg["force_ui_language"] = False
            changed = True

        if "open_router_key" not in cfg:
            cfg["open_router_key"] = ""
            changed = True

        if "chat_models" not in cfg or not isinstance(cfg.get("chat_models"), dict):
            cfg["chat_models"] = {}
            changed = True

        if "pinned_chats" not in cfg or not isinstance(cfg.get("pinned_chats"), list):
            cfg["pinned_chats"] = []
            changed = True

        if "is_mic_online" not in cfg:
            cfg["is_mic_online"] = True
            changed = True

        if "use_desktop_voice" not in cfg:
            cfg["use_desktop_voice"] = False
            changed = True

        if "stt_model_online" not in cfg:
            cfg["stt_model_online"] = "openai/gpt-audio-mini"
            changed = True

        if "whisper_cpp_bin" not in cfg:
            cfg["whisper_cpp_bin"] = "/home/$USER/whisper.cpp/build/bin/whisper-cli"
            changed = True

        if "whisper_cpp_model" not in cfg:
            cfg["whisper_cpp_model"] = "/home/$USER/.local/share/whisper/ggml-tiny.bin"
            changed = True

        models = self._get_models_list(cfg)
        if not models:
            cfg["ai_models"] = ["google/gemini-2.5-flash-image"]
            changed = True

        if not str(cfg.get("last_chat", "")).strip():
            cfg["last_chat"] = "default.json"
            changed = True

        if changed:
            self.save_config(cfg)

    def get_available_ui_languages(self) -> list[str]:
        strings = self.get_ui_strings_map()
        if not isinstance(strings, dict):
            return []

        out = []
        for k in strings.keys():
            ks = str(k).strip().lower()
            if ks:
                out.append(ks)

        return out

    def get_ui_language(self) -> str:
        cfg = self.load_config()
        lang = str(cfg.get("ui_language", "tr") or "tr").strip().lower()
        return lang if lang else "tr"

    def set_ui_language(self, lang: str):
        lang = str(lang or "").strip().lower()
        if not lang:
            return
        cfg = self.load_config()
        cfg["ui_language"] = lang
        self.save_config(cfg)

    def _get_models_list(self, cfg: dict):
        models = cfg.get("ai_models", [])
        if not isinstance(models, list):
            models = []
        return [str(m).strip() for m in models if str(m).strip()]

    def _ensure_min_one_model(self, cfg: dict):
        models = self._get_models_list(cfg)
        if not models:
            models = ["google/gemini-2.5-flash-image"]
            cfg["ai_models"] = models
            self.save_config(cfg)
        return models

    def get_chat_model(self, chat_path: Path) -> str:
        cfg = self.load_config()
        models = self._ensure_min_one_model(cfg)

        chat_models = cfg.get("chat_models", {})
        if not isinstance(chat_models, dict):
            chat_models = {}

        key = chat_path.name
        m = str(chat_models.get(key) or "").strip()

        if (not m) or (m not in models):
            m = str(models[0])
            chat_models[key] = m
            cfg["chat_models"] = chat_models
            self.save_config(cfg)

        return m

    def set_chat_model(self, chat_path: Path, model_id: str):
        model_id = str(model_id).strip()
        if not model_id:
            return

        cfg = self.load_config()
        models = self._ensure_min_one_model(cfg)

        if model_id not in models:
            models.insert(0, model_id)
        else:
            models = [m for m in models if m != model_id]
            models.insert(0, model_id)

        cfg["ai_models"] = models

        chat_models = cfg.get("chat_models", {})
        if not isinstance(chat_models, dict):
            chat_models = {}
        chat_models[chat_path.name] = model_id
        cfg["chat_models"] = chat_models

        self.save_config(cfg)
        self.active_model = model_id

    # ---------------- CHAT FILES ----------------

    def load_chat_messages(self):
        try:
            with open(self.current_chat, "r", encoding="utf-8") as f:
                return json.load(f) or []
        except Exception:
            return []

    def save_chat_messages(self, messages):
        with open(self.current_chat, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)

    def list_chat_files(self):
        cfg = self.load_config()
        pinned = cfg.get("pinned_chats", [])
        if not isinstance(pinned, list):
            pinned = []

        files = list(CHAT_DIR.glob("*.json"))

        def mtime(p):
            try:
                return p.stat().st_mtime
            except Exception:
                return 0.0

        def sort_key(p):
            return (0 if p.name in pinned else 1, -mtime(p), p.name.lower())

        return sorted(files, key=sort_key)

    def create_chat(self):
        i = 1
        while True:
            name = f"chat_{i}.json"
            path = CHAT_DIR / name
            if not path.exists():
                break
            i += 1

        path.write_text("[]", encoding="utf-8")
        self.current_chat = path

        cfg = self.load_config()
        cfg["last_chat"] = path.name

        models = self._ensure_min_one_model(cfg)
        chat_models = cfg.get("chat_models", {})
        if not isinstance(chat_models, dict):
            chat_models = {}
        chat_models[path.name] = str(models[0])
        cfg["chat_models"] = chat_models
        self.save_config(cfg)

        self.active_model = self.get_chat_model(self.current_chat)
        print(f"\n✔ {self('o_New_Chat')}: {path.stem}")
        self._read_input(f"{self('o_to_Menu')}")

    def delete_chat(self, file_path: Path):
        if not file_path.exists():
            print("Chat bulunamadı.")
            return

        try:
            file_path.unlink()
        except Exception as e:
            print(f"Delete error: {e}")
            return

        cfg = self.load_config()

        pinned = cfg.get("pinned_chats", [])
        if isinstance(pinned, list) and file_path.name in pinned:
            cfg["pinned_chats"] = [x for x in pinned if x != file_path.name]

        chat_models = cfg.get("chat_models", {})
        if isinstance(chat_models, dict) and file_path.name in chat_models:
            del chat_models[file_path.name]
            cfg["chat_models"] = chat_models

        if cfg.get("last_chat") == file_path.name:
            cfg["last_chat"] = "default.json"

        self.save_config(cfg)

        if self.current_chat == file_path:
            chats = self.list_chat_files()
            if chats:
                self.current_chat = chats[0]
            else:
                default_chat = CHAT_DIR / "default.json"
                default_chat.write_text("[]", encoding="utf-8")
                self.current_chat = default_chat

            cfg = self.load_config()
            cfg["last_chat"] = self.current_chat.name
            self.save_config(cfg)

        self.active_model = self.get_chat_model(self.current_chat)
        print(f"\n✔ {self('o_Delete_Chat')}: {file_path.stem}")

    def rename_chat(self, old_path: Path, new_name_raw: str):
        new_name = (new_name_raw or "").strip()
        if not new_name:
            print("Geçersiz isim.")
            return

        for ch in ["/", "\\", "\n", "\r", "\t"]:
            new_name = new_name.replace(ch, "_")

        new_path = old_path.with_name(new_name + ".json")

        if new_path == old_path:
            print(f"{self('o_Chat_Rename_Fail')}")
            return

        if new_path.exists():
            print("Bu isimde chat zaten var.")
            return

        try:
            old_path.rename(new_path)
        except Exception as e:
            print(f"Yeniden adlandırma hatası: {e}")
            return

        cfg = self.load_config()

        plist = cfg.get("pinned_chats", [])
        if isinstance(plist, list) and old_path.name in plist:
            cfg["pinned_chats"] = [new_path.name if x == old_path.name else x for x in plist]

        if cfg.get("last_chat") == old_path.name:
            cfg["last_chat"] = new_path.name

        chat_models = cfg.get("chat_models", {})
        if isinstance(chat_models, dict) and old_path.name in chat_models:
            chat_models[new_path.name] = chat_models.pop(old_path.name)
            cfg["chat_models"] = chat_models

        self.save_config(cfg)

        if self.current_chat == old_path:
            self.current_chat = new_path
            self.active_model = self.get_chat_model(self.current_chat)

        print(f"\n{self('o_New_Name')} {new_path.stem}")

    def toggle_pin_current_chat(self):
        cfg = self.load_config()

        pinned = cfg.get("pinned_chats", [])
        if not isinstance(pinned, list):
            pinned = []

        current_name = self.current_chat.name

        if current_name in pinned:
            cfg["pinned_chats"] = [x for x in pinned if x != current_name]
            self.save_config(cfg)
            print(f"\n✔ {self('o_Unpin_Current_Chat')}: {self.current_chat.stem}")
        else:
            pinned.append(current_name)
            cfg["pinned_chats"] = pinned
            self.save_config(cfg)
            print(f"\n✔ {self('o_Pin_Current_Chat')}: {self.current_chat.stem}")

    def select_chat(self):
        chats = self.list_chat_files()
        if not chats:
            print("Hiç chat yok.")
            return

        cfg = self.load_config()
        pinned = cfg.get("pinned_chats", [])
        if not isinstance(pinned, list):
            pinned = []

        print(f"\n{self('o_Chats')}:")
        for i, p in enumerate(chats, 1):
            mark = "*" if p == self.current_chat else " "
            pin_mark = "📌 " if p.name in pinned else ""
            print(f"{i}) {mark} {pin_mark}{p.stem}")

        choice = self._read_input(f"\n{self('o_Selection')}: ").strip()
        if not choice.isdigit():
            return

        idx = int(choice) - 1
        if not (0 <= idx < len(chats)):
            return

        self.current_chat = chats[idx]
        cfg = self.load_config()
        cfg["last_chat"] = self.current_chat.name
        self.save_config(cfg)
        self.active_model = self.get_chat_model(self.current_chat)

        print(f"\n{self('o_Active_Chat')}: {self.current_chat.stem}")
        self._read_input(f"{self('o_to_Menu')}")


    # ---------------- IMAGES / FILES ----------------

    def list_pending_attachments(self):
        items = []

        for p in self.pending_images:
            pp = Path(str(p))
            items.append({
                "type": "image",
                "name": pp.name,
                "path": str(pp.resolve()) if pp.exists() else str(pp)
            })

        for f in self.pending_files:
            fp = Path(str(f.get("path", "")))
            items.append({
                "type": "file",
                "name": f.get("name") or fp.name,
                "path": str(fp.resolve()) if fp.exists() else str(fp)
            })

        return items
    
    def delete_pending_attachment_by_number(self, number: int) -> bool:
        items = self.list_pending_attachments()
        idx = number - 101

        if not (0 <= idx < len(items)):
            return False

        item = items[idx]

        if item["type"] == "image":
            self.pending_images = [
                x for x in self.pending_images
                if str(Path(str(x)).resolve()) != item["path"]
            ]
        else:
            self.pending_files = [
                x for x in self.pending_files
                if str(Path(str(x.get("path", ""))).resolve()) != item["path"]
            ]

        print(f"\n✔ {self('o_Delete')}: {item['name']}")
        self._read_input(f"{self('o_to_Menu')}")
        return True

    def save_base64_image(self, b64_data: str, ext: str = "png") -> str | None:
        try:
            raw = base64.b64decode(b64_data)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            out = GENERATED_DIR / f"gen-{stamp}.{ext}"
            out.write_bytes(raw)
            return str(out.resolve())
        except Exception as e:
            print(f"save_base64_image error: {e}")
            return None

    def download_image_to_cache(self, url: str) -> str | None:
        try:
            import urllib.request

            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            ext = "png"
            low = url.lower()
            if ".jpg" in low or ".jpeg" in low:
                ext = "jpg"
            elif ".webp" in low:
                ext = "webp"

            out = GENERATED_DIR / f"gen-{stamp}.{ext}"
            urllib.request.urlretrieve(url, str(out))
            return str(out.resolve())
        except Exception as e:
            print(f"download_image_to_cache error: {e}")
            return None

    def add_file_prompt(self):
        self.clear_screen()
        print(f"{self('o_Attach_File')}")
        print(f"{self('o_Type_ESC')}")
        raw = self._read_input(f"\n{self('o_Drag_Drop')}: ")

        if str(raw).strip().lower() in {"esc", ":q"} or raw == "\x1b":
            return False

        raw = raw.strip()
        if not raw:
            return False

        path = raw.strip().strip("'").strip('"')
        try:
            path = str(Path(path).expanduser().resolve())
        except Exception:
            pass

        p = Path(path)
        if not p.exists():
            print("Dosya bulunamadı.")
            self._read_input("\nMenüye dönmek için Enter...")
            return False

        import mimetypes
        mime, _ = mimetypes.guess_type(str(p))
        mime = (mime or "").lower()

        if mime.startswith("image/"):
            if str(p) not in self.pending_images:
                self.pending_images.append(str(p))
            print(f"Eklendi (image): {p.name}")
        else:
            if not any(x.get("path") == str(p) for x in self.pending_files):
                self.pending_files.append({
                    "path": str(p),
                    "name": p.name,
                    "edit": False
                })
            print(f"Eklendi (file): {p.name}")

        return True

    def _capture_photo_from_script(self):
        script = Path.home() / ".config" / "scripts" / "screenprint.sh"
        if not script.exists():
            print(f"Script bulunamadı: {script}")
            return None

        watch_dirs = [Path.home() / "Resimler", Path.home() / "Pictures", Path("/tmp")]

        def collect_candidates():
            out = []
            for d in watch_dirs:
                if not d.exists():
                    continue
                out += list(d.glob("screen*.*"))
                out += list(d.glob("capture*.*"))
                out += list(d.glob("shot*.*"))
                out += list(d.glob("*.png"))
                out += list(d.glob("*.jpg"))
                out += list(d.glob("*.jpeg"))
            return [p for p in out if p.exists() and p.is_file()]

        try:
            before_files = {}
            for pth in collect_candidates():
                try:
                    before_files[str(pth.resolve())] = pth.stat().st_mtime
                except Exception:
                    pass

            start_ts = datetime.now().timestamp()

            p = subprocess.run(
                [str(script), "only-one"],
                capture_output=True,
                text=True
            )

            if p.returncode != 0:
                print("Fotoğraf çekme iptal edildi veya başarısız oldu.")
                return None

            out = (p.stdout or "").strip()

            if out:
                try:
                    cand = Path(out).expanduser().resolve()
                    if cand.exists() and cand.is_file():
                        old_mtime = before_files.get(str(cand))
                        new_mtime = cand.stat().st_mtime
                        if old_mtime is None or new_mtime > old_mtime or new_mtime >= start_ts:
                            return str(cand)
                except Exception:
                    pass

            after_files = []
            for cand in collect_candidates():
                try:
                    resolved = str(cand.resolve())
                    mtime = cand.stat().st_mtime
                    old_mtime = before_files.get(resolved)

                    is_new = old_mtime is None
                    is_updated = old_mtime is not None and mtime > old_mtime
                    is_after_start = mtime >= start_ts

                    if (is_new or is_updated) and is_after_start:
                        after_files.append(cand)
                except Exception:
                    pass

            if not after_files:
                return None

            newest = max(after_files, key=lambda x: x.stat().st_mtime)
            return str(newest.resolve())

        except Exception as e:
            print(f"Fotoğraf çekme hatası: {e}")
            return None

    def take_photo_and_queue(self):
        self.clear_screen()
        print(f"{self('o_Take_Photo')}")
        print(f"{self('o_Press_ESC')}\n")

        path = self._capture_photo_from_script()
        if not path:
            return False

        if path not in self.pending_images:
            self.pending_images.append(path)

        print(f"\nFotoğraf eklendi: {Path(path).name}")
        return True

    # ---------------- AI ----------------

    def _prompt_multiline(self):
        print(f"{self('o_sub_Send_Message')}")
        print(f"{self('o_Type_ESC')}\n")

        lines = []
        while True:
            line = self._read_input()

            if not lines and self._is_escape_input(line):
                return ""

            if line == "":
                if lines:
                    break
                return ""

            lines.append(line)

        return "\n".join(lines).strip()

    def append_user_message(self, message: str):
        messages = self.load_chat_messages()

        new_message = {"role": "user", "content": message}

        if self.pending_images:
            new_message["images"] = [
                str(Path(p).resolve()) for p in self.pending_images if Path(p).exists()
            ]

        if self.pending_files:
            new_message["files"] = []
            for f in self.pending_files:
                fp = Path(str(f.get("path", "")))
                if fp.exists():
                    new_message["files"].append({
                        "path": str(fp.resolve()),
                        "name": fp.name,
                        "edit": bool(f.get("edit", False))
                    })

        messages.append(new_message)
        self.save_chat_messages(messages)

        self.pending_images.clear()
        self.pending_files.clear()

    def finalize_ai_response(self, raw_text: str):
        raw_text = (raw_text or "").strip()

        try:
            data = json.loads(raw_text)
        except Exception:
            data = {"type": "text", "content": raw_text}

        messages = self.load_chat_messages()

        bot_msg = {
            "role": "bot",
            "content": str(data.get("content") or "").strip()
        }

        usage = data.get("usage")
        if isinstance(usage, dict):
            bot_msg["usage"] = usage

        saved_images = []
        seen_saved = set()

        image_candidates = []
        inline_data_urls = []

        for key in ("image", "url"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                sval = val.strip()
                if sval.startswith("data:image/"):
                    inline_data_urls.append(sval)
                else:
                    image_candidates.append(sval)

        imgs = data.get("images")
        if isinstance(imgs, list):
            for item in imgs:
                if isinstance(item, str) and item.strip():
                    sval = item.strip()
                    if sval.startswith("data:image/"):
                        inline_data_urls.append(sval)
                    else:
                        image_candidates.append(sval)
                elif isinstance(item, dict):
                    u = item.get("url")
                    if isinstance(u, str) and u.strip():
                        sval = u.strip()
                        if sval.startswith("data:image/"):
                            inline_data_urls.append(sval)
                        else:
                            image_candidates.append(sval)

                    iu = item.get("image_url")
                    if isinstance(iu, str) and iu.strip():
                        sval = iu.strip()
                        if sval.startswith("data:image/"):
                            inline_data_urls.append(sval)
                        else:
                            image_candidates.append(sval)
                    elif isinstance(iu, dict):
                        uu = iu.get("url")
                        if isinstance(uu, str) and uu.strip():
                            sval = uu.strip()
                            if sval.startswith("data:image/"):
                                inline_data_urls.append(sval)
                            else:
                                image_candidates.append(sval)

        for url in image_candidates:
            local_path = self.download_image_to_cache(url)
            if local_path and local_path not in seen_saved:
                seen_saved.add(local_path)
                saved_images.append(local_path)

        base64_candidates = []

        for item in inline_data_urls:
            if item.startswith("data:image/") and "," in item:
                base64_candidates.append(item.split(",", 1)[1].strip())

        one_b64 = data.get("image_base64")
        if isinstance(one_b64, str) and one_b64.strip():
            base64_candidates.append(one_b64.strip())

        many_b64 = data.get("images_base64")
        if isinstance(many_b64, list):
            for item in many_b64:
                if isinstance(item, str) and item.strip():
                    base64_candidates.append(item.strip())
                elif isinstance(item, dict):
                    b = item.get("b64_json")
                    if isinstance(b, str) and b.strip():
                        base64_candidates.append(b.strip())

        for item in base64_candidates:
            if item.startswith("data:image/") and "," in item:
                item = item.split(",", 1)[1].strip()
            local_path = self.save_base64_image(item, "png")
            if local_path and local_path not in seen_saved:
                seen_saved.add(local_path)
                saved_images.append(local_path)

        if saved_images:
            bot_msg["images"] = saved_images

        messages.append(bot_msg)
        self.save_chat_messages(messages)
        return bot_msg

    def call_ai(self):
        cmd = [sys.executable, "-u", AI_SCRIPT, str(self.current_chat)]

        try:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUNBUFFERED"] = "1"

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=False,
                env=env
            )

            stdout_text = proc.stdout.decode("utf-8", errors="replace")
            stderr_text = proc.stderr.decode("utf-8", errors="replace")

            stdout_text = fix_mojibake(stdout_text)
            stderr_text = fix_mojibake(stderr_text)

            if proc.returncode != 0:
                err = (stderr_text or stdout_text or "Bilinmeyen hata").strip()
                self.handle_ai_error(err)
                return None

            return self.finalize_ai_response(stdout_text)

        except Exception as e:
            self.handle_ai_error(str(e))
            return None

    def handle_ai_error(self, error_text):
        messages = self.load_chat_messages()
        messages.append({"role": "bot", "content": f"❌ Hata:\n{error_text}"})
        self.save_chat_messages(messages)
        print(f"\n❌ Hata:\n{error_text}")

    def print_last_bot_message(self, bot_msg: dict):
        cfg = self.load_config()
        show_usage = bool(cfg.get("show_usage", False))

        text = str(bot_msg.get("content") or "").strip()
        if text:
            print("\nAssistant:")
            print(text)
            print()

        imgs = bot_msg.get("images")
        if isinstance(imgs, list) and imgs:
            print("Oluşan görseller:")
            for p in imgs:
                print(f"- {p}")
            print()

        usage = bot_msg.get("usage")
        if show_usage and isinstance(usage, dict):
            p = int(usage.get("prompt_tokens", 0) or 0)
            c = int(usage.get("completion_tokens", 0) or 0)
            t = int(usage.get("total_tokens", 0) or 0)
            print(f"[Input tokens: {p} | Output tokens: {c} | Total tokens: {t}]")
            print()

    def send_message_flow(self):
        self.clear_screen()
        message = self._prompt_multiline()
        if not message:
            return

        self.append_user_message(message)

        self.clear_screen()
        print(f"{self('o_AI_Response')}\n")
        bot_msg = self.call_ai()
        if bot_msg:
            self.print_last_bot_message(bot_msg)

        self._read_input(f"{self('o_to_Menu')}")

    # ---------------- MENUS ----------------

    def print_header(self):
        self.active_model = self.get_chat_model(self.current_chat)
        print("\n" + "=" * 60)
        labels = [
            self('o_Active_Chat'),
            self('o_Active_Model'),
            self('o_Language')
        ]

        max_len = max(len(x) for x in labels)

        print(f"{labels[0].ljust(max_len)} : {self.current_chat.stem}")
        print(f"{labels[1].ljust(max_len)} : {self.active_model}")
        print(f"{labels[2].ljust(max_len)} : {self.get_ui_language()}")
        print("=" * 60)

        if self.pending_images or self.pending_files:
            print(f"{self('o_Pending_Attachments')}:")
            n = 101

            for p in self.pending_images:
                print(f"{n}) [{self('o_image')}] {Path(p).name} ({self('o_Delete')})")
                n += 1

            for f in self.pending_files:
                print(f"{n}) [{self('o_file')}] {f.get('name')} ({self('o_Delete')})")
                n += 1

            print("-" * 60)

    def menu_chat(self):
        while True:
            self.clear_screen()

            cfg = self.load_config()
            pinned = cfg.get("pinned_chats", [])
            if not isinstance(pinned, list):
                pinned = []

            is_pinned = self.current_chat.name in pinned
            pin_label = self("o_Unpin_Current_Chat") if is_pinned else self("o_Pin_Current_Chat")

            print(f"\n={self('o_Chats')}=")
            print(f"{self('o_Active_Chat')}: {self.current_chat.stem}{' 📌' if is_pinned else ''}")
            print(f"1) {self('o_Change_Chat')}")
            print(f"2) {self('o_New_Chat')}")
            print(f"3) {self('o_Delete_Chat')}")
            print(f"4) {self('o_Rename')}")
            print(f"5) {pin_label}")
            print(f"6) {self('o_Go_Back')}")

            choice = self._read_input(f"\n{self('o_Selection')}: ").strip()

            if choice == "1":
                self.select_chat()

            elif choice == "2":
                self.create_chat()

            elif choice == "3":
                chats = self.list_chat_files()
                if not chats:
                    print("Hiç chat yok.")
                    continue

                print(f"\n{self('o_Delete_Chat')}:")
                for i, p in enumerate(chats, 1):
                    mark = "*" if p == self.current_chat else " "
                    pin_mark = "📌 " if p.name in pinned else ""
                    print(f"{i}) {mark} {pin_mark}{p.stem}")

                sel = self._read_input(f"\n{self('o_Selection')}: ").strip()

                if not sel.isdigit():
                    continue

                idx = int(sel) - 1
                if not (0 <= idx < len(chats)):
                    continue

                print(f'{self("o_Delete")}("{chats[idx].stem}")? (e/h): ')
                confirm = input(f'({self("o_Delete_Chat_Confirm")})').strip().lower()

                if confirm == "e":
                    self.delete_chat(chats[idx])
                    self._read_input(f"{self('o_to_Menu')}")

            elif choice == "4":
                chats = self.list_chat_files()
                if not chats:
                    print("Hiç chat yok.")
                    continue

                print(f"\n{self('o_Rename_Chat')}:")
                for i, p in enumerate(chats, 1):
                    mark = "*" if p == self.current_chat else " "
                    pin_mark = "📌 " if p.name in pinned else ""
                    print(f"{i}) {mark} {pin_mark}{p.stem}")

                sel = self._read_input(f"\n{self('o_Selection')}: ").strip()

                if not sel.isdigit():
                    continue

                idx = int(sel) - 1
                if not (0 <= idx < len(chats)):
                    continue

                new_name = input(f"{self('o_New_Name')} ").strip()
                self.rename_chat(chats[idx], new_name)
                self._read_input(f"{self('o_to_Menu')}")

            elif choice == "5":
                self.toggle_pin_current_chat()
                self._read_input(f"{self('o_to_Menu')}")

            elif choice == "6":
                return

    def menu_models(self):
        while True:
            self.clear_screen()
            cfg = self.load_config()
            models = self._ensure_min_one_model(cfg)

            print(f"\n{self('o_AI_Model')}")
            print(f"1) {self('o_Change_AI_Model')}")
            print(f"2) {self('o_Add_Model')}")
            print(f"3) {self('o_Delete_Model')}")
            print(f"4) {self('o_Go_Back')}")

            choice = self._read_input(f"\n{self('o_Selection')}: ").strip()

            if choice == "1":
                print(f"\n{self('o_AI_Models')}:")
                active = self.get_chat_model(self.current_chat)
                for i, m in enumerate(models, 1):
                    mark = "*" if m == active else " "
                    print(f"{i}) {mark} {m}")

                sel = self._read_input(f"\n{self('o_Selection')}: ").strip()

                if not sel.isdigit():
                    continue

                idx = int(sel) - 1
                if not (0 <= idx < len(models)):
                    continue

                self.set_chat_model(self.current_chat, models[idx])
                print(f"\n{self('o_Active_Model')}: {models[idx]}")
                self._read_input(f"{self('o_to_Menu')}")


            elif choice == "2":
                model_id = input(f"\n{self('o_Add_Model')}(exp: openai/gpt-4.1-mini): ").strip()

                if self._is_escape_input(model_id):
                    continue

                if model_id:
                    self.set_chat_model(self.current_chat, model_id)
                    print(f"\n✔ {self('o_Add_Model')}: {model_id}")
                    self._read_input(f"{self('o_to_Menu')}")

            elif choice == "3":
                cfg2 = self.load_config()
                models2 = self._ensure_min_one_model(cfg2)

                if len(models2) <= 1:
                    print(f"\n{self('o_Min_Model_Error')}")
                    self._read_input(f"\n{self('o_to_Menu')}")
                    continue

                print(f"\n{self('o_Delete_Model')}:")
                for i, m in enumerate(models2, 1):
                    mark = "*" if m == self.get_chat_model(self.current_chat) else " "
                    print(f"{i}) {mark} {m}")

                sel = self._read_input(f"\n{self('o_Selection')}: ").strip()

                if not sel.isdigit():
                    continue

                idx = int(sel) - 1
                if not (0 <= idx < len(models2)):
                    continue

                model_id = models2[idx]

                confirm = input(f'{self("o_Delete")}("{model_id}")? (e/h): ').strip().lower()

                if confirm == "e":
                    models2 = [m for m in models2 if m != model_id]
                    cfg2["ai_models"] = models2

                    chat_models = cfg2.get("chat_models", {})
                    if not isinstance(chat_models, dict):
                        chat_models = {}

                    new_default = str(models2[0]) if models2 else None
                    for k, v in list(chat_models.items()):
                        if v == model_id:
                            chat_models[k] = new_default

                    cfg2["chat_models"] = chat_models

                    self.save_config(cfg2)
                    self.active_model = self.get_chat_model(self.current_chat)

                    print(f"\n✔ {self('o_Delete_Model')}: {model_id}")
                    self._read_input(f"{self('o_to_Menu')}")

            elif choice == "4":
                return

    def menu_personalization(self):
        while True:
            self.clear_screen()
            cfg = self.load_config()
            show_usage = bool(cfg.get("show_usage", True))

            print("\nPersonalization")
            print(f"1) {self('o_Token_Usage')}: {'✅' if show_usage else '❌'}")
            print(f"2) {self('o_Go_Back')}")

            choice = self._read_input(f"\n{self('o_Selection')}: ").strip()

            if choice == "1":
                cfg["show_usage"] = not show_usage
                self.save_config(cfg)

            elif choice == "2":
                return

    def menu_ai_settings(self):
        while True:
            self.clear_screen()
            cfg = self.load_config()

            force_ui_language = bool(cfg.get("force_ui_language", False))

            print("\nAI Settings")
            print(f"1) {self('o_Force_Language_Text')}({self('o_Force_Language_Hint')}): {'✅' if force_ui_language else '❌'}")
            print(f"2) {self('o_Go_Back')}")

            choice = self._read_input(f"\n{self('o_Selection')}: ").strip()

            if choice == "1":
                cfg["force_ui_language"] = not force_ui_language
                self.save_config(cfg)

            elif choice == "2":
                return

    def menu_settings(self):
        while True:
            self.clear_screen()
            print(f"\n{self('o_Settings')}")
            print(f"1) {self('o_AI_Model')}")
            print(f"2) {self('o_OpenRouter_API_Key')}")
            print(f"3) {self('o_Response_Style')}")
            print(f"4) {self('o_Personalization')}")
            print(f"5) {self('o_Language')}")
            print(f"6) {self('o_AI_Settings')}")
            print(f"7) {self('o_Go_Back')}")

            choice = self._read_input(f"\n{self('o_Selection')}: ").strip()


            if choice == "1":
                self.menu_models()

            elif choice == "2":
                cfg = self.load_config()
                current = str(cfg.get("open_router_key", "") or "")
                print(f"\n{self('o_OpenRouter_API_Key')}:\n{current}\n")
                print(f"\n{self('o_Type_ESC')}")
                new_key = input(f"\n{self('o_OpenRouter_Placeholder')}: ").strip()

                if self._is_escape_input(new_key):
                    continue

                if new_key:
                    cfg["open_router_key"] = new_key
                    self.save_config(cfg)
                    print(f"\n✔ {self('o_Saved')}({self('o_OpenRouter_API_Key')})")
                    self._read_input(f"{self('o_to_Menu')}")

            elif choice == "3":
                cfg = self.load_config()
                current = str(cfg.get("response_style", "") or "")
                print(f"\n{self('o_Response_Style')}:\n{current}\n")
                print(f"\n{self('o_Type_ESC')}")
                print(f"\n\n{self('o_New_Value')}")
                new_style = input(f"\n({self('o_Response_Style_Placeholder')})").strip()

                if self._is_escape_input(new_style):
                    continue

                if new_style:
                    cfg["response_style"] = new_style
                    self.save_config(cfg)
                    print(f"\n✔ {self('o_Saved')}({self('o_Response_Style')})")
                    self._read_input(f"{self('o_to_Menu')}")


            elif choice == "4":
                self.menu_personalization()

            elif choice == "5":
                self.clear_screen()

                current = self.get_ui_language()
                langs = self.get_available_ui_languages()

                print(f"\n{self('o_Language')}: {current}")

                if langs:
                    print(f"\n{self('o_Available_Languages')}:")
                    for lang in langs:
                        mark = "*" if lang == current else " "
                        print(f"  {mark} {lang}")

                print(f"\n{self('o_Language_Select_Hint')}")
                print(f"{self('o_Type_ESC')}")

                new_lang = self._read_input(f"\n{self('o_New_Value')} ").strip().lower()

                if self._is_escape_input(new_lang):
                    continue

                if new_lang not in langs:
                    print(f"\n{self('o_Invalid_Language_Code')}")
                    self._read_input(f"\n{self('o_to_Menu')}")
                    continue

                self.set_ui_language(new_lang)

                print(f"\n✔ {self('o_Saved')} ({self('o_Language')}): {new_lang}")
                self._read_input(f"{self('o_to_Menu')}")

            elif choice == "6":
                self.menu_ai_settings()

            elif choice == "7":
                return


    def run(self):
        while True:
            self.clear_screen()
            self.print_header()
            print(f"1) {self('o_Send_Message')}")
            print(f"2) {self('o_Take_Photo')}")
            print(f"3) {self('o_Attach_File')}")
            print(f"4) {self('o_Chats')}")
            print(f"5) {self('o_Settings')}")
            print(f"6) {self('o_Go_Back')}")

            choice = self._read_input(f"\n{self('o_Selection')}: ").strip()

            if choice.isdigit():
                num = int(choice)
                if num >= 101:
                    if self.delete_pending_attachment_by_number(num):
                        continue

            if choice == "1":
                self.send_message_flow()

            elif choice == "2":
                ok = self.take_photo_and_queue()
                if ok:
                    self.send_message_flow()

            elif choice == "3":
                ok = self.add_file_prompt()
                if ok:
                    self.send_message_flow()

            elif choice == "4":
                self.menu_chat()

            elif choice == "5":
                self.menu_settings()

            elif choice == "6":
                self.clear_screen()
                print("🏁")
                return


if __name__ == "__main__":
    cli = ChatCLI()
    cli.run()
