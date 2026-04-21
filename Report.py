import streamlit as st
import streamlit.components.v1 as components
import json
import time
import base64

# 1. 페이지 설정
st.set_page_config(page_title="POSCO E&C AI Master Builder", layout="wide")

# 2. [전역 저장소] 실시간 동기화 엔진의 핵심
@st.cache_resource
def get_global_store():
    return {
        "report_data": None,
        "current_page": 0,
        "user_labels": {}, 
        "sync_version": 0,
        "chat_history": [],
        "voice_active_users": {}, # {label: {"isMuted": bool, "level": int}}
        "voice_channel": "posco_briefing_room"
    }

shared_store = get_global_store()

# --- [스마트 JSON 어댑터: 무작위 파일 수용] ---
def adapt_json_format(raw_data):
    if isinstance(raw_data, dict) and "pages" in raw_data:
        return raw_data
    
    adapted_page = {
        "tab": "자동변환", "header": "수용된 데이터 리포트", "header_fs": 40,
        "content": "", "line_fs": [], "image": None, "img_width": 600,
        "side_blocks": [], "bottom_blocks": []
    }
    
    if isinstance(raw_data, dict):
        for k in ["title", "header", "name", "subject"]:
            if k in raw_data: adapted_page["header"] = str(raw_data[k]); break
        
        content_parts = []
        for k, v in raw_data.items():
            if isinstance(v, (str, int, float)) and len(str(v)) < 50:
                adapted_page["side_blocks"].append({"type": "metric", "label": str(k), "value": str(v), "fs": 22})
            else:
                content_parts.append(f"{k}: {v}")
        adapted_page["content"] = "\n".join(content_parts)
    
    return {"pages": [adapted_page]}

def create_empty_page():
    return {
        "tab": "새 페이지", "header": "제목을 입력하세요", "header_fs": 40,
        "content": "내용을 입력하세요", "line_fs": [24], "image": None, "img_width": 600,
        "side_blocks": [], "bottom_blocks": []
    }

# --- [ID 식별 및 무한루프 방지] ---
if "user_label" not in st.session_state:
    uid = st.query_params.get("uid")
    if not uid:
        uid = f"u_{int(time.time()*1000)}"
        st.query_params["uid"] = uid
    if uid in shared_store["user_labels"]:
        st.session_state.user_label = shared_store["user_labels"][uid]
    else:
        label = f"참여자 {len(shared_store['user_labels']) + 1}"
        shared_store["user_labels"][uid] = label
        st.session_state.user_label = label

# --- [실시간 음성 시스템: 레벨링 및 제어] ---
def agora_voice_system(app_id, channel, user_label):
    custom_html = f"""
    <script src="https://download.agora.io/sdk/release/AgoraRTC_N-4.11.0.js"></script>
    <div style="padding: 10px; background: #f8f9fa; border-radius: 12px; border: 1px solid #dee2e6; text-align: center; font-family: sans-serif;">
        <div id="v-status" style="font-size: 13px; font-weight: 700; margin-bottom: 5px; color: #495057;">🎙️ 음성 접속 상태</div>
        <div style="width: 100%; height: 8px; background: #e9ecef; border-radius: 4px; margin-bottom: 8px; overflow: hidden;">
            <div id="level-bar" style="width: 0%; height: 100%; background: linear-gradient(90deg, #28a745, #85ea2d); border-radius: 4px; transition: width 0.05s;"></div>
        </div>
        <div style="display: flex; justify-content: center; gap: 8px;">
            <button id="join" style="padding: 6px 12px; border-radius: 4px; border: none; background: #007bff; color: white; cursor: pointer; font-size: 12px; font-weight: bold;">🔊 연결</button>
            <button id="mute" style="padding: 6px 12px; border-radius: 4px; border: none; background: #6c757d; color: white; cursor: pointer; display: none; font-size: 12px; font-weight: bold;">🔇 끄기</button>
        </div>
    </div>
    <script>
        let client = AgoraRTC.createClient({{ mode: "rtc", codec: "vp8" }});
        let localTracks = {{ audioTrack: null }};
        let isMuted = false;
        client.enableAudioVolumeIndicator();
        async function join() {{
            try {{
                await client.join("{app_id}", "{channel}", null, null);
                localTracks.audioTrack = await AgoraRTC.createMicrophoneAudioTrack();
                await client.publish([localTracks.audioTrack]);
                document.getElementById("join").style.display = "none";
                document.getElementById("mute").style.display = "inline";
                document.getElementById("v-status").innerText = "🎙️ 음성 접속 완료";
                client.on("volume-indicator", (volumes) => {{
                    volumes.forEach((v) => {{ if (v.uid === 0) document.getElementById("level-bar").style.width = Math.min(v.level * 2, 100) + "%"; }});
                }});
                client.on("user-published", async (u, m) => {{ await client.subscribe(u, m); if (m === "audio") u.audioTrack.play(); }});
            }} catch (e) {{ console.error(e); }}
        }}
        document.getElementById("join").onclick = join;
        document.getElementById("mute").onclick = () => {{
            isMuted = !isMuted; localTracks.audioTrack.setEnabled(!isMuted);
            document.getElementById("mute").innerText = isMuted ? "🎤 켜기" : "🔇 끄기";
            if(isMuted) document.getElementById("level-bar").style.width = "0%";
        }};
    </script>
    """
    components.html(custom_html, height=130)

# --- 사이드바: 모든 제어 도구 집약 ---
with st.sidebar:
    st.title("🎙️ AI Live Sync")
    is_reporter = st.toggle("🔑 보고자 권한", value=False)
    my_label = "📢 보고자" if is_reporter else f"👤 {st.session_state.user_label}"
    st.info(f"📍 내 정보: **{my_label}**")
    
    try:
        agora_id = st.secrets["AGORA_APP_ID"]
        agora_voice_system(agora_id, shared_store["voice_channel"], my_label)
    except: st.warning("⚠️ Agora ID 설정 필요")

    with st.container(border=True):
        st.caption("👥 실시간 참여 명단")
        if is_reporter:
            options = ["📢 보고자"] + [f"👤 참여자 {i+1}" for i in range(len(shared_store['user_labels']))]
            shared_store["voice_active_users"] = st.multiselect("명단 동기화", options=options, default=list(shared_store["voice_active_users"]))
        for user in shared_store["voice_active_users"]: st.markdown(f"🟢 **{user}**")

    if is_reporter:
        st.divider()
        if shared_store["report_data"]:
            st.download_button("📥 최종 리포트 JSON 저장", data=json.dumps(shared_store["report_data"], indent=4, ensure_ascii=False), file_name="POSCO_Master_Report.json", use_container_width=True)
        uploaded_file = st.file_uploader("📂 JSON 로드 (무작위 형식 포함)", type=['json'])
        if uploaded_file and shared_store["report_data"] is None:
            raw_content = json.loads(uploaded_file.read().decode("utf-8"))
            shared_store["report_data"] = adapt_json_format(raw_content)
        if st.button("🚨 초기화"):
            shared_store.update({"report_data": None, "user_labels": {}, "chat_history": [], "current_page": 0})
            st.cache_resource.clear(); st.rerun()
        edit_mode = st.toggle("📝 전체 편집/저작 활성화", value=False)
    else: edit_mode = False

# --- [메인 브리핑 엔진: 동기화 및 편집] ---
@st.fragment(run_every="1s")
def main_content_area(edit_enabled):
    # 최상단 채팅
    with st.expander("💬 실시간 상호소통 채팅", expanded=False):
        c1, c2 = st.columns([4, 1])
        new_msg = c1.text_input("메시지", key="chat_input", label_visibility="collapsed")
        if c2.button("전송", use_container_width=True) and new_msg:
            shared_store["chat_history"].append(f"**{my_label}**: {new_msg}")
        chat_box = "".join([f"<div style='margin-bottom:5px;'>{m}</div>" for m in shared_store["chat_history"][-10:]])
        st.markdown(f"<div style='height:100px; overflow-y:auto; background:#f1f3f6; padding:10px; border-radius:8px; font-size:14px;'>{chat_box}</div>", unsafe_allow_html=True)

    if shared_store["report_data"] is None:
        if edit_enabled and st.button("📄 빈 보고서로 저작 시작"):
            shared_store["report_data"] = {"pages": [create_empty_page()]}
            st.rerun()
        st.warning("📂 파일을 로드하거나 새 보고서를 생성하세요.")
        return

    data = shared_store["report_data"]
    
    # 페이지 추가/삭제
    if edit_enabled:
        st.write("---")
        pc1, pc2 = st.columns([1, 5])
        if pc1.button("➕ 페이지 추가"):
            data['pages'].insert(shared_store["current_page"] + 1, create_empty_page())
            shared_store["current_page"] += 1; st.rerun()
        if pc2.button("🗑️ 현재 페이지 삭제") and len(data['pages']) > 1:
            data['pages'].pop(shared_store["current_page"])
            shared_store["current_page"] = max(0, shared_store["current_page"] - 1); st.rerun()

    p = data['pages'][shared_store["current_page"]]
    
    # 상단 네비게이션
    if is_reporter:
        tabs = {i: f"P{i+1}. {pg.get('tab', '')}" for i, pg in enumerate(data['pages'])}
        c_idx = st.radio("📑 이동", list(tabs.keys()), index=shared_store["current_page"], format_func=lambda x: tabs[x], horizontal=True)
        if shared_store["current_page"] != c_idx: shared_store["current_page"] = c_idx; shared_store["sync_version"] += 1
        if edit_enabled: p['tab'] = st.text_input("🔖 탭 제목", p.get('tab', ''), key="t_ed")
    else: st.subheader(f"📍 P{shared_store['current_page']+1}. {p.get('tab', '')}")

    st.divider(); col_main, col_side = st.columns([2, 1], gap="large")

    with col_main:
        if edit_enabled:
            c1, c2 = st.columns([4, 1])
            p['header'], p['header_fs'] = c1.text_input("📌 대제목", p.get('header', ''), key="main_h"), c2.number_input("크기", 10, 150, int(p.get('header_fs', 40)))
        st.markdown(f'<h1 style="font-size:{p.get("header_fs", 40)}px;">{p.get("header")}</h1>', unsafe_allow_html=True)

        if edit_enabled:
            img_f = st.file_uploader("🖼️ 이미지 업로드", type=['png', 'jpg'], key=f"img_{shared_store['current_page']}")
            if img_f: p['image'] = f"data:image/png;base64,{base64.b64encode(img_f.getvalue()).decode()}"
            p['img_width'] = st.slider("너비", 100, 1200, int(p.get('img_width', 600)))
        if p.get('image'): st.image(p['image'], width=int(p.get('img_width', 600)))

        # 본문 편집
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
            p['content'], p['line_fs'] = '\n'.join(new_l), new_f

        # 하단 무한 블록 섹션
        st.write("---"); p.setdefault('bottom_blocks', [])
        if edit_enabled and st.button("➕ 하단 새로운 블록 추가"):
            p['bottom_blocks'].append({"header": "제목", "header_fs": 32, "content": "내용", "content_fs": 20, "image": None, "img_width": 500})
        for idx, bb in enumerate(p['bottom_blocks']):
            with st.container(border=edit_enabled):
                if edit_enabled:
                    c1, c2, c3 = st.columns([4, 1, 1])
                    bb['header'], bb['header_fs'] = c1.text_input(f"B제목 {idx}", bb['header'], key=f"bbh_{idx}"), c2.number_input("크기", 10, 80, int(bb.get('header_fs', 32)), key=f"bbhf_{idx}")
                    if c3.button("🗑️", key=f"bbdel_{idx}"): p['bottom_blocks'].pop(idx); st.rerun()
                    bbi = st.file_uploader(f"B이미지 {idx}", type=['png', 'jpg'], key=f"bbi_{idx}")
                    if bbi: bb['image'] = f"data:image/png;base64,{base64.b64encode(bbi.getvalue()).decode()}"
                    bb['content'], bb['content_fs'] = st.text_area("B내용", bb['content'], key=f"bbc_{idx}"), st.number_input("B크기", 10, 60, int(bb.get('content_fs', 20)), key=f"bbcf_{idx}")
                st.markdown(f'<h2 style="font-size:{bb.get("header_fs", 32)}px;">{bb["header"]}</h2>', unsafe_allow_html=True)
                if bb.get('image'): st.image(bb['image'], width=int(bb.get('img_width', 500)))
                st.markdown(f'<p style="font-size:{bb.get("content_fs", 20)}px;">{bb["content"]}</p>', unsafe_allow_html=True)

    with col_side:
        # 우측 모듈형 블록
        p.setdefault('side_blocks', [])
        if edit_enabled:
            st.caption("➕ 우측 블록 추가")
            bc1, bc2, bc3 = st.columns(3)
            if bc1.button("📊 지표"): p['side_blocks'].append({"type": "metric", "label": "라벨", "value": "0", "fs": 20})
            if bc2.button("🖼️ 이미지"): p['side_blocks'].append({"type": "image", "src": None, "width": 300})
            if bc3.button("📝 텍스트"): p['side_blocks'].append({"type": "text", "content": "내용", "fs": 18})
        for idx, block in enumerate(p['side_blocks']):
            with st.container(border=edit_enabled):
                if edit_enabled and st.button(f"🗑️ {idx}", key=f"sb_del_{idx}"): p['side_blocks'].pop(idx); st.rerun()
                if block['type'] == "metric":
                    if edit_enabled: block['label'], block['value'] = st.text_input("라벨", block['label'], key=f"sbl_{idx}"), st.text_input("수치", block['value'], key=f"sbv_{idx}")
                    st.markdown(f'<div style="background:#f1f3f6; padding:12px; border-radius:12px; border-left:5px solid #007bff;"><p style="font-size:14px; margin:0;">{block["label"]}</p><p style="font-size:24px; font-weight:bold; margin:0;">{block["value"]}</p></div>', unsafe_allow_html=True)
                elif block['type'] == "image":
                    if edit_enabled:
                        si = st.file_uploader(f"우측 이미지 {idx}", type=['png', 'jpg'], key=f"sbi_{idx}")
                        if si: block['src'] = f"data:image/png;base64,{base64.b64encode(si.getvalue()).decode()}"
                    if block.get('src'): st.image(block['src'], width=int(block.get('width', 300)))
                elif block['type'] == "text":
                    if edit_enabled: block['content'], block['fs'] = st.text_area("내용", block['content'], key=f"sbt_{idx}"), st.number_input("크기", 10, 60, int(block.get('fs', 18)), key=f"sbf_{idx}")
                    st.markdown(f'<p style="font-size:{block.get("fs", 18)}px; color:#444; margin:0;">{block["content"]}</p>', unsafe_allow_html=True)

main_content_area(edit_mode)
