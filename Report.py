import streamlit as st
import streamlit.components.v1 as components
import json
import time
import base64

# ==========================================
# 1. 페이지 설정 및 프리미엄 클린 디자인 CSS
# ==========================================
st.set_page_config(page_title="AI Live Sync Master Builder", layout="wide")

st.markdown("""
    <style>
    /* 앱 전체 배경을 깨끗한 흰색으로 */
    [data-testid="stAppViewContainer"] { 
        background-color: #ffffff !important; 
    }
    
    /* 메인 화면 컨테이너: 심플하고 세련된 얇은 테두리와 은은한 그림자 */
    .main [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #ffffff !important;
        border: 1px solid #dee2e6 !important; 
        border-radius: 16px !important;
        padding: 35px 40px !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.04) !important; 
        margin-bottom: 50px !important; 
    }
    
    /* 사이드바 내부 컨테이너 레이아웃 유지 */
    [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid #dee2e6 !important; 
        padding: 15px !important; 
        box-shadow: none !important; 
        margin-bottom: 10px !important;
    }
    
    /* 우측 사이드 슬롯: 파란 테두리 없이 깔끔한 여백 레이아웃 */
    .side-slot-card {
        padding: 10px 0px; 
        margin-bottom: 16px;
    }
    
    /* 줄 단위 편집 텍스트 기본 스타일 */
    .text-line { 
        white-space: pre-wrap; 
        word-wrap: break-word; 
        line-height: 1.8; 
        margin-bottom: 10px; 
        color: #334155; 
    }
    
    /* 음성 연결 패널 디자인 */
    .voice-panel { 
        background: #ffffff; 
        border: 1px solid #dee2e6; 
        padding: 15px; 
        border-radius: 16px; 
        text-align: center; 
        margin-bottom: 15px; 
    }
    
    /* 음성 연결/음소거 버튼 스타일링 */
    .btn-join { 
        padding: 8px 16px; 
        background: #007bff; 
        color: white; 
        border: none; 
        border-radius: 8px; 
        cursor: pointer; 
        font-weight: bold; 
        width: 100%;
    }
    .btn-mute { 
        padding: 8px 16px; 
        background: #6c757d; 
        color: white; 
        border: none; 
        border-radius: 8px; 
        cursor: pointer; 
        font-weight: bold; 
        width: 100%;
    }
    .btn-mute.active { 
        background: #dc3545; 
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 전역 저장소 (Global Store)
# ==========================================
@st.cache_resource
def get_global_store():
    return {
        "report_data": None, 
        "current_page": 0, 
        "user_labels": {}, 
        "chat_history": [], 
        "active_sessions": {}, # {uid: {"label": label, "last_seen": timestamp, "voice_connected": bool}}
        "voice_channel": "posco_briefing_room"
    }

shared_store = get_global_store()

# ==========================================
# 3. 유틸리티 로직 및 표준 양식
# ==========================================
def get_sample_json_guide():
    return {
        "pages": [{
            "tab": "샘플 페이지",
            "header": "여기에 전체 리포트 제목 입력",
            "header_fs": 45,
            "header_color": "#1a1c1e",
            "sections": [{
                "title": "섹션 제목",
                "title_fs": 32,
                "title_color": "#1a1c1e",
                "col_ratio": 2.0,
                "main_image": None,
                "full_width": True,
                "lines": [{"text": "여기에 본문 내용을 입력하세요.", "size": 22, "color": "#1e293b"}],
                "side_items": [
                    {"type": "metric", "label": "지표명", "value": "수치", "color": "#007bff", "label_fs": 14, "label_color": "#64748b", "value_fs": 28}
                ]
            }]
        }]
    }

def create_empty_page():
    return get_sample_json_guide()["pages"][0]

def adapt_json_format(raw_data):
    if isinstance(raw_data, dict) and "pages" in raw_data: 
        return raw_data
    return {"pages": [create_empty_page()]}

# ==========================================
# 4. ID 식별 및 음성 시스템 (Agora)
# ==========================================
if "uid" not in st.session_state:
    url_uid = st.query_params.get("uid")
    if url_uid:
        st.session_state.uid = url_uid
    else:
        new_uid = f"u_{int(time.time()*1000)}"
        st.session_state.uid = new_uid
        st.query_params["uid"] = new_uid

if "user_label" not in st.session_state:
    active_now = len([s for s in shared_store["active_sessions"].values() if time.time() - s["last_seen"] < 10])
    label = f"참여자 {active_now + 1}"
    st.session_state.user_label = label

def agora_voice_system(app_id, channel, user_label):
    custom_html = f"""
    <script src="https://download.agora.io/sdk/release/AgoraRTC_N-4.11.0.js"></script>
    <div class="voice-panel">
        <div id="v-status" style="font-size: 13px; font-weight: 700; margin-bottom: 8px; color:#1e293b;">🎙️ {user_label} Voice System</div>
        <div style="width: 100%; height: 10px; background: #e2e8f0; border-radius: 5px; margin-bottom: 12px; overflow: hidden;">
            <div id="level-bar" style="width: 0%; height: 100%; background: #28a745; transition: width 0.05s;"></div>
        </div>
        <button id="mute" class="btn-mute">🎤 마이크 켬</button>
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
                
                client.on("volume-indicator", (vs) => {{ 
                    vs.forEach((v) => {{ 
                        if(v.uid === 0 && !isMuted) document.getElementById("level-bar").style.width = Math.min(v.level * 2, 100) + "%"; 
                        if(isMuted) document.getElementById("level-bar").style.width = "0%";
                    }}); 
                }});
                client.on("user-published", async (u, m) => {{ await client.subscribe(u, m); if(m === "audio") u.audioTrack.play(); }});
            }} catch (e) {{ console.error(e); }}
        }}
        
        function toggleMute() {{
            if (!localTracks.audioTrack) return;
            isMuted = !isMuted; localTracks.audioTrack.setEnabled(!isMuted);
            const btn = document.getElementById("mute");
            if (isMuted) {{ btn.innerText = "🔇 마이크 끔"; btn.classList.add("active"); }} 
            else {{ btn.innerText = "🎤 마이크 켬"; btn.classList.remove("active"); }}
        }}
        join(); # 보이스 시스템 접속 토글 시 자동 실행
        document.getElementById("mute").onclick = toggleMute;
    </script>
    """
    components.html(custom_html, height=150)

# [수정] 참여자 화면 실시간 동기화 및 '마이크 연결자' 전용 필터링 프래그먼트
@st.fragment(run_every="1s")
def sync_member_list(my_uid):
    with st.container(border=True):
        st.caption("👥 실시간 보이스 연결 멤버")
        now = time.time()
        temp_sessions = {}
        
        for uid, info in shared_store["active_sessions"].items():
            # [핵심] 6초 이내 활동 중이고 + 마이크 연결(connected) 버튼을 누른 사람만 필터링
            if (now - info["last_seen"] < 6) and info.get("connected", False):
                base_label = info["label"]
                is_me = (uid == my_uid)
                if base_label not in temp_sessions or is_me:
                    temp_sessions[base_label] = is_me
        
        if not temp_sessions:
            st.write("연결된 멤버 없음")
        else:
            for label in sorted(temp_sessions.keys()):
                display_name = label
                if temp_sessions[label]: display_name += " (나)"
                st.markdown(f"🟢 **{display_name}**")

# ==========================================
# 5. 사이드바 (Sidebar) 통제 센터
# ==========================================
with st.sidebar:
    st.title("🎙️ AI Live Sync")
    is_reporter = st.toggle("🔑 보고자 권한 (편집기능 활성화)", value=False)
    my_label = "📢 보고자" if is_reporter else f"👤 {st.session_state.user_label}"
    
    # [핵심 추가] 마이크 연결/해제 토글 (단순 웹 접속과 보이스 연결을 분리)
    voice_connect = st.toggle("🔊 마이크 연결 (시스템 접속)", value=False, key="voice_conn_toggle")
    
    if voice_connect:
        try:
            agora_id = st.secrets["AGORA_APP_ID"]
            agora_voice_system(agora_id, shared_store["voice_channel"], my_label)
        except: 
            st.warning("⚠️ Agora ID 설정 필요")

    # 명단 출력 (마이크 연결된 사람만 초록불과 함께 표시)
    sync_member_list(st.session_state.uid)

    if is_reporter:
        st.divider()
        st.download_button(label="📘 보고서 표준 양식 다운로드", data=json.dumps(get_sample_json_guide(), indent=4, ensure_ascii=False), file_name="Report_Standard_Template.json", mime="application/json", use_container_width=True)
        st.caption("💡 **Tip:** 위 표준 양식을 다운받아 제미나이(AI)에게 첨부한 뒤 내용을 채워달라고 하세요.")
        st.write("---")
        uploaded_file = st.file_uploader("📂 JSON 로드 (작업본 불러오기)", type=['json'])
        if uploaded_file:
            if st.session_state.get("last_uploaded_id") != uploaded_file.file_id:
                shared_store["report_data"] = adapt_json_format(json.loads(uploaded_file.read().decode("utf-8")))
                st.session_state["last_uploaded_id"] = uploaded_file.file_id
                shared_store["current_page"] = 0
        if st.button("🚨 전체 데이터 초기화"):
            shared_store.update({"report_data": None, "current_page": 0, "chat_history": [], "active_sessions": {}})
            st.session_state.pop("last_uploaded_id", None); st.rerun()
        if shared_store["report_data"]:
            st.download_button(label="📥 최종 리포트 JSON 저장", data=json.dumps(shared_store["report_data"], indent=4, ensure_ascii=False), file_name="My_Final_Report.json", use_container_width=True)
        edit_mode = st.toggle("📝 디자인/저작 모드 활성화", value=False)
    else: edit_mode = False

# ==========================================
# 6. 메인 브리핑 엔진 (Main Content Area)
# ==========================================
@st.fragment(run_every="1s")
def main_content_area(edit_enabled):
    # [핵심] 하트비트 갱신 시 현재 마이크 연결 상태(voice_connect)를 서버에 기록
    shared_store["active_sessions"][st.session_state.uid] = {
        "label": my_label,
        "last_seen": time.time(),
        "connected": st.session_state.get("voice_conn_toggle", False)
    }

    # --- 6-1. 실시간 상호소통 채팅 ---
    with st.expander("💬 실시간 상호소통 채팅", expanded=False):
        c1, c2 = st.columns([4, 1])
        msg = c1.text_input("메시지", key="chat_in", label_visibility="collapsed")
        if c2.button("전송") and msg: shared_store["chat_history"].append(f"**{my_label}**: {msg}")
        chat_box = "".join([f"<div style='margin-bottom:6px;'>{m}</div>" for m in shared_store["chat_history"][-10:]])
        st.markdown(f"<div style='height:120px; overflow-y:auto; background:#f8f9fa; padding:12px; border-radius:10px; border:1px solid #dee2e6;'>{chat_box}</div>", unsafe_allow_html=True)

    # --- 6-2. 빈 데이터 처리 ---
    if shared_store["report_data"] is None:
        st.markdown("<div style='text-align:center; padding:150px; color:#64748b;'><h2>📂 리포트를 로드하거나 양식을 다운로드하세요.</h2></div>", unsafe_allow_html=True)
        if edit_enabled and st.button("📄 완전히 새로운 보고서 시작하기"):
            shared_store["report_data"] = {"pages": [create_empty_page()]}; st.rerun()
        return

    data = shared_store["report_data"]
    if shared_store["current_page"] >= len(data['pages']): shared_store["current_page"] = max(0, len(data['pages']) - 1)
    p = data['pages'][shared_store["current_page"]]
    
    # --- 6-3. 페이지 관리 (보고자 전용) ---
    if edit_enabled:
        st.write("---")
        pc1, pc2 = st.columns([1, 5])
        if pc1.button("➕ 페이지 추가"):
            data['pages'].insert(shared_store["current_page"] + 1, create_empty_page())
            shared_store["current_page"] += 1; st.rerun()
        if pc2.button("🗑️ 페이지 삭제") and len(data['pages']) > 1:
            data['pages'].pop(shared_store["current_page"])
            shared_store["current_page"] = max(0, shared_store["current_page"] - 1); st.rerun()

    if is_reporter:
        tabs = {i: f"P{i+1}. {pg.get('tab', '')}" for i, pg in enumerate(data['pages'])}
        shared_store["current_page"] = st.radio("📑 이동", list(tabs.keys()), index=shared_store["current_page"], format_func=lambda x: tabs[x], horizontal=True)
        if edit_enabled: p['tab'] = st.text_input("🔖 탭 이름 수정", p.get('tab', ''), key=f"t_ed_{shared_store['current_page']}")

    # --- 6-4. 대제목 설정 ---
    if edit_enabled:
        with st.expander("📌 페이지 대제목 디자인 설정"):
            p['header'] = st.text_input("제목 내용", p.get('header', ''), key="h_ed")
            hc1, hc2 = st.columns(2)
            p['header_fs'] = hc1.slider("제목 크기", 10, 150, int(p.get('header_fs', 45)))
            p['header_color'] = hc2.color_picker("제목 색상", p.get('header_color', '#1a1c1e'))

    st.markdown(f'<h1 style="text-align:center; font-size:{p.get("header_fs", 45)}px; color:{p.get("header_color", "#1a1c1e")}; padding-bottom:20px;">{p.get("header")}</h1>', unsafe_allow_html=True)

    # --- 6-5. 섹션 (블록) 루프 및 편집 ---
    sections = p.setdefault('sections', [])
    if edit_enabled and st.button("➕ 새로운 세로 섹션 뭉치 추가", key=f"add_sec_{shared_store['current_page']}"):
        sections.append({"title": "새 섹션", "title_fs": 32, "title_color": "#1a1c1e", "col_ratio": 2.0, "lines": [{"text": "내용", "size": 22, "color": "#1e293b"}], "main_image": None, "full_width": True, "side_items": []})
        st.rerun()

    for s_idx, sec in enumerate(sections):
        with st.container(border=True): 
            if edit_enabled:
                sc1, sc2, sc3, sc4, sc5 = st.columns([2.5, 0.8, 0.8, 1.2, 0.5])
                sec['title'] = sc1.text_input("섹션 제목", sec.get('title', ''), key=f"st_{s_idx}")
                sec['title_fs'] = sc2.number_input("크기", 10, 80, int(sec.get('title_fs', 32)), key=f"stfs_{s_idx}")
                sec['title_color'] = sc3.color_picker("색상", sec.get('title_color', '#1a1c1e'), key=f"stc_{s_idx}")
                sec['col_ratio'] = sc4.slider("좌우비율", 1.0, 4.0, float(sec.get('col_ratio', 2.0)), 0.1, key=f"scr_{s_idx}")
                if sc5.button("🗑️", key=f"sdel_{s_idx}"): sections.pop(s_idx); st.rerun()
            
            st.markdown(f"<h2 style='font-size:{sec.get('title_fs', 32)}px; color:{sec.get('title_color', '#1a1c1e')}; margin-top: 5px; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 2px solid #f8f9fa;'>{sec.get('title')}</h2>", unsafe_allow_html=True)

            col_main, col_side = st.columns([sec.get('col_ratio', 2.0), 1], gap="medium")
            
            # --- [좌측 영역] 본문 그림 및 줄 단위 편집 ---
            with col_main:
                if edit_enabled:
                    with st.expander("🖼️ 본문(좌측) 그림 및 스케일 관리"):
                        img_f = st.file_uploader(f"그림 업로드", type=['png', 'jpg'], key=f"simg_{s_idx}")
                        if img_f: sec['main_image'] = f"data:image/png;base64,{base64.b64encode(img_f.getvalue()).decode()}"
                        sec['full_width'] = st.toggle("칼럼 너비 꽉 채우기", value=sec.get('full_width', True), key=f"fw_{s_idx}")
                        if not sec['full_width']: sec['img_width'] = st.slider("수동 너비 조절", 100, 1200, int(sec.get('img_width', 750)), key=f"sw_{s_idx}")
                        if st.button("🗑️ 그림 삭제", key=f"simg_del_{s_idx}"): sec['main_image'] = None; st.rerun()
                
                if sec.get('main_image'): 
                    style = "width:100%;" if sec.get('full_width', True) else f"width:{sec.get('img_width', 750)}px; max-width:100%;"
                    st.markdown(f'<div style="text-align:center;"><img src="{sec["main_image"]}" style="{style} border-radius:12px; margin-bottom:20px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);" /></div>', unsafe_allow_html=True)
                
                sec.setdefault('lines', [])
                if edit_enabled:
                    st.caption("📝 본문 문구 스타일 편집 (줄 단위)")
                    new_lines = []
                    for l_idx, line in enumerate(sec['lines']):
                        lc1, lc2, lc3, lc4 = st.columns([5, 1.5, 1.5, 0.5])
                        l_t = lc1.text_input(f"T", line['text'], key=f"lt_{s_idx}_{l_idx}", label_visibility="collapsed")
                        l_s = lc2.number_input("S", 10, 100, int(line['size']), key=f"ls_{s_idx}_{l_idx}")
                        l_c = lc3.color_picker("C", line['color'], key=f"lc_{s_idx}_{l_idx}")
                        if not lc4.button("🗑️", key=f"ld_{s_idx}_{l_idx}"): new_lines.append({"text": l_t, "size": l_s, "color": l_c})
                    sec['lines'] = new_lines
                    if st.button("➕ 문구 줄 추가", key=f"la_{s_idx}"): sec['lines'].append({"text": "새로운 문구", "size": 22, "color": "#1e293b"}); st.rerun()
                else:
                    for line in sec.get('lines', []):
                        st.markdown(f'<p class="text-line" style="font-size:{line["size"]}px; color:{line["color"]}; font-weight:bold;">{line["text"]}</p>', unsafe_allow_html=True)

            # --- [우측 영역] 사이드 지표 및 편집 ---
            with col_side:
                sec.setdefault('side_items', [])
                if edit_enabled:
                    sc1, sc2 = st.columns(2)
                    if sc1.button("📊 지표 추가", key=f"am_{s_idx}"): sec['side_items'].append({"type":"metric", "label":"항목", "value":"0", "color":"#007bff", "label_fs": 14, "label_color": "#64748b", "value_fs": 28}); st.rerun()
                    if sc2.button("🖼️ 그림 추가", key=f"ai_{s_idx}"): sec['side_items'].append({"type":"image", "src":None, "width":350}); st.rerun()
                
                for i_idx, item in enumerate(sec['side_items']):
                    if edit_enabled:
                        with st.expander(f"⚙️ {item.get('label', '아이템')} 편집", expanded=True):
                            if item['type'] == "metric":
                                item['label'] = st.text_input("라벨", item.get('label'), key=f"il_{s_idx}_{i_idx}")
                                item['value'] = st.text_area("내용(엔터지원)", item.get('value'), height=120, key=f"iv_{s_idx}_{i_idx}")
                                ic3, ic4 = st.columns(2); item['label_fs'] = ic3.number_input("라벨크기", 10, 60, int(item.get('label_fs', 14)), key=f"ilfs_{s_idx}_{i_idx}"); item['label_color'] = ic4.color_picker("라벨색상", item.get('label_color', '#64748b'), key=f"ilc_{s_idx}_{i_idx}")
                                ic5, ic6 = st.columns(2); item['value_fs'] = ic5.number_input("내용크기", 10, 100, int(item.get('value_fs', 28)), key=f"ivfs_{s_idx}_{i_idx}"); item['color'] = ic6.color_picker("내용색상", item.get('color', '#007bff'), key=f"ic_{s_idx}_{i_idx}")
                            elif item['type'] == "image":
                                siu = st.file_uploader("그림 업로드", key=f"siu_{s_idx}_{i_idx}")
                                if siu: item['src'] = f"data:image/png;base64,{base64.b64encode(siu.getvalue()).decode()}"
                                item['width'] = st.slider("너비", 100, 500, int(item.get('width', 350)), key=f"siw_{s_idx}_{i_idx}")
                            if st.button("🗑️ 삭제", key=f"sdel_{s_idx}_{i_idx}"): sec['side_items'].pop(i_idx); st.rerun()
                    
                    if item['type'] == "metric":
                        fv = item.get('value', '').replace('\n', '<br>')
                        st.markdown(f'<div class="side-slot-card"><div style="font-size:{item.get("label_fs", 14)}px; color:{item.get("label_color", "#64748b")}; margin-bottom:8px;">{item.get("label", "")}</div><div style="font-size:{item.get("value_fs", 28)}px; font-weight:bold; color:{item.get("color", "#007bff")}; line-height:1.5;">{fv}</div></div>', unsafe_allow_html=True)
                    elif item['type'] == "image" and item.get('src'):
                        st.markdown(f'<div class="side-slot-card"><img src="{item["src"]}" style="width:{item.get("width", 350)}px; max-width:100%; border-radius:12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);" /></div>', unsafe_allow_html=True)

# 최종 실행
main_content_area(edit_mode)
