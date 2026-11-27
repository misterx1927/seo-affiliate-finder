from datetime import date
from html import escape
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import re
from urllib.parse import urlsplit

import pandas as pd
import streamlit as st
from openpyxl import Workbook

from src.database import connect
from src.exporter import safe_cell, serp_provenance
from src.pipeline import run_offline
from src.contact_discovery import contact_pages
from src.snapshot import load_snapshot, snapshot_review

st.set_page_config(page_title="Affiliate Finder | Search intelligence", page_icon="✳", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
:root {color-scheme:dark;}
html, body, [class*="css"], [data-testid="stAppViewContainer"] {font-family:'DM Sans', sans-serif;}
[data-testid="stAppViewContainer"] {background: radial-gradient(ellipse at 72% -18%,#293e30 0%,transparent 42%), radial-gradient(ellipse at 5% 47%,#17221a 0%,transparent 34%), #0b100e;}
[data-testid="stHeader"] {background:transparent;}
[data-testid="stDeployButton"] {display:none;}
[data-testid="stSidebar"] {background:#0d1511; border-right:1px solid #26352b;}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {color:#b7c5b9;}
.block-container {padding:2.3rem 3.1rem 4rem; max-width:1500px;}
h1,h2,h3 {font-family:'Manrope',sans-serif !important; letter-spacing:-.045em;}
p {line-height:1.55;}
.topbar {display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #314236;padding-bottom:20px;margin-bottom:30px;gap:15px;}
.brand {display:flex;align-items:center;gap:11px;color:#eff6ec;font-family:'Manrope',sans-serif;font-weight:800;letter-spacing:-.04em;font-size:18px;}
.brand-mark {width:33px;height:33px;display:grid;place-items:center;border-radius:10px;background:#c9f777;color:#172316;font-size:20px;}
.brand-sub {color:#738478;font-size:10px;letter-spacing:.13em;text-transform:uppercase;font-weight:700;margin-left:12px;padding-left:16px;border-left:1px solid #36453b;}
.top-meta {display:flex;gap:8px;align-items:center;}
.pill {border:1px solid #33453a;border-radius:100px;padding:7px 11px;color:#acbcb0;font-size:11px;font-weight:600;white-space:nowrap;}
.dot {display:inline-block;width:6px;height:6px;border-radius:50%;background:#bdf273;margin-right:6px;vertical-align:middle;}
.eyebrow {color:#b8ee70;font-size:10px;letter-spacing:.18em;text-transform:uppercase;font-weight:700;margin:2px 0 13px;}
.hero-title {font:800 clamp(2.3rem,4vw,3.75rem)/1.06 'Manrope',sans-serif;letter-spacing:-.07em;color:#f3f7ef;margin:0 0 14px;}
.hero-title em {font-style:normal;color:#c5f47e;}
.hero-copy {color:#92a498;font-size:15px;max-width:550px;margin:0 0 19px;}
.context-row {display:flex;flex-wrap:wrap;gap:8px;margin:0 0 20px;}
.context-item {font-size:11px;color:#b2c0b3;background:#18221c;border:1px solid #2d3c32;border-radius:8px;padding:7px 10px;}
.demo-note {font-size:11px;line-height:1.5;color:#9aa99d;margin-top:8px;}
.hero-art {position:relative;overflow:hidden;border:1px solid #526b50;border-radius:20px;background:linear-gradient(135deg,#304d35,#15261b 68%);min-height:188px;padding:22px 26px;box-shadow:0 20px 60px #0003;}
.hero-art:after {content:'';position:absolute;width:245px;height:245px;border:1px solid #a0d57c33;border-radius:50%;right:-45px;top:-21px;box-shadow:0 0 0 28px #a0d57c0b,0 0 0 57px #a0d57c0a,0 0 0 87px #a0d57c08;}
.art-kicker {font-size:10px;text-transform:uppercase;letter-spacing:.15em;color:#a6bbaa;font-weight:700;position:relative;z-index:1;}
.art-value {font:800 58px/1 'Manrope',sans-serif;letter-spacing:-.07em;color:#e8f7d6;margin:20px 0 6px;position:relative;z-index:1;}
.art-label {font-size:12px;color:#aabfa9;position:relative;z-index:1;}
.art-footer {margin-top:23px;color:#d4e9c9;font-size:11px;position:relative;z-index:1;}
.section-top {display:flex;justify-content:space-between;align-items:end;margin:36px 0 15px;gap:12px;}
.section-label {font:700 18px 'Manrope',sans-serif;color:#edf4ea;letter-spacing:-.035em;}
.results-summary {display:flex;flex-wrap:wrap;align-items:center;gap:10px 20px;padding:14px 16px;margin:6px 0 2px;border:1px solid #304436;border-radius:12px;background:#131e17;}
.results-count {color:#e8f2e8;font-size:13px;font-weight:700;}
.results-legend {display:flex;flex-wrap:wrap;gap:7px 14px;color:#afbeb2;font-size:12px;}
.results-legend span {white-space:nowrap;}
.section-sub {color:#7f9183;font-size:12px;margin-top:5px;}
.section-side {font-size:10px;text-transform:uppercase;letter-spacing:.14em;color:#819286;white-space:nowrap;}
[data-testid="stMetric"] {background:linear-gradient(155deg,#1e2d22,#121b15);border:1px solid #304535;border-radius:16px;padding:20px 20px 18px;min-height:116px;box-shadow:0 8px 24px #0002;}
[data-testid="stMetricLabel"] p {color:#9baea0;font-size:11px;font-weight:700;letter-spacing:.08em;}
[data-testid="stMetricValue"] {font-family:'Manrope',sans-serif;color:#f2f7ec;font-size:32px;font-weight:700;}
[data-testid="stMetricValue"] div {font-size:32px;}
.stButton > button[kind="primary"] {background:#c7f477;color:#172313;border:0;border-radius:10px;min-height:48px;font-weight:800;box-shadow:0 8px 28px #b6e96e18;}
.stButton > button[kind="primary"]:hover {background:#d7ff99;color:#142010;border:0;}
[data-testid="stTextInput"] input, [data-baseweb="select"] > div {background:#151f19 !important;border-color:#304036 !important;border-radius:9px !important;color:#eaf2e8 !important;}
[data-testid="stDataFrame"] {border:1px solid #2b3a30;border-radius:12px;overflow:hidden;}
[data-testid="stDownloadButton"] button {background:#17231b;border:1px solid #34483a;border-radius:9px;color:#dbe8d9;font-weight:600;}
[data-testid="stAlert"] {border:1px solid #354a39;border-radius:12px;background:#18261c;}
.signal-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:14px 0 8px;}
.signal-card {background:linear-gradient(150deg,#19271d,#111b14);border:1px solid #304436;border-radius:14px;padding:18px 19px;min-height:118px;}
.signal-kicker {color:#a4b6a6;font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;}
.signal-value {font:800 28px/1 'Manrope',sans-serif;color:#ecf5e8;letter-spacing:-.05em;margin:12px 0 7px;}
.signal-note {color:#90a395;font-size:11px;line-height:1.4;}
.signal-card.ready .signal-value {color:#c8f47e;}
.signal-card.review .signal-value {color:#f0d38f;}
.quality-note {border:1px solid #40533c;border-left:3px solid #c5ed81;border-radius:12px;background:#19271c;padding:14px 17px;margin:18px 0 8px;color:#c7d7c7;font-size:12px;line-height:1.55;}
.quality-note strong {color:#eef7e8;}
[data-testid="stExpander"] {border:1px solid #304436;border-radius:14px;background:#111a14;}
[data-testid="stExpander"] summary {padding:1rem 1.1rem;}
[data-testid="stRadio"] [role="radiogroup"] {gap:0.5rem 1.25rem;}
[data-testid="stDataFrame"] {box-shadow:0 12px 35px #0003;}
.detail-heading {font:700 20px 'Manrope',sans-serif;color:#f2f8ef;letter-spacing:-.035em;margin:2px 0 5px;word-break:break-word;}
.detail-sub {color:#91a595;font-size:12px;line-height:1.5;margin-bottom:14px;}
.footer {border-top:1px solid #25332a;margin-top:38px;padding-top:17px;display:flex;justify-content:space-between;gap:12px;color:#6e8073;font-size:11px;}
@media (max-width: 760px) {.block-container {padding:1.1rem 1rem 3rem;} .brand-sub,.top-meta .pill:first-child {display:none;} .topbar {margin-bottom:22px;} .section-side {display:none;} .hero-title {font-size:2.05rem;line-height:1.12;} .hero-copy {font-size:13px;margin-bottom:8px;} .section-top {margin:22px 0 12px;} .footer {display:block;} [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;} [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) [data-testid="stColumn"] {width:auto !important;min-width:0 !important;} [data-testid="stMetric"] {min-height:88px;padding:14px;} [data-testid="stMetricValue"], [data-testid="stMetricValue"] div {font-size:26px;} }
</style>""", unsafe_allow_html=True)

def live_results_exist():
    if not Path("data/live.db").is_file():
        return False
    try:
        with sqlite3.connect("data/live.db") as db:
            return bool(db.execute("SELECT 1 FROM observations LIMIT 1").fetchone())
    except sqlite3.Error:
        return False


def show_contact(value):
    if not value:
        st.write("Нет данных")
    elif re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", str(value)):
        address = escape(str(value), quote=True)
        st.markdown(f'<a href="mailto:{address}">{address}</a>', unsafe_allow_html=True)
    elif str(value).startswith(("https://", "http://")):
        st.link_button("Открыть контакт ↗", str(value))
    else:
        st.write(str(value))


def is_video_result(url):
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    return host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")


def excluded_from_prospects(url):
    host = (urlsplit(str(url)).hostname or "").lower().rstrip(".")
    return host == "trustpilot.com" or host.endswith(".trustpilot.com") or is_video_result(str(url))


def assessment_color(value):
    colors = {
        "Возможно подходит": "color: #b8f27a; background-color: #243d27; font-weight: 600",
        "Нужна проверка": "color: #f3d778; background-color: #44391c; font-weight: 600",
        "Не подходит": "color: #ffb088; background-color: #4a2c1f; font-weight: 600",
        "Нет анализа": "color: #bec7c0; background-color: #303933; font-weight: 600",
    }
    return colors.get(value, "")


def friendly_error(error):
    error = str(error or "").lower()
    if "403" in error or "access challenge" in error:
        return "Сайт ограничил автоматический доступ. Откройте страницу вручную для проверки."
    if "451" in error or "regional" in error:
        return "Содержимое недоступно для выбранного региона. Проверьте страницу вручную."
    if "connection" in error or "dns" in error or "timeout" in error:
        return "Не удалось подключиться к сайту. Попробуйте открыть страницу вручную."
    if "manual review" in error:
        return "Площадку необходимо проверить вручную."
    return "Не удалось надёжно определить данные страницы. Требуется проверка вручную."


@st.cache_data(max_entries=200, show_spinner=False)
def contact_page_from_cache(content, charset, url):
    links = contact_pages(content, charset, url)
    return next((link for link in links if 'contact' in urlsplit(link).path.lower() and not urlsplit(link).query), '')


with st.sidebar:
    st.markdown("### ✳ Affiliate Finder")
    st.caption("Поиск площадок для размещения казино-брендов")
    st.divider()
    st.markdown("**Источник данных**")
    source = st.radio("Источник данных", ["Демо", "Реальные результаты", "Сохранённый прогон"], index=1 if live_results_exist() else 2, label_visibility="collapsed")
    if source == "Демо":
        st.caption("Вымышленные данные, без запросов к API.")
    else:
        st.caption("Сохранённые данные. Новые запросы с этой страницы не запускаются.")
    st.divider()
    st.caption("Канада  /  английский  /  мобильная выдача")

is_demo = source == "Демо"
is_snapshot = source == "Сохранённый прогон"
mode_label = "ДЕМО" if is_demo else ("СОХРАНЁННЫЙ ПРОГОН" if is_snapshot else "РЕАЛЬНЫЕ ДАННЫЕ")
st.markdown(f'''<div class="topbar"><div class="brand"><span class="brand-mark">✳</span> affiliate finder <span class="brand-sub">поиск партнёров</span></div><div class="top-meta"><span class="pill">🇨🇦 &nbsp; Канада / EN / мобильная выдача</span><span class="pill"><span class="dot"></span>{mode_label}</span></div></div>''', unsafe_allow_html=True)

with connect("data/demo.db" if is_demo else "data/live.db") as conn:
    review_path = Path("results/independent-review-2026-11-26.json")
    supplemental = json.loads(review_path.read_text(encoding="utf-8")) if not is_demo and review_path.is_file() else {}
    domain_contact_path = Path("results/public-domain-contacts.json")
    domain_contacts = json.loads(domain_contact_path.read_text(encoding="utf-8")) if not is_demo and domain_contact_path.is_file() else {}
    contact_links = {}
    cached_rows = conn.execute("""SELECT c.url, c.content, c.charset FROM page_cache c
        JOIN pages p ON p.url=c.url WHERE p.status='complete' AND p.relevance='yes'""").fetchall()
    for cached in cached_rows:
        contact_link = contact_page_from_cache(cached['content'], cached['charset'], cached['url'])
        if contact_link:
            contact_links[cached['url']] = contact_link
    rows = conn.execute("""SELECT o.day AS Date, o.keyword AS Keyword, o.position AS Position, o.domain AS Domain,
        o.url AS URL, COALESCE(p.relevance, 'needs_review') AS Relevance, p.brands_json AS Brands,
        COALESCE(p.contact, '') AS Contact, COALESCE(p.status, 'pending') AS Status,
        p.evidence_json AS Evidence, COALESCE(p.error, '') AS Error, COALESCE(p.analysis_version, '') AS AnalysisVersion,
        d.from_web_ranks AS WebRanks, d.verification_requested AS VerificationRequested,
        ps.source AS PageSource,
        COALESCE((SELECT email FROM outreach_contact_candidates x WHERE x.page_url=o.url ORDER BY x.observed_at DESC,x.email,x.source_url LIMIT 1),'') AS ContactCandidate,
        COALESCE((SELECT source_url FROM outreach_contact_candidates x WHERE x.page_url=o.url ORDER BY x.observed_at DESC,x.email,x.source_url LIMIT 1),'') AS ContactCandidateSource
        FROM observations o LEFT JOIN pages p ON o.url=p.url
        LEFT JOIN serp_diagnostics d ON d.run_id=o.run_id AND d.keyword=o.keyword
        LEFT JOIN page_cache_provenance ps ON ps.url=o.url
        ORDER BY o.day DESC, o.keyword, o.position""").fetchall()
    if is_snapshot:
        rows = load_snapshot("results/run-7-ai-updated.csv")
    partial_rows = [] if is_demo or is_snapshot else conn.execute("""SELECT o.run_id AS Run, o.day AS Date, o.keyword AS Keyword,
        o.position AS Position, o.domain AS Domain, o.url AS URL,
        COALESCE(p.status, 'pending') AS Status, p.relevance AS Relevance,
        p.brands_json AS Brands, p.contact AS Contact, p.evidence_json AS Evidence,
        COALESCE(p.error, '') AS Note
        FROM partial_observations o LEFT JOIN pages p ON p.url=o.url
        ORDER BY o.run_id DESC, o.keyword, o.position""").fetchall()
    displayed = []
    for row in rows:
        item = dict(row)
        review = snapshot_review(supplemental, item['URL'], item['Date'], item['Status'])
        if review:
            item['Relevance'] = review['relevance']
            item['Brands'] = json.dumps(review.get('brands', []), ensure_ascii=False)
            item['Contact'] = ''
            item['Status'] = 'supplemental'
            item['Error'] = ''
        item['Review note'] = review.get('note', '') if review else item.pop('SnapshotReviewNote', '')
        item['SERP source'] = 'fictional_demo' if is_demo else (item.pop('SnapshotSerpSource') if is_snapshot else serp_provenance(item['Position'], item.pop('WebRanks'), item.pop('VerificationRequested')))
        item['Page source'] = 'fictional_demo' if is_demo else ('Индексированная версия (дополнительная проверка)' if review else (item.pop('PageSource') or 'direct_or_unknown'))
        item['Public contact candidate'] = (review.get('contact', '') if review else '') or item.pop('ContactCandidate', '')
        item['Contact candidate source'] = (review.get('contact_page', '') if review else '') or item.pop('ContactCandidateSource', '')
        item['Analysis version'] = item.pop('AnalysisVersion', '')
        item['Contact page'] = review.get('contact_page', '') if review and review.get('contact_page') else contact_links.get(item['URL'], '')
        domain_contact = domain_contacts.get((urlsplit(item['URL']).hostname or '').lower().removeprefix('www.'), {})
        if domain_contact and item['Relevance'] == 'yes':
            item['Public contact candidate'] = domain_contact['email'] or item['Public contact candidate']
            item['Contact candidate source'] = domain_contact['source']
            item['Contact page'] = domain_contact['contact_page']
        item.pop('WebRanks', None)
        item.pop('VerificationRequested', None)
        item.pop('PageSource', None)
        displayed.append(item)
    frame = pd.DataFrame(displayed, columns=["Date", "Keyword", "Position", "Domain", "URL", "Relevance", "Brands", "Contact", "Status", "Evidence", "Error", "SERP source", "Page source", "Public contact candidate", "Contact candidate source", "Analysis version", "Contact page", "Review note"])
    if not frame.empty:
        frame["Brands"] = frame["Brands"].apply(lambda value: ", ".join(json.loads(value)) if isinstance(value, str) and value else "")
        frame["Evidence"] = frame["Evidence"].apply(lambda value: json.loads(value) if isinstance(value, str) and value else "")
        latest = frame["Date"].max()
        current = frame[frame["Date"] == latest]
    else:
        latest = None
        current = frame
        if partial_rows:
            partial_frame = pd.DataFrame([dict(row) for row in partial_rows])
            current = partial_frame[partial_frame["Run"] == partial_frame["Run"].max()].copy()
            current["Relevance"] = current["Relevance"].fillna("needs_review")
            latest = current["Date"].max()

    st.markdown('''<div class="eyebrow">✳ &nbsp; GOOGLE · КАНАДА · МОБИЛЬНЫЕ УСТРОЙСТВА</div><div class="hero-title">Поиск <em>площадок</em></div><p class="hero-copy">Позиции, бренды и контакты для размещения казино-брендов.</p>''', unsafe_allow_html=True)
    if is_demo:
        st.info("Демо: ниже вымышленные примеры. Выберите «Реальные результаты» в боковом меню, чтобы увидеть сохранённый поиск.")
        if st.button("Обновить демо", type="primary"):
            result = run_offline(conn, date.today().isoformat())
            if result["status"] == "complete":
                st.toast(f"Демо обновлено: {result['observations']} позиций.")
                st.rerun()
            else:
                st.warning("Некоторые страницы демо требуют проверки.")

a, b, c, d = st.columns(4)
a.metric("ЗАПРОСЫ", str(current["Keyword"].nunique()))
b.metric("ПОЗИЦИИ", str(len(current)))
c.metric("СТРАНИЦЫ", str(current["URL"].nunique()))
prospects = current.loc[(current["Relevance"] == "yes") & (current["Status"].isin(["complete", "supplemental"])) & ~current["URL"].map(excluded_from_prospects).astype(bool)]
prospect_domains = prospects["Domain"].fillna("").astype(str).str.lower().str.removeprefix("www.")
d.metric("ВОЗМОЖНЫЕ ПЛОЩАДКИ", str(prospect_domains.nunique()), help="Предварительная оценка AI или дополнительная проверка. Пригодность площадки нужно подтвердить.")

if latest and not is_demo:
    st.caption(f"Результаты за {latest}")
if not is_demo and "SERP source" in current.columns:
    restored = int((current["SERP source"] == "restored_from_google_web").sum())
    if restored:
        st.caption(f"{restored} из {len(current)} позиций восстановлены через Google Web и могут отличаться от мобильной выдачи. Дополнительная проверка не является AI-анализом, контакты требуют подтверждения.")
    else:
        st.caption("Позиции и контакты требуют дополнительного подтверждения.")

st.markdown('''<div class="section-top"><div><div class="section-label">Результаты поиска</div></div></div>''', unsafe_allow_html=True)
show_history = False
explorer = frame if latest is None else frame[frame["Date"] == latest]
# Trustpilot is a review platform, not a placement prospect. Keep the original
# search result in the stored snapshot, but exclude it from the prospect list.
explorer = explorer.loc[~explorer["URL"].map(excluded_from_prospects).astype(bool)]
categories = ["Возможные площадки", "Нужна проверка", "Не подходят", "Нет анализа"]
selected_categories = st.multiselect("Показать", categories, default=["Возможные площадки"], key="prospect_categories_v3", placeholder="Все категории", help="Можно выбрать несколько категорий одновременно. Trustpilot исключён из списка площадок, исходная выдача сохранена в результатах прогона.")
processed = explorer["Status"].isin(["complete", "supplemental"])
category = pd.Series("Нет анализа", index=explorer.index)
category.loc[processed & (explorer["Relevance"] == "yes")] = "Возможные площадки"
category.loc[processed & (explorer["Relevance"] == "no")] = "Не подходят"
category.loc[processed & (explorer["Relevance"] == "needs_review")] = "Нужна проверка"
if selected_categories:
    explorer = explorer[category.isin(selected_categories)]
only_contacts = st.checkbox("Только с контактом или страницей контактов", value=False, help="Показывает адреса, найденные на странице, возможные публичные контакты и ссылки на контактные страницы. Перед обращением их нужно проверить.")
if only_contacts:
    explorer = explorer[(explorer["Contact"].fillna("") != "") | (explorer["Public contact candidate"].fillna("") != "") | (explorer["Contact page"].fillna("") != "")]
keywords = ["Все запросы"] + sorted(frame["Keyword"].unique().tolist())
selected_keyword = st.selectbox("Поисковый запрос", keywords, index=0, key="prospect_keyword_v2")
filtered = explorer
if selected_keyword != "Все запросы":
    filtered = filtered[filtered["Keyword"] == selected_keyword]
filtered = filtered.sort_values(["Date", "Position", "Keyword"], ascending=[False, True, True], kind="stable")
filtered = filtered.copy()
filtered["_site"] = filtered["Domain"].fillna("").astype(str).str.lower().str.removeprefix("www.")

relevance_labels = {"yes": "Возможно подходит", "no": "Не подходит", "needs_review": "Нужна проверка"}
column_labels = {"URL": "Ссылка на страницу", "Domain": "Домен", "Position": "Позиция", "Relevance": "Оценка", "Brands": "Бренды", "Contact": "Контакт на странице", "Contact page": "Страница контактов", "Public contact candidate": "Возможный контакт", "Contact candidate source": "Источник контакта", "Keyword": "Запрос", "Date": "Дата", "Status": "Способ оценки", "Evidence": "Подтверждение", "Error": "Причина проверки", "SERP source": "Источник позиции", "Page source": "Источник страницы", "Analysis version": "Версия анализа", "Review note": "Примечание к проверке"}
if filtered.empty:
    st.info("Нет результатов с выбранными фильтрами. Измените категории, запрос или снимите ограничение по контактам.")
else:
    presentation = filtered.drop_duplicates(subset=["Date", "_site"]).copy()
    st.markdown(f'''<div class="results-summary"><div class="results-count">Площадок: {len(presentation)}</div><div class="results-legend"><span>🟢 Возможно подходит</span><span>🟡 Проверить</span><span>🟠 Не подходит</span><span>⚪ Нет анализа</span></div></div>''', unsafe_allow_html=True)
    st.caption("Для каждой площадки показана страница с лучшей позицией среди выбранных результатов. Другие выбранные страницы и позиции доступны в подробностях.")
    presentation.insert(0, "№", range(1, len(presentation) + 1))
    # Count coverage across the full latest snapshot, before prospect filters.
    # This is not traffic, search volume, or the reason for a Google rank.
    domain_key = frame["Domain"].fillna("").astype(str).str.lower().str.removeprefix("www.")
    keyword_coverage = frame.assign(_site=domain_key).groupby(["Date", "_site"])["Keyword"].nunique()
    presentation["Запросов в топ-10"] = [int(keyword_coverage.get((day, site), 0)) for day, site in zip(presentation["Date"], presentation["_site"])]
    presentation["Relevance"] = presentation.apply(lambda row: "Нет анализа" if row["Status"] not in ("complete", "supplemental") else relevance_labels.get(row["Relevance"], "Нужна проверка"), axis=1)
    presentation["Brands"] = presentation.apply(lambda row: row["Brands"] or ("Не найдены при анализе" if row["Status"] in ("complete", "supplemental") else "Не удалось определить"), axis=1)
    presentation["Public contact candidate"] = presentation.apply(lambda row: row["Public contact candidate"] or row["Contact"] or ("См. страницу контактов" if row["Contact page"] else "Не найден"), axis=1)
    presentation["Status"] = presentation["Status"].map({"complete": "AI-анализ", "supplemental": "Дополнительная проверка, 26.11.2026", "pending": "Ожидает", "needs_review": "Нет анализа"}).fillna("Нет анализа")
    presentation = presentation.rename(columns=column_labels)
    columns = ["№", "Ссылка на страницу", "Позиция", "Запрос", "Запросов в топ-10", "Возможный контакт", "Страница контактов", "Оценка", "Бренды", "Дата"]
    styled = presentation[columns].style.map(assessment_color, subset=["Оценка"])
    st.caption("Запросов в топ-10 - по скольким запросам площадка попала в результаты за эту дату. Это не посещаемость сайта.")
    st.dataframe(styled, hide_index=True, width="stretch", height=420,
                 column_order=columns,
                 column_config={"№": st.column_config.NumberColumn("№", width=40), "Позиция": st.column_config.NumberColumn("Лучшая позиция", width="small"), "Ссылка на страницу": st.column_config.LinkColumn("Площадка", display_text=r"https?://([^/]+).*", width=135), "Оценка": st.column_config.TextColumn("Оценка страницы", width="medium"), "Бренды": st.column_config.TextColumn("Бренды", width="medium"), "Возможный контакт": st.column_config.TextColumn("Контакт", width=170), "Страница контактов": st.column_config.LinkColumn("Страница контактов", display_text="Открыть контакты ↗")})
    with st.expander("Подробнее о странице и источниках"):
        detail_options = filtered.drop_duplicates(subset=["Date", "_site"])
        selected_site = st.selectbox("Выберите площадку", detail_options["_site"].tolist(), key="site_detail")
        site_results = filtered[filtered["_site"] == selected_site]
        page_options = site_results["URL"].drop_duplicates().tolist()
        selected_url = st.selectbox("Страница площадки", page_options, key="page_detail") if len(page_options) > 1 else page_options[0]
        page_results = site_results[site_results["URL"] == selected_url]
        detail = page_results.iloc[0]
        url = escape(str(detail["URL"]), quote=True)
        domain = escape(str(detail["Domain"]))
        st.markdown(f'''<div class="detail-heading"><a href="{url}" target="_blank" rel="noopener noreferrer">{domain} ↗</a></div><div class="detail-sub">Позиция {escape(str(detail["Position"]))} · {escape(str(detail["Keyword"]))} · {escape(str(detail["Date"]))}</div>''', unsafe_allow_html=True)
        if len(page_results) > 1:
            st.dataframe(page_results[["Position", "Keyword"]].rename(columns={"Position": "Позиция", "Keyword": "Запрос"}), hide_index=True, width="stretch")
        status = "Нет принятого анализа" if detail["Status"] not in ("complete", "supplemental") else relevance_labels.get(detail["Relevance"], "Нужна проверка")
        st.write("**Оценка:** " + status)
        if detail["Status"] not in ("complete", "supplemental"):
            st.info(friendly_error(detail["Error"]))
            st.write("**Бренды:** Не удалось определить")
        else:
            st.write("**Бренды:** " + (str(detail["Brands"]) if detail["Brands"] else "Не найдены при анализе"))
            if detail["Review note"]:
                st.caption("Основание оценки: " + detail["Review note"])
            elif detail["Evidence"]:
                st.caption("Подтверждение на странице: " + str(detail["Evidence"]))
            elif detail["Relevance"] == "no":
                st.caption("Причина оценки не сохранена, требуется дополнительная проверка.")
        contact = detail["Public contact candidate"] or detail["Contact"]
        if contact:
            st.write("**Возможный контакт:**")
            show_contact(contact)
            st.caption("Публичный адрес, его назначение для партнёрств не подтверждено.")
        else:
            st.write("**Возможный контакт:** " + ("Не найден" if detail["Status"] in ("complete", "supplemental") else "Не удалось определить"))
        contact_page = detail["Contact page"]
        if contact_page:
            st.link_button("Страница контактов ↗", str(contact_page))
        if detail["Status"] == "complete" and detail["Error"]:
            st.caption(friendly_error(detail["Error"]))
        source_labels = {"restored_from_google_web": "Восстановлена провайдером через Google Web", "original_or_verification_unavailable": "Исходная либо результат проверки недоступен", "verification_not_requested": "Проверка источника не запрашивалась", "unknown": "Неизвестен", "fictional_demo": "Демо-данные"}
        st.caption("Источник позиции: " + source_labels.get(str(detail["SERP source"]), str(detail["SERP source"])))
        page_source = {"direct_or_unknown": "Страница сайта или источник не указан", "fictional_demo": "Демо-данные"}.get(str(detail["Page source"]), str(detail["Page source"]))
        st.caption("Источник содержимого: " + page_source)
    safe = presentation[[*columns, "Источник позиции", "Примечание к проверке"]].map(safe_cell)
    csv_data = safe.to_csv(index=False).encode("utf-8-sig")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Результаты"
    sheet.append(list(safe.columns))
    for row in safe.itertuples(index=False, name=None): sheet.append(list(row))
    for label in ("Ссылка на страницу", "Источник контакта", "Страница контактов"):
        if label in safe.columns:
            column = list(safe.columns).index(label) + 1
            for row in range(2, sheet.max_row + 1):
                cell = sheet.cell(row, column)
                if isinstance(cell.value, str) and cell.value.startswith(("https://", "http://")):
                    cell.hyperlink = cell.value
                    cell.style = "Hyperlink"
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    output = BytesIO()
    workbook.save(output)
    x, y, _ = st.columns([1, 1, 4])
    with x: st.download_button("↓ Скачать CSV", csv_data, ("demo-results.csv" if is_demo else "live-results.csv"), "text/csv", width="stretch")
    with y: st.download_button("↓ Скачать Excel", output.getvalue(), ("demo-results.xlsx" if is_demo else "live-results.xlsx"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")

if partial_rows:
    partial_view = pd.DataFrame([dict(row) for row in partial_rows])
    partial_view = partial_view[partial_view["Run"] == partial_view["Run"].max()].copy()
    incomplete_count = partial_view["Keyword"].nunique()
    partial_date = str(partial_view["Date"].max())
    with st.expander(f"Неполные результаты за {partial_date}: {incomplete_count} запросов"):
        st.caption("По этим запросам получены не все результаты. Позиции сохранены отдельно и требуют проверки.")
        partial_view = partial_view.loc[~partial_view["URL"].map(excluded_from_prospects).astype(bool)]
        partial_view = partial_view.drop_duplicates(subset=["Keyword", "URL"])
        partial_view["Brands"] = partial_view["Brands"].apply(lambda value: ", ".join(json.loads(value)) if isinstance(value, str) and value else "")
        partial_view["Relevance"] = partial_view["Relevance"].map(relevance_labels).fillna("Нет анализа")
        partial_view = partial_view.rename(columns={**column_labels, "Run": "Запуск", "Note": "Причина проверки"})
        partial_columns = ["Ссылка на страницу", "Позиция", "Запрос", "Оценка", "Бренды", "Причина проверки"]
        st.dataframe(partial_view[partial_columns], hide_index=True, width="stretch", column_config={"Ссылка на страницу": st.column_config.LinkColumn("Ссылка на страницу", display_text=r"https?://([^/]+).*")})

st.markdown('<div class="footer"><span>✳ &nbsp; Affiliate Finder</span><span>Просмотр сохранённых результатов без новых запросов</span></div>', unsafe_allow_html=True)

