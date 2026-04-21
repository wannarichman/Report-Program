import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Live Sync", layout="wide")

# 2. [초강력 전역 동기화] singleton 패턴 적용
@st.cache_resource
def get_global_store():
    # 이 객체는 서버가 떠 있는 동안 모든 접속자가 '완벽히' 공유합니다.
    if "data_store" not in st.session_state:
        return {
            "report_data": None,
            "current_page": 0,
            "comments": [],
            "active_users": 0,
            "version": 0  # 데이터가 바뀔 때마다 올라가는 버전 번호
        }
    return st.session_state.data_store

shared_store = get_global_store()

# 접속자 수 관리
if "user_counted" not in st.session_state:
    shared_store["active_users"] += 1
    st.session_state.user_counted = True

# 3. 음성 설정 (Google STUN)
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

# --- 사이드바 영역 ---
with st.sidebar:
    st.title("🎙️ AI Sync Briefing")
    
    # [설정] 보고자(Master) 권한
    is_master = st.toggle("🔑 보고자(Master) 권한 활성화", value=False)
    st.success(f"👥 실시간 접속: **{shared_store['active_users']}명**")
    
    if st.button("전체 시스템 리셋"):
        shared_store["report_data"] = None
        shared_store["version"] += 1
        st.rerun()

    st.divider()
    
    # 음성 스트리머
    webrtc_streamer(
        key="posco-master-v11",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": False, "audio": True},
    )

    st.divider()

    if is_master:
        st.subheader("📂 마스터 컨트롤")
        uploaded_file = st.file_uploader("보고서 JSON 업로드", type=['json', 'js'])
        if uploaded_file:
            # 보고자가 업로드한 데이터를 전역에 즉시 강제 주입
            content = json.loads(uploaded_file.read().decode("utf-8"))
            shared_store["report_data"] = content
            shared_store["version"] += 1 # 버전 업으로 신호 발생
            st.toast("✅ 모든 접속자 화면에 동기화되었습니다!")
        
        edit_mode = st.toggle("📝 편집 모드", value=False)
    else:
        st.info("📢 보고자의 보고서를 수신 중입니다...")
        # [핵심] 수신자는 2초마다 버전 번호를 체크하여 다르면 새로고침
        time.sleep(2)
        st.rerun()

# 4. 리포트 본문 (동기화 렌더링)
if shared_store["report_data"]:
    data = shared_store["report_data"]
    tab_labels = [f"P{i+1}. {p.get('tab', '')}" for i, p in enumerate(data['pages'])]
    
    if is_master:
        # 마스터가 선택한 페이지 번호를 전역 저장
        current_tab_idx = st.radio("📑 페이지 이동", range(len(tab_labels)), 
                                   format_func=lambda x: tab_labels[x], horizontal=True)
        shared_store["current_page"] = current_tab_idx
    else:
        # 슬레이브는 마스터가 정한 페이지를 강제로 읽음
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
                    m[0] = st.text_input(f"지표{idx}", m[0], key=f"ml_{idx}")
                    m[1] = st.text_input(f"수치{idx}", m[1], key=f"mv_{idx}")
                st.metric(label=m[0], value=m[1], delta=m[2] if len(m)>2 else None)
else:
    st.warning("⚠️ 아직 보고서가 로드되지 않았습니다. 보고자의 업로드를 기다려주세요.")
