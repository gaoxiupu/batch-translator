import streamlit as st
import pandas as pd
import os
import time
import io
import zipfile
import extra_streamlit_components as stx
from utils.translator import translate_text

# Page Configuration
st.set_page_config(
    page_title="Batch-LLM-Translator",
    page_icon="🌐",
    layout="wide"
)

# Initialize Session State
if 'is_processing' not in st.session_state:
    st.session_state.is_processing = False
if 'processed_files' not in st.session_state:
    st.session_state.processed_files = [] # List of tuples: (filename, dataframe)

def main():
    show_translator_app()

def show_translator_app():
    st.title("🌐 Batch-LLM-Translator")
    
    # Initialize Cookie Manager
    cookie_manager = stx.CookieManager()
    
    # --- Sidebar Configuration ---
    with st.sidebar:
        st.header("⚙️ 设置 (Settings)")
        
        # New model options
        model_option = st.selectbox(
            "1. 选择模型 (Model)",
            ("gemini-2.5-flash", "deepseek v3.2", "glm-4.6", "kimi-k2")
        )
        
        # Retrieve API Key from cookie if available
        cookie_api_key = cookie_manager.get(cookie="api_key_v1")
        
        # Initialize session state for API Key if not present
        if 'api_key_input' not in st.session_state:
            st.session_state.api_key_input = cookie_api_key if cookie_api_key else ""

        api_key = st.text_input(
            "2. API Key",
            value=st.session_state.api_key_input,
            type="password",
            help="输入对应模型的 API Key。系统会自动保存到浏览器 Cookies 中。",
            key="api_key_widget"
        )
        
        # Save API Key to cookie when changed
        if api_key != st.session_state.api_key_input:
            st.session_state.api_key_input = api_key
            cookie_manager.set("api_key_v1", api_key, key="set_api_key")
        
        # Supported Languages List
        LANGUAGES = [
            "Simplified Chinese", "Traditional Chinese", "English", "Japanese", "Korean",
            "Vietnamese", "Thai", "Indonesian", "Malay", "Filipino", "Khmer", "Lao", "Burmese",
            "French", "German", "Spanish", "Italian", "Portuguese", "Russian",
            "Ukrainian", "Polish", "Dutch", "Turkish", "Greek", "Hebrew", "Arabic", "Hindi",
            "Albanian", "Armenian", "Austrian German", "Basque", "Belarusian", "Bosnian", "Bulgarian",
            "Catalan", "Croatian", "Czech", "Danish", "Estonian", "Finnish", "Galician", "Georgian",
            "Hungarian", "Icelandic", "Irish", "Latvian", "Lithuanian", "Luxembourgish", "Macedonian",
            "Maltese", "Norwegian", "Romanian", "Serbian", "Slovak", "Slovenian", "Swedish", "Welsh"
        ]
        
        target_lang = st.selectbox(
            "3. 目标语言 (Target Language)",
            options=LANGUAGES,
            index=0, # Defaults to Simplified Chinese
            help="Select the target language. You can type to search."
        )
        
        st.divider()
        st.info("ℹ️ v1.3 by Factory Droid")

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
                
                # BATCH PROCESSING LOGIC
                # We process in chunks to balance Rate Limits vs Context Window.
                # A safe chunk size is 50 lines. 
                # This reduces API calls by 50x (e.g. 1000 lines -> 20 calls), satisfying "avoid too many requests".
                BATCH_SIZE = 50 
                
                for start_idx in range(0, total_rows, BATCH_SIZE):
                    end_idx = min(start_idx + BATCH_SIZE, total_rows)
                    batch_df = df.iloc[start_idx:end_idx]
                    
                    # Prepare batch text
                    # We use a special separator or just newlines.
                    # Warning: If source text contains newlines, this might be tricky.
                    # But assuming standard CSV content (titles, short descriptions).
                    batch_texts = batch_df[source_col].astype(str).tolist()
                    
                    # Remove internal newlines in cells to avoid confusion? 
                    # Or we just hope the LLM is smart enough.
                    # Safer: Replace internal newlines with a placeholder if needed, but for now simple join.
                    batch_input = "\n".join([t.replace('\n', ' ') for t in batch_texts])
                    
                    st.write(f"Processing batch {start_idx}-{end_idx} ({len(batch_texts)} lines)...")
                    
                    # Call API
                    translation_block = translate_text(batch_input, lang, model, key)
                    
                    # Process Output
                    if translation_block.startswith("[Error"):
                        # If error, fill batch with error message
                        translated_lines = [translation_block] * len(batch_texts)
                    else:
                        translated_lines = translation_block.strip().split('\n')
                        
                        # Handle mismatch: 
                        # If LLM returns fewer lines, we might have lost data.
                        # If more lines, maybe it added extra.
                        if len(translated_lines) != len(batch_texts):
                            st.warning(f"Batch mismatch: Input {len(batch_texts)} lines, Output {len(translated_lines)} lines. Attempting to align.")
                            # Pad or truncate
                            if len(translated_lines) < len(batch_texts):
                                translated_lines += [""] * (len(batch_texts) - len(translated_lines))
                            else:
                                translated_lines = translated_lines[:len(batch_texts)]
                    
                    # Update DataFrame
                    df.iloc[start_idx:end_idx, df.columns.get_loc(new_col_name)] = translated_lines
                    
                    # Update status
                    status_text.text(f"正在处理: {file_name} ({end_idx}/{total_rows})")
                    progress_bar.progress((idx + (end_idx / total_rows)) / total_files)
                    
                    # Rate limiting protection
                    time.sleep(1.0) # slightly longer sleep for batch
                
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
