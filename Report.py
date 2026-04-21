import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Live Briefing", layout="wide")

# 2. [전역 공유 저장소]
@st.cache_resource
def get_global_store():
    return {
        "report_data": None,
        "current_page": 0,
        "active_users": 0,
        "sync_version": 0
    }

shared_store = get_global_store()

# 접속자 수 관리
if "user_counted" not in st.session_state:
    shared_store["active_users"] += 1
    st.session_state.user_counted = True

# 3. 음성 설정 (사이드바 고정으로 연결 유지)
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

with st.sidebar:
    st.title("🎙️ 실시간 브리핑")
    is_reporter = st.toggle("🔑 보고자 권한 활성화", value=False)
    st.success(f"👥 접속: **{shared_store['active_users']}명**")
    
    # 음성 스트리머 (본문 갱신과 무관하게 유지)
    webrtc_streamer(
        key="posco-v-final-audio",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": False, "audio": True},
    )

    if st.button("🚨 시스템 전체 초기화"):
        shared_store["report_data"] = None
        shared_store["sync_version"] += 1
        st.cache_resource.clear()
        st.rerun()

    if is_reporter:
        st.divider()
        st.subheader("📂 보고자 컨트롤")
        uploaded_file = st.file_uploader("보고서 JSON 업로드", type=['json', 'js'], key="report_uploader")
        
        if uploaded_file is not None:
            try:
                new_content = json.loads(uploaded_file.read().decode("utf-8"))
                if shared_store["report_data"] is None: # 처음 올릴 때만 자동 주입
                    shared_store["report_data"] = new_content
                    shared_store["sync_version"] += 1
                    st.toast("🚀 보고서 로드 완료")
            except Exception as e:
                st.error(f"파일 오류: {e}")
        
        # 편집 모드 스위치
        edit_mode = st.toggle("📝 실시간 편집 모드", value=False)

# 4. [동기화 엔진] 1초마다 본문 조각만 새로 고침
@st.fragment(run_every="1s")
def sync_content_area():
    if shared_store["report_data"] is None:
        st.info("🛰️ 보고자의 보고서 업로드를 기다리는 중입니다...")
        return

    data = shared_store["report_data"]
    tab_labels = [f"P{i+1}. {p.get('tab', '')}" for i, p in enumerate(data['pages'])]
    
    # --- 페이지 이동 및 편집 로직 ---
    if is_reporter:
        col_ctrl, col_save = st.columns([4, 1])
        with col_ctrl:
            prev_p = shared_store["current_page"]
            current_tab_idx = st.radio("📑 페이지 이동", range(len(tab_labels)), 
                                       format_func=lambda x: tab_labels[x], horizontal=True)
            if prev_p != current_tab_idx:
                shared_store["current_page"] = current_tab_idx
                shared_store["sync_version"] += 1
        
        with col_save:
            # 수정된 최종 결과물 다운로드
            st.download_button("💾 JSON 저장", json.dumps(data, indent=2, ensure_ascii=False), "updated_report.json")
    else:
        current_tab_idx = shared_store["current_page"]
        if current_tab_idx >= len(tab_labels): current_tab_idx = 0
        st.warning(f"📍 현재 브리핑 위치: **{tab_labels[current_tab_idx]}**")

    # --- 본문 출력 및 실시간 편집 ---
    p = data['pages'][current_tab_idx]
    st.divider()
    col_main, col_side = st.columns([2, 1], gap="large")
    
    with col_main:
        if is_reporter and 'edit_mode' in locals() and edit_mode:
            # 제목 수정
            new_header = st.text_input("제목 수정", p.get('header', ''), key=f"edit_h_{current_tab_idx}")
            if new_header != p.get('header'):
                p['header'] = new_header
                shared_store["sync_version"] += 1 # 수정 즉시 신호탄
            
            # 본문 수정
            new_content = st.text_area("본문 수정", p.get('content', ''), height=300, key=f"edit_c_{current_tab_idx}")
            if new_content != p.get('content'):
                p['content'] = new_content
                shared_store["sync_version"] += 1
        
        # 실제 화면 표시
        st.markdown(f"# {p.get('header', '')}")
        if "image" in p:
            st.image(p["image"], width=int(p.get('img_width', 800)))
        for para in p.get('content', '').split('\n'):
            if para.strip(): st.markdown(f"### **{para.strip()}**")

    with col_side:
        st.subheader(p.get('metrics_title', '📊 지표'))
        if "metrics" in p:
            for idx, m in enumerate(p['metrics']):
                if is_reporter and 'edit_mode' in locals() and edit_mode:
                    m[0] = st.text_input(f"라벨{idx}", m[0], key=f"ml_{current_tab_idx}_{idx}")
                    m[1] = st.text_input(f"수치{idx}", m[1], key=f"mv_{current_tab_idx}_{idx}")
                    # 지표 수정 시에도 동기화 신호
                    shared_store["sync_version"] += 1
                st.metric(label=m[0], value=m[1], delta=m[2] if len(m)>2 else None)

# 실행
sync_content_area()
