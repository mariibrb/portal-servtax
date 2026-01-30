import streamlit as st
import pandas as pd
import xmltodict
import io

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
    """
    Processa o dicionário do XML de forma recursiva para garantir que todas
    as tags aninhadas tornem-se colunas individuais.
    """
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

def process_xml_files(uploaded_files):
    """
    Lê os arquivos enviados, converte para dicionário e achata a estrutura.
    """
    extracted_data = []
    
    for uploaded_file in uploaded_files:
        try:
            # Garante a leitura do início do arquivo
            uploaded_file.seek(0)
            content = uploaded_file.read()
            
            # Converte XML para Dicionário
            data_dict = xmltodict.parse(content)
            
            # Achata todas as tags (Recursividade total)
            flat_data = flatten_dict(data_dict)
            
            # Adiciona o nome do arquivo para referência
            flat_data['arquivo_origem'] = uploaded_file.name
            extracted_data.append(flat_data)
        except Exception as e:
            st.error(f"Erro ao processar {uploaded_file.name}: {e}")
            
    if extracted_data:
        return pd.DataFrame(extracted_data)
    return pd.DataFrame()

def main():
    st.title("📑 Portal ServTax")
    st.subheader("Processamento de NFS-e Nacional (Extração Integral de Tags)")
    
    st.markdown("""
    ---
    ### Passo a Passo:
    1. Faça o upload de um ou mais arquivos **XML** de NFS-e.
    2. O sistema lerá **todas** as tags disponíveis no arquivo automaticamente.
    3. Visualize a tabela gerada abaixo.
    4. Clique no botão de download para gerar o arquivo **Excel**.
    ---
    """)

    # Componente de Upload
    uploaded_files = st.file_uploader(
        "Arraste os arquivos XML aqui", 
        type=["xml"], 
        accept_multiple_files=True
    )

    if uploaded_files:
        with st.spinner('Processando arquivos...'):
            df = process_xml_files(uploaded_files)
        
        if not df.empty:
            st.success(f"Sucesso! {len(df)} notas processadas.")
            
            # Preview dos dados
            st.write("### Visualização dos Dados Extraídos")
            st.dataframe(df)

            # Geração do Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='PortalServTax_Dados')
            
            excel_data = output.getvalue()

            st.download_button(
                label="📥 Baixar Dados em Excel",
                data=excel_data,
                file_name="portal_servtax_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Nenhum dado válido foi extraído dos XMLs enviados.")

if __name__ == "__main__":
    main()
