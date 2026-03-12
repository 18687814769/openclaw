import streamlit as st
import requests
import os
import time
import numpy as np
import imageio
from PIL import Image, ImageDraw, ImageFont
import io

# ================= 配置区域 =================
# 1. 获取 API Key (必须在新 App 的 Secrets 里配置)
try:
    API_KEY = st.secrets["nvidia"]["api_key"]
    if not API_KEY or not API_KEY.startswith("nvapi-"):
        st.error("⚠️ API Key 格式错误或为空！请去 Settings -> Secrets 配置 nvapi-...")
        st.stop()
except KeyError:
    st.error("⚠️ 未在 Secrets 中找到 'nvidia' -> 'api_key'。请检查配置。")
    st.stop()

# NVIDIA 图像生成接口
IMAGE_URL = "https://ai.api.nvidia.com/v1/genai/stabilityai/stable-diffusion-xl-base-1.0"

# ==========================================
st.set_page_config(page_title="小景漫剧工厂", page_icon="🎬", layout="wide")

# --- 自定义 CSS ---
st.markdown("""
<style>
.stApp { background-color: #0e1117; color: #fafafa; }
h1 { text-align: center; color: #76b900; }
.stButton>button { background-color: #76b900; color: white; border-radius: 8px; border: none; font-size: 1.2rem; width: 100%; padding: 10px; }
.stButton>button:hover { background-color: #5a8f00; }
.stTextArea label { font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 核心函数：AI 绘图 (增强版) ---
def generate_image(prompt, seed=42):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    # 优化 Prompt，确保生成高质量、适合视频的图
    full_prompt = f"{prompt}, masterpiece, best quality, highly detailed, 8k, cinematic lighting, anime style, dynamic composition"
    
    payload = {
        "prompt": full_prompt,
        "width": 1024,
        "height": 1024,
        "steps": 30,
        "guidance": 7.5,
        "seed": seed # 固定种子以保证一定的一致性（可选）
    }
    
    try:
        response = requests.post(IMAGE_URL, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            return response.content
        else:
            st.error(f"API 错误：{response.status_code} - {response.text[:100]}")
            return None
    except Exception as e:
        st.error(f"请求失败：{str(e)}")
        return None

# --- 核心函数：添加字幕 ---
def add_caption(image_bytes, text):
    image = Image.open(io.BytesIO(image_bytes))
    draw = ImageDraw.Draw(image)
    
    # 尝试加载字体
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except:
        font = ImageFont.load_default()
        
    # 文字位置计算
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    # 底部居中，留边距
    x = (image.width - text_w) // 2
    y = image.height - text_h - 50
    
    # 画黑色半透明底
    draw.rectangle([x-10, y-10, x+text_w+10, y+text_h+10], fill=(0, 0, 0, 180))
    # 画字
    draw.text((x, y), text, font=font, fill=(255, 255, 255))
    
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    return buf.getvalue()

# --- 核心函数：合成视频 (纯 Python) ---
def create_video(frames_data, captions, output_path="output.mp4", fps=24, duration_per_frame=3):
    all_frames = []
    
    for i, img_data in enumerate(frames_data):
        # 添加字幕
        img_with_text = add_caption(img_data, captions[i])
        img_np = np.array(Image.open(io.BytesIO(img_with_text)))
        
        # 扩展帧 (3 秒 * 24 fps = 72 帧)
        for _ in range(duration_per_frame * fps):
            all_frames.append(img_np)
            
    # 写入视频
    try:
        with imageio.get_writer(output_path, fps=fps, codec='libx264', quality=8) as writer:
            for frame in all_frames:
                writer.append_data(frame)
        return output_path
    except Exception as e:
        # 如果 H.264 失败，尝试生成 GIF
        st.warning(f"MP4 编码失败 ({str(e)})，尝试生成 GIF...")
        gif_path = output_path.replace(".mp4", ".gif")
        # 降低帧率生成 GIF
        low_res_frames = all_frames[::12] # 抽帧
        with imageio.get_writer(gif_path, fps=10) as writer:
            for frame in low_res_frames:
                writer.append_data(frame)
        return gif_path

# --- 主界面 ---
st.title("🎬 小景漫剧工厂 v3.0")
st.markdown("### 🌟 输入故事，一键生成高清动态漫剧 (MP4)")

story = st.text_area("请输入小说片段 (支持长文本，AI 会自动提炼)", height=200, placeholder="从前有个少年...")

if st.button("🚀 开始生成漫剧"):
    if not story:
        st.warning("请输入故事内容！")
    else:
        progress = st.progress(0)
        status = st.empty()
        
        # 1. 提炼分镜 (简化版：直接拆分故事为 4 段)
        status.text("🤖 正在分析故事并拆分为 4 个分镜...")
        # 这里简化处理，实际应调用 LLM 拆分。为了演示，我们假设故事分 4 段
        # 如果故事短，就重复使用；如果长，简单切分
        segments = story.split('。')
        prompts = []
        captions = []
        
        # 构造 4 个分镜提示词
        base_prompts = [
            f"{story} -- wide shot, establishing scene, anime style",
            f"{story} -- close up, character expression, dramatic lighting",
            f"{story} -- action scene, dynamic angle, intense",
            f"{story} -- epic finale, masterpiece, emotional"
        ]
        
        # 如果故事被句号拆分了，就取前 4 段作为提示词的一部分，否则用原故事
        if len(segments) >= 4:
             prompts = [f"{segments[i]} {base_prompts[i].split('--')[1]}" for i in range(4)]
        else:
             prompts = base_prompts
             
        captions = ["第一幕：起始", "第二幕：发展", "第三幕：高潮", "第四幕：结局"]
        
        # 2. 生成图片
        image_data_list = []
        image_preview = st.columns(4)
        
        for i in range(4):
            status.text(f"🎨 正在绘制第 {i+1} 张分镜...")
            # 显示进度
            progress.progress((i+1) * 25)
            
            img_bytes = generate_image(prompts[i], seed=123+i) # 固定种子保证一定稳定性
            if img_bytes:
                image_data_list.append(img_bytes)
                # 实时预览
                image_preview[i].image(image_bytes, caption=f"分镜 {i+1}", use_container_width=True)
            else:
                st.error(f"第 {i+1} 张图生成失败，停止。")
                st.stop()
        
        # 3. 合成视频
        status.text("🎬 正在合成视频 (添加字幕/特效)...")
        try:
            video_file = create_video(image_data_list, captions)
            progress.progress(100)
            status.text("✅ 生成成功！")
            
            # 展示结果
            if video_file.endswith(".mp4"):
                st.video(video_file)
                with open(video_file, "rb") as f:
                    st.download_button("📥 下载 MP4 视频", f, "manhua.mp4")
            else:
                st.image(video_file)
                st.info("已生成 GIF 版本（MP4 编码受限）。")
                with open(video_file, "rb") as f:
                    st.download_button("📥 下载 GIF", f, "manhua.gif")
                    
        except Exception as e:
            st.error(f"视频合成出错：{str(e)}")
            st.info("建议：检查 Secrets 配置或网络环境。")

st.markdown("---")
st.caption("© 2026 小景漫剧工厂 | Powered by NVIDIA SDXL")
