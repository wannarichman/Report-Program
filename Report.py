import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C Interactive Dashboard", layout="wide")

# 2. 디자인 CSS (안전한 한 줄 방식)
st.markdown("<style>.content-card { background-color: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border-left: 8px solid #1a2a6c; margin-bottom: 15px; } .key-message { background-color: #fff9db; padding: 15px; border-radius: 10px; border-left: 5px solid #fcc419; font-weight: 600; }</style>", unsafe_allow_headers=True)

# 3. 실시간 화상 설정
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

with st.sidebar:
    st.title("🎥 Live Sync")
    webrtc_streamer(key="cam", mode=WebRtcMode.SENDRECV, rtc_configuration=RTC_CONFIG)
    st.divider()
    st.subheader("📂 데이터 관리")
    uploaded_file = st.file_uploader("JSON 파일 로드", type=['json', 'js'])
    
    # [핵심] 편집 모드 스위치
    edit_mode = st.toggle("📝 편집 모드 활성화", value=False)

# 4. 데이터 로드 및 세션 상태 저장
if uploaded_file and "data" not in st.session_state:
    raw = uploaded_file.read().decode("utf-8")
    st.session_state.data = json.loads(raw)

if "data" in st.session_state:
    data = st.session_state.data
    
    # 5. 헤더 및 타이틀 편집
    if edit_mode:
        data['title'] = st.text_input("리포트 제목 수정", data['title'])
    st.title(data['title'])
    st.divider()

    tabs = st.tabs([f"P{i+1}. {p['tab']}" for i, p in enumerate(data['pages'])])

    for i, tab in enumerate(tabs):
        with tab:
            p = data['pages'][i]
            col_main, col_side = st.columns([1.6, 1])
            
            with col_main:
                # 문구 편집
                if edit_mode:
                    p['header'] = st.text_input(f"P{i+1} 헤더 수정", p['header'])
                    p['content'] = st.text_area(f"P{i+1} 본문 수정", p['content'], height=150)
                
                st.header(p['header'])
                if "image" in p:
                    # 이미지 크기는 Streamlit 기본 기능을 통해 조절
                    st.image(p["image"], use_container_width=True)
                st.markdown(f'<div class="content-card">{p["content"].replace("\\n", "<br>")}</div>', unsafe_allow_headers=True)

            with col_side:
                st.subheader("📊 지표 편집")
                if "metrics" in p:
                    for idx, m in enumerate(p['metrics']):
                        if edit_mode:
                            # 수치 직접 수정
                            m[0] = st.text_input(f"항목명", m[0], key=f"lab_{i}_{idx}")
                            m[1] = st.text_input(f"수치", m[1], key=f"val_{i}_{idx}")
                        st.metric(label=m[0], value=m[1], delta=m[2])

    # 6. JSON 동기화 및 다운로드 버튼
    if edit_mode:
        st.divider()
        st.subheader("💾 데이터 동기화")
        new_json = json.dumps(data, indent=2, ensure_ascii=False)
        st.download_button(
            label="수정된 내용을 JSON 파일로 저장",
            data=new_json,
            file_name="updated_report.json",
            mime="application/json"
        )
else:
    st.info("파일을 업로드하면 보고서가 시작됩니다.")
