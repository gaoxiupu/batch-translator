import streamlit as st
import pandas as pd
import os
import time
import io
import zipfile
import streamlit_authenticator as stauth
from utils.translator import translate_text

# Page Configuration
st.set_page_config(
    page_title="Batch-LLM-Translator",
    page_icon="🌐",
    layout="wide"
)

# --- User Configuration ---
# In a production environment, it is best to use st.secrets or environmental variables.
# For quick setup, we define a default user here.
# Admin Password is: 123456
DEFAULT_CONFIG = {
    'credentials': {
        'usernames': {
            'admin': {
                'email': 'admin@example.com',
                'name': 'Admin User',
                'password': '$2b$12$J6w1/0s0E2k3KcwsWWHA2OdEVsTI0ilCBG/ECGqXZKJF8C5ppZJ6.' # 123456
            }
        }
    },
    'cookie': {
        'expiry_days': 30,
        'key': 'some_random_signature_key',
        'name': 'batch_translator_login'
    }
}

# Initialize Session State
if 'is_processing' not in st.session_state:
    st.session_state.is_processing = False
if 'processed_files' not in st.session_state:
    st.session_state.processed_files = [] # List of tuples: (filename, dataframe)

def main():
    
    # --- Authentication ---
    authenticator = stauth.Authenticate(
        DEFAULT_CONFIG['credentials'],
        DEFAULT_CONFIG['cookie']['name'],
        DEFAULT_CONFIG['cookie']['key'],
        DEFAULT_CONFIG['cookie']['expiry_days']
    )

    try:
        authenticator.login('main')
    except Exception as e:
        st.error(e)

    if st.session_state["authentication_status"]:
        # Show Main App
        with st.sidebar:
            st.write(f"Welcome *{st.session_state['name']}*")
            authenticator.logout('Logout', 'main')
            st.divider()
        
        show_translator_app()
        
    elif st.session_state["authentication_status"] is False:
        st.error('Username/password is incorrect')
    elif st.session_state["authentication_status"] is None:
        st.warning('Please enter your username and password')

def show_translator_app():
    st.title("🌐 Batch-LLM-Translator")
    
    # --- Sidebar Configuration ---
    with st.sidebar:
        st.header("⚙️ 设置 (Settings)")
        
        model_option = st.selectbox(
            "1. 选择模型 (Model)",
            ("DeepSeek", "Gemini", "GLM (智谱)", "Kimi (Moonshot)")
        )
        
        api_key = st.text_input(
            "2. API Key",
            type="password",
            help="输入对应模型的 API Key。Key 仅保存在内存中，刷新页面后失效。"
        )
        
        target_lang = st.text_input(
            "3. 目标语言 (Target Language)",
            value="Simplified Chinese",
            placeholder="e.g., English, Japanese, French"
        )
        
        st.divider()
        st.info("ℹ️ v1.2 by Factory Droid (Secured)")

    # --- Main Area ---
    
    # File Uploader
    uploaded_files = st.file_uploader(
        "📂 上传 CSV 文件 (Upload CSV)", 
        type=['csv'], 
        accept_multiple_files=True,
        help="支持拖拽上传。请确保文件第一列为待翻译内容。"
    )

    # File List & Action
    if uploaded_files:
        st.subheader("📋 待处理列表")
        
        # Display file stats
        file_data = []
        for f in uploaded_files:
            file_data.append({"Filename": f.name, "Size (KB)": round(f.size / 1024, 2)})
        st.table(pd.DataFrame(file_data))

        # Start Button
        start_btn = st.button("▶️ 开始翻译 (Start Translation)", type="primary", disabled=st.session_state.is_processing)
        
        if start_btn:
            if not api_key:
                st.error("❌ 请先在左侧输入 API Key！")
            elif not target_lang:
                st.error("❌ 请输入目标语言！")
            else:
                # Clear previous results
                st.session_state.processed_files = []
                process_files(uploaded_files, model_option, api_key, target_lang)

    # --- Download Area ---
    if st.session_state.processed_files:
        st.divider()
        st.subheader("📥 下载结果 (Download Results)")
        
        # 1. Download as ZIP (if multiple files)
        if len(st.session_state.processed_files) > 1:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for fname, df_res in st.session_state.processed_files:
                    csv_data = df_res.to_csv(index=False).encode('utf-8')
                    zf.writestr(fname, csv_data)
            
            st.download_button(
                label="📦 打包下载所有文件 (.zip)",
                data=zip_buffer.getvalue(),
                file_name="translated_files.zip",
                mime="application/zip",
                type="primary"
            )
            st.caption("或者单独下载：")

        # 2. Individual Downloads
        for fname, df_res in st.session_state.processed_files:
            csv_data = df_res.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"📄 下载 {fname}",
                data=csv_data,
                file_name=fname,
                mime="text/csv"
            )

def process_files(files, model, key, lang):
    st.session_state.is_processing = True
    
    # Progress placeholder
    progress_bar = st.progress(0)
    status_text = st.empty()
    console = st.expander("📟 运行日志 (Console Log)", expanded=True)
    
    total_files = len(files)
    
    with console:
        st.write(f"[INFO] 开始处理 {total_files} 个文件...")
        
        for idx, file in enumerate(files):
            file_name = file.name
            st.write(f"--- [FILE {idx+1}/{total_files}] {file_name} ---")
            status_text.text(f"正在处理: {file_name}...")
            
            try:
                # Reset file pointer
                file.seek(0)
                
                # Read CSV
                df = pd.read_csv(file)
                
                if df.empty:
                    st.warning(f"⚠️ 文件 {file_name} 为空，跳过。")
                    continue
                
                # Identify source column
                source_col = df.columns[0]
                new_col_name = f"Translated_{lang}"
                
                # Initialize new column
                df[new_col_name] = ""
                
                total_rows = len(df)
                
                # Iterate and translate
                for row_idx, row in df.iterrows():
                    source_text = row[source_col]
                    
                    # Call API
                    translation = translate_text(source_text, lang, model, key)
                    
                    # Update DataFrame
                    df.at[row_idx, new_col_name] = translation
                    
                    # Update status
                    if row_idx % 5 == 0 or row_idx == total_rows - 1:
                        status_text.text(f"正在处理: {file_name} ({row_idx+1}/{total_rows})")
                    
                    # Rate limiting protection
                    time.sleep(0.2) 
                
                # Store in session state instead of saving to disk
                base_name = os.path.splitext(file_name)[0]
                safe_lang = lang.replace(" ", "_")
                new_filename = f"{base_name}_{safe_lang}.csv"
                
                st.session_state.processed_files.append((new_filename, df))
                
                st.success(f"✅ 完成处理: {file_name}")
                
            except Exception as e:
                st.error(f"❌ 处理文件 {file_name} 时出错: {str(e)}")
            
            # Update main progress bar
            progress_bar.progress((idx + 1) / total_files)
            
    st.session_state.is_processing = False
    status_text.text("✨ 所有任务已完成！请在下方下载结果。")
    st.balloons()

if __name__ == "__main__":
    main()
