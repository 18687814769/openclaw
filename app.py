import streamlit as st
import requests
import os
import time
import numpy as np
import imageio
from PIL import Image, ImageDraw, ImageFont
import io
import base64

# ================= 配置区域 =================
try:
    API_KEY = st.secrets["nvidia"]["api_key"]
    if not API_KEY or not API_KEY.startswith("nvapi-"):
        st.error("⚠️ API Key 格式不正确！")
        st.stop()
except KeyError:
    st.error("⚠️ 未找到 API Key，请检查 Secrets。")
    st.stop()

# NVIDIA 接口
IMAGE_URL = "https://ai.api.nvidia.com/v1/genai/stabilityai/stable-diffusion-xl-base-1.0"
# 如果需要文本生成，可保留 BASE_URL，此处简化为直接生成图片
BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL_FAST = "meta/llama-3.1-70b-instruct"

# 免费背景音乐 (示例，使用短音频避免同步问题，或生成无声视频)
# 为了完美兼容，我们先生成无声高清视频，音频通过前端播放器叠加（Streamlit 原生支持）
# 或者使用纯 Python 库写入音频 (需 pydub/ffmpeg，此处为了纯净暂不引入，专注视频生成)
BGM_URL = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"

# ==========================================
st.set_page_config(page_title="小景漫剧工厂", page_icon="🎬", layout="wide")

# --- 自定义 CSS ---
st.markdown("""
<style>
.stApp { background-color: #0e1117; color: #fafafa; }
h1 { text-align: center; color: #76b900; }
.stButton>button { background-color: #76b900; color: white; border-radius: 8px; border: none; font-size: 1.2rem; width: 100%; }
.stButton>button:hover { background-color: #5a8f00; }
</style>
""", unsafe_allow_html=True)

# --- 核心函数：AI 绘图 ---
def generate_image(prompt):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    # 添加动态描述词，让画面更有张力
    full_prompt = f"{prompt}, cinematic lighting, 8k, highly detailed, masterpiece, anime style, dynamic angle"
    payload = {
        "prompt": full_prompt,
        "width": 1024,
        "height": 1024,
        "steps": 30,
        "guidance": 7.5
    }
    try:
        response = requests.post(IMAGE_URL, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            return response.content
        else:
            return None
    except:
        return None

# --- 核心函数：添加文字到图片 (纯 Python 实现) ---
def add_text_to_image(image_bytes, text):
    image = Image.open(io.BytesIO(image_bytes))
    draw = ImageDraw.Draw(image)
    # 尝试加载字体，如果失败则使用默认
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except:
        font = ImageFont.load_default()
    
    # 计算文字位置 (底部居中)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((image.width - text_width) // 2, image.height - text_height - 50)
    
    # 绘制黑色背景条以突出文字
    draw.rectangle([position[0]-10, position[1]-10, position[0]+text_width+10, position[1]+text_height+10], fill=(0, 0, 0, 180))
    draw.text(position, text, font=font, fill=(255, 255, 255))
    
    # 转换回字节
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    return buf.getvalue()

# --- 核心函数：生成视频 (纯 Python + imageio) ---
def create_video_from_images(image_paths, texts, output_path="output.mp4"):
    frames = []
    for i, img_path in enumerate(image_paths):
        # 读取图片
        img_data = open(img_path, 'rb').read()
        # 添加字幕
        img_with_text = add_text_to_image(img_data, texts[i])
        # 转换为 numpy 数组
        img_np = np.array(Image.open(io.BytesIO(img_with_text)))
        # 重复帧以模拟时长 (假设 3 秒，30fps = 90 帧)
        for _ in range(90): 
            frames.append(img_np)
    
    # 使用 imageio 写入 MP4 (使用 ffmpeg 插件，但通过 imageio 调用，通常更稳定)
    # 注意：Streamlit Cloud 可能没有系统级 ffmpeg，但 imageio-ffmpeg 会尝试下载或使用内置
    try:
        with imageio.get_writer(output_path, fps=30, codec='libx264') as writer:
            for frame in frames:
                writer.append_data(frame)
        return output_path
    except Exception as e:
        # 如果 libx264 失败，尝试生成 GIF 作为备选
        gif_path = output_path.replace('.mp4', '.gif')
        with imageio.get_writer(gif_path, fps=10) as writer:
            for frame in frames[::3]: # 降低帧率以减小 GIF 体积
                writer.append_data(frame)
        return gif_path

# --- 主界面 ---
st.title("🎬 小景漫剧工厂")
st.markdown("### 🌟 输入故事，一键生成高清动态漫剧")

story = st.text_area("请输入小说片段 (200 字以内)", height=150, placeholder="少年紧握拳头，眼神坚定...")

if st.button("🚀 立即生成"):
    if not story:
        st.warning("请输入故事！")
    else:
        progress = st.progress(0)
        status = st.empty()
        
        # 1. 生成分镜提示词 (简化版，直接基于故事)
        status.text("🤖 正在分析故事...")
        prompts = [
            f"{story} -- wide angle, cinematic",
            f"{story} -- close up, dramatic",
            f"{story} -- action scene, dynamic",
            f"{story} -- epic finale, masterpiece"
        ]
        narrations = ["第一幕：起始", "第二幕：发展", "第三幕：高潮", "第四幕：结局"]
        
        # 2. 生成图片
        image_paths = []
        for i, p in enumerate(prompts):
            status.text(f"🎨 绘制中 ({i+1}/4)...")
            img_data = generate_image(p)
            if img_data:
                fname = f"frame_{i}.png"
                with open(fname, "wb") as f:
                    f.write(img_data)
                image_paths.append(fname)
            progress.progress((i+1) * 25)
        
        if len(image_paths) < 4:
            st.error("图片生成失败")
            st.stop()
            
        # 3. 合成视频
        status.text("🎬 正在合成视频...")
        try:
            video_path = create_video_from_images(image_paths, narrations)
            status.text("✅ 完成！")
            
            if video_path.endswith(".mp4"):
                st.video(video_path)
                with open(video_path, "rb") as f:
                    st.download_button("📥 下载 MP4", f, "manhua.mp4")
            else:
                st.image(video_path)
                st.info("由于环境限制，已生成 GIF 版本。")
                with open(video_path, "rb") as f:
                    st.download_button("📥 下载 GIF", f, "manhua.gif")
                    
        except Exception as e:
            st.error(f"合成失败：{str(e)}")
            st.info("建议：检查环境是否支持 imageio-ffmpeg。")
