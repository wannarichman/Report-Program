import streamlit as st
import streamlit.components.v1 as components
import json
import time
import base64

# 1. 페이지 설정 및 레이아웃
st.set_page_config(page_title="POSCO E&C Digital Report System", layout="wide")

# 2. [전역 저장소] 실시간 데이터 공유 및 상태 유지
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

# [ID 동기화: 참여자 식별 고정]
def sync_user_id():
    js_code = """
    <script>
    const storageKey = 'posco_digital_report_vFinal';
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
        <button id="join" style="padding: 8px 15px; border-radius: 6px; border: none; background: #007bff; color: white; cursor: pointer;">🔊 음성 브리핑 접속</button>
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

# --- 사이드바: 데이터 제어 및 Export ---
with st.sidebar:
    st.title("🎙️ AI Live Sync")
    is_reporter = st.toggle("🔑 보고자 권한 활성화", value=False)
    my_label = "📢 보고자" if is_reporter else f"👤 {st.session_state.user_label}"
    st.info(f"📍 접속 계정: **{my_label}**")
    
    try:
        agora_id = st.secrets["AGORA_APP_ID"]
        agora_voice_component(agora_id, shared_store["voice_channel"], "reporter" if is_reporter else "audience", my_label)
    except: st.warning("⚠️ Agora ID 설정 필요")

    if is_reporter:
        st.divider()
        st.subheader("💾 파일 내보내기 (Export)")
        if shared_store["report_data"]:
            # [핵심] 수정된 모든 상태를 포함한 JSON 저장
            st.download_button(
                "📥 편집된 JSON 보고서 저장", 
                data=json.dumps(shared_store["report_data"], indent=4, ensure_ascii=False), 
                file_name=f"POSCO_Report_{time.strftime('%m%d_%H%M')}.json", 
                use_container_width=True
            )
        
        uploaded_file = st.file_uploader("📂 JSON 보고서 불러오기", type=['json'])
        if uploaded_file and shared_store["report_data"] is None:
            content = json.loads(uploaded_file.read().decode("utf-8"))
            shared_store["report_data"] = content
        
        if st.button("🚨 시스템 전체 초기화", use_container_width=True):
            shared_store.update({"report_data": None, "chat_logs": [], "voice_active_users": {}})
            st.cache_resource.clear(); st.rerun()
        
        edit_mode = st.toggle("📝 전체 실시간 편집 모드", value=False)
    else: edit_mode = False

# 4. [메인 브리핑 엔진]
@st.fragment(run_every="1s")
def sync_content_area(edit_enabled):
    # 상단 참여자 정보
    if is_reporter:
        v_list = st.multiselect("🎙️ 음성 참여자 관리", options=["📢 보고자"] + [f"👤 참여자 {i+1}" for i in range(len(shared_store['user_labels']))], default=list(shared_store["voice_active_users"].keys()))
        shared_store["voice_active_users"] = {u: "발언 중" if "보고자" in u else "참여 중" for u in v_list}

    v_tags = [f'<span style="background:{"#007bff" if "보고자" in u else "#28a745"}; color:white; padding:3px 10px; border-radius:15px; font-size:12px; margin-right:5px;">{u} ({s})</span>' for u, s in shared_store["voice_active_users"].items()]
    st.markdown(f"🎙️ **실시간 참여:** {' '.join(v_tags) if v_tags else '대기 중...'}", unsafe_allow_html=True)
    
    if shared_store["report_data"] is None:
        st.warning("📂 사이드바에서 보고서 JSON 파일을 로드해주세요.")
        return

    data = shared_store["report_data"]
    p = data['pages'][shared_store["current_page"]]

    # 상단 내비게이션 및 탭 수정
    if is_reporter:
        tabs = {i: f"P{i+1}. {pg.get('tab', '')}" for i, pg in enumerate(data['pages'])}
        c_idx = st.radio("📑 페이지 이동", list(tabs.keys()), index=shared_store["current_page"], format_func=lambda x: tabs[x], horizontal=True)
        if shared_store["current_page"] != c_idx:
            shared_store["current_page"] = c_idx; shared_store["sync_version"] += 1
        if edit_enabled: p['tab'] = st.text_input("🔖 탭 이름 수정", p.get('tab', ''), key="tab_ed")
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
                img_f = st.file_uploader("🖼️ 본문 이미지 교체", type=['png', 'jpg'], key="main_img")
                if img_f: p['image'] = f"data:image/png;base64,{base64.b64encode(img_f.getvalue()).decode()}"
                p['img_width'] = st.slider("이미지 너비", 100, 1200, int(p.get('img_width', 600)))
                if st.button("🖼️ 이미지 삭제"): p['image'] = None
        if p.get('image'): st.image(p['image'], width=int(p.get('img_width', 600)))

        # 본문 줄 단위 편집 (내용, 크기, 삭제)
        st.write("---")
        lines = p.get('content', '').split('\n')
        l_fs = p.setdefault('line_fs', [24] * len(lines))
        while len(l_fs) < len(lines): l_fs.append(24)
        
        new_l, new_f = [], []
        for i, (line, fs) in enumerate(zip(lines, l_fs)):
            if edit_enabled:
                c1, c2, c3 = st.columns([6, 1.5, 0.5])
                el = c1.text_input(f"L{i+1}", line, key=f"li_{i}")
                ef = c2.number_input("크기", 10, 100, int(fs), key=f"lf_{i}")
                if not c3.button("🗑️", key=f"del_{i}"): new_l.append(el); new_f.append(ef)
            else:
                if line.strip(): st.markdown(f'<p style="font-size:{fs}px; font-weight:bold; margin:0;">{line}</p>', unsafe_allow_html=True)
        if edit_enabled:
            if st.button("➕ 본문 줄 추가"): new_l.append("새 내용"); new_f.append(24)
            p['content'] = '\n'.join(new_l); p['line_fs'] = new_f; shared_store["sync_version"] += 1

        # [하단 확장 영역: 제목/내용/그림/크기 제어]
        st.write("---")
        p.setdefault('bottom_sections', [])
        if edit_enabled:
            if st.button("➕ 하단 새로운 섹션 추가"):
                p['bottom_sections'].append({"header": "하단 섹션", "header_fs": 32, "content": "내용", "content_fs": 20, "image": None, "img_width": 400})
        
        for idx, bs in enumerate(p['bottom_sections']):
            with st.container(border=edit_enabled):
                if edit_enabled:
                    c1, c2, c3 = st.columns([4, 1, 1])
                    bs['header'] = c1.text_input(f"섹션 제목 {idx}", bs['header'], key=f"bh_{idx}")
                    bs['header_fs'] = c2.number_input("크기", 10, 80, int(bs.get('header_fs', 32)), key=f"bhfs_{idx}")
                    if c3.button("🗑️ 삭제", key=f"bdel_{idx}"): p['bottom_sections'].pop(idx); st.rerun()
                    
                    bs['content'] = st.text_area("내용 수정", bs.get('content', ''), key=f"bc_{idx}")
                    bs['content_fs'] = st.number_input("내용 크기", 10, 60, int(bs.get('content_fs', 20)), key=f"bcfs_{idx}")
                    
                    bi = st.file_uploader(f"섹션 {idx} 이미지", type=['png', 'jpg'], key=f"bi_{idx}")
                    if bi: bs['image'] = f"data:image/png;base64,{base64.b64encode(bi.getvalue()).decode()}"
                    bs['img_width'] = st.slider("너비", 100, 1000, int(bs.get('img_width', 400)), key=f"biw_{idx}")
                
                st.markdown(f'<h2 style="font-size:{bs.get("header_fs", 32)}px;">{bs["header"]}</h2>', unsafe_allow_html=True)
                if bs.get('image'): st.image(bs['image'], width=int(bs.get('img_width', 400)))
                st.markdown(f'<p style="font-size:{bs.get("content_fs", 20)}px;">{bs["content"]}</p>', unsafe_allow_html=True)

    # --- [우측 영역: 지표/가시성/추가 섹션] ---
    with col_side:
        p.setdefault('show_side', True)
        if edit_enabled:
            p['show_side'] = st.toggle("📊 우측 영역 전체 노출", value=p['show_side'])
        
        if p['show_side'] or edit_enabled:
            p.setdefault('metrics_title', '핵심 지표')
            if edit_enabled: p['metrics_title'] = st.text_input("📊 제목 수정", p.get('metrics_title'))
            st.subheader(p.get('metrics_title'))
            
            if 'metrics' in p:
                for idx, m in enumerate(p['metrics']):
                    while len(m) < 4: m.append(True)
                    if edit_enabled:
                        with st.container(border=True):
                            m[0], m[1], m[3] = st.text_input(f"라벨 {idx}", m[0], key=f"ml_{idx}"), st.text_input(f"수치 {idx}", m[1], key=f"mv_{idx}"), st.toggle("노출", value=m[3], key=f"mt_{idx}")
                    if m[3] or edit_enabled:
                        st.markdown(f'<div style="background:#f1f3f6; padding:12px; border-radius:12px; margin-bottom:10px; border-left:5px solid #007bff;"><p style="font-size:14px; color:#555; margin:0;">{m[0]}</p><p style="font-size:20px; font-weight:bold; margin:0;">{m[1]}</p></div>', unsafe_allow_html=True)

            # 우측 하단 추가 섹션 (편집 및 삭제 포함)
            st.divider()
            p.setdefault('side_content', ''); p.setdefault('side_line_fs', [])
            p.setdefault('side_image', None); p.setdefault('side_img_width', 300)
            
            if edit_enabled:
                with st.expander("➕ 우측 추가 요소 편집", expanded=True):
                    si = st.file_uploader("🖼️ 우측 이미지 업로드", type=['png', 'jpg'], key="si_up")
                    if si: p['side_image'] = f"data:image/png;base64,{base64.b64encode(si.getvalue()).decode()}"
                    p['side_img_width'] = st.slider("너비", 50, 500, int(p.get('side_img_width', 300)))
                    if st.button("🖼️ 제거", key="si_del"): p['side_image'] = None

            if p.get('side_image'): st.image(p['side_image'], width=int(p.get('side_img_width', 300)))
            
            slines = p.get('side_content', '').split('\n')
            slfs = p.setdefault('side_line_fs', [18] * len(slines))
            while len(slfs) < len(slines): slfs.append(18)
            
            ns_l, ns_f = [], []
            for i, (line, fs) in enumerate(zip(slines, slfs)):
                if edit_enabled:
                    c1, c2, c3 = st.columns([5, 2, 1])
                    esl, esf = c1.text_input(f"우측 L{i}", line, key=f"sli_{i}"), c2.number_input("크기", 10, 60, int(fs), key=f"slf_{i}")
                    if not c3.button("🗑️", key=f"sdel_{i}"): ns_l.append(esl); ns_f.append(esf)
                else:
                    if line.strip(): st.markdown(f'<p style="font-size:{fs}px; color:#444; margin:0;">{line}</p>', unsafe_allow_html=True)
            if edit_enabled:
                if st.button("➕ 문구 추가"): ns_l.append("새 내용"); ns_f.append(18)
                p['side_content'] = '\n'.join(ns_l); p['side_line_fs'] = ns_f; shared_store["sync_version"] += 1

sync_content_area(edit_mode)
