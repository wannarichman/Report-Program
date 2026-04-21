import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Live Briefing", layout="wide")

# 2. [강력한 전역 동기화] 데이터 구조 보강
@st.cache_resource
def get_global_store():
    return {
        "comments": [], 
        "active_users": 0, 
        "report_data": None,  # 여기에 데이터가 들어가야 함
        "current_page": 0,
        "sync_trigger": 0     # 데이터 변경을 알리는 신호
    }

shared_store = get_global_store()

if "session_counted" not in st.session_state:
    shared_store["active_users"] += 1
    st.session_state.session_counted = True

# 3. 음성 설정 (Google STUN)
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

# --- 사이드바 영역 ---
with st.sidebar:
    st.title("🎙️ AI Briefing")
    
    # [설정] 보고자(Master) 권한
    is_master = st.toggle("🔑 보고자(Master) 권한 활성화", value=False)
    
    st.success(f"👥 접속: **{shared_store['active_users']}명**")
    if st.button("Reset"):
        shared_store["active_users"], shared_store["report_data"] = 1, None
        st.rerun()

    st.divider()

    # 음성 스트리머
    webrtc_streamer(
        key="posco-master-sync-v10",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": False, "audio": True},
    )

    st.divider()
    
    if is_master:
        st.subheader("📂 마스터 컨트롤")
        uploaded_file = st.file_uploader("보고서 JSON 업로드", type=['json', 'js'])
        if uploaded_file:
            # 보고자가 업로드한 데이터를 전역 저장소에 즉시 반영
            new_data = json.loads(uploaded_file.read().decode("utf-8"))
            shared_store["report_data"] = new_data
            shared_store["sync_trigger"] += 1 # 동기화 신호 발생
            st.toast("보고서가 모든 접속자에게 공유되었습니다!")
        
        edit_mode = st.toggle("📝 편집 모드", value=False)
    else:
        st.info("📢 마스터의 보고서를 수신 대기 중...")
        # [핵심] 보고받는 자는 2초마다 데이터를 확인하기 위해 자동 새로고침
        time.sleep(2)
        st.rerun()

# 4. 리포트 본문 (동기화 렌더링)
if shared_store["report_data"]:
    data = shared_store["report_data"]
    
    # 페이지 이동 동기화
    tab_labels = [f"P{i+1}. {p.get('tab', '')}" for i, p in enumerate(data['pages'])]
    
    if is_master:
        # 마스터가 선택한 페이지 번호를 전역 저장
        current_tab_idx = st.radio("📑 페이지 컨트롤", range(len(tab_labels)), 
                                   format_func=lambda x: tab_labels[x], horizontal=True)
        shared_store["current_page"] = current_tab_idx
    else:
        current_tab_idx = shared_store["current_page"]
        # 슬레이브 화면에 현재 페이지 강제 적용
        st.info(f"📍 현재 브리핑 중: **{tab_labels[current_tab_idx]}**")

    # 컨텐츠 표시
    p = data['pages'][current_tab_idx]
    st.divider()
    
    col_main, col_side = st.columns([2, 1], gap="large")
    with col_main:
        if is_master and edit_mode:
            p['header'] = st.text_input("헤더 수정", p.get('header', ''), key=f"he_{current_tab_idx}")
            p['content'] = st.text_area("본문 수정", p.get('content', ''), key=f"ce_{current_tab_idx}")
            p['img_width'] = st.slider("그림 크기", 200, 1200, int(p.get('img_width', 800)), key=f"ie_{current_tab_idx}")
        
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
    
    if is_master and edit_mode:
        st.download_button("💾 수정본 저장", json.dumps(data, indent=2, ensure_ascii=False), "final.json")
else:
    # 데이터가 없을 때의 화면
    st.warning("⚠️ 아직 보고서가 업로드되지 않았습니다.")
    st.write("보고자(PC)에서 파일을 업로드하면 이 화면이 자동으로 보고서로 전환됩니다.")
