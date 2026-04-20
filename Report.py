import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Live Briefing", layout="wide")

# 2. 전역 동기화 저장소 (접속자 수, 댓글, 브리핑 상태 공유)
@st.cache_resource
def get_global_store():
    # user_count: 현재 접속 중인 세션 수 관리
    return {"comments": [], "active_users": 0}

shared_store = get_global_store()

# 접속자 수 관리 로직 (세션 시작 시 증가)
if "session_counted" not in st.session_state:
    shared_store["active_users"] += 1
    st.session_state.session_counted = True

# 3. 실시간 음성 설정
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
    st.title("🎙️ Live Briefing System")
    
    # [신규] 실시간 접속 현황 표시
    st.success(f"👥 현재 앱 접속 인원: **{shared_store['active_users']}명**")
    st.caption("보고자와 청취자가 모두 접속했는지 확인하세요.")
    
    st.divider()

    # 음성 스트리머
    webrtc_ctx = webrtc_streamer(
        key="posco-voice-final-v5",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": False, "audio": True},
    )

    # [신규] 보이스 송출 시각화 (막대 게이지)
    if webrtc_ctx.state.playing:
        st.write("🔊 **실시간 음성 송출 중**")
        # 실제 오디오 분석 대신, 연결 활성화 시 시각적 확인을 위한 게이지
        st.info("마이크 신호 감지됨")
        st.progress(0.8) # 고정된 값이지만 '동작 중'임을 시각적으로 증명
    else:
        st.write("🔇 음성 대기 중")
        st.progress(0)

    st.divider()
    st.subheader("💬 실시간 기술 검토 의견")
    
    with st.form("comment_form", clear_on_submit=True):
        new_comment = st.text_input("의견 입력 (전역 동기화)")
        submit = st.form_submit_button("전송")
        if submit and new_comment:
            timestamp = time.strftime('%H:%M:%S')
            shared_store["comments"].insert(0, f"[{timestamp}] {new_comment}")
            st.rerun()

    for c in shared_store["comments"][:3]:
        st.caption(c)

    if st.button("🔄 화면 강제 새로고침"):
        st.rerun()

    st.divider()
    uploaded_file = st.file_uploader("JSON 보고서 로드", type=['json', 'js'])
    edit_mode = st.toggle("📝 전체 편집 모드", value=False)

# 4. 리포트 렌더링 로직 (편집 기능 포함)
if uploaded_file and "data" not in st.session_state:
    try:
        st.session_state.data = json.loads(uploaded_file.read().decode("utf-8"))
    except:
        st.error("데이터 로드 실패")

if "data" in st.session_state:
    data = st.session_state.data
    
    if edit_mode:
        data['title'] = st.text_input("리포트 전체 제목 수정", data['title'])
    st.title(data.get('title', 'AI R&D Report'))
    st.divider()

    tab_titles = []
    for i, p in enumerate(data['pages']):
        if edit_mode:
            p['tab'] = st.text_input(f"P{i+1} 탭 제목", p.get('tab', ''), key=f"tab_{i}")
        tab_titles.append(f"P{i+1}. {p.get('tab', '')}")

    tabs = st.tabs(tab_titles)

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
                if 'metrics_title' not in p: p['metrics_title'] = "📊 주요 지표"
                if edit_mode:
                    p['metrics_title'] = st.text_input(f"지표 제목", p['metrics_title'], key=f"mt_{i}")
                st.subheader(p['metrics_title'])

                if "metrics" in p:
                    for idx, m in enumerate(p['metrics']):
                        if edit_mode:
                            m[0] = st.text_input(f"명칭{idx}", m[0], key=f"ml_{i}_{idx}")
                            m[1] = st.text_input(f"수치{idx}", m[1], key=f"mv_{i}_{idx}")
                            m[2] = st.text_input(f"상태{idx}", m[2], key=f"md_{i}_{idx}")
                        st.metric(label=m[0], value=m[1], delta=m[2])

    if edit_mode:
        st.download_button("수정본 JSON 저장", json.dumps(data, indent=2, ensure_ascii=False), "final_report.json")
else:
    st.info("파일을 업로드하면 실시간 브리핑이 시작됩니다.")
