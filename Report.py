import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Live Sync", layout="wide")

# 2. [전역 공유 저장소] 서버 메모리 활용
@st.cache_resource
def get_shared_store():
    return {
        "report_data": None,
        "current_page": 0,
        "active_users": 0,
        "sync_version": 0,  # 마스터가 액션을 취할 때마다 올라가는 '신호탄'
        "last_action_time": time.time()
    }

shared_store = get_shared_store()

# 접속자 카운트
if "user_counted" not in st.session_state:
    shared_store["active_users"] += 1
    st.session_state.user_counted = True

# 3. 음성 설정 (WebRTC)
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

# --- 사이드바 영역 ---
with st.sidebar:
    st.title("🎙️ AI Action-Sync")
    
    is_master = st.toggle("🔑 보고자(Master) 권한 활성화", value=False)
    st.success(f"👥 접속 인원: **{shared_store['active_users']}명**")
    
    # [액션 1: 리셋] 클릭 시 버전업
    if st.button("시스템 전체 리셋"):
        shared_store["report_data"] = None
        shared_store["sync_version"] += 1
        st.rerun()

    st.divider()
    
    # [액션 2: 음성 시작]
    webrtc_ctx = webrtc_streamer(
        key="posco-v16-action",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": False, "audio": True},
    )
    
    # 음성 연결 상태가 바뀌면 버전업 (동기화 유도)
    if webrtc_ctx.state.playing and is_master:
        shared_store["sync_version"] += 1

    st.divider()

    if is_master:
        st.subheader("📂 마스터 컨트롤")
        # [액션 3: 업로드] 업로드 시 버전업
        uploaded_file = st.file_uploader("보고서 JSON 업로드", type=['json', 'js'])
        if uploaded_file:
            shared_store["report_data"] = json.loads(uploaded_file.read().decode("utf-8"))
            shared_store["sync_version"] += 1
            st.toast("🚀 모든 접속자 화면 동기화 완료!")
        
        edit_mode = st.toggle("📝 편집 모드", value=False)
    else:
        # ---------------------------------------------------------
        # [슬레이브 동기화 핵심] 마스터의 '액션(버전)'을 실시간 추적
        # ---------------------------------------------------------
        if "local_version" not in st.session_state:
            st.session_state.local_version = shared_store["sync_version"]
        
        # 1초마다 마스터의 sync_version이 바뀌었는지 체크
        time.sleep(1) 
        if st.session_state.local_version != shared_store["sync_version"]:
            st.session_state.local_version = shared_store["sync_version"]
            st.rerun() # 버전이 다르면 즉시 새로고침하여 화면 동기화
        
        st.info("🛰️ 보고자의 액션을 대기 중입니다...")

# 4. 리포트 본문
if shared_store["report_data"]:
    data = shared_store["report_data"]
    tab_labels = [f"P{i+1}. {p.get('tab', '')}" for i, p in enumerate(data['pages'])]
    
    if is_master:
        # [액션 4: 페이지 전환] 클릭 시 버전업
        prev_p = shared_store["current_page"]
        current_tab_idx = st.radio("📑 페이지 이동 컨트롤", range(len(tab_labels)), 
                                   format_func=lambda x: tab_labels[x], horizontal=True)
        
        if prev_p != current_tab_idx:
            shared_store["current_page"] = current_tab_idx
            shared_store["sync_version"] += 1 # 페이지 바뀔 때마다 신호 전송
    else:
        current_tab_idx = shared_store["current_page"]
        if current_tab_idx >= len(tab_labels): current_tab_idx = 0
        st.warning(f"📍 브리핑 위치: **{tab_labels[current_tab_idx]}**")

    p = data['pages'][current_tab_idx]
    st.divider()
    
    col_main, col_side = st.columns([2, 1], gap="large")
    with col_main:
        # 편집 모드에서 수정 발생 시에도 버전업
        if is_master and edit_mode:
            new_header = st.text_input("헤더", p.get('header', ''), key=f"h_{current_tab_idx}")
            if new_header != p.get('header'):
                p['header'] = new_header
                shared_store["sync_version"] += 1
            
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
                st.metric(label=m[0], value=m[1], delta=m[2] if len(m)>2 else None)
else:
    st.warning("⚠️ 보고자의 보고서 업로드를 기다리는 중입니다.")
