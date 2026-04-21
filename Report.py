import streamlit as st
import streamlit.components.v1 as components
import json
import time
import base64

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C Modular Report", layout="wide")

# 2. [전역 저장소]
@st.cache_resource
def get_global_store():
    return {
        "report_data": None,
        "current_page": 0,
        "user_labels": {}, 
        "sync_version": 0,
        "chat_logs": [],
        "voice_active_users": {}, 
        "voice_channel": "posco_briefing_room"
    }

shared_store = get_global_store()

# [ID 동기화]
def sync_user_id():
    js_code = """
    <script>
    const storageKey = 'posco_modular_report_v1';
    let uid = localStorage.getItem(storageKey);
    if (!uid) {
        uid = 'u_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem(storageKey, uid);
    }
    const url = new URL(window.location.href);
    if (url.searchParams.get('uid') !== uid) {
        url.searchParams.set('uid', uid);
        window.parent.location.href = url.href;
    }
    </script>
    """
    components.html(js_code, height=0)

if "user_label" not in st.session_state:
    browser_uid = st.query_params.get("uid")
    if browser_uid:
        if browser_uid in shared_store["user_labels"]:
            st.session_state.user_label = shared_store["user_labels"][browser_uid]
        else:
            label = f"참여자 {len(shared_store['user_labels']) + 1}"
            shared_store["user_labels"][browser_uid] = label
            st.session_state.user_label = label
    else:
        sync_user_id()
        st.session_state.user_label = "식별 중..."

# 3. [음성 컴포넌트]
def agora_voice_component(app_id, channel, role, user_label):
    custom_html = f"""
    <script src="https://download.agora.io/sdk/release/AgoraRTC_N-4.11.0.js"></script>
    <div style="padding: 10px; background: #f8f9fa; border-radius: 12px; border: 1px solid #dee2e6; text-align: center;">
        <button id="join" style="padding: 8px 15px; border-radius: 6px; border: none; background: #007bff; color: white; cursor: pointer;">🔊 음성 채널 접속</button>
        <button id="leave" style="padding: 8px 15px; border-radius: 6px; border: none; background: #dc3545; color: white; display: none; cursor: pointer;">종료</button>
    </div>
    <script>
        let client = AgoraRTC.createClient({{ mode: "rtc", codec: "vp8" }});
        let localTracks = {{ audioTrack: null }};
        async function join() {{
            try {{
                await client.join("{app_id}", "{channel}", null, null);
                if ("{role}" === "reporter") {{
                    localTracks.audioTrack = await AgoraRTC.createMicrophoneAudioTrack();
                    await client.publish([localTracks.audioTrack]);
                }}
                document.getElementById("join").style.display = "none";
                document.getElementById("leave").style.display = "inline";
            }} catch (e) {{ console.error(e); }}
        }}
        async function leave() {{
            for (let trackName in localTracks) {{ if (localTracks[trackName]) {{ localTracks[trackName].stop(); localTracks[trackName].close(); }} }}
            await client.leave();
            document.getElementById("join").style.display = "inline";
            document.getElementById("leave").style.display = "none";
        }}
        document.getElementById("join").onclick = join;
        document.getElementById("leave").onclick = leave;
    </script>
    """
    components.html(custom_html, height=100)

# --- 사이드바 ---
with st.sidebar:
    st.title("🎙️ AI Live Sync")
    is_reporter = st.toggle("🔑 보고자 권한 활성화", value=False)
    my_label = "📢 보고자" if is_reporter else f"👤 {st.session_state.user_label}"
    st.info(f"📍 접속: **{my_label}**")
    
    try:
        agora_id = st.secrets["AGORA_APP_ID"]
        agora_voice_component(agora_id, shared_store["voice_channel"], "reporter" if is_reporter else "audience", my_label)
    except: st.warning("⚠️ Agora ID 설정 필요")

    if is_reporter:
        st.divider()
        if shared_store["report_data"]:
            st.download_button("📥 모듈형 JSON 저장", data=json.dumps(shared_store["report_data"], indent=4, ensure_ascii=False), file_name=f"Modular_Report_{time.strftime('%H%M')}.json", use_container_width=True)
        uploaded_file = st.file_uploader("📂 JSON 로드", type=['json'])
        if uploaded_file and shared_store["report_data"] is None:
            shared_store["report_data"] = json.loads(uploaded_file.read().decode("utf-8"))
        if st.button("🚨 초기화", use_container_width=True):
            shared_store.update({"report_data": None, "chat_logs": [], "voice_active_users": {}})
            st.cache_resource.clear(); st.rerun()
        edit_mode = st.toggle("📝 블록 편집 모드 활성화", value=False)
    else: edit_mode = False

# 4. [메인 엔진]
@st.fragment(run_every="1s")
def sync_content_area(edit_enabled):
    # 음성 참여자 동기화 명단
    if is_reporter:
        v_list = st.multiselect("🎙️ 음성 참여자 관리", options=["📢 보고자"] + [f"👤 참여자 {i+1}" for i in range(len(shared_store['user_labels']))], default=list(shared_store["voice_active_users"].keys()))
        shared_store["voice_active_users"] = {u: "참여 중" for u in v_list}
    
    v_tags = [f'<span style="background:{"#007bff" if "보고자" in u else "#28a745"}; color:white; padding:3px 10px; border-radius:15px; font-size:12px; margin-right:5px;">{u}</span>' for u in shared_store["voice_active_users"].keys()]
    st.markdown(f"🎙️ **실시간 참여:** {' '.join(v_tags) if v_tags else '대기 중...'}", unsafe_allow_html=True)
    
    if shared_store["report_data"] is None:
        st.warning("📂 JSON 보고서를 로드해주세요.")
        return

    data = shared_store["report_data"]
    p = data['pages'][shared_store["current_page"]]

    # 상단 탭
    if is_reporter:
        tabs = {i: f"P{i+1}. {pg.get('tab', '')}" for i, pg in enumerate(data['pages'])}
        c_idx = st.radio("📑 페이지 이동", list(tabs.keys()), index=shared_store["current_page"], format_func=lambda x: tabs[x], horizontal=True)
        if shared_store["current_page"] != c_idx:
            shared_store["current_page"] = c_idx; shared_store["sync_version"] += 1
        if edit_enabled: p['tab'] = st.text_input("🔖 탭 이름", p.get('tab', ''), key="t_ed")
    else:
        st.subheader(f"📍 P{shared_store['current_page']+1}. {p.get('tab', '')}")

    st.divider()
    col_main, col_side = st.columns([2, 1], gap="large")

    # --- [중앙 본문 영역] ---
    with col_main:
        if edit_enabled:
            c1, c2 = st.columns([4, 1])
            p['header'] = c1.text_input("📌 대제목", p.get('header', ''), key="main_h")
            p['header_fs'] = c2.number_input("크기", 10, 150, int(p.get('header_fs', 40)))
        st.markdown(f'<h1 style="font-size:{p.get("header_fs", 40)}px;">{p.get("header")}</h1>', unsafe_allow_html=True)

        if edit_enabled:
            with st.container(border=True):
                img_f = st.file_uploader("🖼️ 이미지 업로드", type=['png', 'jpg'], key="main_img")
                if img_f: p['image'] = f"data:image/png;base64,{base64.b64encode(img_f.getvalue()).decode()}"
                p['img_width'] = st.slider("너비", 100, 1200, int(p.get('img_width', 600)))
        if p.get('image'): st.image(p['image'], width=int(p.get('img_width', 600)))

        # 본문 줄 단위 편집
        lines = p.get('content', '').split('\n')
        l_fs = p.setdefault('line_fs', [24] * len(lines))
        while len(l_fs) < len(lines): l_fs.append(24)
        
        new_l, new_f = [], []
        for i, (line, fs) in enumerate(zip(lines, l_fs)):
            if edit_enabled:
                c1, c2, c3 = st.columns([6, 1.5, 0.5])
                el, ef = c1.text_input(f"L{i}", line, key=f"li_{i}"), c2.number_input("크기", 10, 100, int(fs), key=f"lf_{i}")
                if not c3.button("🗑️", key=f"del_{i}"): new_l.append(el); new_f.append(ef)
            else:
                if line.strip(): st.markdown(f'<p style="font-size:{fs}px; font-weight:bold; margin:0;">{line}</p>', unsafe_allow_html=True)
        if edit_enabled:
            if st.button("➕ 줄 추가"): new_l.append("새 내용"); new_f.append(24)
            p['content'] = '\n'.join(new_l); p['line_fs'] = new_f; shared_store["sync_version"] += 1

        # 하단 무한 확장
        p.setdefault('bottom_sections', [])
        if edit_enabled:
            if st.button("➕ 하단 섹션 블록 추가"):
                p['bottom_sections'].append({"header": "제목", "header_fs": 32, "content": "내용", "content_fs": 20})
        
        for idx, bs in enumerate(p['bottom_sections']):
            with st.container(border=edit_enabled):
                if edit_enabled:
                    c1, c2, c3 = st.columns([4, 1, 1])
                    bs['header'], bs['header_fs'] = c1.text_input(f"제목 {idx}", bs['header'], key=f"bh_{idx}"), c2.number_input("크기", 10, 80, int(bs.get('header_fs', 32)), key=f"bhfs_{idx}")
                    if c3.button("🗑️", key=f"bdel_{idx}"): p['bottom_sections'].pop(idx); st.rerun()
                    bs['content'], bs['content_fs'] = st.text_area("내용", bs.get('content', ''), key=f"bc_{idx}"), st.number_input("내용 크기", 10, 60, int(bs.get('content_fs', 20)), key=f"bcfs_{idx}")
                st.markdown(f'<h2 style="font-size:{bs.get("header_fs", 32)}px;">{bs["header"]}</h2>', unsafe_allow_html=True)
                st.markdown(f'<p style="font-size:{bs.get("content_fs", 20)}px;">{bs["content"]}</p>', unsafe_allow_html=True)

    # --- [우측 모듈형 블록 영역] ---
    with col_side:
        p.setdefault('side_blocks', []) # 우측 블록 리스트 초기화
        
        if edit_enabled:
            with st.container(border=True):
                st.caption("➕ 우측 블록 추가")
                bc1, bc2 = st.columns(2)
                if bc1.button("📊 지표 블록", use_container_width=True):
                    p['side_blocks'].append({"type": "metric", "label": "지표명", "value": "000", "fs": 20})
                if bc2.button("🖼️ 이미지 블록", use_container_width=True):
                    p['side_blocks'].append({"type": "image", "src": None, "width": 300})
                if st.button("📝 텍스트 블록", use_container_width=True):
                    p['side_blocks'].append({"type": "text", "content": "새 텍스트", "fs": 18})

        # 우측 블록 순차 렌더링
        for idx, block in enumerate(p['side_blocks']):
            with st.container(border=edit_enabled):
                if edit_enabled:
                    if st.button(f"🗑️ 블록 {idx+1} 삭제", key=f"sb_del_{idx}", use_container_width=True):
                        p['side_blocks'].pop(idx); st.rerun()
                
                if block['type'] == "metric":
                    if edit_enabled:
                        block['label'] = st.text_input("라벨", block['label'], key=f"sbl_{idx}")
                        block['value'] = st.text_input("수치", block['value'], key=f"sbv_{idx}")
                        block['fs'] = st.slider("크기", 10, 60, int(block['fs']), key=f"sbf_{idx}")
                    st.markdown(f'<div style="background:#f1f3f6; padding:12px; border-radius:12px; margin-bottom:10px; border-left:5px solid #007bff;"><p style="font-size:{block["fs"]*0.7}px; color:#666; margin:0;">{block["label"]}</p><p style="font-size:{block["fs"]}px; font-weight:bold; margin:0;">{block["value"]}</p></div>', unsafe_allow_html=True)
                
                elif block['type'] == "image":
                    if edit_enabled:
                        si = st.file_uploader(f"이미지 {idx}", type=['png', 'jpg'], key=f"sbi_{idx}")
                        if si: block['src'] = f"data:image/png;base64,{base64.b64encode(si.getvalue()).decode()}"
                        block['width'] = st.slider("너비", 50, 500, int(block['width']), key=f"sbiw_{idx}")
                    if block.get('src'): st.image(block['src'], width=int(block['width']))
                
                elif block['type'] == "text":
                    if edit_enabled:
                        block['content'] = st.text_area("텍스트", block['content'], key=f"sbt_{idx}")
                        block['fs'] = st.number_input("크기", 10, 60, int(block['fs']), key=f"sbtf_{idx}")
                    st.markdown(f'<p style="font-size:{block["fs"]}px; color:#444; margin:0;">{block["content"]}</p>', unsafe_allow_html=True)

sync_content_area(edit_mode)
