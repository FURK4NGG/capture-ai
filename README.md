# ai-controller
<!-- system prompt caching,dosya içeriklerini sadece gerekince gönderme -->
<!-- kurulum dosyasi ve sudo chmod,dosyalari yerlestirme klasor olusturma ve izinler -->
<!-- ui ve cli icin proje resimleri -->
<!-- ram tuketimi gibi bilgiler -->
<!-- for nerds ler falan -->

## 🔎 Preparation
1. `Go to the`[`Open Router`](https://openrouter.ai/)`and create your own api key`
2. `Make sure you place your files in the following directories.`  
   ~/capture-ai/ui.py  
   ~/capture-ai/ai.py  
   ~/capture-ai/cli.py  
   ~/capture-ai/capture-ai.sh  
   ~/capture-ai/language/en.json  
   ~/capture-ai/language/tr.json  
   ~/.config/capture-ai/config.json  
   ~/.config/capture-ai/requirements.txt  
   ~/.config/scripts/screenprint.sh  
<details>
<summary>3. Download Packages</summary>

   <details>
   <summary>Arch Packages</summary>


   ```
   cd ~/.config/capture-ai/
   sudo pacman -S --needed git python python-virtualenv python-gobject gtk4 libadwaita gobject-introspection cairo pango glib2 xdg-utils noto-fonts-emoji
   ```

   Enviroment
   ```
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
   <br><br>
   Offline Voice Input (Speech → Text)

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
   <br><br>
   Screenshot
   ```
   sudo pacman -S --needed grim slurp mako libnotify
   ```
   <br>
   <br>
   </details>












   <details>
   <summary>Debian/Ubuntu/Rasberry Pi OS</summary>

      
   ```
   cd ~/.config/capture-ai/
   sudo apt update && sudo apt install -y git python3 python3-venv python3-gi gobject-introspection gir1.2-gtk-4.0 gir1.2-adw-1 libgtk-4-1 libadwaita-1-0 xdg-utils fonts-noto-color-emoji
   ```

   Enviroment
   ```
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
   <br><br>
   Offline Voice Input (Speech → Text)

   🎙️ pw-record / arecord -> 📄 WAV file -> 🧠 whisper-cli -> ✍ Text input  

   🎙️voice record
   >pw-record  
   ```
   sudo apt install -y pipewire wireplumber pipewire-pulse
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
   <br><br>
   Screenshot
   ```
   sudo apt install -y grim slurp scrot dunst libnotify-bin
   ```
   <br>
   <br>
   </details>

</details>
   






~/.config/capture-ai/env.sh --> export OPENROUTER_API_KEY="sk-or-v..."

Run  
bash capture-ai.sh (image,text,cli)  



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
- [x] Adding documents via drag & drop
- [x] AI can read, analyze, modify your documents (within permission)
- [x] Files returned as downloadable outputs
- [x] Supports PDF, DOCX, XLSX
- [x] Lazy Loading, Chat Loading System (Loads latest messages first,older messages load on scroll)
- [x] Change UI colors
- [x] Language support [Turkish, English]*You can easily create your own language file*
- [x] Caching the language file to avoid repeated file reads
- [x] Compatible with Linux(Arch,Debian/Ubuntu) devices
- [x] Control via Terminal (excluding STT and some UI features)
- [x] Per-chat conversational RAG system with enable/disable support(short-term memory + summary memory + embedding-based retrieval + code-aware context)
- [x] Run local text model(Local API-based AI)
- [ ] Compatible with macOS, Windows

 
## 🔎 ALL APP FEATURES
<details>
<summary>For Nerds</summary>
1. For Nerds

1. Chat management  
Create, switch, delete, rename, pin/unpin chats. Chats are sorted with pinned chats first, then by last modified time.

2. Local chat storage  
All chats are stored locally on the machine under the app cache directory.

3. Section-based chat loading  
Chats use lazy loading. Only the latest 10 messages are loaded first, and older messages load while scrolling up.

4. Persistent configuration  
Uses one config.json file for settings such as theme, models, pinned chats, last chat, STT, RAG, colors, local providers, and language.

5. Per-chat model management  
Each chat can have its own active AI model. Recently selected models move to the top of the list.

6. Online and local model support  
Supports OpenRouter models and local API-based text models such as Ollama.

7. Local provider settings  
Local providers can store base URL, startup command, stop command, system prompt, and model parameters.

8. Sidebar UI  
Collapsible sidebar with separate Chats and AI Models sections.

9. Context mode switch  
Each chat can switch between Direct mode and RAG mode.

10. Per-chat conversational RAG  
Supports short-term memory, summary memory, simple retrieval, and code-aware context.

11. Reference tree support  
Selected references can expand recursively so previous context is not lost.

12. Message selection mode  
Users can select one or multiple messages, clear selection, copy, regenerate, or use them as references.

13. Regenerate  
Regenerates from selected user or assistant messages while keeping reference context.

14. Copyable code blocks  
Copy-marked content is rendered as a code-style block with a copy button.

15. Image generation and image handling  
Supports image generation, image previews, cached generated images, and image attachments.

16. Document support  
Supports PDF, DOCX, XLSX, TXT, and MD file creation/output. Generated files are shown with downloadable buttons.

17. PDF handling  
If a PDF contains text, it is sent as text content. If it has little/no text, the first pages are converted to PNG images and sent as image_url.

18. Document editing behavior  
AI can read, analyze, summarize, rewrite, and generate edited document outputs when permission is enabled.

19. File create protocol  
DOCX, XLSX, PDF, TXT, and MD outputs can be generated from AI responses and returned as downloadable files.

20. XLSX support  
Can create new XLSX tables and filter existing XLSX files with supported operations.

21. Drag & drop attachments  
Files and images can be added via drag & drop or file picker.

22. Editable file permission  
Attached files can be toggled editable. The AI only modifies files when permission is enabled.

23. Voice-to-text input  
Supports microphone recording and transcription with online or local STT.

24. Offline STT  
Uses whisper.cpp with configured binary and model paths.

25. Online STT  
Uses OpenRouter audio-capable models and sends WAV audio as input_audio.

26. Token usage display  
Shows input, output, and total token usage for each response when enabled.

27. Token price display  
Can estimate message cost using a configurable token price value.

28. Theme system  
Supports dark/light theme and custom UI colors.

29. Language system  
Supports external language files such as Turkish and English, with cached language loading.

30. Prompt chooser  
Prompt behavior blocks can be enabled/disabled, such as copyable, apply, PDF visual edit, file creation, structured output, and code mode.

31. Terminal control  
The project also supports terminal usage, excluding STT and some GUI-only features.

32. Linux compatibility  
Designed for Linux devices, including Arch and Debian/Ubuntu-based systems.
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
