import streamlit as st
import streamlit.components.v1 as components
import json
import time
import base64

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C Live Sync vFinal", layout="wide")

# 2. [전역 저장소]
@st.cache_resource
def get_global_store():
    return {
        "report_data": None,
        "current_page": 0,
        "user_labels": {}, 
        "sync_version": 0,
        "voice_active_users": {}, # {label: {"isMuted": bool, "level": int}}
        "voice_channel": "posco_briefing_room"
    }

shared_store = get_global_store()

# --- [ID 동기화: 무한 루프 방지 및 고유 ID 고정] ---
def get_user_id():
    # 쿼리 파라미터에서 직접 가져오되, 없으면 JS로 할당
    uid = st.query_params.get("uid")
    if not uid:
        js_code = """
        <script>
        const storageKey = 'posco_uid_v_final_stable';
        let uid = localStorage.getItem(storageKey);
        if (!uid) {
            uid = 'u_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem(storageKey, uid);
        }
        const url = new URL(window.location.href);
        url.searchParams.set('uid', uid);
        window.parent.location.href = url.href;
        </script>
        """
        components.html(js_code, height=0)
        st.stop()
    return uid

browser_uid = get_user_id()

if "user_label" not in st.session_state:
    if browser_uid in shared_store["user_labels"]:
        st.session_state.user_label = shared_store["user_labels"][browser_uid]
    else:
        new_label = f"참여자 {len(shared_store['user_labels']) + 1}"
        shared_store["user_labels"][browser_uid] = new_label
        st.session_state.user_label = new_label

# 3. [Agora 음성 시스템: 실시간 레벨링 및 마이크 제어]
def agora_voice_system(app_id, channel, user_label):
    custom_html = f"""
    <script src="https://download.agora.io/sdk/release/AgoraRTC_N-4.11.0.js"></script>
    <div style="padding: 10px; background: #f8f9fa; border-radius: 12px; border: 1px solid #dee2e6; text-align: center; font-family: sans-serif;">
        <div id="v-status" style="font-size: 14px; font-weight: 700; margin-bottom: 8px;">🎙️ 음성 시스템 (상태: 대기)</div>
        <div id="level-container" style="width: 100%; height: 8px; background: #e9ecef; border-radius: 4px; margin-bottom: 10px; display: none;">
            <div id="level-bar" style="width: 0%; height: 100%; background: #28a745; border-radius: 4px; transition: width 0.1s;"></div>
        </div>
        <div style="display: flex; justify-content: center; gap: 10px;">
            <button id="join" style="padding: 8px 15px; border-radius: 6px; border: none; background: #007bff; color: white; cursor: pointer; font-weight: bold;">🔊 참여하기</button>
            <button id="mute" style="padding: 8px 15px; border-radius: 6px; border: none; background: #6c757d; color: white; cursor: pointer; display: none; font-weight: bold;">🔇 마이크 끄기</button>
        </div>
    </div>
    <script>
        let client = AgoraRTC.createClient({{ mode: "rtc", codec: "vp8" }});
        let localTracks = {{ audioTrack: null }};
        let isMuted = false;
        let myLabel = "{user_label}";

        // 볼륨 표시 활성화
        client.enableAudioVolumeIndicator();

        async function join() {{
            try {{
                await client.join("{app_id}", "{channel}", null, null);
                localTracks.audioTrack = await AgoraRTC.createMicrophoneAudioTrack();
                await client.publish([localTracks.audioTrack]);
                
                document.getElementById("join").style.display = "none";
                document.getElementById("mute").style.display = "inline";
                document.getElementById("level-container").style.display = "block";
                document.getElementById("v-status").innerText = "🎙️ 연결됨 (마이크 활성)";

                // [중요] 자신의 음성 레벨을 서버로 전송
                client.on("volume-indicator", (volumes) => {{
                    volumes.forEach((volume) => {{
                        if (volume.uid === 0) {{ // 내 마이크 수치 (uid 0은 로컬)
                            const level = isMuted ? 0 : volume.level;
                            document.getElementById("level-bar").style.width = level + "%";
                            // Streamlit 서버에 내 상태 알림
                            window.parent.postMessage({{
                                type: 'voice_state_update',
                                label: myLabel,
                                isMuted: isMuted,
                                level: level
                            }}, '*');
                        }}
                    }});
                }});

                client.on("user-published", async (user, mediaType) => {{
                    await client.subscribe(user, mediaType);
                    if (mediaType === "audio") {{ user.audioTrack.play(); }}
                }});
            }} catch (e) {{ console.error(e); }}
        }}

        async function toggleMute() {{
            if (!localTracks.audioTrack) return;
            isMuted = !isMuted;
            await localTracks.audioTrack.setEnabled(!isMuted);
            document.getElementById("mute").innerText = isMuted ? "🎤 마이크 켜기" : "🔇 마이크 끄기";
            document.getElementById("mute").style.background = isMuted ? "#28a745" : "#6c757d";
            document.getElementById("v-status").innerText = isMuted ? "🔇 음소거 중" : "🎙️ 연결됨";
            document.getElementById("level-bar").style.width = "0%";
        }}

        document.getElementById("join").onclick = join;
        document.getElementById("mute").onclick = toggleMute;
    </script>
    """
    components.html(custom_html, height=140)

# --- 사이드바 ---
with st.sidebar:
    st.title("🎙️ AI Live Sync")
    is_reporter = st.toggle("🔑 보고자 권한 활성화", value=False)
    my_label = "📢 보고자" if is_reporter else f"👤 {st.session_state.user_label}"
    st.info(f"📍 내 정보: **{my_label}**")
    
    try:
        agora_id = st.secrets["AGORA_APP_ID"]
        agora_voice_system(agora_id, shared_store["voice_channel"], my_label)
    except: st.warning("⚠️ 사이드바 하단 Agora ID 설정 필요")

    if is_reporter:
        st.divider()
        if shared_store["report_data"]:
            st.download_button("📥 최종 편집본 JSON 저장", data=json.dumps(shared_store["report_data"], indent=4, ensure_ascii=False), file_name="POSCO_Digital_Report.json", use_container_width=True)
        uploaded_file = st.file_uploader("📂 JSON 로드", type=['json'])
        if uploaded_file and shared_store["report_data"] is None:
            shared_store["report_data"] = json.loads(uploaded_file.read().decode("utf-8"))
        if st.button("🚨 초기화", use_container_width=True):
            shared_store.update({"report_data": None, "user_labels": {}, "voice_active_users": {}})
            st.cache_resource.clear(); st.rerun()
        edit_mode = st.toggle("📝 전체 편집 모드 활성화", value=False)
    else: edit_mode = False

# 4. [메인 브리핑 엔진: 1초 단위 동기화]
@st.fragment(run_every="1s")
def sync_content_area(edit_enabled):
    # [실시간 참여자 리스트 보드]
    with st.container(border=True):
        st.caption("🎙️ 실시간 브리핑 참여자 및 음성 레벨링")
        # 보고자가 참여자 명단을 관리하거나, 세션 상태를 통해 자동 감지된 리스트 표시
        if is_reporter:
            # 강제로 명단에 수동 추가할 수 있도록 보고자에게 권한 부여
            options = ["📢 보고자"] + [f"👤 참여자 {i+1}" for i in range(len(shared_store['user_labels']))]
            selected = st.multiselect("참여자 수동 동기화", options=options, default=list(shared_store["voice_active_users"].keys()))
            for s in selected:
                if s not in shared_store["voice_active_users"]:
                    shared_store["voice_active_users"][s] = {"level": 0, "isMuted": False}
            # 선택 해제된 사람 제거
            for k in list(shared_store["voice_active_users"].keys()):
                if k not in selected: shared_store["voice_active_users"].pop(k)

        if not shared_store["voice_active_users"]:
            st.write("대기 중...")
        else:
            v_cols = st.columns(min(len(shared_store["voice_active_users"]), 4))
            for idx, (user, state) in enumerate(shared_store["voice_active_users"].items()):
                with v_cols[idx % 4]:
                    lvl = state.get('level', 0)
                    m_icon = "🔇" if state.get('isMuted') else "🔊"
                    # 실시간 음성 레벨링 바 시각화
                    st.markdown(f"**{user}**")
                    st.progress(min(lvl / 100, 1.0)) # 0.0 ~ 1.0 사이 값

    if shared_store["report_data"] is None:
        st.warning("📂 리포트 JSON 파일을 로드해주세요.")
        return

    data = shared_store["report_data"]; p = data['pages'][shared_store["current_page"]]

    # 상단 내비게이션
    if is_reporter:
        tabs = {i: f"P{i+1}. {pg.get('tab', '')}" for i, pg in enumerate(data['pages'])}
        c_idx = st.radio("📑 페이지", list(tabs.keys()), index=shared_store["current_page"], format_func=lambda x: tabs[x], horizontal=True)
        if shared_store["current_page"] != c_idx: shared_store["current_page"] = c_idx; shared_store["sync_version"] += 1
        if edit_enabled: p['tab'] = st.text_input("🔖 탭 제목 수정", p.get('tab', ''), key="t_ed")
    else: st.subheader(f"📍 P{shared_store['current_page']+1}. {p.get('tab', '')}")

    st.divider()
    col_main, col_side = st.columns([2, 1], gap="large")

    with col_main:
        # [본문 제목 및 편집]
        if edit_enabled:
            c1, c2 = st.columns([4, 1])
            p['header'], p['header_fs'] = c1.text_input("📌 대제목", p.get('header', '')), c2.number_input("크기", 10, 150, int(p.get('header_fs', 40)))
        st.markdown(f'<h1 style="font-size:{p.get("header_fs", 40)}px;">{p.get("header")}</h1>', unsafe_allow_html=True)

        # [이미지 편집]
        if edit_enabled:
            with st.container(border=True):
                img_f = st.file_uploader("🖼️ 이미지 교체", type=['png', 'jpg'], key="main_img")
                if img_f: p['image'] = f"data:image/png;base64,{base64.b64encode(img_f.getvalue()).decode()}"
                p['img_width'] = st.slider("너비", 100, 1200, int(p.get('img_width', 600)))
        if p.get('image'): st.image(p['image'], width=int(p.get('img_width', 600)))

        # [본문 줄 단위 편집]
        lines = p.get('content', '').split('\n'); l_fs = p.setdefault('line_fs', [24] * len(lines))
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

        # [하단 확장 섹션 복구]
        st.write("---")
        p.setdefault('bottom_blocks', [])
        if edit_enabled:
            if st.button("➕ 하단 섹션 추가"):
                p['bottom_blocks'].append({"header": "제목", "header_fs": 32, "content": "내용", "content_fs": 20, "image": None, "img_width": 500})
        for idx, bb in enumerate(p['bottom_blocks']):
            with st.container(border=edit_enabled):
                if edit_enabled:
                    c1, c2, c3 = st.columns([4, 1, 1])
                    bb['header'], bb['header_fs'] = c1.text_input(f"제목 {idx}", bb['header'], key=f"bbh_{idx}"), c2.number_input("크기", 10, 80, int(bb.get('header_fs', 32)), key=f"bbhf_{idx}")
                    if c3.button("🗑️", key=f"bbdel_{idx}"): p['bottom_blocks'].pop(idx); st.rerun()
                    bbi = st.file_uploader(f"이미지 {idx}", type=['png', 'jpg'], key=f"bbi_{idx}")
                    if bbi: bb['image'] = f"data:image/png;base64,{base64.b64encode(bbi.getvalue()).decode()}"
                    bb['img_width'] = st.slider("너비", 100, 1000, int(bb.get('img_width', 500)), key=f"bbw_{idx}")
                    bb['content'] = st.text_area("내용", bb['content'], key=f"bbc_{idx}")
                    bb['content_fs'] = st.number_input("내용 크기", 10, 60, int(bb.get('content_fs', 20)), key=f"bbcf_{idx}")
                st.markdown(f'<h2 style="font-size:{bb.get("header_fs", 32)}px;">{bb["header"]}</h2>', unsafe_allow_html=True)
                if bb.get('image'): st.image(bb['image'], width=int(bb.get('img_width', 500)))
                st.markdown(f'<p style="font-size:{bb.get("content_fs", 20)}px;">{bb["content"]}</p>', unsafe_allow_html=True)

    with col_side:
        # [우측 모듈형 블록]
        p.setdefault('side_blocks', [])
        if edit_enabled:
            with st.container(border=True):
                st.caption("➕ 우측 블록 추가")
                bc1, bc2, bc3 = st.columns(3)
                if bc1.button("📊 지표"): p['side_blocks'].append({"type": "metric", "label": "라벨", "value": "000", "fs": 20})
                if bc2.button("🖼️ 이미지"): p['side_blocks'].append({"type": "image", "src": None, "width": 300})
                if bc3.button("📝 텍스트"): p['side_blocks'].append({"type": "text", "content": "내용", "fs": 18})
        for idx, block in enumerate(p['side_blocks']):
            with st.container(border=edit_enabled):
                if edit_enabled:
                    if st.button(f"🗑️ 블록 {idx}", key=f"sb_del_{idx}"): p['side_blocks'].pop(idx); st.rerun()
                if block['type'] == "metric":
                    if edit_enabled: block['label'], block['value'] = st.text_input("라벨", block['label'], key=f"sbl_{idx}"), st.text_input("수치", block['value'], key=f"sbv_{idx}")
                    st.markdown(f'<div style="background:#f1f3f6; padding:12px; border-radius:12px; border-left:5px solid #007bff;"><p style="font-size:14px; margin:0;">{block["label"]}</p><p style="font-size:{block["fs"]}px; font-weight:bold; margin:0;">{block["value"]}</p></div>', unsafe_allow_html=True)
                elif block['type'] == "image":
                    if edit_enabled:
                        si = st.file_uploader(f"이미지 {idx}", type=['png', 'jpg'], key=f"sbi_{idx}")
                        if si: block['src'] = f"data:image/png;base64,{base64.b64encode(si.getvalue()).decode()}"
                        block['width'] = st.slider("너비", 50, 500, int(block['width']), key=f"sbiw_{idx}")
                    if block.get('src'): st.image(block['src'], width=int(block['width']))
                elif block['type'] == "text":
                    if edit_enabled: block['content'], block['fs'] = st.text_area("내용", block['content'], key=f"sbt_{idx}"), st.number_input("크기", 10, 60, int(block.get('fs', 18)), key=f"sbf_{idx}")
                    st.markdown(f'<p style="font-size:{block.get("fs", 18)}px; color:#444; margin:0;">{block["content"]}</p>', unsafe_allow_html=True)

sync_content_area(edit_mode)
