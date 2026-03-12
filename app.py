import streamlit as st
import requests
import os
import time
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, TextClip, ConcatenateVideoClip
import pandas as pd
from datetime import datetime

# ================= 配置区域 =================
# 从 Secrets 获取 Key (记得在新 App 的 Streamlit 后台也配置好 NVIDIA_API_KEY)
try:
    API_KEY = st.secrets["nvidia"]["api_key"]
    if not API_KEY or not API_KEY.startswith("nvapi-"):
        st.error("⚠️ API Key 格式不正确！请检查 Secrets。")
        st.stop()
except KeyError:
    st.error("⚠️ 未找到 API Key，请检查 Secrets。")
    st.stop()

# NVIDIA 接口
BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
IMAGE_URL = "https://ai.api.nvidia.com/v1/genai/stabilityai/stable-diffusion-xl-base-1.0"
MODEL_FAST = "meta/llama-3.1-70b-instruct"

# 免费背景音乐 (示例)
BGM_URL = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"

# ==========================================
# --- 页面配置 (宽屏模式，适合视频预览) ---
st.set_page_config(page_title="小景漫剧工厂", page_icon="🎬", layout="wide")

# --- 自定义 CSS (暗黑电影风) ---
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    h1 { text-align: center; color: #76b900; font-family: 'Arial', sans-serif; }
    .stButton>button { 
        background-color: #76b900; color: white; 
        border-radius: 8px; border: none; 
        font-size: 1.2rem; font-weight: bold;
        width: 100%; padding: 0.5rem;
    }
    .stButton>button:hover { background-color: #5a8f00; }
    .stTextArea>div>div>textarea { font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

# --- 核心函数：AI 绘图 ---
def generate_image(prompt):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "prompt": prompt + ", cinematic lighting, 8k, highly detailed, masterpiece, anime style",
        "width": 1024, "height": 1024, "steps": 30, "guidance": 7.5
    }
    try:
        response = requests.post(IMAGE_URL, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            return response.content
        else:
            return None
    except:
        return None

# --- 核心函数：视频合成 ---
def create_video_clips(image_paths, narrations, output_path="output.mp4"):
    clips = []
    duration = 3.0  # 每张图 3 秒
    
    # 下载背景音乐
    bgm_path = "bgm.mp3"
    try:
        with open(bgm_path, "wb") as f:
            f.write(requests.get(BGM_URL).content)
        bgm_clip = AudioFileClip(bgm_path).subclip(0, duration * len(image_paths))
    except:
        bgm_clip = None

    for i, img_path in enumerate(image_paths):
        clip = ImageClip(img_path).set_duration(duration)
        # 添加字幕
        txt = TextClip(narrations[i], fontsize=24, color='white', font='Arial', 
                       stroke_color='black', stroke_width=1, 
                       size=(clip.size[0]*0.9, None), method='caption')
        txt = txt.set_pos(('center', 'bottom')).set_duration(duration)
        clip = CompositeVideoClip([clip, txt])
        clips.append(clip)

    final_video = ConcatenateVideoClip(clips, method="compose")
    if bgm_clip:
        final_video = final_video.set_audio(bgm_clip)
    
    final_video.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac')
    return output_path

# --- 主界面 ---
st.title("🎬 小景漫剧工厂")
st.markdown("### 🌟 输入一段故事，一键生成动态漫剧视频")
st.markdown("---")

# 输入区
col1, col2 = st.columns([2, 1])
with col1:
    story = st.text_area("请输入小说片段或故事大纲 (200 字以内效果最佳)", height=150, 
                         placeholder="从前有个少年，他紧握拳头，眼神坚定地望向远方...")

with col2:
    st.image("https://cdn-icons-png.flaticon.com/512/3406/3406979.png", width=200)
    st.markdown("**💡 使用技巧：**\n- 描述具体的画面感\n- 包含人物动作和表情\n- 200 字以内生成最快")

if st.button("🚀 立即生成漫剧视频"):
    if not story:
        st.warning("请先输入故事内容！")
    else:
        progress = st.progress(0)
        status = st.empty()
        
        # 1. 生成分镜 (简化版：直接生成 4 个提示词)
        status.text("🤖 正在分析故事并生成分镜...")
        # 简化逻辑：直接基于故事生成 4 个变体 Prompt
        prompts = [
            f"{story} -- cinematic shot 1, wide angle, anime style",
            f"{story} -- cinematic shot 2, close up, dramatic lighting",
            f"{story} -- cinematic shot 3, action scene, dynamic",
            f"{story} -- cinematic shot 4, epic finale, masterpiece"
        ]
        narrations = ["第一幕：故事开始", "第二幕：情节发展", "第三幕：高潮来临", "第四幕：结局揭晓"]
        progress.progress(10)

        # 2. 生成图片
        image_paths = []
        for i, p in enumerate(prompts):
            status.text(f"🎨 正在绘制高清原画 ({i+1}/4)...")
            img_data = generate_image(p)
            if img_data:
                fname = f"frame_{i}.png"
                with open(fname, "wb") as f:
                    f.write(img_data)
                image_paths.append(fname)
            progress.progress(10 + (i+1)*20)
        
        if len(image_paths) < 4:
            st.error("图片生成失败，请重试。")
            st.stop()

        # 3. 合成视频
        status.text("🎬 正在剪辑合成视频 (添加字幕/音乐/动态效果)...")
        try:
            output_file = "manhua_video.mp4"
            video_path = create_video_clips(image_paths, narrations, output_file)
            progress.progress(100)
            status.text("✅ 生成成功！")
            
            # 展示结果
            st.video(video_path)
            with open(video_path, "rb") as f:
                st.download_button("📥 下载高清视频 (MP4)", f, file_name="my_manhua.mp4")
            
        except Exception as e:
            st.error(f"视频合成失败：{str(e)}")
            st.info("提示：请确保环境已安装 ffmpeg 和 moviepy。")

st.markdown("---")
st.markdown("© 2026 小景漫剧工厂 | Powered by NVIDIA & Streamlit")
