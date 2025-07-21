import streamlit as st
from frontend.ui.utils.client_manager import ClientManager
from frontend.ui.components.chat import ChatInterface   # Chat UI 재사용

st.set_page_config(page_title="GTOne RAG Chat", page_icon="💬", layout="wide")

api_client = ClientManager.get_client()
ChatInterface(api_client).render()