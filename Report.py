import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import time
import base64
import os
import urllib.parse
import google.generativeai as genai  # [핵심 추가] 제미나이 API 연동

# ==========================================
# 1. 페이지 설정 및 프리미엄 클린 디자인 CSS
# ==========================================
st.set_page_config(page_title="AI Live Sync Master Builder", layout="wide")

st.markdown(
    """
<style>
/* 앱 전체 배경을 깨끗한 흰색으로 */
[data-testid="stAppViewContainer"] {
    background-color: #ffffff !important;
}

/* 메인 화면 컨테이너: 심플하고 세련된 얇은 테두리와 은은한 그림자 */
.main [data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #ffffff !important;
    border: 1px solid #dee2e6 !important;
    border-radius: 16px !important;
    padding: 35px 40px !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.04) !important;
    margin-bottom: 50px !important;
}

/* 사이드바 내부 컨테이너 레이아웃 유지 */
[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid #dee2e6 !important;
    padding: 15px !important;
    box-shadow: none !important;
    margin-bottom: 10px !important;
}

/* 우측 사이드 슬롯: 파란 테두리 없이 깔끔한 여백 레이아웃 */
.side-slot-card {
    padding: 10px 0px;
    margin-bottom: 16px;
}

/* 줄 단위 편집 텍스트 기본 스타일 */
.text-line {
    white-space: pre-wrap;
    word-wrap: break-word;
    line-height: 1.8;
    margin-bottom: 10px;
    color: #334155;
}

/* 음성 연결 패널 디자인 */
.voice-panel {
    background: #ffffff;
    border: 1px solid #dee2e6;
    padding: 15px;
    border-radius: 16px;
    text-align: center;
    margin-bottom: 15px;
}

/* 음성 연결/음소거 버튼 스타일링 */
.btn-mute {
    padding: 8px 16px;
    background: #6c757d;
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-weight: bold;
    width: 100%;
}
.btn-mute.active {
    background: #dc3545;
}
</style>
""",
    unsafe_allow_html=True,
)

# ==========================================
# 2. 전역 저장소 (Global Store)
# ==========================================
@st.cache_resource
def get_global_store():
    return {
        "report_data": None,
        "current_page": 0,
        "user_labels": {},
        "chat_history": [],
        "active_sessions": {},
        "voice_channel": "posco_briefing_room",
    }

shared_store = get_global_store()

# ==========================================
# 3. 유틸리티 로직 및 표준 양식
# ==========================================
def get_sample_json_guide():
    return {
        "title": "주간 보고 (AI 생성 기반)",
        "title_fs": 55,
        "title_color": "#0f172a",
        "pages": [
            {
                "tab": "요약",
                "header": "Executive Summary",
                "header_fs": 35,
                "header_color": "#475569",
                "sections": [
                    {
                        "title": "핵심 요약",
                        "title_fs": 32,
                        "title_color": "#1a1c1e",
                        "col_ratio": 1.5,
                        "main_image": None,
                        "full_width": True,
                        "image_query": "business meeting",
                        "chart_type": "Bar",
                        "chart_data": "",
                        "lines": [
                            {"text": "• 핵심 성과 1을 입력합니다.", "size": 24, "color": "#1e293b"},
                            {"text": "• 핵심 성과 2를 입력합니다.", "size": 22, "color": "#1e293b"},
                            {"text": "• 주요 이슈/리스크를 입력합니다.", "size": 22, "color": "#1e293b"},
                        ],
                        "side_items": [
                            {"type": "metric", "label": "종합 진행률", "value": "0%", "color": "#007bff", "label_fs": 14, "label_color": "#64748b", "value_fs": 34},
                            {"type": "metric", "label": "핵심 일정", "value": "D-0: \nD-7: ", "color": "#0ea5e9", "label_fs": 14, "label_color": "#64748b", "value_fs": 22},
                        ],
                    }
                ],
            },
            {
                "tab": "상세 (데이터)",
                "header": "현황 상세 및 데이터 분석",
                "header_fs": 35,
                "header_color": "#475569",
                "sections": [
                    {
                        "title": "데이터 지표 분석",
                        "title_fs": 32,
                        "title_color": "#1a1c1e",
                        "col_ratio": 1.5,
                        "main_image": None,
                        "full_width": True,
                        "image_query": "",
                        "chart_type": "Bar",
                        "chart_data": "항목1, 35\n항목2, 50\n항목3, 42",
                        "lines": [
                            {"text": "• 위 데이터 차트를 통해 실적 추이를 직관적으로 확인할 수 있습니다.", "size": 22, "color": "#1e293b"},
                            {"text": "• 상세 분석 내용 입력.", "size": 22, "color": "#1e293b"},
                        ],
                        "side_items": [
                            {"type": "metric", "label": "정량 지표 요약", "value": "지표A: \n지표B: ", "color": "#16a34a", "label_fs": 14, "label_color": "#64748b", "value_fs": 22}
                        ],
                    }
                ],
            },
            {
                "tab": "액션/리스크",
                "header": "Action Items & Risks",
                "header_fs": 35,
                "header_color": "#475569",
                "sections": [
                    {
                        "title": "Action Items",
                        "title_fs": 32,
                        "title_color": "#1a1c1e",
                        "col_ratio": 1.5,
                        "main_image": None,
                        "full_width": True,
                        "image_query": "",
                        "chart_type": "Bar",
                        "chart_data": "",
                        "lines": [
                            {"text": "1) [담당/기한] 해결 과제 1", "size": 22, "color": "#1e293b"},
                            {"text": "2) [담당/기한] 해결 과제 2", "size": 22, "color": "#1e293b"},
                        ],
                        "side_items": [
                            {"type": "metric", "label": "주요 Blocker", "value": "없음", "color": "#dc2626", "label_fs": 14, "label_color": "#64748b", "value_fs": 26}
                        ],
                    }
                ],
            },
        ],
    }

def create_empty_page():
    return get_sample_json_guide()["pages"][0]

def adapt_json_format(raw_data):
    if isinstance(raw_data, dict) and "pages" in raw_data:
        if "title" not in raw_data:
            raw_data.update({"title": "AI 기반 보고 플랫폼", "title_fs": 55, "title_color": "#0f172a"})
        if "title_fs" not in raw_data:
            raw_data["title_fs"] = 55
        if "title_color" not in raw_data:
            raw_data["title_color"] = "#0f172a"
        return raw_data
    return get_sample_json_guide()

def get_auto_image_url(query: str, w: int = 1600, h: int = 900) -> str:
    if not isinstance(query, str):
        return ""
    q = query.strip()
    if not q:
        return ""
    q_enc = urllib.parse.quote(q)
    return f"https://picsum.photos/seed/{q_enc}/{w}/{h}"

def render_image_src(img_val):
    if not img_val: return ""
    if not isinstance(img_val, str): return ""
    val = img_val.strip()
    if not val: return ""
    if val.startswith("http://") or val.startswith("https://") or val.startswith("data:image"): return val
    if os.path.isfile(val):
        try:
            with open(val, "rb") as f:
                ext = val.split(".")[-1].lower()
                mime = "image/jpeg" if ext in ["jpg", "jpeg"] else f"image/{ext}"
                return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"
        except Exception: return val
    return val

# ==========================================
# 4. ID 식별 및 음성 시스템 
# ==========================================
if "uid" not in st.session_state:
    url_uid = st.query_params.get("uid")
    if url_uid:
        st.session_state.uid = url_uid
    else:
        new_uid = f"u_{int(time.time() * 1000)}"
        st.session_state.uid = new_uid
        st.query_params["uid"] = new_uid

if "user_label" not in st.session_state:
    active_now = len([s for s in shared_store["active_sessions"].values() if time.time() - s["last_seen"] < 10])
    label = f"참여자 {active_now + 1}"
    st.session_state.user_label = label

def agora_voice_system(app_id, channel, user_label):
    custom_html = f"""
<script src="https://download.agora.io/sdk/release/AgoraRTC_N-4.11.0.js"></script>
<div class="voice-panel">
  <div id="v-status" style="font-size: 13px; font-weight: 700; margin-bottom: 8px; color:#1e293b;">🎙️ {user_label}</div>
  <div style="width: 100%; height: 10px; background: #e2e8f0; border-radius: 5px; margin-bottom: 12px; overflow: hidden;">
    <div id="level-bar" style="width: 0%; height: 100%; background: #28a745; transition: width 0.05s;"></div>
  </div>
  <button id="mute" class="btn-mute">🎤 마이크 : 켜짐</button>
</div>
<script>
let client = AgoraRTC.createClient({{ mode: "rtc", codec: "vp8" }});
let localTracks = {{ audioTrack: null }};
let isMuted = false;

async function join() {{
  try {{
    await client.join("{app_id}", "{channel}", null, null);
    localTracks.audioTrack = await AgoraRTC.createMicrophoneAudioTrack();
    await client.publish([localTracks.audioTrack]);
    client.enableAudioVolumeIndicator();

    client.on("volume-indicator", (vs) => {{
      vs.forEach((v) => {{
        if(v.uid === 0 && !isMuted) {{
            document.getElementById("level-bar").style.width = Math.min(v.level * 2, 100) + "%";
        }}
        if(isMuted) {{
            document.getElementById("level-bar").style.width = "0%";
        }}
      }});
    }});
    
    client.on("user-published", async (u, m) => {{
        await client.subscribe(u, m); 
        if(m === "audio") {{
            u.audioTrack.play();
        }}
    }});
  }} catch (e) {{
    console.error(e);
  }}
}}

function toggleMute() {{
  if (!localTracks.audioTrack) return;
  isMuted = !isMuted;
  localTracks.audioTrack.setEnabled(!isMuted);

  const btn = document.getElementById("mute");
  if (isMuted) {{
    btn.innerText = "🔇 마이크 : 꺼짐";
    btn.classList.add("active");
  }} else {{
    btn.innerText = "🎤 마이크 : 켜짐";
    btn.classList.remove("active");
  }}
}}

join();
document.getElementById("mute").onclick = toggleMute;
</script>
"""
    components.html(custom_html, height=160)

@st.fragment(run_every="1s")
def sync_member_list(my_uid):
    with st.container(border=True):
        st.caption("👥 실시간 보이스 연결 멤버")
        now = time.time()
        temp_sessions = {}

        for uid, info in shared_store["active_sessions"].items():
            if (now - info["last_seen"] < 6) and info.get("voice_connected"):
                base_label = info["label"]
                is_me = (uid == my_uid)
                if base_label not in temp_sessions or is_me:
                    temp_sessions[base_label] = is_me

        if not temp_sessions:
            st.write("연결된 멤버 없음")
        else:
            for label in sorted(temp_sessions.keys()):
                display_name = label
                if temp_sessions[label]: display_name += " (나)"
                st.markdown(f"🟢 **{display_name}**")

# ==========================================
# [핵심 추가] AI 텍스트 -> JSON 파싱 로직
# ==========================================
def generate_json_from_ai(api_key, context_text):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        system_prompt = f"""
        당신은 뛰어난 비즈니스 컨설턴트이자 데이터 구조화 전문가입니다.
        사용자가 제공한 [입력 데이터]를 분석하여, 아래 [표준 JSON 양식] 구조에 맞는 완벽한 JSON 데이터를 생성하십시오.
        
        [표준 JSON 양식 참조]
        {json.dumps(get_sample_json_guide(), ensure_ascii=False)}
        
        지시사항:
        1. P1(요약), P2(상세), P3(액션/리스크) 3페이지 구조를 유지하세요.
        2. 사용자의 데이터를 기반으로 각 섹션의 lines, side_items(metric), chart_data를 알아서 작성하세요.
        3. 차트가 필요한 수치 데이터가 있다면 P2의 chart_data 필드에 "항목, 수치\\n항목, 수치" 형태로 작성하세요.
        4. 마크다운 코드블록(```json 등) 없이 오직 파싱 가능한 순수 JSON 문자열만 출력하세요.
        
        [입력 데이터]
        {context_text}
        """
        response = model.generate_content(system_prompt)
        
        # 순수 JSON 추출 (마크다운 찌꺼기 제거)
        clean_text = response.text.strip()
        if clean_text.startswith("
http://googleusercontent.com/immersive_entry_chip/0
http://googleusercontent.com/immersive_entry_chip/1
http://googleusercontent.com/immersive_entry_chip/2
