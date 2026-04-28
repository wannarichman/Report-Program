import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import time
import base64
import os
import copy
import urllib.parse
import requests
import google.generativeai as genai
from datetime import datetime
import zoneinfo
import re
from io import BytesIO

try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except Exception:
    HAS_PYPDF = False

MAX_DOC_CHARS = 30000  # 무료 모델 토큰 보호용
_FENCE = "`" * 3       # 트리플 백틱 상수 (코드펜스 비교용)


# ==========================================
# 0. 유틸: 업로드 파싱 / 페이지 수 추출 / 코드펜스 제거
# ==========================================
def extract_text_from_upload(uploaded_file):
    """Streamlit UploadedFile -> 평문 텍스트. 지원: txt, md, csv, pdf."""
    if uploaded_file is None:
        return ""
    name = (uploaded_file.name or "").lower()
    raw = uploaded_file.getvalue()

    if name.endswith(".pdf"):
        if not HAS_PYPDF:
            return "[오류] pypdf가 설치되지 않았습니다. requirements.txt에 pypdf>=4.0.0 추가 필요."
        try:
            reader = PdfReader(BytesIO(raw))
            pages_text = []
            for i, page in enumerate(reader.pages):
                try:
                    t = page.extract_text() or ""
                except Exception:
                    t = ""
                if t.strip():
                    pages_text.append(f"--- [PDF p.{i+1}] ---\n{t.strip()}")
            full = "\n\n".join(pages_text).strip()
            if not full:
                return "[알림] PDF에서 텍스트를 추출하지 못했습니다(스캔본/이미지 PDF로 추정)."
            return full[:MAX_DOC_CHARS]
        except Exception as e:
            return f"[PDF 파싱 오류] {e}"

    try:
        text = raw.decode("utf-8", errors="ignore")
    except Exception:
        text = str(raw)
    return text[:MAX_DOC_CHARS]


def extract_requested_page_count(text):
    """사용자 입력에서 'N페이지', 'N장', 'N pages' 패턴을 찾아 정수 반환. 없으면 None."""
    if not text:
        return None
    patterns = [
        r"(\d+)\s*페이지",
        r"(\d+)\s*장(?:으로|짜리|분량)?",
        r"(\d+)\s*pages?",
        r"페이지\s*수\s*(?:는|=|:)\s*(\d+)",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            try:
                n = int(m.group(1))
                if 1 <= n <= 12:
                    return n
            except Exception:
                continue
    return None


def _strip_code_fence(text):
    s = (text or "").strip()
    if s.startswith(_FENCE):
        nl = s.find("\n")
        s = s[nl + 1:] if nl != -1 else s[3:]
    if s.endswith(_FENCE):
        s = s[:-3]
    return s.strip()


# ==========================================
# 1. 페이지 설정 및 CSS
# ==========================================
st.set_page_config(page_title="AI Live Sync Master Builder", layout="wide")

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background-color: #ffffff !important; }
.main [data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #ffffff !important; border: 1px solid #dee2e6 !important;
    border-radius: 16px !important; padding: 35px 40px !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.04) !important; margin-bottom: 50px !important;
}
[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid #dee2e6 !important; padding: 15px !important;
    box-shadow: none !important; margin-bottom: 10px !important;
}
.side-slot-card { padding: 10px 0px; margin-bottom: 16px; }
.text-line { white-space: pre-wrap; word-wrap: break-word; line-height: 1.8; margin-bottom: 10px; color: #334155; }
.voice-panel { background:#fff; border:1px solid #dee2e6; padding:15px; border-radius:16px; text-align:center; margin-bottom:15px; }
.btn-mute { padding:8px 16px; background:#6c757d; color:#fff; border:none; border-radius:8px; cursor:pointer; font-weight:bold; width:100%; }
.btn-mute.active { background:#dc3545; }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 2. 전역 저장소
# ==========================================
@st.cache_resource
def get_global_store():
    return {
        "report_data": None, "current_page": 0, "user_labels": {},
        "chat_history": [], "active_sessions": {},
        "voice_channel": "posco_briefing_room",
    }

shared_store = get_global_store()


# ==========================================
# 3. 표준 양식
# ==========================================
def get_sample_json_guide():
    return {
        "title": "주간 보고 (AI 생성 기반)", "title_fs": 55, "title_color": "#0f172a",
        "pages": [
            {"tab": "요약", "header": "Executive Summary", "header_fs": 35, "header_color": "#475569",
             "sections": [{"title": "핵심 요약", "title_fs": 32, "title_color": "#1a1c1e", "col_ratio": 1.5,
                           "main_image": None, "full_width": True, "image_query": "business meeting",
                           "chart_type": "Bar", "chart_data": "",
                           "lines": [{"text": "• 금주 핵심 성과를 요약합니다.", "size": 24, "color": "#1e293b"},
                                     {"text": "• 주요 이슈 및 리스크를 점검합니다.", "size": 22, "color": "#1e293b"}],
                           "side_items": [{"type": "metric", "label": "종합 진행률", "value": "0%", "color": "#007bff", "label_fs": 14, "label_color": "#64748b", "value_fs": 34}]}]},
            {"tab": "상세 (데이터)", "header": "현황 상세 및 데이터 분석", "header_fs": 35, "header_color": "#475569",
             "sections": [{"title": "데이터 지표 분석", "title_fs": 32, "title_color": "#1a1c1e", "col_ratio": 1.5,
                           "main_image": None, "full_width": True, "image_query": "business analytics chart",
                           "chart_type": "Bar", "chart_data": "1분기, 35\n2분기, 50\n3분기, 42\n4분기, 68",
                           "lines": [{"text": "• 위 데이터 차트를 통해 실적 추이를 확인할 수 있습니다.", "size": 22, "color": "#1e293b"}],
                           "side_items": [{"type": "metric", "label": "정량 지표 요약", "value": "목표 달성률: 85%", "color": "#16a34a", "label_fs": 14, "label_color": "#64748b", "value_fs": 22}]}]},
            {"tab": "액션/리스크", "header": "Action Items & Risks", "header_fs": 35, "header_color": "#475569",
             "sections": [{"title": "Action Items", "title_fs": 32, "title_color": "#1a1c1e", "col_ratio": 1.5,
                           "main_image": None, "full_width": True, "image_query": "",
                           "chart_type": "Bar", "chart_data": "",
                           "lines": [{"text": "1) [담당/기한] 해결 과제 1", "size": 22, "color": "#1e293b"}],
                           "side_items": [{"type": "metric", "label": "주요 Blocker", "value": "없음", "color": "#dc2626", "label_fs": 14, "label_color": "#64748b", "value_fs": 26}]}]},
        ],
    }


def create_empty_page():
    return copy.deepcopy(get_sample_json_guide()["pages"][0])


# ==========================================
# 3-1. JSON 자동 보정
# ==========================================
DEFAULT_LINE = {"text": "", "size": 22, "color": "#1e293b"}
DEFAULT_METRIC = {
    "type": "metric", "label": "항목", "value": "",
    "color": "#007bff", "label_fs": 14, "label_color": "#64748b", "value_fs": 28,
}
DEFAULT_IMAGE_ITEM = {"type": "image", "src": None, "width": 350, "image_query": ""}


def _normalize_section(sec):
    sec.setdefault("title", "섹션")
    sec.setdefault("title_fs", 32)
    sec.setdefault("title_color", "#1a1c1e")
    sec.setdefault("col_ratio", 1.5)
    sec.setdefault("main_image", None)
    sec.setdefault("full_width", True)
    sec.setdefault("image_query", "")
    sec.setdefault("chart_type", "Bar")
    sec.setdefault("chart_data", "")

    raw_lines = sec.get("lines") or []
    fixed_lines = []
    for ln in raw_lines:
        if isinstance(ln, str):
            fixed_lines.append({**DEFAULT_LINE, "text": ln})
        elif isinstance(ln, dict):
            base = dict(DEFAULT_LINE)
            base.update({k: v for k, v in ln.items() if v is not None})
            fixed_lines.append(base)
    sec["lines"] = fixed_lines

    raw_items = sec.get("side_items") or []
    fixed_items = []
    for it in raw_items:
        if not isinstance(it, dict):
            continue
        t = it.get("type", "metric")
        if t == "metric":
            base = dict(DEFAULT_METRIC)
            base.update({k: v for k, v in it.items() if v is not None})
            fixed_items.append(base)
        elif t == "image":
            base = dict(DEFAULT_IMAGE_ITEM)
            base.update({k: v for k, v in it.items() if v is not None})
            fixed_items.append(base)
    sec["side_items"] = fixed_items
    return sec


def adapt_json_format(raw_data):
    if not isinstance(raw_data, dict) or "pages" not in raw_data or not isinstance(raw_data["pages"], list):
        return get_sample_json_guide()
    raw_data.setdefault("title", "AI 자동 생성 보고서")
    raw_data.setdefault("title_fs", 55)
    raw_data.setdefault("title_color", "#0f172a")
    fixed_pages = []
    for pg in raw_data["pages"]:
        if not isinstance(pg, dict):
            continue
        pg.setdefault("tab", "페이지")
        pg.setdefault("header", "")
        pg.setdefault("header_fs", 35)
        pg.setdefault("header_color", "#475569")
        secs = pg.get("sections") or []
        pg["sections"] = [_normalize_section(s) for s in secs if isinstance(s, dict)]
        if not pg["sections"]:
            pg["sections"] = [_normalize_section({"title": pg["header"] or pg["tab"], "lines": []})]
        fixed_pages.append(pg)
    if not fixed_pages:
        return get_sample_json_guide()
    raw_data["pages"] = fixed_pages
    return raw_data


# ==========================================
# 4. 외부 정보 수집 (네이버 검색)
# ==========================================
def naver_search_text(query, max_results=5):
    try:
        cid = st.secrets.get("NAVER_CLIENT_ID", "")
        csec = st.secrets.get("NAVER_CLIENT_SECRET", "")
        if not cid or not csec:
            return ""
        headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec}
        snippets = []
        for endpoint in ["news.json", "encyc.json", "webkr.json"]:
            try:
                r = requests.get(
                    "https://openapi.naver.com/v1/search/" + endpoint,
                    params={"query": query, "display": max_results, "sort": "sim"},
                    headers=headers, timeout=5,
                )
                if r.status_code == 200:
                    for item in r.json().get("items", []):
                        title = item.get("title", "").replace("<b>", "").replace("</b>", "")
                        desc = item.get("description", "").replace("<b>", "").replace("</b>", "")
                        link = item.get("link", "")
                        snippets.append(f"- [{title}] {desc} (출처: {link})")
            except Exception:
                continue
        return "\n".join(snippets[:15])
    except Exception:
        return ""


def naver_search_image(query):
    try:
        cid = st.secrets.get("NAVER_CLIENT_ID", "")
        csec = st.secrets.get("NAVER_CLIENT_SECRET", "")
        if not cid or not csec:
            return ""
        r = requests.get(
            "https://openapi.naver.com/v1/search/image",
            params={"query": query, "display": 5, "sort": "sim", "filter": "large"},
            headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec},
            timeout=5,
        )
        if r.status_code == 200:
            items = r.json().get("items", [])
            if items:
                return items[0].get("link", "")
        return ""
    except Exception:
        return ""


def get_auto_image_url(query, w=1600, h=900):
    if not isinstance(query, str):
        return ""
    q = query.strip()
    if not q:
        return ""
    naver_url = naver_search_image(q)
    if naver_url:
        return naver_url
    tags = ",".join([urllib.parse.quote(t.strip()) for t in q.split(",") if t.strip()])
    lock = abs(hash(q)) % 100000
    return f"https://loremflickr.com/{w}/{h}/{tags}?lock={lock}"


def render_image_src(img_val):
    if not img_val or not isinstance(img_val, str):
        return ""
    val = img_val.strip()
    if not val:
        return ""
    if val.startswith("http://") or val.startswith("https://") or val.startswith("data:image"):
        return val
    if os.path.isfile(val):
        try:
            with open(val, "rb") as f:
                ext = val.split(".")[-1].lower()
                mime = "image/jpeg" if ext in ["jpg", "jpeg"] else f"image/{ext}"
                return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"
        except Exception:
            return val
    return val


# ==========================================
# 5. AI 텍스트 -> JSON
# ==========================================
def generate_json_from_ai(api_key, context_text, requested_pages=None):
    try:
        genai.configure(api_key=api_key)
        try:
            available = []
            for m in genai.list_models():
                methods = getattr(m, "supported_generation_methods", []) or []
                if "generateContent" in methods:
                    available.append(m.name)
        except Exception as e:
            return {"error": f"모델 목록 조회 실패: {e}"}
        if not available:
            return {"error": "이 API 키로 generateContent 가능한 모델이 없습니다."}

        preferred_order = [
            "gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-001",
            "gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-1.5-flash-002",
            "gemini-1.5-pro", "gemini-1.5-pro-latest",
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

        now_kst = datetime.now(zoneinfo.ZoneInfo("Asia/Seoul"))
        today_str = now_kst.strftime("%Y년 %m월 %d일")
        year_str = now_kst.strftime("%Y")
        quarter = (now_kst.month - 1) // 3 + 1

        search_seed = (context_text or "")[:200].replace("\n", " ").strip()
        web_context_parts = []
        if search_seed:
            web_context_parts.append(naver_search_text(search_seed))
            web_context_parts.append(naver_search_text("포스코이앤씨 " + search_seed[:80]))
        web_context = "\n".join([p for p in web_context_parts if p]).strip()
        if not web_context:
            web_context = "(외부 검색 결과 없음 — 입력 데이터 기반으로만 생성)"

        page_count_directive = (
            f"\n[페이지 수 제약]\n- pages 배열은 정확히 {requested_pages}개로 만들 것.\n"
            if requested_pages else ""
        )

        schema_doc = json.dumps(get_sample_json_guide(), ensure_ascii=False, indent=2)

        system_prompt = f"""당신은 포스코이앤씨에서 쓰이는 주간/프로젝트 보고서 JSON 생성기입니다.
입력 데이터를 분석하여 보고서용 JSON을 생성하세요.

[현재 시점]
- 오늘: {today_str}
- 연도: {year_str}년 / 분기: {year_str}년 {quarter}분기
- 과거 연도(2024, 2025년)를 "현재"로 표현 금지.

[출력 형식]
- 순수 JSON 하나만 출력 (마크다운/코드펜스 절대 금지).
- 최상위 키: title, title_fs, title_color, pages.
- 각 페이지는 sections 최소 1개. 각 섹션은 lines 최소 2개, side_items 최소 1개.
{page_count_directive}
[JSON 스키마 - 필드 이름만 참고]
{schema_doc}

[외부 검색 컨텍스트]
{web_context}

[절대 규칙]
1. 환각 금지: 팀명/부서명/인물/프로젝트명/회사명/수치/날짜는 입력 데이터 또는 검색 컨텍스트에 명시된 것만 사용.
2. 정보가 부족하면 비우거나("") 일반적 표현("관련 부서", "담당자") 사용.
3. chart_data는 실제 수치 있을 때만 "항목, 수치\\n항목, 수치" 형태. 없으면 "".
4. image_query는 영어 1~3단어 (한글 금지). 추상어("report", "summary", "data") 금지. 단서 없으면 "".
5. 표준양식의 플레이스홀더 문구를 그대로 복사 금지. 입력 데이터 기반으로 재작성.

[입력 데이터]
{context_text}
"""

        generation_config = {"response_mime_type": "application/json", "temperature": 0.5}
        tried = []
        candidates = [chosen_model] + [n for n in available if n != chosen_model]
        response = None
        for model_name in candidates:
            try:
                model = genai.GenerativeModel(model_name, generation_config=generation_config)
                response = model.generate_content(system_prompt)
                break
            except Exception as e:
                tried.append(f"{model_name}: {e}")
                continue
        if response is None:
            return {"error": f"모든 모델 호출 실패: {tried}"}

        clean_text = _strip_code_fence(response.text or "")
        try:
            parsed = json.loads(clean_text)
        except Exception as e:
            return {"error": f"JSON 파싱 실패: {e}\n동봉(앞 500자): {clean_text[:500]}"}

        n_pages = len(parsed.get("pages", []))
        n_lines_total = sum(
            len(s.get("lines", []))
            for p in parsed.get("pages", [])
            for s in p.get("sections", [])
        )
        if n_pages == 0 or n_lines_total == 0:
            return {"error": "모델이 빈 보고서를 돌려주었습니다. 입력을 더 자세히 적어주세요."}
        return parsed

    except Exception as e:
        return {"error": str(e)}


# ==========================================
# 6. ID 식별 및 Agora 음성
# ==========================================
if "uid" not in st.session_state:
    url_uid = st.query_params.get("uid")
    if url_uid:
        st.session_state.uid = url_uid
    else:
        new_uid = f"u{int(time.time() * 1000)}"
        st.session_state.uid = new_uid
        st.query_params["uid"] = new_uid

if "user_label" not in st.session_state:
    active_now = len([s for s in shared_store["active_sessions"].values() if time.time() - s["last_seen"] < 10])
    st.session_state.user_label = f"참여자 {active_now + 1}"


def agora_voice_system(app_id, channel, user_label):
    custom_html = f"""
<script src="https://download.agora.io/sdk/release/AgoraRTC_N-4.11.0.js"></script>
<div class="voice-panel">
  <div id="v-status" style="font-size:13px; font-weight:700; margin-bottom:8px; color:#1e293b;">🎙 {user_label}</div>
  <div style="width:100%; height:10px; background:#e2e8f0; border-radius:5px; margin-bottom:12px; overflow:hidden;">
    <div id="level-bar" style="width:0%; height:100%; background:#28a745; transition:width 0.05s;"></div>
  </div>
  <button id="mute" class="btn-mute">🎤 마이크 : 켜짐</button>
</div>
<script>
let client = AgoraRTC.createClient( mode: "rtc", codec: "vp8" );
let localTracks =  audioTrack: null ;
let isMuted = false;

async function join() {{
  try {{
    await client.join("{app_id}", "{channel}", null, null);
    localTracks.audioTrack = await AgoraRTC.createMicrophoneAudioTrack();
    await client.publish([localTracks.audioTrack]);
    client.enableAudioVolumeIndicator();
    client.on("volume-indicator", (vs) => {{
      vs.forEach((v) => {{
        if (v.uid === 0 && !isMuted) 
          document.getElementById("level-bar").style.width = Math.min(v.level * 2, 100) + "%";
        
        if (isMuted) 
          document.getElementById("level-bar").style.width = "0%";
        
      }});
    }});
    client.on("user-published", async (u, m) => 
      await client.subscribe(u, m);
      if (m === "audio") u.audioTrack.play();
    );
  }} catch (e)  console.error(e); 
}}

function toggleMute() {{
  if (!localTracks.audioTrack) return;
  isMuted = !isMuted;
  localTracks.audioTrack.setEnabled(!isMuted);
  const btn = document.getElementById("mute");
  if (isMuted) 
    btn.innerText = "🔇 마이크 : 꺼짐";
    btn.classList.add("active");
   else 
    btn.innerText = "🎤 마이크 : 켜짐";
    btn.classList.remove("active");
  
}}

join();
document.getElementById("mute").onclick = toggleMute;
</script>
"""
    components.html(custom_html, height=160)


@st.fragment(run_every="1s")
def sync_member_list(my_uid):
    with st.container(border=True):
        st.caption("실시간 보이스 연결 멤버")
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
                display_name = label + (" (나)" if temp_sessions[label] else "")
                st.markdown(f"🟢 {display_name}")


# ==========================================
# 7. 사이드바
# ==========================================
with st.sidebar:
    st.title("AI Live Sync")
    is_reporter = st.toggle("보고자 권한 (편집기능 활성화)", value=False)
    my_label = "보고자" if is_reporter else f"{st.session_state.user_label}"
    voice_connect = st.toggle("마이크 연결", value=False, key="voice_active_toggle")

    if voice_connect:
        try:
            agora_id = st.secrets["AGORA_APP_ID"]
            agora_voice_system(agora_id, shared_store["voice_channel"], my_label)
        except Exception:
            st.warning("Agora ID 설정 필요")

    sync_member_list(st.session_state.uid)

    if is_reporter:
        st.divider()
        with st.expander("AI 자동 보고서 생성", expanded=False):
            try:
                ai_api_key = st.secrets["GEMINI_API_KEY"]
            except Exception:
                ai_api_key = ""
                st.warning("GEMINI_API_KEY 설정 필요")
            ai_text_input = st.text_area(
                "텍스트 데이터 입력 (예: '5페이지로 안전 보고서 만들어줘. ...')"
            )
            ai_file_input = st.file_uploader(
                "또는 문서 업로드 (PDF / TXT / CSV / MD)",
                type=["pdf", "txt", "csv", "md"],
            )

            if st.button("AI 보고서 생성", use_container_width=True):
                if not ai_api_key:
                    st.error("API Key 필요")
                else:
                    context = ai_text_input or ""
                    if ai_file_input:
                        doc_text = extract_text_from_upload(ai_file_input)
                        context += f"\n\n[첨부 문서: {ai_file_input.name}]\n{doc_text}"

                    if not context.strip():
                        st.error("텍스트나 문서를 입력해주세요.")
                    else:
                        req_pages = extract_requested_page_count(ai_text_input)
                        with st.spinner("생성 중..." + (f" ({req_pages}페이지로)" if req_pages else "")):
                            ai_result = generate_json_from_ai(ai_api_key, context, requested_pages=req_pages)
                            if "error" in ai_result:
                                st.error(f"생성 실패: {ai_result['error']}")
                            else:
                                shared_store["report_data"] = adapt_json_format(ai_result)
                                shared_store["current_page"] = 0
                                st.success("완료!")
                                time.sleep(1)
                                st.rerun()

        st.write("---")
        st.download_button(
            "표준 양식 다운로드",
            data=json.dumps(get_sample_json_guide(), indent=4, ensure_ascii=False),
            file_name="Report_Standard_Template.json",
            mime="application/json",
            use_container_width=True,
        )

        uploaded_file = st.file_uploader("JSON 수동 로드", type=["json"])
        if uploaded_file:
            if st.session_state.get("last_uploaded_id") != uploaded_file.file_id:
                shared_store["report_data"] = adapt_json_format(json.loads(uploaded_file.read().decode("utf-8")))
                st.session_state["last_uploaded_id"] = uploaded_file.file_id
                shared_store["current_page"] = 0

        if st.button("전체 데이터 초기화"):
            shared_store.update({"report_data": None, "current_page": 0, "chat_history": [], "active_sessions": {}})
            st.session_state.pop("last_uploaded_id", None)
            st.rerun()

        if shared_store["report_data"]:
            st.download_button(
                "최종 리포트 저장",
                data=json.dumps(shared_store["report_data"], indent=4, ensure_ascii=False),
                file_name="My_Final_Report.json",
                use_container_width=True,
            )

        edit_mode = st.toggle("편집 모드", value=False)
    else:
        edit_mode = False


# ==========================================
# 8. 메인 브리핑 엔진
# ==========================================
@st.fragment(run_every="1s")
def main_content_area(edit_enabled):
    shared_store["active_sessions"][st.session_state.uid] = {
        "label": my_label,
        "last_seen": time.time(),
        "voice_connected": st.session_state.get("voice_active_toggle", False),
    }

    with st.expander("실시간 채팅", expanded=False):
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
            "<div style='text-align:center; padding:150px; color:#64748b;'><h2>좌측에서 AI 생성 또는 파일 로드</h2></div>",
            unsafe_allow_html=True,
        )
        if edit_enabled and st.button("새 보고서 시작"):
            shared_store["report_data"] = adapt_json_format({})
            st.rerun()
        return

    data = shared_store["report_data"]
    cp_idx = shared_store["current_page"]

    if edit_enabled:
        with st.expander("문서 공통 제목 설정", expanded=True):
            data["title"] = st.text_input("문서 제목", data.get("title", ""), key="global_title_input")
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
        if pc1.button("페이지 추가"):
            data["pages"].insert(cp_idx + 1, create_empty_page())
            shared_store["current_page"] += 1
            st.rerun()
        if pc2.button("페이지 삭제") and len(data["pages"]) > 1:
            data["pages"].pop(cp_idx)
            shared_store["current_page"] = max(0, cp_idx - 1)
            st.rerun()

    if is_reporter:
        tabs = {i: f"P{i+1}. {pg.get('tab', '')}" for i, pg in enumerate(data["pages"])}
        shared_store["current_page"] = st.radio(
            "이동", list(tabs.keys()),
            index=shared_store["current_page"],
            format_func=lambda x: tabs[x],
            horizontal=True,
        )

    if edit_enabled:
        p["tab"] = st.text_input("탭 이름", p.get("tab", ""), key=f"tab_edit_{cp_idx}")
        with st.expander("소제목 설정"):
            p["header"] = st.text_input("소제목", p.get("header", ""), key=f"ph_input_{cp_idx}")
            hc1, hc2 = st.columns(2)
            p["header_fs"] = hc1.slider("크기", 10, 150, int(p.get("header_fs", 35)), key=f"phfs_{cp_idx}")
            p["header_color"] = hc2.color_picker("색상", p.get("header_color", "#475569"), key=f"phc_{cp_idx}")

    st.markdown(
        f'<h2 style="text-align:center; font-size:{p.get("header_fs", 35)}px; color:{p.get("header_color", "#475569")}; margin-bottom:30px;">{p.get("header", "")}</h2>',
        unsafe_allow_html=True,
    )

    sections = p.setdefault("sections", [])
    if edit_enabled and st.button("섹션 추가", key=f"add_sec_btn_{cp_idx}"):
        sections.append({
            "title": "새 섹션", "title_fs": 32, "title_color": "#1a1c1e", "col_ratio": 1.5,
            "lines": [{"text": "내용", "size": 22, "color": "#1e293b"}],
            "main_image": None, "full_width": True, "image_query": "",
            "chart_type": "Bar", "chart_data": "", "side_items": [],
        })
        st.rerun()

    ERROR_IMG = "https://placehold.co/800x400/f8fafc/94a3b8?text=Image+Not+Found"

    for s_idx, sec in enumerate(sections):
        with st.container(border=True):
            if edit_enabled:
                sc1, sc2, sc3, sc4, sc5 = st.columns([2.5, 0.8, 0.8, 1.2, 0.5])
                sec["title"] = sc1.text_input("섹션 제목", sec.get("title", ""), key=f"st_t_{cp_idx}_{s_idx}")
                sec["title_fs"] = sc2.number_input("크기", 10, 80, int(sec.get("title_fs", 32)), key=f"st_fs_{cp_idx}_{s_idx}")
                sec["title_color"] = sc3.color_picker("색상", sec.get("title_color", "#1a1c1e"), key=f"st_c_{cp_idx}_{s_idx}")
                sec["col_ratio"] = sc4.slider("비율", 1.0, 4.0, float(sec.get("col_ratio", 1.5)), 0.1, key=f"st_r_{cp_idx}_{s_idx}")
                if sc5.button("X", key=f"st_del_{cp_idx}_{s_idx}"):
                    sections.pop(s_idx)
                    st.rerun()

            st.markdown(
                f"<h3 style='font-size:{sec.get('title_fs', 32)}px; color:{sec.get('title_color', '#1a1c1e')}; margin-bottom:20px; padding-bottom:12px; border-bottom:2px solid #f8f9fa;'>{sec.get('title')}</h3>",
                unsafe_allow_html=True,
            )

            col_main, col_side = st.columns([sec.get("col_ratio", 1.5), 1], gap="medium")

            with col_main:
                if edit_enabled:
                    with st.expander("이미지 관리"):
                        current_img = sec.get("main_image", "")
                        display_img_url = "" if (isinstance(current_img, str) and current_img.startswith("data:image")) else (current_img or "")
                        new_img_url = st.text_input("URL", value=display_img_url, key=f"simg_url_{cp_idx}_{s_idx}")
                        sec["image_query"] = st.text_input("자동 검색어 (영어)", value=sec.get("image_query", ""), key=f"simg_q_{cp_idx}_{s_idx}")
                        img_f = st.file_uploader("업로드", type=["png", "jpg", "jpeg", "gif"], key=f"simg_f_{cp_idx}_{s_idx}")
                        if img_f:
                            sec["main_image"] = f"data:image/png;base64,{base64.b64encode(img_f.getvalue()).decode()}"
                        elif new_img_url != display_img_url:
                            sec["main_image"] = new_img_url
                        sec["full_width"] = st.toggle("너비 채우기", value=sec.get("full_width", True), key=f"fw_{cp_idx}_{s_idx}")
                        if not sec["full_width"]:
                            sec["img_width"] = st.slider("너비", 100, 1200, int(sec.get("img_width", 750)), key=f"sw_{cp_idx}_{s_idx}")
                        if st.button("그림 삭제", key=f"simg_del_{cp_idx}_{s_idx}"):
                            sec["main_image"] = None
                            st.rerun()

                if (not sec.get("main_image")) and sec.get("image_query"):
                    sec["main_image"] = get_auto_image_url(sec.get("image_query"))

                if sec.get("main_image"):
                    final_src = render_image_src(sec["main_image"])
                    style = "width:100%;" if sec.get("full_width", True) else f"width:{sec.get('img_width', 750)}px; max-width:100%;"
                    st.markdown(
                        f'<div style="text-align:center;"><img src="{final_src}" onerror="this.onerror=null; this.src=\'{ERROR_IMG}\';" style="{style} border-radius:12px; margin-bottom:20px; box-shadow:0 4px 12px rgba(0,0,0,0.05);" /></div>',
                        unsafe_allow_html=True,
                    )

                if edit_enabled:
                    with st.expander("차트 관리"):
                        sec["chart_type"] = st.selectbox(
                            "종류", ["Bar", "Line", "Area"],
                            index=["Bar", "Line", "Area"].index(sec.get("chart_type", "Bar")) if sec.get("chart_type") in ["Bar", "Line", "Area"] else 0,
                            key=f"ch_t_{cp_idx}_{s_idx}",
                        )
                        sec["chart_data"] = st.text_area("데이터 (항목, 숫자)", value=sec.get("chart_data", ""), key=f"ch_d_{cp_idx}_{s_idx}")

                if sec.get("chart_data"):
                    try:
                        raw_chart = sec["chart_data"].replace("\\n", "\n")
                        lines_data = [line.strip() for line in raw_chart.split("\n") if "," in line]
                        if lines_data:
                            data_dict = {}
                            for line in lines_data:
                                k, v = line.split(",", 1)
                                data_dict[k.strip()] = float(v.replace(",", "").strip())
                            if data_dict:
                                df = pd.DataFrame(list(data_dict.values()), index=list(data_dict.keys()), columns=["수치"])
                                ctype = sec.get("chart_type", "Bar")
                                if ctype == "Line":
                                    st.line_chart(df, use_container_width=True)
                                elif ctype == "Area":
                                    st.area_chart(df, use_container_width=True)
                                else:
                                    st.bar_chart(df, use_container_width=True)
                    except Exception:
                        st.warning("차트 데이터 형식 오류")

                sec.setdefault("lines", [])
                if edit_enabled:
                    st.caption("본문 편집")
                    new_lines = []
                    for l_idx, line in enumerate(sec["lines"]):
                        lc1, lc2, lc3, lc4 = st.columns([5, 1.5, 1.5, 0.5])
                        l_t = lc1.text_input("T", line["text"], key=f"lt_t_{cp_idx}_{s_idx}_{l_idx}", label_visibility="collapsed")
                        l_s = lc2.number_input("S", 10, 100, int(line["size"]), key=f"lt_s_{cp_idx}_{s_idx}_{l_idx}")
                        l_c = lc3.color_picker("C", line["color"], key=f"lt_c_{cp_idx}_{s_idx}_{l_idx}")
                        if not lc4.button("X", key=f"lt_del_{cp_idx}_{s_idx}_{l_idx}"):
                            new_lines.append({"text": l_t, "size": l_s, "color": l_c})
                    sec["lines"] = new_lines
                    if st.button("줄 추가", key=f"lt_add_{cp_idx}_{s_idx}"):
                        sec["lines"].append({"text": "새 문구", "size": 22, "color": "#1e293b"})
                        st.rerun()
                else:
                    for line in sec.get("lines", []):
                        st.markdown(
                            f'<p class="text-line" style="font-size:{line["size"]}px; color:{line["color"]}; font-weight:bold;">{line["text"]}</p>',
                            unsafe_allow_html=True,
                        )

            with col_side:
                sec.setdefault("side_items", [])
                if edit_enabled:
                    sca, scb = st.columns(2)
                    if sca.button("지표 추가", key=f"si_add_m_{cp_idx}_{s_idx}"):
                        sec["side_items"].append({"type": "metric", "label": "항목", "value": "0", "color": "#007bff", "label_fs": 14, "label_color": "#64748b", "value_fs": 28})
                        st.rerun()
                    if scb.button("그림 추가", key=f"si_add_i_{cp_idx}_{s_idx}"):
                        sec["side_items"].append({"type": "image", "src": None, "width": 350, "image_query": ""})
                        st.rerun()

                for i_idx, item in enumerate(sec["side_items"]):
                    if edit_enabled:
                        with st.expander(f"{item.get('label', '아이템')} 편집", expanded=True):
                            if item["type"] == "metric":
                                item["label"] = st.text_input("라벨", item.get("label"), key=f"si_l_{cp_idx}_{s_idx}_{i_idx}")
                                item["value"] = st.text_area("내용", item.get("value"), height=120, key=f"si_v_{cp_idx}_{s_idx}_{i_idx}")
                                ic3, ic4 = st.columns(2)
                                item["label_fs"] = ic3.number_input("라벨크기", 10, 60, int(item.get("label_fs", 14)), key=f"si_lfs_{cp_idx}_{s_idx}_{i_idx}")
                                item["label_color"] = ic4.color_picker("라벨색상", item.get("label_color", "#64748b"), key=f"si_lc_{cp_idx}_{s_idx}_{i_idx}")
                                ic5, ic6 = st.columns(2)
                                item["value_fs"] = ic5.number_input("내용크기", 10, 100, int(item.get("value_fs", 28)), key=f"si_vfs_{cp_idx}_{s_idx}_{i_idx}")
                                item["color"] = ic6.color_picker("내용색상", item.get("color", "#007bff"), key=f"si_vc_{cp_idx}_{s_idx}_{i_idx}")
                            elif item["type"] == "image":
                                current_side = item.get("src", "")
                                display_side = "" if (isinstance(current_side, str) and current_side.startswith("data:image")) else (current_side or "")
                                new_side_url = st.text_input("URL", value=display_side, key=f"si_url_{cp_idx}_{s_idx}_{i_idx}")
                                item["image_query"] = st.text_input("검색어(영어)", value=item.get("image_query", ""), key=f"si_q_{cp_idx}_{s_idx}_{i_idx}")
                                siu = st.file_uploader("업로드", type=["png", "jpg", "jpeg", "gif"], key=f"si_iu_{cp_idx}_{s_idx}_{i_idx}")
                                if siu:
                                    item["src"] = f"data:image/png;base64,{base64.b64encode(siu.getvalue()).decode()}"
                                elif new_side_url != display_side:
                                    item["src"] = new_side_url
                                item["width"] = st.slider("너비", 100, 500, int(item.get("width", 350)), key=f"si_iw_{cp_idx}_{s_idx}_{i_idx}")
                            if st.button("삭제", key=f"si_del_{cp_idx}_{s_idx}_{i_idx}"):
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
                                f'<img src="{final_side_src}" onerror="this.onerror=null; this.src=\'{ERROR_IMG}\';" style="width:{item.get("width", 350)}px; max-width:100%; border-radius:12px; box-shadow:0 4px 12px rgba(0,0,0,0.08);" />'
                                f'</div>',
                                unsafe_allow_html=True,
                            )


# 실행
main_content_area(edit_mode)
