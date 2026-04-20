import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Voice Briefing", layout="wide")

# 2. 음성 전용 RTC 설정
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

# 3. 실시간 댓글 세션 관리
if "comments" not in st.session_state:
    st.session_state.comments = []

with st.sidebar:
    st.title("🎙️ Voice Briefing")
    
    # [핵심 추가] 음성 입력 상태 표시기
    st.subheader("🔊 Live Audio Status")
    
    # WebRTC 스트리머 설정
    webrtc_ctx = webrtc_streamer(
        key="posco-voice-sync-v2",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": False, "audio": True},
    )

    # 음성 연결 상태에 따른 시각적 피드백
    if webrtc_ctx.state.playing:
        st.success("✅ 음성 송출 중: 마이크가 활성화되었습니다.")
        # 오디오 신호가 들어오고 있음을 보여주는 프로그레스 바 (데모용 시각화)
        st.write("마이크 감도")
        st.progress(0.65) # 실제 데이터 스트림과 연동이 어려운 환경을 대비한 시각적 장치
    else:
        st.error("🛑 대기 중: 'START'를 눌러 참여하세요.")

    st.divider()
    st.subheader("💬 실시간 기술 검토 의견")
    with st.form("comment_form", clear_on_submit=True):
        new_comment = st.text_input("의견 입력")
        submit = st.form_submit_button("전송")
        if submit and new_comment:
            st.session_state.comments.insert(0, f"[{time.strftime('%H:%M:%S')}] {new_comment}")

    for c in st.session_state.comments[:3]:
        st.caption(c)

    st.divider()
    uploaded_file = st.file_uploader("JSON 보고서 로드", type=['json', 'js'])
    edit_mode = st.toggle("📝 편집 모드 활성화", value=False)

# 4. 리포트 렌더링 로직 (기존과 동일)
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
                for para in p.get('content', '').split('\n'):
                    if para.strip():
                        st.markdown(f"### **{para.strip()}**")
                if st.session_state.comments:
                    st.warning(f"🗨️ **최신 피드백:** {st.session_state.comments[0]}")

            with col_side:
                st.subheader(p.get('metrics_title', '📊 주요 지표'))
                if "metrics" in p:
                    for idx, m in enumerate(p['metrics']):
                        st.metric(label=m[0], value=m[1], delta=m[2])
