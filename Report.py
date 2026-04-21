import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C Super-Sync v15", layout="wide")

# 2. [전역 저장소]
@st.cache_resource
def get_shared_store():
    return {
        "report_data": None,
        "current_page": 0,
        "active_users": 0,
        "version": 0
    }

shared_store = get_shared_store()

# 접속자 카운트
if "user_counted" not in st.session_state:
    shared_store["active_users"] += 1
    st.session_state.user_counted = True

# 3. 음성 설정
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

# --- 사이드바 영역 ---
with st.sidebar:
    st.title("🎙️ AI Super-Sync")
    
    is_master = st.toggle("🔑 보고자(Master) 권한 활성화", value=False)
    st.success(f"👥 접속: **{shared_store['active_users']}명**")
    
    if st.button("시스템 전체 리셋"):
        shared_store["report_data"] = None
        shared_store["version"] += 1
        st.rerun()

    st.divider()
    
    webrtc_streamer(
        key="posco-v15-super",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": False, "audio": True},
    )

    st.divider()

    if is_master:
        st.subheader("📂 마스터 컨트롤")
        uploaded_file = st.file_uploader("보고서 JSON 업로드", type=['json', 'js'])
        if uploaded_file:
            shared_store["report_data"] = json.loads(uploaded_file.read().decode("utf-8"))
            shared_store["version"] += 1
            st.toast("✅ 즉시 동기화 활성화!")
        edit_mode = st.toggle("📝 편집 모드", value=False)
    else:
        # [핵심] 1초마다 마스터의 상태를 체크
        st.info("⚡ 보고자 화면 실시간 추적 중 (1s)")
        
        if "prev_page" not in st.session_state:
            st.session_state.prev_page = shared_store["current_page"]
        if "prev_ver" not in st.session_state:
            st.session_state.prev_ver = shared_store["version"]
        
        # 1초 대기
        time.sleep(1)
        
        # 페이지 번호나 데이터 버전이 바뀌었을 때만 새로고침하여 보이스 안정성 확보
        if (st.session_state.prev_page != shared_store["current_page"] or 
            st.session_state.prev_ver != shared_store["version"] or
            shared_store["report_data"] is None):
            
            st.session_state.prev_page = shared_store["current_page"]
            st.session_state.prev_ver = shared_store["version"]
            st.rerun()

# 4. 리포트 본문 (1:1 미러링)
if shared_store["report_data"]:
    data = shared_store["report_data"]
    tab_labels = [f"P{i+1}. {p.get('tab', '')}" for i, p in enumerate(data['pages'])]
    
    if is_master:
        # 보고자가 상단 라디오 버튼으로 페이지를 조절
        current_tab_idx = st.radio("📑 페이지 브리핑 컨트롤", range(len(tab_labels)), 
                                   format_func=lambda x: tab_labels[x], horizontal=True)
        shared_store["current_page"] = current_tab_idx
    else:
        current_tab_idx = shared_store["current_page"]
        if current_tab_idx >= len(tab_labels): current_tab_idx = 0
        st.warning(f"📍 보고자가 **{tab_labels[current_tab_idx]}** 설명 중")

    p = data['pages'][current_tab_idx]
    st.divider()
    
    col_main, col_side = st.columns([2, 1], gap="large")
    with col_main:
        if is_master and edit_mode:
            p['header'] = st.text_input("헤더", p.get('header', ''), key=f"h_{current_tab_idx}")
            p['content'] = st.text_area("본문", p.get('content', ''), height=200, key=f"c_{current_tab_idx}")
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
    st.warning("⚠️ 보고자의 보고서 업로드를 기다리는 중입니다.")
