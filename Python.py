import os
import subprocess
import glob
import uuid
from flask import Flask, render_template, request, send_file, jsonify
import yt_dlp
import imageio_ffmpeg  # Library penyedia biner FFmpeg & FFprobe otomatis
from loading_print import loading_print

loading_print("Loading...", 10, speed=0.7, color="blue")

app = Flask(__name__)

# Temporary directory untuk menyimpan file sebelum diunduh user
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

@app.route('/')
def home():
    return render_template('index.html')


# --- FITUR SPOTIFY ---
@app.route('/download', methods=['POST'])
def download_song():
    data = request.json
    spotify_url = data.get('url')
    
    if not spotify_url or "spotify.com" not in spotify_url:
        return jsonify({"error": "Invalid Spotify URL!"}), 400

    try:
        # Buat folder unik (UUID) untuk request download ini agar tidak bentrok antar user
        session_id = str(uuid.uuid4())
        user_download_dir = os.path.join(DOWNLOAD_DIR, session_id)
        os.makedirs(user_download_dir, exist_ok=True)

        # Menjalankan perintah spotdl dengan output direktori unik
        subprocess.run(
            ["spotdl", "--output", user_download_dir, spotify_url], 
            check=True
        )

        mp3_files = glob.glob(f"{user_download_dir}/*.mp3")
        if not mp3_files:
            return jsonify({"error": "Failed to extract audio."}), 500
        
        target_file = mp3_files[0]
        filename = os.path.basename(target_file)

        return jsonify({"success": True, "filename": filename})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- FITUR YOUTUBE DOWNLOADER (VIDEO & AUDIO) ---
@app.route('/download-youtube', methods=['POST'])
def download_youtube():
    data = request.json
    youtube_url = data.get('url')
    download_type = data.get('type')  # 'audio' atau 'video'
    
    if not youtube_url or ("youtube.com" not in youtube_url and "youtu.be" not in youtube_url):
        return jsonify({"error": "Link YouTube tidak valid!"}), 400

    try:
        # Buat folder unik (UUID) untuk request download ini agar tidak bentrok antar user
        session_id = str(uuid.uuid4())
        user_download_dir = os.path.join(DOWNLOAD_DIR, session_id)
        os.makedirs(user_download_dir, exist_ok=True)

        # CARA PALING MATANG: Ambil full path path exe ffmpeg, lalu ambil foldernya
        ffmpeg_exe_path = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_bin_dir = os.path.dirname(ffmpeg_exe_path)

        # Pengaturan yt-dlp dengan output ke direktori unik user
        if download_type == 'audio':
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(user_download_dir, '%(title)s.%(ext)s'),
                'ffmpeg_location': ffmpeg_exe_path,  # Tembak langsung ke file exe-nya!
                'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
        else:  # Jika user pilih video (MP4)
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': os.path.join(user_download_dir, '%(title)s.%(ext)s'),
                'ffmpeg_location': ffmpeg_bin_dir,  # Tembak ke folder bin-nya agar kebaca ffprobe juga!
                'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            }

        # Jalankan proses download yt-dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Jika tipenya audio, ekstensinya sudah berubah jadi .mp3 oleh postprocessor
            if download_type == 'audio':
                filename = os.path.splitext(filename)[0] + '.mp3'
            
            filename_only = os.path.basename(filename)

        return jsonify({"success": True, "filename": filename_only})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get-file/<filename>')
def get_file(filename):
    # Cari file di dalam seluruh sub-folder UUID secara dinamis
    search_path = os.path.join(DOWNLOAD_DIR, "**", filename)
    matched_files = glob.glob(search_path, recursive=True)
    
    if matched_files:
        file_path = matched_files[0]
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
            
    return "File not found", 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
