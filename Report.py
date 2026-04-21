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
        width: 45%; 
        margin: 0 2%; 
    }
    .btn-mute { 
        padding: 8px 16px; 
        background: #6c757d; 
        color: white; 
        border: none; 
        border-radius: 8px; 
        cursor: pointer; 
        font-weight: bold; 
        width: 45%; 
        margin: 0 2%; 
        display: none; 
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
        "active_sessions": {}, # {uid: {"label": label, "last_seen": timestamp}} 명단 버그 해결용
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
# 4. ID 식별 및 음성 시스템
# ==========================================
if "uid" not in st.session_state:
    st.session_state.uid = st.query_params.get("uid", f"u_{int(time.time()*1000)}")
    st.query_params["uid"] = st.session_state.uid

if "user_label" not in st.session_state:
    # 현재 활성 세션(10초 이내)을 기준으로 참여자 번호 부여
    active_now = len([s for s in shared_store["active_sessions"].values() if time.time() - s["last_seen"] < 10])
    label = f"참여자 {active_now + 1}"
    st.session_state.user_label = label

def agora_voice_system(app_id, channel, user_label):
    custom_html = f"""
    <script src="https://download.agora.io/sdk/release/AgoraRTC_N-4.11.0.js"></script>
    <div class="voice-panel">
        <div id="v-status" style="font-size: 13px; font-weight: 700; margin-bottom: 8px; color:#1e293b;">🎙️ Live Sync Audio</div>
        <div style="width: 100%; height: 10px; background: #e2e8f0; border-radius: 5px; margin-bottom: 12px; overflow: hidden;">
            <div id="level-bar" style="width: 0%; height: 100%; background: #28a745; transition: width 0.05s;"></div>
        </div>
        <div>
            <button id="join" class="btn-join">🔊 접속하기</button>
            <button id="mute" class="btn-mute">🎤 마이크 켬</button>
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
                const muteBtn = document.getElementById("mute");
                muteBtn.style.display = "inline-block";
                
                client.on("volume-indicator", (vs) => {{ 
                    vs.forEach((v) => {{ 
                        if(v.uid === 0 && !isMuted) document.getElementById("level-bar").style.width = Math.min(v.level * 2, 100) + "%"; 
                        if(isMuted) document.getElementById("level-bar").style.width = "0%";
                    }}); 
                }});
                
                client.on("user-published", async (u, m) => {{ 
                    await client.subscribe(u, m); 
                    if(m === "audio") u.audioTrack.play(); 
                }});
                
            }} catch (e) {{ console.error(e); }}
        }}
        
        function toggleMute() {{
            if (!localTracks.audioTrack) return;
            isMuted = !isMuted;
            localTracks.audioTrack.setEnabled(!isMuted);
            
            const btn = document.getElementById("mute");
            if (isMuted) {{
                btn.innerText = "🔇 마이크 끔";
                btn.classList.add("active");
            }} else {{
                btn.innerText = "🎤 마이크 켬";
                btn.classList.remove("active");
            }}
        }}

        document.getElementById("join").onclick = join;
        document.getElementById("mute").onclick = toggleMute;
    </script>
    """
    components.html(custom_html, height=150)

# ==========================================
# 5. 사이드바 (Sidebar) 통제 센터
# ==========================================
with st.sidebar:
    st.title("🎙️ AI Live Sync")
    is_reporter = st.toggle("🔑 보고자 권한 (편집기능 활성화)", value=False)
    my_label = "📢 보고자" if is_reporter else f"👤 {st.session_state.user_label}"
    
    try:
        agora_id = st.secrets["AGORA_APP_ID"]
        agora_voice_system(agora_id, shared_store["voice_channel"], my_label)
    except: 
        st.warning("⚠️ Agora ID가 설정되지 않았습니다.")

    # [수정됨] 실시간 동시 접속자만 표시 (누적 방지)
    with st.container(border=True):
        st.caption("👥 실시간 접속 멤버")
        now = time.time()
        # 6초 이내에 하트비트 신호가 있는 세션만 필터링
        active_list = [
            info["label"] for uid, info in shared_store["active_sessions"].items()
            if now - info["last_seen"] < 6
        ]
        
        if not active_list:
            st.write("접속자 없음")
        else:
            for user in sorted(list(set(active_list))): # 중복 제거 및 정렬
                st.markdown(f"🟢 **{user}**")

    if is_reporter:
        st.divider()
        
        st.download_button(
            label="📘 보고서 표준 양식 다운로드",
            data=json.dumps(get_sample_json_guide(), indent=4, ensure_ascii=False),
            file_name="Report_Standard_Template.json",
            mime="application/json",
            use_container_width=True
        )
        st.caption("💡 **Tip:** 위 표준 양식을 다운받아 제미나이(AI)에게 첨부한 뒤, *'이 JSON 양식에 맞춰서 OO에 대한 보고서를 작성해 줘'* 라고 요청해 보세요.")
        
        st.write("---")
        uploaded_file = st.file_uploader("📂 JSON 로드 (작업본 불러오기)", type=['json'])
        if uploaded_file:
            if st.session_state.get("last_uploaded_id") != uploaded_file.file_id:
                shared_store["report_data"] = adapt_json_format(json.loads(uploaded_file.read().decode("utf-8")))
                st.session_state["last_uploaded_id"] = uploaded_file.file_id
                shared_store["current_page"] = 0
                
        if st.button("🚨 전체 데이터 초기화"):
            shared_store.update({"report_data": None, "current_page": 0, "chat_history": [], "active_sessions": {}})
            st.session_state.pop("last_uploaded_id", None)
            st.rerun()
            
        if shared_store["report_data"]:
            st.download_button(
                label="📥 최종 리포트 JSON 저장", 
                data=json.dumps(shared_store["report_data"], indent=4, ensure_ascii=False), 
                file_name="My_Final_Report.json", 
                use_container_width=True
            )
            
        edit_mode = st.toggle("📝 디자인/저작 모드 활성화", value=False)
    else: 
        edit_mode = False

# ==========================================
# 6. 메인 브리핑 엔진 (Main Content Area)
# ==========================================
@st.fragment(run_every="1s")
def main_content_area(edit_enabled):
    # [수정됨] 하트비트 갱신: 1초마다 내 활동 정보를 서버 저장소에 업데이트
    shared_store["active_sessions"][st.session_state.uid] = {
        "label": my_label,
        "last_seen": time.time()
    }

    # --- 6-1. 실시간 상호소통 채팅 ---
    with st.expander("💬 실시간 상호소통 채팅", expanded=False):
        c1, c2 = st.columns([4, 1])
        msg = c1.text_input("메시지", key="chat_in", label_visibility="collapsed")
        if c2.button("전송") and msg: 
            shared_store["chat_history"].append(f"**{my_label}**: {msg}")
        chat_box = "".join([f"<div style='margin-bottom:6px;'>{m}</div>" for m in shared_store["chat_history"][-10:]])
        st.markdown(f"<div style='height:120px; overflow-y:auto; background:#f8f9fa; padding:12px; border-radius:10px; border:1px solid #dee2e6;'>{chat_box}</div>", unsafe_allow_html=True)

    # --- 6-2. 빈 데이터 처리 ---
    if shared_store["report_data"] is None:
        st.markdown("<div style='text-align:center; padding:150px; color:#64748b;'><h2>📂 리포트를 로드하거나 양식을 다운로드하세요.</h2></div>", unsafe_allow_html=True)
        if edit_enabled and st.button("📄 완전히 새로운 보고서 시작하기"):
            shared_store["report_data"] = {"pages": [create_empty_page()]}
            st.rerun()
        return

    data = shared_store["report_data"]
    
    # --- 6-3. 인덱스 에러 방지 ---
    if shared_store["current_page"] >= len(data['pages']):
        shared_store["current_page"] = max(0, len(data['pages']) - 1)

    p = data['pages'][shared_store["current_page"]]
    
    # --- 6-4. 페이지 관리 및 탭 내비게이션 ---
    if edit_enabled:
        st.write("---")
        pc1, pc2 = st.columns([1, 5])
        if pc1.button("➕ 페이지 추가"):
            data['pages'].insert(shared_store["current_page"] + 1, create_empty_page())
            shared_store["current_page"] += 1
            st.rerun()
        if pc2.button("🗑️ 페이지 삭제") and len(data['pages']) > 1:
            data['pages'].pop(shared_store["current_page"])
            shared_store["current_page"] = max(0, shared_store["current_page"] - 1)
            st.rerun()

    if is_reporter:
        tabs = {i: f"P{i+1}. {pg.get('tab', '')}" for i, pg in enumerate(data['pages'])}
        shared_store["current_page"] = st.radio("📑 이동", list(tabs.keys()), index=shared_store["current_page"], format_func=lambda x: tabs[x], horizontal=True)
        if edit_enabled: 
            p['tab'] = st.text_input("🔖 탭 이름 수정", p.get('tab', ''), key=f"t_ed_{shared_store['current_page']}")

    # --- 6-5. 대제목 설정 및 렌더링 ---
    if edit_enabled:
        with st.expander("📌 페이지 대제목 디자인 설정"):
            p['header'] = st.text_input("제목 내용", p.get('header', ''), key="h_ed")
            hc1, hc2 = st.columns(2)
            p['header_fs'] = hc1.slider("제목 크기", 10, 150, int(p.get('header_fs', 45)))
            p['header_color'] = hc2.color_picker("제목 색상", p.get('header_color', '#1a1c1e'))

    st.markdown(f'<h1 style="text-align:center; font-size:{p.get("header_fs", 45)}px; color:{p.get("header_color", "#1a1c1e")}; padding-bottom:20px;">{p.get("header")}</h1>', unsafe_allow_html=True)

    # --- 6-6. 섹션 (블록) 루프 ---
    sections = p.setdefault('sections', [])
    if edit_enabled and st.button("➕ 새로운 세로 섹션 뭉치 추가", key=f"add_sec_{shared_store['current_page']}"):
        sections.append({
            "title": "새 섹션", "title_fs": 32, "title_color": "#1a1c1e", "col_ratio": 2.0, 
            "lines": [{"text": "내용", "size": 22, "color": "#1e293b"}], 
            "main_image": None, "full_width": True, "side_items": []
        })
        st.rerun()

    for s_idx, sec in enumerate(sections):
        with st.container(border=True): 
            
            # --- 섹션 제목 및 비율 설정 ---
            if edit_enabled:
                sc1, sc2, sc3, sc4 = st.columns([2.5, 1, 1, 1.5])
                sec['title'] = sc1.text_input("섹션 제목", sec.get('title', ''), key=f"st_{shared_store['current_page']}_{s_idx}", label_visibility="collapsed")
                sec['title_fs'] = sc2.number_input("제목 크기", 10, 80, int(sec.get('title_fs', 32)), key=f"stfs_{shared_store['current_page']}_{s_idx}")
                sec['title_color'] = sc3.color_picker("제목 색상", sec.get('title_color', '#1a1c1e'), key=f"stc_{shared_store['current_page']}_{s_idx}")
                sec['col_ratio'] = sc4.slider("좌/우 비율 조절", 1.0, 4.0, float(sec.get('col_ratio', 2.0)), 0.1, key=f"scr_{shared_store['current_page']}_{s_idx}")
            
            st.markdown(f"<h2 style='font-size:{sec.get('title_fs', 32)}px; color:{sec.get('title_color', '#1a1c1e')}; margin-top: 5px; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 2px solid #f8f9fa;'>{sec.get('title')}</h2>", unsafe_allow_html=True)

            current_ratio = sec.get('col_ratio', 2.0)
            col_main, col_side = st.columns([current_ratio, 1], gap="medium")
            
            # --- [좌측 영역] 본문 그림 및 문구 ---
            with col_main:
                if edit_enabled:
                    with st.expander("🖼️ 본문(좌측) 그림 및 스케일 관리"):
                        img_f = st.file_uploader(f"그림 업로드", type=['png', 'jpg'], key=f"simg_{shared_store['current_page']}_{s_idx}")
                        if img_f: 
                            sec['main_image'] = f"data:image/png;base64,{base64.b64encode(img_f.getvalue()).decode()}"
                        
                        sec['full_width'] = st.toggle("칼럼 너비 꽉 채우기 (권장)", value=sec.get('full_width', True), key=f"fw_{shared_store['current_page']}_{s_idx}")
                        if not sec['full_width']:
                            sec['img_width'] = st.slider("수동 너비 조절", 100, 1200, int(sec.get('img_width', 750)), key=f"sw_{shared_store['current_page']}_{s_idx}")
                            
                        if st.button("🗑️ 그림 삭제", key=f"simg_del_{shared_store['current_page']}_{s_idx}"): 
                            sec['main_image'] = None
                            st.rerun()
                
                if sec.get('main_image'): 
                    if sec.get('full_width', True):
                        st.markdown(f'<img src="{sec["main_image"]}" style="width:100%; border-radius:12px; margin-bottom:20px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);" />', unsafe_allow_html=True)
                    else:
                        w = sec.get('img_width', 750)
                        st.markdown(f'<div style="text-align:center; margin-bottom:20px;"><img src="{sec["main_image"]}" style="width:{w}px; max-width:100%; border-radius:12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);" /></div>', unsafe_allow_html=True)
                
                sec.setdefault('lines', [])
                if edit_enabled:
                    st.caption("📝 본문 문구 스타일 편집 (줄 단위)")
                    new_lines = []
                    for l_idx, line in enumerate(sec['lines']):
                        lc1, lc2, lc3, lc4 = st.columns([5, 1.5, 1.5, 0.5])
                        l_t = lc1.text_input(f"T_{l_idx}", line['text'], key=f"lt_{shared_store['current_page']}_{s_idx}_{l_idx}", label_visibility="collapsed")
                        l_s = lc2.number_input("S", 10, 100, int(line['size']), key=f"ls_{shared_store['current_page']}_{s_idx}_{l_idx}")
                        l_c = lc3.color_picker("C", line['color'], key=f"lc_{shared_store['current_page']}_{s_idx}_{l_idx}")
                        if not lc4.button("🗑️", key=f"ld_{shared_store['current_page']}_{s_idx}_{l_idx}"):
                            new_lines.append({"text": l_t, "size": l_s, "color": l_c})
                    sec['lines'] = new_lines
                    if st.button("➕ 문구 줄 추가", key=f"la_{shared_store['current_page']}_{s_idx}"):
                        sec['lines'].append({"text": "새로운 문구", "size": 22, "color": "#1e293b"})
                        st.rerun()
                else:
                    for line in sec.get('lines', []):
                        st.markdown(f'<p class="text-line" style="font-size:{line["size"]}px; color:{line["color"]}; font-weight:bold;">{line["text"]}</p>', unsafe_allow_html=True)

            # --- [우측 영역] 사이드 지표 및 보조 그림 ---
            with col_side:
                sec.setdefault('side_items', [])
                if edit_enabled:
                    sc1, sc2 = st.columns(2)
                    if sc1.button("📊 지표/글자 추가", key=f"am_{shared_store['current_page']}_{s_idx}"): 
                        sec['side_items'].append({"type":"metric", "label":"항목", "value":"0", "color":"#007bff", "label_fs": 14, "label_color": "#64748b", "value_fs": 28})
                        st.rerun()
                    if sc2.button("🖼️ 그림 추가", key=f"ai_{shared_store['current_page']}_{s_idx}"): 
                        sec['side_items'].append({"type":"image", "src":None, "width":350})
                        st.rerun()
                
                for i_idx, item in enumerate(sec['side_items']):
                    if edit_enabled:
                        with st.expander(f"⚙️ {item.get('label', '아이템')} 편집", expanded=True):
                            if st.button("🗑️ 이 아이템 삭제", key=f"sdel_{shared_store['current_page']}_{s_idx}_{i_idx}"): 
                                sec['side_items'].pop(i_idx)
                                st.rerun()
                            
                            if item['type'] == "metric":
                                ic1, ic2 = st.columns(2)
                                item['label'] = ic1.text_input("라벨명", item.get('label', ''), key=f"il_{shared_store['current_page']}_{s_idx}_{i_idx}")
                                item['value'] = st.text_area("수치/내용", item.get('value', ''), height=120, key=f"iv_{shared_store['current_page']}_{s_idx}_{i_idx}")
                                
                                ic3, ic4 = st.columns(2)
                                item['label_fs'] = ic3.number_input("라벨 크기", 10, 60, int(item.get('label_fs', 14)), key=f"ilfs_{shared_store['current_page']}_{s_idx}_{i_idx}")
                                item['label_color'] = ic4.color_picker("라벨 색상", item.get('label_color', '#64748b'), key=f"ilc_{shared_store['current_page']}_{s_idx}_{i_idx}")
                                
                                ic5, ic6 = st.columns(2)
                                item['value_fs'] = ic5.number_input("내용 크기", 10, 100, int(item.get('value_fs', 28)), key=f"ivfs_{shared_store['current_page']}_{s_idx}_{i_idx}")
                                item['color'] = ic6.color_picker("내용 색상", item.get('color', '#007bff'), key=f"ic_{shared_store['current_page']}_{s_idx}_{i_idx}")
                            
                            elif item['type'] == "image":
                                siu = st.file_uploader("사이드 그림 업로드", key=f"siu_{shared_store['current_page']}_{s_idx}_{i_idx}")
                                if siu: 
                                    item['src'] = f"data:image/png;base64,{base64.b64encode(siu.getvalue()).decode()}"
                                item['width'] = st.slider("사이드 그림 너비", 100, 500, int(item.get('width', 350)), key=f"siw_{shared_store['current_page']}_{s_idx}_{i_idx}")
                    
                    if item['type'] == "metric":
                        fv = item.get('value', '').replace('\n', '<br>')
                        st.markdown(f'<div class="side-slot-card"><div style="font-size:{item.get("label_fs", 14)}px; color:{item.get("label_color", "#64748b")}; margin-bottom:6px;">{item.get("label", "")}</div><div style="font-size:{item.get("value_fs", 28)}px; font-weight:bold; color:{item.get("color", "#007bff")}; line-height:1.5;">{fv}</div></div>', unsafe_allow_html=True)
                        
                    elif item['type'] == "image" and item.get('src'):
                        st.markdown(f'<div class="side-slot-card"><img src="{item["src"]}" style="width:{item.get("width", 350)}px; max-width:100%; border-radius:12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);" /></div>', unsafe_allow_html=True)

# 실행부
main_content_area(edit_mode)
