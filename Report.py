import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C Master-Sync Remote", layout="wide")

# 2. [전역 동기화] 보고자 주도권 데이터 추가
@st.cache_resource
def get_global_store():
    return {
        "comments": [], 
        "active_users": 0, 
        "report_data": None,
        "current_page": 0,  # 보고자가 보고 있는 페이지 번호
        "last_update_time": time.time()
    }

shared_store = get_global_store()

if "session_counted" not in st.session_state:
    shared_store["active_users"] += 1
    st.session_state.session_counted = True

# 3. 음성 설정 (보안망 대응)
def get_ice_servers():
    try:
        import requests
        TWILIO_SID = st.secrets["TWILIO_ACCOUNT_SID"]
        TWILIO_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
        response = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Tokens.json",
            auth=(TWILIO_SID, TWILIO_TOKEN), timeout=3
        )
        if response.status_code == 201: return response.json()["ice_servers"]
    except: pass
    return [{"urls": ["stun:stun.l.google.com:19302"]}]

RTC_CONFIG = RTCConfiguration({"iceServers": get_ice_servers()})

# --- 사이드바 영역 ---
with st.sidebar:
    st.title("🎙️ AI Sync Briefing")
    
    # [마스터 설정] 보고자 여부 체크
    is_master = st.toggle("🔑 보고자(Master) 권한 활성화", value=False)
    
    col1, col2 = st.columns([2, 1])
    col1.success(f"👥 접속: **{shared_store['active_users']}명**")
    if col2.button("Reset"):
        shared_store["active_users"] = 1
        shared_store["report_data"] = None
        st.rerun()

    st.divider()

    # 음성 스트리머 (기존 기능 유지)
    webrtc_ctx = webrtc_streamer(
        key="posco-master-sync-v9",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": False, "audio": True},
    )

    st.divider()
    st.subheader("💬 실시간 의견")
    with st.form("comment_form", clear_on_submit=True):
        new_comment = st.text_input("의견 입력")
        if st.form_submit_button("전송"):
            if new_comment:
                shared_store["comments"].insert(0, f"[{time.strftime('%H:%M:%S')}] {new_comment}")
                shared_store["last_update_time"] = time.time()
                st.rerun()

    st.divider()
    if is_master:
        uploaded_file = st.file_uploader("보고서 업로드 (Master Only)", type=['json', 'js'])
        if uploaded_file:
            shared_store["report_data"] = json.loads(uploaded_file.read().decode("utf-8"))
            shared_store["last_update_time"] = time.time()
        edit_mode = st.toggle("📝 편집 모드", value=False)
    else:
        st.info("📢 보고자(Master)의 화면을 추적 중입니다.")
        edit_mode = False

    # [핵심] 2초마다 자동 동기화 체크 (마이크 끊김 방지를 위해 최적화)
    # 보고받는 자 화면만 주기적으로 리프레시
    if not is_master:
        time.sleep(2)
        st.rerun()

# 4. 리포트 본문 (페이지 동기화 로직)
if shared_store["report_data"]:
    data = shared_store["report_data"]
    st.title(data.get('title', 'AI R&D Report'))
    
    tab_labels = [f"P{i+1}. {p.get('tab', '')}" for i, p in enumerate(data['pages'])]
    
    # [동기화 핵심] 
    # 보고자는 탭을 자유롭게 선택하고, 그 인덱스를 shared_store에 저장
    # 보고받는 자는 shared_store에 저장된 인덱스로 강제 고정
    if is_master:
        current_tab_idx = st.radio("📑 페이지 이동 컨트롤", range(len(tab_labels)), 
                                   format_func=lambda x: tab_labels[x], horizontal=True)
        shared_store["current_page"] = current_tab_idx
    else:
        current_tab_idx = shared_store["current_page"]
        st.info(f"📍 현재 보고자가 **{tab_labels[current_tab_idx]}** 페이지를 브리핑 중입니다.")

    # 실제 컨텐츠 렌더링 (선택된 탭만 표시)
    p = data['pages'][current_tab_idx]
    st.divider()
    
    col_main, col_side = st.columns([2, 1], gap="large")
    
    with col_main:
        if edit_mode and is_master:
            p['header'] = st.text_input(f"📌 헤더 수정", p.get('header', ''))
            p['content'] = st.text_area(f"📄 본문 수정", p.get('content', ''), height=200)
            if 'img_width' not in p: p['img_width'] = 800
            p['img_width'] = st.slider(f"🖼️ 그림 크기", 200, 1200, int(p['img_width']))
        
        st.markdown(f"## {p.get('header', '')}")
        if "image" in p:
            st.image(p["image"], width=p.get('img_width', 800))
        
        for para in p.get('content', '').split('\n'):
            if para.strip(): st.markdown(f"### **{para.strip()}**")
        
        if shared_store["comments"]:
            st.warning(f"🗨️ **실시간 피드백:** {shared_store['comments'][0]}")

    with col_side:
        if 'metrics_title' not in p: p['metrics_title'] = "📊 주요 지표"
        st.subheader(p['metrics_title'])
        if "metrics" in p:
            for idx, m in enumerate(p['metrics']):
                if edit_mode and is_master:
                    m[0] = st.text_input(f"지표{idx}", m[0], key=f"ml_{idx}")
                    m[1] = st.text_input(f"수치{idx}", m[1], key=f"mv_{idx}")
                st.metric(label=m[0], value=m[1], delta=m[2] if len(m)>2 else None)
    
    if edit_mode and is_master:
        st.download_button("💾 수정본 저장", json.dumps(data, indent=2, ensure_ascii=False), "sync_report.json")
else:
    st.info("📢 마스터가 보고서를 로드할 때까지 대기 중입니다.")
