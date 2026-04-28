import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import time
import base64
import os
import urllib.parse
import google.generativeai as genai

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
                            {"text": "• 금주 핵심 성과를 요약합니다.", "size": 24, "color": "#1e293b"},
                            {"text": "• 주요 이슈 및 리스크를 점검합니다.", "size": 22, "color": "#1e293b"}
                        ],
                        "side_items": [
                            {"type": "metric", "label": "종합 진행률", "value": "0%", "color": "#007bff", "label_fs": 14, "label_color": "#64748b", "value_fs": 34},
                            {"type": "metric", "label": "핵심 일정", "value": "D-0: \nD-7: ", "color": "#0ea5e9", "label_fs": 14, "label_color": "#64748b", "value_fs": 22}
                        ]
                    }
                ]
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
                        "main_image": "https://picsum.photos/seed/business/800/400",
                        "full_width": True,
                        "image_query": "",
                        "chart_type": "Bar",
                        "chart_data": "1분기, 35\n2분기, 50\n3분기, 42\n4분기, 68",
                        "lines": [
                            {"text": "• 위 데이터 차트를 통해 실적 추이를 확인할 수 있습니다.", "size": 22, "color": "#1e293b"},
                            {"text": "• 상세 분석 내용 텍스트입니다.", "size": 22, "color": "#1e293b"}
                        ],
                        "side_items": [
                            {"type": "metric", "label": "정량 지표 요약", "value": "목표 달성률: 85%\n비용 절감액: 1.2억", "color": "#16a34a", "label_fs": 14, "label_color": "#64748b", "value_fs": 22}
                        ]
                    }
                ]
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
                            {"text": "2) [담당/기한] 해결 과제 2", "size": 22, "color": "#1e293b"}
                        ],
                        "side_items": [
                            {"type": "metric", "label": "주요 Blocker", "value": "없음", "color": "#dc2626", "label_fs": 14, "label_color": "#64748b", "value_fs": 26}
                        ]
                    }
                ]
            }
        ]
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
    """검색어와 실제로 관련 있는 이미지를 반환 (LoremFlickr - Flickr 기반)."""
    if not isinstance(query, str):
        return ""
    q = query.strip()
    if not q:
        return ""
    # 쉼표로 다중 태그 지원 ("business, meeting, office")
    tags = ",".join([urllib.parse.quote(t.strip()) for t in q.split(",") if t.strip()])
    # lock 파라미터로 동일 검색어에 동일 이미지 고정 (캐싱 안정화)
    lock = abs(hash(q)) % 100000
    return f"https://loremflickr.com/{w}/{h}/{tags}?lock={lock}"

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

from datetime import datetime
import zoneinfo  # Python 3.9 미만이면 pytz 사용

# ==========================================
# [핵심] AI 텍스트 -> JSON 파싱 로직 (모델 자동 탐색 + 날짜 주입 + 양식 자유화)
# ==========================================
def generate_json_from_ai(api_key, context_text):
    try:
        genai.configure(api_key=api_key)

        # ✅ 현재 API 키로 실제 호출 가능한 모델 목록을 동적으로 조회
        try:
            available = []
            for m in genai.list_models():
                methods = getattr(m, "supported_generation_methods", []) or []
                if "generateContent" in methods:
                    available.append(m.name)  # 예: "models/gemini-2.5-flash"
        except Exception as e:
            return {"error": f"모델 목록 조회 실패 (SDK 또는 API Key 문제 가능성): {e}"}

        if not available:
            return {"error": "이 API 키로 generateContent 가능한 모델이 없습니다. AI Studio에서 키를 다시 발급받아 주세요."}

        # 선호 순위 (있으면 먼저 사용, 없으면 다음 후보로)
        preferred_order = [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-2.0-flash-001",
            "gemini-1.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash-002",
            "gemini-1.5-pro",
            "gemini-1.5-pro-latest",
        ]

        def pick_model(avail_list):
            short_names = {name.split("/")[-1]: name for name in avail_list}
            for p in preferred_order:
                if p in short_names:
                    return short_names[p]
            for n in avail_list:
                if "flash" in n:
                    return n
            return avail_list[0]

        chosen_model = pick_model(available)

        # ===== ⬇️ 여기서부터 system_prompt 부분만 새로 작성 ⬇️ =====
        # 현재 한국 시간 주입
        now_kst = datetime.now(zoneinfo.ZoneInfo("Asia/Seoul"))
        today_str = now_kst.strftime("%Y년 %m월 %d일")
        year_str = now_kst.strftime("%Y")
        quarter = (now_kst.month - 1) // 3 + 1

        system_prompt = f"""
당신은 뛰어난 비즈니스 컨설턴트이자 데이터 구조화 전문가입니다.
사용자가 제공한 [입력 데이터]를 분석하여, 보고서용 JSON 데이터를 생성하십시오.

[현재 시점 정보 — 반드시 이 기준으로 사고할 것]
- 오늘 날짜: {today_str}
- 현재 연도: {year_str}년
- 현재 분기: {year_str}년 {quarter}분기
- 절대로 과거 연도(예: 2024년, 2025년)를 "현재"나 "다가오는"으로 표현하지 마세요.
- 입력 데이터에 연도 표기가 없으면 모두 {year_str}년 기준으로 해석하세요.

[JSON 출력 스키마 — 구조(필드 이름)만 따르고, 페이지 수/섹션 수/탭명은 자유]
{json.dumps(get_sample_json_guide(), ensure_ascii=False)}

[작성 지침]
1. 위 표준 양식은 "필드 구조 참고용"일 뿐입니다. 페이지 개수, 탭 이름, 섹션 구성, 메트릭 항목은
   입력 데이터의 성격과 분량에 가장 적합하게 자유롭게 설계하세요.
   (예: 단순 회의록은 1~2페이지, 분기보고는 4
        
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
<script src="[https://download.agora.io/sdk/release/AgoraRTC_N-4.11.0.js](https://download.agora.io/sdk/release/AgoraRTC_N-4.11.0.js)"></script>
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
                if temp_sessions[label]:
                    display_name += " (나)"
                st.markdown(f"🟢 **{display_name}**")

# ==========================================
# 5. 사이드바 (Sidebar) 통제 센터
# ==========================================
with st.sidebar:
    st.title("🎙️ AI Live Sync")
    is_reporter = st.toggle("🔑 보고자 권한 (편집기능 활성화)", value=False)
    my_label = "📢 보고자" if is_reporter else f"👤 {st.session_state.user_label}"

    voice_connect = st.toggle("🔊 마이크 연결 (시스템 접속)", value=False, key="voice_active_toggle")

    if voice_connect:
        try:
            agora_id = st.secrets["AGORA_APP_ID"]
            agora_voice_system(agora_id, shared_store["voice_channel"], my_label)
        except Exception:
            st.warning("⚠️ Agora ID 설정 필요")

    sync_member_list(st.session_state.uid)

    if is_reporter:
        st.divider()
        
        # --- AI 생성 기능 ---
        with st.expander("✨ AI 자동 보고서 생성 (Text/File)", expanded=False):
            try:
                ai_api_key = st.secrets["GEMINI_API_KEY"]
            except Exception:
                ai_api_key = ""
                st.warning("⚠️ 서버에 GEMINI_API_KEY가 설정되지 않았습니다.")

            ai_text_input = st.text_area("텍스트 데이터 입력", placeholder="회의록, 초안, 아이디어를 자유롭게 적어주세요.")
            ai_file_input = st.file_uploader("또는 문서 업로드", type=["txt", "csv", "md"])
            
            if st.button("🚀 AI 보고서 생성", use_container_width=True):
                if not ai_api_key:
                    st.error("API Key를 입력해주세요.")
                else:
                    context = ai_text_input
                    if ai_file_input:
                        context += f"\n\n[문서 내용]\n{ai_file_input.getvalue().decode('utf-8')}"
                    
                    if not context.strip():
                        st.error("분석할 텍스트나 문서를 입력해주세요.")
                    else:
                        with st.spinner("AI가 데이터를 분석하여 보고서를 작성 중입니다..."):
                            ai_result = generate_json_from_ai(ai_api_key, context)
                            
                            if "error" in ai_result:
                                st.error(f"생성 실패: {ai_result['error']}")
                            else:
                                shared_store["report_data"] = adapt_json_format(ai_result)
                                shared_store["current_page"] = 0
                                st.success("보고서 생성 완료!")
                                time.sleep(1)
                                st.rerun()

        st.write("---")
        st.download_button(
            label="📘 기존 표준 양식 다운로드",
            data=json.dumps(get_sample_json_guide(), indent=4, ensure_ascii=False),
            file_name="Report_Standard_Template.json",
            mime="application/json",
            use_container_width=True,
        )

        uploaded_file = st.file_uploader("📂 JSON 수동 로드", type=["json"])
        if uploaded_file:
            if st.session_state.get("last_uploaded_id") != uploaded_file.file_id:
                shared_store["report_data"] = adapt_json_format(json.loads(uploaded_file.read().decode("utf-8")))
                st.session_state["last_uploaded_id"] = uploaded_file.file_id
                shared_store["current_page"] = 0

        if st.button("🚨 전체 데이터 초기화"):
            shared_store.update({"report_data": None, "current_page": 0, "chat_history": [], "active_sessions": {}})
            st.session_state.pop("last_uploaded_id", None)
            st.rerun()

        if shared_store["report_data"]:
            st.download_button(
                label="📥 최종 리포트 JSON 저장",
                data=json.dumps(shared_store["report_data"], indent=4, ensure_ascii=False),
                file_name="My_Final_Report.json",
                use_container_width=True,
            )

        edit_mode = st.toggle("📝 디자인/저작 모드 활성화", value=False)
    else:
        edit_mode = False

# ==========================================
# 6. 메인 브리핑 엔진
# ==========================================
@st.fragment(run_every="1s")
def main_content_area(edit_enabled):
    shared_store["active_sessions"][st.session_state.uid] = {
        "label": my_label,
        "last_seen": time.time(),
        "voice_connected": st.session_state.get("voice_active_toggle", False),
    }

    with st.expander("💬 실시간 상호소통 채팅", expanded=False):
        c1, c2 = st.columns([4, 1])
        msg = c1.text_input("메시지", key="chat_in", label_visibility="collapsed")
        if c2.button("전송") and msg:
            shared_store["chat_history"].append(f"**{my_label}**: {msg}")
        chat_box = "".join([f"<div style='margin-bottom:6px;'>{m}</div>" for m in shared_store["chat_history"][-10:]])
        st.markdown(
            f"<div style='height:120px; overflow-y:auto; background:#f8f9fa; padding:12px; border-radius:10px; border:1px solid #dee2e6;'>{chat_box}</div>",
            unsafe_allow_html=True,
        )

    if shared_store["report_data"] is None:
        st.markdown(
            "<div style='text-align:center; padding:150px; color:#64748b;'><h2>📂 좌측 사이드바에서 AI로 자동 생성하거나 파일을 로드하세요.</h2></div>",
            unsafe_allow_html=True,
        )
        if edit_enabled and st.button("📄 완전히 새로운 보고서 시작하기"):
            shared_store["report_data"] = adapt_json_format({})
            st.rerun()
        return

    data = shared_store["report_data"]
    cp_idx = shared_store["current_page"]

    if edit_enabled:
        with st.expander("👑 전체 문서 공통 제목 설정", expanded=True):
            data["title"] = st.text_input("문서 전체 제목", data.get("title", ""), key="global_title_input")
            dtc1, dtc2 = st.columns(2)
            data["title_fs"] = dtc1.slider("제목 글자 크기", 20, 120, int(data.get("title_fs", 55)))
            data["title_color"] = dtc2.color_picker("제목 색상", data.get("title_color", "#0f172a"))

    st.markdown(
        f'<h1 style="text-align:center; font-size:{data.get("title_fs", 55)}px; color:{data.get("title_color", "#0f172a")}; margin-bottom:10px;">{data.get("title", "")}</h1>',
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='margin-top:0; margin-bottom:40px; border:0; border-top:1px solid #eee;'>", unsafe_allow_html=True)

    if cp_idx >= len(data["pages"]):
        shared_store["current_page"] = max(0, len(data["pages"]) - 1)
        st.rerun()

    p = data["pages"][cp_idx]

    if edit_enabled:
        st.write("---")
        pc1, pc2 = st.columns([1, 5])
        if pc1.button("➕ 페이지 추가"):
            data["pages"].insert(cp_idx + 1, create_empty_page())
            shared_store["current_page"] += 1
            st.rerun()
        if pc2.button("🗑️ 페이지 삭제") and len(data["pages"]) > 1:
            data["pages"].pop(cp_idx)
            shared_store["current_page"] = max(0, cp_idx - 1)
            st.rerun()

    if is_reporter:
        tabs = {i: f"P{i+1}. {pg.get('tab', '')}" for i, pg in enumerate(data["pages"])}
        shared_store["current_page"] = st.radio(
            "📑 이동",
            list(tabs.keys()),
            index=shared_store["current_page"],
            format_func=lambda x: tabs[x],
            horizontal=True,
        )

    if edit_enabled:
        p["tab"] = st.text_input("🔖 탭 이름 수정", p.get("tab", ""), key=f"tab_edit_{cp_idx}")

    if edit_enabled:
        with st.expander("📌 페이지별 소제목 디자인 설정"):
            p["header"] = st.text_input("소제목 내용", p.get("header", ""), key=f"ph_input_{cp_idx}")
            hc1, hc2 = st.columns(2)
            p["header_fs"] = hc1.slider("소제목 크기", 10, 150, int(p.get("header_fs", 35)), key=f"phfs_{cp_idx}")
            p["header_color"] = hc2.color_picker("소제목 색상", p.get("header_color", "#475569"), key=f"phc_{cp_idx}")

    st.markdown(
        f'<h2 style="text-align:center; font-size:{p.get("header_fs", 35)}px; color:{p.get("header_color", "#475569")}; margin-bottom:30px;">{p.get("header", "")}</h2>',
        unsafe_allow_html=True,
    )

    sections = p.setdefault("sections", [])
    if edit_enabled and st.button("➕ 새로운 세로 섹션 뭉치 추가", key=f"add_sec_btn_{cp_idx}"):
        sections.append(
            {
                "title": "새 섹션",
                "title_fs": 32,
                "title_color": "#1a1c1e",
                "col_ratio": 1.5,
                "lines": [{"text": "내용", "size": 22, "color": "#1e293b"}],
                "main_image": None,
                "full_width": True,
                "image_query": "",
                "chart_type": "Bar",
                "chart_data": "",
                "side_items": [],
            }
        )
        st.rerun()

    ERROR_IMG = "[https://placehold.co/800x400/f8fafc/94a3b8?text=Image+Not+Found+or+Invalid+URL](https://placehold.co/800x400/f8fafc/94a3b8?text=Image+Not+Found+or+Invalid+URL)"

    for s_idx, sec in enumerate(sections):
        with st.container(border=True):
            if edit_enabled:
                sc1, sc2, sc3, sc4, sc5 = st.columns([2.5, 0.8, 0.8, 1.2, 0.5])
                sec["title"] = sc1.text_input("섹션 제목", sec.get("title", ""), key=f"st_t_{cp_idx}*{s_idx}")
                sec["title_fs"] = sc2.number_input("크기", 10, 80, int(sec.get("title_fs", 32)), key=f"st_fs*{cp_idx}*{s_idx}")
                sec["title_color"] = sc3.color_picker("색상", sec.get("title_color", "#1a1c1e"), key=f"st_c*{cp_idx}*{s_idx}")
                sec["col_ratio"] = sc4.slider("비율", 1.0, 4.0, float(sec.get("col_ratio", 1.5)), 0.1, key=f"st_r*{cp_idx}*{s_idx}")
                if sc5.button("🗑️", key=f"st_del*{cp_idx}*{s_idx}"):
                    sections.pop(s_idx)
                    st.rerun()

            st.markdown(
                f"<h3 style='font-size:{sec.get('title_fs', 32)}px; color:{sec.get('title_color', '#1a1c1e')}; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 2px solid #f8f9fa;'>{sec.get('title')}</h3>",
                unsafe_allow_html=True,
            )

            col_main, col_side = st.columns([sec.get("col_ratio", 1.5), 1], gap="medium")

            with col_main:
                # -----------------------------------
                # 1. 메인 이미지 관리 및 렌더링
                # -----------------------------------
                if edit_enabled:
                    with st.expander("🖼️ 이미지 관리"):
                        current_img = sec.get("main_image", "")
                        display_img_url = "" if (isinstance(current_img, str) and current_img.startswith("data:image")) else (current_img or "")

                        new_img_url = st.text_input("웹 URL 또는 로컬 파일명 (예: image.jpg)", value=display_img_url, key=f"simg_url*{cp_idx}*{s_idx}")
                        sec["image_query"] = st.text_input("자동 이미지 검색어(선택, 비워두면 사용 안함)", value=sec.get("image_query", ""), key=f"simg_q*{cp_idx}*{s_idx}")
                        img_f = st.file_uploader("또는 PC 이미지 업로드 (직접 삽입)", type=["png", "jpg", "jpeg", "gif"], key=f"simg_f*{cp_idx}*{s_idx}")

                        if img_f:
                            sec["main_image"] = f"data:image/png;base64,{base64.b64encode(img_f.getvalue()).decode()}"
                        elif new_img_url != display_img_url:
                            sec["main_image"] = new_img_url

                        sec["full_width"] = st.toggle("너비 꽉 채우기", value=sec.get("full_width", True), key=f"fw*{cp_idx}*{s_idx}")
                        if not sec["full_width"]:
                            sec["img_width"] = st.slider("수동 너비 조절", 100, 1200, int(sec.get("img_width", 750)), key=f"sw*{cp_idx}*{s_idx}")

                        if st.button("🗑️ 그림 삭제", key=f"simg_del*{cp_idx}*{s_idx}"):
                            sec["main_image"] = None
                            st.rerun()

                if (not sec.get("main_image")) and sec.get("image_query"):
                    sec["main_image"] = get_auto_image_url(sec.get("image_query"))

                if sec.get("main_image"):
                    final_src = render_image_src(sec["main_image"])
                    style = "width:100%;" if sec.get("full_width", True) else f"width:{sec.get('img_width', 750)}px; max-width:100%;"
                    st.markdown(
                        f'<div style="text-align:center;"><img src="{final_src}" onerror="this.onerror=null; this.src=\'{ERROR_IMG}\';" style="{style} border-radius:12px; margin-bottom:20px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);" /></div>',
                        unsafe_allow_html=True,
                    )
                
                # -----------------------------------
                # 2. 차트 관리 및 렌더링
                # -----------------------------------
                if edit_enabled:
                    with st.expander("📈 차트/그래프 관리"):
                        sec["chart_type"] = st.selectbox(
                            "차트 종류", ["Bar", "Line", "Area"], 
                            index=["Bar", "Line", "Area"].index(sec.get("chart_type", "Bar")) if sec.get("chart_type") in ["Bar", "Line", "Area"] else 0,
                            key=f"ch_t*{cp_idx}*{s_idx}"
                        )
                        sec["chart_data"] = st.text_area(
                            "차트 데이터 입력 (항목, 숫자 형태 / 줄바꿈으로 구분)", 
                            value=sec.get("chart_data", ""), 
                            key=f"ch_d*{cp_idx}*{s_idx}",
                            help="예시:\n1분기, 50\n2분기, 80"
                        )
                
                if sec.get("chart_data"):
                    try:
                        raw_chart_data = sec["chart_data"].replace('\\n', '\n')
                        lines_data = [line.strip() for line in raw_chart_data.split('\n') if ',' in line]
                        
                        if lines_data:
                            data_dict = {}
                            for line in lines_data:
                                k, v = line.split(',', 1)
                                clean_val = v.replace(',', '').strip()
                                data_dict[k.strip()] = float(clean_val)
                            
                            if data_dict:
                                df = pd.DataFrame(list(data_dict.values()), index=list(data_dict.keys()), columns=["수치"])
                                ctype = sec.get("chart_type", "Bar")
                                st.markdown("<div style='margin-bottom: 20px;'>", unsafe_allow_html=True)
                                if ctype == "Line":
                                    st.line_chart(df, use_container_width=True)
                                elif ctype == "Area":
                                    st.area_chart(df, use_container_width=True)
                                else:
                                    st.bar_chart(df, use_container_width=True)
                                st.markdown("</div>", unsafe_allow_html=True)
                        else:
                            st.warning("⚠️ 차트 데이터가 없거나 쉼표(,)로 구분되지 않았습니다.")
                    except Exception as e:
                        st.warning("⚠️ 차트 데이터를 올바른 형식(항목, 숫자)으로 입력해주세요. (예: 1분기, 50)")

                # -----------------------------------
                # 3. 텍스트 라인 편집 및 렌더링
                # -----------------------------------
                sec.setdefault("lines", [])
                if edit_enabled:
                    st.caption("📝 본문 문구 스타일 편집 (줄 단위)")
                    new_lines = []
                    for l_idx, line in enumerate(sec["lines"]):
                        lc1, lc2, lc3, lc4 = st.columns([5, 1.5, 1.5, 0.5])
                        l_t = lc1.text_input("T", line["text"], key=f"lt_t*{cp_idx}*{s_idx}*{l_idx}", label_visibility="collapsed")
                        l_s = lc2.number_input("S", 10, 100, int(line["size"]), key=f"lt_s_{cp_idx}*{s_idx}*{l_idx}")
                        l_c = lc3.color_picker("C", line["color"], key=f"lt_c_{cp_idx}*{s_idx}*{l_idx}")
                        if not lc4.button("🗑️", key=f"lt_del_{cp_idx}*{s_idx}*{l_idx}"):
                            new_lines.append({"text": l_t, "size": l_s, "color": l_c})
                    sec["lines"] = new_lines

                    if st.button("➕ 문구 줄 추가", key=f"lt_add_{cp_idx}*{s_idx}"):
                        sec["lines"].append({"text": "새로운 문구", "size": 22, "color": "#1e293b"})
                        st.rerun()
                else:
                    for line in sec.get("lines", []):
                        st.markdown(
                            f'<p class="text-line" style="font-size:{line["size"]}px; color:{line["color"]}; font-weight:bold;">{line["text"]}</p>',
                            unsafe_allow_html=True,
                        )

            with col_side:
                # -----------------------------------
                # 4. 사이드 아이템 (지표/이미지) 관리 및 렌더링
                # -----------------------------------
                sec.setdefault("side_items", [])
                if edit_enabled:
                    sc1, sc2 = st.columns(2)
                    if sc1.button("📊 지표 추가", key=f"si_add_m*{cp_idx}*{s_idx}"):
                        sec["side_items"].append(
                            {"type": "metric", "label": "항목", "value": "0", "color": "#007bff", "label_fs": 14, "label_color": "#64748b", "value_fs": 28}
                        )
                        st.rerun()
                    if sc2.button("🖼️ 그림 추가", key=f"si_add_i*{cp_idx}*{s_idx}"):
                        sec["side_items"].append({"type": "image", "src": None, "width": 350, "image_query": ""})
                        st.rerun()

                for i_idx, item in enumerate(sec["side_items"]):
                    if edit_enabled:
                        with st.expander(f"⚙️ {item.get('label', '아이템')} 편집", expanded=True):
                            if item["type"] == "metric":
                                item["label"] = st.text_input("라벨", item.get("label"), key=f"si_l*{cp_idx}*{s_idx}*{i_idx}")
                                item["value"] = st.text_area("내용", item.get("value"), height=120, key=f"si_v_{cp_idx}*{s_idx}*{i_idx}")
                                ic3, ic4 = st.columns(2)
                                item["label_fs"] = ic3.number_input("라벨크기", 10, 60, int(item.get("label_fs", 14)), key=f"si_lfs_{cp_idx}*{s_idx}*{i_idx}")
                                item["label_color"] = ic4.color_picker("라벨색상", item.get("label_color", "#64748b"), key=f"si_lc_{cp_idx}*{s_idx}*{i_idx}")
                                ic5, ic6 = st.columns(2)
                                item["value_fs"] = ic5.number_input("내용크기", 10, 100, int(item.get("value_fs", 28)), key=f"si_vfs_{cp_idx}*{s_idx}*{i_idx}")
                                item["color"] = ic6.color_picker("내용색상", item.get("color", "#007bff"), key=f"si_vc_{cp_idx}*{s_idx}*{i_idx}")

                            elif item["type"] == "image":
                                current_side = item.get("src", "")
                                display_side = "" if (isinstance(current_side, str) and current_side.startswith("data:image")) else (current_side or "")

                                new_side_url = st.text_input("URL/로컬 파일명", value=display_side, key=f"si_url_{cp_idx}*{s_idx}*{i_idx}")
                                item["image_query"] = st.text_input(
                                    "자동 이미지 검색어(선택)",
                                    value=item.get("image_query", ""),
                                    key=f"si_q_{cp_idx}*{s_idx}*{i_idx}",
                                )

                                siu = st.file_uploader("그림 업로드", type=["png", "jpg", "jpeg", "gif"], key=f"si_iu_{cp_idx}*{s_idx}*{i_idx}")

                                if siu:
                                    item["src"] = f"data:image/png;base64,{base64.b64encode(siu.getvalue()).decode()}"
                                elif new_side_url != display_side:
                                    item["src"] = new_side_url

                                item["width"] = st.slider("너비", 100, 500, int(item.get("width", 350)), key=f"si_iw_{cp_idx}*{s_idx}*{i_idx}")

                            if st.button("🗑️ 삭제", key=f"si_del_{cp_idx}*{s_idx}*{i_idx}"):
                                sec["side_items"].pop(i_idx)
                                st.rerun()

                    if item["type"] == "metric":
                        raw_val = item.get("value", "")
                        if isinstance(raw_val, str):
                            raw_val = raw_val.replace("/n", "\n")
                        fv = (raw_val or "").replace("\n", "<br>")
                        st.markdown(
                            f'<div class="side-slot-card">'
                            f'<div style="font-size:{item.get("label_fs", 14)}px; color:{item.get("label_color", "#64748b")}; margin-bottom:8px;">{item.get("label", "")}</div>'
                            f'<div style="font-size:{item.get("value_fs", 28)}px; font-weight:bold; color:{item.get("color", "#007bff")}; line-height:1.5;">{fv}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                    elif item["type"] == "image":
                        if (not item.get("src")) and item.get("image_query"):
                            item["src"] = get_auto_image_url(item.get("image_query"), w=900, h=700)

                        if item.get("src"):
                            final_side_src = render_image_src(item["src"])
                            st.markdown(
                                f'<div class="side-slot-card">'
                                f'<img src="{final_side_src}" onerror="this.onerror=null; this.src=\'{ERROR_IMG}\';" style="width:{item.get("width", 350)}px; max-width:100%; border-radius:12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);" />'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

# 실행
main_content_area(edit_mode)
