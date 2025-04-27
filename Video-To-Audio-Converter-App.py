# streamlit_app.py
import streamlit as st
import os
import yt_dlp
from moviepy.editor import VideoFileClip
import tempfile
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Function to download audio from YouTube and return bytes
def download_audio_from_youtube(url):
    logging.info(f"Attempting to download audio from URL: {url}")
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': os.path.join(tmp_dir, '%(title)s.%(ext)s'),
                'quiet': False, # Set to False for more detailed logs if needed, True for less output
                'verbose': True, # Enable verbose logging from yt-dlp
                'noprogress': True, # Disable progress bar in logs
                'noplaylist': True, # Ensure only single video is downloaded if playlist URL given
                # Consider adding a user-agent if 403 errors persist
                # 'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            }
            logging.info(f"Using yt-dlp options: { {k: v for k, v in ydl_opts.items() if k != 'postprocessors'} }") # Log options except long ones
            
            downloaded_file_path = None
            file_title = "downloaded_audio"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # It's crucial to keep yt-dlp updated (pip install --upgrade yt-dlp)
                # as YouTube changes can break downloads. requirements.txt handles this.
                logging.info("Calling yt-dlp extract_info...")
                info = ydl.extract_info(url, download=True)
                file_title = info.get('title', file_title) # Get title for filename
                logging.info(f"yt-dlp extraction finished. Title: {file_title}")

                # Construct expected output filename based on template and extracted info
                # yt-dlp might slightly modify the title for filesystem compatibility
                # We list files instead of guessing the exact name after postprocessing
                
                mp3_files = [f for f in os.listdir(tmp_dir) if f.endswith('.mp3')]
                logging.info(f"Files in temp directory after download: {os.listdir(tmp_dir)}")
                
                if not mp3_files:
                    logging.error("No mp3 file found in the temporary directory after yt-dlp processing.")
                    # Check if *any* audio file was downloaded before postprocessing?
                    audio_files = [f for f in os.listdir(tmp_dir) if '.' in f and ydl.extract_info(url, download=False).get('ext') in f]
                    if audio_files:
                         logging.error(f"Original audio file ({audio_files[0]}) might exist, but MP3 conversion failed.")
                         return None, f"Audio extraction failed during MP3 conversion. Original format might be incompatible or FFmpeg issue. Files: {os.listdir(tmp_dir)}"
                    else:
                         return None, "Audio download or extraction failed. No audio file found."

                downloaded_file_path = os.path.join(tmp_dir, mp3_files[0])
                safe_filename = f"{file_title}.mp3" # Use the extracted title
                logging.info(f"Found MP3 file: {downloaded_file_path}")

                with open(downloaded_file_path, 'rb') as f:
                    audio_bytes = f.read()
                
                logging.info(f"Successfully read {len(audio_bytes)} bytes for '{safe_filename}'.")
                return audio_bytes, safe_filename
                
    # Catch specific download errors from yt-dlp
    except yt_dlp.utils.DownloadError as e:
        error_str = str(e)
        logging.error(f"yt-dlp DownloadError encountered: {error_str}", exc_info=True) # Log full traceback
        # Handle specific errors like 403 Forbidden
        if 'HTTP Error 403' in error_str:
             error_message = (
                 "Error: Received HTTP 403 Forbidden from YouTube. "
                 "This commonly means YouTube is blocking the request. Potential reasons:\n"
                 "- The video might require login (age restriction, private).\n"
                 "- High request volume from this server.\n"
                 "- Outdated yt-dlp (Streamlit Cloud usually uses the latest from requirements.txt).\n"
                 "- Regional restrictions on the video.\n"
                 # "- Consider trying a different User-Agent in ydl_opts if this persists.\n"
                 f"Original error snippet: {error_str[:200]}..." # Show start of error
             )
             return None, error_message
        elif 'Unsupported URL' in error_str:
             return None, f"Error: The provided URL is not supported by yt-dlp. Please check the URL. ({error_str[:100]}...)"
        else:
             # Handle other download errors
             return None, f"yt-dlp download error: {error_str[:200]}..." # Show start of generic error
             
    except Exception as e:
        # Catch any other unexpected errors during the process
        logging.error(f"An unexpected error occurred during YouTube download: {str(e)}", exc_info=True)
        return None, f"An unexpected error occurred: {str(e)}"

# Function to extract audio from file and return bytes
def extract_audio_from_file(video_path, original_filename):
    logging.info(f"Attempting to extract audio from file: {original_filename}")
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Generate output filename from original uploaded name
            base_name = os.path.splitext(original_filename)[0]
            # Ensure filename is safe for filesystem (basic example)
            safe_base_name = "".join([c for c in base_name if c.isalnum() or c in (' ', '_', '-')]).rstrip()
            if not safe_base_name: safe_base_name = "extracted_audio" # fallback name
            output_filename = f"{safe_base_name}.mp3"
            output_path = os.path.join(tmp_dir, output_filename)
            logging.info(f"Generated output path: {output_path}")
            
            # Process video
            # Ensure moviepy has access to ffmpeg (installed via packages.txt)
            logging.info("Creating VideoFileClip...")
            with VideoFileClip(video_path) as video:
                 if video.audio is None:
                      logging.warning(f"Video file '{original_filename}' has no audio track.")
                      return None, "Error: The uploaded video file does not contain an audio track."
                 
                 logging.info(f"Writing audio file to: {output_path}")
                 # Added codec='mp3' and logger=None to potentially reduce console noise
                 video.audio.write_audiofile(output_path, codec='mp3', logger=None) 
                 logging.info("Finished writing audio file.")
            
            # Read generated audio file
            if not os.path.exists(output_path):
                logging.error(f"MP3 file was not created at {output_path}")
                return None, "Error: Failed to create the audio file."

            with open(output_path, 'rb') as f:
                audio_bytes = f.read()
            
            logging.info(f"Successfully read {len(audio_bytes)} bytes for '{output_filename}'.")
            return audio_bytes, output_filename
            
    except Exception as e:
        logging.error(f"Error processing video file '{original_filename}': {str(e)}", exc_info=True)
        return None, f"Error processing video file: {str(e)}"

# --- Streamlit App UI (Unchanged) ---
def main():
    st.set_page_config(page_title="Video to Audio Converter", page_icon="🎵")
    st.title("🎵 Video to Audio Converter")
    st.write("Easily extract audio from YouTube videos or local video files.")

    # Tabs for the two functionalities
    tab1, tab2 = st.tabs(["📹 YouTube to Audio", "📂 File Upload to Audio"])

    # YouTube to Audio
    with tab1:
        st.header("YouTube to Audio")
        url = st.text_input("Enter YouTube URL:", key="youtube_url_input")
        if st.button("Prepare YouTube Audio", key="youtube_button"):
            if not url or not url.strip():
                st.error("Please enter a valid YouTube URL.")
            elif not ("youtube.com" in url or "youtu.be" in url):
                 st.error("Please enter a valid YouTube URL (must contain youtube.com or youtu.be)")
            else:
                with st.spinner("Processing YouTube link... This may take a moment."):
                    audio_bytes, message = download_audio_from_youtube(url) 
                    
                    if audio_bytes:
                        file_size = len(audio_bytes) / (1024 * 1024)  # Convert to MB
                        st.success(f"Audio ready! Filename: '{message}', Size: {file_size:.2f} MB")
                        
                        # Add download button
                        st.download_button(
                            label="💾 Download Audio",
                            data=audio_bytes,
                            file_name=message, # Use the filename returned
                            mime="audio/mpeg",
                            key="youtube_download_button"
                        )
                    else:
                        # Display the detailed error message
                        st.error(message) 

    # File Upload to Audio
    with tab2:
        st.header("File Upload to Audio")
        video_file = st.file_uploader("Upload a Video File", type=["mp4", "mkv", "avi", "mov", "webm", "flv"], key="file_uploader")
        
        # Using session state to manage button click and file presence
        if 'file_audio_processed' not in st.session_state:
            st.session_state.file_audio_processed = False
        if 'file_audio_data' not in st.session_state:
            st.session_state.file_audio_data = None
        if 'file_audio_message' not in st.session_state:
            st.session_state.file_audio_message = ""

        # Clear previous results if a new file is uploaded
        if video_file and st.session_state.get('uploaded_filename') != video_file.name:
             st.session_state.file_audio_processed = False
             st.session_state.file_audio_data = None
             st.session_state.file_audio_message = ""
             st.session_state.uploaded_filename = video_file.name


        if st.button("Prepare File Audio", key="file_button", disabled=(video_file is None)):
             if video_file is not None:
                 st.session_state.file_audio_processed = False # Reset on new button press
                 with st.spinner("Extracting audio from file..."):
                     # Save uploaded file to temporary location
                     with tempfile.TemporaryDirectory() as tmp_dir:
                         temp_path = os.path.join(tmp_dir, video_file.name)
                         logging.info(f"Saving uploaded file to temporary path: {temp_path}")
                         try:
                            with open(temp_path, "wb") as f:
                                f.write(video_file.getbuffer())
                            logging.info("Finished saving uploaded file.")
                         except Exception as e:
                            logging.error(f"Failed to write uploaded file to temp dir: {e}", exc_info=True)
                            st.error(f"Failed to save uploaded file: {e}")
                            # Exit the 'with' block for spinner if saving failed
                            st.stop() 
                         
                         # Process audio
                         audio_bytes, message = extract_audio_from_file(temp_path, video_file.name) 
                         
                         st.session_state.file_audio_processed = True
                         st.session_state.file_audio_data = audio_bytes
                         st.session_state.file_audio_message = message

        # Display results based on session state
        if st.session_state.file_audio_processed:
            audio_bytes = st.session_state.file_audio_data
            message = st.session_state.file_audio_message
            if audio_bytes:
                file_size = len(audio_bytes) / (1024 * 1024)  # Convert to MB
                st.success(f"Audio ready! Filename: '{message}', Size: {file_size:.2f} MB")
                
                # Add download button
                st.download_button(
                    label="💾 Download Audio",
                    data=audio_bytes,
                    file_name=message, # Use the filename returned
                    mime="audio/mpeg",
                    key="file_download_button"
                )
            else:
                # Display the detailed error message
                st.error(message) 

    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: gray; font-size: small;'>"
        "Powered by yt-dlp & MoviePy. Created by <b>Bibek Kumar Thagunna</b>."
        "</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
