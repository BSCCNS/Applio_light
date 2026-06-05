langs=("en" "es" "fr" "de" "ko" "it" "ru" "zh")

for lang in "${langs[@]}"; do
    python infer_script.py "/Users/tomasandrade/Desktop/my_voice/ElevenLabs-api/v0/raw/${lang}.mp3" "/Users/tomasandrade/Desktop/my_voice/ElevenLabs-api/v0/maria/${lang}_output.wav" 0
done
