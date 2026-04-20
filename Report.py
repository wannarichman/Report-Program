import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Dashboard", layout="wide")

# 2. 실시간 화상 설정
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

with st.sidebar:
    st.title("🎥 Live Sync")
    webrtc_streamer(key="cam", mode=WebRtcMode.SENDRECV, rtc_configuration=RTC_CONFIG)
    st.divider()
    st.subheader("📂 데이터 관리")
    uploaded_file = st.file_uploader("JSON 파일 로드", type=['json', 'js'])
    
    # 편집 모드 스위치
    edit_mode = st.toggle("📝 편집 모드 활성화", value=False)

# 3. 데이터 로드 및 세션 상태 관리
if uploaded_file and "data" not in st.session_state:
    try:
        raw = uploaded_file.read().decode("utf-8")
        st.session_state.data = json.loads(raw)
    except Exception as e:
        st.error(f"파일 로드 실패: {e}")

if "data" in st.session_state:
    data = st.session_state.data
    
    # 타이틀 편집
    if edit_mode:
        data['title'] = st.text_input("리포트 제목 수정", data['title'])
    st.title(data['title'])
    st.divider()

    tabs = st.tabs([f"PAGE {i+1}: {p.get('tab', '')}" for i, p in enumerate(data['pages'])])

    for i, tab in enumerate(tabs):
        with tab:
            p = data['pages'][i]
            col_main, col_side = st.columns([1.6, 1])
            
            with col_main:
                # 헤더 및 본문 편집
                if edit_mode:
                    p['header'] = st.text_input(f"P{i+1} 헤더 수정", p['header'], key=f"h_{i}")
                    p['content'] = st.text_area(f"P{i+1} 본문 수정", p['content'], height=150, key=f"c_{i}")
                
                st.header(p.get('header', ''))
                
                if "image" in p:
                    st.image(p["image"], use_container_width=True)
                
                # 에러 방지를 위해 HTML 없이 순수 텍스트 출력
                st.write(p.get("content", ""))
                
                if "highlight" in p:
                    if edit_mode:
                        p['highlight'] = st.text_input(f"P{i+1} 핵심 메시지 수정", p['highlight'], key=f"hl_{i}")
                    st.success(f"💡 핵심 메시지: {p['highlight']}")

            with col_side:
                st.subheader("📊 지표 편집")
                if "metrics" in p:
                    for idx, m in enumerate(p['metrics']):
                        if edit_mode:
                            m[0] = st.text_input(f"항목명", m[0], key=f"m_lab_{i}_{idx}")
                            m[1] = st.text_input(f"수치", m[1], key=f"m_val_{i}_{idx}")
                        st.metric(label=m[0], value=m[1], delta=m[2])

    # 4. JSON 동기화 다운로드 버튼
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
    st.info("왼쪽 사이드바에서 JSON 파일을 업로드하여 보고서를 시작하세요.")
