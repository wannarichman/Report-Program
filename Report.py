import streamlit as st
import streamlit.components.v1 as components
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Live Sync vFinal", layout="wide")

# 2. [전역 공유 저장소]
@st.cache_resource
def get_global_store():
    return {
        "report_data": None,
        "current_page": 0,
        "active_users": 0,
        "user_labels": {}, 
        "sync_version": 0,
        "chat_logs": [],
        "voice_channel": "posco_briefing_room"
    }

shared_store = get_global_store()

# --- [ID 동기화 로직] ---
def sync_user_id():
    js_code = """
    <script>
    const storageKey = 'posco_uid_v_final_all';
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

browser_uid = st.query_params.get("uid")
if "user_label" not in st.session_state:
    if browser_uid:
        if browser_uid in shared_store["user_labels"]:
            st.session_state.user_label = shared_store["user_labels"][browser_uid]
        else:
            shared_store["active_users"] += 1
            new_label = f"참여자 {shared_store['active_users']}"
            shared_store["user_labels"][browser_uid] = new_label
            st.session_state.user_label = new_label
    else:
        sync_user_id()
        st.session_state.user_label = "식별 중"

# 3. [Agora 음성 컴포넌트]
def agora_voice_component(app_id, channel, role):
    custom_html = f"""
    <script src="https://download.agora.io/sdk/release/AgoraRTC_N-4.11.0.js"></script>
    <div style="padding: 15px; background: #f8f9fa; border-radius: 12px; border: 1px solid #dee2e6; text-align: center;">
        <p style="margin: 0 0 10px 0; font-weight: 600; color: #343a40;">🎙️ 실시간 음성 브리핑</p>
        <div id="audio-visualizer" style="display: none; justify-content: center; align-items: flex-end; height: 30px; gap: 3px; margin-bottom: 10px;">
            <div class="bar" style="width: 4px; height: 10px; background: #007bff; transition: height 0.1s;"></div>
            <div class="bar" style="width: 4px; height: 20px; background: #007bff; transition: height 0.1s;"></div>
            <div class="bar" style="width: 4px; height: 15px; background: #007bff; transition: height 0.1s;"></div>
            <div class="bar" style="width: 4px; height: 25px; background: #007bff; transition: height 0.1s;"></div>
        </div>
        <button id="join" style="padding: 10px 20px; cursor: pointer; border-radius: 6px; border: none; background: #007bff; color: white;">🔊 연결하기</button>
        <button id="leave" style="padding: 10px 20px; cursor: pointer; border-radius: 6px; border: none; background: #dc3545; color: white; display: none;">종료</button>
    </div>
    <script>
        let client = AgoraRTC.createClient({{ mode: "rtc", codec: "vp8" }});
        let localTracks = {{ audioTrack: null }};
        let audioInterval;
        async function join() {{
            try {{
                await client.join("{app_id}", "{channel}", null, null);
                document.getElementById("audio-visualizer").style.display = "flex";
                if ("{role}" === "reporter") {{
                    localTracks.audioTrack = await AgoraRTC.createMicrophoneAudioTrack();
                    await client.publish([localTracks.audioTrack]);
                    audioInterval = setInterval(() => {{
                        const level = localTracks.audioTrack.getVolumeLevel();
                        const bars = document.querySelectorAll(".bar");
                        bars.forEach(bar => {{ bar.style.height = (5 + (level * 50)) + "px"; }});
                    }}, 100);
                }}
                client.on("user-published", async (user, mediaType) => {{
                    await client.subscribe(user, mediaType);
                    if (mediaType === "audio") {{ user.audioTrack.play(); }}
                }});
                document.getElementById("join").style.display = "none";
                document.getElementById("leave").style.display = "inline";
            }} catch (e) {{ console.error(e); }}
        }}
        async function leave() {{
            if(audioInterval) clearInterval(audioInterval);
            for (let trackName in localTracks) {{ if (localTracks[trackName]) {{ localTracks[trackName].stop(); localTracks[trackName].close(); }} }}
            await client.leave();
            document.getElementById("audio-visualizer").style.display = "none";
            document.getElementById("join").style.display = "inline";
            document.getElementById("leave").style.display = "none";
        }}
        document.getElementById("join").onclick = join;
        document.getElementById("leave").onclick = leave;
    </script>
    """
    components.html(custom_html, height=160)

# --- 사이드바 영역 ---
with st.sidebar:
    st.title("🎙️ AI Live Sync")
    is_reporter = st.toggle("🔑 보고자 권한 활성화", value=False)
    st.info(f"📍 접속 계정: **{'📢 보고자 (나)' if is_reporter else st.session_state.user_label + ' (나)'}**")

    try:
        agora_id = st.secrets["AGORA_APP_ID"]
        agora_voice_component(app_id=agora_id, channel=shared_store["voice_channel"], role="reporter" if is_reporter else "audience")
    except: st.warning("⚠️ Agora ID 설정 필요")

    if is_reporter:
        st.divider()
        st.subheader("💾 데이터 관리")
        
        # [신규 기능] 편집된 내용을 JSON으로 저장 및 다운로드
        if shared_store["report_data"]:
            json_string = json.dumps(shared_store["report_data"], indent=4, ensure_ascii=False)
            st.download_button(
                label="📥 편집된 보고서 JSON 저장",
                data=json_string,
                file_name=f"edited_report_{time.strftime('%m%d_%H%M')}.json",
                mime="application/json",
                use_container_width=True
            )
        
        if st.button("🚨 시스템 전체 초기화", use_container_width=True):
            shared_store.update({"report_data": None, "chat_logs": [], "sync_version": shared_store["sync_version"]+1, "active_users": 0, "user_labels": {}})
            st.cache_resource.clear()
            st.rerun()
        
        st.divider()
        uploaded_file = st.file_uploader("📂 JSON 업로드 (범용 적용)", type=['json', 'js'])
        if uploaded_file:
            try:
                content = json.loads(uploaded_file.read().decode("utf-8"))
                for p_data in content.get('pages', []):
                    p_data.setdefault('show_p', True); p_data.setdefault('show_img', True); p_data.setdefault('show_txt', True)
                    p_data.setdefault('img_width', 800)
                    if 'metrics' in p_data:
                        for m_data in p_data['metrics']:
                            while len(m_data) < 4: m_data.append(True)
                if shared_store["report_data"] is None:
                    shared_store["report_data"] = content
                    shared_store["sync_version"] += 1
            except: st.error("JSON 형식 오류")
        
        current_edit_mode = st.toggle("📝 실시간 편집 모드", value=False)

# 4. [동기화 엔진]
@st.fragment(run_every="1s")
def sync_content_area(edit_enabled):
    with st.expander("💬 실시간 채팅", expanded=True):
        c_col, i_col = st.columns([4, 1])
        with i_col:
            sender = "📢 보고자" if is_reporter else f"👤 {st.session_state.user_label}"
            chat_input = st.text_input("메시지", key="chat_in", label_visibility="collapsed")
            if st.button("전송", use_container_width=True):
                if chat_input:
                    shared_store["chat_logs"].insert(0, f"[{time.strftime('%H:%M:%S')}] **{sender}**: {chat_input}")
                    shared_store["sync_version"] += 1
        with c_col:
            for log in shared_store["chat_logs"][:3]: st.write(log)

    if shared_store["report_data"] is None:
        st.warning("🛰️ 보고서 대기 중...")
        return

    data = shared_store["report_data"]
    p = data['pages'][shared_store["current_page"]] if shared_store["current_page"] < len(data['pages']) else data['pages'][0]
    
    if is_reporter:
        tab_list = {i: f"P{i+1}. {pg.get('tab', '')}" + (" (숨김)" if not pg.get('show_p', True) else "") for i, pg in enumerate(data['pages'])}
        current_idx = st.radio("📑 페이지 이동", list(tab_list.keys()), index=shared_store["current_page"], format_func=lambda x: tab_list[x], horizontal=True)
        if shared_store["current_page"] != current_idx:
            shared_store["current_page"] = current_idx
            shared_store["sync_version"] += 1
    elif not p.get('show_p', True):
        st.error("🚫 보고자가 이 페이지를 숨겼습니다.")
        return

    st.divider()
    
    # [편집 모드 제어 영역]
    if is_reporter and edit_enabled:
        with st.expander("🎨 레이아웃 마스터 제어 (그림 크기/노출 여부)", expanded=True):
            e_col1, e_col2, e_col3 = st.columns(3)
            p['tab'] = e_col1.text_input("🔖 탭 이름", p.get('tab', ''), key=f"t_{shared_store['current_page']}")
            p['header'] = e_col2.text_input("📌 대제목 (# 활용)", p.get('header', ''), key=f"h_{shared_store['current_page']}")
            p['img_width'] = e_col3.slider("🖼️ 그림 너비", 50, 1200, int(p.get('img_width', 800)), 50)
            
            v_col1, v_col2, v_col3 = st.columns(3)
            p['show_p'] = v_col1.checkbox("📑 페이지 전체 표시", value=p.get('show_p', True))
            p['show_img'] = v_col2.checkbox("🖼️ 그림 영역 표시", value=p.get('show_img', True))
            p['show_txt'] = v_col3.checkbox("📄 본문 영역 표시", value=p.get('show_txt', True))
            shared_store["sync_version"] += 1

    col_main, col_side = st.columns([2, 1], gap="large")
    
    with col_main:
        # 대제목 렌더링 (마크다운 지원)
        h_val = p.get('header', '')
        st.markdown(h_val if h_val.startswith('#') else f"# {h_val}")

        if p.get('show_img', True) and "image" in p:
            st.image(p["image"], width=int(p.get('img_width', 800)))
        
        if p.get('show_txt', True):
            lines = p.get('content', '').split('\n')
            new_lines = []
            for i, line in enumerate(lines):
                if is_reporter and edit_enabled:
                    c1, c2 = st.columns([10, 1])
                    edited = c1.text_input(f"L{i+1}", line, key=f"l_{shared_store['current_page']}_{i}", help="#은 크게, ###은 작게")
                    if not c2.button("🗑️", key=f"del_{shared_store['current_page']}_{i}"):
                        new_lines.append(edited)
                    else: shared_store["sync_version"] += 1
                else:
                    if line.strip():
                        st.markdown(line if line.startswith('#') else f"### {line}")
            
            if is_reporter and edit_enabled:
                if st.button("➕ 내용 추가"):
                    new_lines.append("### 새로운 내용 입력")
                    shared_store["sync_version"] += 1
                p['content'] = '\n'.join(new_lines)
                shared_store["sync_version"] += 1

    with col_side:
        st.subheader(p.get('metrics_title', '📊 지표'))
        if "metrics" in p:
            for idx, m in enumerate(p['metrics']):
                while len(m) < 4: m.append(True)
                if is_reporter and edit_enabled:
                    m[3] = st.toggle(f"지표 {idx+1} 노출", value=m[3], key=f"mtog_{shared_store['current_page']}_{idx}")
                    m[0] = st.text_input(f"라벨 {idx+1}", m[0], key=f"ml_{idx}")
                    m[1] = st.text_input(f"수치 {idx+1}", m[1], key=f"mv_{idx}")
                if m[3] or is_reporter:
                    st.metric(label=m[0] + (" (숨김)" if not m[3] else ""), value=m[1])

# 실행
sync_content_area(current_edit_mode if is_reporter else False)
