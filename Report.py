import streamlit as st
import streamlit.components.v1 as components
import json
import time
import base64

# 1. 페이지 설정 및 디자인 프레임워크 (CSS 강화)
st.set_page_config(page_title="POSCO E&C AI Live Sync Master", layout="wide")

st.markdown("""
    <style>
    .main-frame {
        background-color: #ffffff; padding: 25px; border-radius: 15px;
        border: 1px solid #e1e4e8; min-height: 200px; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }
    .content-line { white-space: pre-wrap; word-wrap: break-word; line-height: 1.6; }
    .side-slot-card {
        background-color: #f8f9fa; padding: 15px; border-radius: 12px;
        border-left: 6px solid #007bff; margin-bottom: 10px;
    }
    .voice-panel { background: #f1f3f6; padding: 10px; border-radius: 12px; text-align: center; }
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

# --- [데이터 보정 및 기본 구조 로직] ---
def adapt_json_format(raw_data):
    if isinstance(raw_data, dict) and "pages" in raw_data: return raw_data
    return {"pages": [create_empty_page()]}

def create_empty_page():
    return {
        "tab": "새 페이지", "header": "제목을 입력하세요", "header_fs": 40,
        "sections": [{"title": "첫 번째 섹션", "content": "내용을 입력하세요", "side_items": []}]
    }

# --- [ID 식별 및 음성 시스템 (기능 유지)] ---
if "user_label" not in st.session_state:
    uid = st.query_params.get("uid", f"u_{int(time.time()*1000)}")
    st.query_params["uid"] = uid
    label = shared_store["user_labels"].get(uid, f"참여자 {len(shared_store['user_labels']) + 1}")
    shared_store["user_labels"][uid] = label
    st.session_state.user_label = label

def agora_voice_system(app_id, channel, user_label):
    custom_html = f"""
    <script src="https://download.agora.io/sdk/release/AgoraRTC_N-4.11.0.js"></script>
    <div class="voice-panel">
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

# --- 사이드바 ---
with st.sidebar:
    st.title("🎙️ AI Live Sync")
    is_reporter = st.toggle("🔑 보고자 권한", value=False)
    my_label = "📢 보고자" if is_reporter else f"👤 {st.session_state.user_label}"
    st.info(f"📍 접속: **{my_label}**")
    
    try:
        agora_id = st.secrets["AGORA_APP_ID"]
        agora_voice_system(agora_id, shared_store["voice_channel"], my_label)
    except: st.warning("⚠️ Agora ID 설정 필요")

    with st.container(border=True):
        st.caption("👥 음성 참여 명단")
        if is_reporter:
            options = ["📢 보고자"] + [f"👤 참여자 {i+1}" for i in range(len(shared_store['user_labels']))]
            shared_store["voice_active_users_list"] = st.multiselect("명단 동기화", options=options, default=shared_store["voice_active_users_list"])
        for user in shared_store["voice_active_users_list"]: st.markdown(f"🟢 **{user}**")

    if is_reporter:
        st.divider()
        if shared_store["report_data"]:
            st.download_button("📥 최종 리포트 JSON 저장", data=json.dumps(shared_store["report_data"], indent=4, ensure_ascii=False), file_name="Master_Report.json", use_container_width=True)
        
        uploaded_file = st.file_uploader("📂 JSON 로드", type=['json'])
        if uploaded_file: shared_store["report_data"] = adapt_json_format(json.loads(uploaded_file.read().decode("utf-8")))
        
        if st.button("🚨 초기화"):
            shared_store["report_data"] = None
            shared_store["current_page"] = 0
            shared_store["chat_history"] = []
            st.rerun()
            
        edit_mode = st.toggle("📝 전체 편집/저작 활성화", value=False)
    else: edit_mode = False

# --- [메인 브리핑 엔진] ---
@st.fragment(run_every="1s")
def main_content_area(edit_enabled):
    with st.expander("💬 실시간 상호소통 채팅", expanded=False):
        c1, c2 = st.columns([4, 1])
        new_msg = c1.text_input("메시지", key="chat_in", label_visibility="collapsed")
        if c2.button("전송") and new_msg: shared_store["chat_history"].append(f"**{my_label}**: {new_msg}")
        chat_box = "".join([f"<div style='margin-bottom:5px;'>{m}</div>" for m in shared_store["chat_history"][-10:]])
        st.markdown(f"<div style='height:100px; overflow-y:auto; background:#f1f3f6; padding:10px; border-radius:8px;'>{chat_box}</div>", unsafe_allow_html=True)

    if shared_store["report_data"] is None:
        st.markdown("<div style='text-align:center; padding:100px;'><h2>📂 리포트가 초기화되었습니다.</h2><p>파일을 로드하거나 아래 버튼으로 시작하세요.</p></div>", unsafe_allow_html=True)
        if edit_enabled and st.button("📄 새 보고서 생성"):
            shared_store["report_data"] = {"pages": [create_empty_page()]}; st.rerun()
        return

    data = shared_store["report_data"]
    
    # 페이지 확장/삭제 (기능 유지)
    if edit_enabled:
        st.write("---")
        pc1, pc2 = st.columns([1, 5])
        if pc1.button("➕ 페이지 추가"):
            data['pages'].insert(shared_store["current_page"] + 1, create_empty_page())
            shared_store["current_page"] += 1; st.rerun()
        if pc2.button("🗑️ 페이지 삭제") and len(data['pages']) > 1:
            data['pages'].pop(shared_store["current_page"])
            shared_store["current_page"] = max(0, shared_store["current_page"] - 1); st.rerun()

    p = data['pages'][shared_store["current_page"]]
    
    # 내비게이션 및 탭 이름 수정 (기능 유지)
    if is_reporter:
        tabs = {i: f"P{i+1}. {pg.get('tab', '')}" for i, pg in enumerate(data['pages'])}
        shared_store["current_page"] = st.radio("📑 이동", list(tabs.keys()), index=shared_store["current_page"], format_func=lambda x: tabs[x], horizontal=True)
        if edit_enabled: p['tab'] = st.text_input("🔖 탭 이름 수정", p.get('tab', ''), key=f"t_ed_{shared_store['current_page']}")
    
    # 제목 편집 (기능 유지)
    if edit_enabled:
        p['header'] = st.text_input("📌 대제목 수정", p.get('header', ''), key=f"h_ed_{shared_store['current_page']}")
        p['header_fs'] = st.slider("📌 제목 크기", 10, 100, int(p.get('header_fs', 40)))

    st.markdown(f'<h1 style="text-align:center; font-size:{p.get("header_fs", 40)}px;">{p.get("header")}</h1>', unsafe_allow_html=True)
    st.divider()

    # 섹션 루프 (1:1 매칭 구조)
    sections = p.setdefault('sections', [])
    if edit_enabled and st.button("➕ 새로운 본문 섹션 추가"):
        sections.append({"title": "새 섹션", "content": "내용을 입력하세요", "side_items": []})

    for s_idx, sec in enumerate(sections):
        col_main, col_side = st.columns([2.5, 1], gap="large")
        with col_main:
            st.markdown('<div class="main-frame">', unsafe_allow_html=True)
            if edit_enabled:
                sec['title'] = st.text_input(f"제목 {s_idx+1}", sec.get('title', ''), key=f"st_{s_idx}")
                sec['content'] = st.text_area(f"내용 {s_idx+1}", sec.get('content', ''), key=f"sc_{s_idx}", height=200)
                sec['content_fs'] = st.slider(f"글자 크기 {s_idx+1}", 10, 60, int(sec.get('content_fs', 22)), key=f"sf_{s_idx}")
            else:
                st.markdown(f"### {sec.get('title')}")
                st.markdown(f'<div class="content-line" style="font-size:{sec.get("content_fs", 22)}px;">{sec.get("content")}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col_side:
            sec.setdefault('side_items', [])
            if edit_enabled:
                sc1, sc2 = st.columns(2)
                if sc1.button("📊 지표", key=f"am_{s_idx}"): sec['side_items'].append({"type":"metric", "label":"항목", "value":"0"})
                if sc2.button("🖼️ 그림", key=f"ai_{s_idx}"): sec['side_items'].append({"type":"image", "src":None})
            
            for i_idx, item in enumerate(sec['side_items']):
                st.markdown('<div class="side-slot-card">', unsafe_allow_html=True)
                if edit_enabled:
                    # 블록 제어 및 데이터 수정 (기능 유지)
                    cc1, cc2 = st.columns([4, 1])
                    if cc2.button("🗑️", key=f"del_{s_idx}_{i_idx}"): sec['side_items'].pop(i_idx); st.rerun()
                    if item['type'] == "metric":
                        item['label'] = st.text_input("지표명", item.get('label', ''), key=f"il_{s_idx}_{i_idx}")
                        item['value'] = st.text_input("수치", item.get('value', ''), key=f"iv_{s_idx}_{i_idx}")
                    elif item['type'] == "image":
                        img_f = st.file_uploader("그림 업로드", key=f"iu_{s_idx}_{i_idx}")
                        if img_f: item['src'] = f"data:image/png;base64,{base64.b64encode(img_f.getvalue()).decode()}"
                
                if item['type'] == "metric":
                    st.markdown(f"<small>{item.get('label')}</small><div style='font-size:26px; font-weight:bold; color:#007bff;'>{item.get('value')}</div>", unsafe_allow_html=True)
                elif item['type'] == "image" and item.get('src'):
                    st.image(item['src'], use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

main_content_area(edit_mode)
