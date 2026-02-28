# ai-controller

sudo pacman -S python3-gi gir1.2-gtk-4.0

~/.config/capture-ai/env.sh --> export OPENROUTER_API_KEY="sk-or-v..."


$capture-ai = /home/$USER/capture-ai/capture-ai.sh


bind = $mainMod SHIFT, Q, exec, $capture-ai image  
bind = $mainMod, Q, exec, $capture-ai text  

Offline Voice for Linux  
🎤 pw-record / arecord  
⬇  
📄 WAV dosyası  
⬇  
🧠 whisper-cli  
⬇  
✍ Metin  

sudo pacman -S --needed git cmake make gcc pipewire wireplumber alsa-utils  

paket kontrol  
command -v pw-record || echo "pw-record yok"  
command -v arecord  || echo "arecord yok"  

git clone https://github.com/ggml-org/whisper.cpp.git  
cd whisper.cpp  
cmake -B build  
cmake --build build -j --config Release  

ls build/bin  
 #... whisper-cli, main, whisper-server, ...  

Tiny model indirme (hafif, düşük CPU)  
mkdir -p ~/.local/share/whisper  
wget -O ~/.local/share/whisper/ggml-tiny.bin \  
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin  

paket test  
ls -l ~/whisper.cpp/build/bin/whisper-cli  
ls -lh ~/.local/share/whisper/ggml-tiny.bin  

Manual test (çalıştığını doğruladık)  
/home/bob/whisper.cpp/build/bin/whisper-cli \  
  -m /home/bob/.local/share/whisper/ggml-tiny.bin \  
  -f /tmp/capture-ai-mic-20260228-205753.wav \  
  -l tr  

<br><br>

## Roadmap
- [x] Use reference trees
- [x] Dark/Light themes
- [x] Copiable code blocks
- [x] Regenerate
- [x] Enter input with your voice -Speech to text(online or local)-
- [ ]
 
## 🔎 Preparation
<details>
<summary>For Nerds</summary>
1. Chat management  
Create new chats (chat_1.json, chat_2.json, …)  
Switch between chats  
Delete chat (with confirmation)  
Rename chat (popover)  
Pin/unpin chats (📌)  
Sorting: pinned first, then most recently modified  

2. Persistent settings (config.json)  
Remember last opened chat (last_chat)  
Dark/light theme (dark_mode)  
Pinned chats (pinned_chats)  
Model list (ai_models)  
Per-chat model mapping (chat_models)  
Store OpenRouter key (open_router_key)  
Mic mode online/offline (is_mic_online)  
Online STT model (stt_model_online)  
Offline whisper.cpp paths (whisper_cpp_bin, whisper_cpp_model)  

3. Sidebar UI  
Collapse/expand sidebar (☰)  
Toggle Chats list  
Toggle AI Models list  

4. Model management (per chat)  
Separate active model per chat  
Selecting a model assigns it to the current chat  
LRU behavior: recently chosen model moves to top  
Delete models (cannot delete the last remaining model)  
If a model is deleted, affected chats fall back to default (self-heal)  
“AI Models +” to add a model (dialog + OpenRouter models link)  

5. Message selection mode  
Click to select one or multiple messages  
Selection counter bar  
Clear selection (✕)  
Selected bubbles get an outline  

6. Reference trees (reference chain expansion)  
Expands used_refs recursively (references of references)  
Ensures context (including images/refs) isn’t lost  
Stores:  
used_refs (indices sent to AI)  
refs_groups (UI reference preview groups)  

7. Reference trees (reference chain expansion)  
Expands used_refs recursively (references of references)  
Ensures context (including images/refs) isn’t lost  
Stores:  
used_refs (indices sent to AI)  
refs_groups (UI reference preview groups)  

8. Regenerate (♻)  
Appears only when exactly one bubble is selected  
If user bubble: re-asks the same prompt  
If bot bubble: finds preceding user prompt + rewrites a similar answer  
Regenerated prompts are marked (regen) with a distinct style 
Keeps reference trees during regeneration  

9. Copy (📋)  
Appears only on the single selected bubble  
If message contains copy ... copy, copies only the inner block  
Otherwise copies full message  

10. Code block detection  
Messages wrapped by copy markers render as a code-style block  
Code block includes a “Copy” button overlay  

11. Image sending / preview  
Supports a pending image preview before sending  
Saves image path into chat history  
Shows a small image preview in message bubbles  
Clears preview after sending  

12. Typing indicator  
Animated “Thinking…” while AI is running  
Removed when response arrives  

13. Scroll behavior  
Floating scroll-to-bottom button (↓) appears when not at bottom  
Clicking scrolls to bottom and re-enables auto-scroll  
Button visibility updates based on scroll position  
(You also tuned behavior to scroll only on regenerate)  

14. Input shortcuts  
Enter to send  
Shift+Enter for newline  
Added: Ctrl+C / Ctrl+V / Ctrl+X / Ctrl+A  

15. Voice-to-text input  
🎤 to start recording, ⏹ to stop  
Uses pw-record if available, otherwise arecord (Linux)  
After stop, transcribes (offline/online) and appends text into input  

16. Offline STT (whisper.cpp)  
Uses whisper-cli + ggml-tiny.bin for low CPU transcription  
Reads .txt output (stdout fallback)  

17. Online STT (OpenRouter)  
If is_mic_online: true, transcribes via OpenRouter  
Sends base64 WAV as input_audio  
Model selected via stt_model_online  
</details>
