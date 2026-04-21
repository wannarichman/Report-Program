import streamlit as st
import streamlit.components.v1 as components
import json
import time
import base64

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Live Sync vFinal", layout="wide")

# 2. [전역 저장소] 실시간 데이터 및 음성 접속 상태 관리
@st.cache_resource
def get_global_store():
    return {
        "report_data": None,
        "current_page": 0,
        "user_labels": {}, 
        "sync_version": 0,
        "chat_logs": [],
        "voice_active_users": {}, # {label: status} 실시간 음성 상태 저장
        "voice_channel": "posco_briefing_room"
    }

shared_store = get_global_store()

# --- [ID 동기화: 참여자 번호 고정] ---
def sync_user_id():
    js_code = """
    <script>
    const storageKey = 'posco_uid_final_master_v1';
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

# 3. [음성 컴포넌트: 실시간 발언자 식별 로직 보강]
def agora_voice_component(app_id, channel, role, user_label):
    # 자바스크립트를 통해 Agora 접속 시 서버(Streamlit)로 즉시 상태 전송
    custom_html = f"""
    <script src="https://download.agora.io/sdk/release/AgoraRTC_N-4.11.0.js"></script>
    <div style="padding: 10px; background: #f8f9fa; border-radius: 12px; border: 1px solid #dee2e6; text-align: center;">
        <p id="v-status" style="margin: 0 0 5px 0; font-size: 14px; font-weight: 600; color: #6c757d;">🎙️ 음성 연결 대기 중</p>
        <button id="join" style="padding: 8px 15px; border-radius: 6px; border: none; background: #007bff; color: white; cursor: pointer;">🔊 음성 참여하기</button>
        <button id="leave" style="padding: 8px 15px; border-radius: 6px; border: none; background: #dc3545; color: white; display: none; cursor: pointer;">종료</button>
    </div>
    <script>
        let client = AgoraRTC.createClient({{ mode: "rtc", codec: "vp8" }});
        let localTracks = {{ audioTrack: null }};
        let userLabel = "{user_label}";

        async function join() {{
            try {{
                await client.join("{app_id}", "{channel}", null, null);
                document.getElementById("v-status").innerText = "🎙️ 연결됨 (채널 입성)";
                document.getElementById("v-status").style.color = "#28a745";
                
                if ("{role}" === "reporter") {{
                    localTracks.audioTrack = await AgoraRTC.createMicrophoneAudioTrack();
                    await client.publish([localTracks.audioTrack]);
                    document.getElementById("v-status").innerText = "📢 보고자 (발언 중)";
                }}
                
                // [핵심] Agora 접속 성공 시 부모 창에 상태 메시지 전송
                window.parent.postMessage({{type: 'voice_sync', label: userLabel, action: 'join', status: "{role}" === "reporter" ? "발언 중" : "참여 중"}}, '*');

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
            window.parent.postMessage({{type: 'voice_sync', label: userLabel, action: 'leave'}}, '*');
            document.getElementById("v-status").innerText = "🎙️ 음성 연결 종료";
            document.getElementById("v-status").style.color = "#6c757d";
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
    st.info(f"📍 접속: **{my_label} (나)**")
    
    try:
        agora_id = st.secrets["AGORA_APP_ID"]
        agora_voice_component(agora_id, shared_store["voice_channel"], "reporter" if is_reporter else "audience", my_label)
    except: st.warning("⚠️ Agora ID 설정 필요")

    if is_reporter:
        st.divider()
        if shared_store["report_data"]:
            st.download_button("📥 편집본 JSON 저장", data=json.dumps(shared_store["report_data"], indent=4, ensure_ascii=False), file_name="posco_sync_master.json", mime="application/json", use_container_width=True)
        if st.button("🚨 시스템 초기화", use_container_width=True):
            shared_store.update({"report_data": None, "chat_logs": [], "user_labels": {}, "voice_active_users": {}})
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
    # [음성 참여 명단 표시 로직 복구]
    if is_reporter:
        # 보고자가 접속한 참여자를 수동으로 식별하거나, 상시 참여자로 등록 가능하도록 UI 보강
        active_list = st.multiselect("🎙️ 음성 참여 명단 관리 (동기화)", options=["📢 보고자"] + [f"👤 참여자 {i+1}" for i in range(len(shared_store['user_labels']))], default=list(shared_store.get("voice_active_users", {}).keys()))
        # 상태 업데이트 (간단하게 '참여 중'으로 통일)
        shared_store["voice_active_users"] = {u: "참여 중" for u in active_list}

    # 음성 라벨 및 참여자 명단 렌더링
    voice_labels = []
    for user, status in shared_store["voice_active_users"].items():
        color = "#007bff" if "보고자" in user else "#28a745"
        voice_labels.append(f'<span style="background:{color}; color:white; padding:2px 8px; border-radius:12px; font-size:12px; margin-right:5px;">{user} ({status})</span>')
    
    st.markdown(f"🎙️ **실시간 음성 브리핑 참여:** {' '.join(voice_labels) if voice_labels else '<span style=\"color:gray;\">대기 중...</span>'}", unsafe_allow_html=True)
    
    if shared_store["report_data"] is None:
        st.warning("🛰️ 리포트 데이터를 대기 중입니다...")
        return

    data = shared_store["report_data"]
    p = data['pages'][shared_store["current_page"]]

    # [수정] 참여자 화면에서도 탭 이름(혁신배경 등)이 보이도록 가시성 로직 수정
    tab_labels = {i: f"P{i+1}. {pg.get('tab', '')}" for i, pg in enumerate(data['pages'])}
    
    if is_reporter:
        current_idx = st.radio("📑 페이지 이동", list(tab_labels.keys()), index=shared_store["current_page"], format_func=lambda x: tab_labels[x], horizontal=True)
        if shared_store["current_page"] != current_idx:
            shared_store["current_page"] = current_idx; shared_store["sync_version"] += 1
        if edit_enabled:
            p['tab'] = st.text_input("🔖 탭 이름 수정", p.get('tab', ''), key=f"t_ed_{shared_store['current_page']}")
    else:
        # 참여자 화면 상단에 현재 어떤 페이지 브리핑 중인지 표시 (P1. 혁신배경 형식)
        st.subheader(f"📍 {tab_labels[shared_store['current_page']]}")

    st.divider()
    col_main, col_side = st.columns([2, 1], gap="large")

    # --- [중앙 본문 및 무한 확장] ---
    with col_main:
        if edit_enabled:
            c1, c2 = st.columns([4, 1])
            p['header'] = c1.text_input("📌 대제목", p.get('header', ''), key=f"h_in_{shared_store['current_page']}")
            p['header_fs'] = c2.number_input("크기", 20, 120, int(p.get('header_fs', 40)), key=f"h_fs_{shared_store['current_page']}")
        st.markdown(f'<h1 style="font-size:{p.get("header_fs", 40)}px; margin:0;">{p.get("header")}</h1>', unsafe_allow_html=True)

        if edit_enabled:
            with st.container(border=True):
                img_f = st.file_uploader("🖼️ 이미지 업로드", type=['png', 'jpg'], key=f"img_up_{shared_store['current_page']}")
                if img_f: p['image'] = f"data:image/png;base64,{base64.b64encode(img_f.getvalue()).decode()}"
                p['img_width'] = st.slider("너비", 100, 1000, int(p.get('img_width', 600)))
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
            if st.button("➕ 줄 추가"): new_l.append("새 내용"); new_f.append(24)
            p['content'] = '\n'.join(new_l); p['line_fs'] = new_f; shared_store["sync_version"] += 1

        # [하단 확장]
        p.setdefault('bottom_sections', [])
        if edit_enabled:
            if st.button("➕ 하단 새로운 섹션 추가"):
                p['bottom_sections'].append({"header": "하단 섹션", "header_fs": 32, "content": "내용", "content_fs": 20, "image": None, "img_width": 400})
        
        for idx, bs in enumerate(p['bottom_sections']):
            with st.container(border=edit_enabled):
                if edit_enabled:
                    c1, c2, c3 = st.columns([4, 1, 1])
                    bs['header'] = c1.text_input(f"섹션 제목 {idx}", bs['header'], key=f"bh_{idx}")
                    bs['header_fs'] = c2.number_input("제목 크기", 10, 80, int(bs.get('header_fs', 32)), key=f"bhfs_{idx}")
                    if c3.button("🗑️ 삭제", key=f"bdel_{idx}"): p['bottom_sections'].pop(idx); st.rerun()
                    bs['content'] = st.text_area("내용", bs.get('content', ''), key=f"bc_{idx}")
                    bs['content_fs'] = st.number_input("내용 크기", 10, 60, int(bs.get('content_fs', 20)), key=f"bcfs_{idx}")
                
                st.markdown(f'<h2 style="font-size:{bs.get("header_fs", 32)}px;">{bs["header"]}</h2>', unsafe_allow_html=True)
                st.markdown(f'<p style="font-size:{bs.get("content_fs", 20)}px;">{bs["content"]}</p>', unsafe_allow_html=True)

    # --- [우측 영역] ---
    with col_side:
        p.setdefault('metrics_title', '핵심 지표')
        if edit_enabled:
            p['metrics_title'] = st.text_input("📊 우측 섹션 제목", p.get('metrics_title'), key=f"mt_ed_{shared_store['current_page']}")
        st.subheader(p.get('metrics_title'))
        
        if edit_enabled: p['metric_fs'] = st.slider("지표 크기", 10, 80, int(p.get('metric_fs', 20)))
        
        if 'metrics' in p:
            for idx, m in enumerate(p['metrics']):
                while len(m) < 4: m.append(True)
                if edit_enabled:
                    with st.container(border=True):
                        m[0] = st.text_input(f"라벨 {idx+1}", m[0], key=f"ml_{idx}")
                        m[1] = st.text_input(f"수치 {idx+1}", m[1], key=f"mv_{idx}")
                        m[3] = st.toggle("노출", value=m[3], key=f"mt_{idx}")
                if m[3] or edit_enabled:
                    m_fs = p.get('metric_fs', 20)
                    st.markdown(f'<div style="background:#f1f3f6; padding:12px; border-radius:12px; margin-bottom:10px; border-left:5px solid #007bff;"><p style="font-size:{m_fs*0.7}px; color:#555; margin:0;">{m[0]}</p><p style="font-size:{m_fs}px; font-weight:bold; margin:0;">{m[1]}</p></div>', unsafe_allow_html=True)

sync_content_area(edit_mode)
