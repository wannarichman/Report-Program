import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Live Sync", layout="wide")

# 2. 전역 동기화 저장소 (모든 데이터 공유)
@st.cache_resource
def get_global_store():
    return {
        "comments": [], 
        "active_users": 0, 
        "report_data": None,  # 보고자가 업로드한 데이터가 여기에 저장됨
        "last_sync": time.time()
    }

shared_store = get_global_store()

# 접속자 수 관리
if "session_counted" not in st.session_state:
    shared_store["active_users"] += 1
    st.session_state.session_counted = True

# 3. 음성 설정 (Twilio/Google STUN)
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
    st.title("🎙️ Live Briefing")
    
    # [기능] 접속 현황 및 리셋
    col1, col2 = st.columns([2, 1])
    col1.success(f"👥 접속: **{shared_store['active_users']}명**")
    if col2.button("Reset"):
        shared_store["active_users"] = 1
        shared_store["report_data"] = None
        st.rerun()

    st.divider()

    # [기능] 음성 스트리머 (보이스 송출 바 포함)
    webrtc_ctx = webrtc_streamer(
        key="posco-voice-sync-v6",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": False, "audio": True},
    )

    if webrtc_ctx.state.playing:
        st.write("🔊 **보이스 송출/수신 중**")
        st.progress(0.85)
    else:
        st.write("🔇 음성 참여 대기 중")
        st.progress(0)

    st.divider()
    
    # [기능] 실시간 댓글 동기화
    st.subheader("💬 실시간 의견")
    with st.form("comment_form", clear_on_submit=True):
        new_comment = st.text_input("의견 입력")
        if st.form_submit_button("전송"):
            if new_comment:
                shared_store["comments"].insert(0, f"[{time.strftime('%H:%M:%S')}] {new_comment}")
                shared_store["last_sync"] = time.time()
                st.rerun()

    for c in shared_store["comments"][:3]:
        st.caption(c)

    st.divider()
    
    # [중요] 보고자만 파일을 업로드 (업로드 시 전역 공유됨)
    st.subheader("📂 보고서 컨트롤")
    uploaded_file = st.file_uploader("보고서 업로드 (보고자용)", type=['json', 'js'])
    if uploaded_file:
        try:
            shared_store["report_data"] = json.loads(uploaded_file.read().decode("utf-8"))
            shared_store["last_sync"] = time.time()
        except:
            st.error("파일 로드 실패")

    edit_mode = st.toggle("📝 편집 모드 활성화", value=False)

    # 5초마다 데이터 동기화 확인 (마이크 유지형)
    if time.time() - shared_store["last_sync"] > 5:
        st.rerun()

# 4. 리포트 본문 (전역 데이터 기반 렌더링)
# 보고받는 자는 파일을 안 올려도 shared_store["report_data"]가 있으면 화면이 뜹니다.
if shared_store["report_data"]:
    data = shared_store["report_data"]
    
    if edit_mode:
        data['title'] = st.text_input("리포트 전체 제목 수정", data.get('title', ''))
    st.title(data.get('title', 'AI R&D Report'))
    st.divider()

    tabs = st.tabs([f"P{i+1}. {p.get('tab', '')}" for i, p in enumerate(data['pages'])])
    for i, tab in enumerate(tabs):
        with tab:
            p = data['pages'][i]
            col_main, col_side = st.columns([1.6, 1])
            with col_main:
                if edit_mode:
                    p['header'] = st.text_input(f"P{i+1} 헤더", p.get('header', ''), key=f"h_{i}")
                    p['content'] = st.text_area(f"P{i+1} 본문", p.get('content', ''), key=f"c_{i}")
                
                st.markdown(f"## {p.get('header', '')}")
                if "image" in p:
                    st.image(p["image"], use_container_width=True)
                
                for para in p.get('content', '').split('\n'):
                    if para.strip():
                        st.markdown(f"### **{para.strip()}**")
                
                if shared_store["comments"]:
                    st.warning(f"🗨️ **실시간 피드백:** {shared_store['comments'][0]}")

            with col_side:
                st.subheader(p.get('metrics_title', '📊 지표'))
                if "metrics" in p:
                    for idx, m in enumerate(p['metrics']):
                        if edit_mode:
                            m[0], m[1], m[2] = st.text_input(f"명칭{idx}", m[0], key=f"ml_{i}_{idx}"), st.text_input(f"수치{idx}", m[1], key=f"mv_{i}_{idx}"), st.text_input(f"상태{idx}", m[2], key=f"md_{i}_{idx}")
                        st.metric(label=m[0], value=m[1], delta=m[2])
    
    if edit_mode:
        st.download_button("수정본 저장", json.dumps(data, indent=2, ensure_ascii=False), "final_report.json")
else:
    st.info("📢 보고자가 파일을 업로드할 때까지 대기 중입니다. 접속 인원을 확인하세요.")
