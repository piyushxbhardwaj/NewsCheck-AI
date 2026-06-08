import streamlit as st
import requests
import time
import os
import plotly.graph_objects as go
from datetime import datetime

# Set page config
st.set_page_config(
    page_title="NewsCheck AI - Fact Checker",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/api")

# Custom CSS for gorgeous design
st.markdown("""
<style>
    .reportview-container {
        background: #f8f9fa;
    }
    .metric-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        margin-bottom: 15px;
        border-left: 5px solid #007bff;
    }
    .verdict-TRUE {
        background-color: #d4edda;
        color: #155724;
        padding: 6px 12px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }
    .verdict-LIKELY_TRUE {
        background-color: #d1ecf1;
        color: #0c5460;
        padding: 6px 12px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }
    .verdict-MISLEADING {
        background-color: #fff3cd;
        color: #856404;
        padding: 6px 12px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }
    .verdict-UNVERIFIED {
        background-color: #e2e3e5;
        color: #383d41;
        padding: 6px 12px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }
    .verdict-LIKELY_FALSE {
        background-color: #f8d7da;
        color: #721c24;
        padding: 6px 12px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }
    .verdict-FALSE {
        background-color: #f5c6cb;
        color: #721c24;
        padding: 6px 12px;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }
    .source-card {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        padding: 10px 15px;
        border-radius: 8px;
        margin-bottom: 10px;
    }
    .source-header {
        font-weight: bold;
        font-size: 14px;
        margin-bottom: 5px;
    }
    .source-snippet {
        font-style: italic;
        font-size: 13px;
        color: #6c757d;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to get badge class
def get_verdict_badge(verdict: str):
    v = verdict.replace(" ", "_").upper()
    return f'<span class="verdict-{v}">{verdict}</span>'

# Helper to create a Gauges Chart
def create_gauge(score: int):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = score,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Credibility Score", 'font': {'size': 20}},
        gauge = {
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "#1e293b"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 40], 'color': '#f8d7da'},
                {'range': [40, 70], 'color': '#fff3cd'},
                {'range': [70, 100], 'color': '#d4edda'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': score
            }
        }
    ))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
    return fig

# Main Navigation
st.title("🔍 NewsCheck AI")
st.markdown("### Intelligent Fact-Checking & Credibility Verification")

# Fetch history
history = []
stats = {"total_checked": 0, "average_credibility": 0.0, "verdict_breakdown": {}}

try:
    history_res = requests.get(f"{BACKEND_URL}/history")
    if history_res.status_code == 200:
        history = history_res.json()
        
    stats_res = requests.get(f"{BACKEND_URL}/stats")
    if stats_res.status_code == 200:
        stats = stats_res.json()
except Exception as e:
    st.sidebar.error("Could not connect to the backend server. Make sure it is running.")

# Sidebar History & Stats
st.sidebar.header("Platform Stats")
col1, col2 = st.sidebar.columns(2)
col1.metric("Total Checked", stats.get("total_checked", 0))
col2.metric("Avg Credibility", f"{stats.get('average_credibility', 0)}%")

st.sidebar.divider()
st.sidebar.header("Verification History")

selected_article_id = None
if not history:
    st.sidebar.info("No previous checks found.")
else:
    for idx, item in enumerate(history):
        btn_label = f"{item['title'][:35]}..." if len(item['title']) > 35 else item['title']
        badge_emoji = "✅" if item['verdict'] in ["TRUE", "LIKELY TRUE"] else ("❌" if item['verdict'] in ["FALSE", "LIKELY FALSE"] else "⚠️")
        if st.sidebar.button(f"{badge_emoji} {btn_label}", key=f"hist_{item['id']}"):
            selected_article_id = item['id']

# Main Panel layout
tab1, tab2 = st.tabs(["Analyze New Content", "Review Reports"])

active_article = None

# Load details for selected article
if selected_article_id:
    try:
        res = requests.get(f"{BACKEND_URL}/history/{selected_article_id}")
        if res.status_code == 200:
            active_article = res.json()
            # Switch view focus to report
            st.info(f"Viewing archived report: **{active_article.get('title')}**")
    except Exception as e:
        st.error(f"Error loading report: {e}")

with tab1:
    col_input, col_info = st.columns([2, 1])
    
    with col_input:
        input_type = st.radio("Choose Input Type:", ["News Article URL", "Raw Text Block"])
        
        with st.form("verify_form"):
            url_val = ""
            text_val = ""
            
            if input_type == "News Article URL":
                url_val = st.text_input("News Article URL:", placeholder="https://www.reuters.com/article/example")
            else:
                text_val = st.text_area("Factual Text / Social Media Post:", placeholder="Paste text here...", height=200)
                
            submitted = st.form_submit_button("Start AI Fact-Check")
            
            if submitted:
                if input_type == "News Article URL" and not url_val:
                    st.warning("Please provide a valid URL.")
                elif input_type == "Raw Text Block" and not text_val:
                    st.warning("Please enter some text.")
                else:
                    # Submit Job
                    payload = {}
                    if url_val:
                        payload["url"] = url_val
                    if text_val:
                        payload["text"] = text_val
                        
                    try:
                        with st.spinner("Submitting fact-check job..."):
                            response = requests.post(f"{BACKEND_URL}/verify", json=payload)
                            
                        if response.status_code == 200:
                            job_data = response.json()
                            job_id = job_data.get("job_id")
                            
                            # Polling the status
                            status_container = st.empty()
                            progress_bar = st.progress(0)
                            
                            percent = 0
                            while True:
                                status_res = requests.get(f"{BACKEND_URL}/jobs/{job_id}")
                                if status_res.status_code != 200:
                                    status_container.error("Error retrieving job status.")
                                    break
                                    
                                status_data = status_res.json()
                                status = status_data.get("status")
                                
                                if status == "pending":
                                    status_container.info("🔄 Job queued... waiting for agent start.")
                                    percent = min(percent + 5, 20)
                                elif status == "running":
                                    status_container.warning("🤖 Agents are working (Scraping, Extracting Claims, Researching)...")
                                    percent = min(percent + 10, 85)
                                elif status == "completed":
                                    status_container.success("✅ Fact-check verification completed!")
                                    progress_bar.progress(100)
                                    # Fetch full details
                                    detail_res = requests.get(f"{BACKEND_URL}/history/{job_id}")
                                    if detail_res.status_code == 200:
                                        active_article = detail_res.json()
                                    break
                                elif status == "failed":
                                    status_container.error(f"❌ Job failed: {status_data.get('error')}")
                                    break
                                    
                                progress_bar.progress(percent)
                                time.sleep(3)
                        else:
                            st.error(f"Backend returned error: {response.text}")
                    except Exception as e:
                        st.error(f"Connection failed: {e}")
                        
    with col_info:
        st.markdown("""
        ### How it works
        1. **Article Extractor**: Grabs full text content and metadata from the URL.
        2. **Claim Extractor**: Extracts key verifiable claims out of the text.
        3. **Fact-Check Lookup**: First checks verified platforms (Snopes, Politifact).
        4. **Search & RAG**: Executes targeted web queries and indexes them in a local **FAISS** vector store.
        5. **Fact Verifier**: Evaluates claims against source credibility & relevance scores.
        6. **Bias Detector**: Runs natural language checks for political slant and emotional triggers.
        7. **Report Generator**: Combines scores into an explainable report.
        """)

with tab2:
    if not active_article:
        st.info("Select a past article from the sidebar or run a new check to view detailed reports.")
    else:
        st.header(active_article.get("title", "Analysis Result"))
        if active_article.get("url"):
            st.write(f"**Source URL:** [{active_article['url']}]({active_article['url']})")
            
        st.divider()
        
        # Dashboard Overview Row
        col_gauge, col_bias = st.columns([1, 1])
        
        with col_gauge:
            score = active_article.get("credibility_score", 0)
            verdict = active_article.get("verdict", "UNVERIFIED")
            st.plotly_chart(create_gauge(score), use_container_width=True)
            
            # Big badge
            st.markdown(f"<div style='text-align: center;'><h3>Verdict: {get_verdict_badge(verdict)}</h3></div>", unsafe_allow_html=True)
            
        with col_bias:
            st.subheader("Bias & Tone Assessment")
            st.metric("Political Bias", active_article.get("bias_rating", "Unknown"))
            st.metric("Emotional Tone", active_article.get("tone_rating", "Unknown"))
            
            with st.expander("Analysis Explanation"):
                st.write(active_article.get("bias_explanation", "No explanation available."))
                
        st.divider()
        
        # Executive Summary
        st.subheader("Executive Summary")
        st.write(active_article.get("summary", "No summary generated."))
        
        st.divider()
        
        # Claims Section
        st.subheader("Factual Claims Verification")
        claims = active_article.get("claims", [])
        
        if not claims:
            st.warning("No claims were extracted for verification from this text.")
        else:
            for idx, claim in enumerate(claims, 1):
                verdict_str = claim.get("verdict", "UNVERIFIED")
                claim_expander_title = f"Claim {idx}: {claim['claim_text'][:80]}... - [{verdict_str}]"
                
                with st.expander(claim_expander_title):
                    st.markdown(f"**Full Claim:** {claim['claim_text']}")
                    st.markdown(f"**Verdict:** {get_verdict_badge(verdict_str)}", unsafe_allow_html=True)
                    st.markdown(f"**Analysis:** {claim.get('explanation')}")
                    
                    st.write("**Collected Evidence:**")
                    evs = claim.get("evidences", [])
                    if not evs:
                        st.info("No explicit evidence was found for this specific claim.")
                    else:
                        for ev in evs:
                            # Render evidence cards
                            domain_str = ev.get("source_domain", "Unknown Source")
                            credibility_pct = int(ev.get("source_credibility", 0.5) * 100)
                            relevance_pct = int(ev.get("relevance_score", 0.0) * 100)
                            
                            st.markdown(
                                f"""
                                <div class="source-card">
                                    <div class="source-header">
                                        <a href="{ev.get('source_url')}" target="_blank">{ev.get('source_title', domain_str)}</a>
                                        <span style='float: right; font-size: 12px; color: gray;'>
                                            Domain Trust: {credibility_pct}% | Match: {relevance_pct}%
                                        </span>
                                    </div>
                                    <div class="source-snippet">"{ev.get('snippet')}"</div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                            
        st.divider()
        # Full report markdown
        with st.expander("Show Raw Markdown Report"):
            st.markdown(active_article.get("final_report", "No report text."))
