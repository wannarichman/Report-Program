import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Voice Briefing", layout="wide")

# 2. 음성 전용 RTC 설정 (가장 가벼운 STUN 서버 사용)
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

# 3. 실시간 댓글 시스템 세션 관리
if "comments" not in st.session_state:
    st.session_state.comments = []

with st.sidebar:
    st.title("🎙️ Voice Briefing")
    st.info("회의 참여자 모두 'START'를 눌러 음성 대화에 참여하세요.")
    
    # [변경] 비디오를 끄고 오디오만 활성화하여 연결성 극대화
    webrtc_streamer(
        key="posco-voice-sync",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": False, "audio": True}, # 오디오만 사용
    )
    
    st.divider()
    st.subheader("💬 실시간 기술 검토 의견")
    
    # 댓글 입력창
    with st.form("comment_form", clear_on_submit=True):
        new_comment = st.text_input("의견 입력")
        submit = st.form_submit_button("전송")
        if submit and new_comment:
            st.session_state.comments.insert(0, f"[{time.strftime('%H:%M:%S')}] {new_comment}")

    # 최근 댓글 목록 표시
    for c in st.session_state.comments[:5]: # 최근 5개만 표시
        st.caption(c)

    st.divider()
    uploaded_file = st.file_uploader("JSON 보고서 로드", type=['json', 'js'])
    edit_mode = st.toggle("📝 편집 모드 활성화", value=False)

# 4. 리포트 렌더링 로직
if uploaded_file and "data" not in st.session_state:
    try:
        st.session_state.data = json.loads(uploaded_file.read().decode("utf-8"))
    except:
        st.error("데이터 파일 로드 실패")

if "data" in st.session_state:
    data = st.session_state.data
    st.title(data.get('title', 'AI R&D Report'))
    st.divider()

    tabs = st.tabs([f"P{i+1}. {p.get('tab', '')}" for i, p in enumerate(data['pages'])])

    for i, tab in enumerate(tabs):
        with tab:
            p = data['pages'][i]
            col_main, col_side = st.columns([1.6, 1])
            
            with col_main:
                st.markdown(f"## {p.get('header', '')}")
                if "image" in p:
                    st.image(p["image"], use_container_width=True)
                
                # 가독성 강조 본문
                for para in p.get('content', '').split('\n'):
                    if para.strip():
                        st.markdown(f"### **{para.strip()}**")
                
                # 최신 댓글 하단 강조 (동기화 느낌 강조)
                if st.session_state.comments:
                    st.warning(f"🗨️ **실시간 피드백:** {st.session_state.comments[0]}")

            with col_side:
                st.subheader(p.get('metrics_title', '📊 주요 지표'))
                if "metrics" in p:
                    for idx, m in enumerate(p['metrics']):
                        st.metric(label=m[0], value=m[1], delta=m[2])
else:
    st.info("왼쪽 사이드바에서 보고서 파일을 업로드하여 '보이스 브리핑'을 시작하세요.")
