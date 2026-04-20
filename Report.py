import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Dashboard", layout="wide")

# 2. 실시간 화상 보고 설정
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

with st.sidebar:
    st.title("🎥 Live Sync")
    # 기존 카메라 기능 유지
    webrtc_streamer(
        key="cam-stream",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": True, "audio": True},
    )
    st.divider()
    st.subheader("📂 보고서 데이터 로드")
    # 기존 JSON 업로드 기능 유지
    uploaded_file = st.file_uploader("JSON 파일을 선택하세요", type=['json', 'js'])

# 3. 데이터 로직
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

# 4. 화면 렌더링 (에러 방지를 위해 Streamlit 표준 함수만 사용)
if user_data:
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
                    st.header(p.get('header', ''))
                    
                    # 이미지 출력 (JSON에 포함된 이미지 링크 반영)
                    if "image" in p:
                        st.image(p["image"], use_container_width=True)
                    
                    # 본문 출력 (안전한 표준 방식)
                    st.write(p.get("content", ""))
                    
                    if "highlight" in p:
                        st.success(f"💡 핵심 메시지: {p['highlight']}")

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
    st.info("왼쪽 사이드바에서 JSON 파일을 업로드하여 보고서를 시작하세요.")
