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
        "chat_logs": [],
        "is_voice_live": False
    }

shared_store = get_global_store()

# 3. 음성 설정 (에러 방지를 위해 타임아웃 연장 및 STUN 고정)
RTC_CONFIG = RTCConfiguration({
    "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}],
    "iceTransportPolicy": "all"
})

# --- 사이드바 영역 ---
with st.sidebar:
    st.title("🎙️ 실시간 브리핑")
    is_reporter = st.toggle("🔑 보고자 권한 활성화", value=False)
    
    # [안정화] 음성 모듈을 별도의 컨테이너에 넣어 간섭 최소화
    voice_container = st.container()
    with voice_container:
        try:
            webrtc_ctx = webrtc_streamer(
                key="posco-v-final-safe-audio",
                mode=WebRtcMode.SENDRECV,
                rtc_configuration=RTC_CONFIG,
                media_stream_constraints={"video": False, "audio": True},
                async_processing=True,
                # 세션 유지력 강화
                rtc_events=["iceconnectionstatechange"]
            )
        except Exception as e:
            st.error("음성 모듈 초기화 중... 잠시 기다려주세요.")
            webrtc_ctx = None

    if is_reporter and webrtc_ctx and webrtc_ctx.state.playing != shared_store["is_voice_live"]:
        shared_store["is_voice_live"] = webrtc_ctx.state.playing
        shared_store["sync_version"] += 1

    st.divider()
    if st.button("🚨 전체 리셋 (데이터+음성)"):
        shared_store["report_data"] = None
        shared_store["chat_logs"] = []
        shared_store["sync_version"] += 1
        st.cache_resource.clear()
        st.rerun()

    if is_reporter:
        st.subheader("📂 보고자 컨트롤")
        uploaded_file = st.file_uploader("보고서 JSON 업로드", type=['json', 'js'])
        if uploaded_file:
            content = json.loads(uploaded_file.read().decode("utf-8"))
            if shared_store["report_data"] is None:
                shared_store["report_data"] = content
                shared_store["sync_version"] += 1
        current_edit_mode = st.toggle("📝 실시간 편집 모드", value=False)

# 4. [동기화 엔진] 채팅과 본문을 묶어 음성과 격리
@st.fragment(run_every="1s")
def sync_content_area(edit_enabled):
    # 음성 알림
    if not is_reporter and shared_store["is_voice_live"]:
        st.info("🔊 **보고자의 음성 브리핑 진행 중** (사이드바 START 클릭)")

    # --- 실시간 채팅창 ---
    with st.expander("💬 실시간 채팅", expanded=True):
        c_col, i_col = st.columns([4, 1])
        with i_col:
            user_role = "📢 보고자" if is_reporter else "👤 접속자"
            chat_input = st.text_input("메시지", key="chat_in", label_visibility="collapsed")
            if st.button("전송", use_container_width=True):
                if chat_input:
                    shared_store["chat_logs"].insert(0, f"[{time.strftime('%H:%M:%S')}] **{user_role}**: {chat_input}")
                    shared_store["sync_version"] += 1
        with c_col:
            # 채팅 가독성 확보 (최신 3건)
            for log in shared_store["chat_logs"][:3]:
                st.write(log)

    if shared_store["report_data"] is None:
        st.warning("🛰️ 보고자의 업로드를 기다리는 중...")
        return

    data = shared_store["report_data"]
    tab_labels = [f"P{i+1}. {p.get('tab', '')}" for i, p in enumerate(data['pages'])]
    
    # 페이지 이동
    if is_reporter:
        prev_p = shared_store["current_page"]
        current_tab_idx = st.radio("📑 페이지 이동", range(len(tab_labels)), 
                                   index=shared_store["current_page"],
                                   format_func=lambda x: tab_labels[x], horizontal=True)
        if prev_p != current_tab_idx:
            shared_store["current_page"] = current_tab_idx
            shared_store["sync_version"] += 1
    else:
        current_tab_idx = shared_store["current_page"]
        if current_tab_idx >= len(tab_labels): current_tab_idx = 0
        st.warning(f"📍 현재 위치: **{tab_labels[current_tab_idx]}**")

    # 리포트 렌더링
    p = data['pages'][current_tab_idx]
    st.divider()
    col_main, col_side = st.columns([2, 1], gap="large")
    
    with col_main:
        if is_reporter and edit_enabled:
            p['tab'] = st.text_input("🔖 탭 이름", p.get('tab', ''), key=f"t_{current_tab_idx}")
            p['header'] = st.text_input("📌 제목", p.get('header', ''), key=f"h_{current_tab_idx}")
            p['content'] = st.text_area("📄 본문", p.get('content', ''), height=250, key=f"c_{current_tab_idx}")
            if 'img_width' not in p: p['img_width'] = 800
            p['img_width'] = st.slider("🖼️ 크기", 200, 1200, int(p['img_width']), key=f"i_{current_tab_idx}")
            shared_store["sync_version"] += 1
        
        st.markdown(f"# {p.get('header', '')}")
        if "image" in p:
            st.image(p["image"], width=int(p.get('img_width', 800)))
        for para in p.get('content', '').split('\n'):
            if para.strip(): st.markdown(f"### **{para.strip()}**")

    with col_side:
        st.subheader(p.get('metrics_title', '📊 지표'))
        if "metrics" in p:
            for idx, m in enumerate(p['metrics']):
                if is_reporter and edit_enabled:
                    m[0] = st.text_input(f"라벨{idx}", m[0], key=f"ml_{current_tab_idx}_{idx}")
                    m[1] = st.text_input(f"수치{idx}", m[1], key=f"mv_{current_tab_idx}_{idx}")
                st.metric(label=m[0], value=m[1], delta=m[2] if len(m)>2 else None)

# 실행
sync_content_area(current_edit_mode if is_reporter else False)
