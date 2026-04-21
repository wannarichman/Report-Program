import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Live Sync", layout="wide")

# 2. [전역 동기화] 세션 추적 로직 보강
@st.cache_resource
def get_global_store():
    return {
        "report_data": None,
        "current_page": 0,
        "comments": [],
        "active_users": 0,
        "session_ids": set(), # 접속한 세션 ID들을 저장하여 중복 방지
        "version": 0
    }

shared_store = get_global_store()

# [수정] 중복 카운트 방지 로직
if "browser_session_id" not in st.session_state:
    # 새로운 세션일 때만 카운트 증가
    st.session_state.browser_session_id = time.time() # 임시 세션 ID 생성
    shared_store["active_users"] += 1
    shared_store["session_ids"].add(st.session_state.browser_session_id)

# 3. 음성 설정
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

# --- 사이드바 영역 ---
with st.sidebar:
    st.title("🎙️ AI Sync Briefing")
    
    is_master = st.toggle("🔑 보고자(Master) 권한 활성화", value=False)
    
    # [개선] 접속자 수 표시 및 수동 보정 기능
    st.success(f"👥 실시간 접속: **{shared_store['active_users']}명**")
    
    col1, col2 = st.columns(2)
    if col1.button("인원 -1"): # 인원이 너무 많게 나올 때 수동으로 줄임
        shared_store["active_users"] = max(0, shared_store["active_users"] - 1)
        st.rerun()
    if col2.button("인원 초기화"): # 0명으로 리셋 (본인 접속 시 다시 1됨)
        shared_store["active_users"] = 0
        shared_store["session_ids"] = set()
        st.rerun()

    if st.button("🚨 시스템 전체 리셋"):
        shared_store["report_data"] = None
        shared_store["version"] += 1
        st.rerun()

    st.divider()
    
    webrtc_streamer(
        key="posco-master-v12",
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
            st.toast("✅ 보고서가 공유되었습니다!")
        edit_mode = st.toggle("📝 편집 모드", value=False)
    else:
        st.info("📢 마스터의 보고서를 수신 중...")
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
        current_tab_idx = shared_store["current_page"]
        st.info(f"📍 마스터가 **{tab_labels[current_tab_idx]}** 브리핑 중")

    p = data['pages'][current_tab_idx]
    st.divider()
    
    col_main, col_side = st.columns([2, 1], gap="large")
    with col_main:
        if is_master and edit_mode:
            p['header'] = st.text_input("헤더 수정", p.get('header', ''), key=f"h_{current_tab_idx}")
            p['content'] = st.text_area("본문 수정", p.get('content', ''), key=f"c_{current_tab_idx}")
            p['img_width'] = st.slider("그림 크기", 200, 1200, int(p.get('img_width', 800)), key=f"i_{current_tab_idx}")
        
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
                    m[0], m[1] = st.text_input(f"지표{idx}", m[0], key=f"ml_{idx}"), st.text_input(f"수치{idx}", m[1], key=f"mv_{idx}")
                st.metric(label=m[0], value=m[1], delta=m[2] if len(m)>2 else None)
else:
    st.warning("⚠️ 보고서 대기 중...")
