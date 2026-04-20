import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Dashboard", layout="wide")

# 2. PPT 스타일의 커스텀 UI 디자인 (CSS 들여쓰기 주의)
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .title-text { font-size: 45px !important; font-weight: 800; color: #1a2a6c; margin-bottom: 5px; }
    .header-text { font-size: 32px !important; font-weight: 700; color: #2c3e50; line-height: 1.2; margin-bottom: 20px; }
    .content-card { 
        background-color: white; padding: 25px; border-radius: 15px; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.05); border-left: 8px solid #1a2a6c;
        font-size: 19px; line-height: 1.6; color: #444; margin-bottom: 20px;
    }
    .key-message {
        background-color: #fff9db; padding: 15px 20px; border-radius: 10px;
        border-left: 5px solid #fcc419; font-weight: 600; color: #333; font-size: 18px;
    }
</style>
""", unsafe_allow_headers=True)

# 3. 실시간 화상 보고 설정
RTC_CONFIGURATION = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

with st.sidebar:
    st.markdown("<h2 style='color:#1a2a6c;'>📷 Live Sync</h2>", unsafe_allow_headers=True)
    webrtc_streamer(
        key="cam-stream",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIGURATION,
        media_stream_constraints={"video": True, "audio": True},
    )
    st.divider()
    st.subheader("📂 보고서 파일 로드")
    uploaded_file = st.file_uploader("JSON 파일을 선택하세요", type=['json', 'js'])

# 4. 데이터 로직
user_data = None
if uploaded_file:
    try:
        content = uploaded_file.read().decode("utf-8")
        if "const reportData =" in content:
            json_str = content.split("=", 1)[1].strip().rstrip(";")
            user_data = json.loads(json_str)
        else:
            user_data = json.loads(content)
    except Exception as e:
        st.error(f"데이터 로드 오류: {e}")

if user_data:
    st.markdown(f"<p class='title-text'>{user_data.get('title', 'AI R&D Report')}</p>", unsafe_allow_headers=True)
    st.divider()

    tab_labels = [f"PAGE {i+1}: {p['tab']}" for i, p in enumerate(user_data['pages'])]
    tabs = st.tabs(tab_labels)

    for i, tab in enumerate(tabs):
        with tab:
            p = user_data['pages'][i]
            col_main, col_side = st.columns([1.6, 1])
            
            with col_main:
                st.markdown(f"<p class='header-text'>{p['header']}</p>", unsafe_allow_headers=True)
                st.markdown(f"<div class='content-card'>{p['content']}</div>", unsafe_allow_headers=True)
                if "highlight" in p:
                    st.markdown(f"<div class='key-message'>💡 핵심 메시지: {p['highlight']}</div>", unsafe_allow_headers=True)

            with col_side:
                st.write("") 
                if "metrics" in p:
                    st.markdown("### 📊 성과 지표")
                    for m in p['metrics']:
                        if len(m) == 3:
                            st.metric(label=m[0], value=m[1], delta=m[2])
                if "tags" in p:
                    st.write("---")
                    st.caption(", ".join([f"#{t}" for t in p['tags']]))
else:
    st.info("왼쪽 사이드바에서 보고서 데이터 파일(.json)을 업로드하십시오.")
