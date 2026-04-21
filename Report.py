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
        "user_list": [], 
        "sync_version": 0,
        "chat_logs": [],
        "voice_channel": "posco_briefing_room"
    }

shared_store = get_global_store()

# [참여자 레벨링 및 본인 식별 로직]
if "user_label" not in st.session_state:
    shared_store["active_users"] += 1
    # 들어온 순서대로 번호 부여
    st.session_state.user_num = shared_store["active_users"]
    st.session_state.user_label = f"참여자 {st.session_state.user_num}"
    shared_store["user_list"].append(st.session_state.user_label)

# 3. [Agora 음성 컴포넌트]
def agora_voice_component(app_id, channel, role):
    custom_html = f"""
    <script src="https://download.agora.io/sdk/release/AgoraRTC_N-4.11.0.js"></script>
    <div style="padding: 15px; background: #f8f9fa; border-radius: 12px; border: 1px solid #dee2e6; text-align: center; font-family: sans-serif;">
        <p style="margin: 0 0 10px 0; font-weight: 600; color: #343a40;">🎙️ 실시간 음성 브리핑</p>
        <div id="audio-visualizer" style="display: none; justify-content: center; align-items: flex-end; height: 30px; gap: 3px; margin-bottom: 10px;">
            <div class="bar" style="width: 4px; height: 10px; background: #007bff; transition: height 0.1s;"></div>
            <div class="bar" style="width: 4px; height: 20px; background: #007bff; transition: height 0.1s;"></div>
            <div class="bar" style="width: 4px; height: 15px; background: #007bff; transition: height 0.1s;"></div>
            <div class="bar" style="width: 4px; height: 25px; background: #007bff; transition: height 0.1s;"></div>
        </div>
        <button id="join" style="padding: 10px 20px; cursor: pointer; border-radius: 6px; border: none; background: #007bff; color: white; font-weight: bold;">🔊 연결하기</button>
        <button id="leave" style="padding: 10px 20px; cursor: pointer; border-radius: 6px; border: none; background: #dc3545; color: white; font-weight: bold; display: none;">종료</button>
        <p id="status" style="margin-top: 8px; font-size: 12px; color: #6c757d;">연결 대기 중</p>
    </div>
    <script>
        let client = AgoraRTC.createClient({{ mode: "rtc", codec: "vp8" }});
        let localTracks = {{ audioTrack: null }};
        let audioInterval;
        async function join() {{
            try {{
                await client.join("{app_id}", "{channel}", null, null);
                document.getElementById("status").innerText = "연결됨 (통화 중)";
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
            }} catch (e) {{ document.getElementById("status").innerText = "연결 실패"; }}
        }}
        async function leave() {{
            if(audioInterval) clearInterval(audioInterval);
            for (let trackName in localTracks) {{ if (localTracks[trackName]) {{ localTracks[trackName].stop(); localTracks[trackName].close(); }} }}
            await client.leave();
            document.getElementById("status").innerText = "연결 종료";
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
    
    # [수정] 본인 식별 이름 결정
    if is_reporter:
        my_name_display = "📢 보고자 (나)"
    else:
        my_name_display = f"👤 {st.session_state.user_label} (나)"
    
    st.info(f"📍 접속 계정: **{my_name_display}**")

    # Agora 음성 컴포넌트
    try:
        agora_id = st.secrets["AGORA_APP_ID"]
        agora_voice_component(
            app_id=agora_id, 
            channel=shared_store["voice_channel"],
            role="reporter" if is_reporter else "audience"
        )
    except:
        st.warning("⚠️ Agora ID 설정 필요")

    # [참여자 목록 표시] 본인일 경우 (나) 표시
    with st.expander(f"👥 현재 참여자 ({len(shared_store['user_list'])}명)", expanded=False):
        if is_reporter:
            st.write("- **📢 보고자 (나)**")
        else:
            st.write("- 📢 보고자")
            
        for user in shared_store["user_list"]:
            if not is_reporter and user == st.session_state.user_label:
                st.write(f"- **👤 {user} (나)**")
            else:
                st.write(f"- 👤 {user}")

    if is_reporter:
        st.divider()
        if st.button("🚨 시스템 전체 초기화", use_container_width=True):
            shared_store.update({"report_data": None, "chat_logs": [], "sync_version": shared_store["sync_version"]+1, "active_users": 0, "user_list": []})
            st.cache_resource.clear()
            st.rerun()
        uploaded_file = st.file_uploader("JSON 업로드", type=['json', 'js'])
        if uploaded_file:
            content = json.loads(uploaded_file.read().decode("utf-8"))
            if shared_store["report_data"] is None:
                shared_store["report_data"] = content
                shared_store["sync_version"] += 1
        current_edit_mode = st.toggle("📝 실시간 편집 모드", value=False)

# 4. [동기화 엔진]
@st.fragment(run_every="1s")
def sync_content_area(edit_enabled):
    with st.expander("💬 실시간 채팅 및 질의응답", expanded=True):
        chat_col, input_col = st.columns([4, 1])
        with input_col:
            # [채팅 식별자 수정]
            chat_sender = "📢 보고자" if is_reporter else f"👤 {st.session_state.user_label}"
            chat_input = st.text_input("메시지", key="chat_in", label_visibility="collapsed", placeholder="입력...")
            if st.button("전송", use_container_width=True):
                if chat_input:
                    shared_store["chat_logs"].insert(0, f"[{time.strftime('%H:%M:%S')}] **{chat_sender}**: {chat_input}")
                    shared_store["sync_version"] += 1
        with chat_col:
            for log in shared_store["chat_logs"][:3]:
                # 채팅 로그에서도 본인이 쓴 글 강조 (옵션)
                st.write(log)

    if shared_store["report_data"] is None:
        st.warning("🛰️ 보고서 대기 중...")
        return

    data = shared_store["report_data"]
    tab_labels = [f"P{i+1}. {p.get('tab', '')}" for i, p in enumerate(data['pages'])]
    
    if is_reporter:
        current_tab_idx = st.radio("📑 페이지 이동", range(len(tab_labels)), index=shared_store["current_page"], format_func=lambda x: tab_labels[x], horizontal=True)
        if shared_store["current_page"] != current_tab_idx:
            shared_store["current_page"] = current_tab_idx
            shared_store["sync_version"] += 1
    else:
        current_tab_idx = shared_store["current_page"]
        if current_tab_idx >= len(tab_labels): current_tab_idx = 0
        st.warning(f"📍 현재 브리핑 위치: **{tab_labels[current_tab_idx]}**")

    p = data['pages'][current_tab_idx]
    st.divider()
    col_main, col_side = st.columns([2, 1], gap="large")
    
    with col_main:
        if is_reporter and edit_enabled:
            p['header'] = st.text_input("📌 제목", p.get('header', ''), key=f"h_{current_tab_idx}")
            p['content'] = st.text_area("📄 본문", p.get('content', ''), height=250, key=f"c_{current_tab_idx}")
            shared_store["sync_version"] += 1
        st.markdown(f"# {p.get('header', '')}")
        if "image" in p: st.image(p["image"], width=800)
        for para in p.get('content', '').split('\n'):
            if para.strip(): st.markdown(f"### **{para.strip()}**")

    with col_side:
        st.subheader(p.get('metrics_title', '📊 지표'))
        if "metrics" in p:
            for idx, m in enumerate(p['metrics']):
                if is_reporter and edit_enabled:
                    m[0] = st.text_input(f"라벨{idx}", m[0], key=f"ml_{idx}")
                    m[1] = st.text_input(f"수치{idx}", m[1], key=f"mv_{idx}")
                st.metric(label=m[0], value=m[1])

# 실행
sync_content_area(current_edit_mode if is_reporter else False)
