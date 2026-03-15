# ai-controller
<!-- system prompt caching,dosya içeriklerini sadece gerekince gönderme -->
<!-- ekran goruntusu, dosya acma -->

## 🔎 Preparation
1. `Go to the`[`Open Router`](https://openrouter.ai/)`and create your own api key`
2. `Make sure you place your files in the following directories.`  
   ~/capture-ai/ui.py  
   ~/capture-ai/ai.py  
   ~/capture-ai/capture-ai.sh  
   ~/.config/capture-ai/config.json
<details>
<summary>3. Download Packages</summary>

   <details>
   <summary>Arch Packages</summary>


   ```
   sudo pacman -S --needed python python-virtualenv python-gobject gtk4 libadwaita gobject-introspection cairo pango glib2 xdg-utils noto-fonts-emoji
   ```

   Enviroment
   ```
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
   <br><br>
   Offline Voice Input for Linux

   🎙️ pw-record / arecord -> 📄 WAV file -> 🧠 whisper-cli -> ✍ Text input  

   🎙️voice record
   >pw-record  
   ```
   sudo pacman -S --needed pipewire wireplumber pipewire-audio pipewire-pulse
   ```
   
   >arecord
   ```
   sudo pacman -S --needed alsa-utils
   ```
   <br><br>
   📄 Offline Speech to Text
    
   ```
   sudo pacman -S --needed cmake make gcc
   ```

   Packages Check
   ```
   command -v pw-record || echo "pw-record not found"  
   command -v arecord  || echo "arecord not found"  
   ```
   <br><br>
   🧠 Install whisper.cpp (Offline Speech Recognition Engine)  
   
   ```
   git clone https://github.com/ggml-org/whisper.cpp.git  
   cd whisper.cpp  
   cmake -B build  
   cmake --build build -j --config Release
   ```
   
   >ls build/bin  
   #Should see these -> ... whisper-cli, main, whisper-server, ...

   <br><br>
   Download 'Tiny' Model  
   ```
   mkdir -p ~/.local/share/whisper  
   wget -O ~/.local/share/whisper/ggml-tiny.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin
   ```
   
   Packages Check  
   ```
   ls -l ~/whisper.cpp/build/bin/whisper-cli  
   ls -lh ~/.local/share/whisper/ggml-tiny.bin
   ```
   
   Manual Test  
   ```
   /home/bob/whisper.cpp/build/bin/whisper-cli \  
     -m /home/bob/.local/share/whisper/ggml-tiny.bin \  
     -f /tmp/capture-ai-mic-20260228-205753.wav \  
     -l tr
   ```
   <br>
   <br>
   </details>












   <details>
   <summary>Debian/Ubuntu/Rasberry Pi OS</summary>

      
   ```
   sudo apt update && sudo apt install -y python3 python3-venv python3-gi gobject-introspection gir1.2-gtk-4.0 gir1.2-adw-1 libgtk-4-1 libadwaita-1-0 xdg-utils fonts-noto-color-emoji
   ```

   Enviroment
   ```
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
   <br><br>
   Offline Voice Input for Linux

   🎙️ pw-record / arecord -> 📄 WAV file -> 🧠 whisper-cli -> ✍ Text input  

   🎙️voice record
   >pw-record  
   ```
   sudo apt install -y pipewire wireplumber pipewire-pulse pipewire pipewire-pulse wireplumber
   ```
   
   >arecord
   ```
   sudo apt install -y alsa-utils
   ```
   <br><br>
   📄 Offline Speech to Text
    
   ```
   sudo apt install -y cmake make gcc
   ```

   Packages Check
   ```
   command -v pw-record || echo "pw-record not found"
   command -v arecord || echo "arecord not found"
   ```
   <br><br>
   🧠 Install whisper.cpp (Offline Speech Recognition Engine)  
   
   ```
   git clone https://github.com/ggml-org/whisper.cpp.git ~/whisper.cpp
   cd ~/whisper.cpp
   cmake -B build
   cmake --build build -j --config Release
   ```
   
   >ls build/bin  
   #Should see these -> ... whisper-cli, main, whisper-server, ...

   <br><br>
   Download 'Tiny' Model  
   ```
   mkdir -p ~/.local/share/whisper
   wget -O ~/.local/share/whisper/ggml-tiny.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin
   ```
   
   Packages Check  
   ```
   ls -l ~/whisper.cpp/build/bin/whisper-cli
   ls -lh ~/.local/share/whisper/ggml-tiny.bin
   ```
   
   Manual Test  
   ```
   ~/whisper.cpp/build/bin/whisper-cli \
     -m ~/.local/share/whisper/ggml-tiny.bin \
     -f /tmp/capture-ai-mic-20260228-205753.wav \
     -l tr
   ```
   <br>
   <br>
   </details>

</details>
   






#screenhot
sudo pacman -S --needed \
  grim slurp swappy wl-clipboard \
  wf-recorder ffmpeg


~/.config/capture-ai/env.sh --> export OPENROUTER_API_KEY="sk-or-v..."


$capture-ai = /home/$USER/capture-ai/capture-ai.sh


bind = $mainMod SHIFT, Q, exec, $capture-ai image  
bind = $mainMod, Q, exec, $capture-ai text  


<br><br>

## Roadmap
- [x] Easy access with keyboard shortcuts
- [x] Model management per chat
- [x] Generate image
- [x] Access every AI model easily
- [x] Unlimited reference tree support
- [x] Customize how the AI responds
- [x] Shows how many tokens are consumed for each message
- [x] Dark/Light themes
- [x] Just one configure file
- [x] Copyable code blocks
- [x] Regenerate
- [x] Keep all your chats in your machine
- [x] Enter input with your voice -Speech to text(online or local)-
- [x] Adding documents
- [x] AI can access and change your documents within permission
- [x] Change UI colors
- [x] Language support [Turkish, English] 
- [ ] Compatible with macOS, Windows, and Linux devices
- [ ] Run local text model
- [ ] Control with terminal
 
## 🔎 ALL APP FEATURES
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

<details>
<summary>Bilgi Hastaları için</summary>
1. Chat yönetimi  
Yeni chat oluşturma (chat_1.json, chat_2.json…)  
Chat’ler arasında geçiş  
Chat silme (onay pencereli, geri alınamaz)  
Chat ismini değiştirme (rename popover)  
Chat sabitleme (📌 pinned)  
Chat liste sıralaması: önce pinned, sonra son değiştirilene gör  

2. Kalıcı ayarlar (config.json)  
Son açık chat’i hatırlama (last_chat)  
Karanlık/Aydınlık tema tercihi (dark_mode)  
Sabitlenen chat’ler listesi (pinned_chats)  
Model listesi (ai_models)  
Chat başına model eşlemesi (chat_models)  
OpenRouter API key saklama (open_router_key)  
Mikrofon modu online/offline seçimi (is_mic_online)  
Online STT model seçimi (stt_model_online)  
Offline STT için whisper.cpp binary/model yolları (whisper_cpp_bin, whisper_cpp_model)  

3. Sidebar UI  
Sidebar daralt / genişlet (☰)  
Chats listesini aç/kapat  
AI models listesini aç/kapat  

4. Model yönetimi (chat başına)  
Her chat için ayrı aktif model  
Model seçince o chat’e atanır  
LRU mantığı: seçtiğin model liste başına alınır  
Model silme (son model silinemez; en az 1 model kalır)  
Silinen model chat’lerde kullanılıyorsa otomatik default modele çekilir (self-heal)  
“AI Models +” ile yeni model ekleme (dialog + OpenRouter models linki)  

5. Mesaj seçim modu  
Mesaja tıklayarak bir/çok mesaj seçme  
Seçili mesaj sayısını gösteren bar  
Seçimi tek tuşla temizleme (✕)  
Seçili mesajlar balon üzerinde outline ile işaretlenir  

6. Reference trees (referans zinciri / ağaç)  
Seçtiğin referans mesajların used_refs zincirini genişletir  
Yani referansın referansı da otomatik dahil edilir (foto/ref kaybolmasın diye)  
Gönderilen yeni kullanıcı mesajına:  
used_refs (AI’ya giden index seti)  
refs_groups (UI’da referans önizleme grupları)  
kaydedilir  

7. Referans önizleme (refs preview)  
Referansla gönderilmiş mesajlar üstte “mini preview” olarak gösterilir  
Grup grup gösterim (refs_groups)  
Uzun satırlar kısaltılır (200 karakter)  

8. Regenerate (♻)  
Tek seçili balonda görünür  
User mesajı seçilirse: aynı mesajı yeniden sorar  
Bot mesajı seçilirse:  
önceki user sorusunu bulur  
bot cevabını “kopyalama bloğu” içeriğiyle iyileştirerek yeniden üretir  
Regenerate mesajı özel renkle işaretlenir (regen)  
Regenerate sırasında referans zinciri korunur (reference trees)  

9. Copy (📋)  
Tek seçili balonda görünür  
Mesaj içeriğinde copy ... copy bloğu varsa sadece içi kopyalanır  
Yoksa tüm mesaj kopyalanır  

10. Kod bloğu algılama  
İçerikte copy sınırları varsa “code-block” görünümü ile render eder  
Kod bloğunda “Kopyala” butonu vardır (overlay)  

11. Görsel gönderme / önizleme  
Bir görsel “pending_image” olarak eklenebilir  
Chat’e mesajla birlikte image path kaydedilir  
Mesajlarda görsel varsa küçük preview gösterilir  
Gönderim öncesi preview kutusu gösterilir, gönderince temizlenir  

12. Typing indicator  
AI yanıtı beklerken “Düşünüyor…” animasyonu  
Yanıt gelince otomatik kaldırılır  

13. Scroll davranışları  
Aşağı kaydırma butonu (↓) — kullanıcı yukarıdaysa görünür  
Tıklayınca en alta iner ve auto-scroll tekrar açılır  
Scroll konumuna göre buton otomatik gizlenir/gösterilir  
(Sende ayrıca “sadece regenerate’de aşağı kaydır” mantığını da ayarladık)  

14. Input kısayolları  
Enter: gönder  
Shift+Enter: yeni satır  
(Eklediğimiz) Ctrl+C / Ctrl+V / Ctrl+X / Ctrl+A kopyala–yapıştır–kes–tümünü seç  

15. Mikrofon: Sesle yazma (Voice-to-text)  
🎤 butonu ile kayıt başlat / ⏹ ile durdur  
Linux’ta pw-record varsa onu kullanır, yoksa arecord  
Durdurunca offline/online STT’ye göre transcribe edip input’a ekler  

16. Offline STT (whisper.cpp)  
whisper-cli + ggml-tiny.bin ile düşük CPU transkripsiyon  
Çıktıyı .txt’den okur (veya stdout fallback)  

17. Online STT (OpenRouter)  
is_mic_online: true ise OpenRouter üzerinden STT  
Audio input input_audio ile base64 wav gönderme  
Model stt_model_online ile seçilir  
</details>

## 🔒 License  
<h1 align="center">📜 GPL-3.0 License</h1>
