import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import time
import base64
import os
import urllib.parse
import requests
import google.generativeai as genai
from datetime import datetime
import zoneinfo

# ==========================================
# 1. 페이지 설정 및 프리미엄 클린 디자인 CSS
# ==========================================
st.set_page_config(page_title="AI Live Sync Master Builder", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] {
        background-color: #ffffff !important;
    }
    .main [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #ffffff !important;
        border: 1px solid #dee2e6 !important;
        border-radius: 16px !important;
        padding: 35px 40px !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.04) !important;
        margin-bottom: 50px !important;
    }
    [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid #dee2e6 !important;
        padding: 15px !important;
        box-shadow: none !important;
        margin-bottom: 10px !important;
    }
    .side-slot-card {
        padding: 10px 0px;
        margin-bottom: 16px;
    }
    .text-line {
        white-space: pre-wrap;
        word-wrap: break-word;
        line-height: 1.8;
        margin-bottom: 10px;
        color: #334155;
    }
    .voice-panel {
        background: #ffffff;
        border: 1px solid #dee2e6;
        padding: 15px;
        border-radius: 16px;
        text-align: center;
        margin-bottom: 15px;
    }
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
# 3. 표준 양식 및 유틸리티
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
                            {"text": "• 주요 이슈 및 리스크를 점검합니다.", "size": 22, "color": "#1e293b"},
                        ],
                        "side_items": [
                            {"type": "metric", "label": "종합 진행률", "value": "0%", "color": "#007bff", "label_fs": 14, "label_color": "#64748b", "value_fs": 34},
                            {"type": "metric", "label": "핵심 일정", "value": "D-0: \nD-7: ", "color": "#0ea5e9", "label_fs": 14, "label_color": "#64748b", "value_fs": 22},
                        ],
                    }
                ],
            }
        ],
    }

def create_empty_page():
    sample = get_sample_json_guide()["pages"][0]
    return json.loads(json.dumps(sample)) # Deep copy

def adapt_json_format(raw_data):
    if isinstance(raw_data, dict) and "pages" in raw_data:
        if "title" not in raw_data:
            raw_data.update({"title": "AI 기반 보고 플랫폼", "title_fs": 55, "title_color": "#0f172a"})
        return raw_data
    return get_sample_json_guide()

# ==========================================
# 외부 정보 수집 (네이버 검색 API)
# ==========================================
def naver_search_text(query: str, max_results: int = 5) -> str:
    try:
        cid = st.secrets.get("NAVER_CLIENT_ID", "")
        csec = st.secrets.get("NAVER_CLIENT_SECRET", "")
        if not cid or not csec: return ""
        headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec}
        snippets = []
        for endpoint in ["news.json", "encyc.json", "webkr.json"]:
            try:
                r = requests.get(f"https://openapi.naver.com/v1/search/{endpoint}",
                                 params={"query": query, "display": max_results, "sort": "sim"},
                                 headers=headers, timeout=5)
                if r.status_code == 200:
                    for item in r.json().get("items", []):
                        title = item.get("title", "").replace("<b>", "").replace("</b>", "")
                        desc = item.get("description", "").replace("<b>", "").replace("</b>", "")
                        snippets.append(f"- [{title}] {desc}")
            except: continue
        return "\n".join(snippets[:10])
    except: return ""

def naver_search_image(query: str) -> str:
    try:
        cid = st.secrets.get("NAVER_CLIENT_ID", "")
        csec = st.secrets.get("NAVER_CLIENT_SECRET", "")
        if not cid or not csec: return ""
        r = requests.get("https://openapi.naver.com/v1/search/image",
                         params={"query": query, "display": 1, "sort": "sim", "filter": "large"},
                         headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec}, timeout=5)
        if r.status_code == 200:
            items = r.json().get("items", [])
            if items: return items[0].get("link", "")
        return ""
    except: return ""

def get_auto_image_url(query: str, w: int = 1600, h: int = 900) -> str:
    if not query: return ""
    naver_url = naver_search_image(query)
    if naver_url: return naver_url
    tags = urllib.parse.quote(query)
    return f"https://loremflickr.com/{w}/{h}/{tags}?lock={abs(hash(query)) % 1000}"

def render_image_src(img_val):
    if not img_val: return ""
    if img_val.startswith(("http://", "https://", "data:image")): return img_val
    if os.path.isfile(img_val):
        try:
            with open(img_val, "rb") as f:
                ext = img_val.split(".")[-1].lower()
                mime = "image/jpeg" if ext in ["jpg", "jpeg"] else f"image/{ext}"
                return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"
        except: return img_val
    return img_val

# ==========================================
# AI 텍스트 -> JSON 파싱 로직
# ==========================================
def generate_json_from_ai(api_key, context_text):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        now_kst = datetime.now(zoneinfo.ZoneInfo("Asia/Seoul"))
        today_str = now_kst.strftime("%Y년 %m월 %d일")
        
        search_seed = context_text[:100].strip()
        web_context = naver_search_text(search_seed) if search_seed else ""
        
        system_prompt = f"""
        당신은 뛰어난 비즈니스 컨설턴트이자 데이터 구조화 전문가입니다.
        사용자가 제공한 [입력 데이터]를 분석하여 보고서용 JSON 데이터를 생성하십시오.
        오늘 날짜: {today_str}
        외부 검색 컨텍스트: {web_context}
        출력 스키마: {json.dumps(get_sample_json_guide(), ensure_ascii=False)}
        작성 지침: 
        1. 사실관계 환각 금지.
        2. image_query는 반드시 영어 1~3단어로 작성.
        3. 마크다운 없이 순수 JSON만 출력.
        입력 데이터: {context_text}
        """
        response = model.generate_content(system_prompt, generation_config={"response_mime_type": "application/json", "temperature": 0.4})
        return json.loads(response.text)
    except Exception as e:
        return {"error": str(e)}

# ==========================================
# 4. ID 식별 및 음성 시스템
# ==========================================
if "uid" not in st.session_state:
    st.session_state.uid = f"u_{int(time.time() * 1000)}"
if "user_label" not in st.session_state:
    st.session_state.user_label = f"참여자 {int(time.time()) % 100}"

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
                        if(v.uid === 0 && !isMuted) 
                            document.getElementById("level-bar").style.width = Math.min(v.level * 2, 100) + "%";
                        if(isMuted) 
                            document.getElementById("level-bar").style.width = "0%";
                    }});
                }});
                client.on("user-published", async (u, m) => {{
                    await client.subscribe(u, m);
                    if(m === "audio") u.audioTrack.play();
                }});
            }} catch (e) {{ console.error(e); }}
        }}
        document.getElementById("mute").onclick = () => {{
            if (!localTracks.audioTrack) return;
            isMuted = !isMuted;
            localTracks.audioTrack.setEnabled(!isMuted);
            const btn = document.getElementById("mute");
            btn.innerText = isMuted ? "🔇 마이크 : 꺼짐" : "🎤 마이크 : 켜짐";
            isMuted ? btn.classList.add("active") : btn.classList.remove("active");
        }};
        join();
    </script>
    """
    components.html(custom_html, height=160)

@st.fragment(run_every="1s")
def sync_member_list(my_uid, label, voice_active):
    shared_store["active_sessions"][my_uid] = {
        "label": label,
        "last_seen": time.time(),
        "voice_connected": voice_active
    }
    with st.container(border=True):
        st.caption("🟢 실시간 보이스 연결 멤버")
        now = time.time()
        active_now = {uid: info for uid, info in shared_store["active_sessions"].items() if (now - info["last_seen"] < 6)}
        if not active_now:
            st.write("연결된 멤버 없음")
        else:
            for uid, info in active_now.items():
                display = f"{info['label']} {'(나)' if uid == my_uid else ''}"
                st.markdown(f"👤 {display}")

# ==========================================
# 5. 사이드바 (Sidebar) 통제 센터
# ==========================================
with st.sidebar:
    st.title("🚀 AI Live Sync")
    is_reporter = st.toggle("📊 보고자 권한 (편집기능 활성화)", value=False)
    my_label = "💎 보고자" if is_reporter else f"👤 {st.session_state.user_label}"
    voice_connect = st.toggle("🎙️ 마이크 연결", value=False, key="voice_active_toggle")
    
    if voice_connect:
        try:
            agora_id = st.secrets["AGORA_APP_ID"]
            agora_voice_system(agora_id, shared_store["voice_channel"], my_label)
        except:
            st.warning("Agora ID 설정 필요 (secrets.toml)")
    
    sync_member_list(st.session_state.uid, my_label, voice_connect)

    if is_reporter:
        st.divider()
        with st.expander("📝 AI 자동 보고서 생성"):
            ai_api_key = st.secrets.get("GEMINI_API_KEY", "")
            ai_text_input = st.text_area("데이터 입력", placeholder="회의록이나 아이디어를 입력하세요.")
            if st.button("🚀 AI 보고서 생성", use_container_width=True):
                if not ai_api_key: st.error("API Key 필요")
                elif not ai_text_input: st.error("내용 입력 필요")
                else:
                    with st.spinner("AI 작성 중..."):
                        ai_result = generate_json_from_ai(ai_api_key, ai_text_input)
                        if "error" in ai_result: st.error(ai_result["error"])
                        else:
                            shared_store["report_data"] = adapt_json_format(ai_result)
                            shared_store["current_page"] = 0
                            st.rerun()
        
        uploaded_file = st.file_uploader("📂 JSON 수동 로드", type=["json"])
        if uploaded_file:
            shared_store["report_data"] = adapt_json_format(json.load(uploaded_file))
            st.rerun()

    edit_mode = st.toggle("🛠️ 디자인/저작 모드 활성화", value=False) if is_reporter else False

# ==========================================
# 6. 메인 브리핑 엔진
# ==========================================
@st.fragment(run_every="1s")
def main_content_area(edit_enabled):
    # 실시간 채팅
    with st.expander("💬 실시간 상호소통 채팅", expanded=False):
        c1, c2 = st.columns([4, 1])
        msg = c1.text_input("메시지", key="chat_in", label_visibility="collapsed")
        if c2.button("전송") and msg:
            shared_store["chat_history"].append(f"{my_label}: {msg}")
        
        chat_box = "".join([f"<div style='margin-bottom:6px;'>{m}</div>" for m in shared_store["chat_history"][-10:]])
        st.markdown(f"<div style='height:120px; overflow-y:auto; background:#f8f9fa; padding:12px; border-radius:10px; border:1px solid #dee2e6;'>{chat_box}</div>", unsafe_allow_html=True)

    if shared_store["report_data"] is None:
        st.markdown("<div style='text-align:center; padding:150px; color:#64748b;'><h2>좌측 사이드바에서 AI로 자동 생성하거나 파일을 로드하세요.</h2></div>", unsafe_allow_html=True)
        return

    data = shared_store["report_data"]
    cp_idx = shared_store["current_page"]

    # 공통 제목 설정
    if edit_enabled:
        with st.expander("🎨 전체 문서 공통 디자인 설정", expanded=False):
            data["title"] = st.text_input("문서 전체 제목", data.get("title", ""))
            c1, c2 = st.columns(2)
            data["title_fs"] = c1.slider("제목 크기", 20, 120, int(data.get("title_fs", 55)))
            data["title_color"] = c2.color_picker("제목 색상", data.get("title_color", "#0f172a"))

    st.markdown(f'<h1 style="text-align:center; font-size:{data.get("title_fs", 55)}px; color:{data.get("title_color", "#0f172a")};">{data.get("title")}</h1>', unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    # 페이지 네비게이션
    if is_reporter:
        tabs = {i: f"P{i+1}. {pg.get('tab', 'Page')}" for i, pg in enumerate(data["pages"])}
        shared_store["current_page"] = st.radio("이동", list(tabs.keys()), index=cp_idx, format_func=lambda x: tabs[x], horizontal=True)

    p = data["pages"][shared_store["current_page"]]

    if edit_enabled:
        st.write("---")
        c1, c2 = st.columns(2)
        if c1.button("➕ 페이지 추가"):
            data["pages"].append(create_empty_page())
            st.rerun()
        if c2.button("❌ 현재 페이지 삭제") and len(data["pages"]) > 1:
            data["pages"].pop(shared_store["current_page"])
            shared_store["current_page"] = 0
            st.rerun()
        p["tab"] = st.text_input("🏷️ 탭 이름", p.get("tab", ""))
        p["header"] = st.text_input("📌 소제목", p.get("header", ""))

    st.markdown(f'<h2 style="text-align:center; font-size:{p.get("header_fs", 35)}px; color:{p.get("header_color", "#475569")};">{p.get("header")}</h2>', unsafe_allow_html=True)

    # 섹션 렌더링
    ERROR_IMG = "https://placehold.co/800x400/f8fafc/94a3b8?text=Image+Not+Found"
    sections = p.setdefault("sections", [])

    if edit_enabled and st.button("➕ 새로운 섹션 추가"):
        sections.append({
            "title": "새 섹션", "title_fs": 32, "title_color": "#1a1c1e", "col_ratio": 1.5,
            "lines": [{"text": "내용을 입력하세요", "size": 22, "color": "#1e293b"}],
            "main_image": None, "full_width": True, "image_query": "", "chart_type": "Bar", "chart_data": "", "side_items": []
        })
        st.rerun()

    for s_idx, sec in enumerate(sections):
        with st.container(border=True):
            if edit_enabled:
                c1, c2, c3, c4 = st.columns([3, 1, 1, 0.5])
                sec["title"] = c1.text_input("섹션 제목", sec.get("title"), key=f"s_t_{cp_idx}_{s_idx}")
                sec["col_ratio"] = c2.slider("비율", 0.5, 4.0, float(sec.get("col_ratio", 1.5)), key=f"s_r_{cp_idx}_{s_idx}")
                if c4.button("🗑️", key=f"s_d_{cp_idx}_{s_idx}"):
                    sections.pop(s_idx)
                    st.rerun()
            
            st.markdown(f"<h3 style='font-size:{sec.get('title_fs', 32)}px; color:{sec.get('title_color', '#1a1c1e')};'>{sec.get('title')}</h3>", unsafe_allow_html=True)
            
            col_main, col_side = st.columns([sec.get("col_ratio", 1.5), 1], gap="medium")
            
            with col_main:
                # 이미지 관리
                if edit_enabled:
                    with st.expander("🖼️ 이미지/차트 설정"):
                        sec["image_query"] = st.text_input("자동 이미지 검색어(영문)", sec.get("image_query", ""), key=f"i_q_{cp_idx}_{s_idx}")
                        sec["chart_data"] = st.text_area("차트 데이터 (항목,값)", sec.get("chart_data", ""), key=f"c_d_{cp_idx}_{s_idx}")

                if not sec.get("main_image") and sec.get("image_query"):
                    sec["main_image"] = get_auto_image_url(sec["image_query"])
                
                if sec.get("main_image"):
                    st.markdown(f'<div style="text-align:center;"><img src="{render_image_src(sec["main_image"])}" style="width:100%; border-radius:12px; margin-bottom:20px;"></div>', unsafe_allow_html=True)
                
                # 차트 출력
                if sec.get("chart_data"):
                    try:
                        c_lines = [l.split(',') for l in sec["chart_data"].strip().split('\n') if ',' in l]
                        df = pd.DataFrame(c_lines, columns=['항목', '수치'])
                        df['수치'] = pd.to_numeric(df['수치'])
                        st.bar_chart(df.set_index('항목'))
                    except: st.caption("차트 형식: 항목,숫자 (줄바꿈 구분)")

                # 본문 텍스트
                for l_idx, line in enumerate(sec.get("lines", [])):
                    if edit_enabled:
                        lc1, lc2 = st.columns([4, 1])
                        line["text"] = lc1.text_input("내용", line["text"], key=f"l_t_{cp_idx}_{s_idx}_{l_idx}", label_visibility="collapsed")
                        if lc2.button("➖", key=f"l_d_{cp_idx}_{s_idx}_{l_idx}"):
                            sec["lines"].pop(l_idx)
                            st.rerun()
                    st.markdown(f'<p class="text-line" style="font-size:{line["size"]}px; color:{line["color"]}; font-weight:bold;">{line["text"]}</p>', unsafe_allow_html=True)
                
                if edit_enabled and st.button("➕ 줄 추가", key=f"l_a_{cp_idx}_{s_idx}"):
                    sec["lines"].append({"text": "새 줄", "size": 22, "color": "#1e293b"})
                    st.rerun()

            with col_side:
                # 사이드 지표
                if edit_enabled and st.button("➕ 지표 추가", key=f"si_a_{cp_idx}_{s_idx}"):
                    sec.setdefault("side_items", []).append({"type": "metric", "label": "지표", "value": "0"})
                    st.rerun()
                
                for i_idx, item in enumerate(sec.get("side_items", [])):
                    if edit_enabled:
                        item["label"] = st.text_input("라벨", item.get("label"), key=f"si_l_{cp_idx}_{s_idx}_{i_idx}")
                        item["value"] = st.text_input("값", item.get("value"), key=f"si_v_{cp_idx}_{s_idx}_{i_idx}")
                    
                    st.markdown(
                        f'<div class="side-slot-card">'
                        f'<div style="font-size:14px; color:#64748b;">{item.get("label")}</div>'
                        f'<div style="font-size:28px; font-weight:bold; color:#007bff;">{item.get("value")}</div>'
                        f'</div>', unsafe_allow_html=True
                    )

main_content_area(edit_mode)
