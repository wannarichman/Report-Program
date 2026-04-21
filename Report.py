import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Live Sync", layout="wide")

# 2. [전역 저장소] 초기 상태를 None으로 엄격히 제한
@st.cache_resource
def get_shared_store():
    return {
        "report_data": None,  # 처음엔 무조건 비어있어야 함
        "current_page": 0,
        "active_users": 0,
        "sync_version": 0
    }

shared_store = get_shared_store()

# 접속자 카운트 (중복 방지)
if "user_counted" not in st.session_state:
    shared_store["active_users"] += 1
    st.session_state.user_counted = True

# 3. 음성 설정
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

# --- 사이드바 영역 ---
with st.sidebar:
    st.title("🎙️ AI Action-Sync")
    
    is_master = st.toggle("🔑 보고자(Master) 권한 활성화", value=False)
    st.success(f"👥 접속 인원: **{shared_store['active_users']}명**")
    
    # [강력 리셋] 버튼 클릭 시 전역 데이터를 즉시 삭제
    if st.button("🚨 데이터 초기화 (Clean Start)"):
        shared_store["report_data"] = None
        shared_store["sync_version"] += 1
        st.cache_resource.clear() # 캐시 자체를 강제 삭제
        st.rerun()

    st.divider()
    
    webrtc_ctx = webrtc_streamer(
        key="posco-v17-clean",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": False, "audio": True},
    )

    st.divider()

    if is_master:
        st.subheader("📂 마스터 컨트롤")
        uploaded_file = st.file_uploader("보고서 JSON 업로드", type=['json', 'js'], key="report_uploader")
        
        # 파일이 업로드된 '순간'에만 데이터를 전역에 주입
        if uploaded_file is not None:
            try:
                content = json.loads(uploaded_file.read().decode("utf-8"))
                shared_store["report_data"] = content
                shared_store["sync_version"] += 1
                st.success("✅ 새 보고서가 로드되었습니다.")
            except:
                st.error("파일 형식 오류")
        
        edit_mode = st.toggle("📝 편집 모드", value=False)
    else:
        # 슬레이브 동기화 로직 (1초 주기)
        if "local_version" not in st.session_state:
            st.session_state.local_version = shared_store["sync_version"]
        
        time.sleep(1)
        if st.session_state.local_version != shared_store["sync_version"]:
            st.session_state.local_version = shared_store["sync_version"]
            st.rerun()
        
        st.info("🛰️ 보고자의 보고서 업로드를 기다리는 중...")

# 4. 리포트 본문 (데이터가 있을 때만 렌더링)
if shared_store["report_data"] is not None:
    data = shared_store["report_data"]
    tab_labels = [f"P{i+1}. {p.get('tab', '')}" for i, p in enumerate(data['pages'])]
    
    if is_master:
        prev_p = shared_store["current_page"]
        current_tab_idx = st.radio("📑 페이지 이동 컨트롤", range(len(tab_labels)), 
                                   format_func=lambda x: tab_labels[x], horizontal=True)
        if prev_p != current_tab_idx:
            shared_store["current_page"] = current_tab_idx
            shared_store["sync_version"] += 1
    else:
        current_tab_idx = shared_store["current_page"]
        if current_tab_idx >= len(tab_labels): current_tab_idx = 0
        st.warning(f"📍 브리핑 위치: **{tab_labels[current_tab_idx]}**")

    p = data['pages'][current_tab_idx]
    st.divider()
    
    col_main, col_side = st.columns([2, 1], gap="large")
    with col_main:
        st.markdown(f"# {p.get('header', '')}")
        if "image" in p:
            # 밸런스 조정을 위해 img_width 기본값 적용
            st.image(p["image"], width=int(p.get('img_width', 800)))
        
        for para in p.get('content', '').split('\n'):
            if para.strip(): st.markdown(f"### **{para.strip()}**")

    with col_side:
        st.subheader(p.get('metrics_title', '📊 지표'))
        if "metrics" in p:
            for idx, m in enumerate(p['metrics']):
                st.metric(label=m[0], value=m[1], delta=m[2] if len(m)>2 else None)
else:
    # 데이터가 없을 때는 깨끗한 대기 화면만 표시
    st.markdown("### 📋 보고 대기 중")
    st.write("보고자가 보고서 파일을 업로드하면 실시간 브리핑이 시작됩니다.")
    st.image("https://via.placeholder.com/800x400.png?text=Waiting+for+Master+Upload...", use_column_width=True)
