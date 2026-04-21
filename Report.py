import streamlit as st
import streamlit.components.v1 as components
import json
import time
import base64

# 1. 페이지 설정 및 디자인 프레임워크 (UI 시각적 구분 극대화)
st.set_page_config(page_title="POSCO E&C AI Live Sync Master", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f4f7f9; }
    /* 섹션 통합 뭉치: 테두리 및 입체감 강화 */
    .section-container {
        border: 2px solid #cfd4da; padding: 40px; border-radius: 25px;
        background-color: #ffffff; margin-bottom: 50px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.08);
    }
    .side-slot-card {
        background-color: #fcfdfe; padding: 20px; border-radius: 18px;
        border: 1px solid #e9ecef; border-left: 8px solid #007bff; margin-bottom: 15px;
    }
    .text-line { white-space: pre-wrap; word-wrap: break-word; line-height: 1.8; margin-bottom: 12px; }
    .voice-panel { background: #ffffff; border: 1px solid #dee2e6; padding: 15px; border-radius: 20px; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# 2. [전역 저장소] 실시간 동기화 엔진
@st.cache_resource
def get_global_store():
    return {
        "report_data": None, "current_page": 0, "user_labels": {}, 
        "sync_version": 0, "chat_history": [], "voice_active_users_list": [],
        "voice_channel": "posco_briefing_room"
    }

shared_store = get_global_store()

# --- [유틸리티 로직] ---
def adapt_json_format(raw_data):
    if isinstance(raw_data, dict) and "pages" in raw_data: return raw_data
    return {"pages": [create_empty_page()]}

def create_empty_page():
    return {
        "tab": "새 페이지", "header": "제목을 입력하세요", "header_fs": 45, "header_color": "#1a1c1e",
        "sections": [{"title": "새로운 분석 섹션", "lines": [{"text": "내용을 입력하세요", "size": 22, "color": "#000000"}], "main_image": None, "side_items": []}]
    }

# --- [ID 식별 및 음성 시스템 (Agora)] ---
if "user_label" not in st.session_state:
    uid = st.query_params.get("uid", f"u_{int(time.time()*1000)}")
    st.query_params["uid"] = uid
    label = shared_store["user_labels"].get(uid, f"참여자 {len(shared_store['user_labels']) + 1}")
    shared_store["user_labels"][uid] = label; st.session_state.user_label = label

def agora_voice_system(app_id, channel, user_label):
    custom_html = f"""
    <script src="https://download.agora.io/sdk/release/AgoraRTC_N-4.11.0.js"></script>
    <div class="voice-panel">
        <div id="v-status" style="font-size: 13px; font-weight: 700; margin-bottom: 8px;">🎙️ Live Sync Audio</div>
        <div style="width: 100%; height: 10px; background: #e9ecef; border-radius: 5px; margin-bottom: 10px; overflow: hidden;">
            <div id="level-bar" style="width: 0%; height: 100%; background: #28a745; transition: width 0.05s;"></div>
        </div>
        <button id="join" style="padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold;">🔊 연결</button>
    </div>
    <script>
        let client = AgoraRTC.createClient({{ mode: "rtc", codec: "vp8" }});
        let localTracks = {{ audioTrack: null }};
        client.enableAudioVolumeIndicator();
        async function join() {{
            try {{
                await client.join("{app_id}", "{channel}", null, null);
                localTracks.audioTrack = await AgoraRTC.createMicrophoneAudioTrack();
                await client.publish([localTracks.audioTrack]);
                document.getElementById("join").style.display = "none";
                client.on("volume-indicator", (vs) => {{ vs.forEach((v) => {{ if(v.uid === 0) document.getElementById("level-bar").style.width = Math.min(v.level * 2, 100) + "%"; }}); }});
                client.on("user-published", async (u, m) => {{ await client.subscribe(u, m); if(m === "audio") u.audioTrack.play(); }});
            }} catch (e) {{ console.error(e); }}
        }}
        document.getElementById("join").onclick = join;
    </script>
    """
    components.html(custom_html, height=130)

# --- 사이드바: 통합 제어 패널 ---
with st.sidebar:
    st.title("🎙️ AI Live Sync Master")
    is_reporter = st.toggle("🔑 보고자 권한", value=False)
    my_label = "📢 보고자" if is_reporter else f"👤 {st.session_state.user_label}"
    st.info(f"📍 접속: **{my_label}**")
    
    try:
        agora_id = st.secrets["AGORA_APP_ID"]
        agora_voice_system(agora_id, shared_store["voice_channel"], my_label)
    except: st.warning("⚠️ Agora ID 설정 필요")

    with st.container(border=True):
        st.caption("👥 실시간 참여 명단")
        if is_reporter:
            options = ["📢 보고자"] + [f"👤 참여자 {i+1}" for i in range(len(shared_store['user_labels']))]
            shared_store["voice_active_users_list"] = st.multiselect("명단 동기화", options=options, default=shared_store.get("voice_active_users_list", []))
        for user in shared_store.get("voice_active_users_list", []): st.markdown(f"🟢 **{user}**")

    if is_reporter:
        st.divider()
        if shared_store["report_data"]:
            st.download_button("📥 최종 마스터 JSON 저장", data=json.dumps(shared_store["report_data"], indent=4, ensure_ascii=False), file_name="Master_Final.json", use_container_width=True)
        uploaded_file = st.file_uploader("📂 JSON 로드", type=['json'])
        if uploaded_file: shared_store["report_data"] = adapt_json_format(json.loads(uploaded_file.read().decode("utf-8")))
        
        if st.button("🚨 전체 데이터 초기화"):
            shared_store.update({"report_data": None, "current_page": 0, "chat_history": []}); st.rerun()
            
        edit_mode = st.toggle("📝 전체 디자인/저작 모드 활성화", value=False)
    else: edit_mode = False

# --- [메인 브리핑 엔진] ---
@st.fragment(run_every="1s")
def main_content_area(edit_enabled):
    # 1. 채팅 시스템
    with st.expander("💬 실시간 상호소통 채팅", expanded=False):
        c1, c2 = st.columns([4, 1])
        msg = c1.text_input("메시지", key="chat_in", label_visibility="collapsed")
        if c2.button("전송") and msg: shared_store["chat_history"].append(f"**{my_label}**: {msg}")
        chat_box = "".join([f"<div style='margin-bottom:5px;'>{m}</div>" for m in shared_store["chat_history"][-10:]])
        st.markdown(f"<div style='height:120px; overflow-y:auto; background:#f8f9fa; padding:12px; border-radius:10px;'>{chat_box}</div>", unsafe_allow_html=True)

    if shared_store["report_data"] is None:
        st.markdown("<div style='text-align:center; padding:150px; color:#6c757d;'><h2>📂 리포트가 초기화되었습니다.</h2></div>", unsafe_allow_html=True)
        if edit_enabled and st.button("📄 새 보고서 생성"):
            shared_store["report_data"] = {"pages": [create_empty_page()]}; st.rerun()
        return

    data = shared_store["report_data"]
    p = data['pages'][shared_store["current_page"]]
    
    # 2. 페이지 및 탭 관리 (기능 유지)
    if edit_enabled:
        st.write("---")
        pc1, pc2 = st.columns([1, 5])
        if pc1.button("➕ 페이지 추가"):
            data['pages'].insert(shared_store["current_page"] + 1, create_empty_page())
            shared_store["current_page"] += 1; st.rerun()
        if pc2.button("🗑️ 페이지 삭제") and len(data['pages']) > 1:
            data['pages'].pop(shared_store["current_page"]); st.rerun()

    if is_reporter:
        tabs = {i: f"P{i+1}. {pg.get('tab', '')}" for i, pg in enumerate(data['pages'])}
        shared_store["current_page"] = st.radio("📑 이동", list(tabs.keys()), index=shared_store["current_page"], format_func=lambda x: tabs[x], horizontal=True)
        if edit_enabled: p['tab'] = st.text_input("🔖 탭 이름 수정", p.get('tab', ''), key=f"t_ed_{shared_store['current_page']}")

    # 3. 대제목 디자인 (기능 유지)
    if edit_enabled:
        with st.expander("📌 대제목 디자인 설정", expanded=True):
            p['header'] = st.text_input("제목 내용", p.get('header', ''), key="h_ed")
            c1, c2 = st.columns(2)
            p['header_fs'] = c1.slider("제목 크기", 10, 150, int(p.get('header_fs', 45)))
            p['header_color'] = c2.color_picker("제목 색상", p.get('header_color', '#1a1c1e'))

    st.markdown(f'<h1 style="text-align:center; font-size:{p.get("header_fs", 45)}px; color:{p.get("header_color", "#1a1c1e")};">{p.get("header")}</h1>', unsafe_allow_html=True)
    st.divider()

    # 4. 섹션 루프 (통합형 뭉치 + 좌측 그림 + 줄 단위 스타일링)
    sections = p.setdefault('sections', [])
    if edit_enabled and st.button("➕ 새로운 세로 섹션 뭉치 추가", key=f"add_sec_{shared_store['current_page']}"):
        sections.append({"title": "새 섹션", "lines": [{"text": "내용", "size": 22, "color": "#000000"}], "main_image": None, "side_items": []})
        st.rerun()

    for s_idx, sec in enumerate(sections):
        # 섹션 전체를 하나의 명확한 테두리 블록으로 감쌈
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        col_main, col_side = st.columns([2.5, 1], gap="large")
        
        with col_main:
            if edit_enabled:
                sec['title'] = st.text_input(f"섹션 {s_idx+1} 제목", sec.get('title', ''), key=f"st_{shared_store['current_page']}_{s_idx}")
                with st.expander("🖼️ 본문(좌측) 그림 관리"):
                    img_f = st.file_uploader(f"그림 (S{s_idx+1})", type=['png', 'jpg'], key=f"simg_{shared_store['current_page']}_{s_idx}")
                    if img_f: sec['main_image'] = f"data:image/png;base64,{base64.b64encode(img_f.getvalue()).decode()}"
                    sec['img_width'] = st.slider("너비", 100, 1200, int(sec.get('img_width', 750)), key=f"sw_{shared_store['current_page']}_{s_idx}")
                    if st.button("🗑️ 그림 삭제", key=f"simg_del_{s_idx}"): sec['main_image'] = None; st.rerun()
            
            st.markdown(f"## {sec.get('title')}")
            if sec.get('main_image'): st.image(sec['main_image'], width=int(sec.get('img_width', 750)))
            
            # [줄 단위 텍스트 편집: 버그 수정 완료]
            sec.setdefault('lines', [])
            if edit_enabled:
                st.caption("📝 본문 문구 스타일 편집 (줄 단위)")
                new_lines = []
                for l_idx, line in enumerate(sec['lines']):
                    lc1, lc2, lc3, lc4 = st.columns([5, 1.5, 1.5, 0.5])
                    l_t = lc1.text_input(f"T_{l_idx}", line['text'], key=f"lt_{shared_store['current_page']}_{s_idx}_{l_idx}", label_visibility="collapsed")
                    l_s = lc2.number_input("S", 10, 100, int(line['size']), key=f"ls_{shared_store['current_page']}_{s_idx}_{l_idx}")
                    l_c = lc3.color_picker("C", line['color'], key=f"lc_{shared_store['current_page']}_{s_idx}_{l_idx}")
                    if not lc4.button("🗑️", key=f"ld_{shared_store['current_page']}_{s_idx}_{l_idx}"):
                        new_lines.append({"text": l_t, "size": l_s, "color": l_c})
                sec['lines'] = new_lines
                if st.button("➕ 문구 줄 추가", key=f"la_{shared_store['current_page']}_{s_idx}"):
                    sec['lines'].append({"text": "새로운 문구", "size": 22, "color": "#000000"}); st.rerun()
            else:
                for line in sec.get('lines', []):
                    st.markdown(f'<p class="text-line" style="font-size:{line["size"]}px; color:{line["color"]}; font-weight:bold;">{line["text"]}</p>', unsafe_allow_html=True)

        with col_side:
            sec.setdefault('side_items', [])
            if edit_enabled:
                sc1, sc2 = st.columns(2)
                if sc1.button("📊 지표", key=f"am_{shared_store['current_page']}_{s_idx}"): sec['side_items'].append({"type":"metric", "label":"항목", "value":"0", "color":"#007bff"}); st.rerun()
                if sc2.button("🖼️ 그림", key=f"ai_{shared_store['current_page']}_{s_idx}"): sec['side_items'].append({"type":"image", "src":None, "width":350}); st.rerun()
            
            for i_idx, item in enumerate(sec['side_items']):
                st.markdown('<div class="side-slot-card">', unsafe_allow_html=True)
                if edit_enabled:
                    cc1, cc2 = st.columns([4, 1])
                    if cc2.button("🗑️", key=f"sdel_{shared_store['current_page']}_{s_idx}_{i_idx}"): sec['side_items'].pop(i_idx); st.rerun()
                    if item['type'] == "metric":
                        item['label'], item['value'] = st.text_input("지표명", item['label'], key=f"il_{s_idx}_{i_idx}"), st.text_input("수치", item['value'], key=f"iv_{s_idx}_{i_idx}")
                        item['color'] = st.color_picker("색상", item.get('color', '#007bff'), key=f"ic_{s_idx}_{i_idx}")
                    elif item['type'] == "image":
                        siu = st.file_uploader("사이드 그림", key=f"siu_{shared_store['current_page']}_{s_idx}_{i_idx}")
                        if siu: item['src'] = f"data:image/png;base64,{base64.b64encode(siu.getvalue()).decode()}"
                
                if item['type'] == "metric":
                    st.markdown(f"<small>{item['label']}</small><div style='font-size:26px; font-weight:bold; color:{item.get('color', '#007bff')};'>{item['value']}</div>", unsafe_allow_html=True)
                elif item['type'] == "image" and item.get('src'):
                    st.image(item['src'], width=int(item.get('width', 350)))
                st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True) # 섹션 테두리 닫기

main_content_area(edit_mode)
