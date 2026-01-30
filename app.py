import streamlit as st
import pandas as pd
import xmltodict
import io
import zipfile
import os

# Configuração da Página
st.set_page_config(page_title="Portal ServTax", layout="wide", page_icon="📑")

# Aplicação do Padrão Visual (Estilo Rihanna)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&family=Plus+Jakarta+Sans:wght@400;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    h1, h2, h3 {
        font-family: 'Montserrat', sans-serif;
        color: #FF69B4;
    }

    .stButton>button {
        background-color: #FF69B4;
        color: white;
        border-radius: 10px;
        border: none;
        padding: 10px 20px;
        font-weight: bold;
    }

    .stButton>button:hover {
        background-color: #FFDEEF;
        color: #FF69B4;
        border: 1px solid #FF69B4;
    }

    [data-testid="stFileUploadDropzone"] {
        border: 2px dashed #FF69B4;
        background-color: #FFDEEF;
    }
    </style>
    """, unsafe_allow_html=True)

def flatten_dict(d, parent_key='', sep='_'):
    """Processa o dicionário do XML para colunas individuais."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    items.extend(flatten_dict(item, f"{new_key}_{i}", sep=sep).items())
                else:
                    items.append((f"{new_key}_{i}", item))
        else:
            items.append((new_key, v))
    return dict(items)

def extract_xml_from_zip(zip_data, extracted_list):
    """
    Função recursiva para abrir ZIPs dentro de ZIPs e encontrar XMLs.
    """
    with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
        for file_info in z.infolist():
            # Se for um XML, lê o conteúdo
            if file_info.filename.lower().endswith('.xml'):
                with z.open(file_info.filename) as xml_file:
                    extracted_list.append({
                        'name': file_info.filename,
                        'content': xml_file.read()
                    })
            # Se for outro ZIP (recursividade de arquivo)
            elif file_info.filename.lower().endswith('.zip'):
                with z.open(file_info.filename) as inner_zip:
                    extract_xml_from_zip(inner_zip.read(), extracted_list)

def process_files(uploaded_files):
    """Lê arquivos diretos e processa ZIPs recursivamente."""
    xml_contents = []
    
    for uploaded_file in uploaded_files:
        fname = uploaded_file.name.lower()
        content = uploaded_file.read()
        
        if fname.endswith('.xml'):
            xml_contents.append({'name': uploaded_file.name, 'content': content})
        elif fname.endswith('.zip'):
            extract_xml_from_zip(content, xml_contents)
            
    extracted_data = []
    for xml_item in xml_contents:
        try:
            data_dict = xmltodict.parse(xml_item['content'])
            flat_data = flatten_dict(data_dict)
            flat_data['arquivo_origem'] = xml_item['name']
            extracted_data.append(flat_data)
        except Exception as e:
            st.error(f"Erro ao converter {xml_item['name']}: {e}")
            
    return pd.DataFrame(extracted_data)

def main():
    st.title("📑 Portal ServTax")
    st.subheader("Processamento Integral: XMLs e ZIPs (incluindo ZIP dentro de ZIP)")
    
    st.markdown("""
    ---
    ### Como Funciona:
    * **Suporta:** XMLs avulsos, arquivos ZIP simples e **ZIPs aninhados**.
    * **Extração:** Lê todas as tags de serviço do padrão nacional.
    * **Download:** Gera uma planilha única com tudo consolidado.
    ---
    """)

    uploaded_files = st.file_uploader(
        "Arraste XMLs ou arquivos ZIP aqui", 
        type=["xml", "zip"], 
        accept_multiple_files=True
    )

    if uploaded_files:
        with st.spinner('Minerando arquivos e extraindo tags...'):
            df = process_files(uploaded_files)
        
        if not df.empty:
            st.success(f"Sucesso! {len(df)} notas fiscais encontradas no total.")
            st.dataframe(df)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='PortalServTax_Dados')
            
            excel_data = output.getvalue()

            st.download_button(
                label="📥 Baixar Consolidação em Excel",
                data=excel_data,
                file_name="portal_servtax_consolidado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Nenhum XML foi encontrado nos arquivos enviados.")

if __name__ == "__main__":
    main()
