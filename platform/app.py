from flask import Flask, request, redirect, url_for, send_from_directory, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import subprocess
import logging
import sys
from werkzeug.utils import secure_filename
from threading import Thread

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/flask.log'),
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////usr/local/nginx/html/videos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 1000 * 1024 * 1024

UPLOAD_FOLDER = '/usr/local/nginx/html/uploads'
HLS_FOLDER = '/usr/local/nginx/html/hls'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mkv', 'mov'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['HLS_FOLDER'] = HLS_FOLDER

db = SQLAlchemy(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

for directory in [UPLOAD_FOLDER, HLS_FOLDER]:
    if not os.path.exists(directory):
        os.makedirs(directory, mode=0o777)
        logger.info(f"Created directory: {directory}")

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    url = db.Column(db.String(200), nullable=False)
    original_name = db.Column(db.String(200), nullable=False)

with app.app_context():
    db.create_all()
    logger.info("Database tables created successfully")

def process_video(input_path, output_dir):
    try:
        logger.info(f"Processing video: {input_path}")
        os.makedirs(output_dir, exist_ok=True)

        renditions = [
            ('360p', '800k', '96k', '640:360'),
            ('480p', '1400k', '128k', '854:480'),
            ('720p', '2800k', '128k', '1280:720')
        ]

        master_playlist = os.path.join(output_dir, 'playlist.m3u8')
        master_content = '#EXTM3U\n#EXT-X-VERSION:3\n'

        for res, bitrate, audio_bitrate, scale in renditions:
            res_dir = os.path.join(output_dir, res)
            os.makedirs(res_dir, exist_ok=True)

            cmd = [
                'ffmpeg', '-i', input_path,
                '-c:v', 'libx264', '-c:a', 'aac',
                '-b:v', bitrate,
                '-b:a', audio_bitrate,
                '-vf', f'scale={scale}',
                '-preset', 'veryfast',
                '-hls_time', '10',
                '-hls_list_size', '0',
                '-hls_segment_filename', f'{res_dir}/segment_%03d.ts',
                '-f', 'hls',
                f'{res_dir}/playlist.m3u8'
            ]

            logger.info(f"Running FFmpeg command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg error for {res}: {result.stderr}")
                raise Exception(f"Failed to create {res} rendition")

            bandwidth = int(bitrate[:-1]) * 1000
            width, height = scale.split(':')
            master_content += f'#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},RESOLUTION={width}x{height}\n{res}/playlist.m3u8\n'

        with open(master_playlist, 'w') as f:
            f.write(master_content)
            
        logger.info(f"Successfully created HLS streams in {output_dir}")
        return True

    except Exception as e:
        logger.error(f"Video processing error: {str(e)}")
        return False

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            logger.error('No file part in the request')
            return jsonify({'status': 'error', 'message': 'No file part'}), 400

        file = request.files['file']
        if file.filename == '':
            logger.error('No selected file')
            return jsonify({'status': 'error', 'message': 'No selected file'}), 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            base_filename = os.path.splitext(filename)[0]
            
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            logger.info(f"File saved to {file_path}")

            video_hls_dir = os.path.join(app.config['HLS_FOLDER'], base_filename)
            
            if process_video(file_path, video_hls_dir):
                video = Video(
                    name=base_filename,
                    url=f'/hls/{base_filename}/playlist.m3u8',
                    original_name=filename
                )
                db.session.add(video)
                db.session.commit()
                logger.info(f"Video {filename} processed successfully")
                
                return jsonify({
                    'status': 'success',
                    'message': 'Video processed successfully',
                    'video_id': video.id
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Video processing failed'
                }), 500

        return jsonify({'status': 'error', 'message': 'File type not allowed'}), 400

    except Exception as e:
        logger.error(f"Upload error: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/stream/<filename>')
def video_stream(filename):
    return send_from_directory(app.config['HLS_FOLDER'], f'{filename}.m3u8')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/videos')
def list_videos():
    videos = Video.query.all()
    return jsonify([{
        'id': video.id,
        'name': video.name,
        'url': video.url,
        'original_name': video.original_name
    } for video in videos])

if __name__ == '__main__':
    try:
        logger.info("Starting Flask application")
    except Exception as e:
        logger.error("Failed to start Flask application", exc_info=True)


