# ai-controller

sudo pacman -S python3-gi gir1.2-gtk-4.0

~/.config/capture-ai/env.sh --> export OPENROUTER_API_KEY="sk-or-v..."


$capture-ai = /home/$USER/capture-ai/capture-ai.sh


bind = $mainMod SHIFT, Q, exec, $capture-ai image  
bind = $mainMod, Q, exec, $capture-ai text  

Offline Voice for Linux  
sudo pacman -S --needed git cmake make gcc  

git clone https://github.com/ggml-org/whisper.cpp.git  
cd whisper.cpp  
cmake -B build  
cmake --build build -j --config Release  

ls build/bin  
# ... whisper-cli, main, whisper-server, ...  

Tiny model indirme (hafif, düşük CPU)  
mkdir -p ~/.local/share/whisper  
wget -O ~/.local/share/whisper/ggml-tiny.bin \  
https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin  

Manual test (çalıştığını doğruladık)  
/home/bob/whisper.cpp/build/bin/whisper-cli \  
  -m /home/bob/.local/share/whisper/ggml-tiny.bin \  
  -f /tmp/capture-ai-mic-20260228-205753.wav \  
  -l tr  

<br><br>

## Roadmap
- [x] 
- [ ] 
