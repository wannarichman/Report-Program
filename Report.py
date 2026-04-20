import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Dashboard", layout="wide")

# 2. CSS 주입 (가장 안전한 단순 문자열 방식)
design_css = """
<style>
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
"""
st.markdown(design_css, unsafe_allow_headers=True)

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
    st.subheader("📂 보고서 데이터 로드")
    uploaded_file = st.file_uploader("JSON 파일을 선택하세요", type=['json', 'js'])

# 4. 데이터 로직
user_data = None
if uploaded_file is not None:
    try:
        raw_content = uploaded_file.read().decode("utf-8")
        if "const reportData =" in raw_content:
            json_str = raw_content.split("=", 1)[1].strip().rstrip(";")
            user_data = json.loads(json_str)
        else:
            user_data = json.loads(raw_content)
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")

# 5. 화면 렌더링 (에러 발생 지점을 표준 함수로 전면 교체)
if user_data:
    # 제목 출력 (st.write 대신 표준 st.title 사용)
    st.title(user_data.get('title', 'AI R&D Report'))
    st.divider()

    pages = user_data.get('pages', [])
    tab_labels = [f"PAGE {i+1}: {p.get('tab', '')}" for i, p in enumerate(pages)]
    
    if pages:
        tabs = st.tabs(tab_labels)
        for i, tab in enumerate(tabs):
            with tab:
                p = pages[i]
                col_main, col_side = st.columns([1.6, 1])
                
                with col_main:
                    # 헤더 출력
                    st.header(p.get('header', ''))
                    
                    # 이미지 출력 로직
                    if "image" in p:
                        st.image(p["image"], use_container_width=True)
                    
                    # 본문 (HTML 태그를 최소화한 Markdown 카드 방식)
                    st.markdown(f'<div class="content-card">{p.get("content", "")}</div>', unsafe_allow_headers=True)
                    
                    # 핵심 메시지
                    if "highlight" in p:
                        st.markdown(f'<div class="key-message">💡 핵심 메시지: {p["highlight"]}</div>', unsafe_allow_headers=True)

                with col_side:
                    st.subheader("📊 주요 지표")
                    if "metrics" in p:
                        for m in p['metrics']:
                            if len(m) == 3:
                                st.metric(label=m[0], value=m[1], delta=m[2])
                    
                    if "tags" in p:
                        st.write("---")
                        st.caption(", ".join([f"#{t}" for t in p['tags']]))
else:
    st.info("왼쪽 사이드바에서 JSON 파일을 업로드하여 스마트 보고서를 시작하세요.")
