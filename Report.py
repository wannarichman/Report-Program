import streamlit as st
import streamlit.components.v1 as components
import json
import time
import base64

# 1. 페이지 설정 및 디자인 프레임워크 (테두리 및 섹션 구분 강화)
st.set_page_config(page_title="POSCO E&C AI Live Sync Master", layout="wide")

st.markdown("""
    <style>
    .section-container {
        border: 2px solid #e9ecef; padding: 30px; border-radius: 20px;
        background-color: #ffffff; margin-bottom: 35px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }
    .side-slot-card {
        background-color: #f8f9fa; padding: 15px; border-radius: 12px;
        border: 1px solid #dee2e6; border-left: 6px solid #007bff; margin-bottom: 12px;
    }
    .text-line { white-space: pre-wrap; word-wrap: break-word; line-height: 1.7; margin-bottom: 8px; }
    </style>
    """, unsafe_allow_html=True)

# 2. [전역 저장소]
@st.cache_resource
def get_global_store():
    return {
        "report_data": None, "current_page": 0, "user_labels": {}, 
        "sync_version": 0, "chat_history": [], "voice_active_users_list": [],
        "voice_channel": "posco_briefing_room"
    }

shared_store = get_global_store()

# --- [데이터 보정 및 기본 구조] ---
def adapt_json_format(raw_data):
    if isinstance(raw_data, dict) and "pages" in raw_data: return raw_data
    return {"pages": [create_empty_page()]}

def create_empty_page():
    return {
        "tab": "새 페이지", "header": "제목을 입력하세요", "header_fs": 40, "header_color": "#1a1c1e",
        "sections": [{"title": "새 섹션", "lines": [{"text": "내용", "size": 22, "color": "#000000"}], "main_image": None, "side_items": []}]
    }

# --- [ID 식별 및 음성 시스템 (Agora)] ---
if "user_label" not in st.session_state:
    uid = st.query_params.get("uid", f"u_{int(time.time()*1000)}")
    st.query_params["uid"] = uid
    label = shared_store["user_labels"].get(uid, f"참여자 {len(shared_store['user_labels']) + 1}")
    shared_store["user_labels"][uid] = label
    st.session_state.user_label = label

def agora_voice_system(app_id, channel, user_label):
    custom_html = f"""
    <script src="https://download.agora.io/sdk/release/AgoraRTC_N-4.11.0.js"></script>
    <div style="padding: 10px; background: #f1f3f6; border-radius: 15px; text-align: center;">
        <div id="v-status" style="font-size: 13px; font-weight: 700; margin-bottom: 5px;">🎙️ 음성 접속</div>
        <div style="width: 100%; height: 8px; background: #e9ecef; border-radius: 4px; margin-bottom: 8px; overflow: hidden;">
            <div id="level-bar" style="width: 0%; height: 100%; background: #28a745; transition: width 0.05s;"></div>
        </div>
        <button id="join" style="padding: 6px 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">🔊 연결</button>
        <button id="mute" style="padding: 6px 12px; background: #6c757d; color: white; border: none; border-radius: 4px; cursor: pointer; display: none;">🔇 끄기</button>
    </div>
    <script>
        let client = AgoraRTC.createClient({{ mode: "rtc", codec: "vp8" }});
        let localTracks = {{ audioTrack: null }};
        let isMuted = false;
        client.enableAudioVolumeIndicator();
        async function join() {{
            try {{
                await client.join("{app_id}", "{channel}", null, null);
                localTracks.audioTrack = await AgoraRTC.createMicrophoneAudioTrack();
                await client.publish([localTracks.audioTrack]);
                document.getElementById("join").style.display = "none";
                document.getElementById("mute").style.display = "inline";
                client.on("volume-indicator", (vs) => {{ vs.forEach((v) => {{ if(v.uid === 0) document.getElementById("level-bar").style.width = Math.min(v.level * 2, 100) + "%"; }}); }});
                client.on("user-published", async (u, m) => {{ await client.subscribe(u, m); if(m === "audio") u.audioTrack.play(); }});
            }} catch (e) {{ console.error(e); }}
        }}
        document.getElementById("join").onclick = join;
        document.getElementById("mute").onclick = () => {{ isMuted = !isMuted; localTracks.audioTrack.setEnabled(!isMuted); document.getElementById("mute").innerText = isMuted ? "🎤 켜기" : "🔇 끄기"; }};
    </script>
    """
    components.html(custom_html, height=130)

# --- 사이드바: 통합 제어 ---
with st.sidebar:
    st.title("🎙️ AI Live Sync")
    is_reporter = st.toggle("🔑 보고자 권한", value=False)
    my_label = "📢 보고자" if is_reporter else f"👤 {st.session_state.user_label}"
    st.info(f"📍 접속: **{my_label}**")
    
    try:
        agora_id = st.secrets["AGORA_APP_ID"]
        agora_voice_system(agora_id, shared_store["voice_channel"], my_label)
    except: st.warning("⚠️ Agora ID 필요")

    if is_reporter:
        st.divider()
        if shared_store["report_data"]:
            st.download_button("📥 최종 스타일 JSON 저장", data=json.dumps(shared_store["report_data"], indent=4, ensure_ascii=False), file_name="Master_Final.json", use_container_width=True)
        uploaded_file = st.file_uploader("📂 JSON 로드", type=['json'])
        if uploaded_file: shared_store["report_data"] = adapt_json_format(json.loads(uploaded_file.read().decode("utf-8")))
        if st.button("🚨 전체 초기화"):
            shared_store.update({"report_data": None, "current_page": 0, "chat_history": []})
            st.rerun()
        edit_mode = st.toggle("📝 디자인/저작 모드 활성화", value=False)
    else: edit_mode = False

# --- [메인 브리핑 엔진] ---
@st.fragment(run_every="1s")
def main_content_area(edit_enabled):
    # 채팅 시스템
    with st.expander("💬 실시간 상호소통 채팅", expanded=False):
        c1, c2 = st.columns([4, 1])
        msg = c1.text_input("메시지", key="chat_in", label_visibility="collapsed")
        if c2.button("전송") and msg: shared_store["chat_history"].append(f"**{my_label}**: {msg}")
        chat_box = "".join([f"<div style='margin-bottom:5px;'>{m}</div>" for m in shared_store["chat_history"][-10:]])
        st.markdown(f"<div style='height:100px; overflow-y:auto; background:#f8f9fa; padding:10px; border-radius:8px;'>{chat_box}</div>", unsafe_allow_html=True)

    if shared_store["report_data"] is None:
        if edit_enabled and st.button("📄 새 보고서 생성"):
            shared_store["report_data"] = {"pages": [create_empty_page()]}; st.rerun()
        st.warning("📂 파일을 로드하거나 보고서를 생성하세요.")
        return

    data = shared_store["report_data"]
    p = data['pages'][shared_store["current_page"]]
    
    # 페이지/내비게이션 관리
    if edit_enabled:
        pc1, pc2 = st.columns([1, 5])
        if pc1.button("➕ 페이지 추가"):
            data['pages'].insert(shared_store["current_page"] + 1, create_empty_page())
            shared_store["current_page"] += 1; st.rerun()
        if pc2.button("🗑️ 페이지 삭제") and len(data['pages']) > 1:
            data['pages'].pop(shared_store["current_page"])
            shared_store["current_page"] = max(0, shared_store["current_page"] - 1); st.rerun()

    if is_reporter:
        tabs = {i: f"P{i+1}. {pg.get('tab', '')}" for i, pg in enumerate(data['pages'])}
        shared_store["current_page"] = st.radio("📑 이동", list(tabs.keys()), index=shared_store["current_page"], format_func=lambda x: tabs[x], horizontal=True)
        if edit_enabled: p['tab'] = st.text_input("🔖 탭 이름", p.get('tab', ''), key=f"t_ed_{shared_store['current_page']}")

    # 대제목 렌더링
    if edit_enabled:
        p['header'] = st.text_input("📌 대제목", p.get('header', ''))
        c1, c2 = st.columns(2)
        p['header_fs'] = c1.slider("제목 크기", 10, 100, int(p.get('header_fs', 40)))
        p['header_color'] = c2.color_picker("제목 색상", p.get('header_color', '#1a1c1e'))

    st.markdown(f'<h1 style="text-align:center; font-size:{p.get("header_fs", 40)}px; color:{p.get("header_color", "#1a1c1e")};">{p.get("header")}</h1>', unsafe_allow_html=True)
    st.divider()

    # --- [섹션 루프: 세로형 블록 시스템] ---
    sections = p.setdefault('sections', [])
    if edit_enabled and st.button("➕ 새로운 세로 섹션 블록 추가"):
        sections.append({"title": "새 섹션", "lines": [{"text": "내용", "size": 22, "color": "#000000"}], "main_image": None, "side_items": []})

    for s_idx, sec in enumerate(sections):
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        col_main, col_side = st.columns([2.5, 1], gap="large")
        
        with col_main:
            if edit_enabled:
                sec['title'] = st.text_input(f"섹션 {s_idx+1} 제목", sec.get('title', ''), key=f"st_{s_idx}")
                # [좌측 본문 그림 추가 기능]
                with st.expander("🖼️ 좌측 섹션 내 그림 관리"):
                    img_f = st.file_uploader(f"그림 업로드 (섹션 {s_idx+1})", type=['png', 'jpg'], key=f"simg_{s_idx}")
                    if img_f: sec['main_image'] = f"data:image/png;base64,{base64.b64encode(img_f.getvalue()).decode()}"
                    if st.button("🗑️ 그림 삭제", key=f"simg_del_{s_idx}"): sec['main_image'] = None
                    sec['img_width'] = st.slider("그림 너비", 100, 1000, int(sec.get('img_width', 700)), key=f"sw_{s_idx}")
            
            # 본문 상단 섹션 제목
            st.markdown(f"### {sec.get('title')}")
            
            # 좌측 섹션 그림 렌더링
            if sec.get('main_image'):
                st.image(sec['main_image'], width=int(sec.get('img_width', 700)))
            
            # [줄 단위 텍스트 편집 및 렌더링]
            if edit_enabled:
                st.caption("📝 본문 문구 스타일 편집")
                new_lines = []
                for l_idx, line in enumerate(sec.get('lines', [])):
                    lc1, lc2, lc3, lc4 = st.columns([5, 1.5, 1.5, 0.5])
                    l_t = lc1.text_input(f"T_{l_idx}", line['text'], key=f"lt_{s_idx}_{l_idx}", label_visibility="collapsed")
                    l_s = lc2.number_input("S", 10, 100, int(line['size']), key=f"ls_{s_idx}_{l_idx}")
                    l_c = lc3.color_picker("C", line['color'], key=f"lc_{s_idx}_{l_idx}")
                    if not lc4.button("🗑️", key=f"ld_{s_idx}_{l_idx}"):
                        new_lines.append({"text": l_t, "size": l_s, "color": l_c})
                sec['lines'] = new_lines
                if st.button("➕ 문구 줄 추가", key=f"la_{s_idx}"):
                    sec['lines'].append({"text": "새 문구", "size": 22, "color": "#000000"}); st.rerun()
            else:
                for line in sec.get('lines', []):
                    st.markdown(f'<p class="text-line" style="font-size:{line["size"]}px; color:{line["color"]};">{line["text"]}</p>', unsafe_allow_html=True)

        with col_side:
            sec.setdefault('side_items', [])
            if edit_enabled:
                sc1, sc2 = st.columns(2)
                if sc1.button("📊 지표", key=f"am_{s_idx}"): sec['side_items'].append({"type":"metric", "label":"항목", "value":"0", "color": "#007bff"})
                if sc2.button("🖼️ 그림", key=f"ai_{s_idx}"): sec['side_items'].append({"type":"image", "src":None, "width": 350})
            
            for i_idx, item in enumerate(sec['side_items']):
                st.markdown('<div class="side-slot-card">', unsafe_allow_html=True)
                if edit_enabled:
                    if st.button("🗑️", key=f"sdel_{s_idx}_{i_idx}"): sec['side_items'].pop(i_idx); st.rerun()
                    if item['type'] == "metric":
                        item['label'], item['value'] = st.text_input("명", item['label'], key=f"il_{s_idx}_{i_idx}"), st.text_input("값", item['value'], key=f"iv_{s_idx}_{i_idx}")
                        item['color'] = st.color_picker("색", item.get('color', '#007bff'), key=f"ic_{s_idx}_{i_idx}")
                    elif item['type'] == "image":
                        if st.file_uploader("그림", key=f"siu_{s_idx}_{i_idx}"):
                            item['src'] = f"data:image/png;base64,{base64.b64encode(img_f.getvalue()).decode()}"
                
                if item['type'] == "metric":
                    st.markdown(f"<small>{item['label']}</small><div style='font-size:26px; font-weight:bold; color:{item.get('color', '#007bff')};'>{item['value']}</div>", unsafe_allow_html=True)
                elif item['type'] == "image" and item.get('src'):
                    st.image(item['src'], width=int(item.get('width', 350)))
                st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

main_content_area(edit_mode)
