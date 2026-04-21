import streamlit as st
import streamlit.components.v1 as components
import json
import time

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Live Sync", layout="wide")

# 2. [전역 공유 저장소]
@st.cache_resource
def get_global_store():
    return {
        "report_data": None,
        "current_page": 0,
        "active_users": 0,
        "sync_version": 0,
        "chat_logs": [],
        "voice_channel": "posco_briefing_room"
    }

shared_store = get_global_store()

if "user_counted" not in st.session_state:
    shared_store["active_users"] += 1
    st.session_state.user_counted = True

# 3. [Agora 음성 내재화 함수] - st.secrets에서 ID를 가져옵니다.
def agora_voice_component(app_id, channel, role):
    custom_html = f"""
    <script src="https://download.agora.io/sdk/release/AgoraRTC_N-4.11.0.js"></script>
    <div style="padding: 15px; background: #f8f9fa; border-radius: 12px; border: 1px solid #dee2e6; text-align: center; font-family: sans-serif;">
        <p style="margin: 0 0 10px 0; font-weight: 600; color: #343a40;">🎙️ 실시간 음성 브리핑</p>
        <button id="join" style="padding: 10px 20px; cursor: pointer; border-radius: 6px; border: none; background: #007bff; color: white; font-weight: bold;">🔊 연결하기</button>
        <button id="leave" style="padding: 10px 20px; cursor: pointer; border-radius: 6px; border: none; background: #dc3545; color: white; font-weight: bold; display: none;">종료</button>
        <p id="status" style="margin-top: 8px; font-size: 12px; color: #6c757d;">연결 대기 중</p>
    </div>

    <script>
        let client = AgoraRTC.createClient({{ mode: "rtc", codec: "vp8" }});
        let localTracks = {{ audioTrack: null }};
        
        async function join() {{
            try {{
                await client.join("{app_id}", "{channel}", null, null);
                document.getElementById("status").innerText = "연결됨 (통화 중)";
                
                if ("{role}" === "reporter") {{
                    localTracks.audioTrack = await AgoraRTC.createMicrophoneAudioTrack();
                    await client.publish([localTracks.audioTrack]);
                }}

                client.on("user-published", async (user, mediaType) => {{
                    await client.subscribe(user, mediaType);
                    if (mediaType === "audio") {{
                        user.audioTrack.play();
                    }}
                }});

                document.getElementById("join").style.display = "none";
                document.getElementById("leave").style.display = "inline";
            }} catch (e) {{
                console.error(e);
                document.getElementById("status").innerText = "연결 실패: ID 확인 필요";
            }}
        }}

        async function leave() {{
            for (let trackName in localTracks) {{
                let track = localTracks[trackName];
                if (track) {{ track.stop(); track.close(); }}
            }}
            await client.leave();
            document.getElementById("status").innerText = "연결 종료";
            document.getElementById("join").style.display = "inline";
            document.getElementById("leave").style.display = "none";
        }}

        document.getElementById("join").onclick = join;
        document.getElementById("leave").onclick = leave;
    </script>
    """
    components.html(custom_html, height=130)

# --- 사이드바 영역 ---
with st.sidebar:
    st.title("🎙️ AI Live Sync")
    is_reporter = st.toggle("🔑 보고자 권한 활성화", value=False)
    
    # [보안 적용] st.secrets에서 안전하게 App ID 호출
    try:
        agora_id = st.secrets["AGORA_APP_ID"]
        agora_voice_component(
            app_id=agora_id, 
            channel=shared_store["voice_channel"],
            role="reporter" if is_reporter else "audience"
        )
    except:
        st.warning("⚠️ Agora App ID 설정이 필요합니다. (.streamlit/secrets.toml)")

    st.success(f"👥 접속자: **{shared_store['active_users']}명**")
    
    # [보고자 전용 메뉴] 보고받는 자에게는 노출되지 않음
    if is_reporter:
        st.divider()
        if st.button("🚨 시스템 전체 초기화", use_container_width=True):
            shared_store["report_data"] = None
            shared_store["chat_logs"] = []
            shared_store["sync_version"] += 1
            st.cache_resource.clear()
            st.rerun()

        st.subheader("📂 보고서 로드")
        uploaded_file = st.file_uploader("JSON 업로드", type=['json', 'js'], key="report_uploader")
        if uploaded_file:
            try:
                content = json.loads(uploaded_file.read().decode("utf-8"))
                if shared_store["report_data"] is None:
                    shared_store["report_data"] = content
                    shared_store["sync_version"] += 1
            except: st.error("파일 오류")
        current_edit_mode = st.toggle("📝 실시간 편집 모드", value=False)
    else:
        st.info("🛰️ 보고자의 브리핑을 수신 중입니다. [연결하기]를 누르면 음성을 들을 수 있습니다.")

# 4. [동기화 엔진] 채팅 및 본문 렌더링
@st.fragment(run_every="1s")
def sync_content_area(edit_enabled):
    # --- 실시간 채팅 ---
    with st.expander("💬 실시간 소통 및 질의응답", expanded=True):
        c_col, i_col = st.columns([4, 1])
        with i_col:
            user_role = "📢 보고자" if is_reporter else "👤 접속자"
            chat_input = st.text_input("메시지", key="chat_in", label_visibility="collapsed", placeholder="입력...")
            if st.button("전송", use_container_width=True):
                if chat_input:
                    shared_store["chat_logs"].insert(0, f"[{time.strftime('%H:%M:%S')}] **{user_role}**: {chat_input}")
                    shared_store["sync_version"] += 1
        with c_col:
            if not shared_store["chat_logs"]: st.caption("대화가 없습니다.")
            for log in shared_store["chat_logs"][:3]: st.write(log)

    if shared_store["report_data"] is None:
        st.warning("🛰️ 보고서가 로드되지 않았습니다. 보고자의 업로드를 기다려주세요.")
        return

    data = shared_store["report_data"]
    tab_labels = [f"P{i+1}. {p.get('tab', '')}" for i, p in enumerate(data['pages'])]
    
    if is_reporter:
        current_tab_idx = st.radio("📑 페이지 이동", range(len(tab_labels)), 
                                   index=shared_store["current_page"] if shared_store["current_page"] < len(tab_labels) else 0,
                                   format_func=lambda x: tab_labels[x], horizontal=True)
        if shared_store["current_page"] != current_tab_idx:
            shared_store["current_page"] = current_tab_idx
            shared_store["sync_version"] += 1
    else:
        current_tab_idx = shared_store["current_page"]
        if current_tab_idx >= len(tab_labels): current_tab_idx = 0
        st.warning(f"📍 현재 브리핑 위치: **{tab_labels[current_tab_idx]}**")

    # 리포트 본문 렌더링
    p = data['pages'][current_tab_idx]
    st.divider()
    col_main, col_side = st.columns([2, 1], gap="large")
    
    with col_main:
        if is_reporter and edit_enabled:
            p['tab'] = st.text_input("🔖 탭 이름", p.get('tab', ''), key=f"t_{current_tab_idx}")
            p['header'] = st.text_input("📌 제목", p.get('header', ''), key=f"h_{current_tab_idx}")
            p['content'] = st.text_area("📄 본문", p.get('content', ''), height=250, key=f"c_{current_tab_idx}")
            if 'img_width' not in p: p['img_width'] = 800
            p['img_width'] = st.slider("🖼️ 크기", 200, 1200, int(p['img_width']), key=f"i_{current_tab_idx}")
            shared_store["sync_version"] += 1
        
        st.markdown(f"# {p.get('header', '')}")
        if "image" in p: st.image(p["image"], width=int(p.get('img_width', 800)))
        for para in p.get('content', '').split('\n'):
            if para.strip(): st.markdown(f"### **{para.strip()}**")

    with col_side:
        st.subheader(p.get('metrics_title', '📊 주요 지표'))
        if "metrics" in p:
            for idx, m in enumerate(p['metrics']):
                if is_reporter and edit_enabled:
                    m[0] = st.text_input(f"라벨{idx}", m[0], key=f"ml_{current_tab_idx}_{idx}")
                    m[1] = st.text_input(f"수치{idx}", m[1], key=f"mv_{current_tab_idx}_{idx}")
                st.metric(label=m[0], value=m[1])

# 실행
sync_content_area(current_edit_mode if is_reporter else False)
