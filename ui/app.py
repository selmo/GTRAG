import streamlit as st, requests, json
st.title("GTOne RAG Demo")
query = st.text_input("검색어")
if st.button("검색"):
    res = requests.get("http://api:8000/v1/search", params={"q": query})
    for hit in res.json():
        st.write(hit["content"])
        st.caption(f'Score: {hit["score"]:.3f}')
