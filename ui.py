#!/usr/bin/env python4
import gi
import sys
import json
import subprocess
import threading
from pathlib import Path
import base64
import tempfile
from datetime import datetime
import signal
import shutil

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GLib, Gio, Gdk, Pango, Adw
Adw.init()

CONFIG_PATH = Path.home() / ".config" / "capture-ai" / "config.json"
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

BASE_DIR = Path.home() / ".cache" / "capture-ai"
CHAT_DIR = BASE_DIR / "chats"
AI_SCRIPT = str(Path.home() / "capture-ai/ai.py")

CHAT_DIR.mkdir(parents=True, exist_ok=True)

# Config dosyasından son açılan chat'i al, yoksa default.json kullan
if CONFIG_PATH.exists():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f) or {}
    last_chat_name = config.get("last_chat", "default.json")
    dark_mode = config.get("dark_mode", True)
else:
    config = {}
    last_chat_name = "default.json"
    dark_mode = True

DEFAULT_CHAT = CHAT_DIR / last_chat_name
if not DEFAULT_CHAT.exists():
    DEFAULT_CHAT.write_text("[]", encoding="utf-8")


class ChatApp(Gtk.Application):
    def __init__(self, image_path=None):
        super().__init__()
        self.connect("activate", self.on_activate)

        self.current_chat = DEFAULT_CHAT
        self.image_path = image_path

        self.pending_images = []
        self.pending_files = []

        if image_path:
            self.pending_images = [image_path]

        self.sidebar_expanded = True
        self.chats_list_open = True
        self.models_list_open = True

        self.auto_focus_enabled = True
        self.auto_scroll_enabled = True
        self.selected_indexes = set()
        self.selection_mode = False

        # aktif chat’in modeli (chat başına)
        self.active_model = None

    # ---------------- CONFIG HELPERS ----------------

    def load_config(self):
        try:
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f) or {}
        except Exception as e:
            print("config read error:", e)
        return {}

    def save_config(self, cfg: dict):
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("config save error:", e)

    def _get_models_list(self, cfg: dict):
        models = cfg.get("ai_models", [])
        if not isinstance(models, list):
            models = []
        # normalize
        models = [str(m).strip() for m in models if str(m).strip()]
        return models

    def _ensure_min_one_model(self, cfg: dict):
        """
        Senin isteğin: minimum 1 model kalmalı.
        Eğer config boşsa burada bir default ekliyoruz.
        İstersen bunu hata yapacak şekilde değiştirebilirsin.
        """
        models = self._get_models_list(cfg)
        if not models:
            models = ["google/gemini-2.5-flash-image"]
            cfg["ai_models"] = models
            self.save_config(cfg)
        return models

    def get_default_model(self, cfg: dict) -> str:
        models = self._ensure_min_one_model(cfg)
        return str(models[0])

    def get_chat_model(self, chat_path: Path) -> str:
        """
        Bu chat için model:
          - cfg.chat_models[chat_name] varsa ve ai_models içinde ise onu döndür
          - yoksa / silinmişse => ai_models[0] + config’e yaz (self-heal)
        """
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
        """
        Bu chat’in modelini set eder + LRU (en son seçilen model en üste)
        """
        model_id = str(model_id).strip()
        if not model_id:
            return

        cfg = self.load_config()
        models = self._ensure_min_one_model(cfg)

        # LRU: seçileni en üste al
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

        # selected_model artık gereksiz; istersen yazma:
        # cfg["selected_model"] = model_id

        self.save_config(cfg)

        # UI state
        self.active_model = model_id
        self.load_models_list()
        self.apply_models_visibility()

    # ---------------- UI BUILD ----------------

    def on_activate(self, app):
        self.win = Gtk.ApplicationWindow(application=app)
        self.win.set_title("Capture AI")
        self.win.set_default_size(1100, 750)
        self.apply_theme(dark_mode)
        self.apply_css()

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.win.set_child(root)

        # SIDEBAR
        self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.sidebar.add_css_class("sidebar")
        self.sidebar.set_size_request(250, -1)
        self.sidebar.set_hexpand(False)
        self.sidebar.set_halign(Gtk.Align.START)

        self.toggle_btn = Gtk.Button(label="☰")
        self.toggle_btn.connect("clicked", self.toggle_sidebar)
        self.sidebar.append(self.toggle_btn)

        # CHATS HEADER
        self.chats_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.chats_toggle_btn = Gtk.Button(label="Chats ▾")
        self.chats_toggle_btn.connect("clicked", self.toggle_chats_list)
        self.chats_header.append(self.chats_toggle_btn)

        self.new_btn = Gtk.Button(label="+")
        self.new_btn.set_tooltip_text("Yeni Sohbet")
        self.new_btn.connect("clicked", self.create_chat)
        self.chats_header.append(self.new_btn)

        self.sidebar.append(self.chats_header)

        self.chat_list = Gtk.ListBox()
        self.chat_list.set_activate_on_single_click(True)
        self.chat_list.connect("row-activated", self.switch_chat)
        self.sidebar.append(self.chat_list)

        # AI MODELS HEADER + LIST
        self.models_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.models_header.set_hexpand(True)

        self.models_toggle_btn = Gtk.Button(label="AI models ▾")
        self.models_toggle_btn.connect("clicked", self.toggle_models_list)
        self.models_header.append(self.models_toggle_btn)

        models_spacer = Gtk.Box()
        self.models_header.append(models_spacer)
        self.add_model_btn = Gtk.Button(label="+")
        self.add_model_btn.set_tooltip_text("Model ekle")
        self.add_model_btn.connect("clicked", self.open_add_model_dialog)
        self.models_header.append(self.add_model_btn)

        self.sidebar.append(self.models_header)

        self.models_list = Gtk.ListBox()
        self.models_list.connect("row-activated", self.on_model_row_activated)
        self.models_list.set_activate_on_single_click(False)
        self.sidebar.append(self.models_list)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        self.sidebar.append(spacer)

        # Dark mode
        dark_mode_btn = Gtk.Button(label="🌓")
        dark_mode_btn.set_tooltip_text("Toggle Dark Mode")
        dark_mode_btn.connect("clicked", self.toggle_theme)
        self.sidebar.append(dark_mode_btn)

        # API key
        key_btn = Gtk.Button()
        key_btn.set_icon_name("dialog-password-symbolic")
        key_btn.set_tooltip_text("OpenRouter API Key")
        key_btn.connect("clicked", self.open_key_dialog)
        self.sidebar.append(key_btn)

        root.append(self.sidebar)

        # MAIN
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main.set_hexpand(True)
        main.set_vexpand(True)
        main.set_halign(Gtk.Align.FILL)
        root.append(main)

        # OVERLAY
        overlay = Gtk.Overlay()
        overlay.set_hexpand(True)
        overlay.set_vexpand(True)
        main.append(overlay)

        # Scroll content
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.content_box.set_hexpand(True)
        self.content_box.set_vexpand(True)

        self.chat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.chat_box.set_hexpand(True)
        self.content_box.append(self.chat_box)
        # Selection row: "X mesaj referans seçildi" + [X]
        self.selection_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.selection_row.set_margin_start(10)
        self.selection_row.set_halign(Gtk.Align.START)

        self.selection_label = Gtk.Label(label="")
        self.selection_label.set_xalign(0)
        self.selection_label.set_halign(Gtk.Align.START)
        self.selection_label.set_hexpand(False)

        self.selection_clear_btn = Gtk.Button(label="✕")
        self.selection_clear_btn.add_css_class("flat")
        self.selection_clear_btn.set_tooltip_text("Seçimi temizle")
        self.selection_clear_btn.connect("clicked", self.clear_selection)

        # X'e basınca bubble click falan tetiklenmesin (sende _consume_click varsa)
        self._consume_click(self.selection_clear_btn)

        # Başta görünmez ama yer kaplasın (chat zıplamasın)
        self.selection_row.set_opacity(0.0)
        self.selection_row.set_sensitive(False)
        self.selection_row.set_size_request(-1, 34)  # istersen 26-40 arası ayarla

        self.selection_row.append(self.selection_label)
        self.selection_row.append(self.selection_clear_btn)

        # ÖNEMLİ: tanımladıktan sonra append
        self.content_box.append(self.selection_row)

        # --- ATTACHMENTS PREVIEW STRIP (horizontal + scroll) ---
        self.preview_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.preview_row.set_hexpand(True)
        self.preview_row.set_halign(Gtk.Align.FILL)
        self.preview_row.set_margin_start(10)

        self.preview_scroller = Gtk.ScrolledWindow()
        self.preview_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.preview_scroller.set_hexpand(True)
        self.preview_scroller.set_propagate_natural_height(True)
        self.preview_scroller.set_min_content_height(90)

        self.preview_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.preview_hbox.set_halign(Gtk.Align.START)
        self.preview_scroller.set_child(self.preview_hbox)

        self.preview_row.append(self.preview_scroller)

        self.preview_next_btn = Gtk.Button(label=">")
        self.preview_next_btn.add_css_class("flat")
        self.preview_next_btn.set_tooltip_text("Sağa kaydır")
        self.preview_next_btn.connect("clicked", self.scroll_preview_right)
        self.preview_next_btn.set_visible(False)  # sadece taşınca
        self.preview_row.append(self.preview_next_btn)

        # başta gizli (chat zıplamasın istersen opacity yaklaşımı da kullanabilirsin)
        self.preview_row.set_visible(False)
        self.content_box.append(self.preview_row)

        self.refresh_attachments_preview()

        self.bottom_spacer = Gtk.Box()
        self.bottom_spacer.set_size_request(-1, 110)
        self.content_box.append(self.bottom_spacer)

        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_hexpand(True)
        self.scroll.set_vexpand(True)
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_child(self.content_box)
        overlay.set_child(self.scroll)
        vadj = self.scroll.get_vadjustment()
        vadj.connect("value-changed", self.on_scroll_changed)

        # Floating input
        input_wrapper = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        input_wrapper.set_hexpand(True)
        input_wrapper.set_halign(Gtk.Align.FILL)
        input_wrapper.set_valign(Gtk.Align.END)
        input_wrapper.set_margin_bottom(12)
        overlay.add_overlay(input_wrapper)

        # 🔽 Scroll to bottom button
        self.scroll_btn = Gtk.Button(label="↓")
        self.scroll_btn.set_size_request(36, 36)
        self.scroll_btn.set_valign(Gtk.Align.END)
        self.scroll_btn.set_halign(Gtk.Align.END)
        self.scroll_btn.set_margin_bottom(80)  # input'un üstünde dursun
        self.scroll_btn.set_margin_end(20)
        self.scroll_btn.add_css_class("scroll-btn")
        self.scroll_btn.connect("clicked", self.on_scroll_button_clicked)
        self.scroll_btn.set_visible(False)
        overlay.add_overlay(self.scroll_btn)

        clamp = Adw.Clamp()
        clamp.set_hexpand(True)
        clamp.set_halign(Gtk.Align.FILL)
        clamp.props.maximum_size = 800
        clamp.props.tightening_threshold = 800
        input_wrapper.append(clamp)

        input_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        input_row.set_hexpand(True)
        input_row.set_halign(Gtk.Align.FILL)
        clamp.set_child(input_row)

        attach_btn = Gtk.Button(label="📎")
        attach_btn.set_valign(Gtk.Align.END)
        attach_btn.set_tooltip_text("Dosya ekle (fotoğraf / belge)")
        attach_btn.add_css_class("send_btn")
        attach_btn.connect("clicked", self.on_attach_clicked)
        input_row.append(attach_btn)

        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.textview.set_hexpand(True)
        self.textview.set_vexpand(False)
        self.textview.add_css_class("chat-textview")

        self.text_scroll = Gtk.ScrolledWindow()
        self.text_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.text_scroll.set_propagate_natural_height(True)
        self.text_scroll.set_min_content_height(32)
        self.text_scroll.set_max_content_height(140)
        self.text_scroll.add_css_class("chat-input-box")
        self.text_scroll.set_child(self.textview)
        input_row.append(self.text_scroll)

        mic_btn = Gtk.Button(label="🎙️")
        mic_btn.set_valign(Gtk.Align.END)
        mic_btn.set_tooltip_text("Konuşarak yaz (başlat/durdur)")
        mic_btn.connect("clicked", self.toggle_voice_input)
        mic_btn.add_css_class("send_btn")
        input_row.append(mic_btn)

        self.mic_btn = mic_btn
        self._rec_stop = threading.Event()
        self._rec_thread = None
        self._voice_proc = None
        self._last_wav = None

        send_btn = Gtk.Button(label="↑")
        send_btn.set_valign(Gtk.Align.END)
        send_btn.connect("clicked", lambda *_: self.send_message(None))
        send_btn.add_css_class("send_btn")
        input_row.append(send_btn)

        # key controller
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_textview_key_pressed)
        self.textview.add_controller(key_controller)

        # aktif chat modeli yükle
        self.active_model = self.get_chat_model(self.current_chat)

        # load initial
        self.load_chat_list()
        self.load_chat()
        self.apply_chats_visibility()
        self.load_models_list()
        self.apply_models_visibility()

        self.win.present()
        GLib.idle_add(self.force_focus_entry)

    # ---------------- CSS / THEME ----------------

    def apply_css(self):
        css = """
        .chat-input-box {
            border-radius: 14px;
            margin-bottom: 8px;
            padding: 6px 10px;
        }

        .attach-chip {
            padding: 6px 10px;
            border-radius: 10px;
            background: rgba(255,255,255,0.06);
        }
        window.light .attach-chip {
            background: rgba(0,0,0,0.06);
        }

        window.dark .chat-input-box {
            background: #1e1e1e;
        }

        window.light .chat-input-box {
            background: gray;
        }

        .send_btn {
           margin-bottom: 14px;
        }

        .chat-textview {
            background: transparent;
        }

        .selected-chat {
            background: #d0e0ff;
            border-radius: 6px;
        }

        .sidebar {
            padding: 8px;
        }

        .user-bubble {
            background: #303643;
            border-radius: 12px;
            padding: 10px;
            margin-right: 10px;
            color: white;
        }

        .bot-bubble {
            border-radius: 12px;
            padding: 10px;
            margin-left: 10px;
        }

        .user-bubble-ref {
            background: #237227;   /* koyu yeşil gibi (dark mode) */
            border: 1px solid rgba(255,255,255,0.08);
        }

        window.light .user-bubble-ref {
            background: #84B179;   /* koyu yeşil gibi (dark mode) */
            color: #111;
            border: 1px solid rgba(0,0,0,0.08);
        }

        .user-bubble-regen {
            background: #5a3a8a;  /* koyu mor (dark mode) */
            border: 1px solid rgba(255,255,255,0.08);
        }

        window.light .user-bubble-regen {
            background: #e9dcff;  /* açık mor (light mode) */
            color: #111;
            border: 1px solid rgba(0,0,0,0.08);
        }

        .refs-preview {
            padding: 6px 8px;
            border-radius: 10px;
            margin-bottom: 6px;
            background: rgba(255,255,255,0.06);
        }

        .refs-preview-line {
            opacity: 0.55;
            font-size: 0.90em;
        }

        window.light .refs-preview {
            background: rgba(0,0,0,0.06);
        }

        window.light .refs-preview-line {
            opacity: 0.65;
        }

        .refs-groups {
            margin-bottom: 6px;
        }

        .hovered {
            box-shadow: 0 0 6px rgba(0,0,0,0.25);
        }

        .selected {
            outline: 2px solid #ff9800;
        }

        
        .code-block {
            background: #1e1e1e;
            border-radius: 8px;
            padding: 12px;
            font-family: monospace;
        }

        window.light .code-block {
            background: #F9F9F9;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
        }

        .code-copy-btn {
            color: white;
        }

        window.light .code-copy-btn{
            color: #1e1e1e;
        }

        .attach-edit-on {
            outline: 2px solid #2ecc71;
            border-radius: 10px;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def apply_theme(self, is_dark: bool):
        is_dark = bool(is_dark)
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(
            Adw.ColorScheme.FORCE_DARK if is_dark else Adw.ColorScheme.FORCE_LIGHT
        )
        self.win.remove_css_class("dark")
        self.win.remove_css_class("light")
        self.win.add_css_class("dark" if is_dark else "light")

    def toggle_theme(self, *_):
        cfg = self.load_config()
        current = cfg.get("dark_mode", True)
        new_value = not current
        cfg["dark_mode"] = new_value
        self.save_config(cfg)
        self.apply_theme(new_value)

    # ---------------- INPUT ----------------

    def force_focus_entry(self):
        self.textview.grab_focus()
        return False

    def on_textview_key_pressed(self, controller, keyval, keycode, state):
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)

        buffer = self.textview.get_buffer()

        # Ctrl+C / Ctrl+X / Ctrl+V / Ctrl+A
        if ctrl:
            # Ctrl+A: hepsini seç
            if keyval in (Gdk.KEY_a, Gdk.KEY_A):
                start, end = buffer.get_bounds()
                buffer.select_range(start, end)
                return True

            # Ctrl+C: seçileni kopyala
            if keyval in (Gdk.KEY_c, Gdk.KEY_C):
                if buffer.get_has_selection():
                    s, e = buffer.get_selection_bounds()
                    text = buffer.get_text(s, e, True) or ""
                    display = Gdk.Display.get_default()
                    if display:
                        display.get_clipboard().set(text)
                return True

            # Ctrl+X: kes
            if keyval in (Gdk.KEY_x, Gdk.KEY_X):
                if buffer.get_has_selection():
                    s, e = buffer.get_selection_bounds()
                    text = buffer.get_text(s, e, True) or ""
                    display = Gdk.Display.get_default()
                    if display:
                        display.get_clipboard().set(text)
                    buffer.delete(s, e)
                return True

            # Ctrl+V (ve Ctrl+Shift+V): yapıştır
            if keyval in (Gdk.KEY_v, Gdk.KEY_V):
                display = Gdk.Display.get_default()
                if not display:
                    return True
                clipboard = display.get_clipboard()

                def on_text(cb, res):
                    try:
                        text = cb.read_text_finish(res) or ""
                    except Exception:
                        text = ""
                    if not text:
                        return

                    # seçili alan varsa üstüne yaz
                    if buffer.get_has_selection():
                        s, e = buffer.get_selection_bounds()
                        buffer.delete(s, e)

                    it = buffer.get_iter_at_mark(buffer.get_insert())
                    buffer.insert(it, text)

                clipboard.read_text_async(None, on_text)
                return True

        # Enter davranışın (sende vardı)
        if keyval == Gdk.KEY_Return:
            # Shift+Enter = newline
            if shift:
                return False
            # Enter = send
            GLib.idle_add(self.send_message, None)
            return True

        return False

    # ---------------- IMAGE PREVIEW ----------------

    def show_image_preview(self, image_path):
        p = str(Path(image_path).resolve())
        if Path(p).exists() and p not in self.pending_images:
            self.pending_images.append(p)
        self.refresh_attachments_preview()

    def on_attach_clicked(self, *_):
        # GTK4 FileDialog ile çoklu seçim
        dialog = Gtk.FileDialog()

        # Filter’lar
        img_filter = Gtk.FileFilter()
        img_filter.set_name("Images")
        img_filter.add_mime_type("image/png")
        img_filter.add_mime_type("image/jpeg")
        img_filter.add_mime_type("image/webp")
        img_filter.add_mime_type("image/gif")
        img_filter.add_mime_type("image/bmp")
        img_filter.add_mime_type("image/tiff")

        any_filter = Gtk.FileFilter()
        any_filter.set_name("All files")
        any_filter.add_pattern("*")

        flist = Gio.ListStore.new(Gtk.FileFilter)
        flist.append(img_filter)
        flist.append(any_filter)
        dialog.set_filters(flist)

        def on_done(dlg, res):
            try:
                files = dlg.open_multiple_finish(res)  # Gio.ListModel
            except Exception:
                return

            if not files:
                return

            import mimetypes
            for i in range(files.get_n_items()):
                gfile = files.get_item(i)
                if not gfile:
                    continue
                from urllib.parse import urlparse, unquote

                path = gfile.get_path()

                # Bazı sistemlerde get_path() None döner; URI'den düşür
                if not path:
                    uri = gfile.get_uri() or ""
                    if uri.startswith("file://"):
                        path = unquote(urlparse(uri).path)

                # Hâlâ yoksa (remote vb.) geç
                if not path:
                    continue

                mime, _ = mimetypes.guess_type(path)
                mime = (mime or "").lower()

                if mime.startswith("image/"):
                    if path not in self.pending_images:
                        self.pending_images.append(path)
                else:
                    # belge vb. -> dict olarak ekle + duplicate engelle
                    if not any(x.get("path") == path for x in self.pending_files):
                        self.pending_files.append({
                            "path": path,
                            "name": Path(path).name,
                            "edit": False
                        })

            self.refresh_attachments_preview()

        dialog.open_multiple(self.win, None, on_done)

    def refresh_attachments_preview(self):
        # temizle
        if not hasattr(self, "preview_hbox"):
            return

        while True:
            c = self.preview_hbox.get_first_child()
            if not c:
                break
            self.preview_hbox.remove(c)

        has_any = bool(self.pending_images or self.pending_files)
        self.preview_row.set_visible(has_any)
        if not has_any:
            if hasattr(self, "preview_next_btn"):
                self.preview_next_btn.set_visible(False)
            return

        # görseller
        for p in self.pending_images:
            img_path = Path(p)
            if not img_path.exists():
                continue

            item = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            item.set_halign(Gtk.Align.START)

            file = Gio.File.new_for_path(str(img_path.resolve()))
            pic = Gtk.Picture.new_for_file(file)
            pic.set_content_fit(Gtk.ContentFit.COVER)
            pic.set_size_request(96, 72)

            name = Gtk.Label(label=img_path.name)
            name.set_xalign(0)
            name.set_max_width_chars(18)
            name.set_ellipsize(Pango.EllipsizeMode.END)

            item.append(pic)
            item.append(name)
            self.preview_hbox.append(item)

        # belgeler
        for f in self.pending_files:
            p = Path(f.get("path",""))
            if not p.exists():
                continue

            chip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            chip.add_css_class("attach-chip")

            if f.get("edit"):
                chip.add_css_class("attach-edit-on")

            icon = Gtk.Image.new_from_icon_name("text-x-generic-symbolic")
            chip.append(icon)

            lab = Gtk.Label(label=p.name)
            lab.set_xalign(0)
            lab.set_max_width_chars(26)
            lab.set_ellipsize(Pango.EllipsizeMode.END)
            chip.append(lab)

            # tıkla -> edit toggle
            click = Gtk.GestureClick()
            def _on_chip_clicked(_g, _n, _x, _y, item=f):
                item["edit"] = not bool(item.get("edit"))
                self.refresh_attachments_preview()
            click.connect("pressed", _on_chip_clicked)
            chip.add_controller(click)

            self.preview_hbox.append(chip)

        # taşma var mı? (butonu ona göre aç/kapat)
        GLib.idle_add(self._update_preview_overflow)

    def _update_preview_overflow(self):
        try:
            hadj = self.preview_scroller.get_hadjustment()
            if not hadj:
                return False
            overflow = hadj.get_upper() > hadj.get_page_size() + 2
            self.preview_next_btn.set_visible(bool(overflow))
        except Exception:
            pass
        return False

    def scroll_preview_right(self, *_):
        try:
            hadj = self.preview_scroller.get_hadjustment()
            if not hadj:
                return
            step = max(120, hadj.get_page_size() * 0.75)
            hadj.set_value(min(hadj.get_upper() - hadj.get_page_size(), hadj.get_value() + step))
        except Exception:
            pass

    # ---------------- AI ERROR / TYPING ----------------

    def handle_ai_error(self, error_text):
        if hasattr(self, "typing_row"):
            self.chat_box.remove(self.typing_row)
            del self.typing_row
            del self.typing_label

        try:
            with open(self.current_chat, "r", encoding="utf-8") as f:
                messages = json.load(f) or []
        except Exception:
            messages = []

        messages.append({"role": "bot", "content": f"❌ Hata:\n{error_text}"})

        try:
            with open(self.current_chat, "w", encoding="utf-8") as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        self.load_chat()
        self.scroll_to_bottom()

    def show_typing_indicator(self):
        self.typing_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.typing_row.set_halign(Gtk.Align.START)

        bubble = Gtk.Box()
        bubble.add_css_class("bot-bubble")

        self.typing_label = Gtk.Label(label="Düşünüyor")
        bubble.append(self.typing_label)

        self.typing_row.append(bubble)
        self.chat_box.append(self.typing_row)

        self.typing_dots = 0
        GLib.timeout_add(500, self.animate_typing)

        self.scroll_to_bottom()

    def animate_typing(self):
        if not hasattr(self, "typing_label"):
            return False
        dots = "." * (self.typing_dots % 4)
        self.typing_label.set_text(f"Düşünüyor{dots}")
        self.typing_dots += 1
        return True

    def after_ai_response(self):
        if hasattr(self, "typing_row"):
            self.chat_box.remove(self.typing_row)
            del self.typing_row
            del self.typing_label

        self.load_chat()
        self.scroll_to_bottom()

    # ---------------- MODELS LIST ----------------

    def apply_models_visibility(self):
        if not getattr(self, "sidebar_expanded", True):
            self.models_header.set_visible(False)
            self.models_list.set_visible(False)
            return

        self.models_header.set_visible(True)
        self.models_list.set_visible(self.models_list_open)
        self.models_toggle_btn.set_label("AI models ▾" if self.models_list_open else "AI models ▸")

    def on_model_row_activated(self, listbox, row):
        if not row:
            return

        model_id = getattr(row, "model_id", None)
        if not model_id:
            return

        self.set_chat_model(self.current_chat, model_id)

    def toggle_models_list(self, *_):
        self.models_list_open = not self.models_list_open
        self.apply_models_visibility()

    def confirm_delete_model(self, button, model_id: str):
        cfg = self.load_config()
        models = self._ensure_min_one_model(cfg)

        # 1 model kaldıysa sildirme
        if len(models) <= 1:
            dialog = Gtk.Dialog()
            dialog.set_transient_for(self.win)
            dialog.set_modal(True)
            dialog.set_title("Model Silinemez")
            content = dialog.get_content_area()
            content.append(Gtk.Label(label="En az 1 model kalmalı. Son modeli silemezsin."))
            dialog.add_button("Tamam", Gtk.ResponseType.OK)
            dialog.connect("response", lambda d, r: d.destroy())
            dialog.present()
            return

        dialog = Gtk.Dialog()
        dialog.set_transient_for(self.win)
        dialog.set_modal(True)
        dialog.set_title("Model Sil")

        content = dialog.get_content_area()
        label = Gtk.Label(label=f"Bu modeli silmek istiyor musun?\n\n{model_id}")
        label.set_wrap(True)
        content.append(label)

        dialog.add_button("İptal", Gtk.ResponseType.CANCEL)
        dialog.add_button("Sil", Gtk.ResponseType.OK)

        def on_response(d, resp):
            if resp == Gtk.ResponseType.OK:
                cfg2 = self.load_config()
                models2 = self._ensure_min_one_model(cfg2)

                if len(models2) <= 1:
                    d.destroy()
                    return

                models2 = [m for m in models2 if m != model_id]
                cfg2["ai_models"] = models2

                # silinen model chatlerde kullanılıyorsa default’a çek
                chat_models = cfg2.get("chat_models", {})
                if not isinstance(chat_models, dict):
                    chat_models = {}

                new_default = str(models2[0]) if models2 else None
                for k, v in list(chat_models.items()):
                    if v == model_id:
                        chat_models[k] = new_default
                cfg2["chat_models"] = chat_models

                self.save_config(cfg2)

                # aktif chat modeli self-heal
                self.active_model = self.get_chat_model(self.current_chat)

                self.load_models_list()
                self.apply_models_visibility()

            d.destroy()

        dialog.connect("response", on_response)
        dialog.present()

    def open_add_model_dialog(self, *_):
        dialog = Gtk.Dialog()
        dialog.set_transient_for(self.win)
        dialog.set_modal(True)
        dialog.set_title("Model Ekle")

        content = dialog.get_content_area()

        info = Gtk.Label(label="Model ID gir (ör: openai/gpt-4.1-mini)")
        info.set_wrap(True)
        info.set_xalign(0)
        content.append(info)

        entry = Gtk.Entry()
        entry.set_placeholder_text("provider/model (ör: google/gemini-2.5-flash-image)")
        content.append(entry)

        # Ctrl+V ile yapıştırmayı garanti et
        key_controller = Gtk.EventControllerKey()

        def on_key_pressed(controller, keyval, keycode, state):
            ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)

            # hem v hem V yakala
            if ctrl and keyval in (Gdk.KEY_v, Gdk.KEY_V):
                display = Gdk.Display.get_default()
                if not display:
                    return False

                clipboard = display.get_clipboard()

                def on_text(cb, res):
                    try:
                        text = cb.read_text_finish(res) or ""
                    except Exception:
                        text = ""
                    if text:
                        entry.set_text(text.strip())

                clipboard.read_text_async(None, on_text)
                return True

            return False

        key_controller.connect("key-pressed", on_key_pressed)
        entry.add_controller(key_controller)

        # Link
        link = Gtk.LinkButton.new_with_label(
            "https://openrouter.ai/models",
            "OpenRouter – Models sayfasını aç"
        )
        link.set_halign(Gtk.Align.START)
        content.append(link)

        dialog.add_button("İptal", Gtk.ResponseType.CANCEL)
        dialog.add_button("Ekle", Gtk.ResponseType.OK)

        def on_response(d, resp):
            if resp == Gtk.ResponseType.OK:
                model_id = entry.get_text().strip()
                if model_id:
                    # mevcut set_chat_model LRU mantığıyla listeye ekliyor ve bu chat’e atıyor
                    self.set_chat_model(self.current_chat, model_id)
            d.destroy()

        dialog.connect("response", on_response)
        dialog.present()

        def _focus():
            entry.grab_focus()
            return False
        GLib.idle_add(_focus)

    def load_models_list(self):
        while True:
            row = self.models_list.get_first_child()
            if not row:
                break
            self.models_list.remove(row)

        cfg = self.load_config()
        models = self._ensure_min_one_model(cfg)
        active = self.get_chat_model(self.current_chat)
        self.active_model = active

        for model_id in models:
            model_id = str(model_id)

            row = Gtk.ListBoxRow()
            row.model_id = model_id  # <-- önemli

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            box.set_hexpand(True)

            prefix = "✓ " if active == model_id else ""
            label = Gtk.Label(label=prefix + model_id)
            label.set_xalign(0)
            label.set_hexpand(True)
            label.set_halign(Gtk.Align.FILL)
            label.set_single_line_mode(True)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_max_width_chars(22)
            box.append(label)

            trash_btn = Gtk.Button(label="🗑")
            trash_btn.set_tooltip_text("Modeli sil")
            trash_btn.set_size_request(30, 30)
            trash_btn.add_css_class("flat")
            trash_btn.connect("clicked", self.confirm_delete_model, model_id)
            box.append(trash_btn)

            row.set_child(box)
            self.models_list.append(row)

    # ---------------- RENAME POPOVER (ESKİ ÖZELLİK) ----------------

    def open_rename_popover(self, anchor_btn: Gtk.Button, file_path: Path, menu_popover: Gtk.Popover):
        menu_popover.popdown()

        rename_pop = Gtk.Popover()
        rename_pop.set_parent(anchor_btn)
        rename_pop.set_position(Gtk.PositionType.BOTTOM)
        rename_pop.set_has_arrow(True)
        rename_pop.set_autohide(False)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)

        title = Gtk.Label(label="Yeni isim:")
        title.set_halign(Gtk.Align.START)
        vbox.append(title)

        entry = Gtk.Entry()
        entry.set_placeholder_text("ör: my_chat")
        entry.set_text(file_path.stem)

        def do_rename(*_):
            self.rename_chat_file(file_path, entry.get_text(), rename_pop)

        entry.connect("activate", do_rename)
        vbox.append(entry)

        hint = Gtk.Label(label="(Dosya adı olarak kaydedilir)")
        hint.set_halign(Gtk.Align.START)
        hint.add_css_class("dim-label")
        vbox.append(hint)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label="İptal")
        save_btn = Gtk.Button(label="Kaydet")
        save_btn.add_css_class("suggested-action")

        cancel_btn.connect("clicked", lambda *_: rename_pop.popdown())
        save_btn.connect("clicked", do_rename)

        btn_row.append(cancel_btn)
        btn_row.append(save_btn)
        vbox.append(btn_row)

        rename_pop.set_child(vbox)
        rename_pop.popup()

        # focus/select
        def _focus():
            entry.select_region(0, -1)
            entry.grab_focus()
            return False
        GLib.idle_add(_focus)

    def rename_chat_file(self, old_path: Path, new_name_raw: str, pop: Gtk.Popover):
        new_name = (new_name_raw or "").strip()
        if not new_name:
            return

        for ch in ["/", "\\", "\n", "\r", "\t"]:
            new_name = new_name.replace(ch, "_")

        new_path = old_path.with_name(new_name + ".json")

        if new_path == old_path:
            pop.popdown()
            return

        if new_path.exists():
            print(f"Rename failed: {new_path.name} zaten var.")
            return

        try:
            old_path.rename(new_path)
        except Exception as e:
            print("Rename error:", e)
            return

        # pinned update + last_chat update + chat_models update
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

        pop.popdown()
        self.load_chat_list()
        self.load_models_list()
        self.load_chat()

    # ---------------- PIN TOGGLE (ESKİ ÖZELLİK) ----------------

    def toggle_pin_chat(self, file_path: Path):
        cfg = self.load_config()
        pinned = cfg.get("pinned_chats", [])
        if not isinstance(pinned, list):
            pinned = []

        name = file_path.name
        if name in pinned:
            pinned.remove(name)
        else:
            pinned.append(name)

        cfg["pinned_chats"] = pinned
        self.save_config(cfg)
        self.load_chat_list()

    # ---------------- API KEY DIALOG ----------------

    def open_key_dialog(self, button):
        dialog = Gtk.Dialog()
        dialog.set_transient_for(self.win)
        dialog.set_modal(True)
        dialog.set_title("OpenRouter API Key")

        content = dialog.get_content_area()

        entry = Gtk.Entry()
        entry.set_placeholder_text("OpenRouter API Key girin...")
        entry.set_visibility(False)
        content.append(entry)

        dialog.add_button("İptal", Gtk.ResponseType.CANCEL)
        dialog.add_button("Kaydet", Gtk.ResponseType.OK)

        def on_response(dialog, response):
            if response == Gtk.ResponseType.OK:
                new_key = entry.get_text().strip()
                if new_key:
                    cfg = self.load_config()
                    cfg["open_router_key"] = new_key
                    self.save_config(cfg)
            dialog.destroy()

        dialog.connect("response", on_response)
        dialog.present()

    # ---------------- CHAT LIST ----------------

    def load_chat_list(self):
        while True:
            row = self.chat_list.get_first_child()
            if not row:
                break
            self.chat_list.remove(row)

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

        for file in sorted(files, key=sort_key):
            row = Gtk.ListBoxRow()
            row.chat_path = file

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            box.set_hexpand(True)

            if file.name in pinned:
                pin_label = Gtk.Label(label="📌")
                pin_label.set_xalign(0)
                box.append(pin_label)

            label = Gtk.Label(label=file.stem)
            label.set_xalign(0)
            label.set_hexpand(True)
            label.set_halign(Gtk.Align.FILL)
            box.append(label)

            more_btn = Gtk.Button(label="⋯")
            more_btn.set_tooltip_text("Seçenekler")
            more_btn.set_size_request(30, 30)
            more_btn.add_css_class("flat")
            box.append(more_btn)

            popover = Gtk.Popover()
            popover.set_autohide(True)
            popover.set_has_arrow(True)
            popover.set_position(Gtk.PositionType.BOTTOM)
            popover.set_parent(more_btn)

            pop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            pop_box.set_margin_top(8)
            pop_box.set_margin_bottom(8)
            pop_box.set_margin_start(8)
            pop_box.set_margin_end(8)

            # Pin toggle
            is_pinned = file.name in pinned
            pin_item = Gtk.Button(label=("Sabiti kaldır" if is_pinned else "Sabitle"))
            pin_item.set_halign(Gtk.Align.FILL)

            def _toggle_pin(_btn, f=file, p=popover):
                p.popdown()
                self.toggle_pin_chat(f)

            pin_item.connect("clicked", _toggle_pin)
            pop_box.append(pin_item)

            # Rename
            rename_item = Gtk.Button(label="İsmi değiştir")
            rename_item.set_halign(Gtk.Align.FILL)
            rename_item.connect(
                "clicked",
                lambda *_, f=file, p=popover, anchor=more_btn: self.open_rename_popover(anchor, f, p)
            )
            pop_box.append(rename_item)

            # Delete
            del_item = Gtk.Button(label="Chat'i sil")
            del_item.set_halign(Gtk.Align.FILL)
            del_item.connect("clicked", lambda *_, f=file, p=popover: (p.popdown(), self.delete_chat(None, f)))
            pop_box.append(del_item)

            popover.set_child(pop_box)
            more_btn.connect("clicked", lambda *_, p=popover: p.popup())

            row.set_child(box)
            self.chat_list.append(row)

            if file == self.current_chat:
                GLib.idle_add(self.chat_list.select_row, row)

    # ---------------- CHAT DELETE ----------------

    def delete_chat(self, button, file_path):
        dialog = Gtk.Dialog()
        dialog.set_transient_for(self.win)
        dialog.set_modal(True)
        dialog.set_title("Chat Sil")

        content = dialog.get_content_area()
        label = Gtk.Label(label="Bu chat silinsin mi?\nBu işlem geri alınamaz.")
        label.set_wrap(True)
        content.append(label)

        dialog.add_button("İptal", Gtk.ResponseType.CANCEL)
        dialog.add_button("Sil", Gtk.ResponseType.OK)

        def on_response(dialog, response):
            if response == Gtk.ResponseType.OK:
                if file_path.exists():
                    file_path.unlink()

                cfg = self.load_config()

                pinned = cfg.get("pinned_chats", [])
                if isinstance(pinned, list) and file_path.name in pinned:
                    cfg["pinned_chats"] = [x for x in pinned if x != file_path.name]

                # chat_models cleanup
                chat_models = cfg.get("chat_models", {})
                if isinstance(chat_models, dict) and file_path.name in chat_models:
                    del chat_models[file_path.name]
                    cfg["chat_models"] = chat_models

                if cfg.get("last_chat") == file_path.name:
                    cfg["last_chat"] = "default.json"

                self.save_config(cfg)

                if self.current_chat == file_path:
                    chats = list(CHAT_DIR.glob("*.json"))
                    if chats:
                        self.current_chat = chats[0]
                    else:
                        DEFAULT_CHAT.write_text("[]", encoding="utf-8")
                        self.current_chat = DEFAULT_CHAT

                # active model for new current chat
                self.active_model = self.get_chat_model(self.current_chat)

                self.load_chat_list()
                self.load_chat()
                self.load_models_list()

            dialog.destroy()

        dialog.connect("response", on_response)
        dialog.present()

    # ---------------- CHAT VISIBILITY / SIDEBAR ----------------

    def apply_chats_visibility(self):
        if not getattr(self, "sidebar_expanded", True):
            self.chat_list.set_visible(False)
            self.chats_toggle_btn.set_label("Chats ▾" if self.chats_list_open else "Chats ▸")
            return
        self.chat_list.set_visible(self.chats_list_open)
        self.chats_toggle_btn.set_label("Chats ▾" if self.chats_list_open else "Chats ▸")

    def toggle_chats_list(self, *_):
        self.chats_list_open = not self.chats_list_open
        self.apply_chats_visibility()

    def toggle_sidebar(self, button):
        if self.sidebar_expanded:
            self.sidebar.set_size_request(60, -1)
            self.sidebar_expanded = False
            self.chats_toggle_btn.set_visible(False)
            self.apply_chats_visibility()
            self.apply_models_visibility()
        else:
            self.sidebar.set_size_request(250, -1)
            self.sidebar.set_hexpand(False)
            self.sidebar.set_vexpand(True)
            self.sidebar_expanded = True
            self.chats_toggle_btn.set_visible(True)
            self.apply_chats_visibility()
            self.apply_models_visibility()

    # ----------------COPY / REGENERATE --------------------

    def find_prev_user_index(self, messages: list, from_idx: int):
        j = from_idx - 1
        while j >= 0:
            if messages[j].get("role") == "user":
                return j
            j -= 1
        return None

    def build_regen_prompt_for_bot(self, question: str, answer: str) -> str:
        return (
            "Aşağıdaki soru ve verilen cevaba benzer bir sonuç üret.\n"
            "Aynı yaklaşımı ve içeriği koru, ama metni birebir kopyalama; yeniden yaz "
            "ve mümkünse küçük iyileştirmeler yap.\n\n"
            "[SORU]\n"
            f"{question.strip()}\n\n"
            "[ÖNCEKİ CEVAP]\n"
            f"{answer.strip()}\n"
        )

    def copy_message_by_index(self, idx: int):
        try:
            with open(self.current_chat, "r", encoding="utf-8") as f:
                messages = json.load(f) or []
        except Exception:
            return

        if not (0 <= idx < len(messages)):
            return

        content = (messages[idx].get("content") or "")
        if not content:
            return

        inner = self.extract_copy_block(content)
        self.copy_to_clipboard(inner if inner is not None else content)

    def regenerate_by_index(self, idx: int):
            # 1) Chat'i oku
        try:
            with open(self.current_chat, "r", encoding="utf-8") as f:
                messages = json.load(f) or []
        except Exception:
            return

        if not (0 <= idx < len(messages)):
            return

        role = (messages[idx].get("role") or "").strip()
        content = (messages[idx].get("content") or "").strip()
        if not content:
            return

        # 2) regen_text üret
        regen_text = None
        q_idx = None

        if role == "user":
            # user seçiliyse: aynısını tekrar sor
            regen_text = content
        else:
            # bot seçiliyse: bağlı user sorusunu bul + bot cevabı ile benzer üret
            q_idx = self.find_prev_user_index(messages, idx)
            question = (messages[q_idx].get("content") or "").strip() if q_idx is not None else ""

            # bot cevabı copy bloğuysa içeriğini al (daha iyi prompt)
            ans_inner = self.extract_copy_block(content)
            answer = ans_inner if ans_inner is not None else content

            if question:
                # build_regen_prompt_for_bot senin mevcut fonksiyonun (eski özellik)
                regen_text = self.build_regen_prompt_for_bot(question, answer)
            else:
                # user bulunamadıysa sadece cevaba benzer üret
                regen_text = (
                    "Aşağıdaki cevaba benzer bir sonuç üret. Metni birebir kopyalama; yeniden yaz ve iyileştir.\n\n"
                    f"[ÖNCEKİ CEVAP]\n{answer}\n"
                )

        if not regen_text:
            return

        # 3) Referans zinciri: seçilen mesajın used_refs'lerini de dahil et
        #    (böylece içinde referans olan mesaj regenerate edilirken foto/ref kaybolmaz)
        ref_set = set()
        ref_set.add(idx)

        used = messages[idx].get("used_refs") or []
        if isinstance(used, list):
            for j in used:
                if isinstance(j, int) and 0 <= j < len(messages):
                    ref_set |= self.expand_ref_chain(messages, j)

        # bot seçildiyse bağlı user'ı da dahil et + onun zinciri
        if role != "user" and q_idx is not None:
            ref_set.add(q_idx)
            used_q = messages[q_idx].get("used_refs") or []
            if isinstance(used_q, list):
                for j in used_q:
                    if isinstance(j, int) and 0 <= j < len(messages):
                        ref_set |= self.expand_ref_chain(messages, j)

        selected_arg = ",".join(str(x) for x in sorted(ref_set))

        # 4) Chat sonuna yeni user mesajı ekle (regen flag + referans meta + preview)
        new_user = {
            "role": "user",
            "content": regen_text,
            "regen": True,  # regenerate rengi/işareti
            "used_refs": sorted(ref_set),  # AI'ya giden referans setiyle uyumlu meta
        }

        # UI'da karışmaması için: seçilen balon + (bot ise bağlı user) ayrı gruplar
        groups = []

        def _collect_group_for_index(ridx: int):
            if not (0 <= ridx < len(messages)):
                return None
            rmsg = messages[ridx]
            items = []

            # referans mesajının kendi önceki preview'ları (yeni format)
            rg = rmsg.get("refs_groups")
            if isinstance(rg, list) and rg:
                for g in rg:
                    its = g.get("items") if isinstance(g, dict) else None
                    if isinstance(its, list):
                        for it in its:
                            if isinstance(it, dict) and it.get("text"):
                                items.append({"role": it.get("role", ""), "text": it.get("text", "")})
            else:
                # eski format kalmış olabilir
                rp = rmsg.get("refs_preview")
                if isinstance(rp, list) and rp:
                    for it in rp:
                        if isinstance(it, dict) and it.get("text"):
                            items.append({"role": it.get("role", ""), "text": it.get("text", "")})

            # en sona referans mesajın kendisini koy (metin + image varsa pack_preview_item ekler)
            try:
                items.append(self.pack_preview_item(rmsg))
            except Exception:
                # pack_preview_item yoksa yine de minimum göster
                rrole = (rmsg.get("role") or "").strip()
                rtext = (rmsg.get("content") or "").strip()
                if not rtext and rmsg.get("image"):
                    rtext = "[image]"
                items.append({"role": rrole, "text": rtext})

            return {"items": items}

        g1 = _collect_group_for_index(idx)
        if g1 is not None:
            groups.append(g1)

        if role != "user" and q_idx is not None:
            g2 = _collect_group_for_index(q_idx)
            if g2 is not None:
                groups.append(g2)

        new_user["refs_groups"] = groups

        messages.append(new_user)

        try:
            with open(self.current_chat, "w", encoding="utf-8") as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
        except Exception:
            return

        # 5) UI: seçim temizle + typing indicator
        self.selected_indexes.clear()
        self.selection_mode = False
        self.update_selection_label()
        self.auto_scroll_enabled = True
        self.load_chat()
        self.show_typing_indicator()

        # 6) AI çağır: zincir referanslarla birlikte
        threading.Thread(target=self.call_ai, args=(selected_arg,), daemon=True).start()

    def expand_ref_chain(self, messages: list, idx: int, seen=None) -> set[int]:
        if seen is None:
            seen = set()
        if idx in seen:
            return seen
        seen.add(idx)

        msg = messages[idx] if 0 <= idx < len(messages) else None
        if not isinstance(msg, dict):
            return seen

        used = msg.get("used_refs") or []
        if isinstance(used, list):
            for j in used:
                if isinstance(j, int) and 0 <= j < len(messages):
                    self.expand_ref_chain(messages, j, seen)
        return seen

    def pack_preview_item(self, rmsg: dict) -> dict:
        rrole = (rmsg.get("role") or "").strip()
        rtext = (rmsg.get("content") or "").strip()
        has_img = bool(rmsg.get("image"))

        if not rtext and has_img:
            rtext = "[image]"
        elif has_img:
            # metin + image birlikteyse anlaşılır olsun
            rtext = rtext + "  + [image]"

        return {"role": rrole, "text": rtext}

    # ---------------- CHAT CREATE / SWITCH ----------------

    def create_chat(self, button):
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

        # yeni chat default model alır
        models = self._ensure_min_one_model(cfg)
        chat_models = cfg.get("chat_models", {})
        if not isinstance(chat_models, dict):
            chat_models = {}
        chat_models[path.name] = str(models[0])
        cfg["chat_models"] = chat_models
        self.save_config(cfg)

        self.active_model = self.get_chat_model(self.current_chat)

        self.load_chat_list()
        self.load_chat()
        self.load_models_list()

        if not self.sidebar_expanded:
            self.toggle_sidebar(None)

        self.auto_focus_enabled = True
        GLib.idle_add(self.force_focus_entry)

    def switch_chat(self, listbox, row):
        if not row:
            return
        chat_path = getattr(row, "chat_path", None)
        if not chat_path:
            return

        self.current_chat = Path(chat_path)

        self.selected_indexes.clear()
        self.selection_mode = False
        self.update_selection_label()

        cfg = self.load_config()
        cfg["last_chat"] = self.current_chat.name
        self.save_config(cfg)

        self.selected_indexes.clear()
        self.selection_mode = False
        self.selection_label.set_text("")

        self.active_model = self.get_chat_model(self.current_chat)

        self.load_chat()
        self.load_models_list()

        self.auto_focus_enabled = True
        GLib.idle_add(self.force_focus_entry)

    # ---------------- CHAT LOAD / SELECTION ----------------

    def clear_selection(self, *_):
        # tüm seçimleri kaldır
        self.selected_indexes.clear()

        # seçim modunu kapat
        self.selection_mode = False

        # label güncelle + checkboxları kaldırmak için chat’i refresh et
        self.update_selection_label()
        self.load_chat()

    def load_chat(self):
        while True:
            child = self.chat_box.get_first_child()
            if not child:
                break
            self.chat_box.remove(child)

        with open(self.current_chat, "r", encoding="utf-8") as f:
            messages = json.load(f) or []

        for i, msg in enumerate(messages):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            row.set_hexpand(False)

            bubble = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            bubble.set_hexpand(False)

            # Hover shadow (eski özellik)
            motion = Gtk.EventControllerMotion()
            motion.connect("enter", lambda c, b=bubble: b.add_css_class("hovered"))
            motion.connect("leave", lambda c, b=bubble: b.remove_css_class("hovered"))
            bubble.add_controller(motion)

            # Click selection (eski özellik)
            click = Gtk.GestureClick()
            click.connect("pressed", lambda g, n, x, y, idx=i: self.on_message_clicked(idx))
            bubble.add_controller(click)

            # Referans preview (mesaj referansla gönderildiyse)
            groups = msg.get("refs_groups") or []
            if isinstance(groups, list) and groups:
                outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
                outer.add_css_class("refs-groups")

                for g in groups:
                    items = g.get("items") if isinstance(g, dict) else None
                    if not isinstance(items, list) or not items:
                        continue

                    mini = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                    mini.add_css_class("refs-preview")  # aynı background mantığı

                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        rrole = (it.get("role") or "").strip()
                        rtext = (it.get("text") or "").strip()
                        if not rtext:
                            continue

                        if len(rtext) > 200:
                            rtext = rtext[:200] + "..."

                        line = f"{rrole}: {rtext}" if rrole else rtext
                        lab = Gtk.Label(label=line)
                        lab.set_wrap(True)
                        lab.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
                        lab.set_xalign(0)
                        lab.add_css_class("refs-preview-line")
                        mini.append(lab)

                    outer.append(mini)

                bubble.append(outer)

            if msg.get("content"):
                content = msg["content"]
                title_block = self.extract_title_block(content)
                copy_block = self.extract_copy_block(content)
                apply_block = self.extract_apply_block(content)
                apply_ops = None
                apply_err = ""

                if apply_block is not None:
                    apply_ops, apply_err = self.parse_apply_ops(apply_block)

                apply_summary = ""
                if apply_ops:
                    apply_summary = self.build_apply_summary(apply_ops)

                if copy_block is not None:
                     # 🔹 Tek renk kod bloğu container (Title + Kopyala + Kod aynı alan)
                    code_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
                    code_container.add_css_class("code-block")

                    # 🔹 Üst satır: Title solda, Kopyala sağda
                    top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                    top_row.set_hexpand(True)

                    if title_block:
                        title_label = Gtk.Label()
                        safe = GLib.markup_escape_text(title_block.strip())
                        title_label.set_markup(f"<b>{safe}</b>")
                        title_label.set_xalign(0)
                        title_label.set_halign(Gtk.Align.START)
                        top_row.append(title_label)

                    spacer = Gtk.Box()
                    spacer.set_hexpand(True)
                    top_row.append(spacer)

                    copy_btn = Gtk.Button(label="Kopyala")
                    copy_btn.add_css_class("flat")
                    copy_btn.add_css_class("code-copy-btn")
                    copy_btn.set_halign(Gtk.Align.END)
                    copy_btn.set_focusable(False)

                    self._consume_click(copy_btn)
                    copy_btn.connect("clicked", lambda b, t=copy_block: self.copy_to_clipboard(t))
                    top_row.append(copy_btn)

                    # 🔹 Kod label
                    code_label = Gtk.Label(label=copy_block)
                    code_label.set_wrap(True)
                    code_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
                    code_label.set_xalign(0)
                    code_label.set_width_chars(0)
                    code_label.set_max_width_chars(60)

                    code_container.append(top_row)
                    code_container.append(code_label)

                    bubble.append(code_container)
                else:
                    # 🔹 Normal mesaj
                    show_text = content

                    # Eğer apply ops varsa, bot mesajında content yerine özet satırı göster
                    if msg.get("role") != "user" and apply_ops and apply_summary:
                        show_text = apply_summary

                    label = Gtk.Label(label=show_text)
                    label.set_wrap(True)
                    label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
                    label.set_xalign(0)
                    label.set_width_chars(0)
                    label.set_max_width_chars(60)
                    label.set_hexpand(False)

                    bubble.append(label)

            # Tekli image (legacy)
            if msg.get("image"):
                img_path = Path(msg["image"])
                if img_path.exists():
                    file = Gio.File.new_for_path(str(img_path))
                    pic = Gtk.Picture.new_for_file(file)
                    pic.set_content_fit(Gtk.ContentFit.CONTAIN)
                    pic.set_size_request(120, 80)
                    bubble.append(pic)

            # Çoklu images (yeni)
            imgs = msg.get("images")
            if isinstance(imgs, list) and imgs:
                row_imgs = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                row_imgs.set_halign(Gtk.Align.START)

                for ip in imgs:
                    p = Path(str(ip))
                    if not p.exists():
                        continue
                    file = Gio.File.new_for_path(str(p))
                    pic = Gtk.Picture.new_for_file(file)
                    pic.set_content_fit(Gtk.ContentFit.COVER)
                    pic.set_size_request(120, 80)
                    row_imgs.append(pic)

                bubble.append(row_imgs)

            # Files (yeni)
            files = msg.get("files")
            if isinstance(files, list) and files:
                files_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                for f in files:
                    if not isinstance(f, dict):
                        continue
                    name = (f.get("name") or Path(str(f.get("path") or "")).name or "").strip()
                    if not name:
                        continue

                    chip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                    chip.add_css_class("refs-preview")

                    icon = Gtk.Image.new_from_icon_name("text-x-generic-symbolic")
                    chip.append(icon)

                    lab = Gtk.Label(label=name)
                    lab.set_xalign(0)
                    lab.set_max_width_chars(40)
                    lab.set_ellipsize(Pango.EllipsizeMode.END)
                    chip.append(lab)

                    files_box.append(chip)

                bubble.append(files_box)

            if msg.get("role") == "user":
                bubble.add_css_class("user-bubble")

                if msg.get("regen"):
                    bubble.add_css_class("user-bubble-regen")
                elif msg.get("used_refs"):
                    bubble.add_css_class("user-bubble-ref")

                row.set_halign(Gtk.Align.END)
                bubble.set_halign(Gtk.Align.END)
            else:
                bubble.add_css_class("bot-bubble")
                row.set_halign(Gtk.Align.START)

            if i in self.selected_indexes:
                bubble.add_css_class("selected")

            # ---------------- APPLY BUTTONS ----------------
            if msg.get("role") != "user":
                # daha önce sonuç yazıldıysa buton göstermeyelim, sadece feedback gösterelim
                st = msg.get("apply_status")
                if isinstance(st, dict) and "status" in st:
                    status = st.get("status")
                    err = (st.get("err") or "").strip()

                    if status == "ok":
                        txt = "✅ Dosya değiştirildi."
                    elif status == "fail":
                        txt = f"❌ APPLY FAILED: {err}"
                    elif status == "cancel":
                        txt = "⏭️ İşlem iptal edildi."
                    else:
                        txt = ""

                    if txt:
                        status_label = Gtk.Label(label=txt)
                        status_label.set_wrap(True)
                        status_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
                        status_label.set_xalign(0)
                        status_label.add_css_class("refs-preview-line")  # hafif/sönük görünsün istersen
                        bubble.append(status_label)

                else:
                    content_text = msg.get("content") or ""
                    apply_block = self.extract_apply_block(content_text)

                    if apply_block:
                        ops, parse_err = self.parse_apply_ops(apply_block)

                        # KRİTİK: ops varsa bile ancak path'ler gerçek dosyaysa buton göster
                        valid_ops = []
                        if isinstance(ops, list) and ops:
                            valid = True
                            for op in ops:
                                p_raw = str((op or {}).get("path") or "").strip()
                                p = Path(p_raw)
                                # absolute değilse veya dosya yoksa -> hiç buton gösterme
                                if (not p.is_absolute()) or (not p.exists()):
                                    valid = False
                                    break
                            if valid:
                                valid_ops = ops

                        if valid_ops:
                            btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                            btn_row.set_halign(Gtk.Align.START)

                            apply_btn = Gtk.Button(label="Uygula")
                            apply_btn.add_css_class("suggested-action")
                            self._consume_click(apply_btn)

                            reject_btn = Gtk.Button(label="Reddet")
                            reject_btn.add_css_class("flat")
                            self._consume_click(reject_btn)

                            def _on_apply(_b, _ops=valid_ops, _idx=i):
                                # çift tıklama vs engelle
                                apply_btn.set_sensitive(False)
                                reject_btn.set_sensitive(False)

                                ok, err = self.apply_ops_yes(_ops)

                                if ok:
                                    self._set_apply_status(_idx, "ok")
                                else:
                                    self._set_apply_status(_idx, "fail", err)
                                    GLib.idle_add(self.apply_failed_to_input, err)

                                # UI yenile
                                self.load_chat()
                                self.scroll_to_bottom(force=True)

                            def _on_reject(_b, _idx=i):
                                # İstersen "iptal edildi" de gösterebilirsin:
                                self._set_apply_status(_idx, "cancel")
                                # self._set_apply_status(_idx, False, "rejected")
                                self.load_chat()
                                self.scroll_to_bottom(force=True)

                            apply_btn.connect("clicked", _on_apply)
                            reject_btn.connect("clicked", _on_reject)

                            btn_row.append(apply_btn)
                            btn_row.append(reject_btn)

                            bubble.append(btn_row)

                        # parse_err varsa bile input'a basma; sadece buton göstermemek daha doğru
                        # (çünkü her bot mesajında parse_err input’u kirletir)

            # Tek seçili balonda action butonları (copy + regenerate)
            show_actions = (len(self.selected_indexes) == 1 and i in self.selected_indexes)

            # bubble + buton alanı (spacer)
            content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

            btn_space = Gtk.Box()
            btn_space.set_size_request(130, -1)  # buton alanı (70-120 ayarla)

            if msg.get("role") == "user":
                # user sağda → butonlar SOLDA: [space][bubble]
                content.append(btn_space)
                content.append(bubble)
            else:
                # bot solda → butonlar SAĞDA: [bubble][space]
                content.append(bubble)
                content.append(btn_space)

            wrapper = Gtk.Overlay()
            wrapper.set_child(content)

            if show_actions:
                actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

                copy_btn = Gtk.Button(label="📋")
                self._consume_click(copy_btn)
                copy_btn.connect("clicked", lambda _b, idx=i: self.copy_message_by_index(idx))

                regen_btn = Gtk.Button(label="♻")
                self._consume_click(regen_btn)
                regen_btn.connect("clicked", lambda _b, idx=i: self.regenerate_by_index(idx))

                actions.append(copy_btn)
                actions.append(regen_btn)

                actions.set_valign(Gtk.Align.CENTER)

                # BUTONLAR spacer tarafına yaslanacak:
                if msg.get("role") == "user":
                    actions.set_halign(Gtk.Align.START)   # sol spacer içinde kalsın
                    actions.set_margin_start(0)
                else:
                    actions.set_halign(Gtk.Align.END)     # sağ spacer içinde kalsın
                    actions.set_margin_end(0)

                wrapper.add_overlay(actions)

            row.append(wrapper)
            self.chat_box.append(row)

        GLib.idle_add(self.scroll_to_bottom)

    def on_message_clicked(self, index):
        self.auto_scroll_enabled = False
        if not self.selection_mode:
            self.selection_mode = True
            self.selected_indexes.add(index)
        else:
            if index in self.selected_indexes:
                self.selected_indexes.remove(index)
            else:
                self.selected_indexes.add(index)

        if not self.selected_indexes:
            self.selection_mode = False

        self.update_selection_label()
        self.load_chat()

    def update_selection_label(self):
        if not self.selected_indexes:
            self.selection_label.set_text("")
            self.selection_row.set_opacity(0.0)
            self.selection_row.set_sensitive(False)
        else:
            self.selection_label.set_text(f"{len(self.selected_indexes)} mesaj referans seçildi")
            self.selection_row.set_opacity(1.0)
            self.selection_row.set_sensitive(True)

    def scroll_to_bottom(self, force=False):
        if not self.auto_scroll_enabled and not force:
            return

        adj = self.scroll.get_vadjustment()
        if adj:
            adj.set_value(adj.get_upper() - adj.get_page_size())

    def on_scroll_button_clicked(self, *_):
        self.auto_scroll_enabled = True
        self.scroll_to_bottom(force=True)
        self.scroll_btn.set_visible(False)

    def on_scroll_changed(self, adjustment):
        # en altta mı kontrol et
        at_bottom = adjustment.get_value() >= (
            adjustment.get_upper() - adjustment.get_page_size() - 800
        )

        if at_bottom:
            self.scroll_btn.set_visible(False)
        else:
            self.scroll_btn.set_visible(True)

    # ---------------- VOICE INPUT -------------------

    def toggle_voice_input(self, *_):
        # Eğer kayıt açıksa: durdur + transcribe
        if self._voice_proc and self._voice_proc.poll() is None:
            try:
                # pw-record için en güvenlisi SIGINT (Ctrl+C gibi)
                self._voice_proc.send_signal(signal.SIGINT)
            except Exception:
                try:
                    self._voice_proc.terminate()
                except Exception:
                    pass

            try:
                self._voice_proc.wait(timeout=3)
            except Exception:
                try:
                    self._voice_proc.kill()
                except Exception:
                    pass

            self._voice_proc = None

            self.mic_btn.set_label("🎙️")
            self.mic_btn.set_tooltip_text("Konuşarak yaz (başlat/durdur)")

            # transcribe arka planda
            threading.Thread(target=self._transcribe_last_audio, daemon=True).start()
            return

        # Kayıt başlat
        tmp = Path(tempfile.gettempdir())
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self._last_wav = tmp / f"capture-ai-mic-{stamp}.wav"

        pw = shutil.which("pw-record")
        ar = shutil.which("arecord")

        if pw:
            cmd = [pw, "--rate", "16000", "--channels", "1", str(self._last_wav)]
        elif ar:
            cmd = [ar, "-f", "S16_LE", "-r", "16000", "-c", "1", str(self._last_wav)]
        else:
            self.handle_ai_error("pw-record veya arecord bulunamadı.")
            return

        try:
            self._voice_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            self._voice_proc = None
            self.handle_ai_error(f"Ses kaydı başlatılamadı: {e}")
            return

        self.mic_btn.set_label("⏹")
        self.mic_btn.set_tooltip_text("Kaydı durdur")

    def _record_wav_proc(self, out_path: Path, samplerate=16000, channels=1):
        # PipeWire varsa pw-record kullan, yoksa arecord
        pw = shutil.which("pw-record")
        ar = shutil.which("arecord")

        if pw:
            # pw-record --rate 16000 --channels 1 out.wav
            cmd = [pw, "--rate", str(samplerate), "--channels", str(channels), str(out_path)]
        elif ar:
            # arecord -f S16_LE -r 16000 -c 1 out.wav
            cmd = [ar, "-f", "S16_LE", "-r", str(samplerate), "-c", str(channels), str(out_path)]
        else:
            raise RuntimeError("pw-record veya arecord bulunamadı")

        self._voice_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

        # stop flag gelene kadar bekle
        while not self._rec_stop.is_set():
            GLib.usleep(50_000)  # 50ms

        # durdur
        try:
            self._voice_proc.terminate()
        except Exception:
            pass

        try:
            self._voice_proc.wait(timeout=2)
        except Exception:
            try:
                self._voice_proc.kill()
            except Exception:
                pass

    def _append_to_input(self, text: str):
        buf = self.textview.get_buffer()
        it = buf.get_iter_at_mark(buf.get_insert())
        if buf.get_char_count() > 0:
            buf.insert(it, " ")
        buf.insert(it, text)

    def _transcribe_last_audio(self):
        wav = self._last_wav
        if not wav or not Path(wav).exists():
            return

        cfg = self.load_config()
        is_online = bool(cfg.get("is_mic_online", True))

        try:
            if is_online:
                text = self._stt_online_openrouter(wav, cfg)
            else:
                text = self._stt_offline_whisper_cpp(wav, cfg)
        except Exception as e:
            GLib.idle_add(self.handle_ai_error, f"STT hata: {e}")
            return

        print("STT MODE:", "online" if is_online else "offline")
        print("STT RAW TEXT:", repr(text))

        if text:
            GLib.idle_add(self._append_to_input, text.strip())

    def _stt_online_openrouter(self, wav_path: Path, cfg: dict) -> str:
        import requests, json

        key = (cfg.get("open_router_key") or "").strip()
        if not key:
            raise RuntimeError("open_router_key yok")

        model = (cfg.get("stt_model_online") or "openai/gpt-audio-mini").strip()

        audio_b64 = base64.b64encode(Path(wav_path).read_bytes()).decode("utf-8")

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text":
                         "Return ONLY the raw transcription text. No explanations. No prefixes. No extra words."
                        },
                        {"type": "input_audio", "input_audio": {"data": audio_b64, "format": "wav"}},
                    ],
                }
            ],
            "stream": False,
        }

        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost",
                "X-Title": "capture-ai",
            },
            json=payload,
            timeout=120,
        )

        if r.status_code != 200:
            raise RuntimeError(r.text[:500])

        data = r.json()
        return (data["choices"][0]["message"]["content"] or "").strip()

    def _stt_offline_whisper_cpp(self, wav_path: Path, cfg: dict) -> str:
        import tempfile

        bin_path = (cfg.get("whisper_cpp_bin") or "").strip()
        model_path = (cfg.get("whisper_cpp_model") or "").strip()

        if not bin_path or not Path(bin_path).exists():
            raise RuntimeError(f"whisper_cpp_bin bulunamadı: {bin_path}")
        if not model_path or not Path(model_path).exists():
            raise RuntimeError(f"whisper_cpp_model bulunamadı: {model_path}")

        outdir = Path(tempfile.gettempdir()) / "capture-ai-stt"
        outdir.mkdir(parents=True, exist_ok=True)
        outbase = outdir / Path(wav_path).stem

        cmd = [
            bin_path,
            "-m", model_path,
            "-f", str(wav_path),
            "-l", "tr",
            "-otxt",
            "-of", str(outbase),
        ]

        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError((p.stderr or p.stdout or "whisper.cpp failed")[:800])

        txt = Path(str(outbase) + ".txt")
        if not txt.exists():
            # bazı sürümlerde .txt yerine stdout'a basabilir—fallback
            s = (p.stdout or "").strip()
            return s
        return txt.read_text(encoding="utf-8", errors="ignore").strip()

    # ---------------- CHANGE CODE FILES -------------

    def apply_failed_to_input(self, err: str):
        if not err:
            err = "unknown error"

        buf = self.textview.get_buffer()
        # input'u temizle ve hata bas (istersen temizleme, sadece append de yapabilirsin)
        buf.set_text(f"❌ APPLY FAILED: {err}")
        self.textview.grab_focus()

    def _apply_edit_op(self, file_path: str, find: str, mode: str, text: str) -> tuple[bool, str]:
        """
        mode: "before" | "after" | "replace"
        find: dosyada bulunacak anchor string
        text: eklenecek / değiştirilecek içerik
        return: (ok, err)
        """
        try:
            p = Path(file_path)
            if not p.exists():
                return False, f"file not found: {p}"

            original = p.read_text(encoding="utf-8", errors="ignore")

            idx = original.find(find)
            if idx < 0:
                return False, f"find failed: anchor not found in {p.name}"

            if mode == "before":
                new_content = original[:idx] + text + original[idx:]
            elif mode == "after":
                new_content = original[:idx + len(find)] + text + original[idx + len(find):]
            elif mode == "replace":
                new_content = original.replace(find, text, 1)  # sadece ilk eşleşme
            else:
                return False, f"unknown mode: {mode}"

            if new_content == original:
                return False, "no changes produced (maybe identical content?)"

            p.write_text(new_content, encoding="utf-8")
            return True, ""
        except Exception as e:
            return False, f"exception: {e}"

    def apply_ops_yes(self, ops) -> tuple[bool, str]:
        """
        ops: parse edilmiş operasyon listesi
        return: (ok, err)
        """
        if not isinstance(ops, list) or not ops:
            return False, "no ops to apply"

        for op in ops:
            path = str(op.get("path") or "").strip()
            find = str(op.get("find") or "")
            mode = str(op.get("mode") or "").strip().lower()
            text = str(op.get("text") or "")

            ok, err = self._apply_edit_op(path, find, mode, text)
            if not ok:
                return False, err

        return True, ""

    def _set_apply_status(self, msg_index: int, status: str, err: str = ""):
        """
        status: "ok" | "fail" | "cancel"
        """
        try:
            with open(self.current_chat, "r", encoding="utf-8") as f:
                messages = json.load(f) or []
        except Exception:
            return

        if not (0 <= msg_index < len(messages)):
            return

        messages[msg_index]["apply_status"] = {
            "status": status,
            "err": (err or "").strip()
        }

        try:
            with open(self.current_chat, "w", encoding="utf-8") as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
        except Exception:
            return

    def apply_request_yes(self, req: dict):
        """
        req örneği:
          {
            "path": "/home/bob/capture-ai/ui.py",
            "find": "def on_attach_clicked",
            "mode": "before",          # before|after|replace
            "text": "...\n"
          }
        """
        path = str(req.get("path") or "").strip()
        find = str(req.get("find") or "")
        mode = str(req.get("mode") or "").strip().lower()
        text = str(req.get("text") or "")

        # temel doğrulamalar
        if not path:
            GLib.idle_add(self.apply_failed_to_input, "missing path")
            return
        if not find:
            GLib.idle_add(self.apply_failed_to_input, "missing find (anchor) string")
            return
        if mode not in ("before", "after", "replace"):
            GLib.idle_add(self.apply_failed_to_input, f"invalid mode: {mode}")
            return
        if text == "":
            GLib.idle_add(self.apply_failed_to_input, "missing text")
            return

        ok, err = self._apply_edit_op(path, find, mode, text)
        if not ok:
            GLib.idle_add(self.apply_failed_to_input, err)
            return

        # Başarılı olunca istersen input’a kısa bilgi de basabilirsin:
        # (chat'e yazma yok)
        GLib.idle_add(self._append_to_input, f"✅ Applied to {Path(path).name}")


    def apply_request_no(self):
        # hiçbir şey yapma; input'a da yazmak istemiyorsan boş bırak
        return

    # ---------------- SEND / CALL AI ----------------

    def send_message(self, widget):
        buffer = self.textview.get_buffer()
        start, end = buffer.get_bounds()
        message = buffer.get_text(start, end, True).strip()
        if not message:
            return

        with open(self.current_chat, "r", encoding="utf-8") as f:
            messages = json.load(f) or []

        new_message = {"role": "user", "content": message}

        if self.pending_images:
            new_message["images"] = [str(Path(p).resolve()) for p in self.pending_images if Path(p).exists()]

        if self.pending_files:
            new_message["files"] = []
            for f in self.pending_files:
                fp = Path(str(f.get("path","")))
                if fp.exists():
                    new_message["files"].append({
                        "path": str(fp.resolve()),
                        "name": fp.name,
                        "edit": bool(f.get("edit")),  # <-- önemli
                    })

        # referansla gönderildiyse işaretle
        # referansla gönderildiyse: indeks + snapshot önizleme kaydet
        if self.selected_indexes:
            selected = sorted(self.selected_indexes)

            # AI'ya da gitsin diye zinciri genişlet (fotoğraf vs kaybolmasın)
            expanded = set()
            for ridx in selected:
                if 0 <= ridx < len(messages):
                    expanded |= self.expand_ref_chain(messages, ridx)

            new_message["used_refs"] = sorted(expanded)

            # Görünüm için: her seçilen referans kendi balonu gibi bir "group" olsun
            # group = (o mesajın eski refs_preview'si) + (o mesajın kendisi)
            groups = []
            for ridx in selected:
                if not (0 <= ridx < len(messages)):
                    continue
                rmsg = messages[ridx]

                group_items = []

                # Eğer bu referans mesajı daha önce referansla gönderildiyse,
                # onun içindeki refs_groups'u (veya eski refs_preview'u) da gösterelim
                rg = rmsg.get("refs_groups")
                if isinstance(rg, list) and rg:
                    # refs_groups varsa, içindeki tüm item’ları düzleştirip ekleyelim
                    for g in rg:
                        items = g.get("items") if isinstance(g, dict) else None
                        if isinstance(items, list):
                            for it in items:
                                if isinstance(it, dict) and it.get("text"):
                                    group_items.append({"role": it.get("role",""), "text": it.get("text","")})
                else:
                    # Eski sürümden kalan refs_preview varsa onu da ekle
                    rp = rmsg.get("refs_preview")
                    if isinstance(rp, list) and rp:
                        for it in rp:
                            if isinstance(it, dict) and it.get("text"):
                                group_items.append({"role": it.get("role",""), "text": it.get("text","")})

                # en sona referans mesajın kendisini ekle (bağlam bütünlüğü için)
                group_items.append(self.pack_preview_item(rmsg))

                groups.append({"items": group_items})

            new_message["refs_groups"] = groups

        messages.append(new_message)

        with open(self.current_chat, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)

        buffer.set_text("")
        # preview temizle
        self.pending_images.clear()
        self.pending_files.clear()
        self.refresh_attachments_preview()

        selected_arg = ""
        if self.selected_indexes:
            # aynı expanded used_refs setini yeniden hesapla (ya da new_message["used_refs"]'ten al)
            ref_idxs = new_message.get("used_refs") or []
            if isinstance(ref_idxs, list) and ref_idxs:
                selected_arg = ",".join(str(i) for i in ref_idxs if isinstance(i, int))

        self.selected_indexes.clear()
        self.selection_mode = False
        self.update_selection_label()

        self.load_chat()
        self.show_typing_indicator()

        threading.Thread(target=self.call_ai, args=(selected_arg,), daemon=True).start()

    def _consume_click(self, widget: Gtk.Widget):
        """
        Bu widget'a tıklanınca click event'ini yukarı (bubble click handler'ına) taşırma.
        """
        g = Gtk.GestureClick()
        g.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

        def on_pressed(gesture, n_press, x, y):
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)

        g.connect("pressed", on_pressed)
        widget.add_controller(g)

    def extract_title_block(self, text: str):
        lines = text.splitlines()

        start = None
        end = None

        for i, line in enumerate(lines):
            if line.strip() == "title":
                if start is None:
                    start = i
                else:
                    end = i
                    break

        if start is not None and end is not None and end > start:
            return "\n".join(lines[start + 1:end]).strip()

        return None

    def extract_copy_block(self, text: str):
        lines = text.splitlines()

        start = None
        end = None

        for i, line in enumerate(lines):
            if line.strip() == "copy":
                if start is None:
                    start = i
                else:
                    end = i
                    break

        if start is not None and end is not None and end > start:
            return "\n".join(lines[start + 1:end]).strip()

        return None

    def extract_apply_block(self, text: str):
        lines = text.splitlines()

        start = None
        end = None

        for i, line in enumerate(lines):
            if line.strip() == "apply":
                if start is None:
                    start = i
                else:
                    end = i
                    break

        if start is not None and end is not None and end > start:
            return "\n".join(lines[start + 1:end]).strip()

        return None

    def parse_apply_ops(self, apply_text: str):
        """
        apply bloğunun içindeki JSON’u parse eder.
        Kabul edilen formatlar:
          - Tek dict: {"path":..., "find":..., "mode":..., "text":...}
          - Liste: [{"path":...}, {...}]
        Return: (ops_list, err_str)
        """
        try:
            raw = (apply_text or "").strip()
            if not raw:
                return None, "empty apply block"

            data = json.loads(raw)

            if isinstance(data, dict):
                ops = [data]
            elif isinstance(data, list):
                ops = data
            else:
                return None, "apply JSON must be object or array"

            # minimum alan doğrulama
            clean = []
            for i, op in enumerate(ops):
                if not isinstance(op, dict):
                    return None, f"op #{i} is not an object"
                clean.append(op)

            return clean, ""
        except Exception as e:
            return None, f"invalid apply JSON: {e}"

    def _short(self, s: str, n: int = 120) -> str:
        s = (s or "").replace("\n", "\\n")
        return s if len(s) <= n else (s[:n] + "...")

    def build_apply_summary(self, ops: list[dict]) -> str:
        """
        ops -> 1 satırlık özet üretir.
        (Şimdilik ilk op'u baz alıyoruz)
        """
        if not isinstance(ops, list) or not ops or not isinstance(ops[0], dict):
            return ""

        op = ops[0]
        mode = str(op.get("mode") or "").strip().lower()
        find = str(op.get("find") or "")
        text = str(op.get("text") or "")

        if mode not in ("replace", "before", "after"):
            mode = "replace"

        # TR cümle istersen:
        # "Bu satırı replace ediyorum: <find> -> <text>"
        return f'Bu satırı {mode} ediyorum: {self._short(find)}  ->  {self._short(text)}'

    def copy_to_clipboard(self, text: str):
        display = Gdk.Display.get_default()
        if not display:
            return
        clipboard = display.get_clipboard()
        clipboard.set(text)

    def call_ai(self, selected_arg):
        # model parametresi göndermiyoruz.
        # ai.py, chat_models + ai_models[0] mantığıyla kendisi seçecek.
        cmd = [sys.executable, AI_SCRIPT, str(self.current_chat)]

        if selected_arg:
            cmd.append(selected_arg)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                error_message = result.stderr.strip() or "Bilinmeyen hata"
                GLib.idle_add(self.handle_ai_error, error_message)
            else:
                GLib.idle_add(self.after_ai_response)

        except Exception as e:
            GLib.idle_add(self.handle_ai_error, str(e))


if __name__ == "__main__":
    image_arg = None
    if len(sys.argv) >= 2:
        image_arg = sys.argv[1]

    app = ChatApp(image_arg)
    app.run()
