import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import json

# 1. 페이지 설정 및 레이아웃
st.set_page_config(page_title="AI R&D Speed-up Platform", layout="wide")

# 2. 실시간 화상 보고 설정 (WebRTC)
RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)

# 사이드바 구성
with st.sidebar:
    st.title("🎥 Live Briefing")
    # 화상 통화 기능 유지
    webrtc_streamer(
        key="rnd-report-stream",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIGURATION,
        media_stream_constraints={"video": True, "audio": True},
    )
    st.divider()

    # [핵심 기능] 로컬 파일 선택 (JS/JSON 파일 로드)
    st.subheader("📂 보고서 데이터 로드")
    st.info("제미나이가 생성한 보고서 데이터 파일(.json 또는 .js)을 선택하세요.")
    uploaded_file = st.file_uploader("파일 선택", type=['json', 'js'])

# 3. 데이터 로직 처리
user_data = None
if uploaded_file is not None:
    try:
        # 파일 읽기 및 JSON 파싱
        # .js 파일일 경우 'const reportData = ' 부분을 제외한 순수 JSON 구조만 필요합니다.
        content = uploaded_file.read().decode("utf-8")
        if "const reportData =" in content:
            # JS 변수 선언문이 포함된 경우 순수 JSON만 추출 (유연한 처리)
            json_str = content.split("=", 1)[1].strip().rstrip(";")
            user_data = json.loads(json_str)
        else:
            user_data = json.loads(content)
    except Exception as e:
        st.error(f"데이터를 읽는 중 오류가 발생했습니다: {e}")

# 데이터가 없을 때 보여줄 기본 가이드 양식
default_data = {
    "title": "R&D Speed-up 플랫폼",
    "pages": [
        {
            "tab": "시작하기",
            "header": "환영합니다!",
            "content": "사이드바에서 보고서 데이터 파일(.json)을 업로드하시면 즉시 브리핑이 시작됩니다.",
            "highlight": "AI와 협업하여 생성된 지능형 보고서를 지금 확인해보세요."
        }
    ]
}

report_data = user_data if user_data else default_data

# 4. 메인 화면 렌더링 (동적 생성)
st.title(report_data.get("title", "AI R&D Dashboard"))

if "pages" in report_data:
    tabs = st.tabs([p.get("tab", f"Page {i+1}") for i, p in enumerate(report_data["pages"])])

    for i, tab in enumerate(tabs):
        with tab:
            p = report_data["pages"][i]
            st.header(p.get("header", ""))
            st.write(p.get("content", ""))
            
            # 메트릭스(수치) 시각화
            if "metrics" in p:
                cols = st.columns(len(p["metrics"]))
                for idx, m in enumerate(p["metrics"]):
                    # 데이터 형식이 [라벨, 값, 변화량]인 경우 처리
                    if isinstance(m, list) and len(m) == 3:
                        cols[idx].metric(label=m[0], value=m[1], delta=m[2])
            
            # 강조 박스
            if "highlight" in p:
                st.success(p["highlight"])

st.divider()
st.caption("Developed by R&D Speed-up Project Team")
