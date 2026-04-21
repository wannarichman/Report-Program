import streamlit as st
import streamlit.components.v1 as components
import json
import time
import base64

# 1. 페이지 설정 및 디자인 프레임워크 (CSS 강화)
st.set_page_config(page_title="POSCO E&C AI Live Sync Master", layout="wide")

st.markdown("""
    <style>
    .main-frame {
        background-color: #ffffff; padding: 25px; border-radius: 15px;
        border: 1px solid #e1e4e8; min-height: 450px; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }
    .content-line {
        white-space: pre-wrap; word-wrap: break-word;
        margin-bottom: 15px; line-height: 1.6;
    }
    .side-frame {
        background-color: #f8f9fa; padding: 20px; border-radius: 12px;
        border-left: 6px solid #007bff; margin-bottom: 15px; min-height: 100px;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. [전역 저장소]
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

# --- [스마트 JSON 어댑터 및 페이지 생성기] ---
def adapt_json_format(raw_data):
    if isinstance(raw_data, dict) and "pages" in raw_data:
        return raw_data
    adapted_page = {
        "tab": "자동변환", "header": "수용 데이터 리포트", "header_fs": 40,
        "content": "", "content_fs": 22, "image": None, "img_width": 800,
        "side_blocks": [], "bottom_blocks": []
    }
    if isinstance(raw_data, dict):
        for k in ["title", "header", "name"]:
            if k in raw_data: adapted_page["header"] = str(raw_data[k]); break
        content_parts = [f"{k}: {v}" for k, v in raw_data.items() if not isinstance(v, (dict, list))]
        adapted_page["content"] = "\n".join(content_parts)
    return {"pages": [adapted_page]}

def create_empty_page():
    return {
        "tab": "새 페이지", "header": "제목을 입력하세요", "header_fs": 40,
        "content": "내용을 입력하세요 (엔터로 줄바꿈 가능)", "content_fs": 22,
        "image": None, "img_width": 800, "side_blocks": [], "bottom_blocks": []
    }

# --- [ID 식별 및 음성 시스템] ---
if "user_label" not in st.session_state:
    uid = st.query_params.get("uid", f"u_{int(time.time()*1000)}")
    st.query_params["uid"] = uid
    label = shared_store["user_labels"].get(uid, f"참여자 {len(shared_store['user_labels']) + 1}")
    shared_store["user_labels"][uid] = label
    st.session_state.user_label = label

def agora_voice_system(app_id, channel, user_label):
    custom_html = f"""
    <script src="https://download.agora.io/sdk/release/AgoraRTC_N-4.11.0.js"></script>
    <div style="padding: 10px; background: #f8f9fa; border-radius: 12px; border: 1px solid #dee2e6; text-align: center;">
        <div id="v-status" style="font-size: 13px; font-weight: 700; margin-bottom: 5px;">🎙️ 음성 접속</div>
        <div style="width: 100%; height: 8px; background: #e9ecef; border-radius: 4px; margin-bottom: 8px; overflow: hidden;">
            <div id="level-bar" style="width: 0%; height: 100%; background: linear-gradient(90deg, #28a745, #85ea2d); transition: width 0.05s;"></div>
        </div>
        <button id="join" style="padding: 6px 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">🔊 연결</button>
        <button id="mute" style="padding: 6px 12px; background: #6c757d; color: white; border: none; border-radius: 4px; cursor: pointer; display: none;">🔇 끄기</button>
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
                client.on("volume-indicator", (vs) => {{ vs.forEach((v) => {{ if(v.uid === 0) document.getElementById("level-bar").style.width = Math.min(v.level * 2, 100) + "%"; }}); }});
                client.on("user-published", async (u, m) => {{ await client.subscribe(u, m); if(m === "audio") u.audioTrack.play(); }});
            }} catch (e) {{ console.error(e); }}
        }}
        document.getElementById("join").onclick = join;
        document.getElementById("mute").onclick = () => {{ isMuted = !isMuted; localTracks.audioTrack.setEnabled(!isMuted); document.getElementById("mute").innerText = isMuted ? "🎤 켜기" : "🔇 끄기"; }};
    </script>
    """
    components.html(custom_html, height=130)

# --- 사이드바 ---
with st.sidebar:
    st.title("🎙️ AI Live Sync")
    is_reporter = st.toggle("🔑 보고자 권한", value=False)
    my_label = "📢 보고자" if is_reporter else f"👤 {st.session_state.user_label}"
    st.info(f"📍 접속: **{my_label}**")
    
    try:
        agora_id = st.secrets["AGORA_APP_ID"]
        agora_voice_system(agora_id, shared_store["voice_channel"], my_label)
    except: st.warning("⚠️ Agora ID 설정 필요")

    with st.container(border=True):
        st.caption("👥 음성 참여 명단")
        if is_reporter:
            options = ["📢 보고자"] + [f"👤 참여자 {i+1}" for i in range(len(shared_store['user_labels']))]
            shared_store["voice_active_users"] = st.multiselect("명단 동기화", options=options, default=list(shared_store.get("voice_active_users_list", [])))
            shared_store["voice_active_users_list"] = shared_store["voice_active_users"]
        for user in shared_store.get("voice_active_users_list", []): st.markdown(f"🟢 **{user}**")

    if is_reporter:
        st.divider()
        if shared_store["report_data"]:
            st.download_button("📥 최종 리포트 JSON 저장", data=json.dumps(shared_store["report_data"], indent=4, ensure_ascii=False), file_name="Master_Report.json", use_container_width=True)
        uploaded_file = st.file_uploader("📂 JSON 로드", type=['json'])
        if uploaded_file and shared_store["report_data"] is None:
            shared_store["report_data"] = adapt_json_format(json.loads(uploaded_file.read().decode("utf-8")))
        if st.button("🚨 초기화"):
            shared_store.update({"report_data": None, "user_labels": {}, "chat_history": [], "current_page": 0})
            st.cache_resource.clear(); st.rerun()
        edit_mode = st.toggle("📝 레이아웃 저작 모드", value=False)
    else: edit_mode = False

# --- [메인 브리핑 엔진] ---
@st.fragment(run_every="1s")
def main_content_area(edit_enabled):
    # 1. 상호소통 채팅
    with st.expander("💬 실시간 채팅", expanded=False):
        c1, c2 = st.columns([4, 1])
        new_msg = c1.text_input("메시지", key="chat_in", label_visibility="collapsed")
        if c2.button("전송") and new_msg:
            shared_store["chat_history"].append(f"**{my_label}**: {new_msg}")
        chat_box = "".join([f"<div style='margin-bottom:5px;'>{m}</div>" for m in shared_store["chat_history"][-10:]])
        st.markdown(f"<div style='height:100px; overflow-y:auto; background:#f1f3f6; padding:10px; border-radius:8px;'>{chat_box}</div>", unsafe_allow_html=True)

    if shared_store["report_data"] is None:
        if edit_enabled and st.button("📄 새 보고서 만들기"):
            shared_store["report_data"] = {"pages": [create_empty_page()]}; st.rerun()
        st.warning("📂 파일을 로드하세요.")
        return

    data = shared_store["report_data"]
    
    # 페이지 확장 로직
    if edit_enabled:
        st.write("---")
        pc1, pc2 = st.columns([1, 4])
        if pc1.button("➕ 페이지 추가"):
            data['pages'].append(create_empty_page())
            shared_store["current_page"] = len(data['pages']) - 1; st.rerun()
        if pc2.button("🗑️ 삭제") and len(data['pages']) > 1:
            data['pages'].pop(shared_store["current_page"])
            shared_store["current_page"] = max(0, shared_store["current_page"] - 1); st.rerun()

    p = data['pages'][shared_store["current_page"]]
    
    # 네비게이션
    if is_reporter:
        tabs = {i: f"P{i+1}. {pg.get('tab', '')}" for i, pg in enumerate(data['pages'])}
        shared_store["current_page"] = st.radio("📑 이동", list(tabs.keys()), index=shared_store["current_page"], format_func=lambda x: tabs[x], horizontal=True)
    
    st.markdown(f'<h1 style="text-align:center; font-size:{p.get("header_fs", 40)}px;">{p.get("header")}</h1>', unsafe_allow_html=True)
    st.divider()

    # 레이아웃 분할 (2.5:1 고정 비율)
    col_main, col_side = st.columns([2.5, 1], gap="large")

    with col_main:
        st.markdown('<div class="main-frame">', unsafe_allow_html=True)
        if edit_enabled:
            with st.expander("📝 본문 및 이미지 편집"):
                img_f = st.file_uploader("그림", type=['png', 'jpg'], key=f"img_{shared_store['current_page']}")
                if img_f: p['image'] = f"data:image/png;base64,{base64.b64encode(img_f.getvalue()).decode()}"
                p['img_width'] = st.slider("너비", 200, 1000, int(p.get('img_width', 800)))
                p['content_fs'] = st.slider("본문 크기", 10, 60, int(p.get('content_fs', 22)))
                p['header'] = st.text_input("제목 수정", p.get('header', ''))
                p['tab'] = st.text_input("탭 이름", p.get('tab', ''))

        if p.get('image'): st.image(p['image'], width=int(p.get('img_width', 800)))
        
        if edit_enabled:
            p['content'] = st.text_area("내용 (엔터로 줄바꿈)", p.get('content', ''), height=300)
        else:
            st.markdown(f'<div class="content-line" style="font-size:{p.get("content_fs", 22)}px;">{p.get("content")}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        for idx, bb in enumerate(p.get('bottom_blocks', [])):
            st.markdown(f'<div class="main-frame"><h2 style="font-size:{bb.get("header_fs", 28)}px;">{bb["header"]}</h2>', unsafe_allow_html=True)
            if edit_enabled: bb['content'] = st.text_area(f"상세내용 {idx}", bb['content'])
            else: st.markdown(f'<div class="content-line" style="font-size:{bb.get("content_fs", 20)}px;">{bb["content"]}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    with col_side:
        st.markdown("<p style='font-weight:bold; color:#666;'>📊 PERFORMANCE</p>", unsafe_allow_html=True)
        p.setdefault('side_blocks', [])
        if edit_enabled and st.button("➕ 사이드 블록"): p['side_blocks'].append({"type": "metric", "label": "라벨", "value": "0"})
        
        for idx, block in enumerate(p['side_blocks']):
            st.markdown('<div class="side-frame">', unsafe_allow_html=True)
            if edit_enabled:
                if st.button(f"🗑️ {idx}"): p['side_blocks'].pop(idx); st.rerun()
                block['label'], block['value'] = st.text_input("라벨", block['label'], key=f"sl_{idx}"), st.text_input("값", block['value'], key=f"sv_{idx}")
            st.markdown(f'<small>{block["label"]}</small><div style="font-size:26px; font-weight:800; color:#007bff;">{block["value"]}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

main_content_area(edit_mode)
