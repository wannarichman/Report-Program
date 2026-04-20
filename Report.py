import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json
import time

# 1. 페이지 설정 및 가독성 스타일
st.set_page_config(page_title="POSCO E&C AI Live Sync", layout="wide")

# 2. [핵심] 전역 동기화 저장소 (모든 사용자가 이 데이터를 공유함)
@st.cache_resource
def get_global_store():
    return {"comments": [], "is_briefing": False}

shared_store = get_global_store()

# 3. 음성 설정을 위한 Secrets 로드 (보안 강화)
def get_ice_servers():
    try:
        import requests
        TWILIO_SID = st.secrets["TWILIO_ACCOUNT_SID"]
        TWILIO_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
        response = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Tokens.json",
            auth=(TWILIO_SID, TWILIO_TOKEN), timeout=3
        )
        if response.status_code == 201:
            return response.json()["ice_servers"]
    except:
        pass
    return [{"urls": ["stun:stun.l.google.com:19302"]}]

RTC_CONFIG = RTCConfiguration({"iceServers": get_ice_servers()})

with st.sidebar:
    st.title("🎙️ Voice Briefing")
    
    # 음성 스트리머 및 상태 표시
    webrtc_ctx = webrtc_streamer(
        key="posco-voice-final-v4",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": False, "audio": True},
    )

    if webrtc_ctx.state.playing:
        st.success("✅ 음성 브리핑 송출/수신 중")
    else:
        st.info("💡 'START'를 눌러 음성 세션에 참여하세요.")

    st.divider()
    st.subheader("💬 실시간 기술 검토 의견")
    
    # [동기화] 댓글 시스템
    with st.form("comment_form", clear_on_submit=True):
        new_comment = st.text_input("의견 입력 (모든 접속자에게 공유됨)")
        submit = st.form_submit_button("전송")
        if submit and new_comment:
            timestamp = time.strftime('%H:%M:%S')
            shared_store["comments"].insert(0, f"[{timestamp}] {new_comment}")
            st.rerun()

    for c in shared_store["comments"][:5]:
        st.caption(c)

    if st.button("🔄 화면 강제 새로고침"):
        st.rerun()

    st.divider()
    uploaded_file = st.file_uploader("JSON 보고서 로드", type=['json', 'js'])
    edit_mode = st.toggle("📝 전체 편집 모드 활성화", value=False)

# 4. 데이터 렌더링 및 편집 로직
if uploaded_file and "data" not in st.session_state:
    try:
        st.session_state.data = json.loads(uploaded_file.read().decode("utf-8"))
    except:
        st.error("데이터 로드 실패")

if "data" in st.session_state:
    data = st.session_state.data
    
    # 리포트 전체 제목 편집
    if edit_mode:
        data['title'] = st.text_input("리포트 전체 제목 수정", data['title'])
    st.title(data.get('title', 'AI R&D Report'))
    st.divider()

    # 탭 이름 편집 및 생성
    tab_titles = []
    for i, p in enumerate(data['pages']):
        if edit_mode:
            p['tab'] = st.text_input(f"P{i+1} 탭 제목 수정", p.get('tab', ''), key=f"tab_edit_{i}")
        tab_titles.append(f"P{i+1}. {p.get('tab', '')}")

    tabs = st.tabs(tab_titles)

    for i, tab in enumerate(tabs):
        with tab:
            p = data['pages'][i]
            col_main, col_side = st.columns([1.6, 1])
            
            with col_main:
                if edit_mode:
                    p['header'] = st.text_input(f"P{i+1} 헤더 수정", p.get('header', ''), key=f"h_{i}")
                    p['content'] = st.text_area(f"P{i+1} 본문 수정", p.get('content', ''), height=200, key=f"c_{i}")
                
                st.markdown(f"## {p.get('header', '')}")
                if "image" in p:
                    st.image(p["image"], use_container_width=True)
                
                # 본문 가독성 강화 출력
                for para in p.get('content', '').split('\n'):
                    if para.strip():
                        st.markdown(f"### **{para.strip()}**")
                
                if shared_store["comments"]:
                    st.warning(f"🗨️ **실시간 피드백:** {shared_store['comments'][0]}")

            with col_side:
                if 'metrics_title' not in p: p['metrics_title'] = "📊 주요 지표"
                if edit_mode:
                    p['metrics_title'] = st.text_input(f"지표 제목 수정", p['metrics_title'], key=f"mt_{i}")
                st.subheader(p['metrics_title'])

                if "metrics" in p:
                    for idx, m in enumerate(p['metrics']):
                        if edit_mode:
                            m[0] = st.text_input(f"항목{idx}", m[0], key=f"m_lab_{i}_{idx}")
                            m[1] = st.text_input(f"수치{idx}", m[1], key=f"m_val_{i}_{idx}")
                            m[2] = st.text_input(f"상태{idx}", m[2], key=f"m_det_{i}_{idx}")
                        st.metric(label=m[0], value=m[1], delta=m[2])

    if edit_mode:
        st.divider()
        st.download_button("수정된 JSON 저장", json.dumps(data, indent=2, ensure_ascii=False), "final_report.json")
else:
    st.info("왼쪽 사이드바에서 파일을 업로드하세요.")
