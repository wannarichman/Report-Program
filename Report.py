import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Live Sync", layout="wide")

# 2. [전역 공유 저장소] 초기 상태를 엄격히 None으로 설정
@st.cache_resource
def get_global_store():
    return {
        "report_data": None,  # 초기값은 반드시 None
        "current_page": 0,
        "active_users": 0,
        "sync_version": 0
    }

shared_store = get_global_store()

# 접속자 수 관리
if "user_counted" not in st.session_state:
    shared_store["active_users"] += 1
    st.session_state.user_counted = True

# 3. 음성 설정 (사이드바 고정)
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

with st.sidebar:
    st.title("🎙️ 실시간 브리핑")
    is_reporter = st.toggle("🔑 보고자 권한 활성화", value=False)
    st.success(f"👥 접속: **{shared_store['active_users']}명**")
    
    # 음성 스트리머
    webrtc_streamer(
        key="posco-v-final-audio",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": False, "audio": True},
    )

    # [강력 초기화] 버튼 클릭 시 전역 메모리를 즉시 비움
    if st.button("🚨 시스템 전체 초기화"):
        shared_store["report_data"] = None
        shared_store["sync_version"] += 1
        st.cache_resource.clear()
        st.rerun()

    if is_reporter:
        st.divider()
        st.subheader("📂 보고자 컨트롤")
        # [핵심] 파일 업로더의 상태를 세션마다 독립적으로 관리
        uploaded_file = st.file_uploader("보고서 JSON 업로드", type=['json', 'js'], key="report_uploader")
        
        # 새로운 파일이 업로드된 경우에만 전역 저장소 갱신
        if uploaded_file is not None:
            try:
                new_content = json.loads(uploaded_file.read().decode("utf-8"))
                # 기존 데이터와 다를 때만 업데이트하여 무한 루프 방지
                if shared_store["report_data"] != new_content:
                    shared_store["report_data"] = new_content
                    shared_store["sync_version"] += 1
                    st.toast("🚀 보고서가 성공적으로 송출되었습니다.")
            except Exception as e:
                st.error(f"파일 로드 오류: {e}")
        else:
            # 업로더에 파일이 없으면 전역 데이터도 비워버림 (잔상 제거 핵심)
            if shared_store["report_data"] is not None:
                shared_store["report_data"] = None
                shared_store["sync_version"] += 1

# 4. [동기화 엔진] 음성은 유지하고 본문만 실시간 갱신
@st.fragment(run_every="1s")
def sync_content_area():
    # 데이터가 없으면 깨끗한 대기 화면 표시
    if shared_store["report_data"] is None:
        st.info("🛰️ 보고자의 보고서 업로드를 기다리는 중입니다...")
        st.markdown("### 📋 현재 진행 중인 브리핑이 없습니다.")
        st.write("보고자가 파일을 업로드하면 이곳에 실시간으로 리포트가 표시됩니다.")
        return

    # 데이터가 있을 때만 리포트 렌더링
    data = shared_store["report_data"]
    tab_labels = [f"P{i+1}. {p.get('tab', '')}" for i, p in enumerate(data['pages'])]
    
    if is_reporter:
        prev_p = shared_store["current_page"]
        current_tab_idx = st.radio("📑 페이지 이동 컨트롤", range(len(tab_labels)), 
                                   format_func=lambda x: tab_labels[x], horizontal=True)
        if prev_p != current_tab_idx:
            shared_store["current_page"] = current_tab_idx
            shared_store["sync_version"] += 1
    else:
        current_tab_idx = shared_store["current_page"]
        if current_tab_idx >= len(tab_labels): current_tab_idx = 0
        st.warning(f"📍 현재 브리핑 위치: **{tab_labels[current_tab_idx]}**")

    # 리포트 본문 출력
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
