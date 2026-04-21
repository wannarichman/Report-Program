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
        "report_data": None,
        "last_sync": time.time()
    }

shared_store = get_global_store()

if "session_counted" not in st.session_state:
    shared_store["active_users"] += 1
    st.session_state.session_counted = True

# 3. 음성 설정
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
    
    col1, col2 = st.columns([2, 1])
    col1.success(f"👥 접속: **{shared_store['active_users']}명**")
    if col2.button("Reset"):
        shared_store["active_users"] = 1
        shared_store["report_data"] = None
        st.rerun()

    st.divider()

    webrtc_ctx = webrtc_streamer(
        key="posco-voice-sync-final-v7",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIG,
        media_stream_constraints={"video": False, "audio": True},
    )

    if webrtc_ctx.state.playing:
        st.write("🔊 **보이스 브리핑 중**")
        st.progress(0.8)
    else:
        st.write("🔇 음성 대기 중")
        st.progress(0)

    st.divider()
    
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
    
    st.subheader("📂 보고서 컨트롤")
    uploaded_file = st.file_uploader("JSON 업로드 (보고자)", type=['json', 'js'])
    if uploaded_file:
        try:
            shared_store["report_data"] = json.loads(uploaded_file.read().decode("utf-8"))
        except:
            st.error("파일 로드 실패")

    edit_mode = st.toggle("📝 전체 편집 모드 활성화", value=False)
    if st.button("🔄 최신 화면 동기화"):
        st.rerun()

# 4. 리포트 본문 (상세 편집 기능 포함)
if shared_store["report_data"]:
    data = shared_store["report_data"]
    
    # [편집] 전체 제목 수정
    if edit_mode:
        data['title'] = st.text_input("💎 리포트 전체 제목 수정", data.get('title', ''))
    st.title(data.get('title', 'AI R&D Report'))
    st.divider()

    # [편집] 각 탭 제목 수정
    tab_labels = []
    for i, p in enumerate(data['pages']):
        if edit_mode:
            p['tab'] = st.text_input(f"🔖 P{i+1} 탭 이름 수정", p.get('tab', ''), key=f"te_{i}")
        tab_labels.append(f"P{i+1}. {p.get('tab', '')}")

    tabs = st.tabs(tab_labels)
    
    for i, tab in enumerate(tabs):
        with tab:
            p = data['pages'][i]
            col_main, col_side = st.columns([1.6, 1])
            
            with col_main:
                # [편집] 헤더 및 본문 텍스트 수정
                if edit_mode:
                    p['header'] = st.text_input(f"📌 P{i+1} 헤더 수정", p.get('header', ''), key=f"he_{i}")
                    p['content'] = st.text_area(f"📄 P{i+1} 본문 글자 수정", p.get('content', ''), height=250, key=f"ce_{i}")
                    
                    # [편집] 그림 크기(너비) 수정 기능 추가
                    if 'img_width' not in p: p['img_width'] = 700
                    p['img_width'] = st.slider(f"🖼️ P{i+1} 그림 크기 조절", 100, 1200, int(p['img_width']), key=f"ie_{i}")
                
                st.markdown(f"## {p.get('header', '')}")
                
                if "image" in p:
                    # 저장된 너비 값(img_width)을 적용하여 이미지 출력
                    st.image(p["image"], width=p.get('img_width', 700))
                
                for para in p.get('content', '').split('\n'):
                    if para.strip():
                        st.markdown(f"### **{para.strip()}**")
                
                if shared_store["comments"]:
                    st.warning(f"🗨️ **실시간 피드백:** {shared_store['comments'][0]}")

            with col_side:
                # [편집] 지표 영역 제목 및 개별 지표 수정
                if 'metrics_title' not in p: p['metrics_title'] = "📊 주요 지표"
                if edit_mode:
                    p['metrics_title'] = st.text_input(f"📊 지표 제목 수정", p['metrics_title'], key=f"mte_{i}")
                st.subheader(p['metrics_title'])

                if "metrics" in p:
                    for idx, m in enumerate(p['metrics']):
                        if edit_mode:
                            m[0] = st.text_input(f"항목{idx}", m[0], key=f"ml_{i}_{idx}")
                            m[1] = st.text_input(f"수치{idx}", m[1], key=f"mv_{i}_{idx}")
                            m[2] = st.text_input(f"상태{idx}", m[2], key=f"md_{i}_{idx}")
                        st.metric(label=m[0], value=m[1], delta=m[2])
    
    if edit_mode:
        st.divider()
        # 수정된 내용을 담은 새로운 JSON 파일 생성
        st.download_button(
            label="💾 수정된 전체 보고서 JSON 저장",
            data=json.dumps(data, indent=2, ensure_ascii=False),
            file_name="edited_report.json",
            mime="application/json"
        )
else:
    st.info("📢 보고자가 파일을 업로드할 때까지 대기 중입니다.")
