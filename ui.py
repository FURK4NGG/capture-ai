#!/usr/bin/env python3
import sys
import gi
import subprocess
import threading

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

AI_SCRIPT = "/home/bob/ai_capture/ai.py"

MODELS = [
    "qwen/qwen-2.5-vl-7b-instruct:free",
    "meta-llama/llama-3.2-11b-vision-instruct",
    "google/gemini-2.5-flash-image",
]

class App(Gtk.Application):
    def __init__(self, image_path):
        super().__init__(application_id="ai.capture.ui")
        self.image_path = image_path

    def do_activate(self):
        win = Gtk.ApplicationWindow(application=self)
        win.set_title("AI Capture")
        win.set_default_size(900, 800)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.set_margin_top(10)
        root.set_margin_bottom(10)
        root.set_margin_start(10)
        root.set_margin_end(10)

        # === IMAGE ===
        picture = Gtk.Picture.new_for_filename(self.image_path)
        picture.set_hexpand(True)
        picture.set_vexpand(True)
        picture.set_content_fit(Gtk.ContentFit.CONTAIN)

        frame = Gtk.Frame()
        frame.set_hexpand(True)
        frame.set_vexpand(True)
        frame.set_child(picture)
        root.append(frame)

        # === INPUT ROW ===
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Bu görüntü hakkında sorunuzu yazın…")
        self.entry.set_hexpand(True)
        row.append(self.entry)

        self.ask_btn = Gtk.Button(label="Sor")
        self.ask_btn.connect("clicked", self.on_ask)
        row.append(self.ask_btn)

        menu_btn = Gtk.Button(label="⋮")
        row.append(menu_btn)

        root.append(row)

        # === OUTPUT ===
        self.output = Gtk.TextView()
        self.output.set_editable(False)
        self.output.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)

        out_scroll = Gtk.ScrolledWindow()
        out_scroll.set_vexpand(True)
        out_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        out_scroll.set_child(self.output)

        root.append(out_scroll)

        # === MODEL POPOVER ===
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)

        self.checks = {}
        for m in MODELS:
            cb = Gtk.CheckButton(label=m)
            cb.set_active(m == MODELS[0])
            self.checks[m] = cb
            box.append(cb)

        popover.set_child(box)
        popover.set_parent(menu_btn)
        menu_btn.connect("clicked", lambda *_: popover.popup())

        win.set_child(root)
        win.present()

    def on_ask(self, _):
        prompt = self.entry.get_text().strip()
        if not prompt:
            return

        models = [m for m, cb in self.checks.items() if cb.get_active()]
        if not models:
            self.set_output("❌ En az bir model seçmelisiniz.")
            return

        self.ask_btn.set_sensitive(False)
        self.set_output("⏳ Yanıt alınıyor…")

        threading.Thread(
            target=self.run_ai,
            args=(prompt, models),
            daemon=True
        ).start()

    def run_ai(self, prompt, models):
        for model in models:
            try:
                result = subprocess.run(
                    [
                        "python",
                        AI_SCRIPT,
                        self.image_path,
                        prompt,
                        model
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                if result.returncode == 0 and result.stdout.strip():
                    GLib.idle_add(self.on_done, result.stdout.strip())
                    return
            except Exception as e:
                last_error = str(e)

        GLib.idle_add(self.on_done, f"❌ Tüm modeller başarısız.\n{last_error}")

    def on_done(self, text):
        self.set_output(text)
        self.ask_btn.set_sensitive(True)
        return False

    def set_output(self, text):
        buf = self.output.get_buffer()
        buf.set_text(text)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Kullanım: ui.py <image_path>")
        sys.exit(1)

    app = App(sys.argv[1])
    app.run()
