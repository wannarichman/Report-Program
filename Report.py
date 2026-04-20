import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import os

# 1. 페이지 설정
st.set_page_config(page_title="AI R&D Speed-up Platform", layout="wide")

# 2. 실시간 화상 보고 설정 (WebRTC)
# 구글의 무료 STUN 서버를 사용하여 서로 다른 네트워크에서도 연결되도록 설정합니다.
RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)

with st.sidebar:
    st.title("🎥 Live Briefing")
    st.info("상대방과 같은 주소로 접속하면 실시간 소통이 가능합니다.")
    webrtc_streamer(
        key="rnd-report-stream",
        mode=WebRtcMode.SENDRECV, # 송수신 모드
        rtc_configuration=RTC_CONFIGURATION,
        media_stream_constraints={"video": True, "audio": True},
        async_processing=True,
    )
    st.divider()
    st.caption("Status: Connected to AI Node")

# 3. 보고서 데이터 (JSON 대신 코드 내부에 구조화)
report_data = {
    "title": "AI R&D Speed-up: 혁신 보고 체계",
    "pages": [
        {
            "tab": "01. 추진 배경",
            "header": "Goodbye PPT: 보고의 패러다임 전환",
            "content": "기존 PPT 기반 보고 체계는 '형식'을 맞추느라 '본질'을 놓치는 경우가 많았습니다. 보고서 한 장을 위해 평균 4시간 이상의 문서 작업이 소요되는 비효율을 타파하고자 합니다.",
            "metrics": [("문서 작업 시간", "4.2h", "-80%"), ("의사결정 속도", "300%", "UP")]
        },
        {
            "tab": "02. R&D Speed-up",
            "header": "지능형 데이터 자산화와 자동 요약",
            "content": "사내에 흩어진 수천 건의 기술 표준과 논문을 사람이 일일이 찾지 않습니다. AI 에이전트가 단 10초 만에 관련 핵심 정보를 추출하여 보고서 초안(Zero-Draft)을 생성합니다.",
            "metrics": [("자료 검색 시간", "10s", "-99%"), ("연구 몰입도", "120%", "UP")]
        },
        {
            "tab": "03. Vibe Coding",
            "header": "나만의 AI 활용법: 바이브 코딩",
            "content": "이 보고서는 '작성'된 것이 아니라 '생성'되었습니다. 사용자가 비즈니스 로직을 말하면 AI가 즉석에서 코드를 생성하고 배포하는 'Vibe Coding' 프로세스를 구현했습니다.",
            "highlight": "사용자 아이디어 -> AI 논리 구조화 -> AI 코드 생성 -> 즉시 배포"
        },
        {
            "tab": "04. 실시간 보고",
            "header": "Interactive UI: Live Briefing",
            "content": "좌측 사이드바의 실시간 브리핑 창은 별도의 화상 회의 툴 없이도 즉각적인 보고와 피드백을 가능하게 합니다. 보고 중 수집된 데이터는 AI가 실시간으로 본문에 반영합니다."
        },
        {
            "tab": "05. 미래 비전",
            "header": "전사 확산: 기술 중심의 R&D 문화",
            "content": "단순 문서 작업 시간을 줄여 연구원들이 본연의 가치인 '기술 개발'에 집중하게 만드는 것, 그것이 이번 챌린지의 최종 목적입니다.",
            "metrics": [("기회비용 절감", "₩3.5B+", "예상")]
        }
    ]
}

# 4. 메인 화면 렌더링
st.title(report_data["title"])
tabs = st.tabs([p["tab"] for p in report_data["pages"]])

for i, tab in enumerate(tabs):
    with tab:
        p = report_data["pages"][i]
        st.header(p["header"])
        st.write(p["content"])
        
        if "metrics" in p:
            cols = st.columns(len(p["metrics"]))
            for idx, (label, val, delta) in enumerate(p["metrics"]):
                cols[idx].metric(label, val, delta)
        
        if "highlight" in p:
            st.success(p["highlight"])

# 5. 실시간 피드백 섹션
st.divider()
feedback = st.text_input("AI에게 실시간 수정을 요청하세요 (예: 2페이지 수치 업데이트해줘)")
if feedback:
    st.write(f"AI가 '{feedback}' 내용을 분석하여 보고서에 반영 중입니다...")