import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Live Sync", layout="wide")

# 2. [전역 공유 저장소]
@st.cache_resource
def get_global_store():
    return {
        "report_data": None,
        "current_page": 0,
        "active_users": 0,
        "sync_version": 0,
        "is_voice_live": False
    }

shared_store = get_global_store()

if "user_counted" not in st.session_state:
    shared_store["active_users"] += 1
    st.session_state.user_counted = True

# 3. 음성 설정
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

with st.sidebar:
    st.title("🎙️ 실시간 브리핑")
    is_reporter = st.toggle("🔑 보고자 권한 활성화", value=False)
    st.success(f"👥 접속: **{shared_store['active_users']}명**")
    
    webrtc_ctx = webrtc_streamer(
        key="posco-v-final-audio-v5",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": False, "audio": True},
    )

    if is_reporter:
        if webrtc_ctx.state.playing != shared_store["is_voice_live"]:
            shared_store["is_voice_live"] = webrtc_ctx.state.playing
            shared_store["sync_version"] += 1

    if st.button("🚨 시스템 전체 초기화"):
        shared_store["report_data"] = None
        shared_store["is_voice_live"] = False
        shared_store["sync_version"] += 1
        st.cache_resource.clear()
        st.rerun()

    current_edit_mode = False
    if is_reporter:
        st.divider()
        st.subheader("📂 보고자 컨트롤")
        uploaded_file = st.file_uploader("보고서 JSON 업로드", type=['json', 'js'], key="report_uploader")
        if uploaded_file:
            try:
                new_content = json.loads(uploaded_file.read().decode("utf-8"))
                if shared_store["report_data"] is None:
                    shared_store["report_data"] = new_content
                    shared_store["sync_version"] += 1
            except: st.error("파일 오류")
        current_edit_mode = st.toggle("📝 실시간 편집 모드", value=False)

# 4. [동기화 엔진]
@st.fragment(run_every="1s")
def sync_content_area(edit_enabled):
    # 음성 알림 로직
    if not is_reporter and shared_store["is_voice_live"]:
        if "voice_notified" not in st.session_state or not st.session_state.voice_notified:
            st.toast("📢 보고자가 음성 브리핑을 시작했습니다!")
            st.session_state.voice_notified = True
        st.info("🔊 **보고자의 음성 브리핑이 진행 중입니다.** 왼쪽 사이드바의 [START]를 눌러 합류하세요.")
    elif not shared_store["is_voice_live"]:
        st.session_state.voice_notified = False

    if shared_store["report_data"] is None:
        st.info("🛰️ 보고자의 보고서 업로드를 기다리는 중입니다...")
        return

    data = shared_store["report_data"]
    tab_labels = [f"P{i+1}. {p.get('tab', '')}" for i, p in enumerate(data['pages'])]
    
    if is_reporter:
        col_ctrl, col_save = st.columns([4, 1])
        with col_ctrl:
            prev_p = shared_store["current_page"]
            current_tab_idx = st.radio("📑 페이지 이동", range(len(tab_labels)), 
                                       index=shared_store["current_page"],
                                       format_func=lambda x: tab_labels[x], horizontal=True)
            if prev_p != current_tab_idx:
                shared_store["current_page"] = current_tab_idx
                shared_store["sync_version"] += 1
        with col_save:
            st.download_button("💾 JSON 저장", json.dumps(data, indent=2, ensure_ascii=False), "updated_report.json")
    else:
        current_tab_idx = shared_store["current_page"]
        if current_tab_idx >= len(tab_labels): current_tab_idx = 0
        st.warning(f"📍 현재 브리핑 위치: **{tab_labels[current_tab_idx]}**")

    # --- 본문 및 편집 영역 ---
    p = data['pages'][current_tab_idx]
    st.divider()
    col_main, col_side = st.columns([2, 1], gap="large")
    
    with col_main:
        if is_reporter and edit_enabled:
            # [핵심 수정] 모든 편집 위젯의 key에 current_tab_idx를 포함시켜 페이지 전환 시 강제 리셋
            new_tab = st.text_input("🔖 탭 이름 수정", p.get('tab', ''), key=f"t_{current_tab_idx}")
            new_header = st.text_input("📌 제목 수정", p.get('header', ''), key=f"h_{current_tab_idx}")
            new_content = st.text_area("📄 본문 수정", p.get('content', ''), height=250, key=f"c_{current_tab_idx}")
            
            if 'img_width' not in p: p['img_width'] = 800
            new_width = st.slider("🖼️ 그림 크기 조절", 200, 1200, int(p['img_width']), key=f"i_{current_tab_idx}")
            
            # 값 변경 시에만 데이터 업데이트 및 버전업
            if (new_tab != p.get('tab') or new_header != p.get('header') or 
                new_content != p.get('content') or new_width != p.get('img_width')):
                p['tab'], p['header'], p['content'], p['img_width'] = new_tab, new_header, new_content, new_width
                shared_store["sync_version"] += 1
        
        st.markdown(f"# {p.get('header', '')}")
        if "image" in p:
            st.image(p["image"], width=int(p.get('img_width', 800)))
        for para in p.get('content', '').split('\n'):
            if para.strip(): st.markdown(f"### **{para.strip()}**")

    with col_side:
        if 'metrics_title' not in p: p['metrics_title'] = "📊 주요 지표"
        if is_reporter and edit_enabled:
            p['metrics_title'] = st.text_input("📊 지표 섹션 제목", p['metrics_title'], key=f"mt_{current_tab_idx}")
        
        st.subheader(p['metrics_title'])
        if "metrics" in p:
            for idx, m in enumerate(p['metrics']):
                if is_reporter and edit_enabled:
                    m[0] = st.text_input(f"항목{idx}", m[0], key=f"ml_{current_tab_idx}_{idx}")
                    m[1] = st.text_input(f"수치{idx}", m[1], key=f"mv_{current_tab_idx}_{idx}")
                st.metric(label=m[0], value=m[1], delta=m[2] if len(m)>2 else None)

# 실행
sync_content_area(current_edit_mode if is_reporter else False)
