import streamlit as st
import streamlit.components.v1 as components
import json
import time
import base64

# 1. 페이지 설정 및 전역 스타일
st.set_page_config(page_title="POSCO E&C AI Live Sync vFinal", layout="wide")

# 2. [전역 저장소] 모든 참여자 실시간 데이터 공유
@st.cache_resource
def get_global_store():
    return {
        "report_data": None,
        "current_page": 0,
        "user_labels": {}, 
        "sync_version": 0,
        "chat_logs": [],
        "voice_channel": "posco_briefing_room"
    }

shared_store = get_global_store()

# --- [ID 동기화 로직: 재접속 시에도 참여자 번호 유지] ---
def sync_user_id():
    js_code = """
    <script>
    const storageKey = 'posco_uid_v_ultimate';
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

# 참여자 식별 및 레벨링 (참여자 1(나) 형식)
browser_uid = st.query_params.get("uid")
if "user_label" not in st.session_state:
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

# 3. [Agora 음성 소통 컴포넌트]
def agora_voice_component(app_id, channel, role):
    custom_html = f"""
    <script src="https://download.agora.io/sdk/release/AgoraRTC_N-4.11.0.js"></script>
    <div style="padding: 10px; background: #f8f9fa; border-radius: 12px; border: 1px solid #dee2e6; text-align: center;">
        <p style="margin: 0 0 5px 0; font-size: 14px; font-weight: 600;">🎙️ 실시간 음성 채널</p>
        <button id="join" style="padding: 8px 15px; cursor: pointer; border-radius: 6px; border: none; background: #007bff; color: white;">🔊 연결</button>
        <button id="leave" style="padding: 8px 15px; cursor: pointer; border-radius: 6px; border: none; background: #dc3545; color: white; display: none;">종료</button>
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
                client.on("user-published", async (user, mediaType) => {{
                    await client.subscribe(user, mediaType);
                    if (mediaType === "audio") {{ user.audioTrack.play(); }}
                }});
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
    components.html(custom_html, height=120)

# --- 사이드바: 관리 및 저장 기능 ---
with st.sidebar:
    st.title("🎙️ AI Live Sync")
    is_reporter = st.toggle("🔑 보고자 권한 활성화", value=False)
    
    my_display = "📢 보고자 (나)" if is_reporter else f"👤 {st.session_state.user_label} (나)"
    st.info(f"📍 접속: **{my_display}**")
    
    try:
        agora_id = st.secrets["AGORA_APP_ID"]
        agora_voice_component(app_id=agora_id, channel=shared_store["voice_channel"], role="reporter" if is_reporter else "audience")
    except: st.warning("⚠️ Agora ID 설정 필요")

    if is_reporter:
        st.divider()
        st.subheader("💾 데이터 관리")
        # 편집본 JSON 저장 기능 (모든 설정 포함)
        if shared_store["report_data"]:
            st.download_button(
                label="📥 현재 편집본 JSON 저장",
                data=json.dumps(shared_store["report_data"], indent=4, ensure_ascii=False),
                file_name=f"posco_edited_{time.strftime('%H%M')}.json",
                mime="application/json",
                use_container_width=True
            )
        
        if st.button("🚨 시스템 초기화", use_container_width=True):
            shared_store.update({"report_data": None, "chat_logs": [], "user_labels": {}})
            st.cache_resource.clear(); st.rerun()
            
        uploaded_file = st.file_uploader("📂 JSON 파일 로드", type=['json'])
        if uploaded_file and shared_store["report_data"] is None:
            content = json.loads(uploaded_file.read().decode("utf-8"))
            for p_data in content.get('pages', []):
                p_data.setdefault('show_p', True); p_data.setdefault('header_fs', 40)
                p_data.setdefault('img_width', 600); p_data.setdefault('metric_fs', 20)
                # 줄별 폰트 데이터 보정
                lines = p_data.get('content', '').split('\n')
                if 'line_fs' not in p_data or len(p_data['line_fs']) != len(lines):
                    p_data['line_fs'] = [24] * len(lines)
            shared_store["report_data"] = content; shared_store["sync_version"] += 1
            
        edit_mode = st.toggle("📝 실시간 개별 편집 활성화", value=False)
    else: edit_mode = False

# 4. [메인 브리핑 엔진: 1초 단위 실시간 동기화]
@st.fragment(run_every="1s")
def sync_content_area(edit_enabled):
    # 실시간 채팅 영역
    with st.expander("💬 실시간 채팅", expanded=True):
        c_col, i_col = st.columns([4, 1])
        with i_col:
            sender = "📢 보고자" if is_reporter else f"👤 {st.session_state.user_label}"
            chat_input = st.text_input("채팅", key="chat_in", label_visibility="collapsed")
            if st.button("전송", use_container_width=True):
                if chat_input:
                    shared_store["chat_logs"].insert(0, f"[{time.strftime('%H:%M:%S')}] **{sender}**: {chat_input}")
                    shared_store["sync_version"] += 1
        with c_col:
            for log in shared_store["chat_logs"][:3]: st.write(log)

    if shared_store["report_data"] is None:
        st.warning("🛰️ 리포트 데이터를 대기 중입니다...")
        return

    data = shared_store["report_data"]
    p = data['pages'][shared_store["current_page"]]

    # 상단 페이지 내비게이션 (보고자 동기화)
    if is_reporter:
        tab_labels = {i: f"P{i+1}. {pg.get('tab', '')}" for i, pg in enumerate(data['pages'])}
        current_idx = st.radio("📑 페이지 이동", list(tab_labels.keys()), index=shared_store["current_page"], format_func=lambda x: tab_labels[x], horizontal=True)
        if shared_store["current_page"] != current_idx:
            shared_store["current_page"] = current_idx; shared_store["sync_version"] += 1
    
    st.divider()
    col_main, col_side = st.columns([2, 1], gap="large")

    with col_main:
        # [대제목 편집: 크기 조절기 통합]
        if edit_enabled:
            c1, c2 = st.columns([4, 1])
            p['header'] = c1.text_input("📌 대제목 수정", p.get('header', ''), key=f"h_in_{shared_store['current_page']}")
            p['header_fs'] = c2.number_input("크기", 20, 120, int(p.get('header_fs', 40)), key=f"h_fs_{shared_store['current_page']}")
        st.markdown(f'<h1 style="font-size:{p.get("header_fs")}px; margin-bottom:20px;">{p.get("header")}</h1>', unsafe_allow_html=True)

        # [그림 영역: 직접 업로드 및 삭제, 크기 조절]
        if edit_enabled:
            with st.container(border=True):
                st.caption("🖼️ 그림 실시간 관리")
                img_file = st.file_uploader("그림 파일 업로드", type=['png', 'jpg', 'jpeg'], key=f"img_up_{shared_store['current_page']}")
                if img_file:
                    p['image'] = f"data:image/png;base64,{base64.b64encode(img_file.getvalue()).decode()}"
                
                c1, c2 = st.columns([3, 1])
                p['img_width'] = c1.slider("이미지 너비", 100, 1200, int(p.get('img_width', 600)))
                if c2.button("🖼️ 이미지 제거", use_container_width=True): p['image'] = None
        
        if p.get('image'):
            st.image(p['image'], width=int(p.get('img_width', 600)))

        # [본문 줄 단위 개별 편집: 크기/삭제/추가]
        st.write("---")
        content_lines = p.get('content', '').split('\n')
        line_fs = p.get('line_fs', [24] * len(content_lines))
        
        # 데이터 동기화 보정
        while len(line_fs) < len(content_lines): line_fs.append(24)
        
        new_lines, new_fs = [], []
        for i, (line, fs) in enumerate(zip(content_lines, line_fs)):
            if edit_enabled:
                c1, c2, c3 = st.columns([6, 1.5, 0.5])
                ed_line = c1.text_input(f"L{i+1} 문구", line, key=f"li_{shared_store['current_page']}_{i}")
                ed_fs = c2.number_input("크기", 10, 100, int(fs), key=f"lf_{shared_store['current_page']}_{i}")
                if not c3.button("🗑️", key=f"del_{shared_store['current_page']}_{i}"):
                    new_lines.append(ed_line); new_fs.append(ed_fs)
            else:
                if line.strip():
                    st.markdown(f'<p style="font-size:{fs}px; font-weight:bold; margin:0; line-height:1.4;">{line}</p>', unsafe_allow_html=True)
        
        if edit_enabled:
            if st.button("➕ 새로운 줄 추가"):
                new_lines.append("새로운 내용을 입력하세요"); new_fs.append(24)
            p['content'] = '\n'.join(new_lines); p['line_fs'] = new_fs; shared_store["sync_version"] += 1

    with col_side:
        # [우측 지표 편집 및 크기 제어]
        st.subheader("📊 핵심 지표 설정")
        if 'metrics' in p:
            for idx, m in enumerate(p['metrics']):
                if edit_enabled:
                    with st.container(border=True):
                        m[0] = st.text_input(f"지표 {idx+1} 라벨", m[0], key=f"ml_{shared_store['current_page']}_{idx}")
                        m[1] = st.text_input(f"수치 {idx+1}", m[1], key=f"mv_{shared_store['current_page']}_{idx}")
                        m[3] = st.toggle("노출 여부", value=m[3], key=f"mt_{shared_store['current_page']}_{idx}")
                
                if m[3] or edit_enabled:
                    m_fs = p.get('metric_fs', 20)
                    st.markdown(f"""
                    <div style="background:#f1f3f6; padding:12px; border-radius:12px; margin-bottom:12px; border-left:6px solid #007bff;">
                        <p style="font-size:{m_fs*0.7}px; color:#555; margin:0;">{m[0]}</p>
                        <p style="font-size:{m_fs}px; font-weight:bold; margin:0; color:#222;">{m[1]}</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            if edit_enabled:
                p['metric_fs'] = st.slider("지표 전체 텍스트 크기", 10, 80, int(p.get('metric_fs', 20)))

# 최종 실행
sync_content_area(edit_mode)
