import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import streamlit.components.v1 as components
import json

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Dashboard", layout="wide")

# 2. CSS 주입 (TypeError 방지를 위해 html 컴포넌트 방식 사용)
design_html = """
<style>
    .title-text { font-size: 40px; font-weight: 800; color: #1a2a6c; font-family: sans-serif; }
    .header-text { font-size: 28px; font-weight: 700; color: #2c3e50; font-family: sans-serif; }
    .content-card { 
        background-color: white; padding: 20px; border-radius: 12px; 
        box-shadow: 0 4px 10px rgba(0,0,0,0.05); border-left: 8px solid #1a2a6c;
        font-size: 18px; color: #444; font-family: sans-serif; margin-bottom: 15px;
    }
    .key-message {
        background-color: #fff9db; padding: 15px; border-radius: 10px;
        border-left: 5px solid #fcc419; font-weight: 600; color: #333; font-family: sans-serif;
    }
</style>
"""
# markdown 대신 components를 사용하여 내부 충돌 회피
components.html(design_html, height=0)

# 3. 실시간 화상 보고 설정
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

with st.sidebar:
    st.title("📷 Live Sync")
    webrtc_streamer(
        key="cam-stream",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": True, "audio": True},
    )
    st.divider()
    st.subheader("📂 보고서 데이터")
    uploaded_file = st.file_uploader("JSON 파일을 로드하세요", type=['json', 'js'])

# 4. 데이터 로직
user_data = None
if uploaded_file is not None:
    try:
        raw_data = uploaded_file.read().decode("utf-8")
        if "const reportData =" in raw_data:
            json_str = raw_data.split("=", 1)[1].strip().rstrip(";")
            user_data = json.loads(json_str)
        else:
            user_data = json.loads(raw_data)
    except:
        st.error("데이터 형식 오류")

# 5. 화면 렌더링
if user_data:
    # 텍스트 출력 시에도 커스텀 CSS 클래스 적용 (HTML 태그 직접 사용)
    main_title = user_data.get('title', 'AI R&D Report')
    st.write(f'<p class="title-text">{main_title}</p>', unsafe_allow_headers=True)
    st.divider()

    pages = user_data.get('pages', [])
    tab_labels = [f"P{i+1}. {p.get('tab', '')}" for i, p in enumerate(pages)]
    
    if pages:
        tabs = st.tabs(tab_labels)
        for i, tab in enumerate(tabs):
            with tab:
                p = pages[i]
                col_left, col_right = st.columns([1.5, 1])
                
                with col_left:
                    st.write(f'<p class="header-text">{p.get("header", "")}</p>', unsafe_allow_headers=True)
                    st.write(f'<div class="content-card">{p.get("content", "")}</div>', unsafe_allow_headers=True)
                    if "highlight" in p:
                        st.write(f'<div class="key-message">💡 {p["highlight"]}</div>', unsafe_allow_headers=True)

                with col_right:
                    st.markdown("### 📊 지표 확인")
                    if "metrics" in p:
                        for m in p['metrics']:
                            if len(m) == 3:
                                st.metric(label=m[0], value=m[1], delta=m[2])
else:
    st.info("파일을 업로드하면 보고서 대시보드가 활성화됩니다.")
