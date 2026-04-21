import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Live Sync", layout="wide")

# 2. [초강력 전역 동기화] 서버가 켜져 있는 동안 모든 세션이 이 객체를 바라봅니다.
if "shared_memory" not in st.session_state.__dict__:
    @st.cache_resource
    def init_shared_store():
        return {
            "report_data": None,
            "current_page": 0,
            "active_users": 0,
            "version": 0
        }
    st.session_state.shared_memory = init_shared_store()

shared_store = st.session_state.shared_memory

# 접속자 수 관리 (중복 방지)
if "counted" not in st.session_state:
    shared_store["active_users"] += 1
    st.session_state.counted = True

# 3. 음성 설정
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

# --- 사이드바 영역 ---
with st.sidebar:
    st.title("🎙️ AI Sync Briefing")
    
    # [권한 설정]
    is_master = st.toggle("🔑 보고자(Master) 권한 활성화", value=False)
    st.success(f"👥 현재 접속: **{shared_store['active_users']}명**")
    
    # 인원 보정 버튼
    c1, c2 = st.columns(2)
    if c1.button("인원 -1"): shared_store["active_users"] -= 1
    if c2.button("인원 초기화"): shared_store["active_users"] = 1
    
    if st.button("🚨 시스템 전체 리셋"):
        shared_store["report_data"] = None
        shared_store["version"] += 1
        st.rerun()

    st.divider()
    
    # 음성 스트리머
    webrtc_streamer(
        key="posco-v13-final",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": False, "audio": True},
    )

    st.divider()

    if is_master:
        st.subheader("📂 마스터 컨트롤")
        uploaded_file = st.file_uploader("보고서 JSON 업로드", type=['json', 'js'])
        if uploaded_file:
            # 보고자가 파일을 올리면 즉시 전역 저장소에 갱신
            shared_store["report_data"] = json.loads(uploaded_file.read().decode("utf-8"))
            shared_store["version"] += 1
            st.success("✅ 보고서가 서버에 업로드되었습니다!")
        
        edit_mode = st.toggle("📝 편집 모드", value=False)
    else:
        # 보고받는 자는 2초마다 버전 변화를 감지하여 자동 리프레시
        st.info("📢 마스터의 보고서를 수신 중...")
        if shared_store["report_data"] is None:
            time.sleep(2)
            st.rerun()

# 4. 리포트 본문 (동기화 렌더링)
if shared_store["report_data"]:
    data = shared_store["report_data"]
    tab_labels = [f"P{i+1}. {p.get('tab', '')}" for i, p in enumerate(data['pages'])]
    
    if is_master:
        current_tab_idx = st.radio("📑 페이지 이동", range(len(tab_labels)), 
                                   format_func=lambda x: tab_labels[x], horizontal=True)
        shared_store["current_page"] = current_tab_idx
    else:
        # 마스터의 페이지 번호와 무조건 동기화
        current_tab_idx = shared_store["current_page"]
        if current_tab_idx >= len(tab_labels): current_tab_idx = 0
        st.info(f"📍 브리핑 중: **{tab_labels[current_tab_idx]}**")

    p = data['pages'][current_tab_idx]
    st.divider()
    
    col_main, col_side = st.columns([2, 1], gap="large")
    with col_main:
        if is_master and edit_mode:
            p['header'] = st.text_input("헤더", p.get('header', ''), key=f"h_{current_tab_idx}")
            p['content'] = st.text_area("본문", p.get('content', ''), key=f"c_{current_tab_idx}")
            p['img_width'] = st.slider("크기", 200, 1200, int(p.get('img_width', 800)), key=f"i_{current_tab_idx}")
        
        st.markdown(f"# {p.get('header', '')}")
        if "image" in p:
            st.image(p["image"], width=int(p.get('img_width', 800)))
        
        for para in p.get('content', '').split('\n'):
            if para.strip(): st.markdown(f"### **{para.strip()}**")

    with col_side:
        st.subheader(p.get('metrics_title', '📊 지표'))
        if "metrics" in p:
            for idx, m in enumerate(p['metrics']):
                if is_master and edit_mode:
                    m[0], m[1] = st.text_input(f"L{idx}", m[0], key=f"l_{idx}"), st.text_input(f"V{idx}", m[1], key=f"v_{idx}")
                st.metric(label=m[0], value=m[1], delta=m[2] if len(m)>2 else None)
else:
    st.warning("⚠️ 현재 서버에 로드된 보고서가 없습니다. 보고자는 파일을 업로드해 주세요.")
