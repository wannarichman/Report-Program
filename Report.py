import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C Interactive Dashboard", layout="wide")

# 2. 실시간 화상 설정
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

with st.sidebar:
    st.title("🎥 Live Sync")
    webrtc_streamer(key="cam", mode=WebRtcMode.SENDRECV, rtc_configuration=RTC_CONFIG)
    st.divider()
    st.subheader("📂 데이터 관리")
    uploaded_file = st.file_uploader("JSON 파일 로드", type=['json', 'js'])
    
    # 전체 편집 모드 활성화
    edit_mode = st.toggle("📝 전체 편집 및 가독성 설정 모드", value=False)

# 3. 데이터 및 세션 관리
if uploaded_file and "data" not in st.session_state:
    try:
        raw = uploaded_file.read().decode("utf-8")
        st.session_state.data = json.loads(raw)
    except Exception as e:
        st.error(f"파일 로드 실패: {e}")

if "data" in st.session_state:
    data = st.session_state.data
    
    if edit_mode:
        data['title'] = st.text_input("리포트 전체 제목 수정", data['title'])
    
    st.markdown(f"# {data['title']}")
    st.divider()

    # 탭 이름 편집 로직
    tab_titles = []
    for i, p in enumerate(data['pages']):
        if edit_mode:
            new_tab_name = st.text_input(f"P{i+1} 탭 이름 수정", p.get('tab', ''), key=f"tab_edit_{i}")
            p['tab'] = new_tab_name
        tab_titles.append(f"P{i+1}. {p.get('tab', '')}")

    tabs = st.tabs(tab_titles)

    for i, tab in enumerate(tabs):
        with tab:
            p = data['pages'][i]
            col_main, col_side = st.columns([1.6, 1])
            
            with col_main:
                if edit_mode:
                    p['header'] = st.text_input(f"P{i+1} 헤더 수정", p['header'], key=f"h_{i}")
                    p['content'] = st.text_area(f"P{i+1} 본문 수정", p['content'], height=200, key=f"c_{i}")
                    img_width = st.slider(f"그림 크기 조절 (%)", 10, 100, 70, key=f"img_w_{i}")
                else:
                    img_width = 70

                st.markdown(f"## {p.get('header', '')}")
                
                if "image" in p:
                    st.image(p["image"], width=int(img_width * 10))
                
                # 본문 가독성 강화 출력
                content_body = p.get('content', '')
                paragraphs = content_body.split('\n')
                for para in paragraphs:
                    if para.strip():
                        st.markdown(f"### **{para.strip()}**")
                
                if "highlight" in p:
                    if edit_mode:
                        p['highlight'] = st.text_input(f"핵심 메시지 수정", p['highlight'], key=f"hl_{i}")
                    st.success(f"**💡 핵심 메시지: {p['highlight']}**")

            with col_side:
                # [수정] 지표 부분 편집 기능 강화
                if edit_mode:
                    st.subheader("📊 지표 데이터 편집")
                else:
                    st.subheader("📊 주요 지표")

                if "metrics" in p:
                    for idx, m in enumerate(p['metrics']):
                        if edit_mode:
                            # 1. 지표 제목(Label) 수정
                            m[0] = st.text_input(f"지표명 {idx+1}", m[0], key=f"m_lab_{i}_{idx}")
                            # 2. 지표 수치(Value) 수정
                            m[1] = st.text_input(f"수치 {idx+1}", m[1], key=f"m_val_{i}_{idx}")
                            # 3. 지표 상태/변화량(Delta) 수정 (비효율, 단방향 등)
                            m[2] = st.text_input(f"상태 메시지 {idx+1}", m[2], key=f"m_det_{i}_{idx}")
                            st.divider()
                        
                        st.metric(label=m[0], value=m[1], delta=m[2])

    # 4. JSON 저장 및 동기화
    if edit_mode:
        st.divider()
        st.subheader("💾 데이터 최종 동기화")
        new_json = json.dumps(data, indent=2, ensure_ascii=False)
        st.download_button(
            label="수정된 내용을 JSON 파일로 저장",
            data=new_json,
            file_name="posco_report_final.json",
            mime="application/json"
        )
else:
    st.info("왼쪽 사이드바에서 JSON 파일을 업로드하여 스마트 보고서를 시작하세요.")
