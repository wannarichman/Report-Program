import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Live Sync", layout="wide")

# 2. [전역 공유 저장소]
@st.cache_resource
def get_shared_store():
    return {
        "report_data": None,
        "current_page": 0,
        "active_users": 0,
        "sync_version": 0
    }

shared_store = get_shared_store()

# 접속자 수 관리
if "user_counted" not in st.session_state:
    shared_store["active_users"] += 1
    st.session_state.user_counted = True

# 3. 음성 설정 (마이크 유지의 핵심)
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

# --- 사이드바: 음성 세션 (이곳은 새로고침되지 않음) ---
with st.sidebar:
    st.title("🎙️ 실시간 브리핑")
    is_reporter = st.toggle("🔑 보고자 권한 활성화", value=False)
    st.success(f"👥 접속: **{shared_store['active_users']}명**")
    
    # [핵심] 음성 스트리머는 사이드바에 고정하여 본문 갱신 시에도 끊기지 않게 함
    webrtc_streamer(
        key="posco-v-stable-audio",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": False, "audio": True},
    )

    if st.button("🚨 전체 리셋"):
        shared_store["report_data"] = None
        shared_store["sync_version"] += 1
        st.cache_resource.clear()
        st.rerun()

    if is_reporter:
        st.divider()
        st.subheader("📂 보고자 컨트롤")
        uploaded_file = st.file_uploader("보고서 JSON 업로드", type=['json', 'js'])
        if uploaded_file:
            shared_store["report_data"] = json.loads(uploaded_file.read().decode("utf-8"))
            shared_store["sync_version"] += 1
            st.toast("🚀 보고서 동기화 완료")

# 4. [동기화 엔진] 1초마다 본문만 새로 그리는 조각(Fragment) 정의
@st.fragment(run_every="1s")
def sync_content_area():
    if shared_store["report_data"] is None:
        st.warning("⚠️ 보고서 대기 중...")
        return

    data = shared_store["report_data"]
    tab_labels = [f"P{i+1}. {p.get('tab', '')}" for i, p in enumerate(data['pages'])]
    
    # 보고자: 페이지 전환 컨트롤러 표시
    if is_reporter:
        prev_p = shared_store["current_page"]
        current_tab_idx = st.radio("📑 페이지 이동", range(len(tab_labels)), 
                                   format_func=lambda x: tab_labels[x], horizontal=True)
        if prev_p != current_tab_idx:
            shared_store["current_page"] = current_tab_idx
            shared_store["sync_version"] += 1
    else:
        # 보고받는 자: 마스터 페이지 자동 추적
        current_tab_idx = shared_store["current_page"]
        if current_tab_idx >= len(tab_labels): current_tab_idx = 0
        st.warning(f"📍 브리핑 위치: **{tab_labels[current_tab_idx]}**")

    # 본문 렌더링
    p = data['pages'][current_tab_idx]
    st.divider()
    col_main, col_side = st.columns([2, 1], gap="large")
    
    with col_main:
        st.markdown(f"# {p.get('header', '')}")
        if "image" in p:
            st.image(p["image"], width=int(p.get('img_width', 800)))
        for para in p.get('content', '').split('\n'):
            if para.strip(): st.markdown(f"### **{para.strip()}**")

    with col_side:
        st.subheader(p.get('metrics_title', '📊 지표'))
        if "metrics" in p:
            for idx, m in enumerate(p['metrics']):
                st.metric(label=m[0], value=m[1], delta=m[2] if len(m)>2 else None)

# 실행
sync_content_area()
