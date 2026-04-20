import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json
import requests

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C Interactive Dashboard", layout="wide")

# 2. Twilio TURN 서버 설정을 Secrets에서 안전하게 불러오기
def get_ice_servers():
    """
    Streamlit Cloud의 Secrets에 저장된 Twilio 정보를 사용하여 
    보안망(사내망)에서도 화상이 끊기지 않도록 TURN 서버를 동적으로 가져옵니다.
    """
    try:
        # Streamlit Cloud의 Settings > Secrets에 저장된 값을 읽음
        TWILIO_SID = st.secrets["TWILIO_ACCOUNT_SID"]
        TWILIO_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
        
        response = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Tokens.json",
            auth=(TWILIO_SID, TWILIO_TOKEN),
            timeout=3
        )
        if response.status_code == 201:
            return response.json()["ice_servers"]
    except Exception as e:
        # Secrets 설정이 안 되어 있거나 오류 발생 시 기본 STUN 서버 사용
        return [{"urls": ["stun:stun.l.google.com:19302"]}]

# 3. 실시간 화상 설정 (다대다 연결 최적화)
RTC_CONFIG = RTCConfiguration({"iceServers": get_ice_servers()})

with st.sidebar:
    st.title("🎥 Live Sync")
    st.info("회의 참여자 모두 'START'를 눌러야 실시간 소통이 시작됩니다.")
    
    webrtc_streamer(
        key="posco-vibe-conference-final",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": True, "audio": True},
        async_processing=True,
    )
    st.divider()
    st.subheader("📂 데이터 관리")
    uploaded_file = st.file_uploader("JSON 파일 로드", type=['json', 'js'])
    
    # 전체 편집 모드 활성화
    edit_mode = st.toggle("📝 전체 편집 및 가독성 설정 모드", value=False)

# 4. 데이터 로드 및 세션 상태 관리
if uploaded_file and "data" not in st.session_state:
    try:
        raw = uploaded_file.read().decode("utf-8")
        st.session_state.data = json.loads(raw)
    except Exception as e:
        st.error(f"파일 로드 실패: {e}")

if "data" in st.session_state:
    data = st.session_state.data
    
    # 리포트 전체 제목 편집
    if edit_mode:
        data['title'] = st.text_input("리포트 전체 제목 수정", data['title'])
    st.markdown(f"# {data['title']}")
    st.divider()

    # 탭 이름 편집 로직
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
                    p['content'] = st.text_area(f"P{i+1} 본문 수정 (엔터로 구분)", p.get('content', ''), height=200, key=f"c_{i}")
                    img_width = st.slider(f"그림 크기 조절 (%)", 10, 100, 70, key=f"img_w_{i}")
                else:
                    img_width = 70

                st.markdown(f"## {p.get('header', '')}")
                
                if "image" in p:
                    st.image(p["image"], width=int(img_width * 10))
                
                # 본문 가독성 강화 (문단별로 굵고 크게 출력)
                content_body = p.get('content', '')
                for para in content_body.split('\n'):
                    if para.strip():
                        st.markdown(f"### **{para.strip()}**")
                
                if "highlight" in p:
                    if edit_mode:
                        p['highlight'] = st.text_input(f"핵심 메시지 수정", p.get('highlight', ''), key=f"hl_{i}")
                    st.success(f"**💡 핵심 메시지: {p.get('highlight', '')}**")

            with col_side:
                # 지표 섹션 제목 편집
                if 'metrics_title' not in p: p['metrics_title'] = "📊 주요 지표"
                if edit_mode:
                    p['metrics_title'] = st.text_input(f"지표 제목 수정", p['metrics_title'], key=f"mt_{i}")
                st.subheader(p['metrics_title'])

                if "metrics" in p:
                    for idx, m in enumerate(p['metrics']):
                        if edit_mode:
                            m[0] = st.text_input(f"지표명 {idx+1}", m[0], key=f"m_lab_{i}_{idx}")
                            m[1] = st.text_input(f"수치 {idx+1}", m[1], key=f"m_val_{i}_{idx}")
                            m[2] = st.text_input(f"상태 메시지 {idx+1}", m[2], key=f"m_det_{i}_{idx}")
                            st.divider()
                        st.metric(label=m[0], value=m[1], delta=m[2])

    # 5. JSON 저장 및 동기화
    if edit_mode:
        st.divider()
        st.subheader("💾 데이터 동기화")
        new_json = json.dumps(data, indent=2, ensure_ascii=False)
        st.download_button(
            label="수정된 내용을 JSON 파일로 저장",
            data=new_json,
            file_name="posco_report_vibe.json",
            mime="application/json"
        )
else:
    st.info("왼쪽 사이드바에서 JSON 파일을 업로드하여 스마트 보고서를 시작하세요.")
