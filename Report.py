import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json
import time

# 1. 페이지 설정 및 디자인 최적화
st.set_page_config(page_title="POSCO E&C AI Live Sync", layout="wide")

# 주요 지표(Metric) 시각적 밸런스를 위한 CSS
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #dee2e6;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. [전역 공유 저장소] 모든 기기가 이 객체를 공유하여 실시간 동기화
@st.cache_resource
def get_global_store():
    return {
        "report_data": None,
        "current_page": 0,
        "active_users": 0,
        "sync_version": 0 # 보고자의 액션 감지용 버전 번호
    }

shared_store = get_global_store()

# 접속자 수 관리 (세션 중복 방지)
if "user_counted" not in st.session_state:
    shared_store["active_users"] += 1
    st.session_state.user_counted = True

# 3. 음성 설정 (Google STUN 서버 활용)
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

# --- 사이드바: 컨트롤 및 소통 영역 ---
with st.sidebar:
    st.title("🎙️ 실시간 브리핑 시스템")
    
    # 권한 설정
    is_reporter = st.toggle("🔑 보고자 권한 활성화", value=False)
    st.success(f"👥 현재 접속: **{shared_store['active_users']}명**")
    
    # 시스템 초기화 버튼
    if st.button("🚨 데이터 전체 초기화"):
        shared_store["report_data"] = None
        shared_store["sync_version"] += 1
        st.cache_resource.clear()
        st.rerun()

    st.divider()
    
    # 음성 스트리머 (오디오 전용)
    webrtc_streamer(
        key="posco-v-final-sync",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": False, "audio": True},
    )

    st.divider()

    if is_reporter:
        st.subheader("📂 보고자 컨트롤")
        uploaded_file = st.file_uploader("보고서 JSON 업로드", type=['json', 'js'])
        
        if uploaded_file:
            try:
                # 보고자가 파일을 올리면 전역 저장소에 즉시 기록
                content = json.loads(uploaded_file.read().decode("utf-8"))
                shared_store["report_data"] = content
                shared_store["sync_version"] += 1 # 동기화 신호 발생
                st.toast("🚀 모든 접속자에게 보고서가 송출되었습니다.")
            except:
                st.error("파일 형식 오류")
        
        edit_mode = st.toggle("📝 편집 모드 활성화", value=False)
    else:
        # [보고받는 자 핵심 로직] 1초마다 보고자의 액션(버전) 변화 감지
        if "local_ver" not in st.session_state:
            st.session_state.local_ver = shared_store["sync_version"]
        
        time.sleep(1) # 1초 대기
        
        # 보고자가 무언가 클릭하여 버전이 바뀌었다면 즉시 새로고침
        if st.session_state.local_ver != shared_store["sync_version"]:
            st.session_state.local_ver = shared_store["sync_version"]
            st.rerun()
        
        st.info("🛰️ 보고자의 브리핑을 수신 대기 중...")

# 4. 리포트 본문 렌더링 (전역 데이터 기반)
if shared_store["report_data"] is not None:
    data = shared_store["report_data"]
    tab_labels = [f"P{i+1}. {p.get('tab', '')}" for i, p in enumerate(data['pages'])]
    
    if is_reporter:
        # 보고자가 페이지를 전환하면 즉시 동기화 신호 발생
        prev_p = shared_store["current_page"]
        current_tab_idx = st.radio("📑 페이지 이동 컨트롤", range(len(tab_labels)), 
                                   format_func=lambda x: tab_labels[x], horizontal=True)
        if prev_p != current_tab_idx:
            shared_store["current_page"] = current_tab_idx
            shared_store["sync_version"] += 1
    else:
        # 보고받는 자는 보고자가 선택한 페이지로 자동 고정
        current_tab_idx = shared_store["current_page"]
        if current_tab_idx >= len(tab_labels): current_tab_idx = 0
        st.warning(f"📍 현재 브리핑 위치: **{tab_labels[current_tab_idx]}**")

    # 실제 컨텐츠 표시 영역
    p = data['pages'][current_tab_idx]
    st.divider()
    
    # 좌우 밸런스 2:1 레이아웃
    col_main, col_side = st.columns([2, 1], gap="large")
    
    with col_main:
        if is_reporter and edit_mode:
            p['header'] = st.text_input("헤더 수정", p.get('header', ''), key=f"h_{current_tab_idx}")
            p['content'] = st.text_area("본문 수정", p.get('content', ''), key=f"c_{current_tab_idx}")
            p['img_width'] = st.slider("그림 크기", 200, 1200, int(p.get('img_width', 800)), key=f"i_{current_tab_idx}")
            # 수정 시에도 버전업을 원하면 여기에 shared_store["sync_version"] += 1 추가 가능
        
        st.markdown(f"# {p.get('header', '')}")
        if "image" in p:
            st.image(p["image"], width=int(p.get('img_width', 800)))
        
        # 가독성 높은 본문 출력
        for para in p.get('content', '').split('\n'):
            if para.strip(): 
                st.markdown(f"### **{para.strip()}**")

    with col_side:
        st.subheader(p.get('metrics_title', '📊 주요 지표'))
        if "metrics" in p:
            for idx, m in enumerate(p['metrics']):
                if is_reporter and edit_mode:
                    m[0], m[1] = st.text_input(f"L{idx}", m[0], key=f"l_{idx}"), st.text_input(f"V{idx}", m[1], key=f"v_{idx}")
                st.metric(label=m[0], value=m[1], delta=m[2] if len(m)>2 else None)
    
    if is_reporter and edit_mode:
        st.download_button("💾 수정본 저장", json.dumps(data, indent=2, ensure_ascii=False), "final_report.json")
else:
    # 초기 대기 화면
    st.warning("⚠️ 보고서가 로드되지 않았습니다. 보고자(PC)가 파일을 업로드해 주세요.")
    st.info("보고받는 자는 링크 접속 후 대기하시면 보고자가 파일을 올리는 순간 화면이 자동 동기화됩니다.")
