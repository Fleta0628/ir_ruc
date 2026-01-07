import streamlit as st
import sys
import os
import time

# Add parent directory to sys.path to allow importing from task4
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

st.set_page_config(
    page_title="RUC Search",
    page_icon="🎓",
    layout="centered"
)

# Custom CSS for cleaner UI
st.markdown("""
<style>
    .stChatFloatingInputContainer {
        bottom: 20px;
    }
    .stMarkdown a {
        color: #C8102E !important; /* RUC Red */
        text-decoration: none;
    }
    .ref-card {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
        font-size: 0.9em;
        border-left: 4px solid #6c757d; /* Default Low */
    }
    .high-auth { border-left-color: #28a745 !important; }
    .med-auth { border-left-color: #ffc107 !important; }
    .low-auth { border-left-color: #6c757d !important; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource(show_spinner="正在加载知识库和模型，请稍候... (首次加载可能需要 1-2 分钟)")
def get_engine():
    # Lazy import to prevent blocking UI startup
    from task4.answer_engine import AnswerEngine
    return AnswerEngine()

def format_intent(intent_dict):
    # Sort intent by probability
    sorted_intent = sorted(intent_dict.items(), key=lambda x: x[1], reverse=True)
    top_intent = sorted_intent[0][0]
    return f"{top_intent} ({intent_dict[top_intent]:.2f})"

def display_references(references, debug_mode):
    if not references:
        return
        
    for ref in references:
        auth_class = "low-auth"
        if ref["authority"] == "High": auth_class = "high-auth"
        elif ref["authority"] == "Medium": auth_class = "med-auth"
        
        with st.container():
            st.markdown(f"""
            <div class="ref-card {auth_class}">
                <b>[{ref['id']}] <a href="{ref['url']}" target="_blank">{ref['title']}</a></b><br>
                <small>Authority: {ref['authority']} | Score: {ref['score']:.4f}</small>
            </div>
            """, unsafe_allow_html=True)
            
            if debug_mode and "details" in ref:
                with st.expander(f"Debug Info for [{ref['id']}]"):
                    st.json(ref["details"])
                    st.text(ref["details"].get("raw_content", ""))

def main():
    st.title("🎓 Enhanced RUC Search")
    st.caption("Data-Centric AI 驱动的校园问答引擎 | Powered by Qwen2.5 & RAG")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Sidebar
    with st.sidebar:
        st.header("Settings")
        debug_mode = st.toggle("Debug Mode", value=False)
        st.markdown("---")
        st.markdown("**About**")
        st.markdown("本项目利用 PageRank 与 LLM 增强技术，提供更精准、权威的人大校园搜索服务。")

    # Display History
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "references" in message:
                st.markdown("---")
                st.markdown("### 📚 References")
                display_references(message["references"], debug_mode)

    # Input
    if prompt := st.chat_input("Ask something about RUC..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            # Placeholder for streaming
            status_container = st.status("Thinking...", expanded=True)
            response_placeholder = st.empty()
            full_response = ""
            references = []
            
            try:
                engine = get_engine()
                # Stream Generator
                stream = engine.generate_answer_stream(prompt)
                
                # First yield is metadata
                try:
                    meta = next(stream)
                    if meta["type"] == "meta":
                        intent = meta["intent"]
                        references = meta["references"]
                        retrieval_time = meta["retrieval_time"]
                        
                        # Update Status
                        with status_container:
                            st.write(f"**🎯 Detected Intent**: {format_intent(intent)}")
                            st.write(f"**⚡ Retrieval Time**: {retrieval_time:.4f}s")
                            st.write(f"**📚 Documents Found**: {len(references)}")
                        
                        status_container.update(label="Reasoning Complete", state="complete", expanded=False)
                except StopIteration:
                    st.error("Retrieval failed to return metadata.")
                    meta = {}
                except Exception as e:
                    # Catch retrieval errors specifically
                    st.error(f"Retrieval Error: {e}")
                    raise e
                
                # Stream Content
                for chunk in stream:
                    if chunk["type"] == "content":
                        full_response += chunk["content"]
                        response_placeholder.markdown(full_response + "▌")
                
                response_placeholder.markdown(full_response)
                
                # Display References
                if references:
                    st.markdown("---")
                    st.markdown("### 📚 References")
                    display_references(references, debug_mode)
                
                # Save to history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": full_response,
                    "references": references
                })
                
            except Exception as e:
                st.error(f"An error occurred: {e}")
                # Print to terminal as well for debugging
                print(f"ERROR: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
