import streamlit as st
import streamlit.components.v1 as components
import json
import time
import base64

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Live Sync vFinal", layout="wide")

# 2. [전역 저장소] 실시간 데이터 및 음성 접속자 관리
@st.cache_resource
def get_global_store():
    return {
        "report_data": None,
        "current_page": 0,
        "user_labels": {}, 
        "sync_version": 0,
        "chat_logs": [],
        "voice_active_users": [], # 음성 참여자 명단 추가
        "voice_channel": "posco_briefing_room"
    }

shared_store = get_global_store()

# --- [ID 동기화 로직: 참여자 번호 고정] ---
def sync_user_id():
    js_code = """
    <script>
    const storageKey = 'posco_uid_v_final_total_v2';
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

# 3. [Agora 음성 컴포넌트: 참여자 정보 전송 포함]
def agora_voice_component(app_id, channel, role, user_label):
    custom_html = f"""
    <script src="https://download.agora.io/sdk/release/AgoraRTC_N-4.11.0.js"></script>
    <div style="padding: 10px; background: #f8f9fa; border-radius: 12px; border: 1px solid #dee2e6; text-align: center;">
        <p style="margin: 0 0 5px 0; font-size: 14px; font-weight: 600;">🎙️ 실시간 음성 브리핑</p>
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
                // 접속자 알림을 위해 Streamlit에 메시지 전송 (간이 구현)
                window.parent.postMessage({{type: 'voice_join', label: "{user_label}"}}, '*');
                
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
            window.parent.postMessage({{type: 'voice_leave', label: "{user_label}"}}, '*');
            document.getElementById("join").style.display = "inline";
            document.getElementById("leave").style.display = "none";
        }}
        document.getElementById("join").onclick = join;
        document.getElementById("leave").onclick = leave;
    </script>
    """
    components.html(custom_html, height=120)

# --- 사이드바 ---
with st.sidebar:
    st.title("🎙️ AI Live Sync")
    is_reporter = st.toggle("🔑 보고자 권한 활성화", value=False)
    my_label = "📢 보고자" if is_reporter else f"👤 {st.session_state.user_label}"
    st.info(f"📍 접속 계정: **{my_label} (나)**")
    
    try:
        agora_id = st.secrets["AGORA_APP_ID"]
        agora_voice_component(agora_id, shared_store["voice_channel"], "reporter" if is_reporter else "audience", my_label)
    except: st.warning("⚠️ Agora ID 설정 필요")

    if is_reporter:
        st.divider()
        if shared_store["report_data"]:
            st.download_button("📥 편집본 JSON 저장", data=json.dumps(shared_store["report_data"], indent=4, ensure_ascii=False), file_name="posco_final_edited.json", mime="application/json", use_container_width=True)
        if st.button("🚨 시스템 초기화", use_container_width=True):
            shared_store.update({"report_data": None, "chat_logs": [], "user_labels": {}})
            st.cache_resource.clear(); st.rerun()
        uploaded_file = st.file_uploader("📂 JSON 파일 로드", type=['json'])
        if uploaded_file and shared_store["report_data"] is None:
            content = json.loads(uploaded_file.read().decode("utf-8"))
            shared_store["report_data"] = content; shared_store["sync_version"] += 1
        edit_mode = st.toggle("📝 전체 실시간 편집 활성화", value=False)
    else: edit_mode = False

# 4. [메인 엔진: 실시간 동기화 & 편집]
@st.fragment(run_every="1s")
def sync_content_area(edit_enabled):
    # [신규] 음성 접속 참여자 정보 표시
    st.caption("🎙️ 현재 음성 브리핑 참여 중: " + (", ".join(shared_store.get("voice_active_users", ["연결 없음"]))))
    
    with st.expander("💬 실시간 채팅", expanded=True):
        c_col, i_col = st.columns([4, 1])
        with i_col:
            sender_name = "📢 보고자" if is_reporter else f"👤 {st.session_state.user_label}"
            chat_input = st.text_input("채팅", key="chat_in", label_visibility="collapsed")
            if st.button("전송", use_container_width=True):
                if chat_input:
                    shared_store["chat_logs"].insert(0, f"[{time.strftime('%H:%M:%S')}] **{sender_name}**: {chat_input}")
                    shared_store["sync_version"] += 1
        with c_col:
            for log in shared_store["chat_logs"][:2]: st.write(log)

    if shared_store["report_data"] is None:
        st.warning("🛰️ 리포트 데이터를 대기 중입니다...")
        return

    data = shared_store["report_data"]
    p = data['pages'][shared_store["current_page"]]

    # 상단 탭 관리
    if is_reporter:
        tab_labels = {i: f"P{i+1}. {pg.get('tab', '')}" for i, pg in enumerate(data['pages'])}
        current_idx = st.radio("📑 페이지 이동", list(tab_labels.keys()), index=shared_store["current_page"], format_func=lambda x: tab_labels[x], horizontal=True)
        if shared_store["current_page"] != current_idx:
            shared_store["current_page"] = current_idx; shared_store["sync_version"] += 1
        if edit_enabled:
            p['tab'] = st.text_input("🔖 탭 이름 수정", p.get('tab', ''), key=f"t_ed_{shared_store['current_page']}")
    
    st.divider()
    col_main, col_side = st.columns([2, 1], gap="large")

    # --- 중앙 본문 영역 ---
    with col_main:
        if edit_enabled:
            c1, c2 = st.columns([4, 1])
            p['header'] = c1.text_input("📌 대제목 수정", p.get('header', ''), key=f"h_in_{shared_store['current_page']}")
            p['header_fs'] = c2.number_input("크기", 20, 120, int(p.get('header_fs', 40)), key=f"h_fs_{shared_store['current_page']}")
        st.markdown(f'<h1 style="font-size:{p.get("header_fs", 40)}px;">{p.get("header")}</h1>', unsafe_allow_html=True)

        if edit_enabled:
            with st.container(border=True):
                img_f = st.file_uploader("🖼️ 본문 이미지", type=['png', 'jpg'], key=f"img_up_{shared_store['current_page']}")
                if img_f: p['image'] = f"data:image/png;base64,{base64.b64encode(img_f.getvalue()).decode()}"
                p['img_width'] = st.slider("이미지 너비", 100, 1000, int(p.get('img_width', 600)))
        
        if p.get('image'): st.image(p['image'], width=int(p.get('img_width', 600)))

        st.write("---")
        lines = p.get('content', '').split('\n')
        l_fs = p.setdefault('line_fs', [24] * len(lines))
        while len(l_fs) < len(lines): l_fs.append(24)
        
        new_l, new_f = [], []
        for i, (line, fs) in enumerate(zip(lines, l_fs)):
            if edit_enabled:
                c1, c2, c3 = st.columns([6, 1.5, 0.5])
                el = c1.text_input(f"L{i+1}", line, key=f"li_{shared_store['current_page']}_{i}")
                ef = c2.number_input("크기", 10, 100, int(fs), key=f"lf_{shared_store['current_page']}_{i}")
                if not c3.button("🗑️", key=f"del_{shared_store['current_page']}_{i}"):
                    new_l.append(el); new_f.append(ef)
            else:
                if line.strip(): st.markdown(f'<p style="font-size:{fs}px; font-weight:bold; margin:0;">{line}</p>', unsafe_allow_html=True)
        
        if edit_enabled:
            if st.button("➕ 본문 줄 추가"):
                new_l.append("새 내용"); new_f.append(24)
            p['content'] = '\n'.join(new_l); p['line_fs'] = new_f; shared_store["sync_version"] += 1

    # --- 우측 지표 및 추가 영역 ---
    with col_side:
        # [신규] "핵심 지표" 섹션 제목 수정 기능
        p.setdefault('metrics_title', '핵심 지표')
        if edit_enabled:
            p['metrics_title'] = st.text_input("📊 지표 섹션 제목 수정", p.get('metrics_title'), key=f"m_title_ed_{shared_store['current_page']}")
        
        st.subheader(p.get('metrics_title'))
        
        if edit_enabled: p['metric_fs'] = st.slider("지표 수치 크기", 10, 80, int(p.get('metric_fs', 20)))
        
        if 'metrics' in p:
            for idx, m in enumerate(p['metrics']):
                while len(m) < 4: m.append(True)
                if edit_enabled:
                    with st.container(border=True):
                        m[0] = st.text_input(f"라벨 {idx+1}", m[0], key=f"ml_{shared_store['current_page']}_{idx}")
                        m[1] = st.text_input(f"수치 {idx+1}", m[1], key=f"mv_{shared_store['current_page']}_{idx}")
                        m[3] = st.toggle("노출", value=m[3], key=f"mt_{shared_store['current_page']}_{idx}")
                if m[3] or edit_enabled:
                    m_fs = p.get('metric_fs', 20)
                    st.markdown(f'<div style="background:#f1f3f6; padding:12px; border-radius:10px; margin-bottom:10px; border-left:5px solid #007bff;"><p style="font-size:{m_fs*0.7}px; color:#555; margin:0;">{m[0]}</p><p style="font-size:{m_fs}px; font-weight:bold; margin:0;">{m[1]}</p></div>', unsafe_allow_html=True)

        # 우측 하단 자유 추가 영역 (기능 유지)
        st.divider()
        st.subheader("📝 추가 정보 영역")
        p.setdefault('side_content', '')
        p.setdefault('side_line_fs', [])
        p.setdefault('side_image', None)
        p.setdefault('side_img_width', 300)

        if edit_enabled:
            with st.expander("➕ 우측 요소 추가/편집", expanded=True):
                side_img_f = st.file_uploader("🖼️ 우측 이미지", type=['png', 'jpg'], key=f"s_img_up_{shared_store['current_page']}")
                if side_img_f: p['side_image'] = f"data:image/png;base64,{base64.b64encode(side_img_f.getvalue()).decode()}"
                p['side_img_width'] = st.slider("우측 이미지 너비", 50, 500, int(p.get('side_img_width', 300)))
                if st.button("🖼️ 이미지 제거", key=f"s_img_del_{shared_store['current_page']}"): p['side_image'] = None

        if p.get('side_image'): st.image(p['side_image'], width=int(p.get('side_img_width', 300)))

        s_lines = p.get('side_content', '').split('\n')
        s_l_fs = p.get('side_line_fs', [18] * len(s_lines))
        while len(s_l_fs) < len(s_lines): s_l_fs.append(18)
        
        new_sl, new_sf = [], []
        for i, (line, fs) in enumerate(zip(s_lines, s_l_fs)):
            if edit_enabled:
                c1, c2, c3 = st.columns([5, 2, 1])
                esl = c1.text_input(f"우측 L{i+1}", line, key=f"sli_{shared_store['current_page']}_{i}")
                esf = c2.number_input("크기", 10, 60, int(fs), key=f"slf_{shared_store['current_page']}_{i}")
                if not c3.button("🗑️", key=f"sdel_{shared_store['current_page']}_{i}"):
                    new_sl.append(esl); new_sf.append(esf)
            else:
                if line.strip(): st.markdown(f'<p style="font-size:{fs}px; color:#444; margin:0;">{line}</p>', unsafe_allow_html=True)
        
        if edit_enabled:
            if st.button("➕ 우측 문구 추가"):
                new_sl.append("추가 정보 입력"); new_sf.append(18)
            p['side_content'] = '\n'.join(new_sl); p['side_line_fs'] = new_sf; shared_store["sync_version"] += 1

sync_content_area(edit_mode)
