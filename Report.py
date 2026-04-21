import streamlit as st
import streamlit.components.v1 as components
import json
import time
import base64

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Live Sync vFinal", layout="wide")

# 2. [전역 저장소] 
@st.cache_resource
def get_global_store():
    return {
        "report_data": None,
        "current_page": 0,
        "user_labels": {}, 
        "sync_version": 0,
        "chat_logs": [],
        "voice_active_users": [], 
        "voice_channel": "posco_briefing_room"
    }

shared_store = get_global_store()

# [ID 동기화 로직]
def sync_user_id():
    js_code = """
    <script>
    const storageKey = 'posco_uid_final_ultimate_v5';
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
        <p style="margin: 0 0 5px 0; font-size: 14px; font-weight: 600;">🎙️ 실시간 음성 브리핑</p>
        <button id="join" style="padding: 8px 15px; border-radius: 6px; border: none; background: #007bff; color: white;">🔊 연결</button>
        <button id="leave" style="padding: 8px 15px; border-radius: 6px; border: none; background: #dc3545; color: white; display: none;">종료</button>
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
            st.download_button("📥 편집본 JSON 저장", data=json.dumps(shared_store["report_data"], indent=4, ensure_ascii=False), file_name="posco_sync_final.json", mime="application/json", use_container_width=True)
        if st.button("🚨 시스템 초기화", use_container_width=True):
            shared_store.update({"report_data": None, "chat_logs": [], "user_labels": {}})
            st.cache_resource.clear(); st.rerun()
        uploaded_file = st.file_uploader("📂 JSON 파일 로드", type=['json'])
        if uploaded_file and shared_store["report_data"] is None:
            content = json.loads(uploaded_file.read().decode("utf-8"))
            shared_store["report_data"] = content; shared_store["sync_version"] += 1
        edit_mode = st.toggle("📝 전체 실시간 편집 활성화", value=False)
    else: edit_mode = False

# 4. [메인 엔진: 실시간 동기화 & 마이크로 편집]
@st.fragment(run_every="1s")
def sync_content_area(edit_enabled):
    # 상단 접속자 정보
    st.markdown(f"🎙️ **음성 채널 참여자:** {', '.join(shared_store['voice_active_users']) if shared_store['voice_active_users'] else '대기 중...'}")
    
    if shared_store["report_data"] is None:
        st.warning("🛰️ 리포트 데이터를 대기 중입니다...")
        return

    data = shared_store["report_data"]
    p = data['pages'][shared_store["current_page"]]

    # 상단 탭 관리 및 음성 참여자 관리
    if is_reporter:
        tab_labels = {i: f"P{i+1}. {pg.get('tab', '')}" for i, pg in enumerate(data['pages'])}
        current_idx = st.radio("📑 페이지 이동", list(tab_labels.keys()), index=shared_store["current_page"], format_func=lambda x: tab_labels[x], horizontal=True)
        if shared_store["current_page"] != current_idx:
            shared_store["current_page"] = current_idx; shared_store["sync_version"] += 1
        
        if edit_enabled:
            shared_store["voice_active_users"] = st.multiselect("🎙️ 음성 참여자 명단 관리", options=["📢 보고자"] + [f"👤 참여자 {i+1}" for i in range(len(shared_store['user_labels']))], default=shared_store["voice_active_users"])
            p['tab'] = st.text_input("🔖 탭 이름 수정", p.get('tab', ''), key=f"t_ed_{shared_store['current_page']}")

    st.divider()
    col_main, col_side = st.columns([2, 1], gap="large")

    # --- [중앙 본문 및 하단 무한 확장 영역] ---
    with col_main:
        # 본문 제목 및 크기
        if edit_enabled:
            c1, c2 = st.columns([4, 1])
            p['header'] = c1.text_input("📌 대제목", p.get('header', ''), key=f"h_in_{shared_store['current_page']}")
            p['header_fs'] = c2.number_input("크기", 20, 120, int(p.get('header_fs', 40)), key=f"h_fs_{shared_store['current_page']}")
        st.markdown(f'<h1 style="font-size:{p.get("header_fs", 40)}px;">{p.get("header")}</h1>', unsafe_allow_html=True)

        # 본문 이미지 업로드
        if edit_enabled:
            with st.container(border=True):
                img_f = st.file_uploader("🖼️ 이미지 업로드", type=['png', 'jpg'], key=f"img_up_{shared_store['current_page']}")
                if img_f: p['image'] = f"data:image/png;base64,{base64.b64encode(img_f.getvalue()).decode()}"
                p['img_width'] = st.slider("너비 조절", 100, 1000, int(p.get('img_width', 600)))
        if p.get('image'): st.image(p['image'], width=int(p.get('img_width', 600)))

        # 본문 문구 편집
        st.write("---")
        c_lines = p.get('content', '').split('\n')
        c_l_fs = p.setdefault('line_fs', [24] * len(c_lines))
        while len(c_l_fs) < len(c_lines): c_l_fs.append(24)
        
        nc_lines, nc_fs = [], []
        for i, (line, fs) in enumerate(zip(c_lines, c_l_fs)):
            if edit_enabled:
                c1, c2, c3 = st.columns([6, 1.5, 0.5])
                el = c1.text_input(f"본문 L{i+1}", line, key=f"li_{shared_store['current_page']}_{i}")
                ef = c2.number_input("크기", 10, 100, int(fs), key=f"lf_{shared_store['current_page']}_{i}")
                if not c3.button("🗑️", key=f"del_{shared_store['current_page']}_{i}"):
                    nc_lines.append(el); nc_fs.append(ef)
            else:
                if line.strip(): st.markdown(f'<p style="font-size:{fs}px; font-weight:bold; margin:0;">{line}</p>', unsafe_allow_html=True)
        if edit_enabled:
            if st.button("➕ 본문 줄 추가"): nc_lines.append("새 내용"); nc_fs.append(24)
            p['content'] = '\n'.join(nc_lines); p['line_fs'] = nc_fs; shared_store["sync_version"] += 1

        # [하단 무한 확장 영역 - 제목/내용/그림/크기 조절 통합]
        st.write("---")
        p.setdefault('bottom_sections', [])
        if edit_enabled:
            if st.button("➕ 하단 새로운 섹션 추가"):
                p['bottom_sections'].append({"header": "추가 섹션", "header_fs": 32, "content": "새로운 내용", "content_fs": 20, "image": None, "img_width": 400})
        
        for idx, bs in enumerate(p['bottom_sections']):
            with st.container(border=edit_enabled):
                if edit_enabled:
                    c1, c2, c3 = st.columns([4, 1, 1])
                    bs['header'] = c1.text_input(f"섹션 제목 {idx+1}", bs['header'], key=f"bh_{idx}")
                    bs['header_fs'] = c2.number_input("제목 크기", 10, 80, int(bs.get('header_fs', 32)), key=f"bhfs_{idx}")
                    if c3.button("🗑️ 삭제", key=f"bdel_{idx}"):
                        p['bottom_sections'].pop(idx); st.rerun()
                    
                    bs['content'] = st.text_area("내용 수정", bs.get('content', ''), key=f"bc_{idx}")
                    bs['content_fs'] = st.number_input("내용 크기", 10, 60, int(bs.get('content_fs', 20)), key=f"bcfs_{idx}")
                    
                    b_img = st.file_uploader(f"섹션 {idx+1} 이미지", type=['png', 'jpg'], key=f"bi_{idx}")
                    if b_img: bs['image'] = f"data:image/png;base64,{base64.b64encode(b_img.getvalue()).decode()}"
                    bs['img_width'] = st.slider("이미지 너비", 100, 1000, int(bs.get('img_width', 400)), key=f"biw_{idx}")
                
                st.markdown(f'<h2 style="font-size:{bs.get("header_fs", 32)}px;">{bs["header"]}</h2>', unsafe_allow_html=True)
                if bs.get('image'): st.image(bs['image'], width=int(bs.get('img_width', 400)))
                st.markdown(f'<p style="font-size:{bs.get("content_fs", 20)}px;">{bs["content"]}</p>', unsafe_allow_html=True)

    # --- [우측 영역 - 지표 및 자유 추가 영역 통합] ---
    with col_side:
        p.setdefault('show_side', True)
        if edit_enabled:
            p['show_side'] = st.toggle("📊 우측 영역 노출", value=p['show_side'])
        
        if p['show_side'] or edit_enabled:
            p.setdefault('metrics_title', '핵심 지표')
            if edit_enabled:
                p['metrics_title'] = st.text_input("📊 지표 섹션 제목", p.get('metrics_title'), key=f"mt_ed_{shared_store['current_page']}")
            st.subheader(p.get('metrics_title'))
            
            # [지표 편집 및 크기]
            if 'metrics' in p:
                for idx, m in enumerate(p['metrics']):
                    while len(m) < 4: m.append(True)
                    if edit_enabled:
                        with st.container(border=True):
                            m[0] = st.text_input(f"라벨 {idx+1}", m[0], key=f"ml_{idx}")
                            m[1] = st.text_input(f"수치 {idx+1}", m[1], key=f"mv_{idx}")
                            m[3] = st.toggle("노출", value=m[3], key=f"mt_{idx}")
                    if m[3] or edit_enabled:
                        st.markdown(f'<div style="background:#f1f3f6; padding:12px; border-radius:10px; margin-bottom:10px; border-left:5px solid #007bff;"><p style="font-size:14px; color:#555; margin:0;">{m[0]}</p><p style="font-size:20px; font-weight:bold; margin:0;">{m[1]}</p></div>', unsafe_allow_html=True)

            # [우측 하단 자유 추가 영역 복구]
            st.divider()
            p.setdefault('side_title', '추가 정보')
            if edit_enabled:
                p['side_title'] = st.text_input("📝 추가 섹션 제목", p.get('side_title'), key=f"st_ed_{shared_store['current_page']}")
            st.subheader(p.get('side_title'))

            p.setdefault('side_content', ''); p.setdefault('side_line_fs', [])
            p.setdefault('side_image', None); p.setdefault('side_img_width', 300)

            if edit_enabled:
                with st.expander("➕ 우측 요소 편집", expanded=True):
                    s_img = st.file_uploader("🖼️ 우측 이미지 업로드", type=['png', 'jpg'], key=f"si_up_{shared_store['current_page']}")
                    if s_img: p['side_image'] = f"data:image/png;base64,{base64.b64encode(s_img.getvalue()).decode()}"
                    p['side_img_width'] = st.slider("너비", 50, 500, int(p.get('side_img_width', 300)))
                    if st.button("🖼️ 이미지 제거", key=f"si_del"): p['side_image'] = None

            if p.get('side_image'): st.image(p['side_image'], width=int(p.get('side_img_width', 300)))

            s_lines = p.get('side_content', '').split('\n')
            s_l_fs = p.setdefault('side_line_fs', [18] * len(s_lines))
            while len(s_l_fs) < len(s_lines): s_l_fs.append(18)
            
            ns_lines, ns_fs = [], []
            for i, (line, fs) in enumerate(zip(s_lines, s_l_fs)):
                if edit_enabled:
                    c1, c2, c3 = st.columns([5, 2, 1])
                    esl = c1.text_input(f"우측 L{i+1}", line, key=f"sli_{shared_store['current_page']}_{i}")
                    esf = c2.number_input("크기", 10, 60, int(fs), key=f"slf_{shared_store['current_page']}_{i}")
                    if not c3.button("🗑️", key=f"sdel_{i}"): ns_lines.append(esl); ns_fs.append(esf)
                else:
                    if line.strip(): st.markdown(f'<p style="font-size:{fs}px; color:#444; margin:0;">{line}</p>', unsafe_allow_html=True)
            if edit_enabled:
                if st.button("➕ 우측 문구 추가"): ns_lines.append("새 내용"); ns_fs.append(18)
                p['side_content'] = '\n'.join(ns_lines); p['side_line_fs'] = ns_fs; shared_store["sync_version"] += 1

sync_content_area(edit_mode)
